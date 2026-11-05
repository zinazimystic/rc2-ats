"""Count SQL statements issued per request (SQLAlchemy `before_cursor_execute`).

The remote Postgres costs ~90 ms per round trip, so the statement count of an endpoint is its latency budget.

    with count_queries() as qc:
        client.get("/api/jobs")
    assert qc.count <= 6, qc.report()
"""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager

from sqlalchemy import event

_SKIP = re.compile(r"^\s*(PRAGMA|SAVEPOINT|RELEASE|ROLLBACK TO)", re.I)


class QueryCounter:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        return len(self.statements)

    def _on_execute(self, conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if _SKIP.match(statement):
            return
        with self._lock:
            self.statements.append(" ".join(statement.split()))

    def report(self, width: int = 150) -> str:
        return "\n".join(f"{i + 1:>3}. {s[:width]}" for i, s in enumerate(self.statements))

    def tables(self) -> dict[str, int]:
        """Statement count per primary table (diagnostics for spotting N+1 patterns)."""
        out: dict[str, int] = {}
        for s in self.statements:
            m = re.search(r"\b(?:FROM|INTO|UPDATE)\s+([a-z_]+)", s, re.I)
            key = (m.group(1) if m else "?").lower()
            out[key] = out.get(key, 0) + 1
        return out


@contextmanager
def count_queries():
    from app.db.session import engine

    qc = QueryCounter()
    event.listen(engine, "before_cursor_execute", qc._on_execute)
    try:
        yield qc
    finally:
        event.remove(engine, "before_cursor_execute", qc._on_execute)
