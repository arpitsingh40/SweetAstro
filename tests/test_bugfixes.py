"""
Regression tests for real bugs found in the software audit (2026-09-12):

1. Estimated timezone was not reset when the birthplace changed
2. Rule evaluator resolved the Upapada Lagna lord from the wrong house
3. MAR-0009 ("7th house free of malefics") could never match (dead rule)
4. MAR-0034/MAR-0036 claimed Saturn/Rahu transits but tested Jupiter
5. MAR-0033 lost its condition; MAR-0055 was a duplicate of MAR-0031
6. core/arudha.py used non-classical exception rules and disagreed with
   core/jaimini.py about the Upapada Lagna
7. The ensemble weight optimizer was silently broken and pseudo-predicted
8. calculate_convergence_score crashed on a None double-transit result
9. The muhurta chat payload could report a search range longer than the
   range actually scanned
"""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from SweetAstro.src.chat.session import BirthSlots
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import INDEX_TO_SIGN, SIGN_LORDS
from SweetAstro.src.core.jaimini import calculate_chara_karakas, calculate_jaimini_points
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.core.arudha import calculate_arudha_pada
from SweetAstro.src.core.transits import get_transit_positions
from SweetAstro.src.core.yogas import detect_yogas, kala_sarpa_planets
from SweetAstro.src.prediction.convergence import calculate_convergence_score
from SweetAstro.src.prediction.ensemble import EnsembleWeights, SystemEnsemble
from SweetAstro.src.rules.evaluator import EvaluationReport, RuleEvaluator
from SweetAstro.src.rules.loader import RuleCatalog
from SweetAstro.src.rules.schema import RuleCondition

RULES_DIR = Path(__file__).parent.parent / "data" / "rules"
MALEFICS = {"Saturn", "Mars", "Rahu", "Ketu", "Sun"}


@pytest.fixture(scope="module")
def demo():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    d9 = calculate_navamsa_chart(d1)
    karakas = calculate_chara_karakas(d1)
    jaimini_pts = calculate_jaimini_points(d1, d9)
    return d1, d9, karakas, jaimini_pts


# ---------------------------------------------------------------------------
# Bug 1 — timezone reset on place change
# ---------------------------------------------------------------------------

def test_place_change_resets_estimated_timezone():
    slots = BirthSlots()
    slots.merge({"place": "Jaipur, India", "tz_offset_estimate": 5.5, "dob": "1995-05-15"})
    assert slots.tz_offset == 5.5 and slots.tz_estimated is True

    slots.merge({"place": "London, UK", "tz_offset_estimate": 0.0})
    assert slots.place == "London, UK"
    assert slots.tz_offset == 0.0, "estimated timezone must follow the new birthplace"
    assert slots.tz_estimated is True


def test_place_change_keeps_explicit_timezone():
    slots = BirthSlots()
    slots.merge({"place": "London, UK", "tz_offset": 0.0})
    assert slots.tz_estimated is False
    slots.merge({"place": "Mumbai, India"})
    assert slots.tz_offset == 0.0, "explicitly stated timezone must be preserved"


# ---------------------------------------------------------------------------
# Bug 2 — UL lord resolution
# ---------------------------------------------------------------------------

def test_ul_lord_uses_sign_lord():
    evaluator = RuleEvaluator(RuleCatalog())
    condition = RuleCondition(entity="active_dasha_lord",
                              condition_type="is_lord_of_house",
                              target="upapada_lagna")

    distinguishing = 0
    for birth in [(1995, 5, 15, 14, 30), (1982, 6, 21, 21, 3),
                  (1946, 6, 14, 10, 54), (2000, 9, 15, 6, 30)]:
        d1 = calculate_d1_chart(*birth, 0.0, 5.5, 28.6139, 77.2090)
        d9 = calculate_navamsa_chart(d1)
        karakas = calculate_chara_karakas(d1)
        jaimini_pts = calculate_jaimini_points(d1, d9)

        correct_lord = SIGN_LORDS[INDEX_TO_SIGN[jaimini_pts.upapada_lagna_index]]
        wrong_lord = d1.houses[jaimini_pts.upapada_lagna_index].lord

        ok = SimpleNamespace(mahadasha=correct_lord, antardasha="__none__", pratyantardasha="__none__")
        assert evaluator._check_condition(condition, d1, d9, ok, None, None,
                                          karakas, jaimini_pts) is True
        if wrong_lord != correct_lord:
            distinguishing += 1
            bad = SimpleNamespace(mahadasha=wrong_lord, antardasha="__none__", pratyantardasha="__none__")
            assert evaluator._check_condition(condition, d1, d9, bad, None, None,
                                              karakas, jaimini_pts) is False

    assert distinguishing > 0, "fixture must include a chart that separates sign-lord from house-number lord"


