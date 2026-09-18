"""
Explicit chance baselines for the accuracy harness.

- uniform_random: predictions drawn uniformly inside the search window
  (simulated `simulations` times; mean and 95% interval reported).
- modal_age_month: predict the modal marriage age+month fitted on the TRAIN
  split only.
- permutation_test: shuffle actuals across charts and recompute the primary
  endpoint to obtain a p-value for the engine's observed hit rate.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Tuple

from .dataset import ChartRecord
from .metrics import hit_within, mean, percentile, top1_year


def _window_years(record: ChartRecord, min_age: int, max_age: int) -> List[int]:
    return [record.dob.year + age for age in range(min_age, max_age + 1)]


def uniform_random_baseline(records: List[ChartRecord], min_age: int, max_age: int,
                            simulations: int = 2000, seed: int = 0,
                            window_months: int = 12) -> Dict[str, float]:
    if not records:
        return {"top1_year": 0.0, "top1_lo": 0.0, "top1_hi": 0.0,
                "hit_12m": 0.0, "hit_lo": 0.0, "hit_hi": 0.0}
    rng = random.Random(seed)
    top1_runs: List[float] = []
    hit_runs: List[float] = []
    for _ in range(simulations):
        t1 = 0
        h12 = 0
        for rec in records:
            year = rng.choice(_window_years(rec, min_age, max_age))
            month = rng.randint(1, 12)
            t1 += top1_year(year, rec.marriage_date.year)
            h12 += hit_within(year, month, rec.marriage_date.year, rec.marriage_date.month, window_months)
        top1_runs.append(t1 / len(records) * 100.0)
        hit_runs.append(h12 / len(records) * 100.0)
    top1_runs.sort()
    hit_runs.sort()
    return {
        "top1_year": round(mean(top1_runs), 1),
        "top1_lo": round(percentile(top1_runs, 2.5), 1),
        "top1_hi": round(percentile(top1_runs, 97.5), 1),
        "hit_12m": round(mean(hit_runs), 1),
        "hit_lo": round(percentile(hit_runs, 2.5), 1),
        "hit_hi": round(percentile(hit_runs, 97.5), 1),
    }


def modal_age_month_baseline(train: List[ChartRecord], test: List[ChartRecord],
                             min_age: int, max_age: int) -> Dict[str, float]:
    if not train or not test:
        return {"top1_year": 0.0, "hit_12m": 0.0, "modal_age": None, "modal_month": None}
    ages = Counter(int(round(r.marriage_age_years)) for r in train)
    months = Counter(r.marriage_date.month for r in train)
    modal_age = ages.most_common(1)[0][0]
    modal_month = months.most_common(1)[0][0]
    top1 = 0
    hit = 0
    for rec in test:
        year = rec.dob.year + min(max(modal_age, min_age), max_age)
        top1 += top1_year(year, rec.marriage_date.year)
        hit += hit_within(year, modal_month, rec.marriage_date.year, rec.marriage_date.month, 12)
    n = len(test)
    return {
        "top1_year": round(top1 / n * 100.0, 1),
        "hit_12m": round(hit / n * 100.0, 1),
        "modal_age": modal_age,
        "modal_month": modal_month,
    }


def permutation_test(predicted_years: List[int], actual_years: List[int],
                     reps: int = 1000, seed: int = 0) -> Tuple[float, float]:
    """One-sided permutation p-value for the primary endpoint (top-1 year)."""
    n = len(predicted_years)
    if n == 0:
        return (1.0, 0.0)
    observed = sum(1 for p, a in zip(predicted_years, actual_years) if p == a) / n
    rng = random.Random(seed)
    shuffled = list(actual_years)
    at_least = 0
    for _ in range(reps):
        rng.shuffle(shuffled)
        stat = sum(1 for p, a in zip(predicted_years, shuffled) if p == a) / n
        if stat >= observed - 1e-12:
            at_least += 1
    p_value = (at_least + 1) / (reps + 1)
    return (round(p_value, 4), round(observed * 100.0, 1))
