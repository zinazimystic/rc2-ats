"""Resume serialisation, upload validation and the 're-score after edits' helper."""
from __future__ import annotations

import hashlib
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Unprocessable
from app.models import Application, CandidateSkill, Resume, User
from app.schemas.common import Flag
from app.schemas.resume import CandidateSkillOut, ParsedResume, ResumeDetailOut, ResumeOut
from app.services import pipeline
from app.services.access import safe_call

ALLOWED_EXT = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
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


def _base(resume: Resume) -> dict:
    parsed = None
    if resume.parsed:
        try:
            parsed = ParsedResume.model_validate(resume.parsed)
        except Exception:  # noqa: BLE001
            parsed = None
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
    )


def to_resume_out(resume: Resume) -> ResumeOut:
    return ResumeOut(**_base(resume))


def to_resume_detail(resume: Resume) -> ResumeDetailOut:
    return ResumeDetailOut(**_base(resume), text=resume.text)


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
