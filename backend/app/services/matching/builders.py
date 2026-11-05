"""Glue between ORM rows and the pure matching specs; embedding helpers (all failures degrade to keyword matching)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Job, Resume
from app.schemas.resume import ParsedResume
from app.services.ai import embeddings
from app.services.matching import matcher
from app.services.matching.specs import (
    CandidateSpec, ChunkSpec, EduSpec, ExpSpec, JobSpec, ProjSpec, ReqSpec, Semantics, SkillSpec,
)
from app.services.parsing.redaction import redact_plain

log = logging.getLogger("app.matching")
JOB_TEXT_MAX = 3000


def job_spec(job: Job) -> JobSpec:
    from app.models.job import DEFAULT_WEIGHTS

    return JobSpec(
        title=job.title or "",
        description=job.description or "",
        requirements=tuple(ReqSpec(r.skill, r.kind, r.importance, r.id) for r in job.requirements),
        min_experience_years=float(job.min_experience_years or 0),
        education_level=job.education_level or "none",
        qualifications=tuple(job.qualifications or ()),
        weights={**DEFAULT_WEIGHTS, **(job.weights or {})},
    )


def job_text(job: Job) -> str:
    skills = ", ".join(r.skill for r in job.requirements)
    return f"{job.title}\n{job.description or ''}\nSkills: {skills}"[:JOB_TEXT_MAX]


def req_text(skill: str) -> str:
    """Text embedded for a job requirement. A bare tool name ("CI/CD") embeds far from plain-worded experience ("automated
    build and release pipelines"), so known skills are expanded with their description / aliases (similarity 0.1 -> 0.55)."""
    from app.services.parsing.normalizer import taxonomy

    return f"Experience with {taxonomy().describe(skill)}"


def ensure_job_embeddings(db: Session, job: Job) -> bool:
    """Embed the job and each requirement when missing. Returns False when embeddings are unavailable."""
    if not embeddings.embeddings_available():
        return False
    need_job = job.embedding is None
    need = [r for r in job.requirements if r.embedding is None]
    if not need_job and not need:
        return True
    texts = ([job_text(job)] if need_job else []) + [req_text(r.skill) for r in need]
    try:
        vecs = embeddings.embed_texts(texts)
    except embeddings.EmbeddingUnavailable as exc:
        log.info("job embeddings unavailable: %s", exc)
        return False
    i = 0
    if need_job:
        job.embedding = vecs[0]
        i = 1
    for r in need:
        r.embedding = vecs[i]
        i += 1
    db.flush()
    return True


def candidate_spec(resume: Resume, interests: tuple[str, ...] = ()) -> CandidateSpec:
    try:
        parsed = ParsedResume.model_validate(resume.parsed or {})
    except Exception:
        parsed = ParsedResume()
    skills = tuple(
        SkillSpec(s.name, s.raw_name, s.presence, s.verification, s.evidence, s.start, s.end, s.source)
        for s in resume.skills
        if not s.removed
    )
    chunks = tuple(ChunkSpec(c.text, c.start_char, c.end_char, c.section) for c in resume.chunks)
    exp = tuple(
        ExpSpec(e.title, tuple(e.skills), e.start_date, e.end_date, e.current, e.description, e.verification)
        for e in parsed.experience
    )
    proj = tuple(
        ProjSpec(p.name, " ".join(x for x in [p.name, p.description, " ".join(p.tech)] if x), tuple(p.tech), p.verification, p.evidence, p.start, p.end)
        for p in parsed.projects
    )
    edu = tuple(EduSpec(e.level, e.field, e.degree, e.verification) for e in parsed.education)
    return CandidateSpec(skills, chunks, exp, proj, edu, tuple(parsed.certifications), parsed.total_years_claimed, interests)


def spec_from_extraction(parsed, skills, chunks, interests: tuple[str, ...] = ()) -> CandidateSpec:  # noqa: ANN001
    """CandidateSpec straight from an Extraction + chunk drafts (no DB rows): used by the fairness counterfactuals."""
    return CandidateSpec(
        skills=tuple(SkillSpec(s.name, s.raw_name, "present", s.verification, s.evidence, s.start, s.end, s.source) for s in skills),
        chunks=tuple(ChunkSpec(c.text, c.start, c.end, c.section) for c in chunks),
        experience=tuple(ExpSpec(e.title, tuple(e.skills), e.start_date, e.end_date, e.current, e.description, e.verification) for e in parsed.experience),
        projects=tuple(
            ProjSpec(p.name, " ".join(x for x in [p.name, p.description, " ".join(p.tech)] if x), tuple(p.tech), p.verification, p.evidence, p.start, p.end)
            for p in parsed.projects
        ),
        education=tuple(EduSpec(e.level, e.field, e.degree, e.verification) for e in parsed.education),
        certifications=tuple(parsed.certifications),
        total_years_claimed=parsed.total_years_claimed,
        interests=interests,
    )


def semantics_from_vectors(job: Job, chunk_vecs: list, cand: CandidateSpec, *, with_projects: bool = True) -> Semantics:
    if not chunk_vecs or all(v is None for v in chunk_vecs):
        return Semantics(False)
    req_vecs = [r.embedding for r in job.requirements]
    proj_vecs = None
    if with_projects and cand.projects and job.embedding is not None and embeddings.embeddings_available():
        try:
            proj_vecs = embeddings.embed_texts([redact_plain(p.text[:2000]) for p in cand.projects])
        except embeddings.EmbeddingUnavailable:
            proj_vecs = None
    return matcher.compute_semantics(req_vecs, chunk_vecs, job.embedding, proj_vecs)


def semantics(job: Job, resume: Resume, cand: CandidateSpec, *, with_projects: bool = True) -> Semantics:
    """Cosine similarities from stored vectors; project texts are embedded on the fly (cached)."""
    return semantics_from_vectors(job, [c.embedding for c in resume.chunks], cand, with_projects=with_projects)
