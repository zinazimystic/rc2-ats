from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine

log = logging.getLogger("app.db")


def init_db() -> None:
    """Create extensions/tables/indexes. Idempotent; safe to call on every startup."""
    import app.models  # noqa: F401  (register tables)

    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            has_vector = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
            if not has_vector:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception as exc:  # pragma: no cover - depends on the managed DB
                    log.warning("Could not create pgvector extension: %s", exc)
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for stmt in (
                "CREATE INDEX IF NOT EXISTS ix_resume_chunks_embedding ON resume_chunks USING hnsw (embedding vector_cosine_ops)",
            ):
                try:
                    conn.execute(text(stmt))
                except Exception as exc:  # pragma: no cover
                    log.warning("Index creation skipped: %s", exc)
