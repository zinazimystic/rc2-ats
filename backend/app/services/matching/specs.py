"""Plain, immutable inputs to the matcher/scorer. They deliberately contain NO protected or personal attributes
(no name, contact, age, gender, nationality...), so the score cannot depend on them by construction."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class ReqSpec:
    skill: str
    kind: str = "required"  # required | preferred
    importance: int = 3
    id: UUID | None = None

    @property
    def weight(self) -> float:
        return max(1, min(5, self.importance)) * (1.0 if self.kind == "required" else 0.5)


@dataclass(frozen=True)
class SkillSpec:
    name: str
    raw_name: str | None = None
    presence: str = "present"  # present | absent
    verification: str = "verified"  # verified | fuzzy | unverified | self_reported
    evidence: str | None = None
    start: int | None = None
    end: int | None = None
    source: str = "rules"


@dataclass(frozen=True)
class ChunkSpec:
    text: str
    start: int
    end: int
    section: str | None = None


@dataclass(frozen=True)
class ExpSpec:
    title: str | None = None
    skills: tuple[str, ...] = ()
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    description: str | None = None
    verification: str = "verified"


@dataclass(frozen=True)
class ProjSpec:
    name: str | None = None
    text: str = ""
    tech: tuple[str, ...] = ()
    verification: str = "verified"
    evidence: str | None = None
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class EduSpec:
    level: str | None = None
    field: str | None = None
    degree: str | None = None
    verification: str = "verified"


@dataclass(frozen=True)
class CandidateSpec:
    skills: tuple[SkillSpec, ...] = ()
    chunks: tuple[ChunkSpec, ...] = ()
    experience: tuple[ExpSpec, ...] = ()
    projects: tuple[ProjSpec, ...] = ()
    education: tuple[EduSpec, ...] = ()
    certifications: tuple[str, ...] = ()
    total_years_claimed: float | None = None
    interests: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobSpec:
    title: str = ""
    description: str = ""
    requirements: tuple[ReqSpec, ...] = ()
    min_experience_years: float = 0
    education_level: str = "none"
    qualifications: tuple[str, ...] = ()
    weights: dict = field(default_factory=lambda: {"skills": 50, "experience": 25, "projects": 15, "qualifications": 10})


@dataclass(frozen=True)
class Semantics:
    """Pre-computed embedding similarities. `available=False` -> keyword/alias matching only."""

    available: bool = False
    req_best: dict[int, tuple[float, int]] = field(default_factory=dict)  # req index -> (cosine, chunk index)
    project_sims: dict[int, float] = field(default_factory=dict)  # project index -> cosine to the job


NO_SEMANTICS = Semantics(False)
