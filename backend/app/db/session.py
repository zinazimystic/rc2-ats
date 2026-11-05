from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _build_engine() -> Engine:
    url = settings.resolved_database_url
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, echo=settings.sql_echo)

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return eng

    eng = create_engine(
        url,
        pool_size=8,
        max_overflow=5,
        pool_pre_ping=False,  # a pre-ping costs one extra DB round trip per request; pool_recycle covers stale connections
        pool_recycle=270,
        echo=settings.sql_echo,
        # prepared statements are not supported by Supabase's transaction pooler; harmless on the session pooler
        connect_args={"prepare_threshold": None},
    )

    @event.listens_for(eng, "connect")
    def _search_path(dbapi_conn, _):  # noqa: ANN001
        # pgvector may live in the `extensions` schema on Supabase
        cur = dbapi_conn.cursor()
        cur.execute("SET search_path TO public, extensions")
        cur.close()
        dbapi_conn.commit()

    return eng


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
