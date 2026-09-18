"""Long-term memory tests: fingerprint, upsert dedup, persistence, schema, API."""

import json
from pathlib import Path

import jsonschema

from SweetAstro.src.chat.memory import (
    MEMORY_SCHEMA_VERSION, MemoryStore, birth_fingerprint, profile_id_for,
)
from SweetAstro.src.chat.session import ChatSession, SessionStore

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "memory_schema.json"


def _kundali(dob="1995-05-15", tob="14:30:00", name="Ananya"):
    return {
        "birth": {
            "name": name, "dob": dob, "tob": tob, "tob_unknown": False,
            "place": "Jaipur, Rajasthan, India", "place_query": "Jaipur",
            "lat": 26.9124, "lon": 75.7873, "tz_offset": 5.5, "tz_estimated": False,
        },
        "chart": {
            "ayanamsha": "Lahiri (Chitrapaksha)", "ascendant": "Libra 12.34°",
            "moon_sign": "Leo", "moon_nakshatra": "Purva Phalguni",
            "moon_nakshatra_pada": 2, "dasha": "Sun MD / Moon AD / Venus PD",
            "vargas": ["D1", "D9", "D10"],
        },
    }


def _session(session_id, kundali):
    session = ChatSession(session_id=session_id)
    session.kundali = kundali
    return session


class _FakeClient:
    """Stub LLM: fixed extraction queue, streamed canned reply, call capture."""

    def __init__(self, extractions, reply="Answer."):
        self._extractions = list(extractions)
        self._reply = reply
        self.stream_calls = []

    def complete_json(self, messages, **kwargs):
        return self._extractions.pop(0) if self._extractions else {}

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        for word in self._reply.split(" "):
            yield {"type": "content", "text": word + " "}


# --------------------------------------------------------------------- hashing

def test_fingerprint_is_name_independent_and_birth_sensitive():
    a = birth_fingerprint({"dob": "1995-05-15", "tob": "14:30:00", "lat": 26.9124, "lon": 75.7873, "tz_offset": 5.5})
    b = birth_fingerprint({"dob": "1995-05-15", "tob": "14:30:00", "lat": 26.9124, "lon": 75.7873, "tz_offset": 5.5})
    assert a == b and len(a) == 64
    assert profile_id_for(a).startswith("prof_")

    changed = birth_fingerprint({"dob": "1995-05-16", "tob": "14:30:00", "lat": 26.9124, "lon": 75.7873, "tz_offset": 5.5})
    assert changed != a

    unknown = birth_fingerprint({"dob": "1995-05-15", "tob_unknown": True, "lat": 26.9124, "lon": 75.7873})
    assert unknown != a


# ----------------------------------------------------------------------- store

def test_upsert_deduplicates_by_birth_and_links_sessions():
    store = MemoryStore()
    pid1 = store.upsert_from_session(_session("chat-1", _kundali()))
    pid2 = store.upsert_from_session(_session("chat-2", _kundali(tob="14:30:00", name="Ananya S.")))
    assert pid1 == pid2
    assert store.count() == 1

    profile = store.get(pid1)
    assert profile["sessions"] == ["chat-1", "chat-2"]
    assert profile["kundali"]["moon_nakshatra"] == "Purva Phalguni"

    other = store.upsert_from_session(_session("chat-3", _kundali(dob="1990-01-01")))
    assert other != pid1
    assert store.count() == 2


def test_upsert_ignores_sessions_without_kundali():
    store = MemoryStore()
    session = ChatSession(session_id="no-chart")
    assert store.upsert_from_session(session) is None
    assert store.count() == 0


def test_memory_persists_and_reloads(tmp_path):
    path = tmp_path / "memory.json"
    store = MemoryStore(path)
    pid = store.upsert_from_session(_session("chat-1", _kundali()))
    assert path.exists()

    reloaded = MemoryStore(path)
    assert reloaded.count() == 1
    profile = reloaded.get(pid)
    assert profile["birth"]["dob"] == "1995-05-15"
    assert profile["sessions"] == ["chat-1"]


