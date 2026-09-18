"""
Confidence-contract tests (user directive, 2026-09-13).

Engine confidence is a single calibrated level: Low, Medium or High. The LLM
must state it exactly once, never as a hybrid range ("Low to Medium"), and the
reason must name the evidence classes instead of "N independent factors agree".
"""

import re

from SweetAstro.src.chat.orchestrator import ChatOrchestrator
from SweetAstro.src.chat.payload import build_chart_payload
from SweetAstro.src.chat.session import SessionStore
from SweetAstro.src.consumer import answer_question
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.evaluation.chat_quality import ChatQualityContext, score_chat_answer
from SweetAstro.src.interpretation.promise import assess_promise
from SweetAstro.src.llm.calibrated_language import (
    hybrid_confidence_labels, normalize_confidence_labels,
)

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30, second=0,
             tz_offset=5.5, lat=28.6139, lon=77.2090)


class _FakeClient:
    def __init__(self, extraction, reply):
        self._extraction = extraction
        self._reply = reply
        self.stream_calls = []

    def complete_json(self, messages, **kwargs):
        return dict(self._extraction)

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        for word in self._reply.split(" "):
            yield {"type": "content", "text": word + " "}


def _payload():
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    return build_chart_payload(
        result, name="Ananya", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="career growth", topic="career",
    )


# ---------------------------------------------------------------------------
# Canonical payload block
# ---------------------------------------------------------------------------

def test_payload_has_single_canonical_confidence_block():
    payload = _payload()
    assert "ASSESSMENT CONFIDENCE (canonical" in payload
    assert payload.count("- Level: ") == 1
    assert "- Basis: " in payload
    # The old duplicated overall line is gone; per-topic evidence stays labelled
    assert "Engine confidence:" not in payload
    assert "topic confidence:" in payload and "topic evidence:" in payload


# ---------------------------------------------------------------------------
# Prompt contract
# ---------------------------------------------------------------------------

def test_prompts_lock_single_canonical_confidence():
    from SweetAstro.src.chat import prompt as P

    assert "state the confidence level exactly once" in P._COMMON_SHAPE_RULES.lower()
    assert "never hybrid ranges" in P._COMMON_SHAPE_RULES.lower()
    for shape in (P.VERDICT_SYSTEM_PROMPT, P.TIMING_SYSTEM_PROMPT, P.ANALYSIS_SYSTEM_PROMPT):
        assert "never a range" in shape.lower()
    assert "state exactly once" in P.ANSWER_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Final-text normalization against the engine level
# ---------------------------------------------------------------------------

def test_normalize_confidence_labels_helper():
    assert normalize_confidence_labels("Confidence: Low to Medium", "Medium") == "Confidence: Medium"
    assert normalize_confidence_labels("High-Medium outlook", "Low") == "Low outlook"
    assert normalize_confidence_labels("Medium/High risk", "High") == "High risk"
    # Unknown canonical level: leave the text untouched
    assert normalize_confidence_labels("Low to Medium", "Unknown") == "Low to Medium"
    assert hybrid_confidence_labels("Low to Medium") == ["Low to Medium"]
    assert hybrid_confidence_labels("plain Low confidence") == []


def test_finalize_normalizes_hybrid_confidence_to_engine_level(monkeypatch):
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (26.9124, 75.7873, "Geocoded (mock) -> Jaipur, India."),
    )
    extraction = {
        "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
        "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
        "question": "When will I get married?", "topic": "marriage",
    }
    client = _FakeClient(extraction, "🔮 Bottom Line\n\nConfidence — Low to Medium: mixed signals.")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = list(orch.handle_message(
        "conf-hybrid", "When will I get married? Born 15 May 1995 at 2:30 pm in Jaipur."))
    done = next(e for e in events if e.type == "done")
    final = done.data["content"]

    payload = client.stream_calls[-1][1]["content"]
    match = re.search(r"ASSESSMENT CONFIDENCE[^\n]*\n- Level:\s*(Low|Medium|High)", payload)
    assert match, "canonical confidence block missing from payload"
    level = match.group(1)

    assert "low to medium" not in final.lower(), "hybrid confidence leaked to the final text"
    assert level in final


# ---------------------------------------------------------------------------
# Rubric flags hybrids
# ---------------------------------------------------------------------------

def test_rubric_flags_hybrid_confidence_labels():
    report = score_chat_answer(
        "Confidence — Low to Medium: mixed signals.",
        context=ChatQualityContext(topic="career"),
    )
    assert any(i.dimension == "calibration" and "hybrid" in i.detail for i in report.issues)


# ---------------------------------------------------------------------------
# Engine-side reason quality
# ---------------------------------------------------------------------------

def test_consumer_confidence_reason_names_evidence_classes():
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    assert result.answer.predictions
    for pred in result.answer.predictions:
        assert "/4 natal evidence checks support" in pred.confidence_reason
        assert "dignity" in pred.confidence_reason  # at least one named class
        assert "independent factors" not in pred.confidence_reason


def test_overall_confidence_basis_has_no_duplicate_parts():
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    parts = [p.strip() for p in result.answer.confidence_reason.split("|")]
    assert len(parts) == len(set(parts)), result.answer.confidence_reason


# ---------------------------------------------------------------------------
# Precision-aware sensitivity (a user-certain time is not punished for chart
# sensitivity measured at a wider window than the stated precision)
# ---------------------------------------------------------------------------

def test_sensitivity_window_follows_stated_precision():
    reliable = answer_question(**BIRTH, question="career growth", time_reliable=True)
    assert reliable.stability is not None
    assert reliable.stability.window_minutes == 5

    uncertain = answer_question(**BIRTH, question="career growth", time_reliable=False)
    assert uncertain.stability is not None
    assert uncertain.stability.window_minutes == 30


def test_user_certain_time_is_not_capped_at_wide_window():
    # This chart is stable at ±5 min (stated precision) but flips at ±30 min;
    # with a user-provided time it must not be capped for the wider window.
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    assert result.stability.lagna_stable is True
    assert "capped at this precision" not in result.answer.confidence_reason
    assert result.answer.confidence in ("Medium", "High")


def test_sensitivity_cap_attributes_cause_to_chart_not_user(monkeypatch):
    from SweetAstro.src.core.time_sensitivity import TimeStability

    unstable = TimeStability(
        window_minutes=5, lagna_stable=False, d9_lagna_stable=False, moon_pada_stable=True,
        summary=("Birth-time stability within ±5 min: the lagna sign changes inside this window — "
                 "the chart sits near a sign boundary, so house-based analysis is capped at this precision."),
    )
    monkeypatch.setattr("SweetAstro.src.consumer.assess_birth_time_stability",
                        lambda *a, **k: unstable)
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    reason = result.answer.confidence_reason
    assert "Sensitivity cap (Medium)" in reason
    assert "chart sensitivity, not doubt about the time provided" in reason
    assert "Verify the birth time" not in reason


def test_promise_statement_reports_factor_counts():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    result = assess_promise(d1, "career")
    assert "supporting /" in result.statement and "limiting factors" in result.statement
    assert "independent" not in result.statement
