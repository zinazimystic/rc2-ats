from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.core.deps import DB, Candidate, CurrentUser, Recruiter
from app.core.errors import Conflict, NotFound, ServiceUnavailable, Unprocessable
from app.core.pagination import Limit, Offset, set_total
from app.models import Application, Job, Notification, Resume, User
from app.schemas.application import ApplicationRowOut, CompareOut, JobApplicantsOut
from app.schemas.common import Msg
from app.schemas.job import JobExtractIn, JobExtractOut, JobIn, JobListItem, JobOut, JobUpdate
from app.schemas.search import MyMatchOut, TalentPoolItem
from app.services import applications as app_service
from app.services import jobs as job_service
from app.services import jobs_ai, resumes, search
from app.services import my_match as my_match_service
from app.services.access import get_owned_job, safe_call
from app.services.ai import llm
from app.services.audit import log_event
from app.services.notifications import notify

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobListItem])
def list_jobs(
    db: DB,
    user: CurrentUser,
    response: Response,
    status: Literal["open", "closed"] | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Limit = 200,
    offset: Offset = 0,
):
    """Round trips: jobs+requirements (+has_applied flag for candidates) in ONE query; recruiters add one for the counts."""
    stmt = select(Job).options(joinedload(Job.requirements)).order_by(Job.created_at.desc())
    if user.role == "recruiter":
        stmt = stmt.where(Job.recruiter_id == user.id)
    else:
        applied = select(Application.job_id).where(Application.candidate_id == user.id, Application.status != "withdrawn")
        stmt = stmt.where(or_(Job.status == "open", Job.id.in_(applied))).add_columns(Job.id.in_(applied).label("applied"))
    if status:
        stmt = stmt.where(Job.status == status)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Job.title).like(like), func.lower(Job.department).like(like), func.lower(Job.location).like(like)))
    count_stmt = select(func.count()).select_from(stmt.order_by(None).with_only_columns(Job.id).subquery())
    stmt = stmt.limit(limit).offset(offset)
    if user.role == "recruiter":
        jobs = list(db.scalars(stmt).unique().all())
        set_total(response, len(jobs), limit, offset, lambda: db.scalar(count_stmt) or 0)
        return job_service.to_list_items(db, jobs, user)
    rows = db.execute(stmt).unique().all()
    set_total(response, len(rows), limit, offset, lambda: db.scalar(count_stmt) or 0)
    return job_service.to_list_items(db, [r[0] for r in rows], user, applied={r[0].id for r in rows if r[1]})


@router.get("/{job_id}/my-match", response_model=MyMatchOut)
def my_match(job_id: uuid.UUID, db: DB, user: Candidate, resume_id: uuid.UUID | None = None):
    """The candidate's own fit estimate for a job (what to work on). Never includes recruiter-side data."""
    return my_match_service.my_match(db, user, job_id, resume_id)


@router.post("", response_model=JobOut, status_code=201)
def create_job(body: JobIn, db: DB, user: Recruiter):
    job = job_service.create_job(db, user, body)
    db.commit()
    job_service.after_job_commit(job.id)
    db.expire_all()
    job = get_owned_job(db, user, job.id)
    return job_service.to_job_out(db, job, user)


@router.post("/extract-requirements", response_model=JobExtractOut)
def extract_requirements(body: JobExtractIn, user: Recruiter):
    try:
        return jobs_ai.extract_job_requirements(body.title, body.description)
    except (llm.LLMUnavailable, llm.LLMError) as exc:
        raise ServiceUnavailable(f"Requirement extraction is unavailable right now: {exc}", code="llm_unavailable")


def _visible_job(db, user, job_id: uuid.UUID) -> Job:
    if user.role == "recruiter":
        return get_owned_job(db, user, job_id)
    job = db.scalars(select(Job).options(joinedload(Job.requirements)).where(Job.id == job_id)).unique().first()
    if job is None:
        raise NotFound("Job not found")
    if job.status != "open":
        applied = db.scalar(select(Application.id).where(Application.job_id == job_id, Application.candidate_id == user.id))
        if applied is None:
            raise NotFound("Job not found")
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: DB, user: CurrentUser):
    return job_service.to_job_out(db, _visible_job(db, user, job_id), user)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(job_id: uuid.UUID, body: JobUpdate, db: DB, user: Recruiter):
    job = get_owned_job(db, user, job_id)
    job, rescore = job_service.update_job(db, job, user, body)
    db.commit()
    job_service.after_job_commit(job.id)
    if rescore:
        job_service.requeue_job_applications(db, job)
    db.expire_all()
    return job_service.to_job_out(db, get_owned_job(db, user, job_id), user)


@router.post("/{job_id}/close", response_model=JobOut)
def close_job(job_id: uuid.UUID, db: DB, user: Recruiter):
    job = job_service.set_job_status(db, get_owned_job(db, user, job_id), user, "closed")
    db.commit()
    return job_service.to_job_out(db, job, user)


@router.post("/{job_id}/reopen", response_model=JobOut)
def reopen_job(job_id: uuid.UUID, db: DB, user: Recruiter):
    job = job_service.set_job_status(db, get_owned_job(db, user, job_id), user, "open")
    db.commit()
    return job_service.to_job_out(db, job, user)


