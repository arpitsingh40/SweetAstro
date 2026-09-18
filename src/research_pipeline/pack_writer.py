"""
Method-pack skeleton writer (research side).

Turns an extracted candidate into a disabled method pack under
``data/methods/``. The pack starts ``"enabled": false`` and must pass
``method_packs`` review (evidence gate + tests + manual edit for the
server-side computation) before it can reach an answer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .extract import CandidateClaim
from .store import VideoRecord
from ..methods.reasons import canonical_reason_tags

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")


class PackWriterError(RuntimeError):
    """Raised when a pack skeleton cannot be written."""


DEFAULT_SAFETY_RULES = [
    "Unvalidated modern method derived from video research; never presented as classical authority.",
    "Optional, zero-cost, fallback-only: surfaced only when the engine cannot fully answer the question.",
    "No guarantee language; verify worked examples before enabling.",
]


def write_pack_skeleton(candidate: CandidateClaim, record: Optional[VideoRecord],
                        slug: str, topic: Optional[str] = None,
                        directory: Optional[Path] = None) -> Path:
    slug = (slug or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise PackWriterError(
            "slug must be 3-61 chars of lowercase letters, digits and hyphens")
    root = Path(directory) if directory else (
        Path(__file__).resolve().parent.parent.parent / "data" / "methods")
    path = root / f"{slug}.json"
    if path.exists():
        raise PackWriterError(f"{path.name} already exists; edit it instead")
    topic_key = (topic or candidate.target or "general").lower()
    entry = {
        "label": f"Modern method for {topic_key} (candidate {candidate.candidate_id})",
        "formula": candidate.formula or "describe the deterministic server computation here",
        "steps": list(candidate.steps) or ["describe step 1", "describe step 2"],
        "adapted": False,
        "note": "",
    }
    if candidate.remedies:
        entry["remedies"] = list(candidate.remedies)
    reason_tags = canonical_reason_tags(candidate.reason_tags)
    if reason_tags:
        entry["reason_tags"] = reason_tags
    if candidate.quote:
        entry["quote"] = candidate.quote
        entry["locator"] = candidate.locator
    pack = {
        "version": "0.1.0",
        "slug": slug,
        "method": candidate.claim[:120],
        "source": {
            "teacher": record.channel if record else "",
            "channel": record.channel if record else "",
            "basis": "YouTube video research (evidence gate: see candidate report)",
            "confidence": "modern",
            "research_note": f"docs/research/video_method_pipeline.md#candidate-{candidate.candidate_id}",
            "label": f"{candidate.claim[:60]} (modern — {record.channel if record else 'video research'})",
        },
        "enabled": False,
        "allow_quotes": False,
        "evidence": {
            "candidate_id": candidate.candidate_id,
            "video_id": candidate.video_id,
            "locator": candidate.locator,
            "passes": candidate.passes,
            "extractor_confidence": candidate.confidence,
        },
        "source_videos": [{
            "id": candidate.video_id,
            "title": record.title if record else "",
            "locator": candidate.locator,
        }],
        "safety_rules": DEFAULT_SAFETY_RULES,
        "topic_map": {topic_key: entry},
    }
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
