"""
Gemstone gate tests: suitability scoring, safety classes, and consumer integration.
"""

from types import SimpleNamespace

import pytest

from SweetAstro.src.remedies.gemstone import evaluate_gemstone


def _assessment(planet, recommendation, *, afflicted=False, lordship=(), dignity="Friend", house=2,
                vargottama=False):
    return SimpleNamespace(
        planet=planet,
        recommendation=recommendation,
        recommendation_reason="test reason",
        afflicted=afflicted,
        functional_lordship=list(lordship),
        sign_dignity=dignity,
        house=house,
        vargottama=vargottama,
    )


def test_nodes_are_avoid_as_strengthening():
    for node in ("Rahu", "Ketu"):
        verdict = evaluate_gemstone(_assessment(node, "pacify"), in_relevant_dasha=True)
        assert verdict.safety == "avoid-as-strengthening"
        assert verdict.suitability_score == 15
        assert verdict.mention_allowed is True
        assert "pacify" in verdict.why_unsuitable.lower()


def test_pacify_planet_is_mention_only():
    verdict = evaluate_gemstone(
        _assessment("Venus", "pacify", afflicted=True, lordship=(3, 8)), in_relevant_dasha=True)
    assert verdict.safety == "mention-only"
    assert verdict.suitability_score == 20
    assert verdict.why_considered  # must still state why considered


def test_strengthen_in_dasha_unafflicted_is_consider():
    verdict = evaluate_gemstone(
        _assessment("Jupiter", "strengthen", afflicted=False, lordship=(1, 10), dignity="Exalted"),
        in_relevant_dasha=True)
    assert verdict.safety == "consider-with-verification"
    assert verdict.suitability_score == 70
    assert "verification" in verdict.note.lower()


def test_strengthen_without_dasha_scores_lower():
    verdict = evaluate_gemstone(
        _assessment("Mercury", "strengthen", afflicted=False, lordship=(1, 4)),
        in_relevant_dasha=False)
    assert verdict.safety == "mention-only"
    assert verdict.suitability_score == 40


def test_dusthana_afflicted_overrides_strengthen():
    verdict = evaluate_gemstone(
        _assessment("Saturn", "strengthen", afflicted=True, lordship=(8, 12)),
        in_relevant_dasha=True)
    assert verdict.suitability_score <= 25
    assert verdict.safety == "mention-only"


def test_every_verdict_has_alternative_and_reasons():
    for planet, rec in [("Sun", "balance"), ("Moon", "balance"), ("Mars", "pacify")]:
        verdict = evaluate_gemstone(_assessment(planet, rec, afflicted=rec == "pacify"),
                                    in_relevant_dasha=False)
        assert verdict.alternative
        assert verdict.reasons
        assert "no guarantee" in (verdict.note + verdict.why_unsuitable).lower() or verdict.note
        assert 0 <= verdict.suitability_score <= 100


def test_real_chart_integration():
    from SweetAstro.src.core.chart import calculate_d1_chart
    from SweetAstro.src.core.strength import assess_planet_strength
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090)
    assessment = assess_planet_strength(d1, "Jupiter", None, ["Jupiter"])
    verdict = evaluate_gemstone(assessment, in_relevant_dasha=True)
    assert verdict.gem == "Yellow Sapphire (Pukhraj)"
    assert verdict.safety in ("avoid-as-strengthening", "mention-only", "consider-with-verification")
    assert verdict.suitability_score in (15, 20, 25, 40, 70)


def test_consumer_answer_includes_gem_score():
    from SweetAstro.src.consumer import answer_question
    result = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question="wealth and career", time_reliable=True,
    )
    reason = result.answer.remedy_suitability_reason
    assert "Gemstone" in reason
    assert "Suitability score" in reason
