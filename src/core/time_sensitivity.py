"""
Birth-time stability (sensitivity) report.

Astrological houses, divisional charts and dasha balance depend on the exact
birth minute. This module re-computes the chart at +/- a configurable window
and reports what is stable vs unstable, so a consumer can see *why* a
reading is high- or reduced-confidence.

Not a prediction — a transparency check.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .chart import calculate_d1_chart
from .navamsa import calculate_navamsa_sign_index


@dataclass
class TimeStability:
    window_minutes: int
    lagna_stable: bool
    d9_lagna_stable: bool
    moon_pada_stable: bool
    summary: str


def assess_birth_time_stability(
    year: int, month: int, day: int, hour: int, minute: int,
    tz_offset: float, lat: float, lon: float,
    window_minutes: int = 30,
    second: float = 0.0,
) -> TimeStability:
    base_dt = datetime(year, month, day, hour, minute, int(second))

    def chart_at(dt: datetime):
        return calculate_d1_chart(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                                  dt.second, tz_offset, lat, lon)

    base = chart_at(base_dt)
    earlier = chart_at(base_dt - timedelta(minutes=window_minutes))
    later = chart_at(base_dt + timedelta(minutes=window_minutes))

    lagna_stable = (earlier.ascendant_sign == base.ascendant_sign == later.ascendant_sign)

    base_d9, _ = calculate_navamsa_sign_index(base.ascendant_deg)
    earlier_d9, _ = calculate_navamsa_sign_index(earlier.ascendant_deg)
    later_d9, _ = calculate_navamsa_sign_index(later.ascendant_deg)
    d9_lagna_stable = (earlier_d9 == base_d9 == later_d9)

    base_pada = base.planets["Moon"].nakshatra_pada
    moon_pada_stable = (earlier.planets["Moon"].nakshatra_pada == base_pada ==
                        later.planets["Moon"].nakshatra_pada)

    if lagna_stable and d9_lagna_stable:
        summary = (f"Birth-time stability within ±{window_minutes} min: lagna sign and D9 lagna "
                   f"stay unchanged — house and varga statements are stable at this precision.")
    elif lagna_stable:
        summary = (f"Birth-time stability within ±{window_minutes} min: lagna sign is stable, but "
                   f"the D9 lagna changes — navamsa-level (marriage/dharma) statements carry extra "
                   f"uncertainty at this precision.")
    else:
        summary = (f"Birth-time stability within ±{window_minutes} min: the lagna sign changes inside "
                   f"this window — the chart sits near a sign boundary, so house-based analysis is "
                   f"capped at this precision.")
    if not moon_pada_stable:
        summary += " The Moon's nakshatra pada also changes within the window (fine dasha balance indicative)."

    return TimeStability(
        window_minutes=window_minutes,
        lagna_stable=lagna_stable,
        d9_lagna_stable=d9_lagna_stable,
        moon_pada_stable=moon_pada_stable,
        summary=summary,
    )
