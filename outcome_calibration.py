"""
Outcome calibration report runner.

Reads user-reported outcomes (data/outcomes/outcomes.jsonl), aggregates them
by verdict and topic, and writes a transparent review report to reports/.

Reporting only — no weight changes, no accuracy claim. A public accuracy
statement requires a pre-registered run on >=500 verified records
(docs/accuracy_protocol.md).

Usage:
    python outcome_calibration.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from SweetAstro.src.chat.outcomes import load_outcomes
from SweetAstro.src.evaluation.outcome_calibration import (
    build_calibration_report, render_calibration_report,
)

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def main() -> int:
    records = load_outcomes()
    report = build_calibration_report(records)
    markdown = render_calibration_report(report)

    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (REPORTS_DIR / f"outcome_calibration_{stamp}.md").write_text(markdown, encoding="utf-8")
    (REPORTS_DIR / f"outcome_calibration_{stamp}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Outcome records: {report['total']}")
    print(report["readiness"]["note"])
    print(f"Report: reports/outcome_calibration_{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
