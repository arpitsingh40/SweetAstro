"""
Tests for answer-experience improvements:

  1. adaptive depth — lookup answers use the compact prompt, readings the full one
  2. payload verification — invented numbers get a calibration note
  3. birth-basis confirmation — uncertain basis is confirmed before the reading
  4. trivial replies — yes/no/thanks are handled without LLM calls
"""

from SweetAstro.src.chat.config import DEEPSEEK_ANSWER_THINKING
from SweetAstro.src.chat.orchestrator import (
    ChatOrchestrator, _infer_answer_mode, _infer_answer_shape,
)
from SweetAstro.src.chat.prompt import (
    ANSWER_SYSTEM_PROMPT, LOOKUP_SYSTEM_PROMPT, TIMING_SYSTEM_PROMPT,
    VERDICT_SYSTEM_PROMPT,
)
from SweetAstro.src.chat.session import SessionStore
from SweetAstro.src.chat.verify import verify_answer


class FakeDeepSeekClient:
    def __init__(self, extractions=None, reply="🔮 Bottom Line\n\nThe chart suggests steady growth."):
        self.extractions = list(extractions or [])
        self.reply = reply
        self.stream_calls = []
        self.stream_kwargs = []
        self.json_calls = []

    def complete_json(self, messages, **kwargs):
        self.json_calls.append(messages)
        return self.extractions.pop(0) if self.extractions else {}

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        self.stream_kwargs.append(kwargs)
        words = self.reply.split(" ")
        for idx, word in enumerate(words):
            suffix = "" if idx == len(words) - 1 else " "
            yield {"type": "content", "text": word + suffix}


def _events(orch, session_id, message):
    return list(orch.handle_message(session_id, message))


def _patch_geo(monkeypatch):
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (28.6139, 77.2090, "Geocoded (mock)."),
    )


VALID_EXTRACTION = {
    "dob": "1995-05-15", "tob": "14:30", "place": "New Delhi, India",
    "tz_offset": 5.5, "question": "General reading", "topic": "general",
}


# ===========================================================================
# verify_answer unit tests
# ===========================================================================

def test_verify_answer_flags_invented_year_and_degree():
    payload = "Ascendant: Cancer 28.88°\nDasha timeline 2020-01-01 to 2040-12-31"
    violations = verify_answer("This runs to 1856; the ascendant is 888.88°.", payload)
    assert "year 1856" in violations
    assert "degree 888.88°" in violations


def test_verify_answer_accepts_payload_figures():
    payload = "Ascendant: Cancer 28.88°\nDasha timeline 2020-03-01 to 2040-02-28"
    assert verify_answer("Venus dasha runs March 2020 to 2040; ascendant 28.88°.", payload) == []


def test_verify_answer_flags_invented_month_year():
    assert verify_answer("It starts in July 2020.", "Timeline 2020-03-01") == ["period July 2020"]


# ===========================================================================
# adaptive depth
# ===========================================================================

def test_infer_answer_mode_heuristics():
    assert _infer_answer_mode("What is my nakshatra?") == "lookup"
    assert _infer_answer_mode("Which rashi am I in?") == "lookup"
    assert _infer_answer_mode("Tell me my lagna") == "lookup"
    assert _infer_answer_mode("When will I get married?") == "reading"
    assert _infer_answer_mode("Please predict my career") == "reading"


def test_lookup_mode_uses_compact_prompt(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(VALID_EXTRACTION, answer_mode="lookup", question="What is my nakshatra?")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "lookup1", "What is my nakshatra? Born 15 May 1995 14:30 in Delhi.")
    meta = next(e for e in events if e.type == "meta")
    assert meta.data["depth"] == "lookup"
    assert client.stream_calls[-1][0]["content"] == LOOKUP_SYSTEM_PROMPT
    assert client.stream_kwargs[-1].get("max_tokens") == (4096 if DEEPSEEK_ANSWER_THINKING else 700)


def test_infer_answer_shape_heuristics():
    assert _infer_answer_shape("can i become rich in this month?") == "verdict"
    assert _infer_answer_shape("Will I get the job?") == "verdict"
    assert _infer_answer_shape("When will I get married?") == "timing"
    assert _infer_answer_shape("Which year will I buy a house?") == "timing"
    assert _infer_answer_shape("Give me remedies for Saturn") == "remedy"
    assert _infer_answer_shape("What gemstone should I wear?") == "remedy"
    assert _infer_answer_shape("Give me a full detailed reading") == "report"
    assert _infer_answer_shape("go deeper please") == "report"
    assert _infer_answer_shape("Tell me about my career") == "analysis"
    assert _infer_answer_shape("What is my nakshatra?", answer_mode="lookup") == "lookup"


