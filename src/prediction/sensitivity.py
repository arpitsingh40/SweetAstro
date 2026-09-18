"""
Birth-Time Uncertainty and Sensitivity Engine.
Implements Point 21 and Point 22: Evaluates temporal prediction stability across
birth time uncertainty windows (e.g. ±10 minutes).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..core.chart import calculate_d1_chart
from ..core.navamsa import calculate_navamsa_chart
from ..core.dasha import calculate_vimshottari_timeline, get_dasha_at_date


@dataclass
class SensitivityReport:
    window_minutes: int
    samples_tested: int
    lagna_stable_ratio: float       # 0.0 to 1.0
    navamsa_stable_ratio: float     # 0.0 to 1.0
    dasha_stable_ratio: float       # 0.0 to 1.0
    overall_stability_score: float  # 0 to 100%
    stability_classification: str   # "High", "Moderate", "Birth-Time Sensitive"
    details: str


def evaluate_birth_time_sensitivity(
    year: int, month: int, day: int,
    hour: int, minute: int, second: float = 0.0,
    tz_offset_hours: float = 5.5,
    lat: float = 28.6139, lon: float = 77.2090,
    window_minutes: int = 10,
    step_minutes: int = 2,
    target_eval_date: Optional[datetime] = None
) -> SensitivityReport:
    """
    Simulates birth time perturbations across [T0 - window, T0 + window]
    to measure how resilient the chart parameters and predictive dashas are.
    """
    base_d1 = calculate_d1_chart(year, month, day, hour, minute, second, tz_offset_hours, lat, lon)
    base_d9 = calculate_navamsa_chart(base_d1)
    base_dt = datetime(year, month, day, hour, minute, int(second))
    base_timeline = calculate_vimshottari_timeline(base_dt, base_d1.planets["Moon"].longitude)

    eval_dt = target_eval_date or (base_dt + timedelta(days=28 * 365.25))
    base_dasha = get_dasha_at_date(base_timeline, eval_dt)
    base_ad = base_dasha.antardasha if base_dasha else ""

    lagna_matches = 0
    d9_matches = 0
    dasha_matches = 0
    total_samples = 0

    minute_offsets = range(-window_minutes, window_minutes + 1, step_minutes)

    for offset in minute_offsets:
        total_samples += 1
        perturbed_dt = base_dt + timedelta(minutes=offset)

        # Compute perturbed chart
        p_d1 = calculate_d1_chart(
            perturbed_dt.year, perturbed_dt.month, perturbed_dt.day,
            perturbed_dt.hour, perturbed_dt.minute, perturbed_dt.second,
            tz_offset_hours, lat, lon
        )
        p_d9 = calculate_navamsa_chart(p_d1)

        # Check Lagna stability
        if p_d1.ascendant_sign == base_d1.ascendant_sign:
            lagna_matches += 1

        # Check D9 Lagna stability
        if p_d9.ascendant_d9_sign == base_d9.ascendant_d9_sign:
            d9_matches += 1

        # Check Dasha stability at evaluation target
        p_timeline = calculate_vimshottari_timeline(perturbed_dt, p_d1.planets["Moon"].longitude)
        p_dasha = get_dasha_at_date(p_timeline, eval_dt)
        p_ad = p_dasha.antardasha if p_dasha else ""

        if p_ad == base_ad:
            dasha_matches += 1

    lagna_ratio = lagna_matches / total_samples
    d9_ratio = d9_matches / total_samples
    dasha_ratio = dasha_matches / total_samples

    # Composite stability score: D1 (30%), D9 (40%), Dasha (30%)
    overall = (lagna_ratio * 30.0) + (d9_ratio * 40.0) + (dasha_ratio * 30.0)

    if overall >= 80.0:
        classification = "High"
        desc = f"Prediction remains consistent across {overall:.0f}% of plausible birth-time variance (±{window_minutes} mins)."
    elif overall >= 60.0:
        classification = "Moderate"
        desc = f"Moderate stability ({overall:.0f}%); Navamsa or sub-periods shift towards boundary of ±{window_minutes} mins."
    else:
        classification = "Birth-Time Sensitive"
        desc = f"Prediction is sensitive ({overall:.0f}% stability); Ascendant or Navamsa cusp lies within {window_minutes} mins."

    return SensitivityReport(
        window_minutes=window_minutes,
        samples_tested=total_samples,
        lagna_stable_ratio=round(lagna_ratio, 3),
        navamsa_stable_ratio=round(d9_ratio, 3),
        dasha_stable_ratio=round(dasha_ratio, 3),
        overall_stability_score=round(overall, 1),
        stability_classification=classification,
        details=desc
    )
