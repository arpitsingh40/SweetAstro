"""
Unit Tests for Prediction Hierarchy & Sensitivity Engine.
"""

from pathlib import Path
import pytest
from datetime import datetime
from SweetAstro.src.service import SweetAstroEngine


def test_full_prediction_workflow():
    rules_dir = Path(__file__).parent.parent / "data" / "rules"
    engine = SweetAstroEngine(rules_dir=rules_dir)

    answer = engine.predict_marriage(
        year=1995, month=5, day=15,
        hour=14, minute=30, second=0.0,
        tz_offset=5.5,
        lat=28.6139, lon=77.2090,
        name="Test Native",
        search_start_age=25,
        search_end_age=35
    )

    # 1. Validate User-Facing Answer is calibrated, not an absolute claim
    assert "💍 The clearest marriage window" in answer.bold_headline
    assert "not a prediction" in answer.bold_headline
    assert "You will get married in" not in answer.bold_headline
    assert len(answer.why_saying_this) > 50
    assert len(answer.what_happens_before_then) > 50
    assert len(answer.partner_and_marriage_profile) > 50
    assert len(answer.closing_question) > 10

    # 2. Validate Internal Probability & Evidence Bookkeeping (Point 30)
    payload = answer.internal_payload
    assert payload.event == "Marriage"
    assert payload.month_score > 0.0
    assert payload.year_score > 0.0
    assert payload.birth_time_stability_pct >= 0.0
    assert payload.stability_classification in ["High", "Moderate", "Birth-Time Sensitive"]
    assert len(payload.why_not_other_months["monthly_breakdown"]) == 12
