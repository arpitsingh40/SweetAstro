"""
Tests for the accuracy evaluation harness.

These tests validate the *evaluation machinery* (metrics, split, manifest,
baselines), not astrological performance.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from SweetAstro.src.evaluation.baselines import (
    modal_age_month_baseline, permutation_test, uniform_random_baseline,
)
from SweetAstro.src.evaluation.dataset import (
    ChartRecord, load_dataset, split_records, validate_records,
)
from SweetAstro.src.evaluation.metrics import (
    bootstrap_ci, calibration_table, hit_within, month_error, summarize, top3_year,
)
from SweetAstro.src.evaluation.preregistration import (
    build_manifest, dataset_fingerprint, verify_manifest, write_manifest,
)
from SweetAstro.src.evaluation.protocol import PROTOCOL
from SweetAstro.src.evaluation.report import render_markdown

DATA_DIR = Path(__file__).parent.parent / "data"
RULES_DIR = DATA_DIR / "rules"
SEED_DATASET = DATA_DIR / "test_charts" / "historical_verified.json"


def _record(chart_id="T-1", rodden="AA", dob=date(1990, 1, 1),
            marriage=date(2018, 6, 15), lat=28.6, lon=77.2):
    return ChartRecord(
        chart_id=chart_id, rodden=rodden, dob=dob, tob="12:00:00",
        tz_offset=5.5, lat=lat, lon=lon, marriage_date=marriage,
    )


# ---------------------------------------------------------------- dataset

def test_load_seed_dataset():
    records = load_dataset(SEED_DATASET)
    assert len(records) == 5
    assert all(r.rodden in ("AA", "A") for r in records)
    assert all(r.marriage_date > r.dob for r in records)
    assert records[0].birth_datetime.hour in range(24)


def test_csv_roundtrip(tmp_path):
    csv_path = tmp_path / "d.csv"
    csv_path.write_text(
        "chart_id,name,rodden,dob,tob,tz_offset,lat,lon,marriage_date,marriage_type,source\n"
        "C1,Test,AA,1990-01-01,12:00:00,5.5,28.61,77.20,2018-06-15,first,unit-test\n",
        encoding="utf-8",
    )
    records = load_dataset(csv_path)
    assert len(records) == 1
    assert records[0].chart_id == "C1"
    assert records[0].marriage_age_years == pytest.approx(28.45, abs=0.05)


def test_marriage_before_birth_rejected(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "chart_id,rodden,dob,tob,tz_offset,lat,lon,marriage_date\n"
        "C1,AA,1990-01-01,12:00:00,5.5,28.61,77.20,1980-06-15\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not after dob"):
        load_dataset(csv_path)


def test_validate_catches_duplicate_ids():
    records = [_record("DUP"), _record("DUP")]
    report = validate_records(records)
    assert not report.ok
    assert any("duplicate chart_id" in e for e in report.errors)


def test_validate_flags_outside_window():
    old = _record("OLD", dob=date(1950, 1, 1), marriage=date(1965, 1, 1))  # age 15
    report = validate_records([old])
    assert "OLD" in report.outside_window


def test_split_deterministic_and_disjoint():
    records = [_record(f"C{i}") for i in range(40)]
    train_a, test_a = split_records(records, seed=42)
    train_b, test_b = split_records(records, seed=42)
    assert [r.chart_id for r in train_a] == [r.chart_id for r in train_b]
    assert [r.chart_id for r in test_a] == [r.chart_id for r in test_b]
    ids = {r.chart_id for r in train_a} | {r.chart_id for r in test_a}
    assert ids == {r.chart_id for r in records}
    assert not ({r.chart_id for r in train_a} & {r.chart_id for r in test_a})


# ---------------------------------------------------------------- metrics

def test_perfect_predictions_score_100():
    preds = [{"predicted_year": 2000, "predicted_month": 5, "top3_years": [2000],
              "actual_year": 2000, "actual_month": 5, "score": 90.0} for _ in range(10)]
    s = summarize(preds)
    assert s["top1_year"] == 100.0
    assert s["top3_year"] == 100.0
    assert s["hit_within_12_months"] == 100.0
    assert s["mae_months"] == 0.0


def test_hit_window_math():
    # 11 months apart -> inside 12, outside 6
    assert hit_within(2020, 1, 2020, 12, 12) is True
    assert hit_within(2020, 1, 2020, 12, 6) is False
    assert month_error(2020, 1, 2020, 12) == 11
    assert top3_year([1999, 2000, 2001], 2000) is True
    assert top3_year([1999, 2000, 2001], 2005) is False


def test_bootstrap_ci_is_ordered():
    lo, hi = bootstrap_ci([1, 1, 0, 1, 0], reps=200, seed=7)
    assert 0.0 <= lo <= hi <= 1.0


def test_calibration_buckets():
    preds = [{"predicted_year": 2000, "predicted_month": 5, "top3_years": [2000],
              "actual_year": 2000, "actual_month": 5, "score": 80.0}]
    table = calibration_table(preds)
    hit_rows = [r for r in table if r["n"] > 0]
    assert len(hit_rows) == 1
    assert hit_rows[0]["top1_year"] == 100.0


# ---------------------------------------------------------------- baselines

def test_uniform_baseline_deterministic_and_bounded():
    records = [_record(f"B{i}", marriage=date(1990 + 20 + i, 6, 15)) for i in range(20)]
    a = uniform_random_baseline(records, 18, 45, simulations=100, seed=1)
    b = uniform_random_baseline(records, 18, 45, simulations=100, seed=1)
    assert a == b
    assert 0.0 <= a["top1_lo"] <= a["top1_hi"] <= 100.0
    expected = 100.0 / (45 - 18 + 1)  # one chance per year in window
    assert a["top1_year"] == pytest.approx(expected, abs=5.0)


def test_modal_baseline_learns_from_train():
    train = [_record(f"T{i}", marriage=date(2020, 6, 15)) for i in range(10)]  # dob 1990 -> age 30
    test = [_record("X1", dob=date(1980, 1, 1), marriage=date(2010, 6, 15))]
    out = modal_age_month_baseline(train, test, 18, 45)
    assert out["modal_age"] == 30
    assert out["modal_month"] == 6
    assert out["top1_year"] == 100.0  # 1980 + 30 = 2010


def test_permutation_test_detects_perfect_signal():
    preds = [2000, 2001, 2002, 2003, 2004]
    p_value, observed = permutation_test(preds, preds, reps=100, seed=3)
    assert observed == 100.0
    assert p_value < 0.05


def test_permutation_test_null_signal():
    preds = [2000, 2000, 2000, 2000]
    actuals = [1990, 1991, 1992, 1993]
    p_value, observed = permutation_test(preds, actuals, reps=200, seed=3)
    assert observed == 0.0
    assert p_value == 1.0


# ---------------------------------------------------------------- manifest

def test_manifest_verify_detects_changes(tmp_path):
    records = [_record("M1"), _record("M2")]
    manifest = build_manifest(PROTOCOL, SEED_DATASET, records, RULES_DIR)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)

    ok, diffs = verify_manifest(manifest_path, manifest)
    assert ok and diffs == []

    changed = dict(manifest)
    changed["dataset_sha256"] = "0" * 64
    ok, diffs = verify_manifest(manifest_path, changed)
    assert not ok
    assert any("dataset_sha256" in d for d in diffs)


def test_dataset_fingerprint_order_independent():
    a = [_record("A"), _record("B")]
    b = [_record("B"), _record("A")]
    assert dataset_fingerprint(a) == dataset_fingerprint(b)
    c = [_record("A"), _record("B", marriage=date(2019, 1, 1))]
    assert dataset_fingerprint(a) != dataset_fingerprint(c)


# ---------------------------------------------------------------- end to end

def test_run_evaluation_requires_freeze(tmp_path):
    from SweetAstro.src.evaluation.harness import run_evaluation
    with pytest.raises(RuntimeError, match="no frozen manifest"):
        run_evaluation(SEED_DATASET, manifest_path=tmp_path / "missing.json")


def test_run_evaluation_end_to_end(tmp_path):
    from SweetAstro.src.evaluation.harness import run_evaluation

    manifest_path = tmp_path / "manifest.json"
    result = run_evaluation(SEED_DATASET, manifest_path=manifest_path, allow_freeze=True)

    assert result.n_train + result.n_test == result.validation["n_primary"]
    assert result.n_test >= 1
    assert 0.0 <= result.engine_test["top1_year"] <= 100.0
    assert result.uniform_baseline["top1_hi"] >= result.uniform_baseline["top1_lo"]
    assert result.permutation["p_value"] >= 0.0
    assert result.runtime_seconds >= 0.0

    markdown = render_markdown(result)
    assert "Accuracy Backtest Report" in markdown
    assert "No accuracy claim is possible" in markdown  # 5-chart seed => <30 test charts
    assert "uniform" in markdown.lower()
