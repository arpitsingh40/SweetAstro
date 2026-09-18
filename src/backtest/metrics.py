"""
Empirical Backtesting Metrics (machinery validation).

These metrics score the engine on the small seed dataset. They are
**machinery validation only**: the seed set is far below the protocol's
>=500-chart requirement, so no accuracy claim may be derived from them
(docs/accuracy_protocol.md). Every summary carries an explicit claim note.

Naming (audit round 2): `within_2_months_share` was previously mislabelled
"top_3_month_accuracy" (it counts records within +/-2 months), and
`high_confidence_top3_year_share` was previously "calibration_score" (it is a
hit share among high-score records, not a calibration curve).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math

MACHINERY_VALIDATION_NOTE = (
    "Machinery validation only — not an accuracy claim. The seed dataset is far below the "
    "pre-registered >=500-chart requirement (docs/accuracy_protocol.md)."
)


@dataclass
class SingleEvaluationRecord:
    prediction_id: str
    chart_id: str
    predicted_year: int
    predicted_month: int
    predicted_period_label: str
    actual_year: int
    actual_month: int
    actual_date_str: str
    is_top_1_year: bool
    is_top_3_year: bool
    year_error: int
    month_error: float
    confidence_score: float
    stability_score: float
    withheld: bool = False   # promise gate produced no timing (protocol 1.2.0)


@dataclass
class BacktestSummaryMetrics:
    total_charts_tested: int
    top_1_year_accuracy: float       # Percentage (0 - 100)
    top_3_year_accuracy: float       # Percentage (0 - 100)
    top_1_month_accuracy: float      # Percentage (0 - 100)
    within_2_months_share: float     # Percentage (0 - 100); was "top_3_month_accuracy"
    mean_absolute_error_months: float
    median_absolute_error_months: float
    std_dev_months: float
    confidence_interval_95: (float, float)  # 95% CI for MAE
    high_confidence_top3_year_share: float  # was "calibration_score"
    claim_note: str = MACHINERY_VALIDATION_NOTE


def calculate_month_delta(p_yr: int, p_m: int, a_yr: int, a_m: int) -> float:
    """Calculates absolute error in months between predicted and actual date."""
    p_total = (p_yr * 12) + p_m
    a_total = (a_yr * 12) + a_m
    return abs(p_total - a_total)


def compute_summary_metrics(records: List[SingleEvaluationRecord]) -> BacktestSummaryMetrics:
    """Computes comprehensive empirical metrics across all evaluated records."""
    n = len(records)
    if n == 0:
        return BacktestSummaryMetrics(
            0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, (0.0, 0.0), 0.0
        )

    top_1_yr = sum(1 for r in records if r.is_top_1_year) / n * 100.0
    top_3_yr = sum(1 for r in records if r.is_top_3_year) / n * 100.0
    top_1_m = sum(1 for r in records if r.month_error == 0 and not r.withheld) / n * 100.0
    top_3_m = sum(1 for r in records if r.month_error <= 2 and not r.withheld) / n * 100.0

    # Withheld records carry no delta and are excluded from error statistics
    # (they still count as misses in the hit-rate shares above).
    month_errors = [r.month_error for r in records if not r.withheld]
    n_scored = len(month_errors)
    mae = sum(month_errors) / n_scored if n_scored else 0.0

    sorted_err = sorted(month_errors)
    mid = n_scored // 2
    if n_scored == 0:
        median_err = 0.0
    elif n_scored % 2 == 1:
        median_err = sorted_err[mid]
    else:
        median_err = (sorted_err[mid - 1] + sorted_err[mid]) / 2.0

    variance = sum((e - mae) ** 2 for e in month_errors) / max(1, n_scored - 1)
    std_dev = math.sqrt(variance)
    standard_error = std_dev / math.sqrt(n_scored) if n_scored else 0.0
    margin = 1.96 * standard_error
    ci_95 = (round(max(0.0, mae - margin), 2), round(mae + margin, 2))

    # High-confidence hit share: compare high-confidence records' top-3-year hits
    high_conf = [r for r in records if r.confidence_score >= 75.0]
    high_conf_acc = (sum(1 for r in high_conf if r.is_top_3_year) / len(high_conf) * 100.0) if high_conf else 0.0

    return BacktestSummaryMetrics(
        total_charts_tested=n,
        top_1_year_accuracy=round(top_1_yr, 1),
        top_3_year_accuracy=round(top_3_yr, 1),
        top_1_month_accuracy=round(top_1_m, 1),
        within_2_months_share=round(top_3_m, 1),
        mean_absolute_error_months=round(mae, 2),
        median_absolute_error_months=round(median_err, 2),
        std_dev_months=round(std_dev, 2),
        confidence_interval_95=ci_95,
        high_confidence_top3_year_share=round(high_conf_acc, 1),
    )
