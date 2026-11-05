"""AI interview questions tailored to the candidate's evidence and the job's gaps. Needs the LLM (503 otherwise)."""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, field_validator
from rapidfuzz import fuzz
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload, undefer

from app.core.errors import ServiceUnavailable
from app.models import Application, Assessment, InterviewQuestion, Job, Resume
from app.schemas.interview import QuestionGenerateIn
from app.schemas.resume import ParsedResume
from app.services.ai import llm, prompts
from app.services.parsing.verifier import Index

log = logging.getLogger("app.questions")
DIFFS = ("beginner", "intermediate", "advanced")


class _Q(BaseModel):
    difficulty: str = "intermediate"
    category: str = "skill"
    question: str
    answer_guidelines: list[str] = []
    related_skill: str | None = None
    source_quote: str | None = None

    @field_validator("answer_guidelines", mode="before")
    @classmethod
    def _g(cls, v):
        if isinstance(v, str):
            return [v]
        return [str(x) for x in (v or [])]


class _QOut(BaseModel):
    questions: list[_Q] = []


def _load(db: Session, application: Application):
    resume = db.scalars(select(Resume).where(Resume.id == application.resume_id).options(undefer(Resume.text))).first() if application.resume_id else None
    job = db.scalars(select(Job).where(Job.id == application.job_id).options(selectinload(Job.requirements))).first()
    assessment = db.scalars(select(Assessment).where(Assessment.application_id == application.id)).first()
    return resume, job, assessment


def _context(job: Job, resume: Resume | None, assessment: Assessment | None, include_projects: bool, existing: list[str]) -> dict:
    parsed = ParsedResume.model_validate((resume.parsed if resume else None) or {})
    reqs = [{"skill": r.skill, "kind": r.kind, "importance": r.importance} for r in job.requirements]
    results = (assessment.requirements if assessment else []) or []
    ctx = {
        "job": {"title": job.title, "description": (job.description or "")[:1500], "requirements": reqs, "min_experience_years": job.min_experience_years},
        "candidate_evidenced_skills": [
            {"skill": r["skill"], "evidence": ((r.get("evidence") or [{}])[0].get("quote") or "")[:160]}
            for r in results if r.get("status") == "evidenced"
        ][:15],
        "gaps": [r["skill"] for r in results if r.get("status") in ("missing_evidence", "confirmed_absent", "partial")][:10],
        "experience": [{"title": e.title, "skills": e.skills[:8]} for e in parsed.experience[:6]],
        "existing_questions": existing[:30],
    }
    if include_projects:
        ctx["projects"] = [
            {"name": p.name, "description": (p.description or "")[:400], "tech": p.tech[:8], "evidence_quote": (p.evidence or "")[:300]}
            for p in parsed.projects[:4]
        ]
    return ctx


def _clean(qs: list[_Q], existing: list[str], idx: Index | None) -> list[dict]:
    out: list[dict] = []
    seen = list(existing)
    for q in qs:
        text = (q.question or "").strip()
        if len(text) < 8 or any(fuzz.token_set_ratio(text.lower(), s.lower()) >= 85 for s in seen):
            continue
        seen.append(text)
        diff = q.difficulty.lower().strip() if q.difficulty else "intermediate"
        diff = diff if diff in DIFFS else "intermediate"
        cat = (q.category or "skill").lower().strip()
        cat = cat if cat in {"skill", "project", "gap", "behavioral"} else "skill"
        guides = [g.strip()[:300] for g in q.answer_guidelines if g and g.strip()][:5]
        quote, verified = None, None
        if q.source_quote and q.source_quote.strip():
            v = idx.verify(q.source_quote) if idx else None
            if v and v.verification != "unverified" and v.quote:
                quote, verified = v.quote[:400], True
            else:
                quote, verified = q.source_quote.strip()[:400], False
        out.append(dict(difficulty=diff, category=cat, question=text[:1500], answer_guidelines=guides,
                        related_skill=(q.related_skill or None) and q.related_skill.strip()[:80], source_quote=quote, source_verified=verified))
    return out


