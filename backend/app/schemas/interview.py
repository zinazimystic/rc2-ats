from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.common import (
    ORM,
    Difficulty,
    InterviewStatus,
    InterviewType,
    Recommendation,
)


# ----------------------------------------------------------------------------- questions
class QuestionOut(ORM):
    id: UUID
    application_id: UUID
    difficulty: Difficulty
    category: str  # skill | project | gap | behavioral
    question: str
    answer_guidelines: list[str] = []
    related_skill: str | None = None
    source_quote: str | None = None
    source_verified: bool | None = None
    is_edited: bool = False
    position: int = 0
    created_at: datetime


class QuestionGenerateIn(BaseModel):
    beginner: int = Field(default=2, ge=0, le=8)
    intermediate: int = Field(default=3, ge=0, le=8)
    advanced: int = Field(default=2, ge=0, le=8)
    include_projects: bool = True
    # when true, existing questions are kept and new ones are appended
    append: bool = False


class QuestionIn(BaseModel):
    difficulty: Difficulty = "intermediate"
    category: str = Field(default="skill", max_length=40)
    question: str = Field(min_length=5, max_length=2000)
    answer_guidelines: list[str] = Field(default_factory=list, max_length=10)
    related_skill: str | None = Field(default=None, max_length=80)


class QuestionPatch(BaseModel):
    difficulty: Difficulty | None = None
    category: str | None = Field(default=None, max_length=40)
    question: str | None = Field(default=None, min_length=5, max_length=2000)
    answer_guidelines: list[str] | None = Field(default=None, max_length=10)
    related_skill: str | None = Field(default=None, max_length=80)


# ----------------------------------------------------------------------------- interviews
class FeedbackRatings(BaseModel):
    technical: int = Field(ge=1, le=5)
    communication: int = Field(ge=1, le=5)
    problem_solving: int = Field(ge=1, le=5)
    culture_fit: int = Field(ge=1, le=5)


class FeedbackIn(BaseModel):
    ratings: FeedbackRatings
    recommendation: Recommendation
    comments: str | None = Field(default=None, max_length=4000)


class FeedbackOut(ORM):
    id: UUID
    interview_id: UUID
    author_id: UUID
    author_name: str = ""
    ratings: FeedbackRatings
    recommendation: Recommendation
    comments: str | None = None
    created_at: datetime


class ConflictOut(BaseModel):
    kind: str  # interviewer | candidate
    interview_id: UUID
    start_at: datetime
    end_at: datetime
    with_whom: str  # name of the other candidate / the interviewer
    message: str


class InterviewIn(BaseModel):
    interviewer_name: str = Field(min_length=1, max_length=120)
    interviewer_email: EmailStr | None = None
    interview_type: InterviewType = "technical"
    start_at: datetime  # ISO 8601; naive values are treated as UTC
    duration_minutes: int = Field(default=60, ge=15, le=480)
    location: str | None = Field(default=None, max_length=300)  # room or meeting link
    notes: str | None = Field(default=None, max_length=2000)
    force: bool = False  # schedule even when conflicts exist


class InterviewPatch(BaseModel):
    interviewer_name: str | None = Field(default=None, min_length=1, max_length=120)
    interviewer_email: EmailStr | None = None
    interview_type: InterviewType | None = None
    start_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    status: InterviewStatus | None = None
    force: bool = False

    @model_validator(mode="after")
    def _nonempty(self):
        if not any(v is not None for k, v in self.model_dump().items() if k != "force"):
            raise ValueError("Nothing to update")
        return self


class InterviewOut(ORM):
    id: UUID
    application_id: UUID
    candidate_id: UUID | None = None
    candidate_name: str = ""
    job_id: UUID | None = None
    job_title: str = ""
    interviewer_name: str
    interviewer_email: str | None = None
    interview_type: InterviewType
    start_at: datetime
    end_at: datetime
    location: str | None = None
    notes: str | None = None
    status: InterviewStatus
    has_conflict: bool = False
    conflict_details: list[ConflictOut] = []
    feedback: list[FeedbackOut] = []
    created_at: datetime


class ConflictErrorOut(BaseModel):
    """Body of the 409 returned when a conflict is detected and force is false."""

    detail: str
    code: str = "schedule_conflict"
    conflicts: list[ConflictOut]