def test_timing_question_uses_timing_prompt(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(VALID_EXTRACTION, question="When will I get married?", topic="marriage")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "reading1", "When will I get married? Born 15 May 1995 14:30 in Delhi.")
    meta = next(e for e in events if e.type == "meta")
    assert meta.data["depth"] == "reading"
    assert meta.data["shape"] == "timing"
    assert client.stream_calls[-1][0]["content"] == TIMING_SYSTEM_PROMPT
    # Reasoning ON needs a bigger completion budget so thinking cannot consume
    # the whole window and leave the answer empty.
    expected_budget = 4096 if DEEPSEEK_ANSWER_THINKING else 900
    assert client.stream_kwargs[-1].get("max_tokens") == expected_budget
    assert client.stream_kwargs[-1].get("thinking") is DEEPSEEK_ANSWER_THINKING


def test_verdict_question_uses_verdict_prompt(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(VALID_EXTRACTION, question="Can I become rich this month?", topic="wealth")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "verdict1", "Can I become rich this month? Born 15 May 1995 14:30 in Delhi.")
    done = next(e for e in events if e.type == "done")
    assert done.data.get("shape") == "verdict"
    assert client.stream_calls[-1][0]["content"] == VERDICT_SYSTEM_PROMPT


def test_explicit_report_keeps_full_prompt(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(VALID_EXTRACTION, question="Give me a full detailed reading", topic="general")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "report1", "Give me the full detailed reading. Born 15 May 1995 14:30 in Delhi.")
    done = next(e for e in events if e.type == "done")
    assert done.data.get("shape") == "report"
    assert client.stream_calls[-1][0]["content"] == ANSWER_SYSTEM_PROMPT
    assert "max_tokens" not in client.stream_kwargs[-1]


# ===========================================================================
# payload verification wiring
# ===========================================================================

def test_invented_figure_gets_calibration_note(monkeypatch):
    _patch_geo(monkeypatch)
    client = FakeDeepSeekClient(extractions=[dict(VALID_EXTRACTION)], reply="Your breakthrough comes in 1856.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "verify1", "Tell me about my career. Born 15 May 1995 14:30 in Delhi.")
    done = next(e for e in events if e.type == "done")
    assert "could not be cross-checked" in done.data["content"]


# ===========================================================================
# panchanga lookup
# ===========================================================================

def test_panchanga_lookup_bypasses_muhurta(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = {"place": "New Delhi, India", "tz_offset": 5.5, "answer_mode": "lookup"}
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "panch1", "What is the panchang today?")
    meta = next(e for e in events if e.type == "meta")
    assert meta.data["mode"] == "panchanga"
    assert meta.data["depth"] == "lookup"
    assert client.stream_calls[-1][0]["content"] == LOOKUP_SYSTEM_PROMPT
    assert "VERIFIED PANCHANGA" in client.stream_calls[-1][1]["content"]
    done = next(e for e in events if e.type == "done")
    assert done.data["mode"] == "panchanga"


# ===========================================================================
# birth-basis confirmation
# ===========================================================================

def _unknown_time_extraction():
    return {
        "dob": "1995-05-15", "tob_unknown": True, "place": "New Delhi, India",
        "tz_offset": 5.5, "question": "How is my career?", "topic": "career",
    }


def test_confirmation_gate_blocks_first_reading(monkeypatch):
    _patch_geo(monkeypatch)
    client = FakeDeepSeekClient(extractions=[_unknown_time_extraction()])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    first = _events(orch, "confirm1", "I don't know my birth time. Born 15 May 1995 in Delhi.")
    done = next(e for e in first if e.type == "done")
    assert done.data.get("confirmation_required") is True
    assert not client.stream_calls

    session = orch.store.get("confirm1")
    assert session.awaiting_confirmation is True

    second = _events(orch, "confirm1", "yes")
    assert "meta" in [e.type for e in second]
    payload_system = client.stream_calls[-1][1]["content"]
    assert "UNCERTAIN" in payload_system
    assert len(client.json_calls) == 1  # extraction skipped on the "yes" turn


def test_lookup_mode_survives_confirmation_turn(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(_unknown_time_extraction(), answer_mode="lookup",
                      question="What is my nakshatra?")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    first = _events(orch, "confirm4",
                    "What is my nakshatra? I don't know my birth time. Born 15 May 1995 in Delhi.")
    assert next(e for e in first if e.type == "done").data.get("confirmation_required") is True
    assert not client.stream_calls

    _events(orch, "confirm4", "yes")
    assert client.stream_calls[-1][0]["content"] == LOOKUP_SYSTEM_PROMPT
    assert client.stream_kwargs[-1].get("max_tokens") == (4096 if DEEPSEEK_ANSWER_THINKING else 700)


def test_confirmation_no_asks_for_correction(monkeypatch):
    _patch_geo(monkeypatch)
    client = FakeDeepSeekClient(extractions=[_unknown_time_extraction()])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    _events(orch, "confirm2", "I don't know my birth time. Born 15 May 1995 in Delhi.")
    before = len(client.stream_calls)
    events = _events(orch, "confirm2", "no")
    done = next(e for e in events if e.type == "done")
    assert "correct" in done.data["content"].lower()
    assert len(client.stream_calls) == before
    assert orch.store.get("confirm2").awaiting_confirmation is False


def test_reliable_basis_skips_confirmation(monkeypatch):
    _patch_geo(monkeypatch)
    client = FakeDeepSeekClient(extractions=[dict(VALID_EXTRACTION)])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "confirm3", "Full reading please. Born 15 May 1995 14:30 in Delhi.")
    done = next(e for e in events if e.type == "done")
    assert done.data.get("confirmation_required") is None
    assert client.stream_calls


# ===========================================================================
# trivial replies
# ===========================================================================

def test_thanks_is_canned_without_llm(monkeypatch):
    _patch_geo(monkeypatch)
    client = FakeDeepSeekClient(extractions=[dict(VALID_EXTRACTION)])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "thanks1", "thanks")
    done = next(e for e in events if e.type == "done")
    # Report voice: no "You're welcome" companion phrasing
    assert "noted" in done.data["content"].lower()
    assert "welcome" not in done.data["content"].lower()
    assert not client.stream_calls
    assert not client.json_calls


