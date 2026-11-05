from __future__ import annotations

import uuid

from fastapi import APIRouter, Response
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.core.deps import DB, Candidate, Recruiter
from app.core.errors import Conflict, NotFound, Unprocessable
from app.models import Application, Assessment, AuditEvent, Job, RecruiterNote, Resume, User
from app.schemas.application import (
    ApplicationDetailOut,
    ApplyIn,
    AssessmentOut,
    CandidateApplicationOut,
    FairnessOut,
    HistoryEventOut,
    NoteIn,
    NoteOut,
    OverrideIn,
    TransitionIn,
)
from app.schemas.common import Msg
from app.services import applications as app_service
from app.services import fairness, interviews as iv_service, pipeline, workflow
from app.services.access import get_owned_application, get_owned_note, safe_call
from app.services.audit import log_event
from app.services.notifications import notify

router = APIRouter(prefix="/applications", tags=["applications"])
notes_router = APIRouter(prefix="/notes", tags=["applications"])


def _own_candidate_app(db, user: User, application_id: uuid.UUID) -> Application:
    a = db.scalar(
        select(Application)
        .options(selectinload(Application.job), selectinload(Application.candidate))
        .where(Application.id == application_id)
    )
    if a is None or a.candidate_id != user.id:
        raise NotFound("Application not found")
    return a


def _candidate_out(db, a: Application) -> CandidateApplicationOut:
    return app_service.to_candidate_applications(db, [a])[0]


# ----------------------------------------------------------------------------- candidate
@router.post("", response_model=CandidateApplicationOut, status_code=201)
def apply(body: ApplyIn, db: DB, user: Candidate):
    job = db.get(Job, body.job_id)
    if job is None:
        raise NotFound("Job not found")
    if job.status != "open":
        raise Conflict("This job is no longer accepting applications", code="job_closed")
    if body.resume_id is not None:  # the candidate picked a specific resume in the apply dialog
        resume = db.scalar(select(Resume).where(Resume.id == body.resume_id, Resume.candidate_id == user.id, Resume.deleted_at.is_(None)))
        if resume is None or resume.parse_status != "parsed":
            raise Unprocessable("That resume can't be used yet. Pick another resume, or wait until it has finished being read.", code="resume_invalid")
    else:
        resume = db.scalar(
            select(Resume)
            .where(Resume.candidate_id == user.id, Resume.parse_status != "failed", Resume.deleted_at.is_(None))
            .order_by(Resume.is_current.desc(), Resume.created_at.desc())
            .limit(1)
        )
    if resume is None:
        failed = db.scalar(select(Resume).where(Resume.candidate_id == user.id, Resume.deleted_at.is_(None)).order_by(Resume.created_at.desc()).limit(1))
        if failed is not None:  # the candidate did upload, but nothing usable: say why instead of "upload a resume"
            reason = failed.parse_error or "it could not be read"
            raise Unprocessable(f"Your resume could not be processed ({reason.rstrip('.')}). Please upload a readable PDF or DOCX before applying.", code="resume_unreadable")
        raise Unprocessable("Upload a resume before applying", code="no_resume")
    existing = db.scalar(select(Application).where(Application.job_id == job.id, Application.candidate_id == user.id))
    if existing is not None and existing.status != "withdrawn":
        raise Conflict("You have already applied to this job", code="already_applied")
    note = (body.cover_note or "").strip() or None
    if existing is not None:  # re-apply after withdrawing: reuse the row (unique per job+candidate)
        existing.status, existing.processing_state, existing.processing_error = "submitted", "queued", None
        existing.resume_id, existing.cover_note, existing.decided_at, existing.assessed_at = resume.id, note, None, None
        if existing.assessment is not None:
            db.delete(existing.assessment)
        application = existing
        action = "reapplied"
    else:
        application = Application(job_id=job.id, candidate_id=user.id, resume_id=resume.id, cover_note=note,
                                  status="submitted", processing_state="queued")
        db.add(application)
        action = "application_submitted"
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("You have already applied to this job", code="already_applied")
    log_event(db, entity_type="application", entity_id=application.id, application_id=application.id, action=action,
              actor=user, to_value="submitted")
    notify(db, user_id=job.recruiter_id, type="new_application", title=f"New application: {job.title}",
           body=f"{user.full_name} applied.", link=f"/recruiter/jobs/{job.id}")
    db.commit()
    aid = application.id
    if resume.parse_status == "parsed":
        safe_call(pipeline.enqueue_assessment, aid)  # otherwise the resume pipeline queues it once parsing finishes
    db.expire_all()
    return _candidate_out(db, _own_candidate_app(db, user, aid))


@router.get("/me", response_model=list[CandidateApplicationOut])
def my_applications(db: DB, user: Candidate):
    apps = db.scalars(
        select(Application)
        .where(Application.candidate_id == user.id)
        .options(joinedload(Application.job), joinedload(Application.resume).load_only(Resume.id, Resume.filename))
        .order_by(desc(Application.created_at))
    ).unique().all()
    names = {a.resume_id: a.resume.filename for a in apps if a.resume is not None}
    return app_service.to_candidate_applications(db, list(apps), names)


@router.post("/{application_id}/withdraw", response_model=CandidateApplicationOut)
def withdraw(application_id: uuid.UUID, db: DB, user: Candidate):
    a = _own_candidate_app(db, user, application_id)
    workflow.transition(db, a, "withdrawn", user)
    iv_service.cancel_for_withdrawn(db, a)
    notify(db, user_id=a.job.recruiter_id, type="application_withdrawn", title=f"Application withdrawn: {a.job.title}",
           body=f"{user.full_name} withdrew their application.", link=f"/recruiter/jobs/{a.job_id}")
    db.commit()
    return _candidate_out(db, a)


