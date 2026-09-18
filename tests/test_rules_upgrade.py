"""Rule engine upgrades: exceptions, new condition types, data integrity fixes."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.dasha import DashaPeriod
from SweetAstro.src.core.jaimini import calculate_chara_karakas, calculate_jaimini_points
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.core.transits import get_transit_positions
from SweetAstro.src.rules.evaluator import RuleEvaluator
from SweetAstro.src.rules.loader import RuleCatalog
from SweetAstro.src.rules.schema import ClassicalRule, RuleCondition, RuleSource

RULES_DIR = Path(__file__).parent.parent / "data" / "rules"


def _chart_bundle():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)
    d9 = calculate_navamsa_chart(d1)
    karakas = calculate_chara_karakas(d1)
    jaimini_pts = calculate_jaimini_points(d1, d9)
    return d1, d9, karakas, jaimini_pts


def _catalog_with(rule: ClassicalRule) -> RuleCatalog:
    catalog = RuleCatalog()
    catalog.rules = {rule.rule_id: rule}
    return catalog


def _test_rule(**overrides) -> ClassicalRule:
    base = dict(
        rule_id="T-1", domain="Test", category="promise",
        source=RuleSource(book="Test", chapter=1),
        conditions=[RuleCondition(entity="lagna_lord", condition_type="in_house", values=["1"])],
        result="test", base_weight=5.0, interpretation="test",
    )
    base.update(overrides)
    return ClassicalRule(**base)


def test_exception_conditions_cancel_a_matching_rule():
    d1, d9, karakas, jaimini_pts = _chart_bundle()
    lagna_lord = d1.houses[1].lord
    house = d1.planets[lagna_lord].house
    condition = RuleCondition(entity="lagna_lord", condition_type="in_house", values=[str(house)])

    without_exception = _test_rule(conditions=[condition])
    report = RuleEvaluator(_catalog_with(without_exception)).evaluate(
        d1, d9, karakas, jaimini_pts, datetime(2026, 1, 1))
    assert "T-1" in [m.rule_id for m in report.matched_rules]

    with_exception = _test_rule(conditions=[condition], exception_conditions=[condition])
    report2 = RuleEvaluator(_catalog_with(with_exception)).evaluate(
        d1, d9, karakas, jaimini_pts, datetime(2026, 1, 1))
    assert "T-1" not in [m.rule_id for m in report2.matched_rules]


def test_new_condition_types():
    d1, d9, karakas, jaimini_pts = _chart_bundle()
    evaluator = RuleEvaluator(RuleCatalog())
    lagna_lord = d1.houses[1].lord
    lagna_sign = d1.planets[lagna_lord].sign
    transits = get_transit_positions(datetime(2026, 6, 1, 12))

    def check(cond):
        return evaluator._check_condition(cond, d1, d9, None, None, transits,
                                          karakas, jaimini_pts)

    assert check(RuleCondition(entity="lagna_lord", condition_type="in_sign", values=[lagna_sign])) is True
    assert check(RuleCondition(entity="lagna_lord", condition_type="in_sign", values=["Notasign"])) is False
    assert check(RuleCondition(entity="lagna_lord", condition_type="dignity_at_least", values=["Debilitated"])) is True
    assert check(RuleCondition(entity="lagna_lord", condition_type="conjunct_with", values=[lagna_lord])) is True

    house = ((transits["Jupiter"].sign_index - d1.ascendant_sign_index) % 12) + 1
    assert check(RuleCondition(entity="transit_jupiter", condition_type="transit_in_house",
                               target=str(house))) is True
    assert check(RuleCondition(entity="transit_jupiter", condition_type="transit_in_house",
                               target="13")) is False


def test_unknown_condition_type_logs_and_is_unmet(caplog):
    d1, d9, karakas, jaimini_pts = _chart_bundle()
    evaluator = RuleEvaluator(RuleCatalog())
    with caplog.at_level("WARNING", logger="sweetastro.rules"):
        result = evaluator._check_condition(
            RuleCondition(entity="Jupiter", condition_type="made_up_type"),
            d1, d9, None, None, None, karakas, jaimini_pts)
    assert result is False
    assert "Unsupported rule condition type" in caplog.text


def test_active_dasha_lord_aspects_planet():
    d1, d9, karakas, jaimini_pts = _chart_bundle()
    evaluator = RuleEvaluator(RuleCatalog())
    target = "Venus"
    lord = next((p for p, st in d1.planets.items()
                 if d1.planets[target].house in st.aspecting_houses and p not in ("Rahu", "Ketu")), None)
    assert lord is not None, "chart should have some planet aspecting Venus's house"

    period = DashaPeriod(level="MD", lord=lord, start_date=datetime(2020, 1, 1),
                         end_date=datetime(2040, 1, 1), duration_days=7305.0, parent_md=lord)
    dasha = SimpleNamespace(mahadasha=lord, antardasha=lord, pratyantardasha=lord,
                            md_period=period, ad_period=period, pd_period=period)
    assert evaluator._check_condition(
        RuleCondition(entity="active_dasha_lord", condition_type="aspects_planet", target=target),
        d1, d9, dasha, None, None, karakas, jaimini_pts) is True


def test_stability_category_is_scored():
    d1, d9, karakas, jaimini_pts = _chart_bundle()
    catalog = RuleCatalog()
    catalog.load_from_directory(RULES_DIR)
    report = RuleEvaluator(catalog).evaluate(d1, d9, karakas, jaimini_pts, datetime(2026, 1, 1))
    assert isinstance(report.stability_score, float)
    assert report.stability_score >= 0.0


def test_rule_data_fixes_are_present():
    catalog = RuleCatalog()
    catalog.load_from_directory(RULES_DIR)

    mar_0042 = catalog.get_rule("MAR-0042")
    assert mar_0042.conditions[0].entity == "darakaraka"
    assert mar_0042.conditions[0].values == ["1", "4", "5", "7", "9", "10"]

    mar_0043 = catalog.get_rule("MAR-0043")
    assert mar_0043.conditions[0].target == "upapada_lagna"

    mar_0026 = catalog.get_rule("MAR-0026")
    assert mar_0026.conditions[0].condition_type == "in_house"
    assert mar_0026.conditions[0].values == ["7"]

    mar_0035 = catalog.get_rule("MAR-0035")
    assert mar_0035.conditions[0].target == "7th_lord"

    mar_0010 = catalog.get_rule("MAR-0010")
    assert mar_0010.exception_conditions
    assert any(c.condition_type == "dignity_at_least" for c in mar_0010.exception_conditions)

    mar_0001 = catalog.get_rule("MAR-0001")
    assert "is guaranteed" not in mar_0001.interpretation.lower()
    assert "not a guarantee" in mar_0001.interpretation.lower()
