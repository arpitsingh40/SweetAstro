"""Ashtakavarga tests: classical table invariants + chart integration."""

from SweetAstro.src.core.ashtakavarga import (
    ASHTAKA_TABLES, BAV_PLANETS, BAV_TOTALS, CONTRIBUTORS, SAV_TOTAL,
    calculate_ashtakavarga, house_support_label, transit_bindu_note,
)
from SweetAstro.src.core.chart import calculate_d1_chart


def _chart():
    return calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def test_table_totals_match_classical_invariants():
    for planet, total in BAV_TOTALS.items():
        assert sum(len(ASHTAKA_TABLES[planet][c]) for c in CONTRIBUTORS) == total
    assert sum(BAV_TOTALS.values()) == SAV_TOTAL


def test_sav_total_is_always_337():
    result = calculate_ashtakavarga(_chart())
    assert len(result.sav) == 12
    assert sum(result.sav) == SAV_TOTAL


def test_bav_bounds_and_house_mapping():
    d1 = _chart()
    result = calculate_ashtakavarga(d1)
    for planet in BAV_PLANETS:
        assert len(result.bav[planet]) == 12
        assert all(0 <= v <= 8 for v in result.bav[planet])
    for house in range(1, 13):
        sign_idx = d1.houses[house].sign_index
        assert result.sav_by_house[house] == result.sav[sign_idx - 1]
        for planet in BAV_PLANETS:
            assert result.bav_by_house[planet][house] == result.bav[planet][sign_idx - 1]


def test_support_labels_and_transit_note():
    assert house_support_label(31) == "very strong"
    assert house_support_label(25) == "strong"
    assert house_support_label(20) == "moderate"
    assert house_support_label(19) == "weak"
    note = transit_bindu_note(_chart(), "Jupiter", 1)
    assert "Jupiter" in note and "SAV" in note and "bindus" in note
