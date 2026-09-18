"""
Unit Tests for Astronomical Ephemeris & D1 Chart Engine.
"""

import pytest
from datetime import datetime
from SweetAstro.src.core.constants import SIGNS, SIGN_LORDS
from SweetAstro.src.core.ephemeris import (
    datetime_to_julian_day, calculate_lahiri_ayanamsha,
    calculate_sidereal_time, calculate_ascendant, calculate_planet_positions
)
from SweetAstro.src.core.chart import calculate_d1_chart


def test_julian_day_calculation():
    # Standard astronomical benchmark: 2000-01-01 12:00:00 UT = JD 2451545.0
    jd = datetime_to_julian_day(2000, 1, 1, 12, 0, 0, tz_offset_hours=0.0)
    assert abs(jd - 2451545.0) < 1e-4


def test_lahiri_ayanamsha_near_j2000():
    # Standard Lahiri Ayanamsha at J2000.0 is ~23.857 degrees (23° 51' 26")
    jd = 2451545.0
    ayan = calculate_lahiri_ayanamsha(jd)
    assert 23.5 < ayan < 24.2


def test_d1_chart_structure():
    # Sample birth data: 1995-05-15 14:30:00 at New Delhi
    chart = calculate_d1_chart(
        year=1995, month=5, day=15,
        hour=14, minute=30, second=0,
        tz_offset_hours=5.5,
        lat=28.6139, lon=77.2090
    )

    # Basic validations
    assert chart.ascendant_sign in SIGNS
    assert 1 <= chart.ascendant_sign_index <= 12
    assert 0.0 <= chart.ascendant_degree_in_sign < 30.0

    # Ensure all 9 planets are calculated
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        assert p in chart.planets
        p_state = chart.planets[p]
        assert 1 <= p_state.house <= 12
        assert p_state.sign in SIGNS
        assert 0.0 <= p_state.longitude < 360.0

    # Validate 7th house and 7th lord
    h7 = chart.seventh_house
    assert h7.house_num == 7
    assert h7.sign in SIGNS
    assert h7.lord == SIGN_LORDS[h7.sign]
    assert chart.seventh_lord.name == h7.lord