# ---------------------------------------------------------------------------
# Bug 3 — house_free_of_malefics / MAR-0009
# ---------------------------------------------------------------------------

def test_house_free_of_malefics_condition(demo):
    d1, d9, karakas, jaimini_pts = demo
    evaluator = RuleEvaluator(RuleCatalog())
    condition = RuleCondition(entity="7th_house", condition_type="house_free_of_malefics",
                              target="7", values=sorted(MALEFICS))

    expected_seventh = not (set(d1.houses[7].occupants) & MALEFICS)
    assert evaluator._check_condition(condition, d1, d9, None, None, None, karakas, jaimini_pts) is expected_seventh

    sun_house = d1.planets["Sun"].house  # Sun is a malefic
    occupied = RuleCondition(entity="x", condition_type="house_free_of_malefics",
                             target=str(sun_house), values=sorted(MALEFICS))
    assert evaluator._check_condition(occupied, d1, d9, None, None, None, karakas, jaimini_pts) is False


def test_mar_0009_can_match_now(demo):
    d1, d9, karakas, jaimini_pts = demo
    catalog = RuleCatalog()
    catalog.load_from_directory(RULES_DIR)
    evaluator = RuleEvaluator(catalog)
    report = evaluator.evaluate(d1, d9, karakas, jaimini_pts, datetime(2026, 6, 15))
    matched = any(a.rule_id == "MAR-0009" for a in report.matched_rules)
    seventh_clean = not (set(d1.houses[7].occupants) & MALEFICS)
    assert matched is seventh_clean


# ---------------------------------------------------------------------------
# Bug 4/5 — transit rule entities
# ---------------------------------------------------------------------------

def _transit_condition_matches(entity, target, d1, d9, karakas, jaimini_pts):
    evaluator = RuleEvaluator(RuleCatalog())
    condition = RuleCondition(entity=entity, condition_type="transit_aspects_house", target=target)
    for year in range(2026, 2033):
        for month in (1, 4, 7, 10):
            when = datetime(year, month, 15)
            if evaluator._check_condition(condition, d1, d9, None, None,
                                          get_transit_positions(when), karakas, jaimini_pts):
                return True
    return False


def test_transit_saturn_entity_works(demo):
    d1, d9, karakas, jaimini_pts = demo
    assert _transit_condition_matches("transit_saturn", "7", d1, d9, karakas, jaimini_pts)


def test_transit_rahu_entity_works(demo):
    d1, d9, karakas, jaimini_pts = demo
    assert _transit_condition_matches("transit_rahu", "7", d1, d9, karakas, jaimini_pts)


def test_transit_rule_json_integrity():
    import json
    v1 = json.loads((RULES_DIR / "mar_transit_timing.json").read_text(encoding="utf-8"))
    v2 = json.loads((RULES_DIR / "mar_transit_timing_v2.json").read_text(encoding="utf-8"))
    by_id = {r["rule_id"]: r for r in v1 + v2}

    cond = by_id["MAR-0033"]["conditions"][0]
    assert cond["entity"] == "transit_jupiter" and cond["condition_type"] == "aspects_planet"
    assert cond["target"] == "lagna_lord"

    assert by_id["MAR-0034"]["conditions"][0]["entity"] == "transit_saturn"
    assert by_id["MAR-0036"]["conditions"][0]["entity"] == "transit_rahu"

    mar_0055 = by_id["MAR-0055"]["conditions"][0]
    assert mar_0055["target"] == "7_d9_lord", "MAR-0055 must not duplicate MAR-0031"
    mar_0031 = by_id["MAR-0031"]["conditions"][0]
    assert mar_0031["target"] == "7"


def test_transit_7_d9_lord_target(demo):
    d1, d9, karakas, jaimini_pts = demo
    evaluator = RuleEvaluator(RuleCatalog())
    condition = RuleCondition(entity="transit_jupiter", condition_type="transit_aspects_house",
                              target="7_d9_lord")
    found = False
    for year in range(2026, 2033):
        for month in (1, 4, 7, 10):
            when = datetime(year, month, 15)
            transits = get_transit_positions(when)
            lord = d9.seventh_house_lord
            expected = (lord in d1.planets and
                        d1.planets[lord].sign_index in transits["Jupiter"].aspected_sign_indices)
            actual = evaluator._check_condition(condition, d1, d9, None, None,
                                                transits, karakas, jaimini_pts)
            assert actual is expected
            found = found or actual
    assert found, "expected at least one Jupiter transit in 2026-2032 to touch the D9 7th lord sign"


