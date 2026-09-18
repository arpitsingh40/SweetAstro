"""Metric math for the accuracy harness (month-accurate, deterministic)."""

from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def month_index(year: int, month: int) -> int:
    return year * 12 + month


def top1_year(predicted_year: int, actual_year: int) -> bool:
    return predicted_year == actual_year


def top3_year(top3_years: Sequence[int], actual_year: int) -> bool:
    return actual_year in set(top3_years)


def hit_within(predicted_year: int, predicted_month: int,
               actual_year: int, actual_month: int, window_months: int) -> bool:
    return abs(month_index(predicted_year, predicted_month)
               - month_index(actual_year, actual_month)) <= window_months


def month_error(predicted_year: int, predicted_month: int,
                actual_year: int, actual_month: int) -> float:
    return float(abs(month_index(predicted_year, predicted_month)
                     - month_index(actual_year, actual_month)))


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (pct / 100.0)
    lower = int(k)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = k - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def bootstrap_ci(values: Sequence[float], reps: int = 2000, seed: int = 0,
                 alpha: float = 0.05) -> Tuple[float, float]:
    """Percentile bootstrap CI for the mean of `values`."""
    values = list(values)
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(reps):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return (percentile(means, 100 * alpha / 2), percentile(means, 100 * (1 - alpha / 2)))


def summarize(preds: Sequence[Dict], window_months: int = 12) -> Dict[str, float]:
    """Aggregate metrics over prediction/actual dict pairs.

    Each entry: {"predicted_year", "predicted_month", "top3_years", "actual_year",
    "actual_month"}. A withheld prediction (promise gate, protocol 1.2.0) counts
    as a miss for hit-rate endpoints and is excluded from MAE.
    """
    if not preds:
        return {
            "n": 0, "top1_year": 0.0, "top3_year": 0.0,
            f"hit_within_{window_months}_months": 0.0, "mae_months": 0.0,
            "n_withheld": 0,
        }
    n = len(preds)
    withheld = [p for p in preds if p.get("withheld")]
    scored = [p for p in preds if not p.get("withheld")]
    top1 = sum(1 for p in preds if top1_year(p["predicted_year"], p["actual_year"])) / n
    top3 = sum(1 for p in preds if top3_year(p.get("top3_years") or [], p["actual_year"])) / n
    hit = sum(1 for p in preds if hit_within(
        p["predicted_year"], p["predicted_month"],
        p["actual_year"], p["actual_month"], window_months)) / n
    mae = mean(month_error(
        p["predicted_year"], p["predicted_month"],
        p["actual_year"], p["actual_month"]) for p in scored) if scored else 0.0
    return {
        "n": n,
        "top1_year": round(top1 * 100.0, 1),
        "top3_year": round(top3 * 100.0, 1),
        f"hit_within_{window_months}_months": round(hit * 100.0, 1),
        "mae_months": round(mae, 1),
        "n_withheld": len(withheld),
    }


def calibration_table(preds: Sequence[Dict], score_key: str = "score",
                      bins: Optional[List[float]] = None) -> List[Dict]:
    """Hit-rate by engine confidence score bucket (small n => label as indicative).

    Withheld predictions carry no confidence score and are excluded.
    """
    preds = [p for p in preds if not p.get("withheld")]
    if bins is None:
        bins = [0, 25, 50, 75, 100.01]
    rows = []
    for lo, hi in zip(bins, bins[1:]):
        bucket = [p for p in preds if lo <= float(p.get(score_key, 0.0)) < hi]
        if not bucket:
            rows.append({"bin": f"{lo:g}-{hi:g}", "n": 0, "top1_year": None, "hit_12m": None})
            continue
        n = len(bucket)
        rows.append({
            "bin": f"{lo:g}-{hi:g}",
            "n": n,
            "top1_year": round(sum(1 for p in bucket if top1_year(p["predicted_year"], p["actual_year"])) / n * 100, 1),
            "hit_12m": round(sum(1 for p in bucket if hit_within(
                p["predicted_year"], p["predicted_month"],
                p["actual_year"], p["actual_month"], 12)) / n * 100, 1),
        })
    return rows