@router.get("/{job_id}/applications", response_model=JobApplicantsOut)
def job_applications(
    job_id: uuid.UUID,
    response: Response,
    db: DB,
    user: Recruiter,
    status: str | None = None,
    min_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    skill: Annotated[str | None, Query(max_length=80)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Literal["score", "date", "name"] = "score",
    limit: Limit = 200,
    offset: Offset = 0,
):
    job = get_owned_job(db, user, job_id)
    apps = list(
        db.scalars(
            select(Application)
            .where(Application.job_id == job.id)
            .options(*app_service.list_load_options(skills=bool(skill and skill.strip())))
        ).unique().all()
    )
    counts: dict[str, int] = {}
    for a in apps:
        counts[a.status] = counts.get(a.status, 0) + 1
    rows = apps
    if status:
        wanted = {s.strip() for s in status.split(",") if s.strip()}
        rows = [a for a in rows if a.status in wanted]
    else:
        rows = [a for a in rows if a.status != "withdrawn"]
    if min_score is not None:
        rows = [a for a in rows if a.assessment is not None and a.assessment.effective_score >= min_score]
    if q and q.strip():
        needle = q.strip().lower()
        rows = [a for a in rows if needle in a.candidate.full_name.lower() or needle in a.candidate.email.lower()]
    if skill and skill.strip():
        needle = skill.strip().lower()

        def has_skill(a: Application) -> bool:
            if a.resume and any(s.name.lower() == needle and not s.removed and s.presence == "present" for s in a.resume.skills):
                return True
            return needle in [m.lower() for m in app_service.matched_missing(a.assessment)[0]]

        rows = [a for a in rows if has_skill(a)]
    if sort == "name":
        rows.sort(key=lambda a: a.candidate.full_name.lower())
    elif sort == "date":
        rows.sort(key=lambda a: a.created_at, reverse=True)
    else:
        rows.sort(key=lambda a: (a.assessment is None, -(a.assessment.effective_score if a.assessment else 0), a.created_at))
    from app.services.access import job_brief

    total = len(rows)  # filtered total (the page below slices it)
    response.headers["X-Total-Count"] = str(total)
    page = rows[offset: offset + limit]
    return JobApplicantsOut(job=job_brief(job), total=total, status_counts=counts, items=[app_service.to_row(a) for a in page])


@router.get("/{job_id}/compare", response_model=CompareOut)
def compare(job_id: uuid.UUID, db: DB, user: Recruiter, ids: Annotated[str, Query(max_length=400)]):
    job = get_owned_job(db, user, job_id)
    try:
        wanted = list(dict.fromkeys(uuid.UUID(x.strip()) for x in ids.split(",") if x.strip()))
    except ValueError:
        raise Unprocessable("ids must be a comma-separated list of application ids", code="validation_error")
    if not 2 <= len(wanted) <= 4:
        raise Unprocessable("Select between 2 and 4 candidates to compare", code="validation_error")
    apps = list(
        db.scalars(
            select(Application)
            .where(Application.job_id == job.id, Application.id.in_(wanted))
            .options(*app_service.list_load_options(full_resume=True))
        ).unique().all()
    )
    if len(apps) != len(wanted):
        raise NotFound("One or more applications were not found for this job")
    order = {i: n for n, i in enumerate(wanted)}
    apps.sort(key=lambda a: order[a.id])
    from app.services.access import job_brief

    return CompareOut(job=job_brief(job), candidates=[app_service.to_compare(a, a.resume) for a in apps])


@router.get("/{job_id}/talent-pool", response_model=list[TalentPoolItem])
def talent_pool(job_id: uuid.UUID, db: DB, user: Recruiter):
    job = get_owned_job(db, user, job_id, vectors=True)
    return search.talent_pool(db, job, user)


@router.post("/{job_id}/talent-pool/{candidate_id}/invite", response_model=Msg)
def invite(job_id: uuid.UUID, candidate_id: uuid.UUID, db: DB, user: Recruiter):
    job = get_owned_job(db, user, job_id)
    if job.status != "open":
        raise Conflict("Reopen the job before inviting candidates", code="job_closed")
    cand = db.get(User, candidate_id)
    if cand is None or cand.role != "candidate":
        raise NotFound("Candidate not found")
    from app.services.access import recruiter_can_see_candidate

    if not recruiter_can_see_candidate(db, user, candidate_id):
        raise NotFound("Candidate not found")
    if db.scalar(
        select(Application.id).where(
            Application.job_id == job.id, Application.candidate_id == candidate_id, Application.status != "withdrawn"
        )
    ):
        raise Conflict("This candidate has already applied to this job", code="already_applied")
    link = f"/candidate/jobs/{job.id}"
    if db.scalar(select(Notification.id).where(Notification.user_id == candidate_id, Notification.type == "job_invite", Notification.link == link)):
        return Msg(detail="Candidate was already invited")
    notify(db, user_id=candidate_id, type="job_invite", title=f"You're invited to apply: {job.title}",
           body="A recruiter thinks your profile is a strong fit for this role.", link=link)
    notify(db, type="email_invite", channel="email_sim", sender_id=user.id, recipient_email=cand.email,
           title=f"Invitation to apply: {job.title}", body=f"Hi {cand.full_name}, you have been invited to apply for {job.title}.")
    log_event(db, entity_type="job", entity_id=job.id, action="talent_invite", actor=user, to_value=str(candidate_id))
    db.commit()
    return Msg(detail="Invitation sent")
