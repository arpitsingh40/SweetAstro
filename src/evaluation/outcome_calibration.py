"""
Outcome calibration review.

Aggregates user-reported outcomes (data/outcomes/outcomes.jsonl) into a
transparent, read-only report: verdict counts, per-topic rates, and the
prediction snapshot captured with each report (dasha at report time,
current period, stated confidence).

This is reporting only. It never re-tunes weights and never supports an
accuracy claim: docs/accuracy_protocol.md requires a pre-registered run on
>=500 verified records before any public statement.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .interpretation_quality import outcome_dataset_ready

VERDICTS = ("happened", "did_not_happen", "partial")


def _topic_of(record: Dict[str, Any]) -> str:
    prediction = record.get("prediction") or {}
    return str(prediction.get("topic") or record.get("topic") or "unspecified")


@dataclass
class TopicCalibration:
    topic: str
    total: int = 0
    counts: Dict[str, int] = field(default_factory=lambda: {v: 0 for v in VERDICTS})

    @property
    def happened_rate(self) -> float:
        return round(self.counts["happened"] / self.total, 3) if self.total else 0.0


def build_calibration_report(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregates outcome records by verdict and topic (deterministic)."""
    overall = {v: 0 for v in VERDICTS}
    topics: Dict[str, TopicCalibration] = {}
    dated: List[Dict[str, Any]] = []

    for record in records:
        verdict = str(record.get("verdict", ""))
        if verdict not in VERDICTS:
            continue
        overall[verdict] += 1
        topic = _topic_of(record)
        bucket = topics.setdefault(topic, TopicCalibration(topic=topic))
        bucket.total += 1
        bucket.counts[verdict] += 1
        if record.get("date"):
            dated.append({
                "event": record.get("event", "unspecified event"),
                "date": record.get("date"),
                "verdict": verdict,
                "topic": topic,
            })

    total = sum(overall.values())
    readiness = outcome_dataset_ready(records)
    return {
        "total": total,
        "overall": overall,
        "happened_rate": round(overall["happened"] / total, 3) if total else None,
        "topics": [
            {
                "topic": bucket.topic,
                "total": bucket.total,
                "counts": bucket.counts,
                "happened_rate": bucket.happened_rate,
            }
            for bucket in sorted(topics.values(), key=lambda b: (-b.total, b.topic))
        ],
        "dated": sorted(dated, key=lambda item: str(item["date"])),
        "readiness": readiness,
    }


def render_calibration_report(report: Dict[str, Any]) -> str:
    lines = ["# Outcome calibration review", ""]
    lines.append(f"- Records: **{report['total']}**")
    rate = report.get("happened_rate")
    lines.append(f"- Happened rate: **{rate if rate is not None else 'n/a'}**")
    lines.append(f"- Dataset readiness: {report['readiness']['note']}")
    lines.append("")
    if report["topics"]:
        lines.append("## By topic")
        lines.append("")
        lines.append("| Topic | Records | Happened | Partial | Did not | Rate |")
        lines.append("|---|---|---|---|---|---|")
        for item in report["topics"]:
            counts = item["counts"]
            lines.append(
                f"| {item['topic']} | {item['total']} | {counts['happened']} | "
                f"{counts['partial']} | {counts['did_not_happen']} | {item['happened_rate']} |"
            )
        lines.append("")
    if report["dated"]:
        lines.append("## Dated reports")
        lines.append("")
        for item in report["dated"]:
            lines.append(f"- {item['date']}: {item['event']} — {item['verdict']} ({item['topic']})")
        lines.append("")
    lines.append("_Reporting only. No accuracy claim is valid without a pre-registered "
                 "evaluation on >=500 verified records (docs/accuracy_protocol.md)._")
    return "\n".join(lines)
