"""Interpretation quality rubric tests."""

from types import SimpleNamespace

from SweetAstro.src.consumer import answer_question
from SweetAstro.src.evaluation.interpretation_quality import (
    outcome_dataset_ready, score_answer, summarize_outcomes,
)

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30, second=0,
             tz_offset=5.5, lat=26.9124, lon=75.7873, place="Jaipur, India")


def test_real_answer_passes_quality_rubric():
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    report = score_answer(result.answer, result)
    assert report.score >= 80, [(i.dimension, i.detail) for i in report.issues]
    assert not report.high_issues
    assert set(report.dimensions_covered) == {
        "completeness", "calibration", "evidence", "gate_consistency", "safety_hygiene"}


def test_banned_language_and_missing_sections_deduct():
    fake = SimpleNamespace(
        key_factors=[], predictions=[], primary_remedy=None, supporting_remedies=[],
        confidence="High", referrals=[],
        to_markdown=lambda: "You will get married in 2028. Guaranteed.",
    )
    report = score_answer(fake)
    dimensions = {i.dimension for i in report.issues}
    assert "completeness" in dimensions
    assert "calibration" in dimensions
    assert len(report.high_issues) >= 2
    assert report.score < 60


def test_gate_consistency_flags_weak_promise_with_predictions():
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    result.promise = SimpleNamespace(timing_reliable=False)
    report = score_answer(result.answer, result)
    if result.answer.predictions:
        assert any(i.dimension == "gate_consistency" and i.severity == "high"
                   for i in report.issues)


def test_outcome_summary_and_readiness():
    records = [
        {"verdict": "happened"}, {"verdict": "happened"},
        {"verdict": "did_not_happen"}, {"verdict": "partial"},
        {"verdict": "bogus"},
    ]
    summary = summarize_outcomes(records)
    assert summary["total"] == 4
    assert summary["counts"]["happened"] == 2
    assert summary["happened_rate"] == 0.5
    readiness = outcome_dataset_ready(records)
    assert readiness["ready_for_calibration_claims"] is False
    assert "No accuracy claim" in readiness["note"]
