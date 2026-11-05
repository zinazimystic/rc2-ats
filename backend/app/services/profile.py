"""Candidate profile serialisation: completion meter and contact checks (computed server-side, no extra queries)."""
from __future__ import annotations

from app.models import CandidateProfile, Resume, User
from app.schemas.contact import ProfileCompletion
from app.schemas.resume import ProfileOut
from app.services import contact_verify

_ITEMS = (
    ("resume", "Upload a resume"),
    ("headline", "Add a headline"),
    ("phone", "Add a phone number"),
    ("location", "Add your location"),
    ("links", "Add a link such as LinkedIn or GitHub"),
    ("interests", "Add your interests"),
    ("email", "Verify your email"),
)


def current_resume(resumes: list[Resume]) -> Resume | None:
    """The newest parsed, non-deleted resume (current one first)."""
    live = [r for r in resumes if r.deleted_at is None and r.parse_status == "parsed"]
    live.sort(key=lambda r: (not r.is_current, -(r.created_at.timestamp() if r.created_at else 0)))
    return live[0] if live else None


def completion(user: User, p: CandidateProfile, resume: Resume | None) -> ProfileCompletion:
    done = {
        "resume": resume is not None,
        "headline": bool((p.headline or "").strip()),
        "phone": bool((p.phone or "").strip()),
        "location": bool((p.location or "").strip()),
        "links": bool(p.links),
        "interests": bool(p.interests),
        "email": user.email_verified_at is not None,
    }
    missing = [label for key, label in _ITEMS if not done[key]]
    return ProfileCompletion(percent=round(100 * sum(done.values()) / len(_ITEMS)), missing=missing)


def resume_phone(resume: Resume | None) -> str | None:
    parsed = (resume.parsed if resume is not None else None) or {}
    return ((parsed.get("contact") or {}).get("phone")) or None


def profile_out(user: User, p: CandidateProfile, resume: Resume | None) -> ProfileOut:
    phone_for_check = p.phone or resume_phone(resume)
    return ProfileOut(
        user_id=user.id, full_name=user.full_name, email=user.email, headline=p.headline, phone=p.phone, location=p.location,
        links=list(p.links or []), interests=list(p.interests or []), talent_pool_opt_in=p.talent_pool_opt_in,
        retention_until=p.retention_until, whatsapp_enabled=bool(p.whatsapp_enabled),
        contact_checks=contact_verify.contact_checks(user, phone_for_check, bool(p.whatsapp_enabled)),
        completion=completion(user, p, resume),
    )
