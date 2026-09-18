"""Planet factors (P0) tests: maitri, avasthas, junctions, yuddha, exchanges."""

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.planet_factors import (
    BALADI_STATES, baladi_avastha, compound_relation, compute_planet_factors,
    deeptadi_avastha, detect_parivartana, graha_yuddha_pairs, is_gandanta,
    is_sandhi, jagradadi_avastha, natural_relation, parivartana_type,
    temporal_relation,
)
from SweetAstro.src.core.strength import assess_planet_strength

BIRTH_ARGS = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart():
    return calculate_d1_chart(*BIRTH_ARGS)


# ------------------------------------------------------------------ maitri

def test_temporal_relation_groups():
    assert temporal_relation(1, 3) == "Friend"    # 3rd
    assert temporal_relation(1, 4) == "Friend"    # 4th
    assert temporal_relation(12, 1) == "Friend"   # 2nd (wraps)
    assert temporal_relation(1, 6) == "Enemy"     # 6th
    assert temporal_relation(1, 1) == "Enemy"     # same sign
    assert temporal_relation(5, 1) == "Enemy"     # 9th


def test_compound_panchadha_table():
    assert compound_relation("Friend", "Friend") == "Adhimitra"
    assert compound_relation("Friend", "Enemy") == "Sama"
    assert compound_relation("Neutral", "Friend") == "Mitra"
    assert compound_relation("Neutral", "Enemy") == "Shatru"
    assert compound_relation("Enemy", "Friend") == "Sama"
    assert compound_relation("Enemy", "Enemy") == "Adhishatru"


def test_natural_relation_and_node_default():
    assert natural_relation("Sun", "Venus") == "Enemy"
    assert natural_relation("Sun", "Moon") == "Friend"
    assert natural_relation("Jupiter", "Saturn") == "Neutral"
    assert natural_relation("Rahu", "Sun") == "Neutral"  # nodes default


# ----------------------------------------------------------------- avasthas

def test_baladi_avastha_odd_and_even_signs():
    assert baladi_avastha(1, 3.0) == "Bala"
    assert baladi_avastha(1, 6.0) == "Kumara"
    assert baladi_avastha(1, 15.0) == "Yuva"
    assert baladi_avastha(1, 27.0) == "Mrita"
    # Even signs run in reverse
    assert baladi_avastha(2, 3.0) == "Mrita"
    assert baladi_avastha(2, 15.0) == "Yuva"
    assert baladi_avastha(2, 27.0) == "Bala"
    assert set(BALADI_STATES) == {"Bala", "Kumara", "Yuva", "Vriddha", "Mrita"}


def test_jagradadi_and_deeptadi_states():
    assert jagradadi_avastha("Own") == "Jagrat"
    assert jagradadi_avastha("Friend") == "Swapna"
    assert jagradadi_avastha("Debilitated") == "Supta"

    assert deeptadi_avastha("Exalted", is_combust=True,
                            has_malefic_conj=True, has_benefic_conj=False) == "Deepta"
    assert deeptadi_avastha("Own", is_combust=False,
                            has_malefic_conj=False, has_benefic_conj=False) == "Swastha"
    assert deeptadi_avastha("Friend", is_combust=False,
                            has_malefic_conj=False, has_benefic_conj=False) == "Mudita"
    assert deeptadi_avastha("Neutral", is_combust=False,
                            has_malefic_conj=False, has_benefic_conj=True) == "Shanta"
    assert deeptadi_avastha("Neutral", is_combust=False,
                            has_malefic_conj=False, has_benefic_conj=False) == "Dina"
    assert deeptadi_avastha("Enemy", is_combust=False,
                            has_malefic_conj=False, has_benefic_conj=False) == "Duhkhita"
    assert deeptadi_avastha("Debilitated", is_combust=True,
                            has_malefic_conj=False, has_benefic_conj=False) == "Vikala"
    assert deeptadi_avastha("Debilitated", is_combust=False,
                            has_malefic_conj=True, has_benefic_conj=False) == "Khala"
    assert deeptadi_avastha("Debilitated", is_combust=False,
                            has_malefic_conj=False, has_benefic_conj=False) == "Kopita"


