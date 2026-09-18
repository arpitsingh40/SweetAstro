"""
Frozen evaluation protocol constants — see docs/accuracy_protocol.md.

Changing ANY value here invalidates prior results and requires a new
protocol version, a new freeze, and a fresh dataset.
"""

PROTOCOL_VERSION = "1.2.0"
PROTOCOL_DATE = "2026-09-13"

PROTOCOL_CHANGELOG = {
    "1.2.0": (
        "Model revision — the scored marriage-timing engine now applies the natal promise gate. "
        "When PredictionHierarchy.evaluate_promise nets below the moderate band (< -10), predict() "
        "withholds all timing candidates instead of returning a best year/month; withheld records "
        "count as automatic misses for hit-rate endpoints and are excluded from MAE (reported as "
        "n_withheld). Hierarchy levels 4-5 now score on the same ensemble scale as level 3 (the "
        "earlier 'calibrated_score' mix is removed). Endpoints, windows, split, seed and ensemble "
        "weights are unchanged. Requires a fresh freeze before scoring."
    ),
    "1.1.0": (
        "Rules revision only — endpoints, windows, split, seed and weights unchanged. "
        "Rule exceptions are now evaluated; previously unsupported condition types were "
        "implemented (in_sign, conjunct_with, dignity_at_least, transit_in_house, "
        "aspects_planet with dasha lords and planet aliases); duplicate/dead rule "
        "conditions corrected (MAR-0026, MAR-0035, MAR-0042, MAR-0043); legacy absolute "
        "wording replaced with calibrated language. Requires a fresh freeze."
    ),
    "1.0.0": "Initial frozen baseline.",
}

PROTOCOL = {
    "protocol_version": PROTOCOL_VERSION,
    "effective_date": PROTOCOL_DATE,
    "changelog": PROTOCOL_CHANGELOG,
    "model": "PredictionHierarchy.predict (legacy marriage timing engine)",
    "primary_endpoint": "top1_year_exact",
    "secondary_endpoints": [
        "top3_year",
        "hit_within_6_months",
        "hit_within_12_months",
        "hit_within_24_months",
        "mae_months",
    ],
    "search_window": {"min_age": 18, "max_age": 45},
    "hit_window_months": 12,
    "split": {"method": "sha256(chart_id + seed) ranked, exact train_pct/remainder", "train_pct": 70, "seed": 20260912},
    "included_rodden": ["AA", "A"],
    "baselines": ["uniform_random", "modal_age_month", "permutation_test"],
    "bootstrap": {"reps": 2000, "seed": 20260912},
    "permutation": {"reps": 1000, "seed": 20260912},
    "uniform_baseline": {"simulations": 2000, "seed": 20260912},
    "stopping_rule": (
        "Single pre-registered scoring run on the held-out test split. No post-hoc "
        "tuning. Any change to rules, weights, endpoints, windows or split requires a "
        "new protocol version and a fresh dataset."
    ),
}
