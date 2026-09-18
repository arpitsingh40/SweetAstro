"""Sukshma/Prana dasha depth tests."""

from datetime import datetime

from SweetAstro.src.core.dasha import (
    VIMSHOTTARI_ORDER, calculate_vimshottari_timeline, get_deep_dasha_at_date,
    get_dasha_at_date, upcoming_periods, _subdivide,
)


def _timeline():
    birth = datetime(1995, 5, 15, 14, 30)
    return birth, calculate_vimshottari_timeline(birth, moon_lon=160.0)


def test_subdivide_is_proportional_and_starts_at_parent_lord():
    start = datetime(2020, 1, 1)
    end = datetime(2030, 1, 1)
    periods = _subdivide("Venus", start, end)
    assert len(periods) == 9
    assert periods[0].lord == "Venus"
    assert periods[0].start_date == start
    assert periods[-1].end_date == end
    total = sum(p.duration_days for p in periods)
    assert abs(total - (end - start).total_seconds() / 86400.0) < 1.0
    index = VIMSHOTTARI_ORDER.index("Venus")
    assert [p.lord for p in periods] == [VIMSHOTTARI_ORDER[(index + i) % 9] for i in range(9)]


def test_deep_dasha_state_is_consistent():
    birth, timeline = _timeline()
    query = datetime(2032, 6, 1)
    state = get_deep_dasha_at_date(timeline, query)
    base = get_dasha_at_date(timeline, query)
    assert state is not None and base is not None
    assert state.mahadasha == base.mahadasha
    assert state.antardasha == base.antardasha
    assert state.pratyantardasha == base.pratyantardasha
    assert state.sookshma in VIMSHOTTARI_ORDER
    assert state.prana in VIMSHOTTARI_ORDER
    assert state.sd_period.start_date <= query < state.sd_period.end_date
    assert state.prd_period.start_date <= query < state.prd_period.end_date
    # Prana sequence starts from the Sukshma lord
    seq = _subdivide(state.sookshma, state.sd_period.start_date, state.sd_period.end_date)
    assert seq[0].lord == state.sookshma
    assert any(p.lord == state.prana for p in seq)


def test_upcoming_periods_are_future_and_sorted():
    _, timeline = _timeline()
    query = datetime(2030, 1, 1)
    upcoming = upcoming_periods(timeline, query, levels=("MD", "AD"), limit=6)
    assert upcoming
    assert all(p.start_date > query for p in upcoming)
    starts = [p.start_date for p in upcoming]
    assert starts == sorted(starts)
