"""
Unit Tests for Transit (Gochara) & Double Transit Engine.
"""

import pytest
from datetime import datetime
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.transits import get_transit_positions, evaluate_double_transit


def test_transit_positions_calculation():
    target_dt = datetime(2028, 3, 15, 12, 0, 0)
    transits = get_transit_positions(target_dt)

    assert "Jupiter" in transits
    assert "Saturn" in transits
    assert "Rahu" in transits
    assert "Ketu" in transits

    for p in ["Jupiter", "Saturn"]:
        pos = transits[p]
        assert 1 <= pos.sign_index <= 12
        assert len(pos.aspected_sign_indices) > 0


def test_double_transit_evaluation():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    target_dt = datetime(2028, 3, 15, 12, 0, 0)

    result = evaluate_double_transit(d1, target_dt)
    assert isinstance(result.is_active, bool)
    assert 0.0 <= result.total_transit_score <= 100.0
    assert len(result.description) > 0


def test_transit_tz_offset_is_explicit():
    # Naive datetimes are UTC by default; passing a local offset must shift
    # the computed sky (Moon moves ~0.55 deg/hour).
    target_dt = datetime(2028, 3, 15, 6, 0, 0)
    utc_pos = get_transit_positions(target_dt, planets=["Moon"])["Moon"]
    shifted = get_transit_positions(target_dt, planets=["Moon"], tz_offset_hours=5.5)["Moon"]
    assert (utc_pos.degree_in_sign != shifted.degree_in_sign
            or utc_pos.sign_index != shifted.sign_index)

    gochara_shifted = evaluate_double_transit(
        calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090),
        target_dt, tz_offset_hours=5.5,
    )
    assert 0.0 <= gochara_shifted.total_transit_score <= 100.0
