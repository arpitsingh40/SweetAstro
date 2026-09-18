"""
Compatibility (Kundli Milan) + multi-subject chat tests.

All LLM calls are mocked — the deterministic engine (charts, kutas) is real.
"""

from SweetAstro.src.chat.extractor import clean_extraction
from SweetAstro.src.chat.orchestrator import ChatOrchestrator
from SweetAstro.src.chat.session import BirthSlots, SessionStore, merge_prefixed


class FakeDeepSeekClient:
    def __init__(self, extractions=None, reply="🔮 Bottom Line\n\nThe kutas are mixed."):
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


def _events(orch, session_id, message):
    return list(orch.handle_message(session_id, message))


def _types(events):
    return [event.type for event in events]


def _mock_geocode(monkeypatch):
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (26.9124, 75.7873, "Geocoded (mock) -> Jaipur, India."),
    )


# ===========================================================================
# Extraction validation
# ===========================================================================

def test_clean_extraction_validates_partner_fields():
    cleaned = clean_extraction({
        "dob": "1995-05-15", "place": "Jaipur",
        "partner_name": "Rohit", "partner_dob": "1993-11-02",
        "partner_tob": "6:15 am", "partner_place": "Mumbai, India",
        "partner_tz_offset_estimate": 5.5, "compatibility_request": True,
    })
    assert cleaned["partner_name"] == "Rohit"
    assert cleaned["partner_dob"] == "1993-11-02"
    assert cleaned["partner_tob"] == "06:15:00"
    assert cleaned["partner_tz_offset_estimate"] == 5.5
    assert cleaned["compatibility_request"] is True


def test_clean_extraction_drops_invalid_partner_fields():
    cleaned = clean_extraction({
        "partner_dob": "not-a-date",
        "partner_tz_offset": 99.0,
        "partner_tob_unknown": "yes",       # not a bool -> ignored
        "compatibility_request": "yes",     # not a bool -> ignored
    })
    assert "partner_dob" not in cleaned
    assert "partner_tz_offset" not in cleaned
    assert "partner_tob_unknown" not in cleaned
    assert "compatibility_request" not in cleaned


def test_clean_extraction_validates_subjects():
    cleaned = clean_extraction({
        "subjects": [
            {"role": "child", "name": "Arjun", "dob": "2018-03-04", "place": "Jaipur"},
            {"role": "pet", "dob": "2020-01-01"},   # invalid role
            {"role": "parent", "name": ""},         # no usable data
        ]
    })
    assert len(cleaned["subjects"]) == 1
    assert cleaned["subjects"][0]["role"] == "child"
    assert cleaned["subjects"][0]["name"] == "Arjun"


def test_merge_prefixed_fills_partner_slots():
    person = BirthSlots()
    changed = merge_prefixed(
        person, {"partner_dob": "1993-11-02", "partner_place": "Mumbai, India"}, "partner_")
    assert "dob" in changed and "place" in changed
    assert person.dob == "1993-11-02"
    assert person.place == "Mumbai, India"


# ===========================================================================
# Orchestrator flows
# ===========================================================================

def test_compatibility_flow_asks_for_partner_details(monkeypatch):
    _mock_geocode(monkeypatch)
    extraction = {
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "topic": "compatibility", "compatibility_request": True,
        "question": "Are we compatible?",
    }
    client = FakeDeepSeekClient(extractions=[extraction],
                                reply="Please share the other person's birth details.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "c1", "Kundli milan for me and my partner?")
    assert "meta" not in _types(events)
    assert "done" in _types(events)
    guide = client.stream_calls[0][0]["content"]
    assert "other person's birth details" in guide.lower()

    session = orch.store.get("c1")
    assert "partner" in session.last_missing


def test_compatibility_flow_computes_kutas(monkeypatch):
    _mock_geocode(monkeypatch)
    extraction = {
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "partner_name": "Rohit", "partner_dob": "1993-11-02", "partner_tob": "06:15:00",
        "partner_place": "Mumbai, India", "partner_tz_offset": 5.5,
        "topic": "compatibility", "compatibility_request": True,
        "question": "Are we compatible?",
    }
    client = FakeDeepSeekClient(extractions=[extraction],
                                reply="🔮 Bottom Line\n\nTraditional score noted.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "c2", "Check our kundli milan")
    meta = next(event for event in events if event.type == "meta")
    card = meta.data["birth_data"]
    assert card["mode"] == "compatibility"
    assert card["person_a"]["name"] == "Ananya"
    assert card["person_b"]["name"] == "Rohit"
    assert 0 <= card["total"] <= card["max_total"] == 36
    assert len(card["kutas"]) == 8

    payload = client.stream_calls[-1][1]["content"]
    assert payload.startswith("=== VERIFIED KUNDLI MILAN")
    assert "Ashtakoota" in payload
    assert "Mangal dosha" in payload

    done = next(event for event in events if event.type == "done")
    assert done.data["mode"] == "compatibility"


def test_compatibility_partner_unknown_time_is_flagged(monkeypatch):
    _mock_geocode(monkeypatch)
    extraction = {
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "partner_name": "Rohit", "partner_dob": "1993-11-02", "partner_tob_unknown": True,
        "partner_place": "Mumbai, India", "partner_tz_offset": 5.5,
        "topic": "compatibility", "compatibility_request": True,
    }
    client = FakeDeepSeekClient(extractions=[extraction], reply="🔮 Bottom Line\n\nDone.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "c3", "Kundli milan?")
    assert "meta" in _types(events)
    payload = client.stream_calls[-1][1]["content"]
    assert "birth time unavailable (noon used)" in payload


def test_subject_chart_flow_uses_second_person(monkeypatch):
    _mock_geocode(monkeypatch)
    first = {
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "topic": "career", "question": "How is my career?",
    }
    client = FakeDeepSeekClient(extractions=[first], reply="Your career reading.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    _events(orch, "s4", "How is my career? Born 15 May 1995 2:30 pm in Jaipur")
    second = {
        "subjects": [{
            "role": "child", "name": "Arjun", "dob": "2018-03-04", "tob": "09:00:00",
            "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        }],
        "topic": "career", "question": "How will my son's career be?",
    }
    client.extractions.append(second)
    events = _events(orch, "s4", "How will my son's career be?")

    assert "meta" in _types(events)
    payload = client.stream_calls[-1][1]["content"]
    assert "Subject:" in payload
    assert "their child" in payload
    assert "NOT the user" in payload
    assert "arjun" in payload.lower()

    session = orch.store.get("s4")
    assert session.active_subject in session.people
    assert session.people[session.active_subject].dob == "2018-03-04"


def test_personality_topic_flows_to_payload(monkeypatch):
    _mock_geocode(monkeypatch)
    extraction = {
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "topic": "personality", "question": "What is my nature and strengths?",
        "answer_shape": "analysis",
    }
    client = FakeDeepSeekClient(extractions=[extraction], reply="Your nature, per the chart:")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "p1", "Tell me about my nature and strengths")
    assert "meta" in _types(events)
    payload = client.stream_calls[-1][1]["content"]
    assert "Detected topic: personality" in payload
