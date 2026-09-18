"""P1/P2 tests: classical Shadbala components, sensitive points, Rajayoga."""

import math
from datetime import datetime

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.classical_shadbala import (
    NAISARGIKA_BALA, RASHMI_MINIMUM, ayana_bala, calculate_classical_shadbala,
    chesta_bala, dig_bala_classical, dina_bala, drekkana_bala, hora_lord,
    kendradi_bala, natonnata_bala, ojhayugma_bala, paksha_bala,
    saptavargaja_bala, tribhaga_bala, uchcha_bala,
)
from SweetAstro.src.core.sensitive_points import (
    is_pushkara_bhaga, is_pushkara_navamsa,
)
from SweetAstro.src.core.strength import assess_planet_strength
from SweetAstro.src.core.yogas import detect_yogas

BIRTH = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart():
    return calculate_d1_chart(*BIRTH)


# ------------------------------------------------------------ components

def test_uchcha_bala_bounds():
    # Sun exalted at 10 Aries -> 60; debilitated at 10 Libra -> 0
    assert uchcha_bala("Sun", 10.0) == 60.0
    assert uchcha_bala("Sun", 190.0) == 0.0
    assert 0.0 <= uchcha_bala("Moon", 123.0) <= 60.0


def test_naisargika_and_minimums():
    assert NAISARGIKA_BALA["Sun"] == 60.0
    assert NAISARGIKA_BALA["Saturn"] < NAISARGIKA_BALA["Mars"]
    assert sorted(NAISARGIKA_BALA.values(), reverse=True) == [
        NAISARGIKA_BALA[p] for p in ("Sun", "Moon", "Venus", "Jupiter",
                                     "Mercury", "Mars", "Saturn")]
    assert RASHMI_MINIMUM["Mercury"] == 7.0


def test_parity_house_drekkana_dig():
    assert ojhayugma_bala("Sun", 1) == 15.0      # odd sign, odd-preferring
    assert ojhayugma_bala("Sun", 2) == 0.0
    assert ojhayugma_bala("Moon", 4) == 15.0     # even sign, Moon prefers even
    assert ojhayugma_bala("Moon", 1) == 0.0

    assert kendradi_bala(1) == 60.0 and kendradi_bala(2) == 30.0 and kendradi_bala(3) == 15.0

    assert drekkana_bala("Jupiter", 5.0) == 15.0
    assert drekkana_bala("Mercury", 15.0) == 15.0
    assert drekkana_bala("Moon", 25.0) == 15.0
    assert drekkana_bala("Jupiter", 15.0) == 0.0

    # Dig: strong point at Lagna degree for Jupiter, opposite point zero
    d1 = _chart()
    assert dig_bala_classical("Jupiter", d1.ascendant_deg, d1.ascendant_deg) == 60.0
    assert dig_bala_classical("Jupiter", (d1.ascendant_deg + 180) % 360,
                              d1.ascendant_deg) == 0.0


def test_kala_components():
    assert natonnata_bala("Mercury", True) == 60.0
    assert natonnata_bala("Sun", True) == 60.0
    assert natonnata_bala("Sun", False) == 0.0
    assert natonnata_bala("Moon", False) == 60.0

    assert paksha_bala("Jupiter", 180.0) == 60.0   # full moon
    assert paksha_bala("Jupiter", 0.0) == 0.0      # new moon
    assert paksha_bala("Mars", 0.0) == 60.0        # malefic at new moon
    assert paksha_bala("Moon", 180.0) == 120.0     # Moon doubled

    assert tribhaga_bala("Mercury", 7.0) == 60.0
    assert tribhaga_bala("Sun", 11.0) == 60.0
    assert tribhaga_bala("Saturn", 17.0) == 60.0
    assert tribhaga_bala("Jupiter", 3.0) == 60.0

    assert dina_bala("Moon", 0) == 45.0            # Monday
    assert dina_bala("Sun", 0) == 0.0
    assert hora_lord(0, 6.0) == "Moon"             # Monday first hora
    assert hora_lord(0, 7.0) == "Saturn"           # Chaldean sequence


def test_chesta_and_ayana():
    assert chesta_bala("Saturn", -0.01, True) == 60.0
    assert chesta_bala("Saturn", 0.0335, False) == 0.0
    assert 0.0 <= ayana_bala("Sun", 0.0, 0.409) <= 60.0


