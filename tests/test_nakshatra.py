"""Nakshatra depth + natal panchanga tests."""

from collections import Counter

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import NAKSHATRAS
from SweetAstro.src.core.nakshatra import (
    NAKSHATRA_DETAILS, compute_natal_panchanga, nakshatra_detail,
)


def test_all_27_nakshatras_have_details_and_match_lords():
    assert len(NAKSHATRA_DETAILS) == 27
    for entry in NAKSHATRAS:
        detail = NAKSHATRA_DETAILS[entry["name"]]
        assert detail.lord == entry["lord"]
        assert detail.deity and detail.gana and detail.yoni and detail.nature
        assert len(detail.traits) >= 3


def test_gana_and_nature_classical_counts():
    gana = Counter(d.gana for d in NAKSHATRA_DETAILS.values())
    assert gana == {"Deva": 9, "Manushya": 9, "Rakshasa": 9}
    nature = Counter(d.nature for d in NAKSHATRA_DETAILS.values())
    assert nature["Dhruva"] == 4 and nature["Chara"] == 5 and nature["Ugra"] == 5
    assert nature["Tikshna"] == 4 and nature["Mishra"] == 2 and nature["Kshipra"] == 3
    assert nature["Mridu"] == 4


def test_natal_panchanga_matches_chart_engine():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)
    panchanga = compute_natal_panchanga(1995, 5, 15, 14, 30, 0, tz_offset=5.5)
    moon = d1.planets["Moon"]
    assert panchanga.nakshatra == moon.nakshatra
    assert panchanga.nakshatra_pada == moon.nakshatra_pada
    assert panchanga.nakshatra_lord == moon.nakshatra_lord
    assert panchanga.moon_sign == moon.sign
    assert 1 <= panchanga.tithi_index <= 30
    assert panchanga.paksha in ("Shukla", "Krishna")
    assert panchanga.yoga and panchanga.karana
    assert panchanga.vara == "Monday"  # 1995-05-15 was a Monday
    assert panchanga.vara_sanskrit == "Somavara"
    detail = nakshatra_detail(panchanga.nakshatra)
    assert detail is not None
    assert panchanga.deity == detail.deity and panchanga.gana == detail.gana


def test_evening_birth_vara_does_not_double_apply_timezone():
    # 1995-05-15 21:30 IST is still Monday locally; a tz double-application
    # used to roll it over to Tuesday.
    late = compute_natal_panchanga(1995, 5, 15, 21, 30, 0, tz_offset=5.5)
    assert late.vara == "Monday"
    assert late.vara_sanskrit == "Somavara"

    close_to_midnight = compute_natal_panchanga(1995, 5, 15, 23, 45, 0, tz_offset=5.5)
    assert close_to_midnight.vara == "Monday"
