from __future__ import annotations

import hmac

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.deps import DB, CurrentUser
from app.core.errors import Conflict, Forbidden, TooManyRequests, Unauthorized
from app.core.ratelimit import limiter
from app.core.security import (
    burn_password_check,
    clear_session_cookie,
    create_access_token,
    hash_password,
    set_session_cookie,
    verify_password,
)
from app.models import CandidateProfile, User
from app.schemas.auth import LoginIn, RegisterIn, UserOut
from app.schemas.common import Msg

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_LIMIT = 5
LOGIN_WINDOW = 60.0


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, request: Request, db: DB):
    if body.role == "recruiter" and settings.recruiter_invite_code:
        if not hmac.compare_digest((body.invite_code or "").strip(), settings.recruiter_invite_code):
            raise Forbidden("A valid invite code is required to register as a recruiter", code="invalid_invite_code")
    ip = request.client.host if request.client else "unknown"
    limiter.check(f"register:{ip}", 20, 3600, "Too many sign-ups from this address. Please try again later.")
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise Conflict("An account with this email already exists", code="email_taken")
    user = User(email=body.email, password_hash=hash_password(body.password), full_name=body.full_name, role=body.role)
    db.add(user)
    if body.role == "candidate":
        user.profile = CandidateProfile(links=[], interests=[])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("An account with this email already exists", code="email_taken")
    limiter.hit(f"register:{ip}", 3600)
    set_session_cookie(response, create_access_token(user.id, user.role))
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, request: Request, db: DB):
    ip = request.client.host if request.client else "unknown"
    key = f"login:{ip}:{body.email}"
    limiter.check(key, LOGIN_LIMIT, LOGIN_WINDOW, "Too many failed sign-in attempts. Please wait a minute and try again.")
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        burn_password_check(body.password)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        limiter.hit(key, LOGIN_WINDOW)
        raise Unauthorized("Incorrect email or password", code="invalid_credentials")
    limiter.clear(key)
    set_session_cookie(response, create_access_token(user.id, user.role))
    return user


@router.post("/logout", response_model=Msg)
def logout(response: Response, user: CurrentUser):
    clear_session_cookie(response)
    return Msg(detail="Signed out")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
