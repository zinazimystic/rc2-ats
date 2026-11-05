"""Evidence-first requirement matching: every credit points at a verbatim resume quote (or says why not)."""
from __future__ import annotations

from app.core.config import settings
from app.schemas.application import RequirementResult
from app.schemas.common import Evidence
from app.services.matching.specs import CandidateSpec, ChunkSpec, JobSpec, ReqSpec, Semantics, SkillSpec
from app.services.parsing.normalizer import taxonomy

MAX_QUOTE = 300


def compute_semantics(
    req_vecs: list[list[float] | None],
    chunk_vecs: list[list[float] | None],
    job_vec: list[float] | None = None,
    project_vecs: list[list[float] | None] | None = None,
) -> Semantics:
    """Cosine similarities between job requirements / job text and the candidate's chunks / projects."""
    import numpy as np

    cv = [(i, v) for i, v in enumerate(chunk_vecs) if v is not None]
    if not cv:
        return Semantics(False)
    cmat = np.asarray([v for _, v in cv], dtype=float)
    cmat = cmat / (np.linalg.norm(cmat, axis=1, keepdims=True) + 1e-12)
    req_best: dict[int, tuple[float, int]] = {}
    for ri, rv in enumerate(req_vecs):
        if rv is None:
            continue
        r = np.asarray(rv, dtype=float)
        r = r / (np.linalg.norm(r) + 1e-12)
        sims = cmat @ r
        j = int(np.argmax(sims))
        req_best[ri] = (float(sims[j]), cv[j][0])
    proj: dict[int, float] = {}
    if job_vec is not None and project_vecs:
        jv = np.asarray(job_vec, dtype=float)
        jv = jv / (np.linalg.norm(jv) + 1e-12)
        for pi, pv in enumerate(project_vecs):
            if pv is not None:
                p = np.asarray(pv, dtype=float)
                proj[pi] = float(p @ jv / (np.linalg.norm(p) + 1e-12))
    return Semantics(True, req_best, proj)


def _ev_skill(s: SkillSpec) -> list[Evidence]:
    if not s.evidence:
        return []
    return [Evidence(quote=s.evidence[:MAX_QUOTE], start=s.start, end=s.end)]


def _ev_chunk(c: ChunkSpec, sim: float) -> Evidence:
    return Evidence(quote=c.text[:MAX_QUOTE], start=c.start, end=min(c.end, c.start + MAX_QUOTE), similarity=round(sim, 3), section=c.section)


def match_one(req: ReqSpec, idx: int, cand: CandidateSpec, sem: Semantics) -> RequirementResult:
    tax = taxonomy()
    target = tax.canonical(req.skill)
    by_name: dict[str, SkillSpec] = {}
    for s in cand.skills:
        by_name.setdefault(tax.canonical(s.name), s)

    base = dict(requirement_id=req.id, skill=req.skill, kind=req.kind, importance=req.importance)

    # 1. the candidate states they do NOT have the skill -> never guess otherwise
    own = by_name.get(target)
    if own is not None and own.presence == "absent":
        return RequirementResult(**base, status="confirmed_absent", credit=0.0, match_type="none",
                                 explanation=f"The candidate states they do not have {req.skill} experience.")

    best_credit, best = 0.0, None  # type: float, RequirementResult | None

    def consider(res: RequirementResult) -> None:
        nonlocal best_credit, best
        if res.credit > best_credit:
            best_credit, best = res.credit, res

    # 2. exact / alias match on an extracted skill
    if own is not None:
        surface = (own.raw_name or own.name).strip()
        mt = "exact" if surface.lower() == req.skill.strip().lower() or own.name.lower() == req.skill.strip().lower() else "alias"
        if own.verification in ("verified", "fuzzy"):
            ev = _ev_skill(own)
            where = f' in the resume: "{ev[0].quote[:140]}"' if ev else ""
            consider(RequirementResult(**base, status="evidenced", credit=1.0, match_type=mt, matched_as=own.name, evidence=ev,
                                       explanation=f"{req.skill} is evidenced{where}."
                                       + (f" (written as {surface})" if mt == "alias" and surface.lower() != req.skill.lower() else "")))
        else:
            ev = _ev_skill(own)
            why = "self-reported by the candidate" if own.verification == "self_reported" else "claimed but not verifiable in the resume text"
            consider(RequirementResult(**base, status="partial", credit=0.5, match_type="self_reported", matched_as=own.name, evidence=ev,
                                       explanation=f"{req.skill} is {why}; half credit until confirmed."))

    # 3. related skill from the taxonomy
    if best_credit < 1.0:
        for rname, w in tax.related(target).items():
            rs = by_name.get(rname)
            if rs is None or rs.presence == "absent" or rs.verification in ("unverified",):
                continue
            credit = min(0.7, float(w))
            consider(RequirementResult(**base, status="partial", credit=round(credit, 3), match_type="related", matched_as=rs.name,
                                       evidence=_ev_skill(rs),
                                       explanation=f"No direct {req.skill} evidence, but the candidate lists related skill {rs.name} (relatedness {w:.2f})."))

    # 4. semantic best chunk
    if best_credit < 0.7 and sem.available and idx in sem.req_best:
        sim, ci = sem.req_best[idx]
        if ci < len(cand.chunks):
            chunk = cand.chunks[ci]
            if sim >= settings.sem_strong:
                consider(RequirementResult(**base, status="partial", credit=0.7, match_type="semantic", evidence=[_ev_chunk(chunk, sim)],
                                           explanation=f"No explicit {req.skill} mention, but a resume passage is strongly similar (similarity {sim:.2f})."))
            elif sim >= settings.sem_weak:
                consider(RequirementResult(**base, status="partial", credit=0.35, match_type="semantic", evidence=[_ev_chunk(chunk, sim)],
                                           explanation=f"Weak semantic similarity to {req.skill} (similarity {sim:.2f}); needs human review."))

    if best is not None:
        return best
    return RequirementResult(**base, status="missing_evidence", credit=0.0, match_type="none",
                             explanation=f"No evidence of {req.skill} was found in the resume. This is missing evidence, not proof the candidate lacks it.")


def match_requirements(job: JobSpec, cand: CandidateSpec, sem: Semantics) -> list[RequirementResult]:
    return [match_one(r, i, cand, sem) for i, r in enumerate(job.requirements)]