def test_saptavargaja_and_full_assembly():
    d1 = _chart()
    sapta = saptavargaja_bala(d1, "Venus")
    assert 0.0 < sapta <= 7 * 45.0

    cb = calculate_classical_shadbala(
        d1, "Venus", is_daytime=True, hour_local=14.5, weekday=0,
        sun_moon_elongation=120.0,
    )
    assert cb.total_virupas > 0
    assert cb.total_rupas == round(cb.total_virupas / 60.0, 2)
    assert cb.category in ("Strong", "Borderline", "Weak")
    # Ishta/Kashta derivation from Uchcha x Chesta
    assert math.isclose(cb.ishta_phala,
                        round(math.sqrt(cb.uchcha * cb.chesta), 2), abs_tol=0.05)
    assert math.isclose(cb.kashta_phala,
                        round(math.sqrt((60 - cb.uchcha) * (60 - cb.chesta)), 2),
                        abs_tol=0.05)
    assert abs(sum(cb.components.values()) - cb.total_virupas) < 0.05


# ------------------------------------------------------------ P2 points

def test_pushkara_navamsa_and_bhaga():
    # C. S. Patel ranges: Aries 20-23°20'; Virgo 11°30' outside; Aquarius 24°05' inside
    assert is_pushkara_navamsa(1, 21.0) is True
    assert is_pushkara_navamsa(1, 27.5) is True    # fire second range 26°40'-30°
    assert is_pushkara_navamsa(1, 25.0) is False   # gap between the two ranges
    assert is_pushkara_navamsa(6, 11.5) is False
    assert is_pushkara_navamsa(11, 24.0833) is True

    # Jataka Parijata Bhaga: Aries 21, Aquarius 19
    assert is_pushkara_bhaga(1, 21.4) is True
    assert is_pushkara_bhaga(1, 22.0) is False
    assert is_pushkara_bhaga(11, 24.0, convention="patel") is True
    assert is_pushkara_bhaga(11, 24.0, convention="jataka_parijata") is False


# ------------------------------------------------------------ integration

def test_deep_assessment_carries_classical_strength():
    d1 = _chart()
    base = assess_planet_strength(d1, "Venus", None, ["Venus"])
    assert base.classical_shadbala is None

    deep = assess_planet_strength(
        d1, "Venus", None, ["Venus"],
        birth_dt=datetime(1995, 5, 15, 14, 30), classical=True,
    )
    assert deep.classical_shadbala is not None
    assert deep.classical_shadbala["rupas"] > 0
    assert deep.classical_shadbala["category"] in ("Strong", "Borderline", "Weak")
    assert isinstance(deep.sensitive, (str, type(None)))


def test_rajayoga_is_lord_based_and_neecha_bhanga_detected():
    d1 = _chart()
    profile = detect_yogas(d1, None, None)
    raja = [y for y in profile.yogas if "Rajayoga" in y.yoga_name]
    for yoga in raja:
        assert yoga.yoga_type == "rajayoga"
    # Neecha Bhanga only for genuinely debilitated planets
    for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        nb = [y for y in profile.yogas if y.yoga_name == f"Neecha Bhanga ({planet})"]
        if nb:
            assert d1.planets[planet].dignity == "Debilitated"


# ------------------------------------------------------------------- P3

def test_varsha_masa_lords_are_weekday_lords():
    from SweetAstro.src.core.strength_extras import varsha_masa_lords

    d1 = _chart()
    lords = varsha_masa_lords(datetime(1995, 5, 15, 14, 30), 5.5,
                              d1.planets["Sun"].longitude)
    weekday_lords = {"Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"}
    assert lords["varsha_lord"] in weekday_lords
    assert lords["masa_lord"] in weekday_lords
    assert lords["varsha_ingress"] <= "1995-05-15"
    assert lords["masa_ingress"] <= "1995-05-15"
    assert varsha_masa_lords(datetime(1995, 5, 15, 14, 30), 5.5,
                             d1.planets["Sun"].longitude) == lords


def test_bhava_bala_has_twelve_houses():
    from SweetAstro.src.core.strength_extras import calculate_bhava_bala

    rows = calculate_bhava_bala(_chart())
    assert len(rows) == 12
    for row in rows[:12]:
        assert 1 <= row.house <= 12
        assert row.category in ("Strong", "Moderate", "Weak")
        assert abs(row.total - round(row.bhavadhipati + row.drishti, 2)) < 1e-9


def test_dasha_agreement_structure_and_verdict():
    from SweetAstro.src.core.strength_extras import dasha_agreement_for_planet

    d1 = _chart()
    birth = datetime(1995, 5, 15, 14, 30)
    result = dasha_agreement_for_planet(d1, birth, birth, "Venus")
    assert result.planet == "Venus"
    assert result.agreement_count == sum(
        (result.vimshottari_match, result.yogini_match, result.chara_match))
    assert result.verdict in ("cross-confirmed", "single-system", "not activated")
    assert "never stacked" in result.note
