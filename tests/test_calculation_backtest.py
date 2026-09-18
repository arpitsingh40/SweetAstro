"""
Calculation backtest — validates every astronomical/astrological calculation
against trusted, authenticated sources.

Reference sources
-----------------
[SE]        Swiss Ephemeris 2.10.03 (pyswisseph), Lahiri/Chitrapaksha sidereal
            mode — the reference implementation used by professional Vedic
            astrology software (derived from JPL DE ephemerides).
[SE-FROZEN] Values computed once from [SE] on 2026-09-12 and frozen below, so
            regressions are still detected if the library is unavailable.
[BPHS]      Brihat Parashara Hora Shastra classical divisional-chart and
            Vimshottari rules, with expected values computed by hand (the
            arithmetic is shown inline where non-obvious).

Run:  pytest tests/test_calculation_backtest.py -v
"""

import math
from datetime import datetime
from pathlib import Path

import pytest

from SweetAstro.src.core import ephemeris
from SweetAstro.src.core.chart import (
    calculate_d1_chart, _get_nakshatra_and_pada,
)
from SweetAstro.src.core.dasha import (
    calculate_vimshottari_timeline, get_dasha_at_date,
)
from SweetAstro.src.core.navamsa import calculate_navamsa_sign_index
from SweetAstro.src.core.vargas import varga_sign_index
from SweetAstro.src.core.constants import INDEX_TO_SIGN, NAKSHATRAS

DATA_DIR = Path(__file__).parent.parent / "data"

# ---------------------------------------------------------------------------
# Reference charts used across the suite
# ---------------------------------------------------------------------------
# label, year, month, day, hour, minute, tz_offset, lat, lon
REFERENCE_CHARTS = [
    ("demo_delhi", 1995, 5, 15, 14, 30, 5.5, 28.6139, 77.2090),
    ("london_1982", 1982, 6, 21, 21, 3, 1.0, 51.5074, -0.1278),
    ("nyc_1946", 1946, 6, 14, 10, 54, -4.0, 40.7128, -74.0060),
    ("sydney_south", 2000, 9, 15, 6, 30, 10.0, -33.8688, 151.2093),
    ("tromso_arctic", 1980, 1, 15, 3, 0, 1.0, 69.6492, 18.9553),
    ("equator_2024", 2024, 6, 1, 12, 0, 0.0, 0.0, 0.0),
]

PLANET_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

# ---------------------------------------------------------------------------
# [SE-FROZEN] Lahiri ayanamsha at reference Julian Days (pyswisseph 2.10.03)
# ---------------------------------------------------------------------------
AYANAMSHA_FROZEN = [
    (2451545.0, 23.857092),    # J2000.0 2000-01-01 12:00 UT
    (2415020.5, 22.460531),    # 1900-01-01 00:00 UT
    (2433282.5, 23.158725),    # 1950-01-01 00:00 UT
    (2469807.5, 24.555613),    # 2050-01-01 00:00 UT
    (2449852.875, 23.792378),  # 1995-05-15 09:00 UT (demo chart)
]

# ---------------------------------------------------------------------------
# [SE-FROZEN] Demo chart 1995-05-15 14:30 +05:30, New Delhi (28.6139, 77.2090)
# ---------------------------------------------------------------------------
DEMO_FROZEN = {
    "ayanamsha": 23.792378,
    "ascendant": 151.651742,   # Virgo 1.65 deg (sidereal)
    "Sun": 30.284033,
    "Moon": 217.485219,
    "Mars": 121.767180,
    "Mercury": 51.328802,
    "Jupiter": 228.821914,
    "Venus": 4.268300,
    "Saturn": 328.804248,
    "Rahu": 190.856536,
    "Ketu": 10.856536,
}

# J2000 tropical apparent Sun longitude [SE] — cross-check against almanacs
J2000_TROPICAL_SUN = 280.368920


# ===========================================================================
# 1. Ephemeris backend + frozen references
# ===========================================================================

def test_swisseph_available():
    """The authoritative ephemeris must be installed for production accuracy."""
    assert ephemeris.ephemeris_engine_name() == "swisseph", (
        "pyswisseph is not installed — charts fall back to the approximate Meeus "
        "engine. Install with: pip install pyswisseph"
    )


@pytest.mark.parametrize("jd,expected", AYANAMSHA_FROZEN)
def test_ayanamsha_matches_frozen_reference(jd, expected):
    assert ephemeris.calculate_lahiri_ayanamsha(jd) == pytest.approx(expected, abs=1e-4)


