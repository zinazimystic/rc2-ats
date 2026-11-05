"""Offline contact checks (phonenumbers). Nothing here contacts the person: it validates format, region and line type, and
reports honestly what cannot be verified (WhatsApp, deliverability)."""
from __future__ import annotations

import re

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType, geocoder

from app.core.config import settings
from app.schemas.contact import ContactChecks, EmailCheck, PhoneCheck, WhatsAppInfo

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_TYPES = {
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE: "landline",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "other",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.TOLL_FREE: "toll_free",
    PhoneNumberType.PREMIUM_RATE: "other",
    PhoneNumberType.SHARED_COST: "other",
    PhoneNumberType.PERSONAL_NUMBER: "other",
    PhoneNumberType.PAGER: "other",
    PhoneNumberType.UAN: "other",
    PhoneNumberType.VOICEMAIL: "other",
}


def _country_name(region: str | None) -> str | None:
    if not region:
        return None
    try:
        import pycountry  # type: ignore

        c = pycountry.countries.get(alpha_2=region)
        return c.name if c else region
    except Exception:
        pass
    # offline name via the geocoder: describe a number-less region using the library's own data
    try:
        sample = phonenumbers.example_number(region)
        if sample is not None:
            return geocoder.country_name_for_number(sample, "en") or region
    except Exception:  # pragma: no cover
        pass
    return region


def _whatsapp(e164: str | None, enabled: bool | None) -> WhatsAppInfo:
    digits = re.sub(r"\D", "", e164 or "")
    if enabled is True and digits:
        return WhatsAppInfo(status="declared", link=f"https://wa.me/{digits}")
    if enabled is False:
        return WhatsAppInfo(status="not_declared", link=None)
    return WhatsAppInfo(status="unknown", link=None)


def check_phone(raw: str, default_region: str | None = None, *, whatsapp_enabled: bool | None = None) -> PhoneCheck:
    region_default = (default_region or settings.default_phone_region or "PK").upper()
    raw = (raw or "").strip()
    out = PhoneCheck(raw=raw)
    if not raw:
        out.issues.append("No phone number provided")
        out.whatsapp = _whatsapp(None, whatsapp_enabled)
        return out
    default_name = _country_name(region_default) or region_default
    try:
        num = phonenumbers.parse(raw, None if raw.lstrip().startswith(("+", "00")) else region_default)
    except NumberParseException:
        out.issues.append("This doesn't look like a phone number")
        out.whatsapp = _whatsapp(None, whatsapp_enabled)
        return out
    explicit = raw.lstrip().startswith(("+", "00"))
    region = phonenumbers.region_code_for_number(num) or (region_default if not explicit else None)
    out.country_code = f"+{num.country_code}"
    out.region = region
    out.country = _country_name(region)
    out.possible = phonenumbers.is_possible_number(num)
    out.valid = phonenumbers.is_valid_number(num)
    nsn = phonenumbers.national_significant_number(num)
    out.national_length = len(nsn)
    if out.possible or out.valid:
        out.e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    out.line_type = _TYPES.get(phonenumbers.number_type(num), "unknown")
    if out.valid:
        loc = geocoder.description_for_number(num, "en")
        out.location = loc or out.country
    else:
        out.location = out.country
    if not explicit:
        out.issues.append(f"Missing country code - assumed {default_name} (+{num.country_code})")
    if not out.valid:
        reason = phonenumbers.is_possible_number_with_reason(num)
        label = out.country or "this country"
        if reason not in (phonenumbers.ValidationResult.TOO_SHORT, phonenumbers.ValidationResult.TOO_LONG):  # length is plausible for some number type: compare with a typical mobile
            exp = _expected_length(region)
            if exp and out.national_length < exp:
                reason = phonenumbers.ValidationResult.TOO_SHORT
            elif exp and out.national_length > exp:
                reason = phonenumbers.ValidationResult.TOO_LONG
        if reason == phonenumbers.ValidationResult.TOO_SHORT:
            exp = _expected_length(region)
            out.issues.append(f"Number is too short for {label}" + (f" (expected {exp} digits)" if exp else ""))
        elif reason == phonenumbers.ValidationResult.TOO_LONG:
            exp = _expected_length(region)
            out.issues.append(f"Number is too long for {label}" + (f" (expected {exp} digits)" if exp else ""))
        else:
            out.issues.append(f"This number isn't a valid number for {label}")
    out.whatsapp = _whatsapp(out.e164 if out.valid else None, whatsapp_enabled)
    return out


def _expected_length(region: str | None) -> int | None:
    if not region:
        return None
    try:
        ex = phonenumbers.example_number_for_type(region, PhoneNumberType.MOBILE) or phonenumbers.example_number(region)
        return len(phonenumbers.national_significant_number(ex)) if ex else None
    except Exception:  # pragma: no cover
        return None


def check_email(user, value: str | None = None) -> EmailCheck:
    email = (value if value is not None else getattr(user, "email", "")) or ""
    verified_at = getattr(user, "email_verified_at", None) if user is not None else None
    return EmailCheck(value=email, valid_format=bool(_EMAIL_RE.match(email)), verified=verified_at is not None, verified_at=verified_at)


def contact_checks(user, phone: str | None, whatsapp_enabled: bool | None = None) -> ContactChecks:
    return ContactChecks(
        email=check_email(user),
        phone=check_phone(phone, whatsapp_enabled=whatsapp_enabled) if phone and phone.strip() else None,
    )
