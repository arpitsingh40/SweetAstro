"""Chara Dasha tests: sequence, durations, dual lords, lookup, determinism."""

from datetime import datetime, timedelta

from SweetAstro.src.core.chara_dasha import (
    CHARA_DUAL_LORDS, calculate_chara_timeline, chara_house_of_sign,
    chara_sign_years, get_chara_at_date,
)
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import INDEX_TO_SIGN

BIRTH = datetime(1995, 5, 15, 14, 30)


def _chart():
    return calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def test_sign_years_are_bounded_and_deterministic():
    d1 = _chart()
    for sign_index in range(1, 13):
        years = chara_sign_years(d1, sign_index)
        assert 1 <= years <= 12
    assert chara_sign_years(d1, 1) == chara_sign_years(d1, 1)


def test_first_mahadasha_is_lagna_sign_from_birth():
    d1 = _chart()
    timeline = calculate_chara_timeline(d1, BIRTH, cycles=1)
    mds = [p for p in timeline if p.level == "MD"]
    assert len(mds) == 12
    assert mds[0].lord == d1.ascendant_sign
    assert mds[0].start_date == BIRTH
    assert abs(mds[0].duration_days - chara_sign_years(
        d1, d1.ascendant_sign_index) * 365.2425) < 0.01


def test_sequence_direction_follows_lagna_parity():
    d1 = _chart()
    timeline = calculate_chara_timeline(d1, BIRTH, cycles=1)
    mds = [p for p in timeline if p.level == "MD"]
    forward = d1.ascendant_sign_index % 2 == 1
    expected = [
        INDEX_TO_SIGN[((d1.ascendant_sign_index - 1 + (i if forward else -i)) % 12) + 1]
        for i in range(12)
    ]
    assert [p.lord for p in mds] == expected


def test_antardashas_cover_their_mahadasha():
    d1 = _chart()
    timeline = calculate_chara_timeline(d1, BIRTH, cycles=1)
    mds = [p for p in timeline if p.level == "MD"]
    ads = [p for p in timeline if p.level == "AD"]
    assert len(ads) == 12 * 12
    first_md = mds[0]
    first_ads = [p for p in ads if p.parent_md == first_md.lord]
    assert len(first_ads) == 12
    assert first_ads[0].start_date == first_md.start_date
    assert first_ads[-1].end_date == first_md.end_date


def test_dual_lord_signs_are_declared():
    assert set(CHARA_DUAL_LORDS) == {"Scorpio", "Aquarius"}
    assert len(CHARA_DUAL_LORDS["Scorpio"]) == 2
    assert len(CHARA_DUAL_LORDS["Aquarius"]) == 2


def test_chara_lookup_and_house_mapping():
    d1 = _chart()
    timeline = calculate_chara_timeline(d1, BIRTH, cycles=1)
    state = get_chara_at_date(timeline, BIRTH + timedelta(days=365.25 * 3))
    assert state is not None
    assert state.mahadasha_sign in [INDEX_TO_SIGN[i] for i in range(1, 13)]
    assert state.antardasha_sign in [INDEX_TO_SIGN[i] for i in range(1, 13)]
    assert chara_house_of_sign(d1, d1.ascendant_sign) == 1


def test_chara_timeline_is_contiguous():
    d1 = _chart()
    timeline = calculate_chara_timeline(d1, BIRTH, cycles=1)
    mds = [p for p in timeline if p.level == "MD"]
    for prev, nxt in zip(mds, mds[1:]):
        assert prev.end_date == nxt.start_date
