"""STUB - Agent A replaces this."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import DuplicateFlag, Resume, User


def detect_for_resume(db: Session, resume: Resume) -> list[DuplicateFlag]:
    raise NotImplementedError


def merge(db: Session, flag: DuplicateFlag, actor: User) -> None:
    raise NotImplementedError
