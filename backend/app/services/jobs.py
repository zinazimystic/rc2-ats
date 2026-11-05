"""Job serialisation (with per-status counts, no N+1) and create/update logic."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict
from app.models import DEFAULT_WEIGHTS, Application, Job, JobRequirement, User
from app.schemas.job import JobIn, JobListItem, JobOut, JobUpdate, JobWeights, RequirementOut
from app.services import jobs_ai, pipeline, tasks
from app.services.access import safe_call
from app.services.audit import log_event

log = logging.getLogger("app.jobs")

SHORTLIST_STATES = ("shortlisted", "interview", "selected")
PENDING_STATES = ("ai_assessed", "recruiter_review")
# fields whose change invalidates existing assessments
RESCORE_FIELDS = {"requirements", "weights", "min_experience_years", "education_level", "qualifications"}


def job_counts(db: Session, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    if not job_ids:
        return {}
    rows = db.execute(
        select(Application.job_id, Application.status, func.count())
        .where(Application.job_id.in_(job_ids))
        .group_by(Application.job_id, Application.status)
    ).all()
    out: dict[uuid.UUID, dict[str, int]] = {jid: {"applicants": 0, "shortlisted": 0, "pending": 0} for jid in job_ids}
    for jid, status, n in rows:
        if status == "withdrawn":
            continue
        c = out[jid]
        c["applicants"] += n
        if status in SHORTLIST_STATES:
            c["shortlisted"] += n
        if status in PENDING_STATES:
            c["pending"] += n
    return out


def applied_job_ids(db: Session, candidate: User, job_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not job_ids:
        return set()
    rows = db.scalars(
        select(Application.job_id).where(
            Application.candidate_id == candidate.id, Application.job_id.in_(job_ids), Application.status != "withdrawn"
        )
    ).all()
    return set(rows)


def _weights(job: Job) -> JobWeights:
    try:
        return JobWeights(**{**DEFAULT_WEIGHTS, **(job.weights or {})})
    except Exception:  # noqa: BLE001 - corrupt weights must not break reads
        return JobWeights()


def to_job_out(db: Session, job: Job, viewer: User) -> JobOut:
    out = JobOut(
        id=job.id,
        recruiter_id=job.recruiter_id,
        title=job.title,
        department=job.department,
        location=job.location,
        employment_type=job.employment_type,
        work_mode=job.work_mode,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        currency=job.currency,
        description=job.description,
        min_experience_years=job.min_experience_years,
        education_level=job.education_level,
        qualifications=list(job.qualifications or []),
        weights=_weights(job),
        status=job.status,
        version=job.version,
        requirements=[RequirementOut.model_validate(r) for r in job.requirements],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
    if viewer.role == "recruiter":
        c = job_counts(db, [job.id])[job.id]
        out.applicant_count, out.shortlisted_count, out.pending_review_count = c["applicants"], c["shortlisted"], c["pending"]
    else:
        out.has_applied = job.id in applied_job_ids(db, viewer, [job.id])
    return out


def to_list_items(db: Session, jobs: list[Job], viewer: User, applied: set[uuid.UUID] | None = None) -> list[JobListItem]:
    ids = [j.id for j in jobs]
    counts = job_counts(db, ids) if viewer.role == "recruiter" else {}
    if applied is None:
        applied = applied_job_ids(db, viewer, ids) if viewer.role == "candidate" else set()
    items = []
    for j in jobs:
        c = counts.get(j.id, {"applicants": 0, "shortlisted": 0, "pending": 0})
        items.append(
            JobListItem(
                id=j.id,
                title=j.title,
                department=j.department,
                location=j.location,
                employment_type=j.employment_type,
                work_mode=j.work_mode,
                status=j.status,
                salary_min=j.salary_min,
                salary_max=j.salary_max,
                currency=j.currency,
                min_experience_years=j.min_experience_years,
                required_skills=[r.skill for r in j.requirements if r.kind == "required"],
                preferred_skills=[r.skill for r in j.requirements if r.kind == "preferred"],
                applicant_count=c["applicants"],
                shortlisted_count=c["shortlisted"],
                pending_review_count=c["pending"],
                has_applied=(j.id in applied) if viewer.role == "candidate" else None,
                created_at=j.created_at,
            )
        )
    return items


def _dedupe_requirements(reqs):
    seen: dict[str, object] = {}
    for r in reqs:
        key = r.skill.strip().lower()
        if not key:
            continue
        prev = seen.get(key)
        # keep the strongest: required beats preferred, then higher importance
        if prev is None or (r.kind == "required" and prev.kind != "required") or (r.kind == prev.kind and r.importance > prev.importance):
            seen[key] = r
    return list(seen.values())


def create_job(db: Session, recruiter: User, data: JobIn) -> Job:
    job = Job(
        recruiter_id=recruiter.id,
        title=data.title.strip(),
        department=data.department,
        location=data.location,
        employment_type=data.employment_type,
        work_mode=data.work_mode,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        currency=(data.currency or "USD").upper(),
        description=data.description.strip(),
        min_experience_years=data.min_experience_years,
        education_level=data.education_level,
        qualifications=[q.strip() for q in data.qualifications if q.strip()],
        weights=(data.weights or JobWeights()).model_dump(),
        status="open",
        version=1,
    )
    for i, r in enumerate(_dedupe_requirements(data.requirements)):
        job.requirements.append(JobRequirement(skill=r.skill.strip(), kind=r.kind, importance=r.importance, position=i))
    db.add(job)
    db.flush()
    log_event(db, entity_type="job", entity_id=job.id, action="job_created", actor=recruiter, to_value=job.title)
    return job


def update_job(db: Session, job: Job, recruiter: User, data: JobUpdate) -> tuple[Job, bool]:
    """Apply a partial update. Returns (job, rescore_needed)."""
    changes = data.model_dump(exclude_unset=True)
    rescore = False
    if "salary_min" in changes or "salary_max" in changes:
        lo = changes.get("salary_min", job.salary_min)
        hi = changes.get("salary_max", job.salary_max)
        if lo is not None and hi is not None and lo > hi:
            from app.core.errors import Unprocessable

            raise Unprocessable("salary_min cannot exceed salary_max", code="validation_error")
    nullable = {"department", "location", "salary_min", "salary_max"}
    for field in ("title", "department", "location", "employment_type", "work_mode", "salary_min", "salary_max", "currency", "description"):
        if field not in changes:
            continue
        value = changes[field]
        if value is None and field not in nullable:
            continue
        if field == "currency":
            value = value.upper()
        if isinstance(value, str):
            value = value.strip() or (None if field in nullable else value)
        setattr(job, field, value)
    for field in ("min_experience_years", "education_level"):
        if changes.get(field) is not None and changes[field] != getattr(job, field):
            setattr(job, field, changes[field])
            rescore = True
    if changes.get("qualifications") is not None:
        new_q = [q.strip() for q in changes["qualifications"] if q.strip()]
        if new_q != list(job.qualifications or []):
            job.qualifications = new_q
            rescore = True
    if data.weights is not None and data.weights.model_dump() != _weights(job).model_dump():
        job.weights = data.weights.model_dump()
        rescore = True
    if data.requirements is not None:
        incoming = _dedupe_requirements(data.requirements)
        existing = {r.skill.strip().lower(): r for r in job.requirements}
        before = [(r.skill.strip().lower(), r.kind, r.importance) for r in job.requirements]
        keep: list[JobRequirement] = []
        for i, r in enumerate(incoming):
            row = existing.pop(r.skill.strip().lower(), None)
            if row is None:
                row = JobRequirement(skill=r.skill.strip(), kind=r.kind, importance=r.importance, position=i)
            else:
                row.skill, row.kind, row.importance, row.position = r.skill.strip(), r.kind, r.importance, i
            keep.append(row)
        job.requirements[:] = keep  # orphans (removed requirements) are deleted by cascade
        after = [(r.skill.strip().lower(), r.kind, r.importance) for r in keep]
        if sorted(before) != sorted(after):
            rescore = True
    if rescore:
        job.version = (job.version or 1) + 1
    db.flush()
    log_event(db, entity_type="job", entity_id=job.id, action="job_updated", actor=recruiter,
              data={"fields": sorted(changes.keys()), "version": job.version})
    return job, rescore


def requeue_job_applications(db: Session, job: Job) -> int:
    """Queue a fresh assessment for every live application of the job."""
    apps = db.scalars(
        select(Application).where(Application.job_id == job.id, Application.status != "withdrawn").options(selectinload(Application.resume))
    ).all()
    n = 0
    for a in apps:
        if a.resume is None or a.resume.parse_status != "parsed":
            continue
        if safe_call(pipeline.enqueue_assessment, a.id):
            n += 1
    return n


def after_job_commit(job_id: uuid.UUID) -> None:
    safe_call(tasks.submit, jobs_ai.embed_job, job_id)


def set_job_status(db: Session, job: Job, recruiter: User, status: str) -> Job:
    if job.status == status:
        raise Conflict(f"This job is already {status}")
    old = job.status
    job.status = status
    log_event(db, entity_type="job", entity_id=job.id, action="job_status", actor=recruiter, from_value=old, to_value=status)
    return job
