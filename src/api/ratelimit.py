"""
Simple sliding-window rate limiter (thread-safe, in-memory).

Used to protect the LLM key from accidental loops or abuse on the chat
endpoints. Limits are per client key (IP address) per minute.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic):
        self.limit = max(1, limit)
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            events = self._events[key]
            cutoff = now - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def retry_after_seconds(self, key: str) -> float:
        with self._lock:
            events = self._events.get(key)
            if not events:
                return 0.0
            return max(0.0, self.window_seconds - (self._clock() - events[0]))
