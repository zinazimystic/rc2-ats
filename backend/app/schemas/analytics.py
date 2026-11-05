from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORM, CandidateBrief, JobBrief


class Kpis(BaseModel):
    active_jobs: int = 0
    total_jobs: int = 0
    total_applications: int = 0
    shortlisted: int = 0
    pending_reviews: int = 0  # ai_assessed + recruiter_review
    interviews_scheduled: int = 0  # upcoming scheduled interviews
    selected: int = 0
    rejected: int = 0


class JobStageCount(BaseModel):
    job_id: UUID
    title: str
    total: int
    by_stage: dict[str, int] = {}


class StageCount(BaseModel):
    stage: str
    label: str
    count: int


class SkillGap(BaseModel):
    skill: str
    count: int  # applicants lacking evidence
    percent: float  # of assessed applicants


class ScoreBucket(BaseModel):
    bucket: str  # "0-20", "20-40", ...
    count: int


class ActivityItem(BaseModel):
    at: datetime
    text: str
    application_id: UUID | None = None


class AnalyticsOut(BaseModel):
    kpis: Kpis
    applications_by_job: list[JobStageCount] = []
    stage_funnel: list[StageCount] = []
    shortlist_rate: float | None = None  # shortlisted+ / total, 0..1
    avg_processing_seconds: float | None = None  # submitted -> AI assessment available
    avg_time_to_decision_hours: float | None = None
    top_skill_gaps: list[SkillGap] = []
    score_distribution: list[ScoreBucket] = []
    recent_activity: list[ActivityItem] = []
    job_filter: JobBrief | None = None


class NotificationOut(ORM):
    id: UUID
    type: str
    channel: str = "in_app"  # in_app | email_sim (simulated email outbox)
    title: str
    body: str | None = None
    link: str | None = None
    recipient_email: str | None = None
    read: bool
    created_at: datetime


class DuplicateOut(BaseModel):
    id: UUID
    status: str  # pending | confirmed | dismissed
    reasons: list[str] = []
    similarity: float | None = None
    candidate_a: CandidateBrief
    candidate_b: CandidateBrief
    created_at: datetime
