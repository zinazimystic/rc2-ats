"""STUB - Agent A replaces this."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Job, User
from app.schemas.search import RecommendationOut, TalentPoolItem, TalentSearchIn, TalentSearchOut


def talent_search(db: Session, recruiter: User, req: TalentSearchIn) -> TalentSearchOut:
    raise NotImplementedError


def recommend_jobs(db: Session, candidate: User, limit: int = 10) -> list[RecommendationOut]:
    raise NotImplementedError


def talent_pool(db: Session, job: Job, recruiter: User) -> list[TalentPoolItem]:
    raise NotImplementedError