def test_demo_chart_matches_frozen_reference():
    chart = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    assert chart.ayanamsha == pytest.approx(DEMO_FROZEN["ayanamsha"], abs=1e-4)
    assert chart.ascendant_deg == pytest.approx(DEMO_FROZEN["ascendant"], abs=1e-4)
    for planet, expected in DEMO_FROZEN.items():
        if planet in ("ayanamsha", "ascendant"):
            continue
        assert chart.planets[planet].longitude == pytest.approx(expected, abs=1e-4), planet


def test_j2000_tropical_sun_sanity():
    """Independent almanac sanity check on the library configuration."""
    import swisseph as swe
    pos, _ = swe.calc_ut(2451545.0, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)
    assert pos[0] == pytest.approx(J2000_TROPICAL_SUN, abs=0.001)
    # Sidereal = tropical - ayanamsha
    assert (pos[0] - 23.857092) % 360 == pytest.approx(256.511828, abs=0.001)


# ===========================================================================
# 2. Engine wrapper vs direct Swiss Ephemeris calls (all reference charts)
# ===========================================================================

@pytest.mark.parametrize("label,y,mo,d,h,mi,tz,lat,lon", REFERENCE_CHARTS)
def test_planet_longitudes_match_swisseph(label, y, mo, d, h, mi, tz, lat, lon):
    import swisseph as swe

    if not ephemeris.HAS_SWISSEPH:
        pytest.skip("pyswisseph not installed")

    jd = ephemeris.datetime_to_julian_day(y, mo, d, h, mi, 0.0, tz)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    mapping = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
        "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
    }
    chart = calculate_d1_chart(y, mo, d, h, mi, 0.0, tz, lat, lon)

    for planet, pid in mapping.items():
        direct, _ = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SPEED)
        assert chart.planets[planet].longitude == pytest.approx(direct[0] % 360.0, abs=1e-6), \
            f"{label}/{planet}"
    # Ketu is exactly 180 degrees from Rahu
    expected_ketu = (chart.planets["Rahu"].longitude + 180.0) % 360.0
    assert chart.planets["Ketu"].longitude == pytest.approx(expected_ketu, abs=1e-9)


@pytest.mark.parametrize("label,y,mo,d,h,mi,tz,lat,lon", REFERENCE_CHARTS)
def test_ascendant_matches_swisseph(label, y, mo, d, h, mi, tz, lat, lon):
    import swisseph as swe

    if not ephemeris.HAS_SWISSEPH:
        pytest.skip("pyswisseph not installed")

    jd = ephemeris.datetime_to_julian_day(y, mo, d, h, mi, 0.0, tz)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', swe.FLG_SIDEREAL)
    chart = calculate_d1_chart(y, mo, d, h, mi, 0.0, tz, lat, lon)
    assert chart.ascendant_deg == pytest.approx(ascmc[0] % 360.0, abs=1e-6), label


@pytest.mark.parametrize("label,y,mo,d,h,mi,tz,lat,lon", REFERENCE_CHARTS)
def test_house_assignments_whole_sign(label, y, mo, d, h, mi, tz, lat, lon):
    chart = calculate_d1_chart(y, mo, d, h, mi, 0.0, tz, lat, lon)
    for h_num, house in chart.houses.items():
        expected_sign_idx = ((chart.ascendant_sign_index + h_num - 2) % 12) + 1
        assert house.sign_index == expected_sign_idx
    for planet, state in chart.planets.items():
        expected_house = ((state.sign_index - chart.ascendant_sign_index + 12) % 12) + 1
        assert state.house == expected_house, planet


# ===========================================================================
# 3. Fallback regression tests (the old fallback was 180 deg wrong)
# ===========================================================================

@pytest.mark.parametrize("label,y,mo,d,h,mi,tz,lat,lon", REFERENCE_CHARTS)
def test_fallback_ascendant_close_to_swisseph(monkeypatch, label, y, mo, d, h, mi, tz, lat, lon):
    """The built-in fallback (used only if pyswisseph is missing) must stay sane.

    Regression: an earlier formula returned the descendant (exactly 180 deg off).
    """
    if not ephemeris.HAS_SWISSEPH:
        pytest.skip("pyswisseph not installed")
    jd = ephemeris.datetime_to_julian_day(y, mo, d, h, mi, 0.0, tz)
    ayan = ephemeris.calculate_lahiri_ayanamsha(jd)
    trusted = ephemeris.calculate_ascendant(jd, lat, lon, ayan)
    monkeypatch.setattr(ephemeris, "HAS_SWISSEPH", False)
    fallback = ephemeris.calculate_ascendant(jd, lat, lon, ayan)
    diff = (fallback - trusted + 540.0) % 360.0 - 180.0
    assert abs(diff) < 0.05, f"{label}: fallback asc off by {diff:+.4f} deg"