# ----------------------------------------------------------------------------- recruiter
def _detail(db, user, application_id: uuid.UUID) -> ApplicationDetailOut:
    db.expire_all()
    a = get_owned_application(db, user, application_id)
    a = db.scalar(
        select(Application)
        .where(Application.id == a.id)
        .options(
            selectinload(Application.job), selectinload(Application.candidate).selectinload(User.profile),
            selectinload(Application.assessment), selectinload(Application.notes),
        )
    )
    return app_service.to_detail(db, a)


@router.get("/{application_id}", response_model=ApplicationDetailOut)
def get_application(application_id: uuid.UUID, db: DB, user: Recruiter):
    return _detail(db, user, application_id)


@router.post("/{application_id}/transition", response_model=ApplicationDetailOut)
def transition(application_id: uuid.UUID, body: TransitionIn, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    workflow.transition(db, a, body.to_status, user, body.reason)
    db.commit()
    return _detail(db, user, application_id)


@router.post("/{application_id}/reprocess", response_model=ApplicationDetailOut, status_code=202)
def reprocess(application_id: uuid.UUID, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    if a.status == "withdrawn":
        raise Conflict("This application was withdrawn", code="withdrawn")
    resume = db.get(Resume, a.resume_id) if a.resume_id else None
    if resume is None or resume.parse_status != "parsed":
        raise Unprocessable("The resume has not been parsed yet. Reprocess the resume first.", code="resume_not_parsed")
    if a.processing_state == "processing":
        raise Conflict("This application is already being processed", code="already_processing")
    a.processing_state, a.processing_error = "queued", None
    db.commit()
    safe_call(pipeline.enqueue_assessment, a.id)
    return _detail(db, user, application_id)


@router.post("/{application_id}/override", response_model=AssessmentOut)
def override(application_id: uuid.UUID, body: OverrideIn, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    asm = db.scalar(select(Assessment).where(Assessment.application_id == a.id))
    if asm is None:
        raise Conflict("There is no AI assessment to override yet", code="no_assessment")
    old = asm.effective_score
    asm.override_score, asm.override_reason, asm.overridden_by = round(body.score, 1), body.reason.strip(), user.id
    log_event(db, entity_type="application", entity_id=a.id, application_id=a.id, action="override", actor=user,
              from_value=f"{old:.1f}", to_value=f"{asm.override_score:.1f}", note=asm.override_reason)
    db.commit()
    return app_service.to_assessment_out(asm, a.job.version)


@router.get("/{application_id}/notes", response_model=list[NoteOut])
def list_notes(application_id: uuid.UUID, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    rows = db.scalars(
        select(RecruiterNote).where(RecruiterNote.application_id == a.id).options(selectinload(RecruiterNote.author))
        .order_by(RecruiterNote.created_at.desc())
    ).all()
    return [NoteOut(id=n.id, application_id=n.application_id, author_id=n.author_id, author_name=n.author.full_name,
                    body=n.body, created_at=n.created_at) for n in rows]


@router.post("/{application_id}/notes", response_model=NoteOut, status_code=201)
def add_note(application_id: uuid.UUID, body: NoteIn, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    text = body.body.strip()
    if not text:
        raise Unprocessable("A note cannot be empty", code="validation_error")
    n = RecruiterNote(application_id=a.id, author_id=user.id, body=text)
    db.add(n)
    db.flush()
    log_event(db, entity_type="application", entity_id=a.id, application_id=a.id, action="note_added", actor=user, note=text[:200])
    db.commit()
    return NoteOut(id=n.id, application_id=a.id, author_id=user.id, author_name=user.full_name, body=n.body, created_at=n.created_at)


@notes_router.delete("/{note_id}", response_model=Msg)
def delete_note(note_id: uuid.UUID, db: DB, user: Recruiter):
    n = get_owned_note(db, user, note_id)
    log_event(db, entity_type="application", entity_id=n.application_id, application_id=n.application_id, action="note_deleted", actor=user)
    db.delete(n)
    db.commit()
    return Msg(detail="Note deleted")


@router.get("/{application_id}/history", response_model=list[HistoryEventOut])
def history(application_id: uuid.UUID, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    events = db.scalars(select(AuditEvent).where(AuditEvent.application_id == a.id).order_by(AuditEvent.created_at)).all()
    actor_ids = {e.actor_id for e in events if e.actor_id}
    names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(actor_ids))).all()) if actor_ids else {}
    return [
        HistoryEventOut(id=e.id, action=e.action, from_value=e.from_value, to_value=e.to_value, actor_id=e.actor_id,
                        actor_name=names.get(e.actor_id) if e.actor_id else "System", actor_role=e.actor_role, note=e.note,
                        created_at=e.created_at)
        for e in events
    ]


@router.post("/{application_id}/fairness-check", response_model=FairnessOut)
def fairness_check(application_id: uuid.UUID, db: DB, user: Recruiter):
    a = get_owned_application(db, user, application_id)
    if db.scalar(select(Assessment.id).where(Assessment.application_id == a.id)) is None:
        raise Conflict("The fairness check needs a completed AI assessment", code="no_assessment")
    result = fairness.run_fairness_check(db, a)
    db.commit()
    return result
