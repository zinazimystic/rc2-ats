"""Append-only audit trail helper."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def log_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: User | None = None,
    actor_role: str | None = None,
    application_id: uuid.UUID | None = None,
    from_value: str | None = None,
    to_value: str | None = None,
    note: str | None = None,
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit event to the session (caller commits)."""
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        application_id=application_id,
        action=action,
        from_value=from_value,
        to_value=to_value,
        actor_id=actor.id if actor else None,
        actor_role=actor_role or (actor.role if actor else "system"),
        note=note,
        data=data,
    )
    db.add(event)
    return event
