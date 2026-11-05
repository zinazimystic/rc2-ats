from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine

log = logging.getLogger("app.db")


# (table, column, postgres DDL type + default, sqlite DDL type + default)
NEW_COLUMNS: list[tuple[str, str, str, str]] = [
    ("users", "email_verified_at", "TIMESTAMP NULL", "DATETIME NULL"),
    ("users", "email_code_hash", "VARCHAR(128) NULL", "VARCHAR(128) NULL"),
    ("users", "email_code_expires_at", "TIMESTAMP NULL", "DATETIME NULL"),
    ("users", "email_code_attempts", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ("candidate_profiles", "whatsapp_enabled", "BOOLEAN NOT NULL DEFAULT FALSE", "BOOLEAN NOT NULL DEFAULT 0"),
    ("resumes", "deleted_at", "TIMESTAMP NULL", "DATETIME NULL"),
]


def _ensure_columns() -> None:
    """create_all never alters existing tables: add columns introduced after the first deploy. Idempotent."""
    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for table, col, pg_ddl, _ in NEW_COLUMNS:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {pg_ddl}"))
                except Exception as exc:  # pragma: no cover - depends on the managed DB
                    log.warning("Could not add column %s.%s: %s", table, col, exc)
        return
    with engine.begin() as conn:
        for table, col, _, lite_ddl in NEW_COLUMNS:
            have = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if have and col not in have:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {lite_ddl}"))


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
    _ensure_columns()
    if engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for stmt in (
                "CREATE INDEX IF NOT EXISTS ix_resume_chunks_embedding ON resume_chunks USING hnsw (embedding vector_cosine_ops)",
            ):
                try:
                    conn.execute(text(stmt))
                except Exception as exc:  # pragma: no cover
                    log.warning("Index creation skipped: %s", exc)
