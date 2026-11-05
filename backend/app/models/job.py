import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, deferred, joinedload, mapped_column, relationship, selectinload, undefer

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import Embedding, JSONType

DEFAULT_WEIGHTS = {"skills": 50, "experience": 25, "projects": 15, "qualifications": 10}


class Job(Base, IdMixin, TimestampMixin):
    __tablename__ = "jobs"

    recruiter_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    department: Mapped[Optional[str]] = mapped_column(String(120))
    location: Mapped[Optional[str]] = mapped_column(String(160))
    employment_type: Mapped[str] = mapped_column(String(20), default="full_time")
    work_mode: Mapped[str] = mapped_column(String(20), default="onsite")
    salary_min: Mapped[Optional[float]] = mapped_column(Float)
    salary_max: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    description: Mapped[str] = mapped_column(Text)
    min_experience_years: Mapped[float] = mapped_column(Float, default=0)
    education_level: Mapped[str] = mapped_column(String(20), default="none")
    qualifications: Mapped[list] = mapped_column(JSONType, default=list)
    weights: Mapped[dict] = mapped_column(JSONType, default=lambda: dict(DEFAULT_WEIGHTS))
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open | closed
    version: Mapped[int] = mapped_column(Integer, default=1)
    embedding: Mapped[Optional[list]] = deferred(mapped_column(Embedding))  # vectors are heavy: load via undefer only when scoring

    requirements: Mapped[list["JobRequirement"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobRequirement.position"
    )


class JobRequirement(Base, IdMixin):
    __tablename__ = "job_requirements"

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10), default="required")  # required | preferred
    importance: Mapped[int] = mapped_column(Integer, default=3)  # 1..5
    position: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Optional[list]] = deferred(mapped_column(Embedding))  # vectors are heavy: load via undefer only when scoring

    job: Mapped[Job] = relationship(back_populates="requirements")


def job_vector_options(*, join: bool = False):
    """Loader options for code that SCORES a job: the job's requirements plus the (deferred) embedding vectors, in one go.
    Everything else (lists, detail pages, counts) leaves the heavy vectors on the server."""
    loader = joinedload(Job.requirements) if join else selectinload(Job.requirements)
    return (undefer(Job.embedding), loader.undefer(JobRequirement.embedding))
