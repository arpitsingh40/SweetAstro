"""
Outcome feedback log.

Users can report what actually happened ("it happened in March 2027",
"nothing happened"). These reports are appended to a JSONL file so the
engine's calibration can eventually be reviewed against reality — the only
honest path to demonstrated accuracy.

Storage only; nothing here changes a reading or claims accuracy.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sweetastro.chat")

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "outcomes" / "outcomes.jsonl"


def outcomes_path() -> Path:
    override = os.environ.get("SWEETASTRO_OUTCOMES_PATH")
    return Path(override) if override else DEFAULT_PATH


def record_outcome(session_id: str, outcome: Dict[str, Any]) -> bool:
    record = {"recorded_at": time.time(), "session_id": session_id, **outcome}
    path = outcomes_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError as exc:
        logger.warning("Could not record outcome for session %s: %s", session_id, exc)
        return False


def load_outcomes(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target = path or outcomes_path()
    if not target.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
