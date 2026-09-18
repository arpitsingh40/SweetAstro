"""
Unit Tests for Vimshottari Dasha Engine.
"""

import pytest
from datetime import datetime
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
from SweetAstro.src.core.constants import VIMSHOTTARI_YEARS, VIMSHOTTARI_ORDER


def test_dasha_timeline_generation():
    birth_dt = datetime(1990, 1, 1, 0, 0, 0)
    # 0° Aries Moon -> Ashwini nakshatra (Lord Ketu, 7 years)
    moon_lon = 0.0
    timeline = calculate_vimshottari_timeline(birth_dt, moon_lon, max_years=100.0)

    assert len(timeline) > 0

    # First MD should be Ketu
    first_md = [p for p in timeline if p.level == "MD"][0]
    assert first_md.lord == "Ketu"

    # Second MD should be Venus
    md_list = [p for p in timeline if p.level == "MD"]
    assert md_list[1].lord == "Venus"


def test_dasha_at_date_lookup():
    birth_dt = datetime(1990, 1, 1, 0, 0, 0)
    moon_lon = 0.0
    timeline = calculate_vimshottari_timeline(birth_dt, moon_lon, max_years=100.0)

    # Lookup 2 years after birth -> still in Ketu MD
    query_dt = datetime(1992, 1, 1, 0, 0, 0)
    dasha_state = get_dasha_at_date(timeline, query_dt)

    assert dasha_state is not None
    assert dasha_state.mahadasha == "Ketu"
    assert dasha_state.antardasha in VIMSHOTTARI_ORDER
    assert dasha_state.pratyantardasha in VIMSHOTTARI_ORDER
