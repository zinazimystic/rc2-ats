from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ApplicationStatus, CandidateBrief, Evidence, JobBrief


class TalentSearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    job_id: UUID | None = None  # restrict to applicants of this job
    limit: int = Field(default=20, ge=1, le=50)


class SearchApplicationRef(BaseModel):
    application_id: UUID
    job_id: UUID
    job_title: str
    status: ApplicationStatus


class TalentSearchResult(BaseModel):
    candidate: CandidateBrief
    resume_id: UUID
    score: float  # 0..100
    semantic_score: float | None = None  # 0..100
    skill_coverage: float | None = None  # 0..100
    matched_skills: list[str] = []
    evidence: list[Evidence] = []
    applications: list[SearchApplicationRef] = []
    in_talent_pool: bool = False


class TalentSearchOut(BaseModel):
    query: str
    detected_skills: list[str] = []
    mode: str  # semantic | keyword
    results: list[TalentSearchResult] = []
    warning: str | None = None


class RecommendationOut(BaseModel):
    job: JobBrief
    score: float  # 0..100
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    reason: str = ""


class TalentPoolItem(BaseModel):
    candidate: CandidateBrief
    resume_id: UUID
    score: float
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    previously_applied_to: str | None = None
    invited: bool = False