@pytest.mark.parametrize("label,y,mo,d,h,mi,tz,lat,lon", REFERENCE_CHARTS)
def test_fallback_planets_within_accuracy_envelope(monkeypatch, label, y, mo, d, h, mi, tz, lat, lon):
    """Fallback positions must stay within their documented ~1 deg envelope."""
    if not ephemeris.HAS_SWISSEPH:
        pytest.skip("pyswisseph not installed")
    jd = ephemeris.datetime_to_julian_day(y, mo, d, h, mi, 0.0, tz)
    ayan = ephemeris.calculate_lahiri_ayanamsha(jd)
    trusted = ephemeris.calculate_planet_positions(jd, ayan)
    monkeypatch.setattr(ephemeris, "HAS_SWISSEPH", False)
    fallback = ephemeris.calculate_planet_positions(jd, ayan)
    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu"]:
        diff = (fallback[planet]["longitude"] - trusted[planet]["longitude"] + 540.0) % 360.0 - 180.0
        assert abs(diff) < 1.0, f"{label}/{planet}: off by {diff:+.4f} deg"
    # Sun speed regression (was 100x too large due to a radians/degrees mixup)
    assert 0.9 < fallback["Sun"]["speed"] < 1.1
    # Moon speed regression (was ~95 deg/day from a dimensionally wrong
    # derivative; true lunar motion is ~11.8-15.4 deg/day)
    assert 11.0 < fallback["Moon"]["speed"] < 16.0, fallback["Moon"]["speed"]
    # Nodes match the primary backend's retrogression convention
    assert fallback["Rahu"]["is_retrograde"] is False
    assert fallback["Ketu"]["is_retrograde"] is False


# ===========================================================================
# 4. Nakshatra and Pada (hand-computed from the 13d20' division)
# ===========================================================================

NAKSHATRA_CASES = [
    (0.0, "Ashwini", 1, "Ketu"),
    (3.30, "Ashwini", 1, "Ketu"),          # pada width = 3d20'
    (3.40, "Ashwini", 2, "Ketu"),
    (13.35, "Bharani", 1, "Venus"),
    (16.70, "Bharani", 2, "Venus"),
    (20.00, "Bharani", 3, "Venus"),
    (26.70, "Krittika", 1, "Sun"),
    (30.00, "Krittika", 2, "Sun"),
    (86.70, "Punarvasu", 3, "Jupiter"),    # 80 + 6.7 (Punarvasu spans 80-93.33)
    (213.35, "Anuradha", 1, "Saturn"),     # Anuradha spans 213.33-226.67
    (217.49, "Anuradha", 2, "Saturn"),     # demo chart Moon
    (346.70, "Revati", 1, "Mercury"),
    (359.99, "Revati", 4, "Mercury"),
]


@pytest.mark.parametrize("lon,expected_nak,expected_pada,expected_lord", NAKSHATRA_CASES)
def test_nakshatra_pada(lon, expected_nak, expected_pada, expected_lord):
    nak, pada, lord = _get_nakshatra_and_pada(lon)
    assert nak == expected_nak
    assert pada == expected_pada
    assert lord == expected_lord


def test_all_27_nakshatras_mapped():
    assert len(NAKSHATRAS) == 27
    for idx in range(27):
        start = idx * (360.0 / 27.0) + 0.01
        nak, pada, lord = _get_nakshatra_and_pada(start)
        assert nak == NAKSHATRAS[idx]["name"]
        assert lord == NAKSHATRAS[idx]["lord"]
        assert 1 <= pada <= 4


# ===========================================================================
# 5. Navamsa D9 (hand-computed continuous mapping)
# ===========================================================================

NAVAMSA_CASES = [
    (0.0, "Aries"),
    (3.40, "Taurus"),
    (30.1, "Capricorn"),     # earth sign: navamsa count starts at Capricorn
    (60.1, "Libra"),         # air sign: starts at Libra
    (90.1, "Cancer"),        # water sign: starts at Cancer
    (120.1, "Aries"),        # fire sign: starts at Aries again
    (180.1, "Libra"),
    (270.1, "Capricorn"),
    (359.9, "Pisces"),
]


