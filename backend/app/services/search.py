"""Semantic talent search, job recommendations and talent pool. Access is always filtered to what the viewer may see."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, inspect as sa_inspect, or_, select, text as sql_text
from sqlalchemy.orm import Session, joinedload, load_only, selectinload, undefer

from app.core.errors import NotFound
from app.db.types import utcnow
from app.models import Application, CandidateProfile, Job, Notification, Resume, ResumeChunk, User, job_vector_options
from app.schemas.common import CandidateBrief, Evidence, JobBrief
from app.schemas.search import (
    RecommendationOut, SearchApplicationRef, TalentPoolItem, TalentSearchIn, TalentSearchOut, TalentSearchResult,
)
from app.services.ai import embeddings
from app.services.matching import builders, matcher, scorer
from app.services.parsing.normalizer import taxonomy

log = logging.getLogger("app.search")
TOP_CHUNKS = 3


def _brief(u: User, p: CandidateProfile | None) -> CandidateBrief:
    return CandidateBrief(id=u.id, full_name=u.full_name, email=u.email, headline=p.headline if p else None, location=p.location if p else None)


def _scale(sim: float) -> float:
    return max(0.0, min(1.0, (sim - 0.25) / (0.65 - 0.25)))


# --------------------------------------------------------------------------- access
def _pool_ok(p: CandidateProfile | None) -> bool:
    return bool(p and p.talent_pool_opt_in and (p.retention_until is None or p.retention_until > utcnow()))


def accessible_users(db: Session, recruiter: User, *, job_id: UUID | None = None) -> dict[UUID, tuple[User, bool]]:
    """candidate_id -> (user with profile, in_talent_pool) in ONE query: applicants to the recruiter's jobs plus (when no job
    is given) opted-in candidates within retention. Merged duplicates and inactive accounts are excluded."""
    applicants = select(Application.candidate_id).join(Job, Job.id == Application.job_id).where(
        Job.recruiter_id == recruiter.id, Application.status != "withdrawn"
    )
    if job_id is not None:
        applicants = applicants.where(Application.job_id == job_id)
    allowed = User.id.in_(applicants)
    if job_id is None:
        pooled = select(CandidateProfile.user_id).where(
            CandidateProfile.talent_pool_opt_in.is_(True),
            or_(CandidateProfile.retention_until.is_(None), CandidateProfile.retention_until > utcnow()),
        )
        allowed = or_(allowed, User.id.in_(pooled))
    users = db.scalars(
        select(User).where(allowed, User.role == "candidate", User.is_active.is_(True)).options(joinedload(User.profile))
    ).unique().all()
    return {u.id: (u, _pool_ok(u.profile)) for u in users if not (u.profile is not None and u.profile.merged_into_id is not None)}


def accessible_candidates(db: Session, recruiter: User, *, job_id: UUID | None = None) -> dict[UUID, bool]:
    """candidate_id -> in_talent_pool (see `accessible_users`)."""
    return {cid: pool for cid, (_, pool) in accessible_users(db, recruiter, job_id=job_id).items()}


def _current_resumes(db: Session, candidate_ids: list[UUID], *, text: bool = False, chunks: bool = False, light: bool = False) -> dict[UUID, Resume]:
    """Each candidate's current parsed resume (skills included). Round trips: 1 + skills (+ chunks). `light` loads only the ids
    (enough for search, where evidence comes from chunks); `text` adds the resume text (keyword fallback only)."""
    if not candidate_ids:
        return {}
    opts = [selectinload(Resume.skills)]
    if light:
        opts.append(load_only(Resume.id, Resume.candidate_id, Resume.is_current, Resume.created_at))
    if text:
        opts.append(undefer(Resume.text))
    if chunks:
        opts.append(selectinload(Resume.chunks))
    rows = db.scalars(
        select(Resume).where(Resume.candidate_id.in_(candidate_ids), Resume.parse_status == "parsed", Resume.deleted_at.is_(None))
        .order_by(Resume.is_current.desc(), Resume.created_at.desc())
        .options(*opts)
    ).all()
    out: dict[UUID, Resume] = {}
    for r in rows:
        out.setdefault(r.candidate_id, r)
    return out


# --------------------------------------------------------------------------- semantic chunk lookup
@dataclass
class _Hit:
    sim: float
    text: str
    start: int
    end: int
    section: str | None


def _chunk_hits(db: Session, resume_ids: list[UUID], qv: list[float]) -> dict[UUID, list[_Hit]]:
    hits: dict[UUID, list[_Hit]] = {}
    if db.get_bind().dialect.name == "postgresql":
        try:
            rows = db.execute(
                sql_text(
                    "SELECT resume_id, text, start_char, end_char, section, 1 - (embedding <=> CAST(:q AS vector)) AS sim "
                    "FROM resume_chunks WHERE resume_id = ANY(:ids) AND embedding IS NOT NULL "
                    "ORDER BY embedding <=> CAST(:q AS vector) LIMIT 600"
                ),
                {"q": "[" + ",".join(f"{x:.6f}" for x in qv) + "]", "ids": list(resume_ids)},
            ).all()
            for rid, txt, s, e, sec, sim in rows:
                hits.setdefault(rid, []).append(_Hit(float(sim), txt, s, e, sec))
            return {k: sorted(v, key=lambda h: -h.sim)[:TOP_CHUNKS] for k, v in hits.items()}
        except Exception as exc:  # fall back to the portable path
            db.rollback()
            log.warning("pgvector query failed, using numpy fallback: %s", exc)
            hits = {}
    import numpy as np

    chunks = db.scalars(select(ResumeChunk).where(ResumeChunk.resume_id.in_(resume_ids), ResumeChunk.embedding.is_not(None))).all()
    if not chunks:
        return {}
    mat = np.asarray([c.embedding for c in chunks], dtype=float)
    mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    q = np.asarray(qv, dtype=float)
    q = q / (np.linalg.norm(q) + 1e-12)
    sims = mat @ q
    for c, s in zip(chunks, sims):
        hits.setdefault(c.resume_id, []).append(_Hit(float(s), c.text, c.start_char, c.end_char, c.section))
    return {k: sorted(v, key=lambda h: -h.sim)[:TOP_CHUNKS] for k, v in hits.items()}


# --------------------------------------------------------------------------- talent search
def talent_search(db: Session, recruiter: User, req: TalentSearchIn) -> TalentSearchOut:
    tax = taxonomy()
    query = req.query.strip()
    detected = tax.skills_in(query)
    if req.job_id is not None:
        job = db.get(Job, req.job_id)
        if job is None or job.recruiter_id != recruiter.id:
            raise NotFound("Job not found")
    access_u = accessible_users(db, recruiter, job_id=req.job_id)
    access = {cid: pool for cid, (_, pool) in access_u.items()}
    users = {cid: u for cid, (u, _) in access_u.items()}
    semantic_possible = embeddings.embeddings_available()
    resumes = _current_resumes(db, list(access), text=not semantic_possible, light=True)
    out = TalentSearchOut(query=query, detected_skills=detected, mode="keyword")
    if not resumes:
        return out

    qv: list[float] | None = None
    if semantic_possible:
        try:
            qv = embeddings.embed_text(query)
        except embeddings.EmbeddingUnavailable as exc:
            log.info("semantic search unavailable: %s", exc)
    hits: dict[UUID, list[_Hit]] = {}
    if qv is not None:
        out.mode = "semantic"
        hits = _chunk_hits(db, [r.id for r in resumes.values()], qv)
    else:
        out.warning = "Semantic search is unavailable right now (embeddings service not reachable); showing keyword matches."
        if semantic_possible:  # embeddings failed mid-request: the keyword path needs the resume text (one batched load)
            db.scalars(select(Resume).where(Resume.id.in_([r.id for r in resumes.values()])).options(undefer(Resume.text))).all()

    app_rows = db.execute(
        select(Application, Job).join(Job, Job.id == Application.job_id)
        .where(Job.recruiter_id == recruiter.id, Application.candidate_id.in_(list(resumes)))
    ).all()
    refs: dict[UUID, list[SearchApplicationRef]] = {}
    for a, j in app_rows:
        refs.setdefault(a.candidate_id, []).append(SearchApplicationRef(application_id=a.id, job_id=j.id, job_title=j.title, status=a.status))

    tokens = {t for t in re.findall(r"[a-z0-9+#.]{3,}", query.lower()) if t not in {"and", "the", "with", "for", "years", "experience", "developer", "engineer"}}
    results: list[TalentSearchResult] = []
    for cid, resume in resumes.items():
        user = users.get(cid)
        if user is None:
            continue
        have = {tax.canonical(s.name): s for s in resume.skills if not s.removed and s.presence == "present" and s.verification in ("verified", "fuzzy", "self_reported")}
        matched = [d for d in detected if d in have]
        coverage = (100.0 * len(matched) / len(detected)) if detected else None
        evidence: list[Evidence] = []
        semantic = None
        if out.mode == "semantic":
            hs = hits.get(resume.id, [])
            if hs:
                top = hs[:2]
                semantic = 100.0 * sum(_scale(h.sim) for h in top) / len(top)
                evidence = [Evidence(quote=h.text[:300], start=h.start, end=min(h.end, h.start + 300), similarity=round(h.sim, 3), section=h.section) for h in hs]
            score = (0.6 * (semantic or 0) + 0.4 * coverage) if coverage is not None else (semantic or 0)
        else:
            if coverage is not None:
                score = coverage
            else:
                low = (resume.text or "").lower()
                score = 100.0 * (sum(1 for t in tokens if t in low) / len(tokens)) if tokens else 0.0
        if score <= 0:
            continue
        for m in matched:
            s = have[m]
            if s.evidence and not any(e.start == s.start and e.end == s.end for e in evidence):
                evidence.append(Evidence(quote=s.evidence[:300], start=s.start, end=s.end))
        results.append(TalentSearchResult(
            candidate=_brief(user, user.profile), resume_id=resume.id, score=round(score, 1),
            semantic_score=round(semantic, 1) if semantic is not None else None,
            skill_coverage=round(coverage, 1) if coverage is not None else None,
            matched_skills=matched, evidence=evidence[:5], applications=refs.get(cid, []), in_talent_pool=access.get(cid, False),
        ))
    results.sort(key=lambda r: (-r.score, r.candidate.full_name.lower()))
    out.results = results[: req.limit]
    return out


# --------------------------------------------------------------------------- scoring a resume against a job
def _score_against(job: Job, resume: Resume, interests: tuple[str, ...] = (), *, with_projects: bool = False):
    jspec = builders.job_spec(job)
    cspec = builders.candidate_spec(resume, interests)
    sem = builders.semantics(job, resume, cspec, with_projects=with_projects)
    results = matcher.match_requirements(jspec, cspec, sem)
    sc = scorer.score(jspec, cspec, results, sem)
    return jspec, results, sc


def _interest_boost(interests: tuple[str, ...], job: Job) -> float:
    if not interests:
        return 0.0
    blob = (job.title + " " + " ".join(r.skill for r in job.requirements)).lower()
    hit = sum(1 for i in interests if i and i.lower() in blob)
    return min(5.0, 2.5 * hit)


def _split(results) -> tuple[list[str], list[str]]:  # noqa: ANN001
    matched = [r.skill for r in results if r.status == "evidenced" or (r.status == "partial" and r.credit >= 0.7)]
    missing = [r.skill for r in results if r.status in ("missing_evidence", "confirmed_absent")]
    return matched, missing


# --------------------------------------------------------------------------- recommendations
def best_resume(db: Session, candidate: User) -> Resume | None:
    """The candidate's current parsed, non-deleted resume with skills (joined: one query). Chunks load lazily (one more)."""
    return db.scalars(
        select(Resume).where(Resume.candidate_id == candidate.id, Resume.parse_status == "parsed", Resume.deleted_at.is_(None))
        .order_by(Resume.is_current.desc(), Resume.created_at.desc())
        .options(joinedload(Resume.skills))
        .limit(1)
    ).unique().first()


