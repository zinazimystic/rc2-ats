from __future__ import annotations

import uuid

from fastapi import APIRouter, Response
from sqlalchemy import func, select, update

from app.core.deps import DB, CurrentUser, Recruiter
from app.core.errors import NotFound
from app.core.pagination import Limit, Offset, set_total
from app.models import Notification
from app.schemas.analytics import NotificationOut
from app.schemas.common import Msg

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(response: Response, db: DB, user: CurrentUser, unread: bool | None = None, limit: Limit = 100, offset: Offset = 0):
    where = [Notification.user_id == user.id, Notification.channel == "in_app"]
    if unread:
        where.append(Notification.read.is_(False))
    rows = db.scalars(select(Notification).where(*where).order_by(Notification.created_at.desc()).limit(limit).offset(offset)).all()
    set_total(response, len(rows), limit, offset, lambda: db.scalar(select(func.count()).select_from(Notification).where(*where)) or 0)
    return rows


@router.get("/outbox", response_model=list[NotificationOut])
def outbox(response: Response, db: DB, user: Recruiter, limit: Limit = 100, offset: Offset = 0):
    where = [Notification.sender_id == user.id, Notification.channel == "email_sim"]
    rows = db.scalars(select(Notification).where(*where).order_by(Notification.created_at.desc()).limit(limit).offset(offset)).all()
    set_total(response, len(rows), limit, offset, lambda: db.scalar(select(func.count()).select_from(Notification).where(*where)) or 0)
    return rows


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
