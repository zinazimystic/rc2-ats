from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import (
    ORM,
    ExtractionMethod,
    Flag,
    ParseStatus,
    Presence,
    SkillSource,
    Verification,
)


class ContactInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = []


class EducationItem(BaseModel):
    degree: str | None = None
    level: str | None = None  # none|high_school|diploma|bachelor|master|phd
    field: str | None = None
    institution: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    evidence: str | None = None
    start: int | None = None
    end: int | None = None
    verification: Verification = "verified"


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None  # "YYYY-MM" or "YYYY"
    end_date: str | None = None  # "YYYY-MM", "YYYY" or None when current
    current: bool = False
    description: str | None = None
    skills: list[str] = []
    evidence: str | None = None
    start: int | None = None
    end: int | None = None
    verification: Verification = "verified"


class ProjectItem(BaseModel):
    name: str | None = None
    description: str | None = None
    tech: list[str] = []
    url: str | None = None
    evidence: str | None = None
    start: int | None = None
    end: int | None = None
    verification: Verification = "verified"


class ParsedResume(BaseModel):
    contact: ContactInfo = ContactInfo()
    summary: str | None = None
    education: list[EducationItem] = []
    experience: list[ExperienceItem] = []
    projects: list[ProjectItem] = []
    certifications: list[str] = []
    total_years_claimed: float | None = None


class CandidateSkillOut(ORM):
    id: UUID
    name: str
    raw_name: str | None = None
    category: str | None = None
    presence: Presence = "present"
    source: SkillSource
    verification: Verification
    evidence: str | None = None
    start: int | None = None
    end: int | None = None
    removed: bool = False


class ResumeOut(ORM):
    id: UUID
    candidate_id: UUID
    filename: str
    content_type: str | None = None
    size: int
    parse_status: ParseStatus
    parse_error: str | None = None
    warnings: list[str] = []
    integrity_flags: list[Flag] = []
    extraction_method: ExtractionMethod | None = None
    page_count: int | None = None
    is_current: bool = True
    parsed: ParsedResume | None = None
    skills: list[CandidateSkillOut] = []
    created_at: datetime


class ResumeDetailOut(ResumeOut):
    # full extracted text; evidence start/end offsets index into this string
    text: str | None = None


class SkillAddIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    presence: Presence = "present"


class SkillPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    presence: Presence | None = None
    # recruiter/candidate confirms an unverified skill is correct
    confirm: bool | None = None
    removed: bool | None = None


class ParsedPatchIn(BaseModel):
    contact: ContactInfo | None = None
    summary: str | None = Field(default=None, max_length=4000)
    education: list[EducationItem] | None = None
    experience: list[ExperienceItem] | None = None
    projects: list[ProjectItem] | None = None
    certifications: list[str] | None = None


class ProfileIn(BaseModel):
    headline: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    links: list[str] | None = Field(default=None, max_length=10)
    interests: list[str] | None = Field(default=None, max_length=20)
    talent_pool_opt_in: bool | None = None
    retention_until: datetime | None = None


class ProfileOut(ORM):
    user_id: UUID
    full_name: str = ""
    email: str = ""
    headline: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = []
    interests: list[str] = []
    talent_pool_opt_in: bool = False
    retention_until: datetime | None = None
