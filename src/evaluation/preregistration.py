"""
Pre-registration manifest: freeze protocol + dataset + rules before scoring.

The manifest is written once (`--freeze`). Later runs recompute the hashes and
refuse to score if anything changed — this prevents post-hoc tuning.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from .dataset import ChartRecord

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "accuracy_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_fingerprint(records: List[ChartRecord]) -> str:
    """Canonical fingerprint of the evaluation data (order-independent)."""
    canonical = sorted(
        (r.chart_id, r.rodden, r.dob.isoformat(), r.tob, r.tz_offset,
         round(r.lat, 6), round(r.lon, 6), r.marriage_date.isoformat())
        for r in records
    )
    payload = json.dumps(canonical, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def rules_fingerprint(rules_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(rules_dir).glob("*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(sha256_file(path).encode("utf-8"))
    return digest.hexdigest()


def build_manifest(protocol: Dict, dataset_path: Path, records: List[ChartRecord],
                   rules_dir: Path) -> Dict:
    return {
        "protocol_version": protocol["protocol_version"],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_path": str(Path(dataset_path).resolve()),
        "dataset_sha256": dataset_fingerprint(records),
        "rules_sha256": rules_fingerprint(rules_dir),
        "search_window": protocol["search_window"],
        "split": protocol["split"],
        "primary_endpoint": protocol["primary_endpoint"],
        "included_rodden": protocol["included_rodden"],
    }


def write_manifest(path: Path, manifest: Dict) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def verify_manifest(path: Path, current: Dict) -> Tuple[bool, List[str]]:
    """Returns (ok, differences). `ok` is False when the frozen state changed."""
    if not Path(path).exists():
        return (False, ["no frozen manifest exists — run with --freeze first"])
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    diffs: List[str] = []
    for key in ("protocol_version", "dataset_sha256", "rules_sha256",
                "search_window", "split", "primary_endpoint", "included_rodden"):
        if frozen.get(key) != current.get(key):
            diffs.append(f"{key}: frozen={frozen.get(key)!r} current={current.get(key)!r}")
    return (not diffs, diffs)
