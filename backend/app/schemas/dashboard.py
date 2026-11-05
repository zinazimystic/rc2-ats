from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.schemas.application import CandidateApplicationOut, CandidateInterviewOut
from app.schemas.job import JobListItem
from app.schemas.resume import ProfileOut, ResumeOut
from app.schemas.search import RecommendationOut


class UpcomingInterviewOut(CandidateInterviewOut):
    application_id: UUID
    job_id: UUID
    job_title: str


class CandidateDashboardOut(BaseModel):
    """Everything the candidate home screen needs, in one request."""

    profile: ProfileOut
    resumes: list[ResumeOut] = []  # lightweight: no extracted text
    applications: list[CandidateApplicationOut] = []
    recommendations: list[RecommendationOut] = []  # top 6
    open_jobs: list[JobListItem] = []  # up to 50, has_applied set
    upcoming_interviews: list[UpcomingInterviewOut] = []
    unread_notifications: int = 0
