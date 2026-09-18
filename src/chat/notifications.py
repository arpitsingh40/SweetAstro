"""
Web-push subscriptions and due-notification computation (config-gated).

Dependency-free by design: the bounded subscription store and the schedule
computation are unit-testable without a push service. Actual delivery needs
VAPID keys and a worker calling an external sender; that is intentionally out
of scope here. Notifications are substance-only (dasha boundaries), never
engagement mechanics.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List

LEAD_DAYS = 3
MAX_SUBSCRIPTIONS = 500


@dataclass
class PushSubscription:
    endpoint: str
    keys: Dict[str, str] = field(default_factory=dict)
    profile: str = ""


class NotificationStore:
    """Thread-safe, bounded, idempotent subscription store (in memory)."""

    def __init__(self, max_subscriptions: int = MAX_SUBSCRIPTIONS):
        self.max_subscriptions = max(1, max_subscriptions)
        self._subscriptions: Dict[str, PushSubscription] = {}
        self._lock = threading.Lock()

    def subscribe(self, endpoint: str, keys: Dict[str, str], profile: str = "") -> bool:
        endpoint = (endpoint or "").strip()
        if not endpoint:
            return False
        with self._lock:
            if endpoint in self._subscriptions:
                self._subscriptions[endpoint].keys = dict(keys or {})
                self._subscriptions[endpoint].profile = profile
                return False
            while len(self._subscriptions) >= self.max_subscriptions:
                oldest = next(iter(self._subscriptions))
                self._subscriptions.pop(oldest, None)
            self._subscriptions[endpoint] = PushSubscription(
                endpoint=endpoint, keys=dict(keys or {}), profile=profile)
            return True

    def unsubscribe(self, endpoint: str) -> bool:
        with self._lock:
            return self._subscriptions.pop((endpoint or "").strip(), None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def list(self) -> List[PushSubscription]:
        with self._lock:
            return list(self._subscriptions.values())


def build_due_notifications(periods: List[Any], now: datetime, *,
                            lead_days: int = LEAD_DAYS) -> List[Dict[str, str]]:
    """Dasha periods starting inside the lead window, as push payloads."""
    window_end = now + timedelta(days=lead_days)
    due: List[Dict[str, str]] = []
    for period in periods:
        start = getattr(period, "start_date", None)
        if start is None:
            continue
        if now <= start <= window_end:
            level = getattr(period, "level", "")
            lord = getattr(period, "lord", "")
            due.append({
                "title": f"Vimshottari {level} {lord} begins {start:%d %b}",
                "body": (f"A new {level} period ({lord}) starts on {start:%Y-%m-%d}. "
                         "Open SweetAstro for the chart reading."),
                "start": start.strftime("%Y-%m-%d"),
                "url": "/app/today",
            })
    return due
