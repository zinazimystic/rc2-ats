import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import Embedding, JSONType, UTCDateTime


class Resume(Base, IdMixin, TimestampMixin):
    __tablename__ = "resumes"

    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[Optional[str]] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_bytes: Mapped[Optional[bytes]] = deferred(mapped_column(LargeBinary))
    text: Mapped[Optional[str]] = deferred(mapped_column(Text))
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    parse_status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSONType, default=list)  # list[str]
    integrity_flags: Mapped[list] = mapped_column(JSONType, default=list)  # list[Flag dict]
    extraction_method: Mapped[Optional[str]] = mapped_column(String(10))  # llm | rules
    parsed: Mapped[Optional[dict]] = mapped_column(JSONType)  # ParsedResume dict
    doc_embedding: Mapped[Optional[list]] = mapped_column(Embedding)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)  # used by tasks.recover_stuck

    chunks: Mapped[list["ResumeChunk"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="ResumeChunk.idx"
    )
    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="CandidateSkill.name"
    )


class ResumeChunk(Base, IdMixin):
    __tablename__ = "resume_chunks"

    resume_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    section: Mapped[Optional[str]] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[Optional[list]] = mapped_column(Embedding)

    resume: Mapped[Resume] = relationship(back_populates="chunks")


class CandidateSkill(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidate_skills"
    __table_args__ = (UniqueConstraint("resume_id", "name", name="uq_resume_skill"),)

    resume_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))  # canonical name
    raw_name: Mapped[Optional[str]] = mapped_column(String(120))
    category: Mapped[Optional[str]] = mapped_column(String(40))
    presence: Mapped[str] = mapped_column(String(10), default="present")  # present | absent
    source: Mapped[str] = mapped_column(String(12), default="ai")  # ai | rules | candidate | recruiter
    verification: Mapped[str] = mapped_column(String(14), default="verified")  # verified|fuzzy|unverified|self_reported
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    start: Mapped[Optional[int]] = mapped_column(Integer)
    end: Mapped[Optional[int]] = mapped_column(Integer)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    resume: Mapped[Resume] = relationship(back_populates="skills")
