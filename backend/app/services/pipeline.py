"""Resume processing and application assessment pipelines (run in background tasks, one DB session per task)."""
from __future__ import annotations

import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.types import utcnow
from app.models import Application, Assessment, CandidateSkill, Job, Resume, ResumeChunk, User, job_vector_options
from app.schemas.common import Flag
from app.services import tasks, workflow
from app.services.ai import embeddings
from app.services.matching import builders, explain, matcher, scorer
from app.services.parsing import extractor, files, integrity
from app.services.parsing.redaction import redact_plain
from app.services.parsing.sections import ChunkDraft, chunk_text, detect_sections

log = logging.getLogger("app.pipeline")
OPEN_STATUSES = ("submitted", "parsed", "ai_assessed", "recruiter_review", "shortlisted", "interview")
# resume ids whose next extraction must bypass the ai_cache (candidate-triggered re-parse); consumed by _process_resume
REFRESH_EXTRACTION: set[UUID] = set()
GENERIC_PARSE_ERROR = "We could not process this resume because of an internal error. Please try again or upload a different file."


# --------------------------------------------------------------------------- shared helpers
def build_chunks(text: str, names: list[str]) -> tuple[list[ChunkDraft], bool]:
    """Chunk the ORIGINAL text (offsets stay valid); embed the REDACTED chunk text. Returns (chunks, embedded_ok)."""
    chunks = chunk_text(text, detect_sections(text))
    if not chunks or not embeddings.embeddings_available():
        return chunks, False
    texts = [_embed_text(c.text, names) for c in chunks]
    keep = [i for i, t in enumerate(texts) if len(t) >= 3]
    if not keep:
        return chunks, False
    try:
        vecs = embeddings.embed_texts([texts[i] for i in keep])
    except embeddings.EmbeddingUnavailable as exc:
        log.info("chunk embeddings unavailable: %s", exc)
        return chunks, False
    for i, v in zip(keep, vecs):
        chunks[i].embedding = v
    return chunks, True


def _embed_text(text: str, names: list[str]) -> str:
    """Redacted chunk text for embedding; protected-attribute markers are dropped so they cannot influence similarity."""
    t = redact_plain(text, names).replace("[REDACTED: protected attribute]", " ")
    return re.sub(r"\s+", " ", t).strip()


def mean_embedding(chunks: list[ChunkDraft]) -> list[float] | None:
    vecs = [c.embedding for c in chunks if c.embedding]
    if not vecs:
        return None
    dim = len(vecs[0])
    m = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    n = math.sqrt(sum(x * x for x in m)) or 1.0
    return [x / n for x in m]


# --------------------------------------------------------------------------- resume
def enqueue_resume(resume_id: UUID) -> None:
    with SessionLocal() as db:
        r = db.get(Resume, resume_id)
        if r is None:
            return
        r.parse_status = "pending"
        r.parse_error = None
        db.commit()
    tasks.submit(process_resume, resume_id)


def _fail_resume(resume_id: UUID, message: str) -> None:
    with SessionLocal() as db:
        r = db.get(Resume, resume_id)
        if r is None:
            return
        r.parse_status = "failed"
        r.parse_error = message
        apps = db.scalars(
            select(Application).where(Application.resume_id == resume_id, Application.processing_state.in_(("queued", "processing")))
        ).all()
        for a in apps:
            a.processing_state = "failed"
            a.processing_error = message
        db.commit()


def process_resume(resume_id: UUID) -> None:
    try:
        with SessionLocal() as db:
            _process_resume(db, resume_id)
    except files.ParseFailure as exc:
        log.info("resume %s rejected: %s", resume_id, exc.message)
        _fail_resume(resume_id, exc.message)
    except Exception:
        log.exception("resume %s processing failed", resume_id)
        _fail_resume(resume_id, GENERIC_PARSE_ERROR)


