"""Application serialisation (recruiter + candidate views) and shared helpers."""
from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, Assessment, AuditEvent, Interview, Resume, User
from app.schemas.application import (
    ApplicationDetailOut,
    ApplicationRowOut,
    AssessmentOut,
    CandidateApplicationOut,
    CandidateInterviewOut,
    CompareCandidate,
    ComponentScore,
    ComponentSummary,
    TimelineItem,
)
from app.schemas.application import RequirementResult
from app.schemas.common import Flag, JobBrief
from app.schemas.application import LearningSuggestion
from app.services import interviews as iv_service
from app.services import workflow
from app.services.access import candidate_brief, job_brief
from app.services.resumes import to_resume_detail

OPEN_STATES = ("submitted", "parsed", "ai_assessed", "recruiter_review", "shortlisted", "interview")


def list_load_options():
    return (
        selectinload(Application.candidate).selectinload(User.profile),
        selectinload(Application.assessment),
        selectinload(Application.job),
    )


def to_assessment_out(assessment: Assessment, job_version: int | None) -> AssessmentOut:
    comps: dict[str, ComponentScore] = {}
    for name, c in (assessment.components or {}).items():
        try:
            comps[name] = ComponentScore(**c)
        except Exception:  # noqa: BLE001 - tolerate older/partial component payloads
            comps[name] = ComponentScore(score=float(c.get("score", 0)), weight=float(c.get("weight", 0)), points=float(c.get("points", 0)))
    return AssessmentOut(
        id=assessment.id,
        application_id=assessment.application_id,
        job_version=assessment.job_version,
        total_score=assessment.total_score,
        override_score=assessment.override_score,
        override_reason=assessment.override_reason,
        effective_score=assessment.effective_score,
        components=comps,
        requirements=[RequirementResult(**r) for r in (assessment.requirements or [])],
        strengths=list(assessment.strengths or []),
        gaps=list(assessment.gaps or []),
        learning_suggestions=[LearningSuggestion(**s) for s in (assessment.learning_suggestions or [])],
        summary=assessment.summary,
        summary_method=assessment.summary_method,
        flags=[Flag(**f) for f in (assessment.flags or [])],
        semantic_available=assessment.semantic_available,
        stale=job_version is not None and assessment.job_version != job_version,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
    )


def component_summary(assessment: Assessment | None) -> ComponentSummary:
    if assessment is None:
        return ComponentSummary()
    comps = assessment.components or {}

    def pick(name: str) -> float | None:
        c = comps.get(name)
        if not c or c.get("applicable") is False:
            return None
        return c.get("score")

    return ComponentSummary(
        skills=pick("skills"), experience=pick("experience"), projects=pick("projects"), qualifications=pick("qualifications")
    )


def matched_missing(assessment: Assessment | None) -> tuple[list[str], list[str]]:
    matched, missing = [], []
    for r in (assessment.requirements if assessment else None) or []:
        if r.get("status") in ("evidenced", "partial"):
            matched.append(r["skill"])
        elif r.get("kind") == "required":
            missing.append(r["skill"])
    return matched, missing


def to_row(a: Application) -> ApplicationRowOut:
    asm = a.assessment
    matched, missing = matched_missing(asm)
    return ApplicationRowOut(
        id=a.id,
        candidate=candidate_brief(a.candidate),
        status=a.status,
        processing_state=a.processing_state,
        processing_error=a.processing_error,
        effective_score=asm.effective_score if asm else None,
        total_score=asm.total_score if asm else None,
        override_score=asm.override_score if asm else None,
        components=component_summary(asm),
        matched_skills=matched,
        missing_skills=missing,
        flags=[Flag(**f) for f in (asm.flags if asm else None) or []],
        is_duplicate=a.is_duplicate,
        resume_id=a.resume_id,
        applied_at=a.created_at,
        updated_at=a.updated_at,
    )


def to_detail(db: Session, a: Application) -> ApplicationDetailOut:
    resume = None
    if a.resume_id:
        r = db.get(Resume, a.resume_id)
        if r is not None:
            resume = to_resume_detail(r)
    ivs = iv_service.load_interviews(db, Interview.application_id == a.id)
    asm = a.assessment
    return ApplicationDetailOut(
        id=a.id,
        job=job_brief(a.job),
        candidate=candidate_brief(a.candidate),
        resume=resume,
        status=a.status,
        processing_state=a.processing_state,
        processing_error=a.processing_error,
        cover_note=a.cover_note,
        is_duplicate=a.is_duplicate,
        assessment=to_assessment_out(asm, a.job.version) if asm else None,
        allowed_transitions=workflow.allowed_transitions(a, "recruiter"),
        notes_count=len(a.notes),
        interviews=[iv_service.to_interview_out(i, a) for i in ivs],
        applied_at=a.created_at,
        updated_at=a.updated_at,
    )


