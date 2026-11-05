from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WhatsAppInfo(BaseModel):
    status: str = "unknown"  # declared | not_declared | unknown
    link: str | None = None
    note: str = "WhatsApp can't be verified automatically; this reflects what the candidate told us."


class PhoneCheck(BaseModel):
    raw: str
    e164: str | None = None
    valid: bool = False
    possible: bool = False
    country_code: str | None = None  # "+92"
    region: str | None = None  # "PK"
    country: str | None = None  # "Pakistan"
    location: str | None = None  # "Lahore" or the country name
    line_type: str = "unknown"  # mobile | landline | voip | toll_free | other | unknown
    national_length: int | None = None
    issues: list[str] = []
    whatsapp: WhatsAppInfo = WhatsAppInfo()


class EmailCheck(BaseModel):
    value: str
    valid_format: bool = False
    verified: bool = False
    verified_at: datetime | None = None


class ContactChecks(BaseModel):
    email: EmailCheck
    phone: PhoneCheck | None = None


class ProfileCompletion(BaseModel):
    percent: int
    missing: list[str] = []
