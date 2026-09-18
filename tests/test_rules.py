"""
Unit Tests for Classical Rule Loading & Rule Evaluator.
"""

from pathlib import Path
import pytest
from datetime import datetime
from SweetAstro.src.rules.loader import RuleCatalog
from SweetAstro.src.rules.evaluator import RuleEvaluator
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.core.jaimini import calculate_chara_karakas, calculate_jaimini_points
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
from SweetAstro.src.core.transits import evaluate_double_transit, get_transit_positions


def test_rule_catalog_loading():
    rules_dir = Path(__file__).parent.parent / "data" / "rules"
    catalog = RuleCatalog()
    loaded_count = catalog.load_from_directory(rules_dir)

    assert loaded_count >= 10
    assert catalog.get_rule("MAR-0001") is not None
    assert catalog.get_rule("MAR-0010") is not None
    assert catalog.get_rule("MAR-0020") is not None
    assert catalog.get_rule("MAR-0030") is not None


def test_rule_evaluator_execution():
    rules_dir = Path(__file__).parent.parent / "data" / "rules"
    catalog = RuleCatalog()
    catalog.load_from_directory(rules_dir)
    evaluator = RuleEvaluator(catalog)

    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    d9 = calculate_navamsa_chart(d1)
    karakas = calculate_chara_karakas(d1)
    jaimini_pts = calculate_jaimini_points(d1, d9)

    birth_dt = datetime(1995, 5, 15, 14, 30, 0)
    timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)

    target_dt = datetime(2025, 6, 15, 12, 0, 0)
    dasha = get_dasha_at_date(timeline, target_dt)
    dt_result = evaluate_double_transit(d1, target_dt)
    transits = get_transit_positions(target_dt)

    report = evaluator.evaluate(
        d1, d9, karakas, jaimini_pts, target_dt, dasha, dt_result, transits
    )

    assert report.positive_score >= 0.0
    assert report.net_score >= 0.0
    assert isinstance(report.matched_rules, list)
