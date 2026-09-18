"""
Panchanga and Muhurta verification tests.

The reference values come from authentic published panchanga data extracted
from DrikPanchang.com (drik ganita, Lahiri ayanamsha) and frozen in
data/reference/panchanga_drikpanchang.json. Times are local civil time; the
panchang day runs sunrise to sunrise.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from SweetAstro.src.core.panchanga import (
    KARANA_MOVABLE, YOGA_NAMES, PanchangaError, compute_panchanga,
    karana_name, sun_times, tithi_name,
)
from SweetAstro.src.core.constants import INDEX_TO_SIGN
from SweetAstro.src.core.muhurta import (
    NAKSHATRA_INDEX, assess_day, chandrabala_for, find_muhurta_days,
    lagna_windows, load_muhurta_rules, tara_for, tara_is_favourable, vishti_windows,
)

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "reference" / "panchanga_drikpanchang.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
CASES = [dict(case, id=f"{case['location_key']}_{case['date']}") for case in FIXTURE["cases"]]

SIGN_TO_ENGLISH = {
    "Mesha": "Aries", "Vrishabha": "Taurus", "Mithuna": "Gemini", "Karka": "Cancer",
    "Simha": "Leo", "Kanya": "Virgo", "Tula": "Libra", "Vrishchika": "Scorpio",
    "Dhanu": "Sagittarius", "Makara": "Capricorn", "Kumbha": "Aquarius", "Meena": "Pisces",
}
# DrikPanchang spells the classical "Gara" karana as "Garaja"
KARANA_ALIASES = {"Garaja": "Gara"}

DELHI = (28.635556, 77.224444, 212, 5.5)


def _parse_fixture_time(text: str, base_date: date, sunrise: datetime) -> datetime:
    parsed = datetime.strptime(text.strip(), "%I:%M %p")
    value = datetime(base_date.year, base_date.month, base_date.day, parsed.hour, parsed.minute)
    if value < sunrise:
        value += timedelta(days=1)
    return value


def _minutes(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 60.0


def _compute(case):
    y, m, d = (int(x) for x in case["date"].split("-"))
    return compute_panchanga(y, m, d, 5.5, case["latitude"], case["longitude"], case["elevation_m"])


# ---------------------------------------------------------------- reference verification

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_sunrise_sunset_vs_reference(case):
    panchanga = _compute(case)
    exp_sunrise = _parse_fixture_time(case["sunrise"], panchanga.date, panchanga.sunrise - timedelta(days=1))
    exp_sunset = _parse_fixture_time(case["sunset"], panchanga.date, panchanga.sunrise - timedelta(days=1))
    assert _minutes(panchanga.sunrise, exp_sunrise) <= 2.0, f"sunrise {panchanga.sunrise} vs {case['sunrise']}"
    assert _minutes(panchanga.sunset, exp_sunset) <= 2.0, f"sunset {panchanga.sunset} vs {case['sunset']}"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_five_limbs_vs_reference(case):
    panchanga = _compute(case)
    for key, ours_name, ours_end in [
        ("tithi", panchanga.tithi_name, panchanga.tithi_ends),
        ("nakshatra", panchanga.nakshatra, panchanga.nakshatra_ends),
        ("yoga", panchanga.yoga, panchanga.yoga_ends),
        ("karana", panchanga.karana, panchanga.karana_ends),
    ]:
        rows = case.get(key) or []
        if not rows:
            continue
        exp_name, exp_time = rows[0]
        exp_name = KARANA_ALIASES.get(exp_name, exp_name)
        assert ours_name == exp_name, f"{key}: {ours_name} != {exp_name}"
        exp_dt = _parse_fixture_time(exp_time, panchanga.date, panchanga.sunrise - timedelta(days=1))
        assert _minutes(ours_end, exp_dt) <= 6.0, f"{key} ends {ours_end} vs {exp_time}"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_day_windows_vs_reference(case):
    panchanga = _compute(case)
    for key, ours in [("rahu_kalam", panchanga.rahu_kalam), ("yamaganda", panchanga.yamaganda),
                      ("gulika_kalam", panchanga.gulika_kalam), ("abhijit", panchanga.abhijit)]:
        exp = case.get(key)
        if not exp:
            continue
        exp_start = _parse_fixture_time(exp[0], panchanga.date, panchanga.sunrise - timedelta(days=1))
        exp_end = _parse_fixture_time(exp[1], panchanga.date, panchanga.sunrise - timedelta(days=1))
        assert _minutes(ours[0], exp_start) <= 2.0, f"{key} start {ours[0]} vs {exp[0]}"
        assert _minutes(ours[1], exp_end) <= 2.0, f"{key} end {ours[1]} vs {exp[1]}"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_meta_vs_reference(case):
    panchanga = _compute(case)
    if case.get("weekday"):
        assert panchanga.vara_sanskrit == case["weekday"]
    if case.get("moon_sign"):
        assert panchanga.moon_sign == SIGN_TO_ENGLISH[case["moon_sign"]]
    assert abs(panchanga.ayanamsha - case["ayanamsha"]) <= 0.01


# ---------------------------------------------------------------- mapping units

def test_tithi_name_mapping():
    assert tithi_name(1) == ("Shukla", "Pratipada")
    assert tithi_name(15) == ("Shukla", "Purnima")
    assert tithi_name(16) == ("Krishna", "Pratipada")
    assert tithi_name(30) == ("Krishna", "Amavasya")
    with pytest.raises(ValueError):
        tithi_name(31)


def test_karana_name_mapping():
    assert karana_name(0) == "Kimstughna"
    assert karana_name(1) == "Bava"
    assert karana_name(7) == "Vishti"
    assert karana_name(8) == "Bava"       # movable cycle repeats
    assert karana_name(14) == "Vishti"
    assert karana_name(56) == "Vishti"
    assert karana_name(57) == "Shakuni"
    assert karana_name(58) == "Chatushpada"
    assert karana_name(59) == "Naga"
    assert len(KARANA_MOVABLE) == 7


def test_yoga_names_complete():
    assert len(YOGA_NAMES) == 27
    assert YOGA_NAMES[22] == "Shubha"
    assert YOGA_NAMES[0] == "Vishkambha"
    assert YOGA_NAMES[-1] == "Vaidhriti"


def test_sunrise_reference_value_frozen():
    sunrise, sunset = sun_times(2026, 9, 12, DELHI[3], DELHI[0], DELHI[1], DELHI[2])
    assert sunrise.strftime("%H:%M") == "06:04"
    assert sunset.strftime("%H:%M") == "18:30"


def test_panchanga_at_explicit_time():
    # Pratipada ends 07:46 on 2026-09-12, so a 13:00 query is Dwitiya
    panchanga = compute_panchanga(2026, 9, 12, 5.5, *DELHI[:3],
                                  at=datetime(2026, 9, 12, 13, 0))
    assert panchanga.tithi_name == "Dwitiya"
    assert panchanga.paksha == "Shukla"


def test_polar_error_is_explicit():
    with pytest.raises(PanchangaError):
        sun_times(2026, 6, 21, 2.0, 78.2232, 15.6267)  # Svalbard: midnight sun


# ---------------------------------------------------------------- muhurta

def _day(y, m, d):
    return compute_panchanga(y, m, d, 5.5, *DELHI[:3])


def test_muhurta_rules_load():
    rules = load_muhurta_rules()
    assert rules["version"]
    assert "vivaha" in rules["events"]
    assert "Vishti" in rules["common"]["avoid_karana"]


def test_vivaha_suitable_day():
    verdict = assess_day(_day(2026, 9, 12), "vivaha", include_windows=True)  # Uttara Phalguni, Shukla Pratipada
    assert verdict.suitable is True
    assert verdict.windows, "candidate windows expected on a clean day"
    assert any("pass" in r for r in verdict.reasons)


def test_vivaha_rejects_rikta_tithi():
    verdict = assess_day(_day(2026, 9, 15), "vivaha")  # Chaturthi (Rikta)
    assert verdict.suitable is False
    assert any("avoided tithi" in r for r in verdict.reasons)


def test_vivaha_rejects_unlisted_nakshatra():
    verdict = assess_day(_day(2026, 9, 14), "vivaha")  # Chitra not in vivaha list
    assert verdict.suitable is False
    assert any("Chitra" in r for r in verdict.reasons)


def test_vivaha_rejects_bhadra():
    verdict = assess_day(_day(2026, 9, 26), "vivaha")  # Vishti (Bhadra) karana at sunrise
    assert verdict.suitable is False
    assert any("Bhadra" in r or "Vishti" in r for r in verdict.reasons)


def test_abhijit_never_overlaps_rahu_kalam():
    verdict = assess_day(_day(2026, 9, 12), "vivaha", include_windows=True)
    assert verdict.windows
    rahu_start, rahu_end = _day(2026, 9, 12).rahu_kalam
    for start, end, _label in verdict.windows:
        assert end <= rahu_start or start >= rahu_end


def test_find_muhurta_days_range():
    days = find_muhurta_days(date(2026, 9, 12), date(2026, 9, 16), 5.5,
                             DELHI[0], DELHI[1], "vivaha", elevation_m=DELHI[2])
    dates = {d.day.date for d in days}
    assert date(2026, 9, 12) in dates
    assert date(2026, 9, 15) not in dates          # Rikta tithi
    assert all(d.suitable for d in days)


def test_unknown_event_raises():
    with pytest.raises(ValueError):
        assess_day(_day(2026, 9, 12), "space_travel")


# ---------------------------------------------------------------- depth: personal + windows

def test_tara_mapping():
    assert tara_for(0, 0) == "Janma"
    assert tara_for(0, 1) == "Sampat"
    assert tara_for(0, 8) == "Parama Mitra"   # 9th tara
    assert tara_for(0, 9) == "Janma"          # cycle repeats
    assert tara_is_favourable("Sampat") is True
    assert tara_is_favourable("Vipat") is False


def test_chandrabala_mapping():
    assert chandrabala_for(1, 1) == "favourable"
    assert chandrabala_for(1, 4) == "unfavourable"   # 4th from natal Moon sign
    assert chandrabala_for(1, 2) == "mixed"


def test_lagna_windows_within_daylight():
    day = _day(2026, 9, 12)
    windows = lagna_windows(day, ["Virgo", "Libra"])
    assert windows
    for start, end, sign in windows:
        assert day.sunrise <= start < end <= day.sunset
        assert sign in ("Virgo", "Libra")


def test_vishti_windows_detected():
    day = _day(2026, 9, 26)  # reference: Vishti (Bhadra) karana at sunrise
    windows = vishti_windows(day)
    assert windows, "expected a Bhadra window on 2026-09-26"
    for start, end in windows:
        assert day.sunrise <= start < end <= day.sunset


def test_personal_tarabala_blocks_day():
    day = _day(2026, 9, 12)
    day_index = NAKSHATRA_INDEX[day.nakshatra]
    birth_index = (day_index - 2) % 27      # 3rd tara from birth = Vipat
    verdict = assess_day(day, "vivaha", birth_nakshatra_index=birth_index)
    assert verdict.suitable is False
    assert verdict.tara == "Vipat"
    assert any("Tarabala" in r for r in verdict.reasons)


def test_personal_chandrabala_blocks_day():
    day = _day(2026, 9, 12)
    moon_rashi_index = next(i for i in range(1, 13) if INDEX_TO_SIGN[i] == day.moon_sign)
    birth_rashi = ((moon_rashi_index - 4) % 12) + 1   # day Moon in 4th from natal sign
    verdict = assess_day(day, "vivaha", birth_rashi_index=birth_rashi)
    assert verdict.suitable is False
    assert verdict.chandrabala == "unfavourable"
    assert any("Chandrabala" in r for r in verdict.reasons)


def test_candidate_windows_are_sorted_and_labeled():
    verdict = assess_day(_day(2026, 9, 12), "vivaha", include_windows=True)
    assert verdict.windows
    starts = [w[0] for w in verdict.windows]
    assert starts == sorted(starts)
    labels = " ".join(w[2] for w in verdict.windows)
    assert "lagna" in labels or "Abhijit" in labels


# ---------------------------------------------------------------- API

def test_panchanga_api_endpoint():
    from fastapi.testclient import TestClient
    from SweetAstro.src.api.app import app

    client = TestClient(app)
    response = client.get("/api/panchanga", params={"date": "2026-09-12"})
    assert response.status_code == 200
    body = response.json()
    assert body["tithi"].startswith("Shukla")
    assert body["nakshatra"] == "Uttara Phalguni"
    assert body["sunrise"].startswith("2026-09-12 06:04")
    rahu_start = datetime.strptime(body["rahu_kalam"][0], "%Y-%m-%d %H:%M:%S")
    assert abs((rahu_start - datetime(2026, 9, 12, 9, 11)).total_seconds()) <= 120

    bad = client.get("/api/panchanga", params={"date": "not-a-date"})
    assert bad.status_code == 400


# ---------------------------------------------------------------- fallback

def test_sunrise_fallback_within_five_minutes_of_swisseph(monkeypatch):
    """Without pyswisseph the built-in solar calculation must stay close."""
    from SweetAstro.src.core import panchanga as pan

    if not pan.HAS_SWISSEPH:
        pytest.skip("pyswisseph not installed — primary path unavailable")

    cases = [
        (2026, 9, 12, 5.5, 28.6356, 77.2244),
        (2026, 1, 15, 5.5, 28.6, 77.2),
        (1995, 5, 15, 5.5, 26.9, 75.8),
    ]
    for (y, m, d, tz, lat, lon) in cases:
        sw_rise, sw_set = pan.sun_times(y, m, d, tz, lat, lon)
        monkeypatch.setattr(pan, "HAS_SWISSEPH", False)
        fb_rise, fb_set = pan.sun_times(y, m, d, tz, lat, lon)
        monkeypatch.setattr(pan, "HAS_SWISSEPH", True)
        assert abs((fb_rise - sw_rise).total_seconds()) < 300, (y, m, d)
        assert abs((fb_set - sw_set).total_seconds()) < 300, (y, m, d)
