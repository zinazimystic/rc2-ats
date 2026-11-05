"""FastAPI dependencies: current user + role guards."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.session import make_transient_to_detached

from app.core.config import settings
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

DB = Annotated[Session, Depends(get_db)]


def _token_from_request(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header[:7].lower() == "bearer " and header[7:].strip():
        return header[7:].strip()
    return request.cookies.get(settings.cookie_name)


# --- tiny per-process cache of the User row (30 s): saves one DB round trip per request. Only plain columns are cached
# (relationships load lazily on the attached copy); anything that changes the row must call invalidate_user().
USER_CACHE_TTL = 30.0
_user_cache: dict[uuid.UUID, tuple[float, dict]] = {}
_user_cache_lock = threading.Lock()


def invalidate_user(user_id: uuid.UUID | None = None) -> None:
    with _user_cache_lock:
        if user_id is None:
            _user_cache.clear()
        else:
            _user_cache.pop(user_id, None)


def _load_user(db: Session, user_id: uuid.UUID) -> User | None:
    now = time.monotonic()
    with _user_cache_lock:
        hit = _user_cache.get(user_id)
    if hit is not None and hit[0] > now:
        user = User(**hit[1])
        make_transient_to_detached(user)
        db.add(user)  # persistent, clean: later changes are tracked and flushed normally
        return user
    user = db.get(User, user_id)
    if user is not None and user.is_active and USER_CACHE_TTL > 0:
        snap = {a.key: getattr(user, a.key) for a in sa_inspect(User).column_attrs}
        with _user_cache_lock:
            _user_cache[user_id] = (now + USER_CACHE_TTL, snap)
    elif user is None or not user.is_active:
        invalidate_user(user_id)
    return user


def get_current_user(request: Request, db: DB) -> User:
    token = _token_from_request(request)
    if not token:
        raise Unauthorized("Please sign in to continue")
    user_id = decode_access_token(token)
    if user_id is None:
        raise Unauthorized("Your session has expired. Please sign in again")
    user = _load_user(db, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Your session is no longer valid. Please sign in again")
    return user


def require_recruiter(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "recruiter":
        raise Forbidden("This action is only available to recruiters")
    return user


def require_candidate(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "candidate":
        raise Forbidden("This action is only available to candidates")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
Recruiter = Annotated[User, Depends(require_recruiter)]
Candidate = Annotated[User, Depends(require_candidate)]
