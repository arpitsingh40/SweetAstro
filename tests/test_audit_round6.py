"""
Regression tests for audit round 2 backlog execution (2026-09-13):

1.  Fallback ephemeris frame: J2000 Keplerian elements must be precessed to the
    equinox of date before the ayanamsha subtraction.
2.  Legacy accuracy surfaces carry the "machinery validation only" claim guard.
3.  Hierarchy promise gate: obstructed promise withholds timing (protocol 1.2.0);
    withheld records count as misses and are excluded from MAE.
4.  Gemstone note is composed from verdict fields (never a hardcoded label).
5.  Lal Kitab label removed from consumer remedies with no Lal Kitab source.
6.  MEDIUM batch: finance referral retired, sanitizer/rubric share one word list,
    payload timing blocks withheld when promise is weak, "probability %" renamed,
    split-hash erratum published, legacy marriage_timing relabelled,
    explainability de-overclaimed, metric names corrected, verify_answer
    rounding-tolerant, hierarchy scoring on one ensemble scale.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from SweetAstro.src.chat.payload import build_chart_payload
from SweetAstro.src.chat.verify import verify_answer
from SweetAstro.src.consumer import answer_question
from SweetAstro.src.core import ephemeris
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.evaluation.metrics import summarize
from SweetAstro.src.evaluation.protocol import PROTOCOL_CHANGELOG, PROTOCOL_VERSION
from SweetAstro.src.interpretation.promise import PromiseAssessment
from SweetAstro.src.llm.calibrated_language import BANNED_ABSOLUTE, sanitize_absolute_language
from SweetAstro.src.llm.explainability import PredictionExplainability
from SweetAstro.src.prediction.ensemble import SystemEnsemble
from SweetAstro.src.prediction.hierarchy import CandidatePeriod, PredictionHierarchy
from SweetAstro.src.remedies.catalog import lal_kitab_remedy, modern_conduct_remedy
from SweetAstro.src.remedies.gemstone import evaluate_gemstone, format_gemstone_note

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30, second=0,
             tz_offset=5.5, lat=28.6139, lon=77.2090)


# ---------------------------------------------------------------------------
# 1. Fallback ephemeris frame
# ---------------------------------------------------------------------------

def test_frame_precession_matches_fallback_ayanamsha_delta(monkeypatch):
    monkeypatch.setattr(ephemeris, "HAS_SWISSEPH", False)
    for jd in (2415020.5, 2433282.5, 2451545.0, 2449852.875, 2469807.5):
        expected = ephemeris.calculate_lahiri_ayanamsha(jd) - 23.857092
        assert ephemeris.frame_precession_deg(jd) == pytest.approx(expected, abs=1e-9)


def test_fallback_planets_are_precessed_to_equinox_of_date(monkeypatch):
    """At 1900 the J2000-frame error is ~1.4 deg; the fix must keep < 0.35 deg."""
    if not ephemeris.HAS_SWISSEPH:
        pytest.skip("pyswisseph not installed")
    jd = ephemeris.datetime_to_julian_day(1900, 1, 1, 0, 0, 0.0, 0.0)
    ayan = ephemeris.calculate_lahiri_ayanamsha(jd)
    trusted = ephemeris.calculate_planet_positions(jd, ayan)
    monkeypatch.setattr(ephemeris, "HAS_SWISSEPH", False)
    fallback = ephemeris.calculate_planet_positions(jd, ayan)
    for planet in ["Sun", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        diff = (fallback[planet]["longitude"] - trusted[planet]["longitude"] + 540.0) % 360.0 - 180.0
        assert abs(diff) < 0.35, f"{planet}: {diff:+.4f} deg at 1900"


# ---------------------------------------------------------------------------
# 2. Legacy accuracy surfaces
# ---------------------------------------------------------------------------

def test_backtest_metrics_carry_machinery_validation_claim_guard():
    from SweetAstro.src.backtest.metrics import (
        MACHINERY_VALIDATION_NOTE, SingleEvaluationRecord, compute_summary_metrics,
    )
    record = SingleEvaluationRecord(
        prediction_id="SA-MAR-000001", chart_id="C1",
        predicted_year=2020, predicted_month=5, predicted_period_label="May 2020",
        actual_year=2020, actual_month=5, actual_date_str="2020-05-01",
        is_top_1_year=True, is_top_3_year=True, year_error=0, month_error=0.0,
        confidence_score=80.0, stability_score=90.0,
    )
    metrics = compute_summary_metrics([record])
    assert metrics.claim_note == MACHINERY_VALIDATION_NOTE
    assert "not an accuracy claim" in metrics.claim_note
    # Audit rename: misnamed fields are gone
    assert not hasattr(metrics, "calibration_score")
    assert not hasattr(metrics, "top_3_month_accuracy")
    assert metrics.high_confidence_top3_year_share == 100.0
    assert metrics.within_2_months_share == 100.0


def test_backtest_api_stamps_no_accuracy_claim():
    from fastapi.testclient import TestClient
    from SweetAstro.src.api.app import app

    response = TestClient(app).post("/api/backtest/run")
    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["accuracy_claim"] is False
    assert "not an accuracy claim" in metrics["claim_note"]
    assert "high_confidence_top3_year_share" in metrics


def test_legacy_metrics_exclude_withheld_from_error_stats():
    from SweetAstro.src.backtest.metrics import (
        SingleEvaluationRecord, compute_summary_metrics,
    )

    def rec(**over):
        base = dict(
            prediction_id="X", chart_id="C1", predicted_year=2020, predicted_month=5,
            predicted_period_label="May 2020", actual_year=2020, actual_month=5,
            actual_date_str="2020-05-01", is_top_1_year=True, is_top_3_year=True,
            year_error=0, month_error=0.0, confidence_score=80.0, stability_score=90.0,
        )
        base.update(over)
        return SingleEvaluationRecord(**base)

    withheld = rec(predicted_year=0, predicted_month=0, predicted_period_label="withheld",
                   is_top_1_year=False, is_top_3_year=False, month_error=0.0,
                   confidence_score=0.0, withheld=True)
    metrics = compute_summary_metrics([rec(), withheld])
    assert metrics.top_1_year_accuracy == 50.0
    assert metrics.mean_absolute_error_months == 0.0  # withheld skipped
    assert metrics.within_2_months_share == 50.0      # withheld still a miss


def test_blind_runner_records_withheld_predictions():
    import json
    from pathlib import Path
    from types import SimpleNamespace

    from SweetAstro.src.backtest.metrics import compute_summary_metrics
    from SweetAstro.src.prediction.hierarchy import ProgressivePrediction
    from SweetAstro.src.service import SweetAstroEngine

    root = Path(__file__).parent.parent
    dataset = json.loads((root / "data" / "test_charts" / "historical_verified.json")
                         .read_text(encoding="utf-8"))
    engine = SweetAstroEngine(rules_dir=root / "data" / "rules")
    gated = ProgressivePrediction(
        promise_indicated=False, promise_strength="Delayed / Challenging",
        age_range=(26, 40), top_years=[], top_quarters=[], top_months=[],
        best_year=0, best_quarter="", best_month="", best_month_score=0.0,
        all_monthly_scores={})
    engine.backtest_runner.hierarchy = SimpleNamespace(predict=lambda *a, **k: gated)

    record = engine.backtest_runner.run_single_blind_chart(dataset[0])
    assert record.withheld is True
    assert record.predicted_period_label.startswith("withheld")
    assert record.is_top_1_year is False and record.is_top_3_year is False
    assert compute_summary_metrics([record]).mean_absolute_error_months == 0.0


# ---------------------------------------------------------------------------
# 3. Hierarchy promise gate (protocol 1.2.0)
# ---------------------------------------------------------------------------

class _StubEvaluator:
    def __init__(self, promise_score, delay_score):
        self._report = SimpleNamespace(promise_score=promise_score, delay_score=delay_score)

    def evaluate(self, *args, **kwargs):
        return self._report


@pytest.mark.parametrize("promise,delay,indicated,strength", [
    (50.0, 10.0, True, "Strong"),
    (30.0, 30.0, True, "Moderate / Delayed"),
    (5.0, 40.0, False, "Delayed / Challenging"),
])
def test_evaluate_promise_returns_real_gate(promise, delay, indicated, strength):
    hierarchy = PredictionHierarchy(_StubEvaluator(promise, delay))
    result = hierarchy.evaluate_promise(None, None)
    assert result[0] is indicated
    assert result[1] == strength
    assert result[2] == delay


def test_predict_withholds_timing_when_promise_obstructed():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    d9 = calculate_navamsa_chart(d1)
    hierarchy = PredictionHierarchy(_StubEvaluator(0.0, 40.0))
    pred = hierarchy.predict(d1, d9, None, None, datetime(1995, 5, 15, 14, 30), [])
    assert pred.promise_indicated is False
    assert pred.promise_strength == "Delayed / Challenging"
    assert pred.top_years == [] and pred.top_quarters == [] and pred.top_months == []
    assert pred.best_month == "" and pred.best_month_score == 0.0
    assert pred.all_monthly_scores == {}


def test_legacy_answer_engine_handles_gated_prediction():
    from SweetAstro.src.llm.answer_engine import AnswerSynthesisEngine
    from SweetAstro.src.prediction.hierarchy import ProgressivePrediction

    gated = ProgressivePrediction(
        promise_indicated=False, promise_strength="Delayed / Challenging",
        age_range=(26, 40), top_years=[], top_quarters=[], top_months=[],
        best_year=0, best_quarter="", best_month="", best_month_score=0.0,
        all_monthly_scores={})
    sensitivity = SimpleNamespace(
        overall_stability_score=75.0, stability_classification="High", window_minutes=10)
    answer = AnswerSynthesisEngine().generate_decisive_answer(gated, sensitivity)
    assert "Timing withheld" in answer.bold_headline
    assert answer.internal_payload.month_score == 0.0
    assert answer.internal_payload.year_score == 0.0
    assert answer.internal_payload.why_not_other_months["monthly_breakdown"] == []
    assert "withheld" in answer.internal_payload.best_period.lower()


def test_harness_withheld_records_count_as_misses_and_skip_mae():
    preds = [        {"predicted_year": 2020, "predicted_month": 5, "top3_years": [2020],
         "actual_year": 2020, "actual_month": 5, "score": 80.0, "withheld": False},
        {"predicted_year": 0, "predicted_month": 0, "top3_years": [],
         "actual_year": 2020, "actual_month": 5, "score": 0.0, "withheld": True},
    ]
    s = summarize(preds)
    assert s["top1_year"] == 50.0
    assert s["top3_year"] == 50.0
    assert s["n_withheld"] == 1
    assert s["mae_months"] == 0.0  # withheld excluded; only the exact hit remains


def test_protocol_version_bumped_for_model_change():
    assert PROTOCOL_VERSION == "1.2.0"
    assert "1.2.0" in PROTOCOL_CHANGELOG
    entry = PROTOCOL_CHANGELOG["1.2.0"].lower()
    assert "promise gate" in entry and "withheld" in entry


def test_protocol_erratum_published_for_split_hash():
    from pathlib import Path

    text = (Path(__file__).parent.parent / "docs" / "accuracy_protocol.md").read_text(encoding="utf-8")
    assert "Erratum 1" in text
    assert "seed:*" in text or "seed}:{chart_id" in text or 'f"{seed}:{chart_id}"' in text


# ---------------------------------------------------------------------------
# 4. Gemstone note composed from the verdict
# ---------------------------------------------------------------------------

def _assessment(planet, recommendation, *, afflicted=False, lordship=(), dignity="Friend"):
    return SimpleNamespace(
        planet=planet, recommendation=recommendation, recommendation_reason="test reason",
        afflicted=afflicted, functional_lordship=list(lordship), sign_dignity=dignity,
        house=2, vargottama=False,
    )


def test_gemstone_note_follows_safety_class():
    consider = evaluate_gemstone(
        _assessment("Jupiter", "strengthen", lordship=(1, 10), dignity="Exalted"),
        in_relevant_dasha=True)
    note = format_gemstone_note(consider)
    assert "verification" in note.lower()
    assert "Unsuitable now" not in note

    mention = evaluate_gemstone(_assessment("Venus", "pacify", afflicted=True, lordship=(3, 8)),
                                in_relevant_dasha=True)
    mention_note = format_gemstone_note(mention)
    assert "not recommended" in mention_note.lower()

    node = evaluate_gemstone(_assessment("Rahu", "pacify"), in_relevant_dasha=True)
    node_note = format_gemstone_note(node)
    assert "not advised" in node_note.lower()


def test_consumer_gemstone_reason_composed_from_verdict():
    result = answer_question(**BIRTH, question="wealth and career", time_reliable=True)
    reason = result.answer.remedy_suitability_reason
    assert "Gemstone" in reason
    assert "Suitability score" in reason
    assert "Unsuitable now" not in reason


# ---------------------------------------------------------------------------
# 5. Lal Kitab provenance
# ---------------------------------------------------------------------------

def test_consumer_never_labels_unsourced_practice_lal_kitab():
    result = answer_question(**BIRTH, question="wealth growth", time_reliable=True)
    for remedy in ([result.answer.primary_remedy] if result.answer.primary_remedy else []) \
            + result.answer.supporting_remedies:
        assert remedy.tradition != "Lal Kitab"
        assert "Lal Kitab" not in remedy.title
    conduct = [r for r in result.answer.supporting_remedies if r.kind == "conduct"]
    for remedy in conduct:
        assert remedy.tradition == "modern conduct"


def test_catalog_separates_modern_conduct_from_lal_kitab():
    conduct = modern_conduct_remedy("X house steadiness", "practice", "purpose", "reason")
    assert conduct.kind == "conduct"
    assert conduct.tradition == "modern conduct"
    assert "declared modern" in conduct.practice
    sourced = lal_kitab_remedy("X", "practice", "purpose", "reason")
    assert sourced.tradition == "Lal Kitab" and "Lal Kitab" in sourced.practice


# ---------------------------------------------------------------------------
# 6. MEDIUM batch
# ---------------------------------------------------------------------------

def test_finance_referral_retired_from_prompts():
    from SweetAstro.src.chat import prompt as prompt_mod

    blob = (prompt_mod.ANSWER_SYSTEM_PROMPT + prompt_mod._COMMON_SHAPE_RULES
            + prompt_mod.REMEDY_SYSTEM_PROMPT + prompt_mod.TIMING_SYSTEM_PROMPT)
    assert "health/legal/finance/crisis" not in blob
    assert "health/legal/crisis" in blob


def test_sanitizer_and_rubric_share_one_banned_list():
    for phrase in BANNED_ABSOLUTE:
        fixed = sanitize_absolute_language(f"X {phrase} Y")
        if phrase == "not guaranteed":
            continue
        assert phrase not in fixed.lower(), f"sanitizer left '{phrase}'"
    # Negated guarantees are rewritten, not flagged by the rubric
    assert "not assured" in sanitize_absolute_language("This is not guaranteed.")


def test_payload_withholds_timing_blocks_when_promise_weak(monkeypatch):
    from SweetAstro.src.chat.payload import build_chart_payload

    weak = PromiseAssessment(
        topic="career", level="Weak", score=-2.0,
        supportive_factors=[], limiting_factors=["Saturn occupies H10"],
        timing_reliable=False, statement="The chart shows a weak promise for career.",
    )
    monkeypatch.setattr("SweetAstro.src.consumer.assess_promise", lambda *a, **k: weak)
    result = answer_question(**BIRTH, question="Career growth?", time_reliable=True)
    payload = build_chart_payload(
        result, name="Native", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="Career growth?", topic="career",
        dasha_detail="MD Sun: 2020-01-01 to 2026-01-01 | AD Moon: 2024-01-01 to 2025-01-01",
    )
    assert "TIMING WITHHELD" in payload
    assert "Dasha period boundaries:" not in payload
    assert "Personal timeline" not in payload
    assert "Current Vimshottari dasha:" in payload  # current anchor stays factual


def test_candidate_period_uses_score_share_name():
    fields = CandidatePeriod.__dataclass_fields__
    assert "probability_pct" not in fields
    assert "score_share_pct" in fields


def test_verify_answer_is_rounding_tolerant():
    payload = "Ascendant: Leo 151.6517 deg, Moon: Scorpio 217.4852 deg"
    assert verify_answer("The ascendant is 151.7° and the Moon is 217.49°.", payload) == []
    assert verify_answer("The ascendant is 151.9°.", payload) == ["degree 151.9°"]


def test_explainability_no_longer_overclaims():
    gated = SimpleNamespace(
        promise_indicated=False, promise_strength="Delayed / Challenging",
        top_months=[], top_years=[], all_monthly_scores={},
    )
    sensitivity = SimpleNamespace(overall_stability_score=80.0, window_minutes=10)
    reasons = "\n".join(PredictionExplainability.generate_why_this_period(gated, sensitivity))
    assert "withheld" in reasons.lower() or "no timing period" in reasons.lower()
    assert "clear fruition" not in reasons.lower()
    assert "genuine marital union" not in reasons.lower()
    why_not = PredictionExplainability.generate_why_not_other_months(gated)
    assert why_not["monthly_breakdown"] == []
    assert "withheld" in why_not["summary"].lower()


def test_hierarchy_scoring_uses_one_ensemble_scale():
    from SweetAstro.src.rules.loader import RuleCatalog
    from SweetAstro.src.rules.evaluator import RuleEvaluator
    from pathlib import Path

    rules_dir = Path(__file__).parent.parent / "data" / "rules"
    catalog = RuleCatalog()
    catalog.load_from_directory(rules_dir)
    hierarchy = PredictionHierarchy(RuleEvaluator(catalog))
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    d9 = calculate_navamsa_chart(d1)
    birth_dt = datetime(1995, 5, 15, 14, 30)
    pred = hierarchy.predict(d1, d9, None, None, birth_dt, [], search_start_age=25, search_end_age=30)

    ensemble = SystemEnsemble()
    assert pred.best_month_score == ensemble.score_period(pred.top_months[0].convergence)
    # Quarters cover the full candidate set -> shares normalize to 100
    assert abs(sum(q.score_share_pct for q in pred.top_quarters) - 100.0) < 1.0
    for group in (pred.top_years, pred.top_months):
        assert group and all(0.0 <= c.score_share_pct <= 100.0 for c in group)
    assert ensemble.score_period(pred.top_years[0].convergence) > 0.0


def test_legacy_marriage_timing_is_relabelled():
    from SweetAstro.src.prediction import marriage_timing

    doc = (marriage_timing.__doc__ or "").upper()
    assert "LEGACY" in doc
    assert "NOT USED BY ANY PRODUCTION PATH" in doc
