"""Interview scheduling: conflict detection (interviewer + candidate double-booking), serialisation, lifecycle."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import Conflict, Unprocessable
from app.db.types import utcnow
from app.models import Application, Interview, InterviewFeedback, Job, User
from app.schemas.interview import (
    ConflictOut,
    FeedbackIn,
    FeedbackOut,
    FeedbackRatings,
    InterviewIn,
    InterviewOut,
    InterviewPatch,
)
from app.services import workflow
from app.services.audit import log_event
from app.services.notifications import notify


def as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _fmt(dt: datetime) -> str:
    return as_utc(dt).strftime("%a %d %b %Y, %H:%M UTC")


def _same_interviewer(a_name: str, a_email: str | None, b_name: str, b_email: str | None) -> bool:
    if a_email and b_email:
        return a_email.strip().lower() == b_email.strip().lower()
    return a_name.strip().lower() == b_name.strip().lower()


def find_conflicts(
    db: Session,
    recruiter: User,
    application: Application,
    *,
    start_at: datetime,
    end_at: datetime,
    interviewer_name: str,
    interviewer_email: str | None,
    exclude_id: uuid.UUID | None = None,
) -> list[ConflictOut]:
    """Overlapping scheduled interviews for the same interviewer or the same candidate. Back-to-back is fine."""
    rows = db.execute(
        select(Interview, User.full_name, Application.candidate_id)
        .join(Application, Application.id == Interview.application_id)
        .join(Job, Job.id == Application.job_id)
        .join(User, User.id == Application.candidate_id)
        .where(
            Interview.status == "scheduled",
            Interview.start_at < end_at,
            Interview.end_at > start_at,
            (Job.recruiter_id == recruiter.id) | (Application.candidate_id == application.candidate_id),
        )
    ).all()
    conflicts: list[ConflictOut] = []
    for iv, cand_name, cand_id in rows:
        if exclude_id and iv.id == exclude_id:
            continue
        if cand_id == application.candidate_id:
            conflicts.append(
                ConflictOut(
                    kind="candidate",
                    interview_id=iv.id,
                    start_at=iv.start_at,
                    end_at=iv.end_at,
                    with_whom=iv.interviewer_name,
                    message=f"The candidate already has an interview with {iv.interviewer_name} "
                    f"({_fmt(iv.start_at)} – {as_utc(iv.end_at).strftime('%H:%M')})",
                )
            )
        elif _same_interviewer(interviewer_name, interviewer_email, iv.interviewer_name, iv.interviewer_email):
            conflicts.append(
                ConflictOut(
                    kind="interviewer",
                    interview_id=iv.id,
                    start_at=iv.start_at,
                    end_at=iv.end_at,
                    with_whom=cand_name,
                    message=f"{iv.interviewer_name} is already interviewing {cand_name} "
                    f"({_fmt(iv.start_at)} – {as_utc(iv.end_at).strftime('%H:%M')})",
                )
            )
    return conflicts


def conflict_error(conflicts: list[ConflictOut]) -> Conflict:
    return Conflict(
        "This time clashes with another interview. Pick another slot or schedule anyway.",
        code="schedule_conflict",
        extra={"conflicts": [c.model_dump(mode="json") for c in conflicts]},
    )


def to_interview_out(iv: Interview, application: Application | None = None, authors: dict | None = None) -> InterviewOut:
    app = application or iv.application
    cand = app.candidate if app is not None else None
    job = app.job if app is not None else None
    fb = []
    for f in iv.feedback:
        author_name = (authors or {}).get(f.author_id) or (f.author.full_name if f.author else "")
        fb.append(
            FeedbackOut(
                id=f.id,
                interview_id=f.interview_id,
                author_id=f.author_id,
                author_name=author_name,
                ratings=FeedbackRatings(**f.ratings),
                recommendation=f.recommendation,
                comments=f.comments,
                created_at=f.created_at,
            )
        )
    return InterviewOut(
        id=iv.id,
        application_id=iv.application_id,
        candidate_id=app.candidate_id if app else None,
        candidate_name=cand.full_name if cand else "",
        job_id=app.job_id if app else None,
        job_title=job.title if job else "",
        interviewer_name=iv.interviewer_name,
        interviewer_email=iv.interviewer_email,
        interview_type=iv.interview_type,
        start_at=iv.start_at,
        end_at=iv.end_at,
        location=iv.location,
        notes=iv.notes,
        status=iv.status,
        has_conflict=iv.has_conflict,
        conflict_details=[ConflictOut(**c) for c in (iv.conflict_details or [])],
        feedback=fb,
        created_at=iv.created_at,
    )


def load_interviews(db: Session, where_clause) -> list[Interview]:
    return list(
        db.scalars(
            select(Interview)
            .options(
                selectinload(Interview.feedback).selectinload(InterviewFeedback.author),
                selectinload(Interview.application).selectinload(Application.candidate),
                selectinload(Interview.application).selectinload(Application.job),
            )
            .where(where_clause)
            .order_by(Interview.start_at)
        ).all()
    )


def _check_future(start_at: datetime) -> None:
    if as_utc(start_at) < utcnow() - timedelta(minutes=5):
        raise Unprocessable("Interviews cannot be scheduled in the past", code="past_time")


def schedule(db: Session, recruiter: User, application: Application, data: InterviewIn) -> Interview:
    if application.status in ("withdrawn", "rejected", "selected"):
        raise Unprocessable(
            f"Cannot schedule an interview for an application that is {workflow.status_label(application.status).lower()}",
            code="illegal_state",
        )
    if application.status not in ("shortlisted", "interview"):
        raise Unprocessable("Shortlist the candidate before scheduling an interview", code="illegal_state")
    start = as_utc(data.start_at)
    _check_future(start)
    end = start + timedelta(minutes=data.duration_minutes)
    conflicts = find_conflicts(
        db, recruiter, application, start_at=start, end_at=end,
        interviewer_name=data.interviewer_name, interviewer_email=data.interviewer_email,
    )
    if conflicts and not data.force:
        raise conflict_error(conflicts)
    iv = Interview(
        application_id=application.id,
        scheduled_by=recruiter.id,
        interviewer_name=data.interviewer_name.strip(),
        interviewer_email=data.interviewer_email,
        interview_type=data.interview_type,
        start_at=start,
        end_at=end,
        location=data.location,
        notes=data.notes,
        status="scheduled",
        has_conflict=bool(conflicts),
        conflict_details=[c.model_dump(mode="json") for c in conflicts],
    )
    db.add(iv)
    db.flush()
    if application.status == "shortlisted":
        workflow.transition(db, application, "interview", recruiter, "Interview scheduled")
    log_event(
        db, entity_type="interview", entity_id=iv.id, application_id=application.id, action="interview_scheduled",
        actor=recruiter, to_value=start.isoformat(),
        note=f"{data.interview_type} interview with {iv.interviewer_name}",
        data={"forced_over_conflict": bool(conflicts)},
    )
    job_title = application.job.title if application.job else "your application"
    notify(
        db, user_id=application.candidate_id, type="interview_scheduled",
        title=f"Interview scheduled: {job_title}",
        body=f"{data.interview_type.title()} interview on {_fmt(start)}" + (f" · {iv.location}" if iv.location else ""),
        link="/candidate",
    )
    _outbox(db, recruiter, application, iv, "Interview invitation")
    return iv


def _outbox(db: Session, recruiter: User, application: Application, iv: Interview, subject: str) -> None:
    job_title = application.job.title if application.job else ""
    body = f"{subject} for {job_title}: {_fmt(iv.start_at)} ({iv.interview_type})" + (f" at {iv.location}" if iv.location else "")
    notify(db, type="email_interview", channel="email_sim", sender_id=recruiter.id,
           recipient_email=application.candidate.email, title=f"{subject}: {job_title}", body=body)
    if iv.interviewer_email:
        notify(db, type="email_interview", channel="email_sim", sender_id=recruiter.id,
               recipient_email=iv.interviewer_email, title=f"{subject}: {application.candidate.full_name}", body=body)


def update(db: Session, recruiter: User, iv: Interview, data: InterviewPatch) -> Interview:
    application = iv.application
    changes = data.model_dump(exclude_unset=True, exclude={"force"})
    if iv.status != "scheduled":
        if set(changes) - {"notes"}:
            raise Conflict(f"This interview is {iv.status} and can no longer be changed", code="interview_closed")
    new_status = changes.get("status")
    if new_status and new_status != iv.status and iv.status != "scheduled":
        raise Conflict(f"This interview is {iv.status} and can no longer be changed", code="interview_closed")

    timing_changed = False
    if "interviewer_name" in changes and changes["interviewer_name"] is not None:
        iv.interviewer_name = changes["interviewer_name"].strip()
        timing_changed = True
    for f in ("interviewer_email",):
        if f in changes:
            setattr(iv, f, changes[f])
            timing_changed = True
    for f in ("interview_type", "location", "notes"):
        if f in changes and (changes[f] is not None or f != "interview_type"):
            setattr(iv, f, changes[f])
    duration = int((iv.end_at - iv.start_at).total_seconds() // 60)
    if changes.get("start_at") is not None:
        new_start = as_utc(changes["start_at"])
        if new_start != as_utc(iv.start_at):
            _check_future(new_start)
        iv.start_at = new_start
        timing_changed = True
    if changes.get("duration_minutes") is not None:
        duration = changes["duration_minutes"]
        timing_changed = True
    iv.end_at = as_utc(iv.start_at) + timedelta(minutes=duration)

    rescheduling = timing_changed and (new_status in (None, "scheduled")) and iv.status == "scheduled"
    if rescheduling:
        conflicts = find_conflicts(
            db, recruiter, application, start_at=iv.start_at, end_at=iv.end_at,
            interviewer_name=iv.interviewer_name, interviewer_email=iv.interviewer_email, exclude_id=iv.id,
        )
        if conflicts and not data.force:
            db.rollback()
            raise conflict_error(conflicts)
        iv.has_conflict = bool(conflicts)
        iv.conflict_details = [c.model_dump(mode="json") for c in conflicts]

    job_title = application.job.title if application.job else "your application"
    if new_status and new_status != iv.status:
        old = iv.status
        iv.status = new_status
        log_event(db, entity_type="interview", entity_id=iv.id, application_id=application.id,
                  action=f"interview_{new_status}", actor=recruiter, from_value=old, to_value=new_status)
        if new_status == "cancelled":
            iv.has_conflict, iv.conflict_details = False, []
            notify(db, user_id=application.candidate_id, type="interview_cancelled",
                   title=f"Interview cancelled: {job_title}", body=f"Your interview on {_fmt(iv.start_at)} was cancelled.", link="/candidate")
    elif rescheduling:
        log_event(db, entity_type="interview", entity_id=iv.id, application_id=application.id,
                  action="interview_rescheduled", actor=recruiter, to_value=as_utc(iv.start_at).isoformat())
        notify(db, user_id=application.candidate_id, type="interview_rescheduled",
               title=f"Interview updated: {job_title}", body=f"Your interview is now on {_fmt(iv.start_at)}.", link="/candidate")
        _outbox(db, recruiter, application, iv, "Interview updated")
    db.flush()
    return iv


def submit_feedback(db: Session, recruiter: User, iv: Interview, data: FeedbackIn) -> Interview:
    if iv.status == "cancelled":
        raise Conflict("Feedback cannot be added to a cancelled interview", code="interview_closed")
    existing = next((f for f in iv.feedback if f.author_id == recruiter.id), None)
    ratings = data.ratings.model_dump()
    if existing:
        existing.ratings, existing.recommendation, existing.comments = ratings, data.recommendation, data.comments
    else:
        iv.feedback.append(
            InterviewFeedback(interview_id=iv.id, author_id=recruiter.id, ratings=ratings,
                              recommendation=data.recommendation, comments=data.comments)
        )
    if iv.status == "scheduled":
        iv.status = "completed"
        iv.has_conflict, iv.conflict_details = False, []
    log_event(db, entity_type="interview", entity_id=iv.id, application_id=iv.application_id, action="interview_feedback",
              actor=recruiter, to_value=data.recommendation, note=data.comments)
    db.flush()
    return iv


def cancel_for_withdrawn(db: Session, application: Application) -> None:
    for iv in db.scalars(select(Interview).where(Interview.application_id == application.id, Interview.status == "scheduled")):
        iv.status = "cancelled"
        iv.has_conflict, iv.conflict_details = False, []
