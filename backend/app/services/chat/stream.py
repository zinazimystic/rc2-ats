"""Streaming orchestration: upstream DeepSeek SSE -> output guard -> client SSE events."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.services.chat import faq
from app.services.chat.guards import DEFLECTION, OUTPUT_REFUSAL, SECRET_NOTE, OutputGuard
from app.services.chat.prompt import CANARY, build_system_prompt, static_prompt_text

log = logging.getLogger("app.chat")

RETRY_STATUS = {429, 500, 502, 503, 504}
FALLBACK_EMPTY = "Sorry, I couldn't come up with an answer just now. Could you rephrase your question?"
_GUARD_SHINGLES = OutputGuard.shingles_of(static_prompt_text())


class UpstreamError(Exception):
    def __init__(self, retry_after: int | None = None):
        super().__init__("upstream failure")
        self.retry_after = retry_after


def chat_available() -> bool:
    return settings.chat_enabled and bool(settings.deepseek_api_key.strip())


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@dataclass
class ChatPlan:
    role: str
    history: list[dict]  # sanitised turns (no system message)
    last_user: str = ""
    page: str | None = None
    blocked: str | None = None  # reason code when the request is deflected without calling the model
    secret_shared: bool = False
    usage_remaining: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


async def stream_completion(messages: list[dict]) -> AsyncIterator[tuple[str, str]]:
    """Yield ("token", text) items and finally ("finish", reason). One quick retry on 429/5xx/transport errors before the first token."""
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.chat_model or settings.deepseek_model,
        "messages": messages,
        "stream": True,
        "temperature": 0.4,
        "max_tokens": settings.chat_max_tokens,
        "thinking": {"type": "disabled"},
    }
    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    timeout = httpx.Timeout(60.0, connect=10.0)
    for attempt in (0, 1):
        got_token = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as r:
                    if r.status_code in RETRY_STATUS:
                        if attempt == 0:
                            await asyncio.sleep(0.6)
                            continue
                        ra = r.headers.get("retry-after", "")
                        raise UpstreamError(int(ra) if ra.isdigit() else 20)
                    if r.status_code >= 400:
                        log.warning("chat upstream status %s", r.status_code)
                        raise UpstreamError(None)
                    finish = "stop"
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            choice = json.loads(data)["choices"][0]
                            text = (choice.get("delta") or {}).get("content")
                            reason = choice.get("finish_reason")
                        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                            continue  # malformed chunk
                        if text:
                            got_token = True
                            yield ("token", text)
                        if reason:
                            finish = "length" if reason == "length" else "stop"
                    yield ("finish", finish)
                    return
        except httpx.TransportError as exc:  # timeouts, connection resets, protocol errors
            if not got_token and attempt == 0:
                await asyncio.sleep(0.4)
                continue
            log.warning("chat upstream transport error: %s", type(exc).__name__)
            raise UpstreamError(10) from exc


def _words(text: str) -> list[str]:
    return re.findall(r"\S+\s*", text)


async def _aclose(agen) -> None:
    try:
        await agen.aclose()
    except Exception:  # noqa: BLE001 - best effort
        pass


async def run_chat(plan: ChatPlan, is_disconnected: Callable[[], Awaitable[bool]]) -> AsyncIterator[str]:
    """Yield SSE frames for one chat turn: meta, token*, then done (or error)."""
    started = time.monotonic()
    finish = "stop"
    reason = plan.blocked or ""
    sent = 0
    yield sse("meta", {"id": plan.id, "role": plan.role})
    try:
        if plan.secret_shared:
            sent += 1
            yield sse("token", {"t": SECRET_NOTE + "\n\n"})
        if plan.blocked:
            finish = "blocked"
            for w in _words(DEFLECTION):
                sent += 1
                yield sse("token", {"t": w})
        elif not chat_available():
            reply = faq.answer(plan.last_user) if settings.chat_enabled else ""
            if not reply:
                reason = "offline"
                yield sse("error", {"code": "offline", "message": "I'm offline right now. Please try again a little later.", "retry_after": None})
                return
            finish, reason = "fallback", "no_llm"
            for w in _words(reply):
                sent += 1
                yield sse("token", {"t": w})
                await asyncio.sleep(0.02)
        else:
            guard = OutputGuard(canary=CANARY, shingles=_GUARD_SHINGLES)
            system = build_system_prompt(plan.role, plan.page)
            upstream = stream_completion([{"role": "system", "content": system}, *plan.history])
            ticks = 0
            try:
                async for kind, value in upstream:
                    if kind == "finish":
                        finish = value
                        break
                    ticks += 1
                    if ticks % 8 == 0 and await is_disconnected():
                        reason = "disconnected"
                        return
                    out = guard.feed(value)
                    if guard.tripped:
                        break
                    if out:
                        sent += 1
                        yield sse("token", {"t": out})
            except UpstreamError as exc:
                reason = "upstream_error"
                yield sse("error", {"code": "upstream_busy", "message": "I'm a bit busy right now. Please try again in a moment.",
                                    "retry_after": exc.retry_after})
                return
            finally:
                await _aclose(upstream)
            if guard.tripped:
                reason, finish = f"output_{guard.tripped}", "blocked"
                sent += 1
                yield sse("token", {"t": ("\n\n" if guard.emitted else "") + OUTPUT_REFUSAL})
            else:
                tail = guard.finish()
                if guard.tripped:
                    reason, finish = f"output_{guard.tripped}", "blocked"
                    tail = ("\n\n" if guard.emitted else "") + OUTPUT_REFUSAL
                if tail:
                    sent += 1
                    yield sse("token", {"t": tail})
                if guard.emitted == 0 and not guard.tripped:
                    finish, reason = "fallback", "empty_reply"
                    sent += 1
                    yield sse("token", {"t": FALLBACK_EMPTY})
        yield sse("done", {"finish": finish, "usage_remaining": plan.usage_remaining})
    finally:
        # privacy: only roles, sizes, outcome and timing are logged, never message text
        log.info("chat role=%s turns=%d finish=%s reason=%s events=%d ms=%d", plan.role, len(plan.history), finish, reason or "-",
                 sent, int((time.monotonic() - started) * 1000))
