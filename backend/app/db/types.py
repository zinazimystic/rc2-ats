"""Portable column types so the same models run on Supabase Postgres (pgvector) and SQLite (dev/tests)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import DateTime, TypeDecorator

from app.core.config import settings


def utcnow() -> datetime:
    """Timezone-aware 'now' in UTC."""
    return datetime.now(timezone.utc)


def to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class UTCDateTime(TypeDecorator):
    """Stores naive UTC, returns tz-aware UTC. Naive inputs are treated as UTC (SQLite drops tzinfo)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return to_naive_utc(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


JSONType = JSON().with_variant(JSONB(), "postgresql")


class Embedding(TypeDecorator):
    """pgvector `vector(N)` on Postgres, JSON list on SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(settings.embedding_dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if hasattr(value, "tolist"):
            return [float(x) for x in value.tolist()]
        if isinstance(value, str):
            return [float(x) for x in value.strip("[]").split(",") if x.strip()]
        return [float(x) for x in value]
