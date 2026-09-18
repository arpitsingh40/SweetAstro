"""
Vimshottari Dasha Engine.
Computes high-precision Mahadasha (MD), Antardasha (AD), and Pratyantardasha (PD)
timelines using the true solar year standard (365.2425 days).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .constants import VIMSHOTTARI_YEARS, VIMSHOTTARI_ORDER, DAYS_PER_YEAR, NAKSHATRAS


@dataclass
class DashaPeriod:
    level: str             # "MD", "AD", "PD"
    lord: str
    start_date: datetime
    end_date: datetime
    duration_days: float
    parent_md: str
    parent_ad: Optional[str] = None


@dataclass
class DashaStateAtDate:
    date: datetime
    mahadasha: str
    antardasha: str
    pratyantardasha: str
    md_period: DashaPeriod
    ad_period: DashaPeriod
    pd_period: DashaPeriod


@dataclass
class DeepDashaState:
    date: datetime
    mahadasha: str
    antardasha: str
    pratyantardasha: str
    sookshma: str
    prana: str
    pd_period: DashaPeriod
    sd_period: DashaPeriod
    prd_period: DashaPeriod


def calculate_vimshottari_timeline(
    birth_dt: datetime,
    moon_lon: float,
    max_years: float = 100.0
) -> List[DashaPeriod]:
    """
    Generates full Vimshottari timeline (MD, AD, PD) from birth date
    based on the exact sidereal Moon longitude.

    Classical balance-of-dasha handling: the birth Mahadasha (and the
    Antardasha within it) are partially elapsed at the moment of birth.
    The full sequence is generated from the *nominal* Mahadasha start
    (birth minus the elapsed portion) and every sub-period is clipped to
    the birth instant. This preserves the standard sub-period order
    (each AD/PD list starts from its own period lord), matching the
    output of professional Vimshottari software.

    Solar-year standard: 365.2425 days (SA-SPEC-V1.0 Sec 4.2).
    """
    norm_moon = moon_lon % 360.0
    nak_span_deg = 360.0 / 27.0  # 13° 20' = 13.3333333333°
    nak_idx = int(norm_moon / nak_span_deg) % 27
    nak_info = NAKSHATRAS[nak_idx]
    birth_lord = nak_info["lord"]

    deg_into_nak = norm_moon - (nak_idx * nak_span_deg)
    fraction_elapsed = deg_into_nak / nak_span_deg
    fraction_remaining = 1.0 - fraction_elapsed

    total_md_years = VIMSHOTTARI_YEARS[birth_lord]
    balance_days = fraction_remaining * total_md_years * DAYS_PER_YEAR
    elapsed_days = fraction_elapsed * total_md_years * DAYS_PER_YEAR

    all_periods: List[DashaPeriod] = []

    # Nominal (pre-birth) start of the first Mahadasha cycle
    nominal_md_start = birth_dt - timedelta(days=elapsed_days)
    start_idx = VIMSHOTTARI_ORDER.index(birth_lord)

    elapsed_total_years = 0.0
    md_index = 0
    current_md_start = nominal_md_start

    while elapsed_total_years < max_years:
        md_lord = VIMSHOTTARI_ORDER[(start_idx + md_index) % 9]
        full_md_years = VIMSHOTTARI_YEARS[md_lord]
        md_nominal_end = current_md_start + timedelta(days=full_md_years * DAYS_PER_YEAR)

        is_first_md = (md_index == 0)
        md_start_dt = birth_dt if is_first_md else current_md_start
        md_period = DashaPeriod(
            level="MD",
            lord=md_lord,
            start_date=md_start_dt,
            end_date=md_nominal_end,
            duration_days=(md_nominal_end - md_start_dt).total_seconds() / 86400.0,
            parent_md=md_lord,
        )
        all_periods.append(md_period)
        elapsed_total_years += (md_nominal_end - md_start_dt).total_seconds() / 86400.0 / DAYS_PER_YEAR

        # Generate ADs (and PDs) from the nominal Mahadasha start, clipping at birth
        ad_start_idx = VIMSHOTTARI_ORDER.index(md_lord)
        ad_current_dt = current_md_start

        for ad_offset in range(9):
            ad_lord = VIMSHOTTARI_ORDER[(ad_start_idx + ad_offset) % 9]
            ad_full_days = full_md_years * (VIMSHOTTARI_YEARS[ad_lord] / 120.0) * DAYS_PER_YEAR
            ad_nominal_end = ad_current_dt + timedelta(days=ad_full_days)
            if ad_nominal_end > md_nominal_end:
                ad_nominal_end = md_nominal_end

            if ad_nominal_end > birth_dt:
                ad_start_dt = max(ad_current_dt, birth_dt)
                all_periods.append(DashaPeriod(
                    level="AD",
                    lord=ad_lord,
                    start_date=ad_start_dt,
                    end_date=ad_nominal_end,
                    duration_days=(ad_nominal_end - ad_start_dt).total_seconds() / 86400.0,
                    parent_md=md_lord,
                    parent_ad=ad_lord,
                ))

                # Pratyantardashas within this AD (proportional to the AD's full span)
                pd_start_idx = VIMSHOTTARI_ORDER.index(ad_lord)
                ad_span_days = (ad_nominal_end - ad_current_dt).total_seconds() / 86400.0
                pd_current_dt = ad_current_dt

                for pd_offset in range(9):
                    pd_lord = VIMSHOTTARI_ORDER[(pd_start_idx + pd_offset) % 9]
                    pd_full_days = ad_span_days * (VIMSHOTTARI_YEARS[pd_lord] / 120.0)
                    pd_nominal_end = pd_current_dt + timedelta(days=pd_full_days)
                    if pd_nominal_end > ad_nominal_end:
                        pd_nominal_end = ad_nominal_end

                    if pd_nominal_end > birth_dt:
                        pd_start_dt = max(pd_current_dt, birth_dt)
                        all_periods.append(DashaPeriod(
                            level="PD",
                            lord=pd_lord,
                            start_date=pd_start_dt,
                            end_date=pd_nominal_end,
                            duration_days=(pd_nominal_end - pd_start_dt).total_seconds() / 86400.0,
                            parent_md=md_lord,
                            parent_ad=ad_lord,
                        ))

                    pd_current_dt = pd_nominal_end
                    if pd_current_dt >= ad_nominal_end:
                        break

            ad_current_dt = ad_nominal_end
            if ad_current_dt >= md_nominal_end:
                break

        current_md_start = md_nominal_end
        md_index += 1

    return all_periods


def get_dasha_at_date(
    timeline: List[DashaPeriod],
    query_dt: datetime
) -> Optional[DashaStateAtDate]:
    """
    Finds the active MD, AD, and PD at an exact datetime.
    """
    active_md: Optional[DashaPeriod] = None
    active_ad: Optional[DashaPeriod] = None
    active_pd: Optional[DashaPeriod] = None

    for p in timeline:
        if p.start_date <= query_dt < p.end_date:
            if p.level == "MD":
                active_md = p
            elif p.level == "AD":
                active_ad = p
            elif p.level == "PD":
                active_pd = p

    if active_md and active_ad and active_pd:
        return DashaStateAtDate(
            date=query_dt,
            mahadasha=active_md.lord,
            antardasha=active_ad.lord,
            pratyantardasha=active_pd.lord,
            md_period=active_md,
            ad_period=active_ad,
            pd_period=active_pd
        )
    return None


def _subdivide(lord: str, start: datetime, end: datetime) -> List[DashaPeriod]:
    """Subdivides a period into its nine proportional Vimshottari sub-periods."""
    order = VIMSHOTTARI_ORDER
    span_days = (end - start).total_seconds() / 86400.0
    start_idx = order.index(lord)
    periods: List[DashaPeriod] = []
    cursor = start
    for offset in range(9):
        sub_lord = order[(start_idx + offset) % 9]
        sub_days = span_days * (VIMSHOTTARI_YEARS[sub_lord] / 120.0)
        sub_end = end if offset == 8 else cursor + timedelta(days=sub_days)
        periods.append(DashaPeriod(
            level="SUB", lord=sub_lord, start_date=cursor, end_date=sub_end,
            duration_days=(sub_end - cursor).total_seconds() / 86400.0,
            parent_md=lord,
        ))
        cursor = sub_end
    return periods


def get_deep_dasha_at_date(
    timeline: List[DashaPeriod],
    query_dt: datetime
) -> Optional[DeepDashaState]:
    """
    Extends the active MD/AD/PD to Sukshma (4th) and Prana (5th) levels.

    Note: proportional subdivision of the active period (standard practice);
    the first post-birth period is already clipped by the timeline, so its
    Sukshma/Prana values are indicative.
    """
    state = get_dasha_at_date(timeline, query_dt)
    if not state:
        return None
    pd = state.pd_period
    sd_periods = _subdivide(state.pratyantardasha, pd.start_date, pd.end_date)
    sd = next((p for p in sd_periods if p.start_date <= query_dt < p.end_date), sd_periods[-1])
    prd_periods = _subdivide(sd.lord, sd.start_date, sd.end_date)
    prd = next((p for p in prd_periods if p.start_date <= query_dt < p.end_date), prd_periods[-1])
    return DeepDashaState(
        date=query_dt,
        mahadasha=state.mahadasha,
        antardasha=state.antardasha,
        pratyantardasha=state.pratyantardasha,
        sookshma=sd.lord,
        prana=prd.lord,
        pd_period=pd,
        sd_period=sd,
        prd_period=prd,
    )


def upcoming_periods(
    timeline: List[DashaPeriod],
    query_dt: datetime,
    levels: Tuple[str, ...] = ("MD", "AD", "PD"),
    limit: int = 8,
) -> List[DashaPeriod]:
    """Returns future period starts (default MD/AD/PD) in chronological order."""
    future = [p for p in timeline if p.start_date > query_dt and p.level in levels]
    future.sort(key=lambda p: (p.start_date, {"MD": 0, "AD": 1, "PD": 2}.get(p.level, 3)))
    return future[:limit]
