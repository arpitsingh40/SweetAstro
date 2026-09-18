"""
Regression tests for audit round 3 (2026-09-12):

17. Safety gate substring false positives: "harmony" (harm), "skills" (kill),
    "never harm", and negated guarantees ("no guarantees are made") were all
    blocking remedies; "will I be rich?" added a HEALTH referral because "ill"
    matched inside "will".
18. Legacy answer engine hard-coded "Strong" factor strengths and tested
    `"7" in dasha_summary` (always False) — misleading internal payload.
19. Interpretation layer audit: dead constant removed; behavior locked with
    tests (timing separation + confidence calibration thresholds).
"""

from datetime import datetime

import pytest

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline
from SweetAstro.src.interpretation.dasha_timing import read_timing
from SweetAstro.src.interpretation.prediction_logic import calibrate_confidence
from SweetAstro.src.remedies.safety import safety_check


# ---------------------------------------------------------------------------
# Bug 17 — safety gate word boundaries and negation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texts", [
    ["Bring harmony to the home"],
    ["Develop technology skills and systems"],
    ["Animal welfare: only kindness, never harm any creature"],
    ["No guarantees are made; this practice is optional"],
    ["This is not guaranteed and remains optional"],
    ["Use skills to build harmony"],
])
def test_safe_texts_are_not_blocked(texts):
    verdict = safety_check("general", texts)
    assert verdict.allowed is True, verdict.reasons


@pytest.mark.parametrize("texts", [
    ["Stop prescribed medication and rely on this"],
    ["This will guarantee wealth"],
    ["You are guaranteed success"],
    ["The expensive gemstone is necessary"],
    ["Dispose in river to remove the affliction"],
    ["Harm the neighbour's property"],
    ["Threaten the opposing party"],
])
def test_unsafe_texts_are_blocked(texts):
    verdict = safety_check("general", texts)
    assert verdict.allowed is False


def test_referrals_no_ill_substring_false_positive():
    verdict = safety_check("will I be rich and successful?", ["budget discipline"])
    assert not any("doctor" in r.lower() for r in verdict.referrals), \
        "'ill' must not match inside 'will'"
    assert verdict.referrals == []  # finance referral retired by product decision


def test_referrals_for_health_legal_crisis():
    health = safety_check("health disease and anxiety", ["gentle routine"])
    assert any("doctor" in r.lower() for r in health.referrals)
    legal = safety_check("divorce and custody case", ["calm conduct"])
    assert any("lawyer" in r.lower() for r in legal.referrals)
    crisis = safety_check("I am in crisis and thinking of self-harm", ["breathe"])
    assert any("emergency" in r.lower() or "helpline" in r.lower() for r in crisis.referrals)


def test_gate_does_not_strip_remedies_with_normal_text():
    from dataclasses import dataclass
    from SweetAstro.src.remedies.catalog import Remedy

    remedy = Remedy(
        kind="donation", tradition="Parashari",
        title="Animal welfare service",
        practice="Support animal welfare; practice only kindness and never harm any creature.",
        planetary_purpose="Channel the node through service.",
        chart_reason="Test reason.", frequency="Weekly", duration="4 weeks",
        safety_note="Safe.", suitability="Moderate", is_primary=True,
    )
    verdict = safety_check("general", [f"{remedy.title} {remedy.practice}"])
    assert verdict.allowed is True


# ---------------------------------------------------------------------------
# Bug 18 — legacy answer engine payload honesty
# ---------------------------------------------------------------------------

def test_legacy_payload_strengths_are_honest():
    from pathlib import Path
    from SweetAstro.src.service import SweetAstroEngine

    engine = SweetAstroEngine(rules_dir=Path(__file__).parent.parent / "data" / "rules")
    answer = engine.predict_marriage(
        1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090,
        search_start_age=25, search_end_age=35,
    )
    payload = answer.internal_payload
    assert payload.parashari_strength == "Not assessed (legacy mode)"
    assert payload.d9_strength == "Not assessed (legacy mode)"
    assert payload.vimshottari_strength == "Not assessed (legacy mode)"
    assert payload.jaimini_strength == "Not assessed (legacy mode)"
    assert payload.transit_strength in ("Double transit active", "No double transit in best window")
    # Legacy absolute headline retired (accuracy protocol: no date claims without
    # demonstrated skill); the field remains for API shape compatibility.
    assert "You will get married in" not in answer.bold_headline
    assert "interpretive estimate" in answer.bold_headline


# ---------------------------------------------------------------------------
# Bug 19 — interpretation layer behavior locks
# ---------------------------------------------------------------------------

def test_read_timing_returns_resolved_dasha():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    birth = datetime(1995, 5, 15, 14, 30)
    timeline = calculate_vimshottari_timeline(birth, d1.planets["Moon"].longitude)
    reading = read_timing(d1, timeline, datetime(2026, 9, 12), [7, 2], "Transit note.")
    assert reading.current_md_ad_pd.count("/") == 2
    assert "— / — / —" not in reading.current_md_ad_pd
    assert reading.natal_promise and reading.dasha_activation and reading.transit_activation


def test_confidence_calibration_thresholds():
    assert calibrate_confidence(5, True, True, True) == "High"
    assert calibrate_confidence(3, True, True, False) == "Medium"
    assert calibrate_confidence(2, True, False, False) == "Low"
    # unreliable birth time caps High at Medium (audit fix)
    assert calibrate_confidence(4, True, True, True) == "High"
    assert calibrate_confidence(4, False, True, True) == "Medium"
    assert calibrate_confidence(2, False, True, True) == "Medium"
