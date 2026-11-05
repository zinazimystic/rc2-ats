from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.common import Flag
from app.schemas.resume import ParsedResume


@dataclass
class SkillDraft:
    name: str  # canonical
    raw_name: str | None
    category: str | None
    evidence: str | None
    start: int | None
    end: int | None
    verification: str  # verified | fuzzy | unverified
    source: str  # ai | rules


@dataclass
class Extraction:
    parsed: ParsedResume
    skills: list[SkillDraft]
    method: str  # llm | rules
    warnings: list[str] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