# ---------------------------------------------------------------------------
# Bug 6 — arudha consistency with jaimini.py (and with the classical rule)
# ---------------------------------------------------------------------------

def _classical_arudha(house_sign_idx: int, lord_sign_idx: int) -> int:
    """Oracle: Phalita-style Arudha rule with the 10th-from-pada exception."""
    dist = (lord_sign_idx - house_sign_idx) % 12
    raw = (lord_sign_idx + dist - 1) % 12 + 1
    seventh = (house_sign_idx + 5) % 12 + 1
    if raw == house_sign_idx or raw == seventh:
        raw = (raw + 8) % 12 + 1  # 10th sign from the pada
    return raw


@pytest.mark.parametrize("birth", [
    (1995, 5, 15, 14, 30),
    (1982, 6, 21, 21, 3),
    (1946, 6, 14, 10, 54),
    (2000, 9, 15, 6, 30),
])
def test_arudha_matches_classical_rule_and_jaimini(birth):
    d1 = calculate_d1_chart(*birth, 0.0, 5.5, 28.6139, 77.2090)
    d9 = calculate_navamsa_chart(d1)
    jaimini_pts = calculate_jaimini_points(d1, d9)

    house = d1.houses[12]
    lord_sign_idx = d1.planets[house.lord].sign_index
    expected = _classical_arudha(house.sign_index, lord_sign_idx)

    legacy = calculate_arudha_pada(d1, 12, "UL")
    assert legacy.sign_index == expected, "arudha.py must follow the classical exception rule"
    assert jaimini_pts.upapada_lagna_index == expected, "jaimini.py must follow the classical exception rule"


# ---------------------------------------------------------------------------
# Bug 7 — optimizer
# ---------------------------------------------------------------------------

def test_optimizer_is_disabled_honestly():
    ensemble = SystemEnsemble()
    with pytest.raises(NotImplementedError, match="accuracy_backtest"):
        ensemble.optimize_weights([], [], [], [], [], [], [])


def test_ensemble_weights_serialize():
    data = EnsembleWeights().to_dict()
    assert set(data) == {"parashari", "d9", "dasha", "transit", "jaimini"}


# ---------------------------------------------------------------------------
# Bug 8 — convergence with missing transit result
# ---------------------------------------------------------------------------

def test_convergence_handles_none_double_transit(demo):
    d1, d9, karakas, _ = demo
    report = EvaluationReport(
        target_date=datetime(2026, 1, 1), matched_rules=[],
        positive_score=20.0, negative_score=5.0, net_score=15.0,
        promise_score=20.0, delay_score=5.0, dasha_score=0.0,
        transit_score=0.0, jaimini_score=0.0,
    )
    breakdown = calculate_convergence_score(report, None, d1, karakas)
    assert breakdown.transit_support >= 0.0
    assert 0.0 <= breakdown.calibrated_score <= 100.0


# ---------------------------------------------------------------------------
# Bug 9 — muhurta search range reporting
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, extractions, reply="🗓️ Best Dates\n\nWindows."):
        self.extractions = list(extractions)
        self.reply = reply
        self.stream_calls = []

    def complete_json(self, messages, **kwargs):
        return self.extractions.pop(0) if self.extractions else {}

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        for word in self.reply.split(" "):
            yield {"type": "content", "text": word + " "}


