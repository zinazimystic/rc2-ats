"""STUB - Agent A replaces this."""
from __future__ import annotations

from uuid import UUID

from app.schemas.job import JobExtractOut


def extract_job_requirements(title: str | None, description: str) -> JobExtractOut:
    raise NotImplementedError


def embed_job(job_id: UUID) -> None:
    raise NotImplementedError