def test_reply_language_directive_and_sanitization(monkeypatch):
    _patch_geo(monkeypatch)
    client = FakeDeepSeekClient(extractions=[dict(VALID_EXTRACTION)])
    orch = ChatOrchestrator(client=client, store=SessionStore())
    list(orch.handle_message(
        "lang1", "Tell me about my career. Born 15 May 1995 14:30 in Delhi.", language="Hindi"))
    messages = client.stream_calls[-1]
    assert any(m["role"] == "system" and "Reply in Hindi" in m["content"] for m in messages)
    assert orch.store.get("lang1").reply_language == "Hindi"

    client2 = FakeDeepSeekClient(extractions=[dict(VALID_EXTRACTION)])
    orch2 = ChatOrchestrator(client=client2, store=SessionStore())
    list(orch2.handle_message(
        "lang2", "Career? Born 15 May 1995 14:30 in Delhi.",
        language="<script>alert(1)</script>"))
    assert orch2.store.get("lang2").reply_language is None


def test_muhurta_turn_does_not_enter_chart_confirmation(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = {
        "place": "New Delhi, India", "tz_offset_estimate": 5.5,
        "muhurta_event": "general",
        "muhurta_start": "2026-09-12", "muhurta_end": "2026-09-16",
    }
    client = FakeDeepSeekClient(extractions=[extraction], reply="🗓️ Best Dates\n\nWindows.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "mh1", "Find an auspicious day for a launch next week.")
    done = next(e for e in events if e.type == "done")
    assert done.data.get("mode") == "muhurta"
    session = orch.store.get("mh1")
    assert session.awaiting_confirmation is False
    assert session.pending_answer_mode is None
    assert session.pending_answer_shape is None


def test_deep_mode_includes_all_planet_dossier(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(VALID_EXTRACTION, question="Give me a deep mode reading", topic="wealth")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "deep1", "Give me a deep mode reading. Born 15 May 1995 14:30 in Delhi.")
    done = next(e for e in events if e.type == "done")
    assert done.data.get("shape") == "report"
    payload = client.stream_calls[-1][1]["content"]
    assert "Deep node dossier" in payload
    assert "deep mode: all seven physical grahas" in payload


def test_normal_reading_has_no_deep_dossier(monkeypatch):
    _patch_geo(monkeypatch)
    extraction = dict(VALID_EXTRACTION, question="When will I get married?", topic="marriage")
    client = FakeDeepSeekClient(extractions=[extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    _events(orch, "deep2", "When will I get married? Born 15 May 1995 14:30 in Delhi.")
    payload = client.stream_calls[-1][1]["content"]
    assert "Deep node dossier" not in payload
