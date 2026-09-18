"""
Unit Tests for D9 Navamsa Chart Engine.
"""

import pytest
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart, calculate_navamsa_sign_index
from SweetAstro.src.core.constants import INDEX_TO_SIGN


def test_navamsa_sign_index_mapping():
    # 0° Aries -> 1st Navamsa -> Aries (index 1)
    sign_idx, deg = calculate_navamsa_sign_index(0.0)
    assert sign_idx == 1
    assert INDEX_TO_SIGN[sign_idx] == "Aries"

    # 3° 20' Aries (3.33333°) -> 2nd Navamsa -> Taurus (index 2)
    sign_idx, deg = calculate_navamsa_sign_index(3.5)
    assert sign_idx == 2
    assert INDEX_TO_SIGN[sign_idx] == "Taurus"

    # 30° (0° Taurus) -> Earth sign -> 1st Navamsa of Taurus is Capricorn (index 10)
    sign_idx, deg = calculate_navamsa_sign_index(30.1)
    assert sign_idx == 10
    assert INDEX_TO_SIGN[sign_idx] == "Capricorn"

    # 60° (0° Gemini) -> Air sign -> 1st Navamsa of Gemini is Libra (index 7)
    sign_idx, deg = calculate_navamsa_sign_index(60.1)
    assert sign_idx == 7
    assert INDEX_TO_SIGN[sign_idx] == "Libra"

    # 90° (0° Cancer) -> Water sign -> 1st Navamsa of Cancer is Cancer (index 4)
    sign_idx, deg = calculate_navamsa_sign_index(90.1)
    assert sign_idx == 4
    assert INDEX_TO_SIGN[sign_idx] == "Cancer"


def test_navamsa_chart_calculation():
    d1 = calculate_d1_chart(1990, 8, 20, 10, 15, 0, 5.5, 28.6139, 77.2090)
    d9 = calculate_navamsa_chart(d1)

    assert 1 <= d9.ascendant_d9_sign_index <= 12
    assert d9.seventh_house_sign is not None
    assert d9.seventh_house_lord is not None

    for p_name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        assert p_name in d9.planets
        p_state = d9.planets[p_name]
        assert 1 <= p_state.d9_sign_index <= 12
        assert 1 <= p_state.d9_house <= 12