# ----------------------------------------------------------- junctions

def test_sandhi_and_gandanta_boundaries():
    assert is_sandhi(0.5) is True
    assert is_sandhi(29.5) is True
    assert is_sandhi(1.0) is False
    assert is_sandhi(15.0) is False

    assert is_gandanta(12, 27.0) is True    # Pisces ending
    assert is_gandanta(12, 25.0) is False
    assert is_gandanta(1, 2.0) is True      # Aries beginning
    assert is_gandanta(9, 3.0) is True      # Sagittarius beginning
    assert is_gandanta(2, 2.0) is False     # Taurus not a fire start/water end


# ------------------------------------------------------------- yuddha

def test_graha_yuddha_winner_and_orb():
    war = graha_yuddha_pairs({"Mars": 10.0, "Venus": 10.5})
    assert "won" in war["Mars"] and "Venus" in war["Mars"]
    assert "lost" in war["Venus"] and "Mars" in war["Venus"]

    assert graha_yuddha_pairs({"Mars": 10.0, "Venus": 11.5}) == {}
    # Luminaries never go to war
    assert graha_yuddha_pairs({"Sun": 10.0, "Moon": 10.2}) == {}
    # Different signs: no war even within 1 degree
    assert graha_yuddha_pairs({"Mars": 29.8, "Venus": 30.1}) == {}


# -------------------------------------------------------- parivartana

def test_parivartana_detection_and_types():
    # Sun in Cancer (Moon's sign), Moon in Leo (Sun's sign)
    signs = {"Sun": 4, "Moon": 5, "Mars": 1, "Mercury": 3,
             "Jupiter": 9, "Venus": 2, "Saturn": 11}
    exchanges = detect_parivartana(signs, {"Sun": 1, "Moon": 7, "Mars": 9,
                                           "Mercury": 3, "Jupiter": 6,
                                           "Venus": 2, "Saturn": 11})
    assert any(ex.startswith("Sun<->Moon") for ex in exchanges)
    assert "(Maha, H1/H7)" in exchanges[0]

    assert parivartana_type(1, 7) == "Maha"
    assert parivartana_type(6, 8) == "Khala"
    assert parivartana_type(1, 8) == "Dainya"
    # Non-mutual placement is not an exchange
    assert detect_parivartana({"Sun": 4, "Moon": 6}) == []


# ------------------------------------------------------------ integration

def test_compute_planet_factors_on_real_chart():
    d1 = _chart()
    for planet in ("Sun", "Moon", "Venus"):
        factors = compute_planet_factors(d1, planet)
        assert factors.planet == planet
        assert len(factors.tatkalika) == 8
        assert len(factors.compound) == 8
        assert factors.baladi in BALADI_STATES
        assert factors.jagradadi in ("Jagrat", "Swapna", "Supta")
        assert factors.deeptadi in ("Deepta", "Swastha", "Mudita", "Shanta",
                                    "Dina", "Duhkhita", "Vikala", "Khala", "Kopita")
        assert factors.bav_bindus is None or 0 <= factors.bav_bindus <= 8


def test_strength_assessment_carries_factors():
    d1 = _chart()
    sa = assess_planet_strength(d1, "Venus", None, ["Venus", "Jupiter"])
    assert sa.compound_friendship
    assert set(sa.avasthas) == {"baladi", "jagradadi", "deeptadi"}
    assert sa.bav_bindus is not None and 0 <= sa.bav_bindus <= 8
    assert isinstance(sa.sandhi, bool) and isinstance(sa.gandanta, bool)


def test_payload_renders_factor_line():
    from SweetAstro.src.chat.payload import build_chart_payload
    from SweetAstro.src.consumer import answer_question

    result = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=26.9124, lon=75.7873,
        question="wealth and income", time_reliable=True,
    )
    payload = build_chart_payload(
        result, name="Ananya", dob="1995-05-15", tob="14:30:00", tz_offset=5.5,
        place="Jaipur, India", geo_note="Geocoded (mock).", time_reliable=True,
        question="wealth and income", topic="wealth",
    )
    assert "factors: avasthas" in payload
    assert "BAV " in payload
