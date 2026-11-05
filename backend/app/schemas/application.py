from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import (
    ORM,
    ApplicationStatus,
    CandidateBrief,
    Evidence,
    EvidenceStatus,
    Flag,
    JobBrief,
    MatchType,
    ProcessingState,
    RequirementKind,
)
from app.schemas.interview import InterviewOut
from app.schemas.resume import ResumeDetailOut


# ----------------------------------------------------------------------------- assessment
class RequirementResult(BaseModel):
    requirement_id: UUID | None = None
    skill: str
    kind: RequirementKind
    importance: int
    status: EvidenceStatus
    credit: float = Field(ge=0, le=1)
    match_type: MatchType = "none"
    matched_as: str | None = None  # the candidate skill / related skill that matched
    evidence: list[Evidence] = []
    explanation: str = ""


class ComponentScore(BaseModel):
    score: float  # 0..100 raw component score
    weight: float  # effective weight (after renormalisation) in %, sums to 100
    points: float  # contribution to the total (score * weight / 100)
    applicable: bool = True
    details: dict = {}


class LearningSuggestion(BaseModel):
    skill: str
    suggestion: str


class AssessmentOut(ORM):
    id: UUID
    application_id: UUID
    job_version: int
    total_score: float
    override_score: float | None = None
    override_reason: str | None = None
    effective_score: float
    components: dict[str, ComponentScore]  # skills | experience | projects | qualifications
    requirements: list[RequirementResult] = []
    strengths: list[str] = []
    gaps: list[str] = []
    learning_suggestions: list[LearningSuggestion] = []
    summary: str | None = None
    summary_method: str | None = None  # llm | template
    flags: list[Flag] = []
    semantic_available: bool = True
    stale: bool = False  # job requirements changed after this assessment
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------------- recruiter views
class ComponentSummary(BaseModel):
    skills: float | None = None
    experience: float | None = None
    projects: float | None = None
    qualifications: float | None = None


class ApplicationRowOut(BaseModel):
    """One row of the ranked applicants table for a job."""

    id: UUID
    candidate: CandidateBrief
    status: ApplicationStatus
    processing_state: ProcessingState
    processing_error: str | None = None
    effective_score: float | None = None
    total_score: float | None = None
    override_score: float | None = None
    components: ComponentSummary = ComponentSummary()
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    flags: list[Flag] = []
    is_duplicate: bool = False
    resume_id: UUID | None = None
    applied_at: datetime
    updated_at: datetime


class JobApplicantsOut(BaseModel):
    job: JobBrief
    total: int
    status_counts: dict[str, int] = {}
    items: list[ApplicationRowOut]


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class NoteOut(ORM):
    id: UUID
    application_id: UUID
    author_id: UUID
    author_name: str = ""
    body: str
    created_at: datetime


class HistoryEventOut(ORM):
    id: UUID
    action: str  # status_change | override | note_added | interview_scheduled | ...
    from_value: str | None = None
    to_value: str | None = None
    actor_id: UUID | None = None
    actor_name: str | None = None
    actor_role: str | None = None  # recruiter | candidate | system
    note: str | None = None
    created_at: datetime


class ApplicationDetailOut(BaseModel):
    id: UUID
    job: JobBrief
    candidate: CandidateBrief
    resume: ResumeDetailOut | None = None
    status: ApplicationStatus
    processing_state: ProcessingState
    processing_error: str | None = None
    cover_note: str | None = None
    is_duplicate: bool = False
    assessment: AssessmentOut | None = None
    allowed_transitions: list[ApplicationStatus] = []
    notes_count: int = 0
    interviews: list[InterviewOut] = []
    applied_at: datetime
    updated_at: datetime


class TransitionIn(BaseModel):
    to_status: ApplicationStatus
    reason: str | None = Field(default=None, max_length=1000)


class OverrideIn(BaseModel):
    score: float = Field(ge=0, le=100)
    reason: str = Field(min_length=3, max_length=1000)


class FairnessVariant(BaseModel):
    name: str  # e.g. "name_swap", "gender_swap", "age_shift", "nationality_swap"
    description: str
    score: float
    delta: float
    model_input_identical: bool


class FairnessOut(BaseModel):
    baseline_score: float
    max_abs_delta: float
    passed: bool
    variants: list[FairnessVariant]
    note: str


class CompareCandidate(BaseModel):
    application_id: UUID
    candidate: CandidateBrief
    status: ApplicationStatus
    effective_score: float | None = None
    components: ComponentSummary = ComponentSummary()
    requirements: list[RequirementResult] = []
    strengths: list[str] = []
    gaps: list[str] = []
    flags: list[Flag] = []
    missing_information: list[str] = []


class CompareOut(BaseModel):
    job: JobBrief
    candidates: list[CompareCandidate]


# ----------------------------------------------------------------------------- candidate views
class ApplyIn(BaseModel):
    job_id: UUID
    cover_note: str | None = Field(default=None, max_length=3000)


class TimelineItem(BaseModel):
    label: str  # candidate-facing label, no internal scores
    at: datetime


class CandidateInterviewOut(BaseModel):
    id: UUID
    interview_type: str
    start_at: datetime
    end_at: datetime
    location: str | None = None
    interviewer_name: str | None = None
    status: str


class CandidateApplicationOut(BaseModel):
    """Candidate-facing application. Never contains scores, notes or rankings."""

    id: UUID
    job: JobBrief
    status: ApplicationStatus
    status_label: str
    processing_state: ProcessingState
    processing_error: str | None = None
    resume_id: UUID | None = None
    resume_filename: str | None = None
    cover_note: str | None = None
    timeline: list[TimelineItem] = []
    interviews: list[CandidateInterviewOut] = []
    can_withdraw: bool = True
    applied_at: datetime
    updated_at: datetime
