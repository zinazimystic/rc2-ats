"""DeepSeek (OpenAI-compatible /chat/completions) client over raw httpx, with JSON-mode, retries and caching."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.ai import cache

log = logging.getLogger("app.ai.llm")
T = TypeVar("T", bound=BaseModel)

_sem = threading.BoundedSemaphore(4)  # at most 4 concurrent provider calls
_disabled_until = 0.0
_lock = threading.Lock()


class LLMUnavailable(Exception):
    """No API key configured, or the provider is unreachable."""


class LLMError(Exception):
    """The provider answered but the output could not be used after retries."""


def llm_available() -> bool:
    return bool(settings.deepseek_api_key.strip()) and time.time() >= _disabled_until


def _disable(seconds: float) -> None:
    global _disabled_until
    with _lock:
        _disabled_until = time.time() + seconds


def reset() -> None:
    global _disabled_until
    _disabled_until = 0.0


def _strip_fences(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S | re.I)
    if m:
        s = m.group(1)
    if not s.startswith(("{", "[")):  # tolerate chatter around the JSON object
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            s = s[a : b + 1]
    return s


def _post(payload: dict) -> dict:
    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key.strip()}", "Content-Type": "application/json"}
    last: Exception | None = None
    for attempt in range(4):
        try:
            with _sem:
                r = httpx.post(url, headers=headers, json=payload, timeout=settings.llm_timeout_seconds)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.PoolTimeout) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in (401, 402, 403):
            _disable(120)
            raise LLMUnavailable(f"DeepSeek rejected the request ({r.status_code}): check DEEPSEEK_API_KEY / balance.")
        if r.status_code == 429 or r.status_code >= 500:
            last = LLMError(f"DeepSeek returned {r.status_code}")
            time.sleep(min(8, 2 ** attempt))
            continue
        if r.status_code >= 400:
            raise LLMError(f"DeepSeek returned {r.status_code}: {r.text[:200]}")
        try:
            return r.json()
        except ValueError as exc:
            last = exc
    if isinstance(last, LLMError):
        raise last
    _disable(30)
    raise LLMUnavailable(f"DeepSeek is unreachable: {type(last).__name__}")


def json_call(system: str, user: str, model: type[T], *, max_tokens: int = 4000, cache_kind: str | None = None) -> T:
    """Ask the LLM for a JSON object and validate it against `model`. Retries once with the validation error."""
    if not llm_available():
        raise LLMUnavailable("No LLM configured (set DEEPSEEK_API_KEY).")
    key = cache.make_key("llm", cache_kind or "", settings.deepseek_model, model.__name__, system, user) if cache_kind else None
    if key:
        hit = cache.get(key)
        if hit and "json" in hit:
            try:
                return model.model_validate(hit["json"])
            except ValidationError:
                pass
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    error_note = ""
    for attempt in range(3):
        msgs = list(messages)
        if error_note:
            msgs.append({"role": "user", "content": error_note})
        data = _post(
            {
                "model": settings.deepseek_model,
                "messages": msgs,
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": max_tokens,
            }
        )
        try:
            choice = data["choices"][0]
            content = (choice.get("message", {}).get("content") or "").strip()
            finish = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError):
            error_note = "The previous reply was malformed. Reply with a single valid json object."
            continue
        if not content or finish == "length":
            error_note = "The previous reply was empty or cut off. Reply with a shorter, complete json object."
            continue
        try:
            parsed = json.loads(_strip_fences(content))
            result = model.model_validate(parsed)
        except (ValueError, ValidationError) as exc:
            error_note = f"The previous json was invalid ({str(exc)[:300]}). Reply again with only a valid json object matching the schema."
            log.info("LLM output failed validation (attempt %s): %s", attempt + 1, str(exc)[:200])
            continue
        if key:
            cache.put(key, cache_kind or "llm", {"json": result.model_dump(mode="json")})
        return result
    raise LLMError("The LLM did not return usable JSON.")
