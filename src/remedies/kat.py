"""
Karma Alignment Technique (KAT) — labelled modern alignment module.

Encodes only the publicly taught domain-triangle framework of Rahul Kaushik's
Karma Alignment Technique (based on Bhrigu Nandi Nadi): diagnose the life
domain, then work with that triangle's planets through nature-aligned conduct
rather than attempting to strengthen all nine planets.

This is a modern, unvalidated interpretive method: it is offered as an optional,
zero-cost alignment option, always labelled, and never as a guarantee. The
per-planet conduct suggestions come from SweetAstro's existing alignment
library; KAT supplies the domain framing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .catalog import PLANET_ALIGNMENT

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rules" / "remedies_kat.json"

SOURCE_LABEL = "KAT (modern method — Rahul Kaushik; based on Bhrigu Nandi Nadi)"


@dataclass
class KatAlignment:
    triangle: str
    label: str
    houses: List[int]
    planets: List[str]
    focus_note: str
    actions: List[str]
    adapted: bool = False
    adapted_note: str = ""
    source_label: str = SOURCE_LABEL
    confidence: str = "modern"

    def to_dict(self) -> Dict:
        return {
            "triangle": self.triangle,
            "label": self.label,
            "houses": self.houses,
            "planets": self.planets,
            "focus_note": self.focus_note,
            "actions": self.actions,
            "adapted": self.adapted,
            "adapted_note": self.adapted_note,
            "source_label": self.source_label,
            "confidence": self.confidence,
        }


def load_kat_rules(path: Optional[Path] = None) -> Dict:
    return json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))


def kat_alignment_for_topic(topic: str, obstructing_planet: Optional[str] = None,
                            rules: Optional[Dict] = None) -> Optional[KatAlignment]:
    """Returns the labelled KAT alignment option for a topic, or None if unmapped."""
    rules = rules or load_kat_rules()
    entry = rules.get("topic_map", {}).get((topic or "").lower())
    if not entry:
        return None
    triangle_key = entry["triangle"]
    triangle = rules["triangles"].get(triangle_key)
    if not triangle:
        return None

    focus_note = triangle["focus_note"]
    if obstructing_planet and obstructing_planet in triangle["planets"]:
        focus_note += (f" The blocked thread here appears to be {obstructing_planet} — "
                       "include it in the alignment instead of dismissing it.")

    actions = [
        f"{planet}: {PLANET_ALIGNMENT.get(planet, 'balanced conduct')}"
        for planet in triangle["planets"]
    ]

    return KatAlignment(
        triangle=triangle_key,
        label=triangle["label"],
        houses=list(triangle["houses"]),
        planets=list(triangle["planets"]),
        focus_note=focus_note,
        actions=actions,
        adapted=bool(entry.get("adapted")),
        adapted_note=entry.get("note", ""),
    )


def format_kat_line(kat: KatAlignment) -> str:
    """Short user-visible line for the Recommended Alignment section."""
    planets = ", ".join(kat.planets)
    adapted = " (SweetAstro topic adaptation)" if kat.adapted else ""
    return (f"Domain alignment — {kat.label}{adapted} [{kat.source_label}]: focus on {planets} "
            "through daily conduct, not all nine planets. Optional, non-guaranteeing.")
