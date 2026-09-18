"""
Push subscription + due-notification tests (no external push service).
"""

from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from SweetAstro.src.api.app import app
from SweetAstro.src.chat.notifications import NotificationStore, build_due_notifications

client = TestClient(app)


class _Period:
    def __init__(self, level: str, lord: str, start_date: datetime):
        self.level = level
        self.lord = lord
        self.start_date = start_date


def test_subscribe_validates_endpoint_and_unsubscribes():
    bad = client.post("/api/notifications/subscribe", json={"endpoint": "http://insecure"})
    assert bad.status_code == 400

    ok = client.post("/api/notifications/subscribe", json={
        "endpoint": "https://push.example/abc",
        "keys": {"p256dh": "key", "auth": "auth"},
        "profile": "profile-1",
    })
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True and body["created"] is True
    assert body["push_configured"] is False  # no VAPID key in tests

    duplicate = client.post("/api/notifications/subscribe", json={
        "endpoint": "https://push.example/abc", "keys": {}, "profile": "profile-1",
    })
    assert duplicate.json()["created"] is False

    off = client.post("/api/notifications/unsubscribe", json={"endpoint": "https://push.example/abc"})
    assert off.json()["removed"] is True


def test_build_due_notifications_selects_lead_window():
    now = datetime(2026, 9, 15)
    periods = [
        _Period("AD", "Venus", now + timedelta(days=2)),
        _Period("MD", "Saturn", now + timedelta(days=10)),
        _Period("PD", "Mercury", now - timedelta(days=1)),
    ]
    due = build_due_notifications(periods, now, lead_days=3)
    assert len(due) == 1
    assert "Venus" in due[0]["title"]
    assert due[0]["start"] == "2026-09-17"
    assert due[0]["url"] == "/app/today"


def test_notification_store_is_bounded_and_idempotent():
    store = NotificationStore(max_subscriptions=2)
    assert store.subscribe("https://a", {}, "p") is True
    assert store.subscribe("https://a", {}, "p") is False
    store.subscribe("https://b", {}, "p")
    store.subscribe("https://c", {}, "p")
    assert store.count() == 2
    assert store.unsubscribe("https://b") is True
    assert store.unsubscribe("https://b") is False


def test_service_worker_source_has_push_handlers():
    path = Path(__file__).parent.parent / "frontend" / "public" / "sw.js"
    text = path.read_text(encoding="utf-8")
    assert '"push"' in text or "'push'" in text
    assert "notificationclick" in text
    assert "showNotification" in text