def recommend_from(resume: Resume, jobs: list[Job], applied: set, interests: tuple[str, ...], limit: int = 10) -> list[RecommendationOut]:
    """Score already-loaded jobs against a resume using STORED vectors only (no embedding API call per request)."""
    recs: list[RecommendationOut] = []
    for job in jobs:
        if job.id in applied:
            continue
        _, results, sc = _score_against(job, resume, interests, with_projects=True)
        total = min(100.0, sc.total + _interest_boost(interests, job))
        matched, missing = _split(results)
        req_n = sum(1 for r in results if r.kind == "required")
        if results:
            reason = f"Evidence for {len([r for r in results if r.kind == 'required' and r.status == 'evidenced'])} of {req_n} required skills" + (f" - strong in {', '.join(matched[:3])}." if matched else ".")
        else:
            reason = "Matched on your overall profile."
        recs.append(RecommendationOut(job=JobBrief(id=job.id, title=job.title, department=job.department, location=job.location, status=job.status),
                                      score=round(total, 1), matched_skills=matched, missing_skills=missing, reason=reason))
    recs.sort(key=lambda r: -r.score)
    return recs[:limit]


def open_jobs_query(exclude_applied_for: UUID | None = None):
    stmt = select(Job).where(Job.status == "open").options(*job_vector_options(join=True)).order_by(Job.created_at.desc())
    if exclude_applied_for is not None:
        stmt = stmt.where(Job.id.not_in(select(Application.job_id).where(Application.candidate_id == exclude_applied_for)))
    return stmt