def _process_resume(db, resume_id: UUID) -> None:  # noqa: ANN001
    resume = db.get(Resume, resume_id)
    if resume is None:
        return
    resume.parse_status = "processing"
    resume.processing_started_at = utcnow()
    resume.parse_error = None
    db.commit()

    user = db.get(User, resume.candidate_id)
    names = [user.full_name] if user and user.full_name else []
    if not resume.file_bytes:
        raise files.ParseFailure("The stored file is missing. Please upload the resume again.", "no_file")

    ex = files.extract_text(resume.file_bytes)
    refresh = resume_id in REFRESH_EXTRACTION
    REFRESH_EXTRACTION.discard(resume_id)
    # The LLM extraction (slow) and chunking + embedding (network bound) are independent: run them side by side.
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_chunks = pool.submit(build_chunks, ex.text, names)
        f_result = pool.submit(extractor.extract, ex.text, names, refresh=True) if refresh else pool.submit(extractor.extract, ex.text, names)
        result = f_result.result()
        chunks, embedded = f_chunks.result()

    warnings = list(ex.warnings) + list(result.warnings)
    if not embedded:
        warnings.append("Semantic matching is unavailable for this resume (embeddings service not reachable); keyword and alias matching is used.")
    flags: list[Flag] = [*ex.flags, *integrity.scan(ex.text, hidden_chars=ex.hidden_chars, hidden_text=ex.hidden_text), *result.flags, *extractor.date_flags(result.parsed)]
    flags += integrity.not_a_resume_flag(result.parsed, result.skills, ex.text)

    resume.text = ex.text
    resume.page_count = ex.page_count
    resume.warnings = warnings
    resume.integrity_flags = [f.model_dump() for f in flags]
    resume.extraction_method = result.method
    resume.parsed = result.parsed.model_dump(mode="json")
    resume.doc_embedding = mean_embedding(chunks)

    db.execute(delete(ResumeChunk).where(ResumeChunk.resume_id == resume.id))
    for c in chunks:
        db.add(ResumeChunk(resume_id=resume.id, idx=c.idx, section=c.section, text=c.text, start_char=c.start, end_char=c.end, embedding=c.embedding))

    # skills: replace machine-derived rows; keep human decisions (added / removed / marked absent)
    existing = {s.name: s for s in db.scalars(select(CandidateSkill).where(CandidateSkill.resume_id == resume.id))}
    for name, s in list(existing.items()):
        if s.source in ("ai", "rules") and not s.removed and s.presence == "present":
            db.delete(s)
            del existing[name]
    db.flush()
    for d in result.skills:
        if d.name in existing:
            continue
        db.add(CandidateSkill(resume_id=resume.id, name=d.name, raw_name=d.raw_name, category=d.category, presence="present",
                              source=d.source, verification=d.verification, evidence=d.evidence, start=d.start, end=d.end))
    resume.parse_status = "parsed"
    db.commit()

    # profile enrichment (only fills blanks; never overwrites)
    try:
        prof = user.profile if user else None
        c = result.parsed.contact
        if prof is not None:
            if not prof.phone and c.phone:
                prof.phone = c.phone[:40]
            if not prof.links and c.links:
                prof.links = c.links[:10]
            if not prof.headline and result.parsed.experience and result.parsed.experience[0].title:
                prof.headline = result.parsed.experience[0].title[:160]
            db.commit()
    except Exception:
        db.rollback()

    try:
        from app.services import duplicates

        duplicates.detect_for_resume(db, resume)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("duplicate detection failed for resume %s", resume_id)

    app_ids = list(
        db.scalars(select(Application.id).where(Application.resume_id == resume.id, Application.status.in_(OPEN_STATUSES)))
    )
    for aid in app_ids:
        enqueue_assessment(aid)


# --------------------------------------------------------------------------- assessment
def enqueue_assessment(application_id: UUID) -> None:
    """Mark queued and run in the background. Callers must commit their own transaction first (eager mode runs inline)."""
    with SessionLocal() as db:
        a = db.get(Application, application_id)
        if a is None:
            return
        a.processing_state = "queued"
        a.processing_error = None
        db.commit()
    tasks.submit(assess_application, application_id)


