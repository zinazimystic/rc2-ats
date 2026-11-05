"""Object-level access rules. Anything a user may not see is a 404 (never a 403) so ids don't leak."""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import NotFound
from app.models import Application, CandidateProfile, Interview, InterviewFeedback, InterviewQuestion, Job, RecruiterNote, Resume, User
from app.schemas.common import CandidateBrief, JobBrief

log = logging.getLogger("app.access")


def safe_call(fn: Callable, *args, **kwargs) -> bool:
    """Run a best-effort background hook (embedding, queueing). Never let it break the request."""
    try:
        fn(*args, **kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Background hook %s failed: %s", getattr(fn, "__name__", fn), exc)
        return False


def candidate_brief(user: User, profile: CandidateProfile | None = None) -> CandidateBrief:
    profile = profile if profile is not None else user.profile
    return CandidateBrief(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        headline=profile.headline if profile else None,
        location=profile.location if profile else None,
    )


def job_brief(job: Job) -> JobBrief:
    return JobBrief(id=job.id, title=job.title, department=job.department, location=job.location, status=job.status)


def parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except ValueError as exc:
        raise NotFound("Not found") from exc


# ----------------------------------------------------------------------------- recruiter-owned objects
def get_owned_job(db: Session, recruiter: User, job_id: uuid.UUID, *, vectors: bool = False) -> Job:
    """Owned job + requirements in ONE query (404 for anyone else). `vectors=True` also loads the deferred embeddings (scoring)."""
    from app.models import job_vector_options

    opts = job_vector_options(join=True) if vectors else (joinedload(Job.requirements),)
    job = db.scalars(select(Job).options(*opts).where(Job.id == job_id)).unique().first()
    if job is None or job.recruiter_id != recruiter.id:
        raise NotFound("Job not found")
    return job


def get_owned_application(db: Session, recruiter: User, application_id: uuid.UUID, *options) -> Application:
    """The application with its job, candidate and the candidate's profile in ONE query (many-to-one joins add no round trips).
    Extra loader options (assessment, notes ...) ride along."""
    app = db.scalars(
        select(Application)
        .options(joinedload(Application.job), joinedload(Application.candidate).joinedload(User.profile), *options)
        .where(Application.id == application_id)
    ).unique().first()
    if app is None or app.job is None or app.job.recruiter_id != recruiter.id:
        raise NotFound("Application not found")
    return app


def get_owned_interview(db: Session, recruiter: User, interview_id: uuid.UUID) -> Interview:
    """Interview + its application (job, candidate, profile) + feedback in one query; 404 when the recruiter does not own the job."""
    iv = db.scalars(
        select(Interview)
        .options(
            joinedload(Interview.application).joinedload(Application.job),
            joinedload(Interview.application).joinedload(Application.candidate).joinedload(User.profile),
            selectinload(Interview.feedback).joinedload(InterviewFeedback.author),
        )
        .where(Interview.id == interview_id)
    ).unique().first()
    if iv is None or iv.application is None or iv.application.job is None or iv.application.job.recruiter_id != recruiter.id:
        raise NotFound("Interview not found")
    return iv


def get_owned_question(db: Session, recruiter: User, question_id: uuid.UUID) -> tuple[InterviewQuestion, Application]:
    q = db.get(InterviewQuestion, question_id)
    if q is None:
        raise NotFound("Question not found")
    return q, get_owned_application(db, recruiter, q.application_id)


def get_owned_note(db: Session, recruiter: User, note_id: uuid.UUID) -> RecruiterNote:
    note = db.get(RecruiterNote, note_id)
    if note is None:
        raise NotFound("Note not found")
    get_owned_application(db, recruiter, note.application_id)
    return note


# ----------------------------------------------------------------------------- resumes
def recruiter_can_see_candidate(db: Session, recruiter: User, candidate_id: uuid.UUID) -> bool:
    """A recruiter may see a candidate who applied to one of their jobs, or who opted in to the talent pool (one query)."""
    applied = exists().where(Application.candidate_id == candidate_id, Application.job_id == Job.id, Job.recruiter_id == recruiter.id)
    opted = exists().where(CandidateProfile.user_id == candidate_id, CandidateProfile.talent_pool_opt_in.is_(True))
    return bool(db.scalar(select(or_(applied, opted))))


def get_resume_for_user(db: Session, user: User, resume_id: uuid.UUID, *options) -> Resume:
    """Load a resume (with optional loader options) in ONE query, then apply the access rules.
    Candidates never see their soft-deleted resumes; recruiters keep access to what applicants submitted."""
    resume = db.scalars(select(Resume).where(Resume.id == resume_id).options(*options)).unique().first()
    if resume is None:
        raise NotFound("Resume not found")
    if user.role == "candidate":
        if resume.candidate_id != user.id or resume.deleted_at is not None:
            raise NotFound("Resume not found")
    elif not recruiter_can_see_candidate(db, user, resume.candidate_id):
        raise NotFound("Resume not found")
    return resume
