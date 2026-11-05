"""In-app notifications plus a simulated email outbox (no real email is ever sent)."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Notification


def notify(
    db: Session,
    *,
    type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    user_id: uuid.UUID | None = None,
    recipient_email: str | None = None,
    channel: str = "in_app",
    sender_id: uuid.UUID | None = None,
) -> Notification:
    """Add a notification to the session (caller commits).

    channel="in_app"    -> shown in the recipient's bell (needs user_id)
    channel="email_sim" -> a simulated email, listed in the recruiter's outbox (sender_id = recruiter)
    """
    n = Notification(
        user_id=user_id,
        sender_id=sender_id,
        recipient_email=recipient_email,
        channel=channel,
        type=type,
        title=title[:200],
        body=body,
        link=link,
    )
    db.add(n)
    return n
