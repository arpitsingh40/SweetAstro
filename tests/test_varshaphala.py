"""Varshaphala (annual chart) tests: solar return accuracy + Muntha cycle."""

from datetime import datetime

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import SIGN_LORDS
from SweetAstro.src.core.varshaphala import (
    compute_varshaphala, solar_return_datetime, sun_sidereal_longitude,
)


def _chart():
    return calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def test_solar_return_lands_on_natal_sun_longitude():
    d1 = _chart()
    natal_sun = d1.planets["Sun"].longitude % 360.0
    returned = solar_return_datetime(natal_sun, 2026)
    current = sun_sidereal_longitude(returned)
    diff = abs(((current - natal_sun + 180.0) % 360.0) - 180.0)
    assert diff < 0.01
    assert returned.year == 2026


def test_muntha_cycles_every_twelve_years():
    d1 = _chart()
    birth = datetime(1995, 5, 15, 14, 30)
    first = compute_varshaphala(d1, birth, 1995, 5.5, 26.9124, 75.7873)
    twelfth = compute_varshaphala(d1, birth, 2007, 5.5, 26.9124, 75.7873)
    assert first.muntha_sign == d1.ascendant_sign
    assert twelfth.muntha_sign == d1.ascendant_sign
    assert first.muntha_lord == SIGN_LORDS[d1.ascendant_sign]
    assert first.muntha_house_from_lagna == 1
    assert first.theme in ("supportive", "mixed", "challenging")
    assert first.varsha_lagna_sign in SIGN_LORDS
    assert "Panchavargiya" in first.note