@pytest.mark.parametrize("lon,expected_sign", NAVAMSA_CASES)
def test_navamsa_mapping(lon, expected_sign):
    idx, _ = calculate_navamsa_sign_index(lon)
    assert INDEX_TO_SIGN[idx] == expected_sign


# ===========================================================================
# 6. Divisional charts (BPHS class rules, hand-computed)
# ===========================================================================

VARGA_CASES = [
    # D2 Hora: odd -> Leo then Cancer; even -> Cancer then Leo
    ("D2", 1, 0.0, "Leo"),
    ("D2", 1, 20.0, "Cancer"),
    ("D2", 2, 0.0, "Cancer"),
    ("D2", 2, 20.0, "Leo"),
    # D3 Drekkana: same, 5th, 9th
    ("D3", 1, 0.0, "Aries"),
    ("D3", 1, 10.0, "Leo"),
    ("D3", 1, 20.0, "Sagittarius"),
    # D4 Chaturthamsha: odd from same; even from 7th
    ("D4", 1, 0.0, "Aries"),
    ("D4", 1, 7.5, "Cancer"),
    ("D4", 1, 15.0, "Libra"),
    ("D4", 1, 22.5, "Capricorn"),
    ("D4", 2, 0.0, "Scorpio"),
    ("D4", 2, 7.5, "Aquarius"),
    ("D4", 2, 15.0, "Taurus"),
    ("D4", 2, 22.5, "Leo"),
    # D7 Saptamsha: odd from same; even from 7th
    ("D7", 1, 0.0, "Aries"),
    ("D7", 1, 4.3, "Taurus"),
    ("D7", 2, 0.0, "Scorpio"),
    # D10 Dashamsha: odd from same; even from 9th
    ("D10", 1, 0.0, "Aries"),
    ("D10", 1, 3.0, "Taurus"),
    ("D10", 2, 0.0, "Capricorn"),
    ("D10", 2, 3.0, "Aquarius"),
    # D12 Dwadashamsha: sequential from same sign
    ("D12", 1, 0.0, "Aries"),
    ("D12", 1, 2.5, "Taurus"),
    ("D12", 1, 27.5, "Pisces"),
    # D16 Kalamsa: movable from Aries, fixed from Leo, dual from Sagittarius
    ("D16", 1, 0.0, "Aries"),
    ("D16", 1, 1.875, "Taurus"),
    ("D16", 2, 0.0, "Leo"),
    ("D16", 3, 0.0, "Sagittarius"),
    # D20 Vimshamsha: movable from Aries, fixed from Sagittarius, dual from Leo
    ("D20", 1, 0.0, "Aries"),
    ("D20", 2, 0.0, "Sagittarius"),
    ("D20", 3, 0.0, "Leo"),
    # D24 Siddhamsha: odd from Leo, even from Cancer
    ("D24", 1, 0.0, "Leo"),
    ("D24", 1, 1.25, "Virgo"),
    ("D24", 2, 0.0, "Cancer"),
    # D27 Bhamsha: fire->Aries, earth->Cancer, air->Libra, water->Capricorn
    ("D27", 1, 0.0, "Aries"),
    ("D27", 2, 0.0, "Cancer"),
    ("D27", 3, 0.0, "Libra"),
    ("D27", 4, 0.0, "Capricorn"),
    ("D27", 5, 0.0, "Aries"),
    # D30 Trimshamsha (Parashara)
    ("D30", 1, 0.0, "Aries"),
    ("D30", 1, 5.0, "Aquarius"),
    ("D30", 1, 10.0, "Sagittarius"),
    ("D30", 1, 18.0, "Gemini"),
    ("D30", 1, 25.0, "Libra"),
    ("D30", 2, 0.0, "Taurus"),
    ("D30", 2, 5.0, "Virgo"),
    ("D30", 2, 12.0, "Pisces"),
    ("D30", 2, 20.0, "Capricorn"),
    ("D30", 2, 25.0, "Scorpio"),
    # D40 Khavedamsha: odd from Aries, even from Libra
    ("D40", 1, 0.0, "Aries"),
    ("D40", 1, 0.75, "Taurus"),
    ("D40", 2, 0.0, "Libra"),
    # D45 Akshavedamsha: movable from Aries, fixed from Leo, dual from Sagittarius
    ("D45", 1, 0.0, "Aries"),
    ("D45", 2, 0.0, "Leo"),
    ("D45", 3, 0.0, "Sagittarius"),
    # D60 Shashtiamsha: from the same sign
    ("D60", 1, 0.0, "Aries"),
    ("D60", 1, 0.5, "Taurus"),
    ("D60", 2, 0.0, "Taurus"),
    # D5 Panchamsha (non-Parashari, declared lord-sign scheme)
    ("D5", 1, 0.0, "Aries"),
    ("D5", 1, 6.0, "Aquarius"),
    ("D5", 1, 24.0, "Libra"),
    ("D5", 2, 0.0, "Taurus"),
    ("D5", 2, 6.0, "Virgo"),
    # D6 Shashtamsha: odd from Aries, even from Libra
    ("D6", 1, 0.0, "Aries"),
    ("D6", 1, 29.9, "Virgo"),
    ("D6", 2, 5.0, "Scorpio"),
    # D8 Ashtamsha: movable Aries, fixed Sagittarius, dual Leo
    ("D8", 1, 0.0, "Aries"),
    ("D8", 2, 0.0, "Sagittarius"),
    ("D8", 3, 0.0, "Leo"),
    # D11 Ekadashamsha: movable from sign, fixed 9th, dual 5th
    ("D11", 1, 0.0, "Aries"),
    ("D11", 1, 15.0, "Virgo"),
    ("D11", 2, 0.0, "Capricorn"),
    ("D11", 3, 0.0, "Libra"),
    # D81 Nav-Navamsha (parivritti / cyclic)
    ("D81", 1, 0.0, "Aries"),
    ("D81", 1, 30.0 / 81.0, "Taurus"),
    ("D81", 2, 0.0, "Capricorn"),
    # D108 Navamsha-Dwadashamsha (parivritti)
    ("D108", 1, 30.0 / 108.0, "Taurus"),
    ("D108", 2, 0.0, "Aries"),
    # D144 Dwadashamsha-Dwadashamsha (parivritti)
    ("D144", 1, 30.0 / 144.0, "Taurus"),
    ("D144", 2, 0.0, "Aries"),
]


