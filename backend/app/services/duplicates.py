"""Duplicate-candidate detection (never merges automatically; a recruiter confirms)."""
from __future__ import annotations

import logging
import re

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, undefer

from app.db.types import utcnow
from app.models import Application, CandidateProfile, DuplicateFlag, Resume, User
from app.services.ai import embeddings
from app.services.audit import log_event

log = logging.getLogger("app.duplicates")
COS_MIN = 0.97
FUZZY_MIN = 92


def normalize_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.strip().lower().rsplit("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    else:
        local = local.split("+", 1)[0]
    return f"{local}@{domain}"


def normalize_phone(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 9 else None


def _contact(resume: Resume) -> tuple[str | None, str | None]:
    c = (resume.parsed or {}).get("contact") or {}
    return normalize_email(c.get("email")), normalize_phone(c.get("phone"))


def _ordered(a: User, b: User) -> tuple[User, User]:
    return (a, b) if str(a.id) < str(b.id) else (b, a)


def detect_for_resume(db: Session, resume: Resume) -> list[DuplicateFlag]:
    """Compare against other candidates' current parsed resumes; create pending flags. Caller commits."""
    me = db.get(User, resume.candidate_id)
    if me is None:
        return []
    my_email, my_phone = _contact(resume)
    my_acct = normalize_email(me.email)
    my_text = None
    others = db.scalars(
        select(Resume)
        .where(Resume.candidate_id != resume.candidate_id, Resume.is_current.is_(True), Resume.parse_status == "parsed")
        .options(undefer(Resume.text))
        .limit(1000)
    ).all()
    created: list[DuplicateFlag] = []
    seen: set[str] = set()
    for o in others:
        if str(o.candidate_id) in seen:
            continue
        other = db.get(User, o.candidate_id)
        if other is None or other.role != "candidate":
            continue
        prof = other.profile
        if prof is not None and prof.merged_into_id is not None:
            continue
        reasons: list[str] = []
        sim: float | None = None
        o_email, o_phone = _contact(o)
        if my_email and (my_email == o_email or my_email == normalize_email(other.email)):
            reasons.append("Same email address")
        elif my_acct and o_email and my_acct == o_email:
            reasons.append("Same email address")
        if my_phone and my_phone == o_phone:
            reasons.append("Same phone number")
        if resume.doc_embedding and o.doc_embedding:
            c = embeddings.cosine(resume.doc_embedding, o.doc_embedding)
            if c >= COS_MIN:
                reasons.append(f"Near-identical resume content (embedding similarity {c:.2f})")
                sim = c
        if sim is None and resume.text is not None and o.text:
            my_text = my_text if my_text is not None else (resume.text or "")
            if my_text and len(my_text) > 200:
                r = fuzz.ratio(my_text[:4000], o.text[:4000])
                if r >= FUZZY_MIN:
                    reasons.append(f"Near-identical resume text ({r:.0f}% match)")
                    sim = r / 100.0
        if not reasons:
            continue
        seen.add(str(o.candidate_id))
        a, b = _ordered(me, other)
        existing = db.scalars(
            select(DuplicateFlag).where(DuplicateFlag.candidate_a_id == a.id, DuplicateFlag.candidate_b_id == b.id)
        ).first()
        if existing is not None:
            if existing.status == "pending":  # refresh reasons
                existing.reasons = sorted(set(existing.reasons or []) | set(reasons))
                existing.similarity = max(existing.similarity or 0, sim or 0) or None
            continue
        flag = DuplicateFlag(candidate_a_id=a.id, candidate_b_id=b.id, reasons=reasons, similarity=sim, status="pending")
        db.add(flag)
        created.append(flag)
        newer = me if (me.created_at or utcnow()) >= (other.created_at or utcnow()) else other
        for app in db.scalars(select(Application).where(Application.candidate_id == newer.id)):
            app.is_duplicate = True
    if created:
        db.flush()
    return created


def merge(db: Session, flag: DuplicateFlag, actor: User) -> None:
    """Confirm a duplicate: link the newer record to the older (primary). Nothing is deleted. Caller commits."""
    a, b = db.get(User, flag.candidate_a_id), db.get(User, flag.candidate_b_id)
    if a is None or b is None:
        return
    primary, dup = (a, b) if (a.created_at <= b.created_at) else (b, a)
    prof = dup.profile
    if prof is None:
        prof = CandidateProfile(user_id=dup.id)
        db.add(prof)
    prof.merged_into_id = primary.id
    flag.status = "confirmed"
    flag.resolved_by = actor.id
    apps = db.scalars(select(Application).where(or_(Application.candidate_id == dup.id))).all()
    for app in apps:
        app.is_duplicate = True
        log_event(db, entity_type="duplicate", entity_id=flag.id, application_id=app.id, action="duplicate_confirmed", actor=actor,
                  note=f"Candidate record linked to primary record {primary.email}", data={"primary_candidate_id": str(primary.id)})
    if not apps:
        log_event(db, entity_type="duplicate", entity_id=flag.id, action="duplicate_confirmed", actor=actor,
                  note=f"Candidate record linked to primary record {primary.email}", data={"primary_candidate_id": str(primary.id)})
    db.flush()
