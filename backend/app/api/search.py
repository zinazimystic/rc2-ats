from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DB, Recruiter
from app.schemas.search import TalentSearchIn, TalentSearchOut
from app.services import search
from app.services.access import get_owned_job

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/talent", response_model=TalentSearchOut)
def talent(body: TalentSearchIn, db: DB, user: Recruiter):
    if body.job_id:
        get_owned_job(db, user, body.job_id)  # 404 for someone else's job
    return search.talent_search(db, user, body)
