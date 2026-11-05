"""Deterministic scoring. Pure functions of (JobSpec, CandidateSpec, requirement results, Semantics): same input -> same score.
The LLM never produces a number that enters the total."""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.schemas.application import ComponentScore, RequirementResult
from app.services.matching.specs import CandidateSpec, ExpSpec, JobSpec, ProjSpec, Semantics
from app.services.parsing import dates
from app.services.parsing.normalizer import taxonomy

COMPONENTS = ("skills", "experience", "projects", "qualifications")
LEVEL_RANK = {"none": 0, "high_school": 1, "diploma": 2, "bachelor": 3, "master": 4, "phd": 5}
_GENERIC_TITLE = {"developer", "engineer", "programmer", "software", "specialist", "senior", "junior", "sr", "jr", "lead", "i", "ii", "iii",
                  "the", "of", "and", "a", "an", "intern", "associate", "principal", "staff", "full", "time", "remote"}
TECH_FIELDS = re.compile(r"comput|software|informat|engineer|data|science|math|technolog|electr|statist|cyber|AI|machine", re.I)


@dataclass
class ScoreResult:
    total: float
    components: dict[str, ComponentScore]
    notes: list[str]


def r1(x: float) -> float:
    return round(x + 1e-9, 1)


# --------------------------------------------------------------------------- components
def skills_component(job: JobSpec, results: list[RequirementResult]) -> tuple[float | None, dict]:
    if not job.requirements:
        return None, {"reason": "The job lists no skill requirements"}
    num = den = 0.0
    for req, res in zip(job.requirements, results):
        num += req.weight * res.credit
        den += req.weight
    score = 100.0 * num / den if den else 0.0
    return score, {
        "evidenced": [r.skill for r in results if r.status == "evidenced"],
        "partial": [r.skill for r in results if r.status == "partial"],
        "missing_evidence": [r.skill for r in results if r.status == "missing_evidence"],
        "confirmed_absent": [r.skill for r in results if r.status == "confirmed_absent"],
    }


def _title_tokens(t: str | None) -> set[str]:
    toks = re.findall(r"[a-z]+", re.sub(r"[-/]", "", (t or "").lower()))
    return {x for x in toks if x not in _GENERIC_TITLE and len(x) > 2}


def _is_relevant(e: ExpSpec, job: JobSpec, core: set[str]) -> bool:
    tax = taxonomy()
    skills = {tax.canonical(s) for s in e.skills} | set(tax.skills_in(e.description or ""))
    if skills & core:
        return True
    return bool(_title_tokens(e.title) & _title_tokens(job.title))


def experience_component(job: JobSpec, cand: CandidateSpec) -> tuple[float, dict]:
    tax = taxonomy()
    req = float(job.min_experience_years or 0)
    core = {tax.canonical(r.skill) for r in job.requirements if r.importance >= 3 and r.kind == "required"} or {
        tax.canonical(r.skill) for r in job.requirements
    }
    # a role using a closely related technology (Flask for Django, MySQL for PostgreSQL) is relevant experience too
    core = core | {rel for c in core for rel, w in tax.related(c).items() if w >= 0.5}
    all_iv, rel_iv, undated = [], [], 0
    for e in cand.experience:
        if e.verification == "unverified":
            continue
        iv = dates.to_interval(e.start_date, e.end_date, e.current)
        if iv is None:
            undated += 1
            continue
        all_iv.append(iv)
        if _is_relevant(e, job, core):
            rel_iv.append(iv)
    total = dates.total_years(all_iv)
    relevant = dates.total_years(rel_iv)
    other = dates.subtract_years(all_iv, rel_iv)
    claim_only = False
    if not all_iv and cand.total_years_claimed:
        relevant = round(0.6 * cand.total_years_claimed, 2)
        total, claim_only = cand.total_years_claimed, True
    details = {
        "required_years": req, "total_years": total, "relevant_years": relevant, "other_years": other,
        "roles": len(cand.experience), "undated_roles": undated, "claim_only": claim_only,
        "missing_evidence": not all_iv and not claim_only,
    }
    if req <= 0:
        score = 100.0 if (all_iv or claim_only) else 50.0
    else:
        score = 100.0 * min(1.0, (relevant + 0.25 * other) / req)
    return score, details


def _scale_sim(sim: float) -> float:
    return max(0.0, min(1.0, (sim - 0.25) / (0.65 - 0.25)))


