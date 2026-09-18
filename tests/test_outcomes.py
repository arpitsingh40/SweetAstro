"""Outcome feedback capture tests."""

from pathlib import Path

from SweetAstro.src.chat.extractor import clean_extraction
from SweetAstro.src.chat.orchestrator import ChatOrchestrator
from SweetAstro.src.chat.outcomes import load_outcomes
from SweetAstro.src.chat.session import ChatSession, SessionStore


class FakeDeepSeekClient:
    def __init__(self, extractions=None):
        self.extractions = list(extractions or [])
        self.stream_calls = []
        self.json_calls = []

    def complete_json(self, messages, **kwargs):
        self.json_calls.append(messages)
        return self.extractions.pop(0) if self.extractions else {}

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        yield {"type": "content", "text": "should not stream"}


def _events(orch, session_id, message):
    return list(orch.handle_message(session_id, message))


def test_clean_extraction_accepts_valid_outcome():
    cleaned = clean_extraction({
        "outcome": {"event": "job change", "date": "2026-07",
                    "verdict": "HAPPENED", "note": "new role"},
    })
    assert cleaned["outcome"]["verdict"] == "happened"
    assert cleaned["outcome"]["date"] == "2026-07"
    assert cleaned["outcome"]["event"] == "job change"


def test_clean_extraction_rejects_bad_outcome():
    assert "outcome" not in clean_extraction({"outcome": {"verdict": "maybe"}})
    assert "outcome" not in clean_extraction({"outcome": "junk"})
    cleaned = clean_extraction({"outcome": {"event": "x", "date": "not-a-date",
                                            "verdict": "did_not_happen"}})
    assert cleaned["outcome"]["date"] is None


def test_orchestrator_records_outcome(tmp_path, monkeypatch):
    target = tmp_path / "outcomes.jsonl"
    monkeypatch.setenv("SWEETASTRO_OUTCOMES_PATH", str(target))

    client = FakeDeepSeekClient(extractions=[
        {"outcome": {"event": "promotion", "date": "2026-06", "verdict": "happened"}},
    ])
    orch = ChatOrchestrator(client=client, store=SessionStore())
    events = _events(orch, "out1", "Quick update: the promotion happened in June 2026.")

    done = next(e for e in events if e.type == "done")
    assert "logged" in done.data["content"]
    assert not client.stream_calls

    session = orch.store.get("out1")
    assert len(session.outcomes) == 1
    assert session.outcomes[0]["verdict"] == "happened"

    records = load_outcomes(target)
    assert len(records) == 1
    assert records[0]["session_id"] == "out1"
    assert records[0]["event"] == "promotion"


def test_session_persistence_round_trips_outcomes():
    session = ChatSession(session_id="s1")
    session.outcomes.append({"event": "x", "date": None, "verdict": "partial", "note": ""})
    restored = ChatSession.from_dict(session.to_dict())
    assert restored.outcomes == session.outcomes