def test_memory_document_matches_json_schema(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    store.upsert_from_session(_session("chat-1", _kundali()))
    document = store.to_document()
    assert document["schema_version"] == MEMORY_SCHEMA_VERSION

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(document, schema, format_checker=jsonschema.FormatChecker())


# ------------------------------------------------------------------ orchestrator

def test_orchestrator_creates_profile_after_full_flow(monkeypatch, tmp_path):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator

    _geocode(monkeypatch)
    store = SessionStore(max_sessions=10, persist_path=tmp_path / "sessions.json")
    orch = ChatOrchestrator(client=_FakeClient([{
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "question": "When will I get married?", "topic": "marriage",
    }]), store=store)

    assert orch.memory is not None
    list(orch.handle_message("m1", "When will I get married? Born 15 May 1995 14:30 in Jaipur."))

    assert orch.memory.count() == 1
    profiles = orch.memory.list_profiles()
    assert profiles[0]["session_count"] == 1
    assert profiles[0]["place"] == "Jaipur, Rajasthan, India"
    assert (tmp_path / "memory.json").exists()


# ------------------------------------------------------------------------- API

def test_memory_api_endpoints(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from SweetAstro.src.api import chat_routes
    from SweetAstro.src.api.app import app
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator

    memory = MemoryStore(tmp_path / "memory.json")
    memory.upsert_from_session(_session("api-1", _kundali()))
    orch = ChatOrchestrator(store=SessionStore(), memory=memory)
    monkeypatch.setattr(chat_routes, "_orchestrator", orch)

    api = TestClient(app)
    listing = api.get("/api/chat/memory")
    assert listing.status_code == 200
    body = listing.json()
    assert body["enabled"] is True
    assert len(body["profiles"]) == 1

    profile_id = body["profiles"][0]["profile_id"]
    detail = api.get(f"/api/chat/memory/{profile_id}")
    assert detail.status_code == 200
    assert detail.json()["kundali"]["moon_sign"] == "Leo"
    assert api.get("/api/chat/memory/prof_missing").status_code == 404


# --------------------------------------------------------------------- recall

def test_find_by_dob_place_and_find_matching():
    store = MemoryStore()
    pid = store.upsert_from_session(_session("s1", _kundali()))

    assert store.find_by_dob_place("1995-05-15", "Jaipur, India")["profile_id"] == pid
    assert store.find_by_dob_place("1995-05-15", "Jaipur")["profile_id"] == pid
    assert store.find_by_dob_place("1994-01-01", "Jaipur") is None
    assert store.find_by_dob_place("1995-05-15", "Mumbai") is None

    assert store.find_matching("1995-05-15", "14:30:00", False, 26.9124, 75.7873, 5.5) is not None
    assert store.find_matching("1995-05-15", "14:31:00", False, 26.9124, 75.7873, 5.5) is None


def _geocode(monkeypatch):
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (26.9124, 75.7873, "Geocoded (mock) -> Jaipur, India."),
    )


def test_new_chat_recalls_saved_birth_time(monkeypatch, tmp_path):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator

    _geocode(monkeypatch)
    store = SessionStore(max_sessions=10, persist_path=tmp_path / "sessions.json")
    client = _FakeClient([
        {"name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
         "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
         "question": "When will I get married?", "topic": "marriage"},
        {"name": "Ananya", "dob": "1995-05-15",
         "place": "Jaipur, India",
         "question": "How is my career?", "topic": "career"},
    ])
    orch = ChatOrchestrator(client=client, store=store)

    list(orch.handle_message("r1", "Marriage? Born 1995-05-15 14:30 in Jaipur."))
    assert orch.memory.count() == 1

    events = list(orch.handle_message("r2", "Career? Born 1995-05-15 in Jaipur."))
    types = [e.type for e in events]
    assert "meta" in types and "done" in types   # no guide turn asking for time

    session2 = orch.store.get("r2")
    assert session2.slots.tob == "14:30:00"
    recalled = session2.recalled_profile
    assert recalled is not None and recalled["used_saved_time"] is True
    assert recalled["session_count"] == 1
    assert recalled["last_question"].startswith("Marriage? ")

    payload = client.stream_calls[-1][1]["content"]
    assert "Returning native" in payload
    assert "recalled from that saved profile" in payload


def test_explicit_unknown_time_is_not_overridden(monkeypatch, tmp_path):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator

    _geocode(monkeypatch)
    store = SessionStore(max_sessions=10, persist_path=tmp_path / "sessions.json")
    client = _FakeClient([
        {"name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
         "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
         "question": "Marriage?", "topic": "marriage"},
        {"dob": "1995-05-15", "tob_unknown": True,
         "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
         "question": "Career?", "topic": "career"},
    ])
    orch = ChatOrchestrator(client=client, store=store)

    list(orch.handle_message("u1", "Marriage? Born 1995-05-15 14:30 in Jaipur."))
    list(orch.handle_message("u2", "I don't know my birth time. Career? Born 1995-05-15 in Jaipur."))

    session2 = orch.store.get("u2")
    assert session2.slots.tob is None              # explicit unknown respected
    assert session2.slots.tob_unknown is True
    recalled = session2.recalled_profile
    assert recalled is not None and recalled["used_saved_time"] is False
