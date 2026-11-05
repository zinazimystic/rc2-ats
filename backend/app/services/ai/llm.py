"""DeepSeek (OpenAI-compatible /chat/completions) client over raw httpx, with JSON-mode, JSON repair, retries and caching."""
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


# --------------------------------------------------------------------------- JSON repair
def _strip_fences(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S | re.I)
    if m:
        s = m.group(1)
    if not s.startswith(("{", "[")):  # tolerate chatter around the JSON object
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            s = s[a : b + 1]
        elif a >= 0:
            s = s[a:]
    return s


def _scan(s: str) -> tuple[list[str], int]:
    """Open brackets (as their closers) at the end of `s`, and the index just after the last complete value/comma."""
    stack: list[str] = []
    in_str = esc = False
    safe = 0
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            safe = i + 1
        elif ch == ",":
            safe = i
    return stack, safe


def _close_truncated(s: str) -> str:
    """Best effort for output cut off by max_tokens: drop the dangling fragment and close the open brackets."""
    stack, safe = _scan(s)
    if not stack:
        return s
    cut = s[:safe] if safe else s
    stack, _ = _scan(cut)
    return cut.rstrip().rstrip(",") + "".join(reversed(stack))


def _no_trailing_commas(s: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", s)


def parse_json_lenient(content: str):
    """Parse model output into a Python object, repairing the usual damage: markdown fences, prose around the object,
    trailing commas, Python literals and truncated output (unclosed brackets). Raises ValueError when hopeless."""
    text = _strip_fences(content)
    literals = re.sub(r"\bNone\b", "null", re.sub(r"\bTrue\b", "true", re.sub(r"\bFalse\b", "false", text)))
    candidates = [text, _no_trailing_commas(text), _no_trailing_commas(literals), _no_trailing_commas(_close_truncated(text)),
                  _no_trailing_commas(_close_truncated(literals))]
    last: Exception | None = None
    for cand in candidates:
        try:
            return json.loads(cand)
        except ValueError as exc:
            last = exc
    raise ValueError(f"not valid JSON: {last}")


_REDACT = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"), (re.compile(r"\+?\d[\d\s().-]{7,}\d"), "[number]")]


def _snippet(content: str, n: int = 300) -> str:
    t = re.sub(r"\s+", " ", content or "")
    for rx, rep in _REDACT:
        t = rx.sub(rep, t)
    return t[:n]


# --------------------------------------------------------------------------- transport
def _post(payload: dict) -> dict:
    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key.strip()}", "Content-Type": "application/json"}
    last: Exception | None = None
    for attempt in range(4):
        try:
            with _sem:
                r = httpx.post(url, headers=headers, json=payload, timeout=settings.llm_timeout_seconds)
        except httpx.TransportError as exc:  # connect/read timeouts, proxy errors, protocol errors
            last = exc
            if attempt >= 1 and not isinstance(exc, httpx.TimeoutException):
                break  # blocked network / refused connection: fail fast, callers degrade to rules
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


def _call(model_name: str, messages: list[dict], max_tokens: int) -> dict:
    return _post(
        {
            "model": model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": max_tokens,
        }
    )


def json_call(
    system: str, user: str, model: type[T], *, max_tokens: int = 4000, cache_kind: str | None = None, refresh: bool = False
) -> T:
    """Ask the LLM for a JSON object and validate it against `model`.

    Robustness: output is repaired (fences, prose, trailing commas, truncation), validated, retried with the validation
    error plus an instruction to be more compact (and a larger token budget), and finally retried once on
    `settings.deepseek_fallback_model` when configured. `refresh=True` bypasses (then overwrites) the cached answer.
    Every failed attempt is logged at WARNING with the reason, finish_reason and a redacted 300-char snippet; callers only
    ever see LLMError / LLMUnavailable."""
    if not llm_available():
        raise LLMUnavailable("No LLM configured (set DEEPSEEK_API_KEY).")
    key = cache.make_key("llm", cache_kind or "", settings.deepseek_model, model.__name__, system, user) if cache_kind else None
    if key and not refresh:
        hit = cache.get(key)
        if hit and "json" in hit:
            try:
                return model.model_validate(hit["json"])
            except ValidationError:
                pass
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    bigger = min(max_tokens * 2, 16000)
    plan = [(settings.deepseek_model, max_tokens), (settings.deepseek_model, bigger), (settings.deepseek_model, bigger)]
    fallback = (settings.deepseek_fallback_model or "").strip()
    if fallback and fallback != settings.deepseek_model:
        plan.append((fallback, bigger))
    error_note = ""
    last_reason = "no attempt"
    for attempt, (model_name, tokens) in enumerate(plan, start=1):
        msgs = list(messages)
        if error_note:
            msgs.append({"role": "user", "content": error_note})
        data = _call(model_name, msgs, tokens)
        content, finish = "", None
        try:
            choice = data["choices"][0]
            content = (choice.get("message", {}).get("content") or "").strip()
            finish = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError):
            last_reason = "malformed provider response"
            error_note = "The previous reply was malformed. Reply with a single valid json object."
            log.warning("LLM %s attempt %s: %s", model_name, attempt, last_reason)
            continue
        if not content:
            last_reason = f"empty output (finish_reason={finish})"
            error_note = "The previous reply was empty. Reply with a compact, complete json object."
            log.warning("LLM %s attempt %s: %s", model_name, attempt, last_reason)
            continue
        try:
            parsed = parse_json_lenient(content)
            if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
                parsed = parsed[0]
            result = model.model_validate(parsed)
        except (ValueError, ValidationError) as exc:
            last_reason = f"{type(exc).__name__}: {str(exc)[:160]}"
            error_note = (
                f"The previous json was invalid ({str(exc)[:300]})."
                + (" The reply was cut off: be much more compact (shorter text, at most 30 skills, 8 roles)." if finish == "length" else "")
                + " Reply again with ONLY one compact, valid json object matching the schema."
            )
            log.warning("LLM %s attempt %s failed: %s | finish_reason=%s | output=%r", model_name, attempt, last_reason, finish, _snippet(content))
            continue
        if finish == "length":
            log.warning("LLM %s attempt %s: output was cut off but repaired (finish_reason=length)", model_name, attempt)
        if key:
            cache.put(key, cache_kind or "llm", {"json": result.model_dump(mode="json")}, overwrite=refresh)
        return result
    log.warning("LLM gave no usable JSON after %s attempts: %s", len(plan), last_reason)
    raise LLMError("The LLM did not return usable JSON.")
