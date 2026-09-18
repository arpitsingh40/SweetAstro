"""
Accuracy evaluation harness.

Pipeline: load+validate dataset → verify pre-registration manifest →
deterministic held-out split → engine predictions → metrics on test →
chance baselines → permutation test → calibration → result payload.

The harness makes no accuracy claim by itself; see docs/accuracy_protocol.md.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.chart import calculate_d1_chart
from ..core.dasha import calculate_vimshottari_timeline
from ..core.jaimini import calculate_chara_karakas, calculate_jaimini_points
from ..core.navamsa import calculate_navamsa_chart
from ..service import SweetAstroEngine
from .baselines import modal_age_month_baseline, permutation_test, uniform_random_baseline
from .dataset import ChartRecord, load_dataset, split_records, validate_records
from .metrics import bootstrap_ci, calibration_table, hit_within, month_error, summarize
from .preregistration import MANIFEST_PATH, build_manifest, verify_manifest, write_manifest
from .protocol import PROTOCOL

RULES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "rules"


@dataclass
class PredictedRecord:
    chart_id: str
    rodden: str
    predicted_year: int
    predicted_month: int
    top3_years: List[int]
    score: float
    actual_year: int
    actual_month: int
    predicted_label: str = ""
    withheld: bool = False

    def to_metrics_dict(self) -> Dict:
        return {
            "predicted_year": self.predicted_year,
            "predicted_month": self.predicted_month,
            "top3_years": self.top3_years,
            "actual_year": self.actual_year,
            "actual_month": self.actual_month,
            "score": self.score,
            "withheld": self.withheld,
        }


@dataclass
class EvaluationResult:
    protocol_version: str
    dataset_path: str
    manifest: Dict
    validation: Dict
    n_train: int
    n_test: int
    coverage_pct: float
    engine_test: Dict
    engine_test_ci: Dict
    engine_train: Dict
    engine_test_all_ratings: Dict
    uniform_baseline: Dict
    modal_baseline: Dict
    permutation: Dict
    calibration: List[Dict]
    per_chart_test: List[Dict]
    runtime_seconds: float
    generated_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> Dict:
        return asdict(self)


def predict_chart(engine: SweetAstroEngine, record: ChartRecord,
                  min_age: int, max_age: int) -> PredictedRecord:
    birth_dt = record.birth_datetime
    d1 = calculate_d1_chart(
        record.dob.year, record.dob.month, record.dob.day,
        birth_dt.hour, birth_dt.minute, birth_dt.second,
        record.tz_offset, record.lat, record.lon,
    )
    d9 = calculate_navamsa_chart(d1)
    karakas = calculate_chara_karakas(d1)
    jaimini_pts = calculate_jaimini_points(d1, d9)
    timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)

    pred = engine.hierarchy.predict(
        d1, d9, karakas, jaimini_pts, birth_dt, timeline,
        search_start_age=min_age, search_end_age=max_age,
    )
    if not pred.promise_indicated:
        # Protocol 1.2.0: the promise gate withholds timing. The record is kept
        # as an automatic miss for hit-rate endpoints (excluded from MAE).
        return PredictedRecord(
            chart_id=record.chart_id,
            rodden=record.rodden,
            predicted_year=0,
            predicted_month=0,
            top3_years=[],
            score=0.0,
            actual_year=record.marriage_date.year,
            actual_month=record.marriage_date.month,
            predicted_label="withheld (weak natal promise)",
            withheld=True,
        )
    best_month = pred.top_months[0] if pred.top_months else None
    return PredictedRecord(
        chart_id=record.chart_id,
        rodden=record.rodden,
        predicted_year=pred.best_year,
        predicted_month=(best_month.month if best_month and best_month.month else 6),
        top3_years=[c.year for c in pred.top_years[:3]],
        score=pred.best_month_score,
        actual_year=record.marriage_date.year,
        actual_month=record.marriage_date.month,
        predicted_label=pred.best_month,
    )


def _ci_over_records(preds: List[PredictedRecord], metric: str, protocol: Dict) -> Dict:
    seed = protocol["bootstrap"]["seed"]
    reps = protocol["bootstrap"]["reps"]
    if metric == "top1_year":
        values = [1.0 if p.predicted_year == p.actual_year else 0.0 for p in preds]
    elif metric == "hit_12m":
        values = [1.0 if hit_within(p.predicted_year, p.predicted_month,
                                     p.actual_year, p.actual_month, 12) else 0.0 for p in preds]
    elif metric == "mae_months":
        values = [month_error(p.predicted_year, p.predicted_month,
                              p.actual_year, p.actual_month)
                  for p in preds if not p.withheld]
    else:
        raise ValueError(metric)
    lo, hi = bootstrap_ci(values, reps=reps, seed=seed)
    scale = 100.0 if metric != "mae_months" else 1.0
    return {"lo": round(lo * scale, 1), "hi": round(hi * scale, 1)}


def run_evaluation(dataset_path: Path, *,
                   protocol: Optional[Dict] = None,
                   manifest_path: Path = MANIFEST_PATH,
                   allow_freeze: bool = False) -> EvaluationResult:
    protocol = protocol or PROTOCOL
    started = time.monotonic()
    dataset_path = Path(dataset_path)

    records = load_dataset(dataset_path)
    validation = validate_records(records,
                                  protocol["search_window"]["min_age"],
                                  protocol["search_window"]["max_age"])
    if not validation.ok:
        raise ValueError("Dataset validation errors:\n  " + "\n  ".join(validation.errors))

    manifest = build_manifest(protocol, dataset_path, records, RULES_DIR)
    if allow_freeze:
        write_manifest(manifest_path, manifest)
    else:
        ok, diffs = verify_manifest(manifest_path, manifest)
        if not ok:
            raise RuntimeError(
                "Pre-registration check failed — refusing to score.\n  "
                + "\n  ".join(diffs)
                + "\nRe-freeze only after reviewing the changes (new protocol version required "
                  "for endpoint/rule changes)."
            )

    train, test = split_records(records, seed=protocol["split"]["seed"],
                                train_pct=protocol["split"]["train_pct"])
    primary_train = [r for r in train if r.included_primary]
    primary_test = [r for r in test if r.included_primary]

    engine = SweetAstroEngine()
    min_age = protocol["search_window"]["min_age"]
    max_age = protocol["search_window"]["max_age"]

    predictions: Dict[str, PredictedRecord] = {}
    for rec in records:
        predictions[rec.chart_id] = predict_chart(engine, rec, min_age, max_age)

    test_preds = [predictions[r.chart_id] for r in primary_test]
    train_preds = [predictions[r.chart_id] for r in primary_train]
    all_primary = [predictions[r.chart_id] for r in records if r.included_primary]
    all_ratings_test = [predictions[r.chart_id] for r in test]

    engine_test = summarize([p.to_metrics_dict() for p in test_preds], protocol["hit_window_months"])
    engine_train = summarize([p.to_metrics_dict() for p in train_preds], protocol["hit_window_months"])
    engine_all = summarize([p.to_metrics_dict() for p in all_primary], protocol["hit_window_months"])

    uniform = uniform_random_baseline(
        primary_test, min_age, max_age,
        simulations=protocol["uniform_baseline"]["simulations"],
        seed=protocol["uniform_baseline"]["seed"],
        window_months=protocol["hit_window_months"],
    )
    modal = modal_age_month_baseline(primary_train, primary_test, min_age, max_age)

    p_value, observed = permutation_test(
        [p.predicted_year for p in test_preds],
        [p.actual_year for p in test_preds],
        reps=protocol["permutation"]["reps"],
        seed=protocol["permutation"]["seed"],
    )

    coverage = 0.0
    if primary_test:
        coverage = sum(1 for r in primary_test
                       if min_age <= r.marriage_age_years <= max_age) / len(primary_test) * 100.0

    return EvaluationResult(
        protocol_version=protocol["protocol_version"],
        dataset_path=str(dataset_path),
        manifest=manifest,
        validation={
            "n_records": validation.n_records,
            "n_primary": validation.n_primary,
            "rodden_counts": validation.rodden_counts,
            "outside_window": validation.outside_window,
            "duplicates": validation.duplicates,
            "warnings": validation.warnings,
        },
        n_train=len(primary_train),
        n_test=len(primary_test),
        coverage_pct=round(coverage, 1),
        engine_test=engine_test,
        engine_test_ci={
            "top1_year": _ci_over_records(test_preds, "top1_year", protocol),
            "hit_12m": _ci_over_records(test_preds, "hit_12m", protocol),
            "mae_months": _ci_over_records(test_preds, "mae_months", protocol),
        },
        engine_train=engine_train,
        engine_test_all_ratings=summarize([p.to_metrics_dict() for p in all_ratings_test],
                                          protocol["hit_window_months"]),
        uniform_baseline=uniform,
        modal_baseline=modal,
        permutation={"p_value": p_value, "observed_top1_pct": observed},
        calibration=calibration_table([p.to_metrics_dict() for p in test_preds]),
        per_chart_test=[
            {
                "chart_id": p.chart_id,
                "rodden": p.rodden,
                "predicted": p.predicted_label,
                "actual": f"{p.actual_year}-{p.actual_month:02d}",
                "error_months": (None if p.withheld
                                 else int(month_error(p.predicted_year, p.predicted_month,
                                                      p.actual_year, p.actual_month))),
                "top1": p.predicted_year == p.actual_year,
            }
            for p in test_preds
        ],
        runtime_seconds=round(time.monotonic() - started, 2),
    )
