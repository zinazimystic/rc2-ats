"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import (
    analytics,
    applications,
    auth,
    candidates,
    duplicates,
    health,
    interviews,
    jobs,
    notifications,
    questions,
    resumes,
    search,
)
from app.core.config import settings
from app.core.errors import install_handlers
from app.core.ratelimit import limiter
from app.db.init_db import init_db
from app.services import tasks

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        n = tasks.recover_stuck()
        if n:
            log.info("Re-queued %s stuck background jobs", n)
    except Exception as exc:  # noqa: BLE001 - recovery is best-effort
        log.warning("Could not recover stuck tasks: %s", exc)
    yield


def create_app() -> FastAPI:
    limiter.reset()
    app = FastAPI(
        title="RC3 Talent Intelligence Platform",
        version="1.0.0",
        redirect_slashes=False,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    install_handlers(app)

    @app.middleware("http")
    async def _guards(request: Request, call_next):
        # Reject oversized uploads early (multipart overhead gets 1 MB of slack)
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_upload_bytes + 1_048_576:
            return JSONResponse(
                status_code=413,
                content={"detail": f"File is too large (maximum {settings.max_upload_mb} MB)", "code": "file_too_large"},
            )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    for r in (
        health.router,
        auth.router,
        jobs.router,
        candidates.router,
        resumes.router,
        resumes.skills_router,
        applications.router,
        applications.notes_router,
        interviews.app_router,
        interviews.router,
        questions.router,
        search.router,
        analytics.router,
        duplicates.router,
        notifications.router,
    ):
        app.include_router(r, prefix="/api")
    return app


app = create_app()
