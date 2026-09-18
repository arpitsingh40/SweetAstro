"""
Unit Tests for Blind Backtest Runner & Tournament Engine.
"""

from pathlib import Path
import pytest
from SweetAstro.src.service import SweetAstroEngine


def test_blind_backtesting_on_verified_dataset():
    rules_dir = Path(__file__).parent.parent / "data" / "rules"
    dataset_path = Path(__file__).parent.parent / "data" / "test_charts" / "historical_verified.json"

    engine = SweetAstroEngine(rules_dir=rules_dir)
    metrics, records = engine.run_backtest(dataset_path)

    # Validate that all charts were evaluated blindly
    assert metrics.total_charts_tested == 5
    assert len(records) == 5

    # Check Prediction ID generation and blind tracking
    for r in records:
        assert r.prediction_id.startswith("SA-MAR-")
        assert r.actual_year > 1900
        assert r.predicted_year > 1900
        assert r.month_error >= 0.0

    # Validate metric bounds
    assert 0.0 <= metrics.top_1_year_accuracy <= 100.0
    assert 0.0 <= metrics.top_3_year_accuracy <= 100.0
    assert metrics.mean_absolute_error_months >= 0.0


@pytest.mark.slow
def test_method_tournament():
    rules_dir = Path(__file__).parent.parent / "data" / "rules"
    dataset_path = Path(__file__).parent.parent / "data" / "test_charts" / "historical_verified.json"

    engine = SweetAstroEngine(rules_dir=rules_dir)
    tournament_results = engine.run_tournament(dataset_path)

    assert len(tournament_results) == 5
    for res in tournament_results:
        assert res.model_name is not None
        assert res.metrics.total_charts_tested == 5
