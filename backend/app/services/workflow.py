"""Application pipeline state machine. Every change is validated, audited and (when relevant) notified."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unprocessable
from app.db.types import utcnow
from app.models import Application, User
from app.services.audit import log_event
from app.services.notifications import notify

STATUS_ORDER = [
    "submitted",
    "parsed",
    "ai_assessed",
    "recruiter_review",
    "shortlisted",
    "interview",
    "selected",
]

# Transitions a recruiter may trigger manually
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"recruiter_review", "rejected"},  # manual path when parsing/AI failed
    "parsed": {"recruiter_review", "rejected"},
    "ai_assessed": {"recruiter_review", "shortlisted", "rejected"},
    "recruiter_review": {"shortlisted", "rejected"},
    "shortlisted": {"interview", "rejected"},
    "interview": {"selected", "rejected"},
    "rejected": {"recruiter_review"},  # reconsider (reason required)
    "selected": set(),
    "withdrawn": set(),
}

# Transitions only the pipeline may perform
SYSTEM_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"parsed"},
    "parsed": {"ai_assessed"},
}

TERMINAL_FOR_CANDIDATE = {"selected", "rejected", "withdrawn"}
REASON_REQUIRED = {"rejected"}

RECRUITER_LABELS = {
    "submitted": "Submitted",
    "parsed": "Parsed",
    "ai_assessed": "AI Assessment Available",
    "recruiter_review": "Recruiter Review",
    "shortlisted": "Shortlisted",
    "interview": "Interview",
    "selected": "Selected",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

CANDIDATE_LABELS = {
    "submitted": "Submitted",
    "parsed": "Under review",
    "ai_assessed": "Under review",
    "recruiter_review": "Under review",
    "shortlisted": "Shortlisted",
    "interview": "Interview scheduled",
    "selected": "Selected",
    "rejected": "Not selected",
    "withdrawn": "Withdrawn",
}

# Statuses the candidate is told about (internal pipeline steps are not announced)
NOTIFY_CANDIDATE = {"shortlisted", "interview", "selected", "rejected"}


def status_label(status: str, *, candidate_view: bool = False) -> str:
    return (CANDIDATE_LABELS if candidate_view else RECRUITER_LABELS).get(status, status)


def allowed_transitions(application: Application, actor_role: str) -> list[str]:
    """Statuses the given role may move this application to right now."""
    if actor_role == "recruiter":
        return sorted(ALLOWED_TRANSITIONS.get(application.status, set()), key=lambda s: STATUS_ORDER.index(s) if s in STATUS_ORDER else 99)
    if actor_role == "candidate":
        return [] if application.status in TERMINAL_FOR_CANDIDATE else ["withdrawn"]
    return []


def _apply(db: Session, application: Application, to_status: str, *, actor: User | None, actor_role: str, note: str | None) -> None:
    from_status = application.status
    application.status = to_status
    now = utcnow()
    if to_status in {"selected", "rejected"}:
        application.decided_at = now
    elif from_status in {"selected", "rejected"}:
        application.decided_at = None
    log_event(
        db,
        entity_type="application",
        entity_id=application.id,
        application_id=application.id,
        action="status_change",
        actor=actor,
        actor_role=actor_role,
        from_value=from_status,
        to_value=to_status,
        note=note,
    )
    if to_status in NOTIFY_CANDIDATE and actor_role == "recruiter":
        job_title = application.job.title if application.job else "your application"
        notify(
            db,
            user_id=application.candidate_id,
            type="application_status",
            title=f"{job_title}: {CANDIDATE_LABELS[to_status]}",
            body=f"Your application status changed to {CANDIDATE_LABELS[to_status]}.",
            link="/candidate",
        )


def transition(db: Session, application: Application, to_status: str, actor: User, reason: str | None = None) -> Application:
    """Validated manual transition by a recruiter (any allowed) or the owning candidate (withdraw only)."""
    db.refresh(application, with_for_update=True)  # lock + fresh state; ignored on SQLite
    reason = (reason or "").strip() or None
    if actor.role == "candidate":
        if actor.id != application.candidate_id:
            raise Forbidden("You can only change your own applications")
        if to_status != "withdrawn":
            raise Forbidden("Candidates can only withdraw an application")
        if application.status in TERMINAL_FOR_CANDIDATE:
            raise Unprocessable("This application can no longer be withdrawn", code="illegal_transition")
        _apply(db, application, "withdrawn", actor=actor, actor_role="candidate", note=reason)
        return application

    if actor.role != "recruiter":
        raise Forbidden("Not allowed")
    allowed = ALLOWED_TRANSITIONS.get(application.status, set())
    if to_status not in allowed:
        raise Unprocessable(
            f"Cannot move an application from {status_label(application.status)} to {status_label(to_status)}",
            code="illegal_transition",
        )
    reconsider = application.status == "rejected" and to_status == "recruiter_review"
    if (to_status in REASON_REQUIRED or reconsider) and not reason:
        raise Unprocessable("A reason is required for this action", code="reason_required")
    _apply(db, application, to_status, actor=actor, actor_role="recruiter", note=reason)
    return application


def system_transition(db: Session, application: Application, to_status: str, note: str | None = None) -> bool:
    """Pipeline-driven transition. Idempotent: returns False (no-op) if not applicable from the current status."""
    if to_status not in SYSTEM_TRANSITIONS.get(application.status, set()):
        return False
    _apply(db, application, to_status, actor=None, actor_role="system", note=note)
    return True