def missing_information(a: Application, resume: Resume | None) -> list[str]:
    out: list[str] = []
    parsed = (resume.parsed if resume else None) or {}
    if resume is None or resume.parse_status != "parsed":
        return ["Resume has not been parsed"]
    if not parsed.get("experience"):
        out.append("No work experience listed")
    if not parsed.get("education"):
        out.append("No education listed")
    if not parsed.get("projects"):
        out.append("No projects listed")
    unverified = [s.name for s in resume.skills if not s.removed and s.verification == "unverified"]
    if unverified:
        out.append(f"{len(unverified)} skill(s) without supporting evidence in the resume")
    return out


def to_compare(a: Application, resume: Resume | None) -> CompareCandidate:
    asm = a.assessment
    return CompareCandidate(
        application_id=a.id,
        candidate=candidate_brief(a.candidate),
        status=a.status,
        effective_score=asm.effective_score if asm else None,
        components=component_summary(asm),
        requirements=[RequirementResult(**r) for r in (asm.requirements if asm else None) or []],
        strengths=list(asm.strengths or []) if asm else [],
        gaps=list(asm.gaps or []) if asm else [],
        flags=[Flag(**f) for f in (asm.flags if asm else None) or []],
        missing_information=missing_information(a, resume),
    )


# ----------------------------------------------------------------------------- candidate view
def _timelines(db: Session, apps: Iterable[Application]) -> dict[uuid.UUID, list[TimelineItem]]:
    apps = list(apps)
    ids = [a.id for a in apps]
    events = (
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.application_id.in_(ids), AuditEvent.action == "status_change")
            .order_by(AuditEvent.created_at)
        ).all()
        if ids
        else []
    )
    by_app: dict[uuid.UUID, list[AuditEvent]] = {}
    for e in events:
        by_app.setdefault(e.application_id, []).append(e)
    out: dict[uuid.UUID, list[TimelineItem]] = {}
    for a in apps:
        items = [TimelineItem(label=workflow.status_label("submitted", candidate_view=True), at=a.created_at)]
        for e in by_app.get(a.id, []):
            label = workflow.status_label(e.to_value or "", candidate_view=True)
            if label != items[-1].label:
                items.append(TimelineItem(label=label, at=e.created_at))
        out[a.id] = items
    return out


def to_candidate_applications(db: Session, apps: list[Application]) -> list[CandidateApplicationOut]:
    if not apps:
        return []
    ids = [a.id for a in apps]
    timelines = _timelines(db, apps)
    ivs = db.scalars(
        select(Interview).where(Interview.application_id.in_(ids), Interview.status == "scheduled").order_by(Interview.start_at)
    ).all()
    iv_by_app: dict[uuid.UUID, list[Interview]] = {}
    for i in ivs:
        iv_by_app.setdefault(i.application_id, []).append(i)
    resume_ids = [a.resume_id for a in apps if a.resume_id]
    names = dict(db.execute(select(Resume.id, Resume.filename).where(Resume.id.in_(resume_ids))).all()) if resume_ids else {}
    result = []
    for a in apps:
        result.append(
            CandidateApplicationOut(
                id=a.id,
                job=JobBrief(id=a.job.id, title=a.job.title, department=a.job.department, location=a.job.location, status=a.job.status),
                status=a.status,
                status_label=workflow.status_label(a.status, candidate_view=True),
                processing_state=a.processing_state,
                processing_error=None,  # internal details are not for candidates
                resume_id=a.resume_id,
                resume_filename=names.get(a.resume_id),
                cover_note=a.cover_note,
                timeline=timelines.get(a.id, []),
                interviews=[
                    CandidateInterviewOut(
                        id=i.id, interview_type=i.interview_type, start_at=i.start_at, end_at=i.end_at,
                        location=i.location, interviewer_name=i.interviewer_name, status=i.status,
                    )
                    for i in iv_by_app.get(a.id, [])
                ],
                can_withdraw=a.status not in workflow.TERMINAL_FOR_CANDIDATE,
                applied_at=a.created_at,
                updated_at=a.updated_at,
            )
        )
    return result
