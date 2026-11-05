"""Background task runner: in-process ThreadPoolExecutor (single uvicorn worker). Runs inline when TASKS_EAGER=true."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import or_, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.types import utcnow

log = logging.getLogger("app.tasks")
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=max(1, settings.task_workers), thread_name_prefix="ats-task")
    return _executor


def _run(fn, args, kwargs) -> None:  # noqa: ANN001
    try:
        fn(*args, **kwargs)
    except Exception:  # a background failure must never crash the worker or the request
        log.exception("background task %s failed", getattr(fn, "__name__", fn))


def submit(fn, *args, **kwargs) -> None:  # noqa: ANN001
    """Run `fn(*args, **kwargs)` in the background (inline when settings.tasks_eager). Never raises."""
    if settings.tasks_eager:
        _run(fn, args, kwargs)
        return
    try:
        _get_executor().submit(_run, fn, args, kwargs)
    except RuntimeError:  # executor shut down (interpreter exit)
        log.warning("task runner is shut down; dropping %s", getattr(fn, "__name__", fn))


def recover_stuck() -> int:
    """Re-queue work lost to a restart: resumes pending or 'processing' > 5 min, applications queued or 'processing' > 5 min."""
    from app.models import Application, Resume
    from app.services import pipeline

    cutoff = utcnow() - timedelta(minutes=5)
    with SessionLocal() as db:
        resume_ids = list(
            db.scalars(
                select(Resume.id).where(
                    or_(
                        Resume.parse_status == "pending",
                        (Resume.parse_status == "processing") & ((Resume.processing_started_at < cutoff) | Resume.processing_started_at.is_(None)),
                    )
                )
            )
        )
        app_ids = list(
            db.scalars(
                select(Application.id).where(
                    or_(
                        Application.processing_state == "queued",
                        (Application.processing_state == "processing")
                        & ((Application.processing_started_at < cutoff) | Application.processing_started_at.is_(None)),
                    )
                )
            )
        )
    for rid in resume_ids:
        pipeline.enqueue_resume(rid)
    for aid in app_ids:
        pipeline.enqueue_assessment(aid)
    n = len(resume_ids) + len(app_ids)
    if n:
        log.info("recovered %s stuck task(s)", n)
    return n
