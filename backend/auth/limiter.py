from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, DefaultDict
from time import monotonic


class LoginRateLimiter:
    def __init__(self, *, max_attempts: int = 5, window_seconds: float = 60.0, block_seconds: float = 300.0) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._failures: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}

    def _now(self) -> float:
        return monotonic()

    def _prune(self, key: str, now: float) -> None:
        bucket = self._failures.get(key)
        if not bucket:
            return
        window_start = now - self.window_seconds
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if not bucket:
            self._failures.pop(key, None)

    def check(self, key: str) -> float | None:
        now = self._now()
        blocked_until = self._blocked_until.get(key)
        if blocked_until and blocked_until > now:
            return blocked_until - now
        if blocked_until and blocked_until <= now:
            self._blocked_until.pop(key, None)
        self._prune(key, now)
        return None

    def hit(self, key: str) -> float | None:
        now = self._now()
        self._prune(key, now)
        bucket = self._failures[key]
        bucket.append(now)
        if len(bucket) >= self.max_attempts:
            blocked_until = now + self.block_seconds
            self._blocked_until[key] = blocked_until
            bucket.clear()
            return blocked_until - now
        return None

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
        self._blocked_until.pop(key, None)
