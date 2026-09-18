"""
Yogini Dasha Engine — the classical 36-year, 8-yogini nakshatra cycle.

Structure (classical):
    Mangala (Moon, 1y) · Pingala (Sun, 2y) · Dhanya (Jupiter, 3y) ·
    Bhramari (Mars, 4y) · Bhadrika (Mercury, 5y) · Ulka (Saturn, 6y) ·
    Siddha (Venus, 7y) · Sankata (Rahu, 8y)          total = 36 years

Starting yogini: (birth nakshatra number + 3) mod 8, where remainder
1 = Mangala, 2 = Pingala, ... 0 = Sankata. The balance of the first
period comes from the unelapsed fraction of the birth nakshatra.

Used as an independent cross-check dasha, never stacked onto Vimshottari
(see docs/research/timely_event_prediction.md §2). Interpretive only:
no accuracy claim may be made without a passed pre-registered run
(docs/accuracy_protocol.md).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from .constants import DAYS_PER_YEAR, NAKSHATRAS
from .dasha import DashaPeriod

YOGINI_ORDER: List[str] = [
    "Mangala", "Pingala", "Dhanya", "Bhramari",
    "Bhadrika", "Ulka", "Siddha", "Sankata",
]

YOGINI_YEARS = {
    "Mangala": 1.0,
    "Pingala": 2.0,
    "Dhanya": 3.0,
    "Bhramari": 4.0,
    "Bhadrika": 5.0,
    "Ulka": 6.0,
    "Siddha": 7.0,
    "Sankata": 8.0,
}

YOGINI_LORDS = {
    "Mangala": "Moon",
    "Pingala": "Sun",
    "Dhanya": "Jupiter",
    "Bhramari": "Mars",
    "Bhadrika": "Mercury",
    "Ulka": "Saturn",
    "Siddha": "Venus",
    "Sankata": "Rahu",
}

YOGINI_CYCLE_YEARS = sum(YOGINI_YEARS.values())  # 36.0

YOGINI_CONVENTION = (
    "Starting yogini from (nakshatra + 3) mod 8; balance from the unelapsed "
    "nakshatra fraction; 36-year cycle; sub-periods proportional to their "
    "yogini years, sequence starting from the parent period's yogini."
)


@dataclass
class YoginiState:
    date: datetime
    mahadasha: str
    antardasha: str
    mahadasha_lord: str
    antardasha_lord: str
    md_period: DashaPeriod
    ad_period: DashaPeriod


def starting_yogini(moon_lon: float) -> str:
    """Returns the birth Yogini from the sidereal Moon longitude."""
    norm_moon = moon_lon % 360.0
    nak_span_deg = 360.0 / 27.0
    nak_idx = int(norm_moon / nak_span_deg) % 27
    nak_number = nak_idx + 1  # 1..27
    remainder = (nak_number + 3) % 8
    idx = (remainder - 1) % 8
    return YOGINI_ORDER[idx]


def calculate_yogini_timeline(
    birth_dt: datetime,
    moon_lon: float,
    max_years: float = 100.0,
) -> List[DashaPeriod]:
    """
    Generates the Yogini Mahadasha/Antardasha timeline from the birth date
    and the exact sidereal Moon longitude. The birth Mahadasha is partially
    elapsed and is clipped to the birth instant; its Antardashas are
    proportional subdivisions of the full period, also clipped at birth.
    """
    norm_moon = moon_lon % 360.0
    nak_span_deg = 360.0 / 27.0
    nak_idx = int(norm_moon / nak_span_deg) % 27
    deg_into_nak = norm_moon - (nak_idx * nak_span_deg)
    fraction_elapsed = deg_into_nak / nak_span_deg
    fraction_remaining = 1.0 - fraction_elapsed

    start_lord = starting_yogini(moon_lon)
    start_idx = YOGINI_ORDER.index(start_lord)

    full_md_days = YOGINI_YEARS[start_lord] * DAYS_PER_YEAR
    elapsed_days = fraction_elapsed * full_md_days
    nominal_start = birth_dt - timedelta(days=elapsed_days)

    periods: List[DashaPeriod] = []
    cursor = nominal_start
    elapsed_years = 0.0
    md_index = 0

    while elapsed_years < max_years:
        md_lord = YOGINI_ORDER[(start_idx + md_index) % 8]
        md_years = YOGINI_YEARS[md_lord]
        md_end = cursor + timedelta(days=md_years * DAYS_PER_YEAR)

        is_first = (md_index == 0)
        md_start = birth_dt if is_first else cursor
        periods.append(DashaPeriod(
            level="MD", lord=md_lord, start_date=md_start, end_date=md_end,
            duration_days=(md_end - md_start).total_seconds() / 86400.0,
            parent_md=md_lord,
        ))
        elapsed_years += (md_end - md_start).total_seconds() / 86400.0 / DAYS_PER_YEAR

        ad_span_days = (md_end - cursor).total_seconds() / 86400.0
        ad_cursor = cursor
        for ad_offset in range(8):
            ad_lord = YOGINI_ORDER[(YOGINI_ORDER.index(md_lord) + ad_offset) % 8]
            ad_full_days = ad_span_days * (YOGINI_YEARS[ad_lord] / YOGINI_CYCLE_YEARS)
            ad_end = md_end if ad_offset == 7 else ad_cursor + timedelta(days=ad_full_days)
            if ad_end > md_end:
                ad_end = md_end
            if ad_end > birth_dt:
                ad_start = max(ad_cursor, birth_dt)
                periods.append(DashaPeriod(
                    level="AD", lord=ad_lord, start_date=ad_start, end_date=ad_end,
                    duration_days=(ad_end - ad_start).total_seconds() / 86400.0,
                    parent_md=md_lord, parent_ad=ad_lord,
                ))
            ad_cursor = ad_end
            if ad_cursor >= md_end:
                break

        cursor = md_end
        md_index += 1

    return periods


def get_yogini_at_date(
    timeline: List[DashaPeriod],
    query_dt: datetime,
) -> Optional[YoginiState]:
    """Returns the active Yogini Mahadasha/Antardasha at a datetime."""
    active_md: Optional[DashaPeriod] = None
    active_ad: Optional[DashaPeriod] = None
    for p in timeline:
        if p.start_date <= query_dt < p.end_date:
            if p.level == "MD":
                active_md = p
            elif p.level == "AD":
                active_ad = p
    if active_md is None or active_ad is None:
        return None
    return YoginiState(
        date=query_dt,
        mahadasha=active_md.lord,
        antardasha=active_ad.lord,
        mahadasha_lord=YOGINI_LORDS[active_md.lord],
        antardasha_lord=YOGINI_LORDS[active_ad.lord],
        md_period=active_md,
        ad_period=active_ad,
    )
