"""Content-addressed cache for LLM outputs and embeddings (table `ai_cache`). Failures are never fatal."""
from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from threading import Lock
from typing import Any

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
