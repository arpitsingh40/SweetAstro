"""
Improved Convergence and Net Evidence Scoring.
Adds Yoga, Shadbala, combustion severity, and multi-factor weighting.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from ..rules.evaluator import EvaluationReport
from ..core.transits import DoubleTransitResult
from ..core.chart import D1Chart
from ..core.jaimini import JaiminiKarakas
from ..core.yogas import detect_yogas, YogaProfile
from ..core.shadbala import calculate_shadbala, ShadbalaScore, MAX_SHADBALA


@dataclass
class ConvergenceBreakdown:
    d1_support: float
    d9_support: float
    dasha_support: float
    transit_support: float
    jaimini_support: float
    yoga_bonus: float
    shadbala_bonus: float
    negative_obstruction: float
    raw_total: float
    calibrated_score: float
    evidence_level: str


def _count_yoga_matches(yoga_profile: YogaProfile, relevant_yogas: List[str]) -> int:
    count = 0
    for y in yoga_profile.yogas:
        if any(r in y.yoga_name for r in relevant_yogas):
            count += 1
    return count


def _best_shadbala_score(shadbala_scores: Dict[str, ShadbalaScore]) -> float:
    if not shadbala_scores:
        return 0.0
    best = max(s.total_bala for s in shadbala_scores.values())
    return best / MAX_SHADBALA * 10.0


def calculate_convergence_score(
    report: EvaluationReport,
    double_transit: DoubleTransitResult,
    d1: Optional[D1Chart] = None,
    karakas: Optional[JaiminiKarakas] = None,
) -> ConvergenceBreakdown:
    d1_support = min(25.0, report.promise_score * 0.6)

    d9_support = 0.0
    for r in report.matched_rules:
        conditions_text = " ".join(r.matched_conditions).lower()
        if ("d9" in conditions_text or "d9" in r.rule_id.lower()
                or r.rule_id == "MAR-0004"):
            d9_support += 15.0
        elif r.rule_id == "MAR-0024":
            d9_support += 10.0
    d9_support = min(20.0, d9_support)

    dasha_support = min(30.0, report.dasha_score * 0.8)

    transit_base = (double_transit.total_transit_score if double_transit else 0.0) * 0.20
    transit_rules = report.transit_score * 0.20
    transit_support = min(25.0, transit_base + transit_rules)

    jaimini_support = min(15.0, report.jaimini_score * 0.7)

    negative_obstruction = min(25.0, report.delay_score * 0.7)
    if double_transit and double_transit.is_active:
        negative_obstruction *= 0.7

    yoga_bonus = 0.0
    shadbala_bonus = 0.0
    if d1 and karakas:
        try:
            yoga_profile = detect_yogas(d1, None, karakas)
            rajayoga_count = yoga_profile.rajayoga_count
            if rajayoga_count >= 2:
                yoga_bonus = 8.0
            elif rajayoga_count == 1:
                yoga_bonus = 4.0
            for y in yoga_profile.yogas:
                if "Hamsa" in y.yoga_name or "Kesari" in y.yoga_name:
                    yoga_bonus += 2.0
            yoga_bonus = min(15.0, yoga_bonus)
        except Exception:
            pass

        try:
            shadbala_scores: Dict[str, ShadbalaScore] = {}
            for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
                if p in d1.planets:
                    shadbala_scores[p] = calculate_shadbala(d1.planets[p], d1)
            shadbala_bonus = _best_shadbala_score(shadbala_scores)
        except Exception:
            pass

    raw_sum = (d1_support + d9_support + dasha_support + transit_support
               + jaimini_support + yoga_bonus + shadbala_bonus
               - negative_obstruction)
    calibrated = max(5.0, min(100.0, raw_sum))

    if calibrated >= 85.0:
        level = "Very High"
    elif calibrated >= 70.0:
        level = "High"
    elif calibrated >= 50.0:
        level = "Moderate"
    else:
        level = "Weak"

    return ConvergenceBreakdown(
        d1_support=round(d1_support, 1),
        d9_support=round(d9_support, 1),
        dasha_support=round(dasha_support, 1),
        transit_support=round(transit_support, 1),
        jaimini_support=round(jaimini_support, 1),
        yoga_bonus=round(yoga_bonus, 1),
        shadbala_bonus=round(shadbala_bonus, 1),
        negative_obstruction=round(negative_obstruction, 1),
        raw_total=round(raw_sum, 1),
        calibrated_score=round(calibrated, 1),
        evidence_level=level,
    )