def projects_component(job: JobSpec, cand: CandidateSpec, sem: Semantics) -> tuple[float, dict]:
    tax = taxonomy()
    if not cand.projects:
        return 0.0, {"missing_evidence": True, "projects": 0, "top": []}
    reqs = {tax.canonical(r.skill): r.weight for r in job.requirements}
    total_w = sum(reqs.values())
    scored: list[tuple[float, str]] = []
    for i, p in enumerate(cand.projects):
        techs = {tax.canonical(t) for t in p.tech} | set(tax.skills_in(p.text))
        overlap = 0.0
        if total_w:
            covered = 0.0
            for k, w in reqs.items():
                if k in techs:
                    covered += w
                else:  # closely related technology earns partial credit (capped like skill credit)
                    rel = max((min(0.7, rw) for t, rw in tax.related(k).items() if t in techs and rw >= 0.4), default=0.0)
                    covered += w * rel
            overlap = min(1.0, covered / (0.6 * total_w))
        if sem.available and i in sem.project_sims:
            s = 0.5 * _scale_sim(sem.project_sims[i]) + 0.5 * overlap
        else:
            s = overlap
        if p.verification == "unverified":
            s *= 0.5
        scored.append((s, p.name or f"Project {i + 1}"))
    scored.sort(key=lambda x: -x[0])
    top = scored[:2]
    score = 100.0 * sum(s for s, _ in top) / len(top)
    return score, {"projects": len(cand.projects), "top": [{"name": n, "score": r1(100 * s)} for s, n in top], "semantic": sem.available}


def qualifications_component(job: JobSpec, cand: CandidateSpec) -> tuple[float | None, dict]:
    req_level = LEVEL_RANK.get(job.education_level, 0)
    if req_level == 0 and not job.qualifications:
        return None, {"reason": "The job sets no education or certification requirement"}
    edu = [e for e in cand.education if e.verification != "unverified"]
    have = max((LEVEL_RANK.get(e.level or "none", 0) for e in edu), default=0)
    details: dict = {"required_level": job.education_level, "candidate_level": next((k for k, v in LEVEL_RANK.items() if v == have), "none")}
    has_evidence = bool(edu) or bool(cand.certifications)
    if not has_evidence:
        details["missing_evidence"] = True
        return 0.0, details
    if req_level == 0:
        level_score = 1.0
    else:
        level_score = 1.0 if have >= req_level else have / req_level
    fields = " ".join(e.field or e.degree or "" for e in edu)
    job_text = (job.title + " " + job.description + " " + " ".join(r.skill for r in job.requirements)).lower()
    jt_tokens = set(re.findall(r"[a-z]{4,}", job_text))
    f_tokens = set(re.findall(r"[a-z]{4,}", fields.lower()))
    tech_job = any((taxonomy().category(r.skill) or "") in {"language", "framework", "database", "devops", "cloud", "data"} for r in job.requirements)
    if not fields.strip():
        field_rel = 0.5
    elif f_tokens & jt_tokens or (tech_job and TECH_FIELDS.search(fields)):
        field_rel = 1.0
    else:
        field_rel = 0.4
    if job.qualifications:
        pool = list(cand.certifications) + [e.degree or "" for e in edu]
        matched = [q for q in job.qualifications if any(fuzz.token_set_ratio(q.lower(), p.lower()) >= 80 for p in pool if p)]
        cert_frac = len(matched) / len(job.qualifications)
        score = 0.6 * (0.8 * level_score + 0.2 * field_rel) + 0.4 * cert_frac
        details.update(certifications_matched=matched, certifications_required=len(job.qualifications))
    else:
        score = 0.8 * level_score + 0.2 * field_rel
    details.update(level_score=round(level_score, 2), field_relevance=field_rel)
    return 100.0 * score, details


# --------------------------------------------------------------------------- total
def score(job: JobSpec, cand: CandidateSpec, results: list[RequirementResult], sem: Semantics) -> ScoreResult:
    raw: dict[str, tuple[float | None, dict]] = {
        "skills": skills_component(job, results),
        "experience": experience_component(job, cand),
        "projects": projects_component(job, cand, sem),
        "qualifications": qualifications_component(job, cand),
    }
    w = {k: float(job.weights.get(k, 0) or 0) for k in COMPONENTS}
    applicable = {k for k, (s, _) in raw.items() if s is not None and w[k] > 0}
    wsum = sum(w[k] for k in applicable)
    comps: dict[str, ComponentScore] = {}
    total = 0.0
    notes: list[str] = []
    for k in COMPONENTS:
        s, d = raw[k]
        if k in applicable and wsum > 0:
            eff = 100.0 * w[k] / wsum
            pts = (s or 0) * eff / 100.0
            total += pts
            comps[k] = ComponentScore(score=r1(s or 0), weight=round(eff, 2), points=r1(pts), applicable=True, details=d)
        else:
            if s is None:
                notes.append(f"{k} not applicable: {d.get('reason', '')}")
            comps[k] = ComponentScore(score=r1(s or 0), weight=0.0, points=0.0, applicable=False, details=d)
    return ScoreResult(total=r1(max(0.0, min(100.0, total))), components=comps, notes=notes)
