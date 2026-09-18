"""
Blind Backtesting Runner.
Implements Point 23 and 35: Strict blind backtesting where prediction is computed
and stamped with an immutable Prediction ID before ground-truth marriage data is unblinded.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..core.chart import calculate_d1_chart
from ..core.navamsa import calculate_navamsa_chart
from ..core.jaimini import calculate_chara_karakas, calculate_jaimini_points
from ..core.dasha import calculate_vimshottari_timeline
from ..rules.loader import RuleCatalog
from ..rules.evaluator import RuleEvaluator
from ..prediction.hierarchy import PredictionHierarchy
from ..prediction.ensemble import EnsembleWeights
from ..prediction.sensitivity import evaluate_birth_time_sensitivity
from .metrics import (
    SingleEvaluationRecord, BacktestSummaryMetrics,
    calculate_month_delta, compute_summary_metrics
)


class BlindBacktestRunner:
    def __init__(self, catalog: RuleCatalog):
        self.catalog = catalog
        self.evaluator = RuleEvaluator(catalog)
        self.hierarchy = PredictionHierarchy(self.evaluator)
        self.prediction_counter = 0

    def generate_prediction_id(self) -> str:
        self.prediction_counter += 1
        return f"SA-MAR-{self.prediction_counter:06d}"

    def run_single_blind_chart(
        self,
        chart_data: Dict[str, Any],
        ensemble_weights: Optional[EnsembleWeights] = None
    ) -> SingleEvaluationRecord:
        """
        Executes blind evaluation:
        1. Computes prediction using only birth data.
        2. Assigns immutable Prediction ID.
        3. Unblinds actual marriage date and measures error.
        """
        # Step 1: Parse birth data
        dob_parts = [int(p) for p in chart_data["dob"].split("-")]
        tob_parts = [int(float(p)) for p in chart_data["tob"].split(":")]
        tz = float(chart_data.get("tz_offset", 0.0))
        lat = float(chart_data["lat"])
        lon = float(chart_data["lon"])

        birth_dt = datetime(dob_parts[0], dob_parts[1], dob_parts[2], tob_parts[0], tob_parts[1], tob_parts[2])

        # Step 2: Compute chart and timelines
        d1 = calculate_d1_chart(
            dob_parts[0], dob_parts[1], dob_parts[2],
            tob_parts[0], tob_parts[1], tob_parts[2],
            tz, lat, lon
        )
        d9 = calculate_navamsa_chart(d1)
        karakas = calculate_chara_karakas(d1)
        jaimini_pts = calculate_jaimini_points(d1, d9)
        dasha_timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)

        # Step 3: Pure Blind Prediction
        pred = self.hierarchy.predict(
            d1, d9, karakas, jaimini_pts, birth_dt, dasha_timeline,
            ensemble_weights=ensemble_weights
        )

        # Immutable Prediction ID assignment
        pred_id = self.generate_prediction_id()

        # Step 4: Sensitivity analysis
        sensitivity = evaluate_birth_time_sensitivity(
            dob_parts[0], dob_parts[1], dob_parts[2],
            tob_parts[0], tob_parts[1], tob_parts[2],
            tz, lat, lon,
            window_minutes=10,
            step_minutes=2
        )

        # Step 5: Unblind actual outcome
        actual_yr = int(chart_data["marriage_year"])
        actual_m = int(chart_data.get("marriage_month", 6))
        actual_date_str = chart_data.get("marriage_date", f"{actual_yr}-{actual_m:02d}-15")

        predicted_yr = pred.best_year
        # Extract best month number
        top_months = pred.top_months
        best_cand_month = top_months[0].month if top_months and top_months[0].month else 6

        if not pred.promise_indicated:
            # Promise gate (protocol 1.2.0): no timing was produced. Record an
            # explicit withheld entry (misses all hit-rate endpoints; excluded
            # from MAE) instead of silently scoring the sentinel year 0.
            return SingleEvaluationRecord(
                prediction_id=pred_id,
                chart_id=chart_data.get("chart_id", "UNKNOWN"),
                predicted_year=0,
                predicted_month=0,
                predicted_period_label="withheld (weak natal promise)",
                actual_year=actual_yr,
                actual_month=actual_m,
                actual_date_str=actual_date_str,
                is_top_1_year=False,
                is_top_3_year=False,
                year_error=0,
                month_error=0.0,
                confidence_score=0.0,
                stability_score=sensitivity.overall_stability_score,
                withheld=True,
            )

        # Measure Errors
        top_3_years = [cp.year for cp in pred.top_years[:3]]
        is_top_1_yr = (predicted_yr == actual_yr)
        is_top_3_yr = (actual_yr in top_3_years)
        yr_error = abs(predicted_yr - actual_yr)
        m_error = calculate_month_delta(predicted_yr, best_cand_month, actual_yr, actual_m)

        return SingleEvaluationRecord(
            prediction_id=pred_id,
            chart_id=chart_data.get("chart_id", "UNKNOWN"),
            predicted_year=predicted_yr,
            predicted_month=best_cand_month,
            predicted_period_label=pred.best_month,
            actual_year=actual_yr,
            actual_month=actual_m,
            actual_date_str=actual_date_str,
            is_top_1_year=is_top_1_yr,
            is_top_3_year=is_top_3_yr,
            year_error=yr_error,
            month_error=m_error,
            confidence_score=pred.best_month_score,
            stability_score=sensitivity.overall_stability_score
        )

    def run_dataset_backtest(
        self,
        dataset_path: Path,
        ensemble_weights: Optional[EnsembleWeights] = None
    ) -> Tuple[BacktestSummaryMetrics, List[SingleEvaluationRecord]]:
        """Runs batch blind backtest over a JSON dataset file."""
        with open(dataset_path, "r", encoding="utf-8") as f:
            charts = json.load(f)

        records: List[SingleEvaluationRecord] = []
        for c in charts:
            rec = self.run_single_blind_chart(c, ensemble_weights=ensemble_weights)
            records.append(rec)

        summary = compute_summary_metrics(records)
        return summary, records
