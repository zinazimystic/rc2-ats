import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JSONType, UTCDateTime


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), index=True)  # recruiter | candidate
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    profile: Mapped[Optional["CandidateProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", foreign_keys="CandidateProfile.user_id"
    )


class CandidateProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    headline: Mapped[Optional[str]] = mapped_column(String(160))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    location: Mapped[Optional[str]] = mapped_column(String(160))
    links: Mapped[list] = mapped_column(JSONType, default=list)
    interests: Mapped[list] = mapped_column(JSONType, default=list)
    talent_pool_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_until: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    # set when a confirmed duplicate record is linked to a primary candidate record
    merged_into_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))

    user: Mapped[User] = relationship(back_populates="profile", foreign_keys=[user_id])
