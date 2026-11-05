from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.deps import DB, CurrentUser, invalidate_user
from app.core.errors import BadRequest, Conflict, Forbidden, ServiceUnavailable, TooManyRequests, Unauthorized
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
from app.db.types import utcnow
from app.schemas.auth import EmailCodeIn, EmailCodeSentOut, LoginIn, RegisterIn, UserOut
from app.schemas.common import Msg
from app.services.mailer import EmailDeliveryError, send_email, verification_email
from app.services.notifications import notify

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_LIMIT = 5
LOGIN_WINDOW = 60.0


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, request: Request, db: DB):
    if body.role == "recruiter" and settings.recruiter_invite_code:
        if not hmac.compare_digest((body.invite_code or "").strip(), settings.recruiter_invite_code):
            raise Forbidden("A valid invite code is required to register as a recruiter", code="invalid_invite_code")
    ip = request.client.host if request.client else "unknown"
    limiter.check(f"register:{ip}", settings.register_rate_limit_per_hour, 3600, "Too many sign-ups from this address. Please try again later.")
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


# ----------------------------------------------------------------------------- email verification
EMAIL_CODE_TTL = timedelta(minutes=15)
EMAIL_CODE_MAX_ATTEMPTS = 5
EMAIL_RESEND_SECONDS = 60
EMAIL_SEND_LIMIT = 5
EMAIL_SEND_WINDOW = 900.0


def _code_hash(user_id, code: str) -> str:
    return hmac.new(f"{settings.jwt_secret}:{user_id}".encode(), code.encode(), hashlib.sha256).hexdigest()


@router.post("/email/send-code", response_model=EmailCodeSentOut)
def send_email_code(db: DB, user: CurrentUser):
    """Create a 6-digit code (stored hashed, valid 15 minutes) and email it over SMTP.
    Without SMTP configured the email is simulated (outbox + in-app notification). A new code can be requested after 60 s."""
    if user.email_verified_at is not None:
        raise Conflict("Your email is already verified.", code="already_verified")
    now = utcnow()
    if user.email_code_expires_at is not None:
        wait = int((user.email_code_expires_at - EMAIL_CODE_TTL + timedelta(seconds=EMAIL_RESEND_SECONDS) - now).total_seconds())
        if wait > 0:
            raise TooManyRequests(f"Please wait {wait} seconds before requesting another code.", code="resend_too_soon",
                                  extra={"retry_after": wait})
    key = f"emailcode:{user.id}"
    limiter.check(key, EMAIL_SEND_LIMIT, EMAIL_SEND_WINDOW, "You've requested too many codes. Please wait a few minutes and try again.")
    code = f"{secrets.randbelow(10**6):06d}"
    previous = (user.email_code_hash, user.email_code_expires_at, user.email_code_attempts)
    user.email_code_hash = _code_hash(user.id, code)
    user.email_code_expires_at = now + EMAIL_CODE_TTL
    user.email_code_attempts = 0
    minutes = int(EMAIL_CODE_TTL.total_seconds() // 60)
    if settings.smtp_enabled:
        subject, text, html_body = verification_email(user.full_name, code, minutes)
        try:
            send_email(user.email, subject, text, html_body)
        except EmailDeliveryError:
            user.email_code_hash, user.email_code_expires_at, user.email_code_attempts = previous
            db.rollback()
            raise ServiceUnavailable("We couldn't send the email right now. Please try again in a moment.", code="email_delivery_failed")
        delivery, detail = "email", f"We've sent a 6-digit code to {user.email}. It expires in {minutes} minutes."
    else:
        body = f"Your verification code is {code}. It expires in {minutes} minutes. This is a demo email: no real email is sent."
        notify(db, type="email_verification", title="Your email verification code (demo)", body=body, user_id=user.id,
               recipient_email=user.email, channel="email_sim")
        notify(db, type="email_code", title=f"Your verification code is {code} (demo email)", body=body, user_id=user.id, link="/profile")
        delivery, detail = "simulated", "Demo mode: no real email is sent. Your code is in your notifications."
    limiter.hit(key, EMAIL_SEND_WINDOW)
    db.commit()
    invalidate_user(user.id)
    return EmailCodeSentOut(detail=detail, delivery=delivery, expires_in_seconds=int(EMAIL_CODE_TTL.total_seconds()),
                            resend_in_seconds=EMAIL_RESEND_SECONDS)


@router.post("/email/verify", response_model=UserOut)
def verify_email(body: EmailCodeIn, db: DB, user: CurrentUser):
    if user.email_verified_at is not None:
        return user
    if not user.email_code_hash or user.email_code_expires_at is None:
        raise BadRequest("Request a verification code first.", code="invalid_code")
    if user.email_code_expires_at < utcnow():
        raise BadRequest("This code has expired. Please request a new one.", code="code_expired")
    if user.email_code_attempts >= EMAIL_CODE_MAX_ATTEMPTS:
        raise BadRequest("Too many incorrect attempts. Please request a new code.", code="code_expired")
    if not hmac.compare_digest(user.email_code_hash, _code_hash(user.id, body.code.strip())):
        user.email_code_attempts += 1
        db.commit()
        invalidate_user(user.id)
        raise BadRequest("That code isn't right. Check it and try again.", code="invalid_code")
    user.email_verified_at = utcnow()
    user.email_code_hash, user.email_code_expires_at, user.email_code_attempts = None, None, 0
    db.commit()
    invalidate_user(user.id)
    return user
