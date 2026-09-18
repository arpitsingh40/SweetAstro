"""
Progressive Time-Resolution Prediction Engine.
Implements the 6-Level Hierarchy:
Level 1: Marriage Promise
Level 2: Likely Age Range
Level 3: Candidate Years
Level 4: Candidate Quarters
Level 5: Candidate Months
Level 6: Date Window
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..core.chart import D1Chart
from ..core.navamsa import NavamsaChart
from ..core.jaimini import JaiminiKarakas, JaiminiPoints
from ..core.dasha import DashaPeriod, get_dasha_at_date
from ..core.transits import evaluate_double_transit, get_transit_positions
from ..rules.evaluator import RuleEvaluator
from .convergence import calculate_convergence_score, ConvergenceBreakdown
from .ensemble import EnsembleWeights, SystemEnsemble


@dataclass
class CandidatePeriod:
    label: str               # e.g., "2028", "Q1 2028", "March 2028"
    year: int
    month: Optional[int]
    eval_date: datetime
    convergence: ConvergenceBreakdown
    score_share_pct: float   # share of the summed ensemble score (not a probability)
    dasha_summary: str
    transit_summary: str


@dataclass
class ProgressivePrediction:
    promise_indicated: bool
    promise_strength: str    # "Strong", "Moderate", "Delayed"
    age_range: Tuple[int, int]
    top_years: List[CandidatePeriod]
    top_quarters: List[CandidatePeriod]
    top_months: List[CandidatePeriod]
    best_year: int
    best_quarter: str
    best_month: str
    best_month_score: float
    all_monthly_scores: Dict[str, float]  # "Jan": 61, "Feb": 74, "Mar": 93...


class PredictionHierarchy:
    def __init__(self, evaluator: RuleEvaluator):
        self.evaluator = evaluator

    def evaluate_promise(self, d1: D1Chart, d9: NavamsaChart) -> Tuple[bool, str, float]:
        """Level 1: Evaluates whether marriage is indicated and measures natal delay factors.

        The gate is real: an obstructed net promise below the moderate band
        returns ``indicated=False`` so ``predict`` withholds all timing.
        """
        # Evaluate natal chart at birth date for promise and delay
        now = datetime.now()
        report = self.evaluator.evaluate(
            d1, d9, None, None, now
        )
        promise_net = report.promise_score - report.delay_score

        if promise_net >= 10.0:
            return True, "Strong", report.delay_score
        elif promise_net >= -10.0:
            return True, "Moderate / Delayed", report.delay_score
        else:
            return False, "Delayed / Challenging", report.delay_score

    def determine_age_range(self, delay_score: float) -> Tuple[int, int]:
        """Level 2: Determines probable age bracket."""
        if delay_score >= 15.0:
            return (26, 40)
        elif delay_score >= 8.0:
            return (21, 36)
        else:
            return (18, 34)

    def predict(
        self,
        d1: D1Chart,
        d9: NavamsaChart,
        karakas: JaiminiKarakas,
        jaimini_pts: JaiminiPoints,
        birth_dt: datetime,
        dasha_timeline: List[DashaPeriod],
        search_start_age: Optional[int] = None,
        search_end_age: Optional[int] = None,
        ensemble_weights: Optional[EnsembleWeights] = None
    ) -> ProgressivePrediction:
        """
        Runs the progressive hierarchy from Level 1 to Level 5.
        """
        ensemble = SystemEnsemble(ensemble_weights)

        # Level 1: Promise
        is_indicated, promise_strength, delay_score = self.evaluate_promise(d1, d9)

        # Level 2: Age Range
        auto_min_age, auto_max_age = self.determine_age_range(delay_score)
        min_age = search_start_age or auto_min_age
        max_age = search_end_age or auto_max_age

        if not is_indicated:
            # Promise gate: an obstructed natal promise withholds all timing
            # candidates instead of naming a "best" year/month. Protocol 1.2.0.
            return ProgressivePrediction(
                promise_indicated=False,
                promise_strength=promise_strength,
                age_range=(min_age, max_age),
                top_years=[],
                top_quarters=[],
                top_months=[],
                best_year=0,
                best_quarter="",
                best_month="",
                best_month_score=0.0,
                all_monthly_scores={},
            )

        # Level 3: Candidate Years
        start_year = birth_dt.year + min_age
        end_year = birth_dt.year + max_age

        candidate_years: List[CandidatePeriod] = []
        year_scores: List[float] = []

        for yr in range(start_year, end_year + 1):
            eval_dt = datetime(yr, 6, 15, 12, 0, 0)
            dasha = get_dasha_at_date(dasha_timeline, eval_dt)
            dt_result = evaluate_double_transit(d1, eval_dt)
            transits = get_transit_positions(eval_dt)

            report = self.evaluator.evaluate(
                d1, d9, karakas, jaimini_pts, eval_dt, dasha, dt_result, transits
            )
            convergence = calculate_convergence_score(report, dt_result, d1, karakas)
            score = ensemble.score_period(convergence, ensemble_weights)
            year_scores.append(score)

            dasha_desc = f"{dasha.mahadasha}/{dasha.antardasha}" if dasha else "N/A"
            candidate_years.append(
                CandidatePeriod(
                    label=str(yr),
                    year=yr,
                    month=None,
                    eval_date=eval_dt,
                    convergence=convergence,
                    score_share_pct=0.0,
                    dasha_summary=dasha_desc,
                    transit_summary=dt_result.description
                )
            )

        # Proportional score share (not a calibrated probability)
        total_score = sum(year_scores) or 1.0
        for cp in candidate_years:
            cp_score = ensemble.score_period(cp.convergence, ensemble_weights)
            cp.score_share_pct = round((cp_score / total_score) * 100.0, 1)

        candidate_years.sort(key=lambda x: ensemble.score_period(x.convergence, ensemble_weights), reverse=True)
        best_year = candidate_years[0].year

        # Level 4: Candidate Quarters for Best Year
        quarters = [
            ("Q1", 2, 15),
            ("Q2", 5, 15),
            ("Q3", 8, 15),
            ("Q4", 11, 15),
        ]
        candidate_quarters: List[CandidatePeriod] = []
        q_scores: List[float] = []

        for q_label, m, d in quarters:
            eval_dt = datetime(best_year, m, d, 12, 0, 0)
            dasha = get_dasha_at_date(dasha_timeline, eval_dt)
            dt_result = evaluate_double_transit(d1, eval_dt)
            transits = get_transit_positions(eval_dt)

            report = self.evaluator.evaluate(
                d1, d9, karakas, jaimini_pts, eval_dt, dasha, dt_result, transits
            )
            conv = calculate_convergence_score(report, dt_result, d1, karakas)
            q_scores.append(ensemble.score_period(conv, ensemble_weights))
            dasha_desc = f"{dasha.mahadasha}/{dasha.antardasha}/{dasha.pratyantardasha}" if dasha else "N/A"

            candidate_quarters.append(
                CandidatePeriod(
                    label=f"{q_label} {best_year}",
                    year=best_year,
                    month=m,
                    eval_date=eval_dt,
                    convergence=conv,
                    score_share_pct=0.0,
                    dasha_summary=dasha_desc,
                    transit_summary=dt_result.description
                )
            )

        total_q = sum(q_scores) or 1.0
        for cq in candidate_quarters:
            cq_score = ensemble.score_period(cq.convergence, ensemble_weights)
            cq.score_share_pct = round((cq_score / total_q) * 100.0, 1)

        candidate_quarters.sort(key=lambda x: ensemble.score_period(x.convergence, ensemble_weights), reverse=True)
        best_quarter = candidate_quarters[0].label

        # Level 5: Candidate Months for Best Year (all 12 months)
        candidate_months: List[CandidatePeriod] = []
        all_monthly_scores: Dict[str, float] = {}
        month_names = [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December"
        ]

        m_scores = []
        for m_idx in range(1, 13):
            eval_dt = datetime(best_year, m_idx, 15, 12, 0, 0)
            dasha = get_dasha_at_date(dasha_timeline, eval_dt)
            dt_result = evaluate_double_transit(d1, eval_dt)
            transits = get_transit_positions(eval_dt)

            report = self.evaluator.evaluate(
                d1, d9, karakas, jaimini_pts, eval_dt, dasha, dt_result, transits
            )
            conv = calculate_convergence_score(report, dt_result, d1, karakas)
            m_score = ensemble.score_period(conv, ensemble_weights)
            m_name = month_names[m_idx - 1]
            all_monthly_scores[m_name] = m_score
            m_scores.append(m_score)

            dasha_desc = f"{dasha.mahadasha}/{dasha.antardasha}/{dasha.pratyantardasha}" if dasha else "N/A"
            candidate_months.append(
                CandidatePeriod(
                    label=f"{m_name} {best_year}",
                    year=best_year,
                    month=m_idx,
                    eval_date=eval_dt,
                    convergence=conv,
                    score_share_pct=0.0,
                    dasha_summary=dasha_desc,
                    transit_summary=dt_result.description
                )
            )

        total_m = sum(m_scores) or 1.0
        for cm in candidate_months:
            cm_score = ensemble.score_period(cm.convergence, ensemble_weights)
            cm.score_share_pct = round((cm_score / total_m) * 100.0, 1)

        candidate_months.sort(key=lambda x: ensemble.score_period(x.convergence, ensemble_weights), reverse=True)
        best_month_cand = candidate_months[0]
        best_month_score = ensemble.score_period(best_month_cand.convergence, ensemble_weights)

        return ProgressivePrediction(
            promise_indicated=is_indicated,
            promise_strength=promise_strength,
            age_range=(min_age, max_age),
            top_years=candidate_years[:5],
            top_quarters=candidate_quarters,
            top_months=candidate_months[:5],
            best_year=best_year,
            best_quarter=best_quarter,
            best_month=best_month_cand.label,
            best_month_score=best_month_score,
            all_monthly_scores=all_monthly_scores
        )
