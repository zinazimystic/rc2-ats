from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DB, CurrentUser
from app.core.errors import Conflict, NotFound, Unprocessable
from app.models import CandidateSkill, Resume
from app.schemas.common import Msg
from app.schemas.resume import CandidateSkillOut, ParsedPatchIn, ParsedResume, ResumeDetailOut, ResumeOut, SkillAddIn, SkillPatchIn
from app.services import pipeline, resumes
from app.services.access import get_resume_for_user, safe_call
from app.services.audit import log_event

router = APIRouter(prefix="/resumes", tags=["resumes"])
skills_router = APIRouter(prefix="/skills", tags=["resumes"])


def _load(db, user, resume_id: uuid.UUID) -> Resume:
    get_resume_for_user(db, user, resume_id)  # 404 when not visible
    return db.scalar(select(Resume).where(Resume.id == resume_id).options(selectinload(Resume.skills)))


@router.get("/{resume_id}", response_model=ResumeDetailOut)
def get_resume(resume_id: uuid.UUID, db: DB, user: CurrentUser):
    return resumes.to_resume_detail(_load(db, user, resume_id))


@router.get("/{resume_id}/file")
def get_file(resume_id: uuid.UUID, db: DB, user: CurrentUser):
    get_resume_for_user(db, user, resume_id)
    data, name, ctype = db.execute(
        select(Resume.file_bytes, Resume.filename, Resume.content_type).where(Resume.id == resume_id)
    ).one()
    if not data:
        raise NotFound("The original file is not available")
    safe = re.sub(r'[^A-Za-z0-9._ -]', "_", name) or "resume"
    return Response(
        content=data,
        media_type=ctype or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{safe}"', "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.patch("/{resume_id}/parsed", response_model=ResumeDetailOut)
def patch_parsed(resume_id: uuid.UUID, body: ParsedPatchIn, db: DB, user: CurrentUser):
    from app.core.errors import Forbidden

    if user.role != "candidate":
        raise Forbidden("Only the candidate can correct their parsed resume")
    resume = _load(db, user, resume_id)
    if resume.parse_status != "parsed":
        raise Conflict("The resume is still being processed", code="not_parsed")
    current = ParsedResume.model_validate(resume.parsed or {}).model_dump()
    current.update(body.model_dump(exclude_unset=True, exclude_none=False))
    resume.parsed = ParsedResume.model_validate(current).model_dump()
    log_event(db, entity_type="resume", entity_id=resume.id, action="resume_edited", actor=user)
    db.commit()
    resumes.requeue_open_applications(db, resume)
    db.expire_all()
    return resumes.to_resume_detail(_load(db, user, resume_id))


@router.post("/{resume_id}/reprocess", response_model=ResumeOut, status_code=202)
def reprocess(resume_id: uuid.UUID, db: DB, user: CurrentUser):
    resume = _load(db, user, resume_id)
    if resume.parse_status == "processing":
        raise Conflict("This resume is already being processed", code="already_processing")
    resume.parse_status, resume.parse_error = "pending", None
    db.commit()
    safe_call(pipeline.enqueue_resume, resume.id)
    db.expire_all()
    return resumes.to_resume_out(_load(db, user, resume_id))


@router.post("/{resume_id}/skills", response_model=CandidateSkillOut, status_code=201)
def add_skill(resume_id: uuid.UUID, body: SkillAddIn, db: DB, user: CurrentUser):
    resume = _load(db, user, resume_id)
    name = re.sub(r"\s+", " ", body.name).strip()
    if not name:
        raise Unprocessable("Skill name is required", code="validation_error")
    source = "candidate" if user.role == "candidate" else "recruiter"
    verification = "self_reported" if user.role == "candidate" else "verified"
    skill = resumes.find_skill(resume, name)
    if skill is None:
        skill = CandidateSkill(resume_id=resume.id, name=name, raw_name=name)
        db.add(skill)
    skill.presence, skill.source, skill.verification = body.presence, source, verification
    skill.removed, skill.updated_by = False, user.id
    log_event(db, entity_type="resume", entity_id=resume.id, action="skill_added", actor=user, to_value=name, note=body.presence)
    db.commit()
    resumes.requeue_open_applications(db, resume)
    db.expire_all()
    return CandidateSkillOut.model_validate(db.get(CandidateSkill, skill.id))


def _skill_for(db, user, skill_id: uuid.UUID) -> tuple[CandidateSkill, Resume]:
    skill = db.get(CandidateSkill, skill_id)
    if skill is None:
        raise NotFound("Skill not found")
    resume = _load(db, user, skill.resume_id)  # raises 404 when not visible
    return db.get(CandidateSkill, skill_id), resume


@skills_router.patch("/{skill_id}", response_model=CandidateSkillOut)
def patch_skill(skill_id: uuid.UUID, body: SkillPatchIn, db: DB, user: CurrentUser):
    skill, resume = _skill_for(db, user, skill_id)
    if body.name and body.name.strip().lower() != skill.name.lower():
        clash = resumes.find_skill(resume, body.name)
        if clash is not None and clash.id != skill.id:
            raise Conflict("This resume already has a skill with that name", code="duplicate_skill")
        skill.name = re.sub(r"\s+", " ", body.name).strip()
        skill.source = "candidate" if user.role == "candidate" else "recruiter"
    if body.presence is not None:
        skill.presence = body.presence
    if body.removed is not None:
        skill.removed = body.removed
    if body.confirm:
        skill.verification = "self_reported" if user.role == "candidate" else "verified"
        skill.source = "candidate" if user.role == "candidate" else "recruiter"
    skill.updated_by = user.id
    log_event(db, entity_type="resume", entity_id=resume.id, action="skill_updated", actor=user, to_value=skill.name)
    db.commit()
    resumes.requeue_open_applications(db, resume)
    db.expire_all()
    return CandidateSkillOut.model_validate(db.get(CandidateSkill, skill_id))


@skills_router.delete("/{skill_id}", response_model=Msg)
def delete_skill(skill_id: uuid.UUID, db: DB, user: CurrentUser):
    skill, resume = _skill_for(db, user, skill_id)
    skill.removed, skill.updated_by = True, user.id  # soft delete keeps the audit trail
    log_event(db, entity_type="resume", entity_id=resume.id, action="skill_removed", actor=user, to_value=skill.name)
    db.commit()
    resumes.requeue_open_applications(db, resume)
    return Msg(detail="Skill removed")