@pytest.mark.parametrize("varga,sign_idx,deg,expected_sign", VARGA_CASES)
def test_varga_hand_computed(varga, sign_idx, deg, expected_sign):
    result_idx = varga_sign_index(varga, (sign_idx - 1) * 30.0 + deg, sign_idx, deg)
    assert INDEX_TO_SIGN[result_idx] == expected_sign, f"{varga} {INDEX_TO_SIGN[sign_idx]} {deg}"


# ===========================================================================
# 7. Vimshottari dasha balance (hand-computed classical arithmetic)
# ===========================================================================

def _timeline(moon_lon, birth=datetime(1990, 1, 1, 12, 0)):
    return calculate_vimshottari_timeline(birth, moon_lon, max_years=120.0)


def _state_at_birth(moon_lon, birth=datetime(1990, 1, 1, 12, 0)):
    return get_dasha_at_date(_timeline(moon_lon, birth), birth)


def test_dasha_full_balance_at_nakshatra_start():
    # Moon at 0 deg Aries = start of Ashwini (Ketu, 7y): full Ketu balance
    state = _state_at_birth(0.0)
    assert (state.mahadasha, state.antardasha, state.pratyantardasha) == ("Ketu", "Ketu", "Ketu")


def test_dasha_half_elapsed_venus_md_runs_rahu_ad_at_birth():
    # Moon at 20 deg Aries: Bharani (Venus, 20y), 50% elapsed -> 10y balance.
    # Venus AD sequence (years): Venus 3.333, Sun 1, Moon 1.667, Mars 1.167, Rahu 3 ...
    # 10y elapsed falls inside Rahu AD (7.167 -> 10.167), 2 months remaining.
    state = _state_at_birth(20.0)
    assert state.mahadasha == "Venus"
    assert state.antardasha == "Rahu"
    remaining = (state.ad_period.end_date - state.ad_period.start_date).total_seconds() / 86400.0
    assert remaining == pytest.approx(0.1667 * 365.2425, rel=0.01)
    # PD at birth (Rahu AD): Rahu .45, Jup .4, Sat .475, Mer .425, Ket .175,
    # Ven .5, Sun .15, Moon .25 -> cumulative 7.75y; birth at 7.7583y -> Mars PD
    assert state.pratyantardasha == "Mars"


