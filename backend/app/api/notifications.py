from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select, update

from app.core.deps import DB, CurrentUser, Recruiter
from app.core.errors import NotFound
from app.models import Notification
from app.schemas.analytics import NotificationOut
from app.schemas.common import Msg

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: DB, user: CurrentUser, unread: bool | None = None):
    stmt = select(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app")
    if unread:
        stmt = stmt.where(Notification.read.is_(False))
    return db.scalars(stmt.order_by(Notification.created_at.desc()).limit(100)).all()


@router.get("/outbox", response_model=list[NotificationOut])
def outbox(db: DB, user: Recruiter):
    return db.scalars(
        select(Notification).where(Notification.sender_id == user.id, Notification.channel == "email_sim")
        .order_by(Notification.created_at.desc()).limit(100)
    ).all()


@router.post("/read-all", response_model=Msg)
def read_all(db: DB, user: CurrentUser):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False)).values(read=True))
    db.commit()
    return Msg(detail="All notifications marked as read")


@router.post("/{notification_id}/read", response_model=NotificationOut)
def read_one(notification_id: uuid.UUID, db: DB, user: CurrentUser):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise NotFound("Notification not found")
    n.read = True
    db.commit()
    return n
