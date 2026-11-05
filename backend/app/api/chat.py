"""Chat assistant: optional-auth streaming endpoint (SSE) and per-role widget config."""
from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from starlette.background import BackgroundTask

from app.core.deps import _load_user, _token_from_request
from app.core.errors import ServiceUnavailable, TooManyRequests, Unprocessable
from app.core.ratelimit import limiter
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.services.chat.guards import MAX_CONTENT, MAX_TOTAL, detect_injection, prepare_history
from app.services.chat.prompt import FORGED_MARKERS
from app.services.chat.stream import ChatPlan, chat_available, run_chat

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_MESSAGES = 20
MINUTE_LIMIT = {"visitor": 20, "user": 40}
DAY_LIMIT = {"visitor": 300, "user": 1000}
MAX_STREAMS_PER_CLIENT = 2
MAX_STREAMS_GLOBAL = 30

_active: dict[str, int] = {}
_active_lock = threading.Lock()
_active_total = 0


# --------------------------------------------------------------------------- request schema
class ChatMessage(BaseModel):
    role: str
    content: str

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("Messages must come from you or the assistant.")
        return v

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Please type a message.")
        if len(v) > MAX_CONTENT:
            raise ValueError(f"Messages can be at most {MAX_CONTENT} characters.")
        return v


class ChatIn(BaseModel):
    messages: list[ChatMessage]
    page: str | None = None

    @field_validator("messages")
    @classmethod
    def _messages(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if not v:
            raise ValueError("Please type a message.")
        if len(v) > MAX_MESSAGES:
            raise ValueError(f"A conversation can have at most {MAX_MESSAGES} messages. Please start a new chat.")
        if v[-1].role != "user":
            raise ValueError("The last message must be yours.")
        if sum(len(m.content) for m in v) > MAX_TOTAL:
            raise ValueError("This conversation is too long. Please start a new chat.")
        return v

    @field_validator("page")
    @classmethod
    def _page(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 200:
            raise ValueError("Page is too long.")
        return v


# --------------------------------------------------------------------------- viewer + limits
def _viewer(request: Request) -> tuple[str, str | None]:
    """(role, user_id) from a verified token; anything else is a visitor. Never raises."""
    token = _token_from_request(request)
    if not token:
        return "visitor", None
    try:
        user_id = decode_access_token(token)
        if user_id is None:
            return "visitor", None
        with SessionLocal() as db:
            user = _load_user(db, user_id)
            if user is not None and user.is_active and user.role in ("recruiter", "candidate"):
                return user.role, str(user.id)
    except Exception:  # noqa: BLE001 - chat must stay available when auth lookups fail
        pass
    return "visitor", None


def _client_key(request: Request, uid: str | None) -> str:
    return f"user:{uid}" if uid else f"ip:{request.client.host if request.client else 'unknown'}"


def _acquire(key: str) -> None:
    global _active_total
    with _active_lock:
        if _active_total >= MAX_STREAMS_GLOBAL:
            raise ServiceUnavailable("The assistant is busy right now. Please try again in a moment.", code="busy", extra={"retry_after": 5})
        if _active.get(key, 0) >= MAX_STREAMS_PER_CLIENT:
            raise TooManyRequests("You already have chats in progress. Please wait for them to finish.", code="rate_limited",
                                  extra={"retry_after": 5})
        _active[key] = _active.get(key, 0) + 1
        _active_total += 1


def _release_once(key: str) -> Any:
    done = threading.Event()

    def release() -> None:
        global _active_total
        if done.is_set():
            return
        done.set()
        with _active_lock:
            left = _active.get(key, 0) - 1
            if left > 0:
                _active[key] = left
            else:
                _active.pop(key, None)
            _active_total = max(0, _active_total - 1)

    return release


def _check_limits(key: str, signed_in: bool) -> int:
    kind = "user" if signed_in else "visitor"
    minute, day = f"chat:m:{key}", f"chat:d:{key}"
    limiter.check(minute, MINUTE_LIMIT[kind], 60.0, "You're sending messages very quickly. Please wait a moment and try again.")
    limiter.check(day, DAY_LIMIT[kind], 86400.0, "You've reached today's chat limit. Please come back tomorrow.")
    limiter.hit(minute, 60.0)
    limiter.hit(day, 86400.0)
    return max(0, DAY_LIMIT[kind] - limiter.count(day, 86400.0))


# --------------------------------------------------------------------------- endpoints
SUGGESTIONS = {
    "visitor": [
        "What does RC3 Talent Intelligence do?",
        "How do I apply for a job?",
        "How is my data kept private?",
        "How does the platform keep hiring fair?",
    ],
    "candidate": [
        "How can I improve my resume?",
        "Help me prepare for an interview",
        "How does job matching work?",
        "How do I verify my email?",
    ],
    "recruiter": [
        "Help me write a job description",
        "Suggest interview questions for a role",
        "How do scoring and fairness work?",
        "Tips for shortlisting candidates",
    ],
}
GREETINGS = {
    "visitor": "Hi! I'm the RC3 assistant. Ask me about the platform, applying for jobs or hiring.",
    "candidate": "Hi! I can help with your resume, interviews and finding the right job. What would you like to know?",
    "recruiter": "Hi! I can help with job descriptions, interview questions and screening fairly. What do you need?",
}


@router.get("/config")
async def chat_config(request: Request):
    role, _ = await run_in_threadpool(_viewer, request)
    return {
        "max_chars": MAX_CONTENT,
        "max_messages": MAX_MESSAGES,
        "suggestions": SUGGESTIONS[role],
        "greeting": GREETINGS[role],
        "available": chat_available(),
    }


@router.post("/stream")
async def chat_stream(body: ChatIn, request: Request):
    role, uid = await run_in_threadpool(_viewer, request)
    key = _client_key(request, uid)
    remaining = _check_limits(key, uid is not None)

    prepared = prepare_history([m.model_dump() for m in body.messages], forged_markers=FORGED_MARKERS)
    if not prepared.messages or prepared.messages[-1]["role"] != "user":
        raise Unprocessable("Please type a message.", code="validation_error")
    blocked = detect_injection(prepared.user_texts)
    plan = ChatPlan(
        role=role,
        history=prepared.messages,
        last_user=prepared.messages[-1]["content"],
        page=body.page,
        blocked=blocked,
        secret_shared=prepared.secret_shared,
        usage_remaining=remaining,
    )

    _acquire(key)
    release = _release_once(key)

    async def events():
        try:
            async for frame in run_chat(plan, request.is_disconnected):
                yield frame
        finally:
            release()

    return StreamingResponse(
        events(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Encoding": "identity",
        },
        background=BackgroundTask(release),
    )
