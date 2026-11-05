"""Shared enums (as Literals) and base classes for every API schema."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


Role = Literal["recruiter", "candidate"]
ApplicationStatus = Literal[
    "submitted",
    "parsed",
    "ai_assessed",
    "recruiter_review",
    "shortlisted",
    "interview",
    "selected",
    "rejected",
    "withdrawn",
]
ProcessingState = Literal["queued", "processing", "done", "failed"]
ParseStatus = Literal["pending", "processing", "parsed", "failed"]
RequirementKind = Literal["required", "preferred"]
EvidenceStatus = Literal["evidenced", "partial", "missing_evidence", "confirmed_absent"]
MatchType = Literal["exact", "alias", "related", "semantic", "self_reported", "none"]
Verification = Literal["verified", "fuzzy", "unverified", "self_reported"]
SkillSource = Literal["ai", "rules", "candidate", "recruiter"]
Presence = Literal["present", "absent"]
Difficulty = Literal["beginner", "intermediate", "advanced"]
JobStatus = Literal["open", "closed"]
InterviewType = Literal["technical", "hr", "behavioral", "panel", "final"]
InterviewStatus = Literal["scheduled", "completed", "cancelled"]
Recommendation = Literal["strong_yes", "yes", "no", "strong_no"]
EducationLevel = Literal["none", "high_school", "diploma", "bachelor", "master", "phd"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship"]
WorkMode = Literal["onsite", "hybrid", "remote"]
ExtractionMethod = Literal["llm", "rules"]
Severity = Literal["info", "warning", "critical"]


class Msg(BaseModel):
    detail: str


class CandidateBrief(ORM):
    id: UUID
    full_name: str
    email: str
    headline: str | None = None
    location: str | None = None


class JobBrief(ORM):
    id: UUID
    title: str
    department: str | None = None
    location: str | None = None
    status: JobStatus = "open"


class Evidence(BaseModel):
    """A verbatim resume excerpt backing a claim. start/end are char offsets into Resume.text."""

    quote: str
    start: int | None = None
    end: int | None = None
    similarity: float | None = None
    section: str | None = None


class Flag(BaseModel):
    type: str  # e.g. unverified_claim, hidden_text, prompt_injection, low_text, no_projects
    message: str
    severity: Severity = "info"


