import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JSONType, UTCDateTime
from app.models.application import Application
from app.models.user import User


class InterviewQuestion(Base, IdMixin, TimestampMixin):
    __tablename__ = "interview_questions"

    application_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    difficulty: Mapped[str] = mapped_column(String(14), default="intermediate")
    category: Mapped[str] = mapped_column(String(40), default="skill")  # skill | project | gap | behavioral
    question: Mapped[str] = mapped_column(Text)
    answer_guidelines: Mapped[list] = mapped_column(JSONType, default=list)
    related_skill: Mapped[Optional[str]] = mapped_column(String(80))
    source_quote: Mapped[Optional[str]] = mapped_column(Text)
    source_verified: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Interview(Base, IdMixin, TimestampMixin):
    __tablename__ = "interviews"

    application_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    scheduled_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    interviewer_name: Mapped[str] = mapped_column(String(120))
    interviewer_email: Mapped[Optional[str]] = mapped_column(String(255))
    interview_type: Mapped[str] = mapped_column(String(20), default="technical")
    start_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    location: Mapped[Optional[str]] = mapped_column(String(300))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="scheduled", index=True)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_details: Mapped[list] = mapped_column(JSONType, default=list)

    application: Mapped[Application] = relationship()
    feedback: Mapped[list["InterviewFeedback"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="InterviewFeedback.created_at"
    )


class InterviewFeedback(Base, IdMixin, TimestampMixin):
    __tablename__ = "interview_feedback"
    __table_args__ = (UniqueConstraint("interview_id", "author_id", name="uq_feedback_interview_author"),)

    interview_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    ratings: Mapped[dict] = mapped_column(JSONType, default=dict)
    recommendation: Mapped[str] = mapped_column(String(12))
    comments: Mapped[Optional[str]] = mapped_column(Text)

    interview: Mapped[Interview] = relationship(back_populates="feedback")
    author: Mapped[User] = relationship()
