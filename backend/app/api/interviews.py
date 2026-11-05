from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select

from app.core.deps import DB, Recruiter
from app.models import Application, Interview, Job
from app.core.pagination import Limit, Offset, set_total
from app.schemas.interview import FeedbackIn, InterviewIn, InterviewOut, InterviewPatch
from app.services import interviews as svc
from app.services.access import get_owned_application, get_owned_interview

router = APIRouter(prefix="/interviews", tags=["interviews"])
app_router = APIRouter(prefix="/applications", tags=["interviews"])


def _one(db, iv_id: uuid.UUID) -> InterviewOut:
    iv = svc.load_interviews(db, Interview.id == iv_id, fresh=True)[0]
    return svc.to_interview_out(iv)


@app_router.get("/{application_id}/interviews", response_model=list[InterviewOut])
def list_for_application(application_id: uuid.UUID, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    return [svc.to_interview_out(i) for i in svc.load_interviews(db, Interview.application_id == a.id)]


@app_router.post("/{application_id}/interviews", response_model=InterviewOut, status_code=201)
def schedule(application_id: uuid.UUID, body: InterviewIn, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    iv = svc.schedule(db, user, a, body)
    db.commit()
    return _one(db, iv.id)


@router.get("", response_model=list[InterviewOut])
def list_interviews(
    response: Response,
    db: DB,
    user: Recruiter,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    status: Literal["scheduled", "completed", "cancelled"] | None = None,
    limit: Limit = 200,
    offset: Offset = 0,
):
    clause = Interview.application_id.in_(
        select(Application.id).join(Job, Job.id == Application.job_id).where(Job.recruiter_id == user.id)
    )
    if from_:
        clause = clause & (Interview.end_at >= svc.as_utc(from_))
    if to:
        clause = clause & (Interview.start_at <= svc.as_utc(to))
    if status:
        clause = clause & (Interview.status == status)
    rows = svc.load_interviews(db, clause, limit=limit, offset=offset)
    set_total(response, len(rows), limit, offset, lambda: db.scalar(select(func.count()).select_from(Interview).where(clause)) or 0)
    return [svc.to_interview_out(i) for i in rows]


@router.patch("/{interview_id}", response_model=InterviewOut)
def patch_interview(interview_id: uuid.UUID, body: InterviewPatch, db: DB, user: Recruiter):
    iv = get_owned_interview(db, user, interview_id)
    svc.update(db, user, iv, body)
    db.commit()
    return _one(db, interview_id)


@router.post("/{interview_id}/feedback", response_model=InterviewOut)
def feedback(interview_id: uuid.UUID, body: FeedbackIn, db: DB, user: Recruiter):
    iv = get_owned_interview(db, user, interview_id)
    svc.submit_feedback(db, user, iv, body)
    db.commit()
    return _one(db, interview_id)
