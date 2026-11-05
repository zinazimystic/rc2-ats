"""STUB - Agent A replaces this."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Application
from app.schemas.application import FairnessOut


def run_fairness_check(db: Session, application: Application) -> FairnessOut:
    raise NotImplementedError
