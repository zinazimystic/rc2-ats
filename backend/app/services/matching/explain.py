"""Human-readable explanation: strengths, gaps, learning areas, flags, summary. Template first; optional LLM narrative
that only sees the structured results (never resume text) and may only name skills that are real gaps."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.schemas.application import ComponentScore, LearningSuggestion, RequirementResult
from app.schemas.common import Flag
from app.services.ai import llm, prompts
from app.services.matching.specs import CandidateSpec, JobSpec, Semantics
from app.services.parsing.normalizer import taxonomy

log = logging.getLogger("app.explain")


@dataclass
class Explanation:
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    learning: list[LearningSuggestion] = field(default_factory=list)
    summary: str = ""
    summary_method: str = "template"
    flags: list[Flag] = field(default_factory=list)


class _Narrative(BaseModel):
    summary: str
    learning: list[dict] = []


def _join(items: list[str], limit: int = 6) -> str:
    items = list(items)
    s = ", ".join(items[:limit])
    return s + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def gap_skills(results: list[RequirementResult]) -> list[str]:
    """Skills where evidence is missing/absent/partial, required first, by importance."""
    order = sorted(
        (r for r in results if r.status in ("missing_evidence", "confirmed_absent", "partial") and r.credit < 0.7),
        key=lambda r: (r.kind != "required", -r.importance, r.skill.lower()),
    )
    return [r.skill for r in order]


def build_flags(cand: CandidateSpec, results: list[RequirementResult], components: dict[str, ComponentScore],
                sem: Semantics, resume_flags: list[dict]) -> list[Flag]:
    flags: list[Flag] = []
    for f in resume_flags or []:
        try:
            flags.append(Flag(**f))
        except Exception:
            continue
    if not cand.projects:
        flags.append(Flag(type="no_projects", severity="info", message="No projects were found in the resume (projects component scored as missing evidence)."))
    q = components.get("qualifications")
    if q and q.details.get("missing_evidence"):
        flags.append(Flag(type="missing_education", severity="warning", message="No education or certification evidence was found; this is treated as missing evidence, not as having no degree."))
    e = components.get("experience")
    if e and e.details.get("missing_evidence"):
        flags.append(Flag(type="missing_dates", severity="warning", message="No dated work experience could be read, so experience is scored conservatively."))
    unv = [r.skill for r in results if r.match_type == "self_reported" and r.kind == "required"]
    if unv:
        flags.append(Flag(type="unverified_claim", severity="warning", message=f"Unverified claims received only half credit: {_join(unv)}."))
    if not sem.available:
        flags.append(Flag(type="semantic_unavailable", severity="info", message="Semantic matching was unavailable; scoring used keyword/alias evidence only."))
    seen, out = set(), []
    for f in flags:
        k = (f.type, f.message)
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def explain(job: JobSpec, cand: CandidateSpec, results: list[RequirementResult], components: dict[str, ComponentScore],
            total: float, sem: Semantics, resume_flags: list[dict] | None = None, *, use_llm: bool = True) -> Explanation:
    tax = taxonomy()
    ex = Explanation()
    ex.flags = build_flags(cand, results, components, sem, resume_flags or [])

    req_all = [r for r in results if r.kind == "required"]
    ev_req = [r for r in req_all if r.status == "evidenced"]
    if ev_req:
        top = sorted(ev_req, key=lambda r: -r.importance)
        ex.strengths.append(f"Evidence found for {len(ev_req)} of {len(req_all)} required skills: {_join([r.skill for r in top])}.")
    ev_pref = [r.skill for r in results if r.kind == "preferred" and r.status == "evidenced"]
    if ev_pref:
        ex.strengths.append(f"Also evidences preferred skills: {_join(ev_pref)}.")
    exp = components.get("experience")
    if exp and exp.applicable:
        d = exp.details
        if d.get("required_years", 0) and d.get("relevant_years", 0) >= d["required_years"]:
            ex.strengths.append(f"{d['relevant_years']:.1f} years of relevant experience (job asks for {d['required_years']:g}).")
        elif d.get("required_years", 0) and d.get("relevant_years", 0) > 0:
            ex.gaps.append(f"{d['relevant_years']:.1f} years of relevant experience against {d['required_years']:g} required.")
        elif d.get("required_years", 0):
            ex.gaps.append(f"No relevant dated experience found against {d['required_years']:g} required years.")
    pr = components.get("projects")
    if pr and pr.details.get("top") and pr.score >= 50:
        ex.strengths.append(f"Relevant project work: {_join([t['name'] for t in pr.details['top']])}.")
    ql = components.get("qualifications")
    if ql and ql.applicable and not ql.details.get("missing_evidence") and ql.score >= 80:
        ex.strengths.append("Education / qualifications meet the job's requirements.")

    for r in sorted(results, key=lambda r: (r.kind != "required", -r.importance)):
        tag = "required" if r.kind == "required" else "preferred"
        if r.status == "missing_evidence":
            ex.gaps.append(f"No evidence of {r.skill} ({tag}).")
        elif r.status == "confirmed_absent":
            ex.gaps.append(f"Candidate states no {r.skill} experience ({tag}).")
        elif r.status == "partial" and r.kind == "required":
            how = {"related": f"only via related skill {r.matched_as}", "semantic": "only by similar wording", "self_reported": "unverified claim"}.get(r.match_type, "partial evidence")
            ex.gaps.append(f"{r.skill} only partially evidenced ({how}).")
    if pr and pr.details.get("missing_evidence"):
        ex.gaps.append("No projects found to demonstrate hands-on work.")
    if ql and ql.details.get("missing_evidence"):
        ex.gaps.append("No education evidence found for the required qualification level.")

    gaps = gap_skills(results)
    for g in gaps[:5]:
        ex.learning.append(LearningSuggestion(skill=g, suggestion=tax.learn_hint(g)))

    ncomp = ", ".join(f"{k} {v.score:.0f}" for k, v in components.items() if v.applicable)
    parts = [f"Scored {total:.1f}/100 for {job.title or 'this role'} ({ncomp})."]
    if req_all:
        parts.append(f"{len(ev_req)} of {len(req_all)} required skills are evidenced in the resume.")
    if gaps:
        parts.append(f"Main gaps: {_join(gaps, 4)}.")
    ex.summary = " ".join(parts)

    if use_llm and llm.llm_available():
        try:
            payload = {
                "job_title": job.title, "total_score": total,
                "components": {k: {"score": v.score, "weight": v.weight} for k, v in components.items() if v.applicable},
                "evidenced_skills": [r.skill for r in results if r.status == "evidenced"],
                "partial_skills": [r.skill for r in results if r.status == "partial"],
                "gap_skills": gaps[:8],
                "experience": exp.details if exp else {},
                "flags": [f.type for f in ex.flags],
            }
            out = llm.json_call(prompts.NARRATIVE_SYSTEM, "<results>\n" + json.dumps(payload, default=str) + "\n</results>", _Narrative,
                                max_tokens=700, cache_kind="narrative")
            allowed = {g.lower(): g for g in gaps}
            learn = []
            for item in out.learning:
                sk = str(item.get("skill", "")).strip()
                sug = str(item.get("suggestion", "")).strip()
                if sk.lower() in allowed and sug:
                    learn.append(LearningSuggestion(skill=allowed[sk.lower()], suggestion=sug[:300]))
            if out.summary.strip():
                ex.summary = out.summary.strip()[:900]
                ex.summary_method = "llm"
                if learn:
                    ex.learning = learn[:5]
        except Exception as exc:  # LLMUnavailable / LLMError / anything else: keep the template summary
            log.info("narrative fell back to template: %s", exc)
    return ex
