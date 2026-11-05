import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JSONType, UTCDateTime, utcnow


class AuditEvent(Base, IdMixin):
    """Append-only audit trail (status changes, overrides, notes, interviews...)."""

    __tablename__ = "audit_events"

    entity_type: Mapped[str] = mapped_column(String(30))  # application | job | resume | interview | duplicate
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    from_value: Mapped[Optional[str]] = mapped_column(String(120))
    to_value: Mapped[Optional[str]] = mapped_column(String(120))
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[Optional[str]] = mapped_column(String(12))  # recruiter | candidate | system
    note: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class Notification(Base, IdMixin):
    """In-app notifications and the simulated email outbox (channel='email_sim')."""

    __tablename__ = "notifications"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(12), default="in_app")
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[Optional[str]] = mapped_column(String(300))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class DuplicateFlag(Base, IdMixin, TimestampMixin):
    """Likely-duplicate candidate pair awaiting human confirmation (never merged automatically)."""

    __tablename__ = "duplicate_flags"
    __table_args__ = (UniqueConstraint("candidate_a_id", "candidate_b_id", name="uq_duplicate_pair"),)

    candidate_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    candidate_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reasons: Mapped[list] = mapped_column(JSONType, default=list)
    similarity: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending|confirmed|dismissed
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)


class AICache(Base):
    """Cache of LLM outputs and embeddings keyed by sha256 of the input."""

    __tablename__ = "ai_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    value: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
