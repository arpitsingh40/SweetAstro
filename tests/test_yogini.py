"""Yogini Dasha engine tests: starting yogini, balance, sequence, lookup."""

from datetime import datetime, timedelta

from SweetAstro.src.core.constants import DAYS_PER_YEAR
from SweetAstro.src.core.yogini import (
    YOGINI_CYCLE_YEARS, YOGINI_LORDS, YOGINI_ORDER, YOGINI_YEARS,
    calculate_yogini_timeline, get_yogini_at_date, starting_yogini,
)

BIRTH = datetime(1990, 1, 1, 0, 0, 0)


def test_yogini_tables_are_consistent():
    assert len(YOGINI_ORDER) == 8
    assert set(YOGINI_YEARS) == set(YOGINI_ORDER)
    assert set(YOGINI_LORDS) == set(YOGINI_ORDER)
    assert YOGINI_CYCLE_YEARS == 36.0
    assert sorted(YOGINI_YEARS.values()) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


def test_starting_yogini_from_nakshatra():
    # Ashwini (nakshatra 1): (1 + 3) mod 8 = 4 -> Bhramari
    assert starting_yogini(0.0) == "Bhramari"
    # Bharani (nakshatra 2): (2 + 3) mod 8 = 5 -> Bhadrika
    assert starting_yogini(360.0 / 27.0) == "Bhadrika"
    # Revati (nakshatra 27): (27 + 3) mod 8 = 6 -> Ulka
    assert starting_yogini(360.0 / 27.0 * 26) == "Ulka"


def test_first_period_balance_and_sequence():
    timeline = calculate_yogini_timeline(BIRTH, 0.0, max_years=40.0)
    mds = [p for p in timeline if p.level == "MD"]

    # 0 deg into Ashwini -> full Bhramari (4 years) first
    assert mds[0].lord == "Bhramari"
    assert mds[0].start_date == BIRTH
    assert abs(mds[0].duration_days - 4.0 * DAYS_PER_YEAR) < 0.01

    # Sequence follows the 8-yogini order
    expected = ["Bhadrika", "Ulka", "Siddha", "Sankata", "Mangala", "Pingala"]
    assert [p.lord for p in mds[1:7]] == expected

    # Antardashas exist within each MD and stay inside their parent span
    ads = [p for p in timeline if p.level == "AD"]
    assert ads
    first_md = mds[0]
    first_ads = [
        p for p in ads
        if p.parent_md == "Bhramari"
        and p.start_date >= first_md.start_date
        and p.end_date <= first_md.end_date
    ]
    assert len(first_ads) == 8
    assert all(p.end_date <= first_md.end_date for p in first_ads)


def test_balance_from_partial_nakshatra():
    # Halfway through Ashwini -> half of Bhramari (2 years) remains
    moon = (360.0 / 27.0) / 2.0
    timeline = calculate_yogini_timeline(BIRTH, moon, max_years=5.0)
    first_md = [p for p in timeline if p.level == "MD"][0]
    assert first_md.lord == "Bhramari"
    assert abs(first_md.duration_days - 2.0 * DAYS_PER_YEAR) < 0.5


def test_yogini_lookup_is_inside_timeline():
    timeline = calculate_yogini_timeline(BIRTH, 10.0, max_years=100.0)
    state = get_yogini_at_date(timeline, BIRTH + timedelta(days=365.25 * 2))
    assert state is not None
    assert state.mahadasha in YOGINI_ORDER
    assert state.antardasha in YOGINI_ORDER
    assert state.mahadasha_lord in YOGINI_LORDS.values()


def test_yogini_timeline_is_deterministic():
    a = calculate_yogini_timeline(BIRTH, 123.4, max_years=80.0)
    b = calculate_yogini_timeline(BIRTH, 123.4, max_years=80.0)
    assert [(p.level, p.lord, p.start_date, p.end_date) for p in a] == \
           [(p.level, p.lord, p.start_date, p.end_date) for p in b]
