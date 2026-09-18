"""
Production-hardening tests: rate limiting, optional API token auth,
and opt-in session persistence.
"""

from pathlib import Path

import pytest

from SweetAstro.src.api.ratelimit import SlidingWindowLimiter
from SweetAstro.src.chat.session import SessionStore


# ---------------------------------------------------------------- rate limiter

def test_sliding_window_limiter():
    now = [0.0]
    limiter = SlidingWindowLimiter(2, window_seconds=60, clock=lambda: now[0])
    assert limiter.allow("a") is True
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False           # third request within window
    assert limiter.allow("b") is True            # other clients unaffected
    now[0] = 61.0
    assert limiter.allow("a") is True            # window slid


def test_retry_after_is_bounded():
    now = [0.0]
    limiter = SlidingWindowLimiter(1, window_seconds=60, clock=lambda: now[0])
    limiter.allow("x")
    assert 0 < limiter.retry_after_seconds("x") <= 60


# ---------------------------------------------------------------- persistence

def test_session_persistence_roundtrip(tmp_path):
    path = tmp_path / "sessions.json"
    store = SessionStore(max_sessions=10, persist_path=path)
    session = store.get_or_create("p1")
    session.add_message("user", "hello")
    session.slots.merge({"dob": "1995-05-15", "place": "Jaipur", "tz_offset_estimate": 5.5})
    session.vastu_layout["rooms"] = {"kitchen": "South-East"}
    session.kundali = {
        "session_id": "p1",
        "birth": {"dob": "1995-05-15", "place": "Jaipur, India", "tz_offset": 5.5},
        "chart": {"ascendant": "Libra 12.34°", "moon_sign": "Leo"},
    }
    session.add_message("assistant", "hi")
    store.save()

    assert path.exists()
    reloaded = SessionStore(max_sessions=10, persist_path=path)
    loaded = reloaded.get("p1")
    assert loaded is not None
    assert [m["role"] for m in loaded.messages] == ["user", "assistant"]
    assert loaded.slots.dob == "1995-05-15"
    assert loaded.slots.place == "Jaipur"
    assert loaded.vastu_layout["rooms"]["kitchen"] == "South-East"
    assert loaded.kundali["birth"]["dob"] == "1995-05-15"
    assert loaded.kundali["chart"]["ascendant"] == "Libra 12.34°"


def test_delete_persists(tmp_path):
    path = tmp_path / "sessions.json"
    store = SessionStore(max_sessions=10, persist_path=path)
    store.get_or_create("gone")
    assert store.delete("gone") is True
    reloaded = SessionStore(max_sessions=10, persist_path=path)
    assert reloaded.get("gone") is None


def test_orchestrator_persists_after_turn(tmp_path):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator

    class _FakeClient:
        def complete_json(self, messages, **kwargs):
            return {}

        def stream(self, messages, **kwargs):
            yield {"type": "content", "text": "Please share your birth details."}

    path = tmp_path / "sessions.json"
    store = SessionStore(max_sessions=10, persist_path=path)
    orch = ChatOrchestrator(client=_FakeClient(), store=store)
    list(orch.handle_message("o1", "hello"))

    reloaded = SessionStore(max_sessions=10, persist_path=path)
    session = reloaded.get("o1")
    assert session is not None
    assert len(session.messages) == 2
    assert session.messages[-1]["role"] == "assistant"


def test_persistence_disabled_by_default(monkeypatch):
    monkeypatch.setattr("SweetAstro.src.chat.session.CHAT_PERSIST", False)
    store = SessionStore(max_sessions=5)
    assert store.persist_path is None
    store.get_or_create("x")
    store.save()  # no-op, must not raise


# ---------------------------------------------------------------- auth middleware

def test_auth_middleware_enforced_when_token_set(monkeypatch):
    from fastapi.testclient import TestClient
    from SweetAstro.src.api import app as app_module

    monkeypatch.setattr(app_module, "API_TOKEN", "secret-token")
    client = TestClient(app_module.app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/chat/config").status_code == 200
    assert client.get("/api/panchanga", params={"date": "2026-09-12"}).status_code == 401

    ok_header = client.get("/api/panchanga", params={"date": "2026-09-12"},
                           headers={"X-Auth-Token": "secret-token"})
    assert ok_header.status_code == 200

    ok_bearer = client.get("/api/panchanga", params={"date": "2026-09-12"},
                           headers={"Authorization": "Bearer secret-token"})
    assert ok_bearer.status_code == 200

    wrong = client.get("/api/panchanga", params={"date": "2026-09-12"},
                       headers={"X-Auth-Token": "nope"})
    assert wrong.status_code == 401


def test_auth_middleware_disabled_without_token(monkeypatch):
    from fastapi.testclient import TestClient
    from SweetAstro.src.api import app as app_module

    monkeypatch.setattr(app_module, "API_TOKEN", "")
    client = TestClient(app_module.app)
    assert client.get("/api/panchanga", params={"date": "2026-09-12"}).status_code == 200


# ---------------------------------------------------------------- rate limit on API

def test_chat_endpoint_rate_limited(monkeypatch):
    from fastapi.testclient import TestClient
    from SweetAstro.src.api import app as app_module, chat_routes
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    class _FakeClient:
        def complete_json(self, messages, **kwargs):
            return {}

        def stream(self, messages, **kwargs):
            yield {"type": "content", "text": "Hello, how can I help?"}

    orchestrator = ChatOrchestrator(client=_FakeClient(), store=SessionStore(max_sessions=5))
    monkeypatch.setattr(chat_routes, "_orchestrator", orchestrator)
    monkeypatch.setattr(chat_routes, "LIMITER", SlidingWindowLimiter(1, window_seconds=60))

    client = TestClient(app_module.app)
    first = client.post("/api/chat", json={"message": "hi"})
    second = client.post("/api/chat", json={"message": "hi again"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert "Rate limit" in second.json()["detail"]
