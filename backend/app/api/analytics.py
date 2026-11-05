from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import DB, Recruiter
from app.schemas.analytics import AnalyticsOut
from app.services import analytics
from app.services.access import get_owned_job

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOut)
def overview(db: DB, user: Recruiter, job_id: uuid.UUID | None = None):
    job = get_owned_job(db, user, job_id) if job_id else None
    return analytics.overview(db, user, job)