def _fail_application(application_id: UUID, message: str) -> None:
    with SessionLocal() as db:
        a = db.get(Application, application_id)
        if a is not None:
            a.processing_state = "failed"
            a.processing_error = message
            db.commit()


def assess_application(application_id: UUID) -> None:
    try:
        with SessionLocal() as db:
            _assess(db, application_id)
    except Exception:
        log.exception("assessment failed for application %s", application_id)
        _fail_application(application_id, "The AI assessment failed. A recruiter can retry it with Reprocess or review the resume manually.")


def run_assessment(db, job: Job, resume: Resume, *, interests: tuple[str, ...] = (), use_llm: bool = True):  # noqa: ANN001
    """Pure-ish core used by assess/fairness/search: returns (results, score_result, explanation, semantics)."""
    jspec = builders.job_spec(job)
    cspec = builders.candidate_spec(resume, interests)
    builders.ensure_job_embeddings(db, job)
    sem = builders.semantics(job, resume, cspec)
    results = matcher.match_requirements(jspec, cspec, sem)
    sc = scorer.score(jspec, cspec, results, sem)
    exp = explain.explain(jspec, cspec, results, sc.components, sc.total, sem, resume.integrity_flags or [], use_llm=use_llm)
    return results, sc, exp, sem


def _assess(db, application_id: UUID) -> None:  # noqa: ANN001
    app = db.get(Application, application_id)
    if app is None:
        return
    if app.status == "withdrawn":
        app.processing_state = "done"
        db.commit()
        return
    resume = db.scalars(
        select(Resume).where(Resume.id == app.resume_id).options(selectinload(Resume.skills), selectinload(Resume.chunks))
    ).first() if app.resume_id else None
    if resume is None:
        app.processing_state = "failed"
        app.processing_error = "No resume is attached to this application."
        db.commit()
        return
    if resume.parse_status == "failed":
        app.processing_state = "failed"
        app.processing_error = resume.parse_error or "The resume could not be read."
        db.commit()
        return
    if resume.parse_status != "parsed":
        app.processing_state = "queued"  # process_resume re-enqueues this application when it finishes
        db.commit()
        return

    app.processing_state = "processing"
    app.processing_started_at = utcnow()
    app.processing_error = None
    workflow.system_transition(db, app, "parsed", note="Resume parsed")
    db.commit()

    job = db.scalars(select(Job).where(Job.id == app.job_id).options(*job_vector_options())).first()
    if job is None:
        raise RuntimeError("job not found")
    prof_interests: tuple[str, ...] = ()
    cand = db.get(User, app.candidate_id)
    if cand is not None and cand.profile is not None:
        prof_interests = tuple(cand.profile.interests or ())

    results, sc, exp, sem = run_assessment(db, job, resume, interests=prof_interests)

    a = db.scalars(select(Assessment).where(Assessment.application_id == app.id)).first()
    if a is None:
        a = Assessment(application_id=app.id)
        db.add(a)
    a.job_version = job.version or 1
    a.total_score = sc.total
    a.components = {k: v.model_dump(mode="json") for k, v in sc.components.items()}
    a.requirements = [r.model_dump(mode="json") for r in results]
    a.strengths = exp.strengths
    a.gaps = exp.gaps
    a.learning_suggestions = [l.model_dump() for l in exp.learning]
    a.summary = exp.summary
    a.summary_method = exp.summary_method
    a.flags = [f.model_dump() for f in exp.flags]
    a.semantic_available = sem.available
    a.model_info = {
        "extraction": resume.extraction_method,
        "llm": settings.deepseek_model if resume.extraction_method == "llm" or exp.summary_method == "llm" else None,
        "embedding": settings.bedrock_embed_model if sem.available else None,
        "scorer": "evidence-v1",
    }
    app.assessed_at = utcnow()
    workflow.system_transition(db, app, "ai_assessed", note=f"AI score {sc.total:.1f}")
    app.processing_state = "done"
    db.commit()
