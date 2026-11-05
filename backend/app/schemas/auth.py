from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORM, Role


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)
    role: Role
    invite_code: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if not v:
            raise ValueError("Name is required")
        return v

    @field_validator("password")
    @classmethod
    def _password_rules(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(ORM):
    id: UUID
    email: str
    full_name: str
    role: Role
    created_at: datetime
    email_verified: bool = False  # read from User.email_verified (property)


class EmailCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class HealthComponent(BaseModel):
    ok: bool
    detail: str | None = None


class HealthOut(BaseModel):
    status: str  # ok | degraded
    database: HealthComponent
    database_backend: str  # postgresql | sqlite
    llm: HealthComponent
    llm_model: str | None = None
    embeddings: HealthComponent
    embedding_model: str | None = None
    embedding_dim: int | None = None
