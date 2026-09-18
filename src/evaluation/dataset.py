"""
Dataset loading, validation, and deterministic splitting for accuracy evaluation.

Supports the existing JSON format (data/test_charts/historical_verified.json)
and a CSV template (data/test_charts/dataset_template.csv).
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VALID_RODDEN = {"AA", "A", "B", "C", "DD", "X", "XX"}
_REQUIRED_CSV = ["chart_id", "rodden", "dob", "tob", "tz_offset", "lat", "lon", "marriage_date"]


@dataclass
class ChartRecord:
    chart_id: str
    rodden: str
    dob: date
    tob: str
    tz_offset: float
    lat: float
    lon: float
    marriage_date: date
    name: str = ""
    marriage_type: str = "first"
    source: str = ""

    @property
    def birth_datetime(self) -> datetime:
        h, m, s = (int(float(p)) for p in self.tob.split(":"))
        return datetime(self.dob.year, self.dob.month, self.dob.day, h, m, s)

    @property
    def marriage_age_years(self) -> float:
        return (self.marriage_date - self.dob).days / 365.25

    @property
    def included_primary(self) -> bool:
        return self.rodden in ("AA", "A")


@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)
    n_records: int = 0
    n_primary: int = 0
    rodden_counts: Dict[str, int] = field(default_factory=dict)
    outside_window: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date(value: Any, field_name: str, errors: List[str]) -> Optional[date]:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    errors.append(f"{field_name}: invalid date '{value}'")
    return None


def _record_from_dict(row: Dict[str, Any], errors: List[str], idx: int) -> Optional[ChartRecord]:
    label = row.get("chart_id") or f"row-{idx}"

    dob = _parse_date(row.get("dob"), f"{label}/dob", errors)
    marriage_date = _parse_date(row.get("marriage_date"), f"{label}/marriage_date", errors)

    try:
        tob = str(row["tob"]).strip()
        parts = [int(float(p)) for p in tob.split(":")]
        while len(parts) < 3:
            parts.append(0)
        assert 0 <= parts[0] <= 23 and 0 <= parts[1] <= 59 and 0 <= parts[2] <= 59
        tob = f"{parts[0]:02d}:{parts[1]:02d}:{parts[2]:02d}"
    except (KeyError, ValueError, AssertionError):
        errors.append(f"{label}/tob: invalid time '{row.get('tob')}'")
        tob = ""

    try:
        tz = float(row["tz_offset"])
        if not -12.0 <= tz <= 14.0:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        errors.append(f"{label}/tz_offset: invalid '{row.get('tz_offset')}'")
        tz = 0.0

    def _coord(key: str, low: float, high: float) -> float:
        try:
            val = float(row[key])
            if not low <= val <= high:
                raise ValueError
            return val
        except (KeyError, ValueError, TypeError):
            errors.append(f"{label}/{key}: invalid '{row.get(key)}'")
            return 0.0

    lat = _coord("lat", -90.0, 90.0)
    lon = _coord("lon", -180.0, 180.0)

    rodden = str(row.get("rodden") or row.get("rodden_rating") or "").strip().upper()
    if rodden not in VALID_RODDEN:
        errors.append(f"{label}/rodden: invalid or missing '{rodden}'")

    if errors and (dob is None or marriage_date is None or not tob):
        return None
    if dob is None or marriage_date is None:
        return None

    if marriage_date <= dob:
        errors.append(f"{label}: marriage_date {marriage_date} not after dob {dob}")
        return None

    return ChartRecord(
        chart_id=str(row.get("chart_id") or label),
        rodden=rodden,
        dob=dob,
        tob=tob,
        tz_offset=tz,
        lat=lat,
        lon=lon,
        marriage_date=marriage_date,
        name=str(row.get("name", "")),
        marriage_type=str(row.get("marriage_type", "first")),
        source=str(row.get("source", "")),
    )


def load_dataset(path: Path) -> List[ChartRecord]:
    path = Path(path)
    errors: List[str] = []
    if path.suffix.lower() == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in _REQUIRED_CSV if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"CSV missing required columns: {missing}")
            rows = list(reader)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Dataset JSON must be a list of records.")
        rows = data

    records: List[ChartRecord] = []
    for idx, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"row-{idx}: not an object")
            continue
        record = _record_from_dict(row, errors, idx)
        if record is not None:
            records.append(record)
    if errors:
        raise ValueError("Dataset validation failed:\n  " + "\n  ".join(errors))
    return records


def validate_records(records: List[ChartRecord], min_age: int = 18, max_age: int = 45) -> ValidationReport:
    report = ValidationReport(n_records=len(records))
    seen_ids: Dict[str, int] = {}
    seen_births: Dict[Tuple, str] = {}
    for rec in records:
        seen_ids[rec.chart_id] = seen_ids.get(rec.chart_id, 0) + 1
        key = (rec.dob, rec.tob, round(rec.lat, 4), round(rec.lon, 4))
        if key in seen_births and seen_births[key] != rec.chart_id:
            report.duplicates.append(f"{seen_births[key]} == {rec.chart_id} (same birth data)")
        seen_births.setdefault(key, rec.chart_id)
        report.rodden_counts[rec.rodden] = report.rodden_counts.get(rec.rodden, 0) + 1
        if rec.included_primary:
            report.n_primary += 1
        if not (min_age <= rec.marriage_age_years <= max_age):
            report.outside_window.append(rec.chart_id)

    for chart_id, count in seen_ids.items():
        if count > 1:
            report.errors.append(f"duplicate chart_id: {chart_id} ({count}x)")
    if report.n_records == 0:
        report.errors.append("dataset is empty")
    if report.n_primary == 0:
        report.warnings.append("no Rodden AA/A records — primary analysis will be empty")
    if report.outside_window:
        report.warnings.append(
            f"{len(report.outside_window)} record(s) marry outside the {min_age}-{max_age} search window "
            "(automatic misses; reported for coverage)"
        )
    return report


def split_records(records: List[ChartRecord], seed: int, train_pct: int = 70) -> Tuple[List[ChartRecord], List[ChartRecord]]:
    """Deterministic hash-ranked split: stable across runs and machines.

    Records are ranked by sha256(chart_id + seed); the first
    round(n * train_pct / 100) go to train and the rest to test. For n > 1 at
    least one record lands in each side, so small datasets never produce an
    empty evaluation split.
    """
    ranked = sorted(records, key=lambda r: hashlib.sha256(f"{seed}:{r.chart_id}".encode("utf-8")).hexdigest())
    n = len(ranked)
    if n == 0:
        return [], []
    if n == 1:
        return [], ranked
    n_train = int(round(n * train_pct / 100.0))
    n_train = min(max(n_train, 1), n - 1)
    return ranked[:n_train], ranked[n_train:]
