"""
Rectification assist tests — deterministic candidate-time ranking, no LLM.
"""

import pytest
from fastapi.testclient import TestClient

from SweetAstro.src.api.app import app
from SweetAstro.src.chat.orchestrator import ChatOrchestrator
from SweetAstro.src.chat.session import SessionStore
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.prediction.rectify import (
    _topic_context, dasha_relevance, rectify_birth_time,
)

client = TestClient(app)

BIRTH = dict(year=1995, month=5, day=15, tz_offset=5.5, lat=28.6139, lon=77.2090)
EVENTS = [
    {"event": "job change", "date": "2019-06"},
    {"event": "relocation", "date": "2022-02"},
]


def test_dasha_relevance_scores_topic_lords_and_unrelated_planets():
    d1 = calculate_d1_chart(1995, 5, 15, 12, 0, 0, 5.5, 28.6139, 77.2090)
    houses, relevant_lords, significators = _topic_context(d1, "career")
    scores = {
        planet: dasha_relevance(planet, d1, houses, relevant_lords, significators)
        for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
    }
    assert max(scores.values()) > 0, "topic lords/significators must score"
    assert any(score == 0 for score in scores.values()), "unrelated planets must score 0"


def test_rectify_requires_two_dated_events():
    with pytest.raises(ValueError, match="At least 2"):
        rectify_birth_time(**BIRTH, events=[{"event": "job", "date": "2019-06"}], topic="career")
    with pytest.raises(ValueError, match="At least 2"):
        rectify_birth_time(**BIRTH, events=[{"event": "job", "date": "garbage"}], topic="career")


def test_rectify_is_deterministic_and_returns_ranked_windows():
    first = rectify_birth_time(**BIRTH, events=EVENTS, topic="career")
    second = rectify_birth_time(**BIRTH, events=EVENTS, topic="career")
    assert first.to_dict() == second.to_dict()
    assert len(first.candidates) == 144  # 24h at 10-minute steps
    assert first.best_windows, "expected at least one best-fit window"
    assert first.event_count == 2

    ranked = first.to_dict()["ranked"]
    assert ranked[0]["events_matched"] >= ranked[-1]["events_matched"]
    assert ranked[0]["score"] >= ranked[-1]["score"]


def test_rectify_api_returns_assist_and_rejects_thin_events():
    response = client.post("/api/rectify", json={
        "dob": "1995-05-15", "tz_offset": 5.5, "lat": 28.6139, "lon": 77.209,
        "topic": "career", "events": EVENTS,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["best_windows"]
    assert body["result"]["event_count"] == 2
    assert body["result"]["ranked"]

    bad = client.post("/api/rectify", json={
        "dob": "1995-05-15", "tz_offset": 5.5, "lat": 28.6139, "lon": 77.209,
        "events": [],
    })
    assert bad.status_code == 400


class FakeDeepSeekClient:
    def __init__(self, extractions=None, reply="🕰️ Best-Fit Windows\n\nTwo candidate windows."):
        self.extractions = list(extractions or [])
        self.reply = reply
        self.stream_calls = []

    def complete_json(self, messages, **kwargs):
        return self.extractions.pop(0) if self.extractions else {}

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        words = self.reply.split(" ")
        for idx, word in enumerate(words):
            yield {"type": "content", "text": word + ("" if idx == len(words) - 1 else " ")}


def test_chat_rectification_flow(monkeypatch):
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (28.6139, 77.2090, "Geocoded (mock)."),
    )
    extraction = {
        "name": "Ananya", "dob": "1995-05-15", "tob_unknown": True,
        "place": "New Delhi, India", "tz_offset_estimate": 5.5,
        "topic": "career", "rectify_request": True,
        "historical_events": EVENTS,
    }
    fake = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=fake, store=SessionStore())

    events = list(orch.handle_message(
        "r1", "I don't know my birth time — find it from my job and relocation dates"))
    meta = next(event for event in events if event.type == "meta")
    assert meta.data["mode"] == "rectification"
    assert meta.data["birth_data"]["best_windows"]

    payload = fake.stream_calls[-1][1]["content"]
    assert payload.startswith("=== VERIFIED RECTIFICATION ASSIST")
    assert "NOT a verified birth time" in payload

    done = next(event for event in events if event.type == "done")
    assert done.data["mode"] == "rectification"
