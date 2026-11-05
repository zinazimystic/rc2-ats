from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DB, Candidate
from app.models import CandidateProfile, Resume
from app.schemas.resume import ProfileIn, ProfileOut, ResumeOut
from app.schemas.search import RecommendationOut
from app.services import pipeline, resumes, search
from app.services.access import safe_call
from app.services.audit import log_event

router = APIRouter(prefix="/candidates/me", tags=["candidates"])


def _profile(db, user) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        profile = CandidateProfile(user_id=user.id, links=[], interests=[])
        db.add(profile)
        db.flush()
    return profile


def _out(user, p: CandidateProfile) -> ProfileOut:
    return ProfileOut(
        user_id=user.id, full_name=user.full_name, email=user.email, headline=p.headline, phone=p.phone, location=p.location,
        links=list(p.links or []), interests=list(p.interests or []), talent_pool_opt_in=p.talent_pool_opt_in,
        retention_until=p.retention_until,
    )


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: DB, user: Candidate):
    p = _profile(db, user)
    db.commit()
    return _out(user, p)


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(body: ProfileIn, db: DB, user: Candidate):
    p = _profile(db, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in ("links", "interests") and value is not None:
            value = [str(v).strip() for v in value if str(v).strip()]
        elif isinstance(value, str):
            value = value.strip() or None
        setattr(p, field, value if value is not None or field in ("headline", "phone", "location", "retention_until") else getattr(p, field))
    db.commit()
    return _out(user, p)


@router.post("/resumes", response_model=ResumeOut, status_code=201)
def upload_resume(db: DB, user: Candidate, file: UploadFile = File(...)):
    limit = resumes.settings.max_upload_bytes
    data = file.file.read(limit + 1)  # read one byte past the limit so oversized files are detected without buffering them
    name, content_type = resumes.validate_upload(file.filename, data)
    for old in db.scalars(select(Resume).where(Resume.candidate_id == user.id, Resume.is_current.is_(True))):
        old.is_current = False
    resume = Resume(
        candidate_id=user.id, filename=name, content_type=content_type, size=len(data), sha256=resumes.sha256(data),
        file_bytes=data, parse_status="pending", warnings=[], integrity_flags=[], is_current=True,
    )
    db.add(resume)
    db.flush()
    log_event(db, entity_type="resume", entity_id=resume.id, action="resume_uploaded", actor=user, to_value=name)
    db.commit()
    rid = resume.id
    ok = safe_call(pipeline.enqueue_resume, rid)  # inline when TASKS_EAGER, else background thread
    db.expire_all()
    resume = db.get(Resume, rid)
    if not ok and resume.parse_status == "pending":
        resume.parse_status, resume.parse_error = "failed", "Could not start processing. Use 'Reprocess' to try again."
        db.commit()
    return resumes.to_resume_out(resume)


@router.get("/resumes", response_model=list[ResumeOut])
def my_resumes(db: DB, user: Candidate):
    rows = db.scalars(
        select(Resume).where(Resume.candidate_id == user.id).options(selectinload(Resume.skills)).order_by(Resume.created_at.desc())
    ).all()
    return [resumes.to_resume_out(r) for r in rows]


@router.get("/recommendations", response_model=list[RecommendationOut])
def recommendations(db: DB, user: Candidate):
    return search.recommend_jobs(db, user)