def _call(system: str, user: str) -> _QOut:
    if not llm.llm_available():
        raise ServiceUnavailable("Question generation needs the AI model, which is not available right now. You can add questions manually.", code="llm_unavailable")
    try:
        return llm.json_call(system, user, _QOut, max_tokens=3500)
    except llm.LLMUnavailable as exc:
        raise ServiceUnavailable(f"The AI model is unavailable: {exc}", code="llm_unavailable") from exc
    except llm.LLMError as exc:
        raise ServiceUnavailable("The AI model did not return usable questions. Please try again.", code="llm_unavailable") from exc


def generate_questions(db: Session, application: Application, spec: QuestionGenerateIn) -> list[InterviewQuestion]:
    """Generate and store questions (flushes; caller commits). Raises ServiceUnavailable when no LLM."""
    if not llm.llm_available():
        raise ServiceUnavailable("Question generation needs the AI model, which is not available right now. You can add questions manually.", code="llm_unavailable")
    resume, job, assessment = _load(db, application)
    if job is None:
        raise ServiceUnavailable("The job for this application no longer exists.", code="not_available")
    existing_rows = list(db.scalars(select(InterviewQuestion).where(InterviewQuestion.application_id == application.id).order_by(InterviewQuestion.position)))
    existing_texts = [q.question for q in existing_rows] if spec.append else []
    ctx = _context(job, resume, assessment, spec.include_projects, existing_texts)
    counts = {"beginner": spec.beginner, "intermediate": spec.intermediate, "advanced": spec.advanced}
    if not any(counts.values()):
        return existing_rows if spec.append else []
    user = ("<context>\n" + json.dumps(ctx, default=str) + "\n</context>\nRequested counts per difficulty: " + json.dumps(counts) +
            (". Include at least one project-based question." if spec.include_projects and ctx.get("projects") else ".") + "\nReturn the json object now.")
    out = _call(prompts.QUESTIONS_SYSTEM, user)
    idx = Index(resume.text) if resume and resume.text else None
    cleaned = _clean(out.questions, existing_texts, idx)
    chosen: list[dict] = []
    taken = {d: 0 for d in DIFFS}
    for q in cleaned:
        if taken[q["difficulty"]] < counts[q["difficulty"]]:
            chosen.append(q)
            taken[q["difficulty"]] += 1
    if not chosen:
        raise ServiceUnavailable("The AI model did not return usable questions. Please try again.", code="llm_unavailable")
    chosen.sort(key=lambda q: (DIFFS.index(q["difficulty"]), q["category"] != "skill"))
    if spec.append:
        pos = (db.scalar(select(func.max(InterviewQuestion.position)).where(InterviewQuestion.application_id == application.id)) or -1) + 1
    else:
        db.execute(delete(InterviewQuestion).where(InterviewQuestion.application_id == application.id))
        pos = 0
        existing_rows = []
    created = []
    for q in chosen:
        row = InterviewQuestion(application_id=application.id, position=pos, is_edited=False, **q)
        pos += 1
        db.add(row)
        created.append(row)
    db.flush()
    return existing_rows + created if spec.append else created


def regenerate_question(db: Session, question: InterviewQuestion) -> InterviewQuestion:
    """Replace one question with a fresh one of the same difficulty and category (flushes; caller commits)."""
    application = db.get(Application, question.application_id)
    resume, job, assessment = _load(db, application)
    others = [q.question for q in db.scalars(select(InterviewQuestion).where(InterviewQuestion.application_id == question.application_id))]
    ctx = _context(job, resume, assessment, question.category == "project", others)
    ctx["target"] = {"difficulty": question.difficulty, "category": question.category, "related_skill": question.related_skill}
    user = "<context>\n" + json.dumps(ctx, default=str) + "\n</context>\nReturn the json object now with exactly one question."
    out = _call(prompts.QUESTION_ONE_SYSTEM, user)
    idx = Index(resume.text) if resume and resume.text else None
    cleaned = _clean(out.questions, others, idx)
    if not cleaned:
        raise ServiceUnavailable("The AI model could not produce a new, different question. Please try again.", code="llm_unavailable")
    q = cleaned[0]
    question.question = q["question"]
    question.answer_guidelines = q["answer_guidelines"]
    question.related_skill = q["related_skill"] or question.related_skill
    question.source_quote = q["source_quote"]
    question.source_verified = q["source_verified"]
    question.is_edited = False
    db.flush()
    return question