def recommend_jobs(db: Session, candidate: User, limit: int = 10) -> list[RecommendationOut]:
    """Round trips: resume+skills (1), chunks (1), open jobs+requirements not yet applied to (1), interests (1)."""
    resume = best_resume(db, candidate)
    if resume is None:
        return []
    jobs = db.scalars(open_jobs_query(candidate.id)).unique().all()
    interests = tuple(db.scalar(select(CandidateProfile.interests).where(CandidateProfile.user_id == candidate.id)) or ())
    return recommend_from(resume, list(jobs), set(), interests, limit)


# --------------------------------------------------------------------------- talent pool
def talent_pool(db: Session, job: Job, recruiter: User) -> list[TalentPoolItem]:
    """Candidates the recruiter may see (opted-in, or applied to another of their jobs) who have not applied to this job.
    Round trips (constant, whatever the pool size): job+requirements+vectors, accessible users, already-applied, resumes,
    skills, chunks, previous applications, invitations."""
    if "embedding" in sa_inspect(job).unloaded:  # callers that need the scoring vectors load them up front (one query)
        job = db.scalars(select(Job).where(Job.id == job.id).options(*job_vector_options(join=True))).unique().one()
    access_u = accessible_users(db, recruiter)
    already = set(db.scalars(select(Application.candidate_id).where(Application.job_id == job.id, Application.status != "withdrawn")))
    ids = [c for c in access_u if c not in already]
    if not ids:
        return []
    users = {cid: access_u[cid][0] for cid in ids}
    resumes = _current_resumes(db, ids, chunks=True)
    prev: dict[UUID, str] = {}
    for cand_id, title in db.execute(
        select(Application.candidate_id, Job.title).join(Job, Job.id == Application.job_id)
        .where(Job.recruiter_id == recruiter.id, Application.candidate_id.in_(ids), Job.id != job.id).order_by(Application.created_at)
    ).all():
        prev[cand_id] = title
    invited = set(db.scalars(select(Notification.user_id).where(Notification.type == "job_invite", Notification.link == f"/candidate/jobs/{job.id}")))
    items: list[TalentPoolItem] = []
    for cid, resume in resumes.items():
        user = users.get(cid)
        if user is None:
            continue
        interests = tuple((user.profile.interests if user.profile else None) or ())
        _, results, sc = _score_against(job, resume, interests)
        total = min(100.0, sc.total + _interest_boost(interests, job))
        matched, missing = _split(results)
        items.append(TalentPoolItem(candidate=_brief(user, user.profile), resume_id=resume.id, score=round(total, 1), matched_skills=matched,
                                    missing_skills=missing, previously_applied_to=prev.get(cid), invited=cid in invited))
    items.sort(key=lambda i: -i.score)
    return items