def test_dasha_elapsed_lands_in_sun_ad():
    # Moon at 16 deg Aries: Bharani 20% elapsed -> 4y into Venus MD.
    # Venus 3.333 + Sun 1 > 4y -> Sun AD with 0.333y remaining.
    state = _state_at_birth(16.0)
    assert state.mahadasha == "Venus"
    assert state.antardasha == "Sun"


def test_dasha_wraparound_order_revati():
    # Moon at 350 deg = Revati (Mercury, 17y), 25% elapsed -> 4.25y balance.
    # Mercury ADs: Mercury 2.408, Ketu 0.992, Venus 2.833 ... 4.25y -> Venus AD
    state = _state_at_birth(350.0)
    assert state.mahadasha == "Mercury"
    assert state.antardasha == "Venus"


def test_dasha_sequence_is_classical():
    # Full-cycle order check from any start
    timeline = _timeline(0.0)  # Ketu start
    md_lords = [p.lord for p in timeline if p.level == "MD"][:10]
    assert md_lords[:9] == ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]


@pytest.mark.parametrize("moon_lon", [20.0, 16.0, 0.0, 350.0, 100.0, 222.2, 359.9])
def test_dasha_timeline_integrity(moon_lon):
    """Every level nests and is contiguous: MD contains ADs contains PDs."""
    birth = datetime(1990, 1, 1, 12, 0)
    timeline = _timeline(moon_lon, birth)
    mds = [p for p in timeline if p.level == "MD"]
    ads = [p for p in timeline if p.level == "AD"]
    pds = [p for p in timeline if p.level == "PD"]

    assert mds[0].start_date == birth
    for prev, nxt in zip(mds, mds[1:]):
        assert abs((nxt.start_date - prev.end_date).total_seconds()) < 2
    for md in mds:
        md_ads = [a for a in ads if a.parent_md == md.lord and a.start_date >= md.start_date and a.end_date <= md.end_date]
        assert md_ads, f"no ADs inside {md.lord} MD"
        assert abs((md_ads[0].start_date - md.start_date).total_seconds()) < 2
        assert abs((md_ads[-1].end_date - md.end_date).total_seconds()) < 2
        for ad in md_ads:
            ad_pds = [p for p in pds if p.parent_md == md.lord and p.parent_ad == ad.lord
                      and p.start_date >= ad.start_date and p.end_date <= ad.end_date]
            assert ad_pds
            assert abs((ad_pds[0].start_date - ad.start_date).total_seconds()) < 2
            assert abs((ad_pds[-1].end_date - ad.end_date).total_seconds()) < 2


def test_dasha_subperiod_durations_are_proportional():
    """AD duration = MD duration * (AD lord years / 120), classical formula."""
    from SweetAstro.src.core.constants import VIMSHOTTARI_YEARS, DAYS_PER_YEAR
    state = _state_at_birth(0.0)
    timeline = _timeline(0.0)
    first_md = [p for p in timeline if p.level == "MD"][0]
    first_ad = [p for p in timeline if p.level == "AD"][0]
    expected_days = VIMSHOTTARI_YEARS[first_ad.lord] / 120.0 * first_md.duration_days
    assert first_ad.duration_days == pytest.approx(expected_days, rel=1e-6)
    assert first_md.duration_days / DAYS_PER_YEAR == pytest.approx(7.0, rel=1e-9)


# ===========================================================================
# 8. Historical dataset end-to-end recomputation
# ===========================================================================

def test_historical_dataset_recomputes():
    import json
    dataset = json.loads((DATA_DIR / "test_charts" / "historical_verified.json").read_text(encoding="utf-8"))
    assert len(dataset) >= 5
    for row in dataset:
        y, mo, d = (int(p) for p in row["dob"].split("-"))
        h, mi, s = (int(float(p)) for p in row["tob"].split(":"))
        chart = calculate_d1_chart(y, mo, d, h, mi, s, float(row["tz_offset"]),
                                   float(row["lat"]), float(row["lon"]))
        assert chart.ascendant_sign in INDEX_TO_SIGN.values()
        for planet, state in chart.planets.items():
            assert 0.0 <= state.longitude < 360.0, f"{row['chart_id']}/{planet}"
        timeline = calculate_vimshottari_timeline(
            datetime(y, mo, d, h, mi, s), chart.planets["Moon"].longitude
        )
        assert timeline and timeline[0].level == "MD"
        # The timeline begins at the birth instant: querying it must resolve
        state = get_dasha_at_date(timeline, datetime(y, mo, d, h, mi, s))
        assert state is not None
