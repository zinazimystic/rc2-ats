"""STUB - Agent A replaces this with the real resume + assessment pipeline."""
from __future__ import annotations

from uuid import UUID


def process_resume(resume_id: UUID) -> None:
    raise NotImplementedError


def assess_application(application_id: UUID) -> None:
    raise NotImplementedError


def enqueue_resume(resume_id: UUID) -> None:
    raise NotImplementedError


def enqueue_assessment(application_id: UUID) -> None:
    raise NotImplementedError
