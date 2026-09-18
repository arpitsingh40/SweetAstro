"""
Tests for Consumer Answer Engine (Sec 1-16).
- No certainty language; calibrated confidence; remedy caps; safety gate.
- Backward compat: legacy marriage flow still works.
"""

from pathlib import Path
from SweetAstro.src.service import SweetAstroEngine
from SweetAstro.src.core.vargas import vargas_for_question, calculate_varga_chart
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.strength import assess_planet_strength
from SweetAstro.src.core.rahu_ketu import analyze_node
from SweetAstro.src.remedies.safety import safety_check

ENGINE = SweetAstroEngine(rules_dir=Path(__file__).parent.parent / "data" / "rules")

BANNED = ["definitely", "guaranteed", "100%", "will surely", "You will get married in"]


def _answer(question="career growth", time_reliable=True):
    r = ENGINE.answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question=question, time_reliable=time_reliable,
    )
    return r.answer


def test_consumer_format_sections():
    a = _answer("career growth and promotion")
    md = a.to_markdown()
    for section in ["🔮 Bottom Line", "🧩 Key Chart Factors", "⏳ Timing",
                    "📈 Opportunity", "⚠️ Risk", "🪐 Recommended Alignment",
                    "🕉️ Traditional Remedies", "🎯 What You Should Do",
                    "Confidence", "Remedy Suitability"]:
        assert section in md
    assert 1 <= len(a.key_factors) <= 5
    assert 1 <= len(a.practical_actions) <= 7
    assert a.confidence in ("Low", "Medium", "High")
    assert a.remedy_suitability in ("Low", "Moderate", "High")


def test_no_certainty_language():
    import re
    for q in ["marriage timing", "wealth and money", "health concerns", "career"]:
        a = _answer(q)
        blob = (a.bottom_line + " " + a.opportunity + " " + a.risk + " " + a.to_markdown()).lower()
        for banned in ["definitely", "will surely", "you will get married in"]:
            assert banned.lower() not in blob, f"Banned phrase '{banned}' in answer for '{q}'"
        assert "100%" not in blob
        # 'guarantee' only allowed in negations like 'not guaranteed / no guarantees / never guarantees'
        for m in re.finditer(r"guarantee\w*", blob):
            ctx = blob[max(0, m.start() - 60):m.start()]
            assert any(neg in ctx for neg in ["not", "no ", "no remedy", "never", "without", "n't", "does not", "do not"]), \
                f"Positive guarantee claim near '{blob[m.start()-30:m.end()+30]}' for '{q}'"


def test_remedy_cap_and_chart_reason():
    a = _answer("wealth accumulation")
    total = (1 if a.primary_remedy else 0) + len(a.supporting_remedies)
    assert total <= 3
    for r in ([a.primary_remedy] if a.primary_remedy else []) + a.supporting_remedies:
        assert r.planetary_purpose and r.chart_reason and r.frequency
        assert r.safety_note and r.suitability in ("Low", "Moderate", "High")
        # Lal Kitab must be labelled distinctly
        if r.kind == "lal_kitab":
            assert "Lal Kitab" in r.title or "Lal Kitab" in r.practice


def test_time_uncertainty_reduces_confidence():
    a_ok = _answer("marriage timing", time_reliable=True)
    a_uncertain = _answer("marriage timing", time_reliable=False)
    order = {"Low": 0, "Medium": 1, "High": 2}
    assert order[a_uncertain.confidence] <= order[a_ok.confidence]
    assert "uncertain" in a_uncertain.confidence_reason.lower() or "reduced" in a_uncertain.confidence_reason.lower()
    # No house-based Lal Kitab when time unreliable
    for r in a_uncertain.supporting_remedies:
        assert r.kind != "lal_kitab"


def test_varga_relevance_matches_question():
    assert vargas_for_question("wealth and income") == ["D1", "D2", "D9", "D10", "D11"]
    assert vargas_for_question("my career and job") == ["D1", "D9", "D10"]
    assert vargas_for_question("marriage partner") == ["D1", "D9"]
    assert vargas_for_question("children") == ["D1", "D7"]
    assert vargas_for_question("property flat") == ["D1", "D4"]
    assert vargas_for_question("health disease") == ["D1", "D6", "D30"]
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090)
    for v in ["D2", "D3", "D4", "D5", "D6", "D7", "D8", "D10", "D11", "D12", "D30"]:
        vc = calculate_varga_chart(d1, v)
        assert 1 <= vc.ascendant_sign_index <= 12
        assert len(vc.planets) == 9


# ---------------------------------------------------------------------------
# Routing word boundaries: "ill" must not match inside "will"
# ---------------------------------------------------------------------------

def test_keyword_matcher_word_boundaries():
    from SweetAstro.src.core.keywords import matches_any

    assert matches_any("When will I get married?", ["ill"]) is False
    assert matches_any("Am I ill?", ["ill"]) is True
    assert matches_any("pregnancy question", ["pregnan"]) is True
    assert matches_any("Will I be rich?", ["rich"]) is True


def test_marriage_question_routes_to_marriage_not_health():
    from SweetAstro.src.consumer import _topic_key

    assert _topic_key("When will I get married?") == "marriage"
    assert _topic_key("When will he get married?") == "marriage"
    assert _topic_key("Will I be rich?") == "wealth"
    assert _topic_key("Am I ill?") == "health"


def test_varga_selection_uses_word_boundaries():
    assert vargas_for_question("When will I get married?") == ["D1", "D9"]
    assert vargas_for_question("Will I be rich?") == ["D1", "D2", "D9", "D10", "D11"]
    assert vargas_for_question("Am I ill?") == ["D1", "D6", "D30"]


def test_consumer_answer_routes_marriage_question_correctly():
    from SweetAstro.src.consumer import answer_question

    result = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question="When will I get married?", time_reliable=True,
    )
    assert result.topic == "marriage"
    assert "D9" in result.vargas


def test_strength_full_chain_and_no_autostrengthen():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090)
    sa = assess_planet_strength(d1, "Jupiter", None, ["Jupiter"])
    assert sa.recommendation in ("strengthen", "pacify", "balance", "leave-alone")
    assert sa.dispositor and sa.nakshatra and sa.nakshatra_lord
    assert isinstance(sa.functional_lordship, list)
    # Nodes default to pacify/balance, never blind strengthen
    ra = analyze_node(d1, "Rahu", None, True)
    assert ra.recommendation in ("pacify", "balance")
    ke = analyze_node(d1, "Ketu", None, True)
    assert ke.recommendation in ("pacify", "balance")
    assert ra.dispositor and ra.nakshatra_lord


def test_safety_referrals_for_health():
    v = safety_check("health disease and anxiety", ["gentle routine"])
    assert any("doctor" in r.lower() or "professional" in r.lower() for r in v.referrals)
    no_finance_referral = safety_check("invest money loan", ["budget plan"])
    assert no_finance_referral.referrals == []
    bad = safety_check("general", ["This will guarantee wealth 100%"])
    assert bad.allowed is False


def test_backtest_mode_note():
    r = ENGINE.answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question="career", time_reliable=True,
        historical_events=[{"event": "job change 2021-06"}],
    )
    md = r.answer.to_markdown()
    assert "Backtest" in md
    assert "not proof" in md.lower() or "in-sample" in md.lower()


def test_legacy_marriage_still_works():
    ans = ENGINE.predict_marriage(1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090,
                                  search_start_age=25, search_end_age=35)
    assert ans.internal_payload.month_score > 0
