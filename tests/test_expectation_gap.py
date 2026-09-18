"""
Expectation-gap tests (user directive, 2026-09-13).

When the engine cannot meet the user's expectation it must say so plainly,
deliver the closest truthful reading, and never let the reply drift past the
capability. These tests lock the assessment, the payload contract, and the
deterministic delivery correction.
"""

from types import SimpleNamespace

from SweetAstro.src.chat.expectation import (
    assess_capability, assessment_block, assessment_verdict_from_payload,
    timing_claim_detected,
)
from SweetAstro.src.chat.orchestrator import ChatOrchestrator
from SweetAstro.src.chat.payload import build_chart_payload
from SweetAstro.src.chat.session import SessionStore
from SweetAstro.src.consumer import answer_question

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30, second=0,
             tz_offset=5.5, lat=28.6139, lon=77.2090)


class _NullClient:
    def complete_json(self, messages, **kwargs):
        return {}

    def stream(self, messages, **kwargs):
        return iter(())


def _promise(topic="marriage", timing_ok=True):
    return SimpleNamespace(topic=topic, timing_reliable=timing_ok)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

def test_normal_question_is_full_capability():
    a = assess_capability("How is my career?", "analysis", _promise("career"), True)
    assert a.verdict == "full"
    assert a.limits == []


def test_exact_date_request_is_partial():
    a = assess_capability("Tell me the exact date of my marriage", "timing",
                          _promise(), True)
    assert a.verdict == "partial"
    assert any("exact" in limit for limit in a.limits)
    assert any("window" in item for item in a.deliverable)


def test_weak_promise_timing_is_blocked():
    a = assess_capability("When will I get married?", "timing",
                          _promise(timing_ok=False), True)
    assert a.verdict == "blocked"
    assert a.timing_blocked
    assert any("strengthen" in item for item in a.unlock)


def test_unknown_birth_time_is_partial_with_unlock():
    a = assess_capability("How is my career?", "analysis", _promise("career"), False)
    assert a.verdict == "partial"
    assert any("birth time is uncertain" in limit for limit in a.limits)
    assert any("verified birth time" in item for item in a.unlock)


def test_past_event_question_is_blocked():
    a = assess_capability("When did he get married?", "timing", _promise(), True)
    assert a.verdict == "blocked"
    assert any("past event" in limit for limit in a.limits)
    assert any("actual event date" in item for item in a.unlock)


# ---------------------------------------------------------------------------
# Payload contract
# ---------------------------------------------------------------------------

def test_assessment_block_round_trips_and_requires_opening():
    a = assess_capability("When did he get married?", "timing", _promise(), True)
    block = assessment_block(a)
    payload = "X\n" + block + "\nY"
    assert assessment_verdict_from_payload(payload) == "blocked"
    assert "- Asked:" in block and "- Deliverable:" in block
    assert "Required opening" in block

    full = assessment_block(assess_capability("How is my career?", "analysis",
                                              _promise("career"), True))
    assert "Required opening" not in full
    assert assessment_verdict_from_payload("X\n" + full) == "full"


def test_build_chart_payload_includes_expectation_block():
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    payload = build_chart_payload(
        result, name="A", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="career growth", topic="career",
        expectation_block="EXPECTATION-CAPABILITY ASSESSMENT (plan)\n- Asked: a\n- Verdict: full",
    )
    assert "EXPECTATION-CAPABILITY ASSESSMENT" in payload
    assert assessment_verdict_from_payload(payload) == "full"


def test_prompts_require_expectation_first():
    from SweetAstro.src.chat import prompt as P

    assert "expectation first" in P._COMMON_SHAPE_RULES.lower()
    assert "expectation first" in P.ANSWER_SYSTEM_PROMPT.lower()
    assert "expectation-capability assessment" in P.ANSWER_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Delivery check
# ---------------------------------------------------------------------------

def test_timing_claim_detection_is_specific():
    assert timing_claim_detected("Marriage in March 2028") is True
    assert timing_claim_detected("around Q2 2027") is True
    assert timing_claim_detected("between 2027-2029") is True
    assert timing_claim_detected("current dasha is Venus") is False
    assert timing_claim_detected("as of 2026 the dasha is Venus") is False


def test_finalize_corrects_reply_that_drifted_past_blocked_timing():
    orch = ChatOrchestrator(client=_NullClient(), store=SessionStore())
    session = orch.store.get_or_create("gap1")
    session.slots.question = "When will I get married?"
    payload = (
        "=== VERIFIED CHART DATA ===\n"
        "EXPECTATION-CAPABILITY ASSESSMENT (plan the reply around this):\n"
        "- Asked: an event-timing window\n"
        "- Verdict: blocked\n"
        "- Deliverable: natal promise and limiting factors\n"
        "- Cannot deliver: timing is withheld because the natal promise for marriage is weak\n"
        "=== END VERIFIED CHART DATA ==="
    )
    drifted = orch._finalize("Marriage will happen in March 2028.", payload, session)
    assert "Correction: timing is withheld" in drifted

    compliant = orch._finalize(
        "The natal promise is weak, so timing is withheld; work on the limiting factors.",
        payload, session)
    assert "Correction" not in compliant


def test_finalize_does_not_touch_non_blocked_payloads():
    orch = ChatOrchestrator(client=_NullClient(), store=SessionStore())
    session = orch.store.get_or_create("gap2")
    session.slots.question = "How is my career?"
    payload = ("=== VERIFIED CHART DATA ===\n"
               "EXPECTATION-CAPABILITY ASSESSMENT (plan):\n- Asked: reading\n- Verdict: full\n"
               "=== END VERIFIED CHART DATA ===")
    final = orch._finalize("A steady period is indicated around March 2028.", payload, session)
    assert "Correction" not in final
