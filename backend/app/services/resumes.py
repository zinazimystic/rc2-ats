"""Resume serialisation, upload validation and the 're-score after edits' helper."""
from __future__ import annotations

import hashlib
import re
import uuid

import logging

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Unprocessable
from app.db.types import utcnow
from app.models import Application, CandidateSkill, Job, Resume, ResumeChunk, User
from app.schemas.common import Flag
from app.schemas.resume import (
    BlockedResume,
    CandidateSkillOut,
    ParsedResume,
    ResumeBulkDeleteOut,
    ResumeDetailOut,
    ResumeNotice,
    ResumeOut,
)
from app.services import pipeline
from app.services.access import safe_call

ALLOWED_EXT = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
log = logging.getLogger("app.resumes")
TERMINAL_STATUSES = ("selected", "rejected", "withdrawn")
OPEN_FOR_RESCORE = ("submitted", "parsed", "ai_assessed", "recruiter_review", "shortlisted", "interview")


def validate_upload(filename: str | None, data: bytes) -> tuple[str, str]:
    """Return (safe_filename, content_type) or raise 422. Checks extension, size, emptiness and magic bytes."""
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f]", "", name)[:200]
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise Unprocessable("Only PDF and DOCX resumes are supported", code="unsupported_file_type")
    if len(data) == 0:
        raise Unprocessable("The uploaded file is empty", code="empty_file")
    if len(data) > settings.max_upload_bytes:
        raise BadRequest(f"File is too large (maximum {settings.max_upload_mb} MB)", code="file_too_large")
    if ext == ".pdf" and not data.lstrip()[:5] == b"%PDF-":
        raise Unprocessable("This file is not a valid PDF", code="invalid_file")
    if ext == ".docx" and not data[:2] == b"PK":
        raise Unprocessable("This file is not a valid DOCX document", code="invalid_file")
    return name or f"resume{ext}", ALLOWED_EXT[ext]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _active_skills(resume: Resume) -> list[CandidateSkillOut]:
    return [CandidateSkillOut.model_validate(s) for s in resume.skills if not s.removed]


# --------------------------------------------------------------------------- friendly notices
def _friendly_failure(error: str | None) -> tuple[str, str, str | None]:
    """Map an internal parse failure to (code, friendly message, action). The raw reason stays in parse_error / the logs."""
    e = (error or "").lower()
    if "password" in e or "encrypt" in e:
        return "password_protected", "This PDF is password-protected. Remove the password and upload it again.", None
    if "scanned" in e or "no text" in e or "could not read any text" in e or "empty" in e:
        return "scanned_image", "This looks like a scanned image. Upload a text-based PDF or DOCX.", None
    if "too large" in e:
        return "too_large", "This file is too large. Upload a smaller PDF or DOCX.", None
    if "corrupt" in e or "unsupported" in e or "unreadable" in e or "could not be read" in e or "not a valid" in e:
        return "unreadable_file", "We couldn't open this file. Try re-saving it as a PDF or DOCX and upload it again.", None
    if "missing" in e and "file" in e:
        return "file_missing", "We no longer have this file. Please upload your resume again.", None
    return "read_failed", "We couldn't read this resume. Please try again, or upload a different file.", "reparse"


def build_notices(resume: Resume) -> list[ResumeNotice]:
    out: list[ResumeNotice] = []
    status = resume.parse_status
    if status in ("pending", "processing"):
        return [ResumeNotice(code="processing", level="info", message="We're reading your resume. This usually takes under a minute.")]
    if status == "failed":
        code, msg, action = _friendly_failure(resume.parse_error)
        return [ResumeNotice(code=code, level="error", message=msg, action=action)]
    if resume.extraction_method == "rules":
        out.append(ResumeNotice(
            code="simple_reading", level="warning", action="reparse",
            message="We couldn't use AI to read this resume, so a simpler method was used. Please review the details or try again.",
        ))
    for w in resume.warnings or []:
        wl = str(w).lower()
        if "truncated" in wl or "only the first" in wl:
            out.append(ResumeNotice(code="long_resume", level="info", message="Your resume is very long, so only the first part was read. Consider a shorter version."))
        elif "could not be read" in wl and "page" in wl:
            out.append(ResumeNotice(code="page_unreadable", level="warning", message="Some pages couldn't be read. Check that all your details were picked up.", action="edit"))
        elif "semantic matching is unavailable" in wl:
            out.append(ResumeNotice(code="basic_matching", level="info", action="reparse",
                                    message="Smart matching was unavailable when this resume was read. Try again later for more detailed job insights."))
    for f in resume.integrity_flags or []:
        if f.get("type") == "low_text":
            out.append(ResumeNotice(code="little_text", level="warning", action="edit",
                                    message="We found very little text in this resume. Please check the details we picked up and add anything missing."))
        elif f.get("type") == "not_a_resume":
            out.append(ResumeNotice(code="not_a_resume", level="warning", action="edit",
                                    message="This file doesn't look like a typical resume. Make sure it's the right document."))
    seen: set[str] = set()
    return [n for n in out if not (n.code in seen or seen.add(n.code))]


def application_stats(db: Session, resume_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, bool]]:
    """resume_id -> (application_count, in_use) in ONE query."""
    if not resume_ids:
        return {}
    rows = db.execute(
        select(Application.resume_id, Application.status, func.count()).where(Application.resume_id.in_(resume_ids))
        .group_by(Application.resume_id, Application.status)
    ).all()
    out: dict[uuid.UUID, tuple[int, bool]] = {}
    for rid, status, n in rows:
        c, active = out.get(rid, (0, False))
        out[rid] = (c + n, active or status not in TERMINAL_STATUSES)
    return out


