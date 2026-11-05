"""Content-addressed cache for LLM outputs and embeddings (table `ai_cache`). Failures are never fatal."""
from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from threading import Lock
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AICache

log = logging.getLogger("app.ai.cache")

_MEM: OrderedDict[str, Any] = OrderedDict()
_MEM_MAX = 4000
_lock = Lock()


def make_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", "replace"))
        h.update(b"\x1f")
    return h.hexdigest()


def get(key: str) -> Any | None:
    with _lock:
        if key in _MEM:
            _MEM.move_to_end(key)
            return _MEM[key]
    try:
        with SessionLocal() as db:
            row = db.get(AICache, key)
            if row is not None:
                _remember(key, row.value)
                return row.value
    except Exception as exc:  # cache must never break the pipeline
        log.debug("cache read failed: %s", exc)
    return None


def get_many(keys: list[str]) -> dict[str, Any]:
    """Batch lookup: memory first, then ONE database query for everything missing (round trips matter on a remote DB)."""
    out: dict[str, Any] = {}
    missing: list[str] = []
    with _lock:
        for k in keys:
            if k in _MEM:
                _MEM.move_to_end(k)
                out[k] = _MEM[k]
            else:
                missing.append(k)
    if missing:
        try:
            with SessionLocal() as db:
                for row in db.scalars(select(AICache).where(AICache.key.in_(missing))):
                    _remember(row.key, row.value)
                    out[row.key] = row.value
        except Exception as exc:
            log.debug("cache batch read failed: %s", exc)
    return out


def put_many(items: list[tuple[str, str, Any]]) -> None:
    """Batch insert of (key, kind, value); existing keys are skipped. Two round trips regardless of size."""
    if not items:
        return
    for k, _, v in items:
        _remember(k, v)
    try:
        with SessionLocal() as db:
            have = set(db.scalars(select(AICache.key).where(AICache.key.in_([k for k, _, _ in items]))))
            db.add_all([AICache(key=k, kind=kind, value=v) for k, kind, v in items if k not in have])
            db.commit()
    except Exception as exc:
        log.debug("cache batch write failed: %s", exc)


def put(key: str, kind: str, value: Any, overwrite: bool = False) -> None:
    _remember(key, value)
    try:
        with SessionLocal() as db:
            row = db.get(AICache, key)
            if row is None:
                db.add(AICache(key=key, kind=kind, value=value))
                db.commit()
            elif overwrite:
                row.value = value
                db.commit()
    except Exception as exc:
        log.debug("cache write failed: %s", exc)


def _remember(key: str, value: Any) -> None:
    with _lock:
        _MEM[key] = value
        _MEM.move_to_end(key)
        while len(_MEM) > _MEM_MAX:
            _MEM.popitem(last=False)


def clear_memory() -> None:
    with _lock:
        _MEM.clear()
