from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import (
    ORM,
    EducationLevel,
    EmploymentType,
    ExtractionMethod,
    JobStatus,
    RequirementKind,
    WorkMode,
)


class JobWeights(BaseModel):
    skills: float = Field(default=50, ge=0, le=100)
    experience: float = Field(default=25, ge=0, le=100)
    projects: float = Field(default=15, ge=0, le=100)
    qualifications: float = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def _sum_100(self):
        total = self.skills + self.experience + self.projects + self.qualifications
        if abs(total - 100) > 0.01:
            raise ValueError("Scoring weights must add up to 100")
        return self


class RequirementIn(BaseModel):
    skill: str = Field(min_length=1, max_length=80)
    kind: RequirementKind = "required"
    importance: int = Field(default=3, ge=1, le=5)

    @field_validator("skill")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RequirementOut(ORM):
    id: UUID
    skill: str
    kind: RequirementKind
    importance: int


class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    employment_type: EmploymentType = "full_time"
    work_mode: WorkMode = "onsite"
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", max_length=8)
    description: str = Field(min_length=10, max_length=20000)
    min_experience_years: float = Field(default=0, ge=0, le=50)
    education_level: EducationLevel = "none"
    qualifications: list[str] = Field(default_factory=list, max_length=20)
    requirements: list[RequirementIn] = Field(default_factory=list, max_length=60)
    weights: JobWeights | None = None

    @model_validator(mode="after")
    def _salary_range(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min cannot exceed salary_max")
        return self


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    employment_type: EmploymentType | None = None
    work_mode: WorkMode | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    description: str | None = Field(default=None, min_length=10, max_length=20000)
    min_experience_years: float | None = Field(default=None, ge=0, le=50)
    education_level: EducationLevel | None = None
    qualifications: list[str] | None = Field(default=None, max_length=20)
    requirements: list[RequirementIn] | None = Field(default=None, max_length=60)
    weights: JobWeights | None = None


class JobOut(ORM):
    id: UUID
    recruiter_id: UUID
    title: str
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType
    work_mode: WorkMode
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str
    description: str
    min_experience_years: float
    education_level: EducationLevel
    qualifications: list[str] = []
    weights: JobWeights
    status: JobStatus
    version: int
    requirements: list[RequirementOut] = []
    applicant_count: int = 0
    shortlisted_count: int = 0
    pending_review_count: int = 0
    # candidate view only: whether the current candidate already applied
    has_applied: bool | None = None
    created_at: datetime
    updated_at: datetime


class JobListItem(ORM):
    id: UUID
    title: str
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType
    work_mode: WorkMode
    status: JobStatus
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = "USD"
    min_experience_years: float = 0
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    applicant_count: int = 0
    shortlisted_count: int = 0
    pending_review_count: int = 0
    has_applied: bool | None = None
    created_at: datetime


class JobExtractIn(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    description: str = Field(min_length=20, max_length=20000)


class ExtractedSkill(BaseModel):
    skill: str
    importance: int = Field(default=3, ge=1, le=5)
    # True when the skill (or an alias) literally appears in the description
    verified: bool = True
    evidence: str | None = None


class JobExtractOut(BaseModel):
    required_skills: list[ExtractedSkill] = []
    preferred_skills: list[ExtractedSkill] = []
    min_experience_years: float | None = None
    education_level: EducationLevel | None = None
    qualifications: list[str] = []
    method: ExtractionMethod = "llm"
    warnings: list[str] = []