@pytest.mark.slow  # scans 120 days of panchanga (~2-3 s) — excluded from the fast dev loop
def test_muhurta_range_is_clamped_to_what_is_scanned(monkeypatch):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator, MUHURTA_MAX_DAYS
    from SweetAstro.src.chat.session import SessionStore

    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (28.6356, 77.2244, "Geocoded (mock)."),
    )
    extraction = {"place": "New Delhi, India", "tz_offset": 5.5,
                  "muhurta_event": "general",
                  "muhurta_start": "2026-09-01", "muhurta_end": "2027-06-01"}
    client = _FakeClient([extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = list(orch.handle_message("m1", "Find an auspicious day between Sep 2026 and Jun 2027."))
    meta = next(e for e in events if e.type == "meta")
    start_str, end_str = meta.data["birth_data"]["range"].split(" to ")
    span = (datetime.strptime(end_str, "%Y-%m-%d") - datetime.strptime(start_str, "%Y-%m-%d")).days + 1
    assert span <= MUHURTA_MAX_DAYS


# ---------------------------------------------------------------------------
# Bug 10 — Kala Sarpa flagged nearly every chart (per-planet test was always
# true for planets outside the two node houses)
# ---------------------------------------------------------------------------

SEVEN = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")


def test_kala_sarpa_requires_one_full_nodal_arc():
    # Rahu in Aries (1), Ketu in Libra (7). All seven planets in signs 2-6.
    planets = {p: 3 for p in SEVEN}
    assert kala_sarpa_planets(planets, 1, 7) == list(SEVEN)

    # Same arc the other way around (signs 8-12).
    planets = {p: 9 for p in SEVEN}
    assert kala_sarpa_planets(planets, 1, 7) == list(SEVEN)


def test_kala_sarpa_broken_by_split_arc_or_node_conjunction():
    # Split across both arcs -> no yoga.
    split = {p: (3 if i % 2 == 0 else 9) for i, p in enumerate(SEVEN)}
    assert kala_sarpa_planets(split, 1, 7) == []

    # Any planet conjunct a node cancels the pattern.
    conjunct = {p: 3 for p in SEVEN}
    conjunct["Venus"] = 7  # with Ketu
    assert kala_sarpa_planets(conjunct, 1, 7) == []


def test_kala_sarpa_sample_chart_is_not_falsely_flagged(demo):
    d1 = demo[0]
    profile = detect_yogas(d1, None, None)
    # This chart's planets are split across both arcs, so the old per-planet
    # logic wrongly flagged Moon/Jupiter/Saturn; the arc test must not.
    assert profile.kala_sarpa_active is False
    assert not [y for y in profile.yogas if "Kala Sarpa" in y.yoga_name]


# ---------------------------------------------------------------------------
# Bug 11 — window merge compared enum .value lexicographically
# ---------------------------------------------------------------------------

def test_window_merge_keeps_stronger_confidence():
    from SweetAstro.src.prediction.marriage_timing import (
        MarriageStrength, MarriageTimingEngine, MarriageWindow,
    )
    engine = object.__new__(MarriageTimingEngine)  # method uses no instance state
    high = MarriageWindow(
        start_date=datetime(2028, 1, 1), end_date=datetime(2028, 2, 1),
        confidence=MarriageStrength.HIGH, indicators=[],
        mahadasha_lord="Venus", antardasha_lord="Sun",
    )
    moderate = MarriageWindow(
        start_date=datetime(2028, 2, 5), end_date=datetime(2028, 3, 1),
        confidence=MarriageStrength.MODERATE, indicators=[],
        mahadasha_lord="Venus", antardasha_lord="Sun",
    )
    merged = engine._merge_overlapping_windows([high, moderate])
    assert len(merged) == 1
    # Old lexicographic compare picked "Moderate" because 'M' > 'H'.
    assert merged[0].confidence is MarriageStrength.HIGH


# ---------------------------------------------------------------------------
# Bug 12 — duplicate Arudha implementations could drift
# ---------------------------------------------------------------------------

def test_arudha_single_source_of_truth(demo):
    from SweetAstro.src.core.arudha import calculate_arudha_pada
    from SweetAstro.src.core.jaimini import _compute_bhava_arudha

    d1 = demo[0]
    for house in range(1, 13):
        assert (_compute_bhava_arudha(d1, house)
                == calculate_arudha_pada(d1, house).sign_index), house


# ---------------------------------------------------------------------------
# Bug 13 — D9 dignity applied D1 moolatrikona ranges to projected degrees
# ---------------------------------------------------------------------------

def test_d9_dignity_has_no_projected_moolatrikona():
    from SweetAstro.src.core.navamsa import calculate_navamsa_chart

    d1 = calculate_d1_chart(1995, 5, 28, 12, 0, 0, 5.5, 28.6, 77.2)
    d9 = calculate_navamsa_chart(d1)
    assert all(p.d9_dignity != "Moolatrikona" for p in d9.planets.values())


# ---------------------------------------------------------------------------
# Bug 14 — solar return overshot into the next year for sidereal Sun >258 deg
# ---------------------------------------------------------------------------

def test_solar_return_stays_inside_the_requested_year():
    from SweetAstro.src.core.varshaphala import solar_return_datetime

    d1 = calculate_d1_chart(1990, 1, 10, 12, 0, 0, 5.5, 28.6, 77.2)
    sun_lon = d1.planets["Sun"].longitude
    for year in (2025, 2026):
        result = solar_return_datetime(sun_lon, year)
        assert result.year == year, (sun_lon, year, result)
