"""
Jaimini Chara Dasha — sign-based rashi dasha (independent timing cross-check).

Declared conventions (the classical chapters preserve variants; this module
states exactly what it does and never silently mixes schools):

1. Sequence: the twelve mahadashas run from the Lagna sign; forward for
   odd-numbered signs (Aries, Gemini, ...) and reverse for even signs — the
   common shorthand. (BPHS also records a pada rule keyed from the ninth
   from Lagna; that variant is NOT applied here.)
2. Duration: count inclusively from the sign to the sign of its lord, in the
   direction of the sign (odd forward / even reverse), then subtract one —
   the count-minus-one school (K.N. Rao reading convention). A lord in its
   own sign gives 12 years. An exalted lord adds one year; a debilitated lord
   removes one (Jaimini Sutras I.1.28 as recorded in B. Suryanarain Rao's
   translation). Result clamped to 1..12.
3. Dual lords: Scorpio (Mars/Ketu) and Aquarius (Saturn/Rahu). Both in the
   same sign -> count to that sign. Otherwise choose the stronger sign:
   occupied beats empty, more occupants beats fewer, an exalted occupant
   settles it; ties fall to the first listed lord.
4. Antardashas: twelve equal sign sub-periods per mahadasha, running in the
   same direction as the sequence, starting from the mahadasha sign.
5. The first mahadasha starts at birth with its full duration (no Lagna
   elapsed-fraction proration) — the K.N. Rao convention.

Interpretive only; no accuracy claim without a passed pre-registered run
(docs/accuracy_protocol.md).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .chart import D1Chart
from .constants import DAYS_PER_YEAR, INDEX_TO_SIGN, SIGN_LORDS, SIGN_TO_INDEX
from .dasha import DashaPeriod

CHARA_DUAL_LORDS: Dict[str, Tuple[str, str]] = {
    "Scorpio": ("Mars", "Ketu"),
    "Aquarius": ("Saturn", "Rahu"),
}

CHARA_CONVENTION = (
    "count-minus-one school (K.N. Rao reading); sequence forward for odd "
    "Lagna signs / reverse for even; 12 equal antardashas in sequence "
    "direction; dual-lord tie-break by occupancy/strength; first mahadasha "
    "full from birth."
)

_MAX_YEARS_PER_SIGN = 12


def _is_odd_sign(sign_index: int) -> bool:
    return (sign_index % 2) == 1


def _step(sign_index: int, offset: int) -> int:
    return ((sign_index - 1 + offset) % 12) + 1


def _sign_sequence(start_index: int) -> List[int]:
    forward = _is_odd_sign(start_index)
    return [
        _step(start_index, i if forward else -i)
        for i in range(12)
    ]


def _count_to(sign_index: int, target_index: int) -> int:
    """Inclusive count from sign to target in the sign's own direction."""
    if _is_odd_sign(sign_index):
        return ((target_index - sign_index) % 12) + 1
    return ((sign_index - target_index) % 12) + 1


def _dignity_adjustment(d1: D1Chart, planets: Tuple[str, ...], target_index: int) -> int:
    adjustment = 0
    for p in planets:
        if d1.planets[p].sign_index != target_index:
            continue
        if d1.planets[p].dignity == "Exalted":
            adjustment += 1
        elif d1.planets[p].dignity == "Debilitated":
            adjustment -= 1
    return adjustment


def _stronger_sign(d1: D1Chart, a_index: int, b_index: int) -> int:
    """Occupied beats empty, more occupants beats fewer, exalted settles ties."""
    def rank(sign_index: int) -> Tuple[int, int, int]:
        occupants = [
            p for p, st in d1.planets.items() if st.sign_index == sign_index
        ]
        exalted = any(d1.planets[p].dignity == "Exalted" for p in occupants)
        return (1 if occupants else 0, len(occupants), 1 if exalted else 0)

    return a_index if rank(a_index) >= rank(b_index) else b_index


def chara_sign_years(d1: D1Chart, sign_index: int) -> int:
    """Years allotted to one sign under the declared convention (1..12)."""
    sign = INDEX_TO_SIGN[sign_index]
    if sign in CHARA_DUAL_LORDS:
        lord_a, lord_b = CHARA_DUAL_LORDS[sign]
        sign_a = d1.planets[lord_a].sign_index
        sign_b = d1.planets[lord_b].sign_index
        target_index = sign_a if sign_a == sign_b else _stronger_sign(d1, sign_a, sign_b)
        lords = (lord_a, lord_b)
    else:
        lord = SIGN_LORDS[sign]
        target_index = d1.planets[lord].sign_index
        lords = (lord,)

    if target_index == sign_index:
        return _MAX_YEARS_PER_SIGN

    years = _count_to(sign_index, target_index) - 1
    years += _dignity_adjustment(d1, lords, target_index)
    return max(1, min(_MAX_YEARS_PER_SIGN, years))


@dataclass
class CharaState:
    date: datetime
    mahadasha_sign: str
    antardasha_sign: str
    md_period: DashaPeriod
    ad_period: DashaPeriod


def calculate_chara_timeline(
    d1: D1Chart,
    birth_dt: datetime,
    cycles: int = 1,
) -> List[DashaPeriod]:
    """
    Full Chara Mahadasha/Antardasha timeline from the Lagna sign.
    `cycles` repeats the twelve-sign sequence (one cycle typically spans
    the native's life; two cycles cover long-range scans).
    """
    periods: List[DashaPeriod] = []
    cursor = birth_dt
    base_sequence = _sign_sequence(d1.ascendant_sign_index)
    forward = _is_odd_sign(d1.ascendant_sign_index)

    for _ in range(max(1, cycles)):
        for md_index in base_sequence:
            years = chara_sign_years(d1, md_index)
            md_end = cursor + timedelta(days=years * DAYS_PER_YEAR)
            md_sign = INDEX_TO_SIGN[md_index]
            periods.append(DashaPeriod(
                level="MD", lord=md_sign, start_date=cursor, end_date=md_end,
                duration_days=(md_end - cursor).total_seconds() / 86400.0,
                parent_md=md_sign,
            ))

            ad_span = (md_end - cursor).total_seconds() / 86400.0
            ad_cursor = cursor
            for ad_offset in range(12):
                ad_index = _step(md_index, ad_offset if forward else -ad_offset)
                ad_end = (
                    md_end if ad_offset == 11
                    else ad_cursor + timedelta(days=ad_span / 12.0)
                )
                if ad_end > md_end:
                    ad_end = md_end
                periods.append(DashaPeriod(
                    level="AD", lord=INDEX_TO_SIGN[ad_index],
                    start_date=ad_cursor, end_date=ad_end,
                    duration_days=(ad_end - ad_cursor).total_seconds() / 86400.0,
                    parent_md=md_sign, parent_ad=INDEX_TO_SIGN[ad_index],
                ))
                ad_cursor = ad_end
                if ad_cursor >= md_end:
                    break

            cursor = md_end

    return periods


def get_chara_at_date(
    timeline: List[DashaPeriod],
    query_dt: datetime,
) -> Optional[CharaState]:
    """Returns the active Chara Mahadasha/Antardasha signs at a datetime."""
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
    return CharaState(
        date=query_dt,
        mahadasha_sign=active_md.lord,
        antardasha_sign=active_ad.lord,
        md_period=active_md,
        ad_period=active_ad,
    )


def chara_house_of_sign(d1: D1Chart, sign: str) -> int:
    """Whole-sign house (from Lagna) occupied by a sign."""
    sign_index = SIGN_TO_INDEX[sign]
    return ((sign_index - d1.ascendant_sign_index) % 12) + 1
