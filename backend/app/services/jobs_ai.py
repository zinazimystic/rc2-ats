"""Job description -> requirements draft (LLM verified against the text, taxonomy-scan fallback) and job embeddings."""
from __future__ import annotations

import logging
import re
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.db.session import SessionLocal
from app.models import Job
from app.schemas.job import ExtractedSkill, JobExtractOut
from app.services.ai import llm, prompts
from app.services.matching import builders
from app.services.parsing.normalizer import taxonomy
from app.services.parsing.verifier import Index

log = logging.getLogger("app.jobs_ai")
_LEVELS = {"none", "high_school", "diploma", "bachelor", "master", "phd"}
_PREF = re.compile(r"nice[- ]to[- ]have|preferred|bonus|plus\b|good to have|desirable|a plus|optional|advantage", re.I)
_REQ = re.compile(r"required|requirements?|must[- ]have|you (?:will )?(?:need|have|bring)|qualifications|what we(?:'|’)re looking for|essential", re.I)


class _JS(BaseModel):
    skill: str
    importance: int = 3
    evidence: str | None = None

    @field_validator("importance", mode="before")
    @classmethod
    def _imp(cls, v):
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return 3


class _JobLLM(BaseModel):
    required_skills: list[_JS] = []
    preferred_skills: list[_JS] = []
    min_experience_years: float | None = None
    education_level: str | None = None
    qualifications: list[str] = []

    @field_validator("min_experience_years", mode="before")
    @classmethod
    def _y(cls, v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None


def _years(text: str) -> float | None:
    vals = [float(x) for x in re.findall(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)", text, re.I)]
    vals = [v for v in vals if 0 < v <= 40]
    return min(vals) if vals else None


def _education(text: str) -> str | None:
    t = text.lower()
    for level, rx in (("phd", r"ph\.?d|doctorate"), ("master", r"master'?s|\bm\.?sc\b|\bmba\b"),
                      ("bachelor", r"bachelor'?s?|\bb\.?sc\b|\bb\.?tech\b|undergraduate|degree in|b\.?e\b"),
                      ("diploma", r"diploma|associate degree")):
        if re.search(rx, t):
            return level
    return None


def _rules(title: str | None, description: str, warnings: list[str]) -> JobExtractOut:
    tax = taxonomy()
    mode = "required"
    req: dict[str, ExtractedSkill] = {}
    pref: dict[str, ExtractedSkill] = {}
    first_seen = 0
    for line in description.split("\n"):
        stripped = line.strip()
        short_heading = len(stripped) < 60 and (stripped.endswith(":") or stripped.isupper() or len(stripped.split()) <= 4)
        if short_heading and _PREF.search(stripped):
            mode = "preferred"
        elif short_heading and _REQ.search(stripped):
            mode = "required"
        line_mode = "preferred" if _PREF.search(stripped) and len(stripped) > 12 else mode
        for h in tax.find(line):
            if h.name in req or h.name in pref:
                continue
            first_seen += 1
            ev = line.strip()[:200]
            imp = max(2, 5 - first_seen // 3) if line_mode == "required" else 2
            (req if line_mode == "required" else pref)[h.name] = ExtractedSkill(skill=h.name, importance=imp, verified=True, evidence=ev)
    if not req and not pref:
        warnings.append("No known skills were detected in the description; add requirements manually.")
    return JobExtractOut(
        required_skills=list(req.values()), preferred_skills=list(pref.values()), min_experience_years=_years(description),
        education_level=_education(description), qualifications=[], method="rules", warnings=warnings,
    )


def extract_job_requirements(title: str | None, description: str) -> JobExtractOut:
    warnings: list[str] = []
    description = (description or "").strip()
    if llm.llm_available():
        try:
            out = llm.json_call(
                prompts.JOB_EXTRACT_SYSTEM,
                f"<job>\nTitle: {title or ''}\n{description[:12000]}\n</job>\nReturn the json object now.",
                _JobLLM, max_tokens=1800, cache_kind="job_extract",
            )
            idx = Index(description)
            tax = taxonomy()
            seen: set[str] = set()

            def conv(items: list[_JS], kind: str) -> list[ExtractedSkill]:
                res = []
                for it in items[:40]:
                    raw = it.skill.strip()
                    if not raw or len(raw) > 80:
                        continue
                    canon = tax.canonical(raw)
                    if canon.lower() in seen:
                        continue
                    seen.add(canon.lower())
                    verified = idx.contains_term(raw) or idx.contains_term(canon) or any(
                        idx.contains_term(a) for a in tax.skills.get(canon, {}).get("aliases", [])
                    ) or idx.verify(it.evidence).verification != "unverified"
                    if not verified:
                        warnings.append(f'"{canon}" was suggested by the AI but does not appear in the description - please check it.')
                    res.append(ExtractedSkill(skill=canon, importance=it.importance if kind == "required" else min(it.importance, 3),
                                              verified=bool(verified), evidence=(it.evidence or None)))
                return res

            req = conv(out.required_skills, "required")
            pref = conv(out.preferred_skills, "preferred")
            lvl = out.education_level if out.education_level in _LEVELS else None
            if not req and not pref:
                raise llm.LLMError("empty extraction")
            return JobExtractOut(
                required_skills=req, preferred_skills=pref, min_experience_years=out.min_experience_years or _years(description),
                education_level=lvl or _education(description), qualifications=[q.strip() for q in out.qualifications if q.strip()][:10],
                method="llm", warnings=warnings,
            )
        except Exception as exc:
            warnings.append(f"AI extraction unavailable ({exc}); used a keyword scan instead. Review the draft carefully.")
    else:
        warnings.append("AI extraction is not configured; used a keyword scan instead. Review the draft carefully.")
    return _rules(title, description, warnings)


def embed_job(job_id: UUID) -> None:
    """Embed job text + each requirement. Failures are tolerated (matching falls back to keywords)."""
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job is None:
                return
            job.embedding = None
            for r in job.requirements:
                r.embedding = None
            db.flush()
            builders.ensure_job_embeddings(db, job)
            db.commit()
    except Exception as exc:
        log.warning("embed_job failed for %s: %s", job_id, exc)
