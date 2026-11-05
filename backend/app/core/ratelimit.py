"""Tiny in-process sliding-window limiter (single uvicorn worker, see README)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import TooManyRequests


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def check(self, key: str, limit: int, window: float, message: str = "Too many attempts. Please wait a minute and try again.") -> None:
        """Raise 429 when `limit` hits were already recorded in the last `window` seconds."""
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, window, now)
            if len(q) >= limit:
                retry = max(1, int(window - (now - q[0])))
                raise TooManyRequests(message, extra={"retry_after": retry})

    def hit(self, key: str, window: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, window, now).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