def _base(resume: Resume, stats: tuple[int, bool] | None = None) -> dict:
    parsed = None
    if resume.parsed:
        try:
            parsed = ParsedResume.model_validate(resume.parsed)
        except Exception:  # noqa: BLE001
            parsed = None
    count, in_use = stats or (0, False)
    return dict(
        id=resume.id,
        candidate_id=resume.candidate_id,
        filename=resume.filename,
        content_type=resume.content_type,
        size=resume.size,
        parse_status=resume.parse_status,
        parse_error=resume.parse_error,
        warnings=list(resume.warnings or []),
        integrity_flags=[Flag(**f) for f in (resume.integrity_flags or [])],
        extraction_method=resume.extraction_method,
        page_count=resume.page_count,
        is_current=resume.is_current,
        parsed=parsed,
        skills=_active_skills(resume),
        created_at=resume.created_at,
        application_count=count,
        in_use=in_use,
        notices=build_notices(resume),
    )


def to_resume_out(resume: Resume, stats: tuple[int, bool] | None = None) -> ResumeOut:
    return ResumeOut(**_base(resume, stats))


def to_resume_outs(db: Session, rows: list[Resume]) -> list[ResumeOut]:
    """Batch serialisation: one extra query for application counts regardless of list size."""
    stats = application_stats(db, [r.id for r in rows])
    return [to_resume_out(r, stats.get(r.id)) for r in rows]


def to_resume_detail(resume: Resume, stats: tuple[int, bool] | None = None) -> ResumeDetailOut:
    return ResumeDetailOut(**_base(resume, stats), text=resume.text)


# --------------------------------------------------------------------------- delete
def in_use_message(titles: list[str]) -> str:
    uniq = sorted(set(titles))
    names = ", ".join(f'"{t}"' for t in uniq[:3]) or "a job"
    if len(uniq) > 3:
        names += f" and {len(uniq) - 3} more"
    return f"Withdraw your application for {names} first, or switch it to another resume."


def delete_resumes(db: Session, user: User, ids: list[uuid.UUID]) -> ResumeBulkDeleteOut:
    """Delete a candidate's resumes: blocked while used by an active application, soft-deleted when only finished
    applications reference it, hard-deleted otherwise. Partial success; one transaction."""
    from app.services.audit import log_event

    ids = list(dict.fromkeys(ids))
    rows = db.scalars(
        select(Resume).where(Resume.id.in_(ids), Resume.candidate_id == user.id, Resume.deleted_at.is_(None))
    ).all()
    refs = (
        db.execute(
            select(Application.resume_id, Application.status, Job.title)
            .join(Job, Job.id == Application.job_id)
            .where(Application.resume_id.in_([r.id for r in rows]))
        ).all()
        if rows
        else []
    )
    by_resume: dict[uuid.UUID, list[tuple[str, str]]] = {}
    for rid, status, title in refs:
        by_resume.setdefault(rid, []).append((status, title))
    out = ResumeBulkDeleteOut()
    soft: list[uuid.UUID] = []
    hard: list[uuid.UUID] = []
    was_current = False
    for r in rows:
        used = by_resume.get(r.id, [])
        active = [t for st, t in used if st not in TERMINAL_STATUSES]
        if active:
            out.blocked.append(BlockedResume(id=r.id, filename=r.filename, reason=in_use_message(active)))
            continue
        (soft if used else hard).append(r.id)
        was_current = was_current or r.is_current
        out.deleted.append(r.id)
    found = {r.id for r in rows}
    for rid in ids:
        if rid not in found:
            out.blocked.append(BlockedResume(id=rid, filename="", reason="This resume was not found or was already deleted."))
    if soft:
        db.execute(update(Resume).where(Resume.id.in_(soft)).values(deleted_at=utcnow(), is_current=False))
    if hard:
        db.execute(delete(ResumeChunk).where(ResumeChunk.resume_id.in_(hard)))
        db.execute(delete(CandidateSkill).where(CandidateSkill.resume_id.in_(hard)))
        db.execute(delete(Resume).where(Resume.id.in_(hard)))
    for rid in out.deleted:
        log_event(db, entity_type="resume", entity_id=rid, action="resume_deleted", actor=user, note="soft" if rid in soft else "hard")
    if out.deleted and was_current:
        promote_newest(db, user)
    db.commit()
    return out


def promote_newest(db: Session, user: User) -> None:
    """Make the newest remaining resume current (no-op when one already is)."""
    remaining = db.execute(
        select(Resume.id, Resume.is_current).where(Resume.candidate_id == user.id, Resume.deleted_at.is_(None))
        .order_by(Resume.created_at.desc())
    ).all()
    if not remaining or any(cur for _, cur in remaining):
        return
    db.execute(update(Resume).where(Resume.id == remaining[0][0]).values(is_current=True))


def requeue_open_applications(db: Session, resume: Resume) -> int:
    """After a resume edit, re-score every live application that uses this resume."""
    apps = db.scalars(
        select(Application).where(
            Application.resume_id == resume.id, Application.status.in_(OPEN_FOR_RESCORE)
        )
    ).all()
    n = 0
    for a in apps:
        if safe_call(pipeline.enqueue_assessment, a.id):
            n += 1
    return n


def find_skill(resume: Resume, name: str) -> CandidateSkill | None:
    key = name.strip().lower()
    return next((s for s in resume.skills if s.name.lower() == key), None)
