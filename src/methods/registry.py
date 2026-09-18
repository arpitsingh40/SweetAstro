"""
Method pack loading, matching and payload formatting.

See ``data/methods/README.md`` for the pack schema. Loading never raises on a
bad file: invalid packs are skipped and reported by ``pack_problems()`` so a
single malformed file cannot take down an answer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .reasons import canonical_reason_tags

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DIR = _PROJECT_ROOT / "data" / "methods"

REQUIRED_FIELDS = ("slug", "method", "source", "enabled", "topic_map")


def methods_dir() -> Path:
    override = os.environ.get("SWEETASTRO_METHODS_DIR")
    return Path(override) if override else DEFAULT_DIR


def quotes_enabled() -> bool:
    """Personal-mode switch: allow verbatim transcript quotes in answers."""
    value = os.environ.get("SWEETASTRO_METHOD_QUOTES", "").strip().lower()
    return value in ("1", "true", "yes", "on")


@dataclass
class MethodPack:
    slug: str
    method: str
    source: Dict[str, Any]
    enabled: bool
    topic_map: Dict[str, Dict[str, Any]]
    safety_rules: List[str] = field(default_factory=list)
    source_videos: List[Dict[str, Any]] = field(default_factory=list)
    allow_quotes: bool = False
    version: str = "1.0.0"

    @property
    def label(self) -> str:
        return str(self.source.get("label") or f"{self.method} (modern method)")

    @property
    def confidence(self) -> str:
        return str(self.source.get("confidence") or "modern")

    @property
    def research_note(self) -> str:
        return str(self.source.get("research_note") or "")


@dataclass
class MethodMatch:
    pack: MethodPack
    topic: str
    entry: Dict[str, Any]

    @property
    def label(self) -> str:
        return str(self.entry.get("label") or f"{self.pack.method}: {self.topic}")


def _load_pack(path: Path) -> Optional[MethodPack]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    missing = [key for key in REQUIRED_FIELDS if key not in data]
    if missing:
        return None
    source = data.get("source")
    topic_map = data.get("topic_map")
    if not isinstance(source, dict) or not isinstance(topic_map, dict):
        return None
    return MethodPack(
        slug=str(data.get("slug") or "").strip(),
        method=str(data.get("method") or "").strip(),
        source=source,
        enabled=bool(data.get("enabled", False)),
        topic_map={str(k).lower(): v for k, v in topic_map.items() if isinstance(v, dict)},
        safety_rules=[str(rule) for rule in (data.get("safety_rules") or [])],
        source_videos=[v for v in (data.get("source_videos") or []) if isinstance(v, dict)],
        allow_quotes=bool(data.get("allow_quotes", False)),
        version=str(data.get("version") or "1.0.0"),
    )


def load_method_packs(directory: Optional[Path] = None) -> List[MethodPack]:
    root = Path(directory) if directory else methods_dir()
    if not root.exists():
        return []
    packs: List[MethodPack] = []
    for path in sorted(root.glob("*.json")):
        pack = _load_pack(path)
        if pack is not None:
            packs.append(pack)
    return packs


def pack_problems(directory: Optional[Path] = None) -> List[str]:
    root = Path(directory) if directory else methods_dir()
    if not root.exists():
        return []
    problems: List[str] = []
    for path in sorted(root.glob("*.json")):
        pack = _load_pack(path)
        if pack is None:
            problems.append(f"{path.name}: unreadable or missing required fields "
                            f"({', '.join(REQUIRED_FIELDS)})")
            continue
        if not pack.slug:
            problems.append(f"{path.name}: empty slug")
        if pack.confidence.lower() != "modern":
            problems.append(f"{path.name}: confidence must be 'modern' "
                            f"(got {pack.confidence!r})")
        if not pack.safety_rules:
            problems.append(f"{path.name}: no safety_rules declared")
    return problems


def method_for_topic(topic: str, directory: Optional[Path] = None,
                     include_disabled: bool = False,
                     reason_tags: Optional[List[str]] = None) -> Optional[MethodMatch]:
    """Best pack for a topic, optionally matched to the exact unfavourable reason.

    Priority: a pack whose reason_tags overlap the engine's reason tags wins;
    an untagged topic-level pack is only a fallback when no tagged pack
    matched. When ``reason_tags`` are supplied, tagged entries that do not
    overlap are never returned.
    """
    wanted = (topic or "general").lower()
    wanted_tags = set(canonical_reason_tags(reason_tags or []))
    best_tagged: Optional[MethodMatch] = None
    best_score = 0
    topic_fallback: Optional[MethodMatch] = None
    for pack in load_method_packs(directory):
        if not pack.enabled and not include_disabled:
            continue
        entry = pack.topic_map.get(wanted)
        if entry is None:
            continue
        entry_tags = set(canonical_reason_tags(entry.get("reason_tags") or []))
        if entry_tags:
            if not wanted_tags:
                continue
            score = len(entry_tags & wanted_tags)
            if score > best_score:
                best_tagged = MethodMatch(pack=pack, topic=wanted, entry=entry)
                best_score = score
        elif topic_fallback is None:
            topic_fallback = MethodMatch(pack=pack, topic=wanted, entry=entry)
    return best_tagged or topic_fallback


def _source_line(match: MethodMatch) -> str:
    pack = match.pack
    parts: List[str] = []
    teacher = str(pack.source.get("teacher") or "").strip()
    channel = str(pack.source.get("channel") or "").strip()
    if teacher:
        parts.append(teacher)
    if channel:
        parts.append(channel)
    videos = ", ".join(
        str(video.get("id")) for video in pack.source_videos if video.get("id"))
    line = "Source: " + (", ".join(parts) if parts else pack.label)
    if videos:
        line += f" — video(s) {videos}"
    if pack.research_note:
        line += f" — note {pack.research_note}"
    return line


def format_method_lines(match: MethodMatch, allow_quotes: bool = False) -> List[str]:
    """Payload lines for a method-pack fallback block."""
    pack = match.pack
    entry = match.entry
    lines = [
        f"Modern method option (unvalidated — {match.label}):",
        f"- Status: modern method pack '{pack.slug}' v{pack.version}; "
        "not classical authority, not independently validated.",
        f"- {_source_line(match)}",
    ]
    guidance = entry.get("guidance") or entry.get("steps") or []
    if isinstance(guidance, str):
        guidance = [guidance]
    for step in guidance:
        lines.append(f"- {step}")
    formula = str(entry.get("formula") or "").strip()
    if formula:
        lines.append(f"- Server-computed basis: {formula}")
    remedies = entry.get("remedies") or []
    if isinstance(remedies, str):
        remedies = [remedies]
    for remedy in remedies:
        lines.append(f"- Remedy (modern, optional): {remedy}")
    entry_tags = canonical_reason_tags(entry.get("reason_tags") or [])
    if entry_tags:
        lines.append(f"- Addresses: {', '.join(entry_tags)}")
    if entry.get("adapted") and entry.get("note"):
        lines.append(f"- Mapping note: {entry['note']}")
    quotes_allowed = allow_quotes and pack.allow_quotes
    quote = str(entry.get("quote") or "").strip()
    if quotes_allowed and quote:
        locator = str(entry.get("locator") or "").strip()
        suffix = f" ({locator})" if locator else ""
        lines.append(f'- Transcript quote{suffix}: "{quote}"')
    for rule in pack.safety_rules:
        lines.append(f"- Rule: {rule}")
    lines.append(
        "- Present as an optional modern method — never as classical authority, "
        "a guarantee, or a prescription.")
    return lines
