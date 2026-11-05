"""FastAPI dependencies: current user + role guards."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

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


def get_current_user(request: Request, db: DB) -> User:
    token = _token_from_request(request)
    if not token:
        raise Unauthorized("Please sign in to continue")
    user_id = decode_access_token(token)
    if user_id is None:
        raise Unauthorized("Your session has expired. Please sign in again")
    user = db.get(User, user_id)
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
