import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JSONType, UTCDateTime
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User


class Application(Base, IdMixin, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_application_job_candidate"),)

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("resumes.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    processing_state: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    cover_note: Mapped[Optional[str]] = mapped_column(Text)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    assessed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    decided_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)

    job: Mapped[Job] = relationship()
    candidate: Mapped[User] = relationship()
    resume: Mapped[Optional[Resume]] = relationship()
    assessment: Mapped[Optional["Assessment"]] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
    notes: Mapped[list["RecruiterNote"]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="RecruiterNote.created_at.desc()"
    )


class Assessment(Base, IdMixin, TimestampMixin):
    __tablename__ = "assessments"

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), unique=True, index=True
    )
    job_version: Mapped[int] = mapped_column(Integer, default=1)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    override_score: Mapped[Optional[float]] = mapped_column(Float)
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    overridden_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    components: Mapped[dict] = mapped_column(JSONType, default=dict)  # name -> ComponentScore dict
    requirements: Mapped[list] = mapped_column(JSONType, default=list)  # list[RequirementResult dict]
    strengths: Mapped[list] = mapped_column(JSONType, default=list)
    gaps: Mapped[list] = mapped_column(JSONType, default=list)
    learning_suggestions: Mapped[list] = mapped_column(JSONType, default=list)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    summary_method: Mapped[Optional[str]] = mapped_column(String(12))
    flags: Mapped[list] = mapped_column(JSONType, default=list)
    semantic_available: Mapped[bool] = mapped_column(Boolean, default=True)
    model_info: Mapped[dict] = mapped_column(JSONType, default=dict)

    application: Mapped[Application] = relationship(back_populates="assessment")

    @property
    def effective_score(self) -> float:
        return self.override_score if self.override_score is not None else self.total_score


class RecruiterNote(Base, IdMixin, TimestampMixin):
    __tablename__ = "recruiter_notes"

    application_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="notes")
    author: Mapped[User] = relationship()
