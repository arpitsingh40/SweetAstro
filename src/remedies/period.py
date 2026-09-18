"""
Period alignment — direction for the running Vimshottari periods.

Deterministic, engine-owned modern conduct guidance: the running Mahadasha
(life chapter), Antardasha (active channel) and Pratyantardasha (immediate
window) lords each carry a conduct focus; the promise assessment's limiting
planet is included as the obstructing thread; the next Antardasha boundary
gives a preparation note.

This is a labelled modern method (SweetAstro adaptation of the KAT/BNN
alignment principle): optional, zero-cost, non-guaranteeing, and never
presented as classical authority. It does not affect the classical
provenance ledger or the promise gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .catalog import PLANET_ALIGNMENT, PLANET_WEEKDAY

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rules" / "period_alignment.json"

SOURCE_LABEL = ("Period alignment (modern — SweetAstro adaptation of the "
                "KAT/BNN conduct principle)")

_PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")
_LEVEL_LABEL = {
    "MD": "Mahadasha (life chapter)",
    "AD": "Antardasha (active channel)",
    "PD": "Pratyantardasha (immediate window)",
}


@dataclass
class PeriodAlignment:
    planets: Dict[str, str] = field(default_factory=dict)
    lines: List[str] = field(default_factory=list)
    obstructing: str = ""
    next_note: str = ""
    time_unreliable: bool = False
    source_label: str = SOURCE_LABEL
    confidence: str = "modern"


def load_period_rules(path: Optional[Path] = None) -> Dict[str, Any]:
    return json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))


def _split_periods(current_md_ad_pd: str) -> Optional[Tuple[str, str, str]]:
    parts = [part.strip() for part in (current_md_ad_pd or "").split("/")]
    if len(parts) != 3:
        return None
    if not all(part in _PLANETS for part in parts):
        return None
    return parts[0], parts[1], parts[2]


def _first_clause(text: str, max_words: int = 9) -> str:
    clause = text.split(";")[0].split(",")[0].strip()
    words = clause.split()
    if len(words) > max_words:
        clause = " ".join(words[:max_words])
    return clause


def _obstructing_planet(promise: Any) -> str:
    if promise is None:
        return ""
    factors = getattr(promise, "limiting_factors", None) or []
    for factor in factors:
        text = str(factor)
        for planet in _PLANETS:
            if planet.lower() in text.lower():
                return planet
    return ""


def _next_ad_note(upcoming: Optional[Sequence[Any]]) -> str:
    for period in upcoming or []:
        level = str(getattr(period, "level", "") or "")
        if level != "AD":
            continue
        lord = str(getattr(period, "lord", "") or "")
        start = getattr(period, "start_date", None)
        if isinstance(start, datetime):
            return f"Next shift: enters {lord} Antardasha on {start:%Y-%m-%d} — start its conduct early."
        if lord:
            return f"Next shift: enters {lord} Antardasha — start its conduct early."
    return ""


def period_alignment(current_md_ad_pd: str, *, rules: Optional[Dict[str, Any]] = None,
                     promise: Any = None,
                     upcoming: Optional[Sequence[Any]] = None,
                     time_reliable: bool = True) -> Optional[PeriodAlignment]:
    """Direction for the running periods, or None when periods are unresolved."""
    periods = _split_periods(current_md_ad_pd)
    if periods is None:
        return None
    rules = rules or load_period_rules()
    planet_rules = rules.get("planets") or {}
    md, ad, pd = periods

    alignment = PeriodAlignment(planets={"MD": md, "AD": ad, "PD": pd})
    alignment.obstructing = _obstructing_planet(promise)
    alignment.next_note = _next_ad_note(upcoming)
    alignment.time_unreliable = not time_reliable

    lines = [f"Period alignment (modern method — {SOURCE_LABEL}; optional, no guarantees):"]
    if not time_reliable:
        lines.append("- Birth-time certainty is reduced: period boundaries carry lower confidence.")
    for level, planet in (("MD", md), ("AD", ad), ("PD", pd)):
        entry = planet_rules.get(planet) or {}
        focus = str(entry.get("focus") or PLANET_ALIGNMENT.get(planet, "balanced conduct"))
        avoid = str(entry.get("avoid") or "").strip()
        domains = str(entry.get("domains") or "").strip()
        if level == "PD":
            lines.append(f"- {_LEVEL_LABEL[level]} — {planet}: keep the daily habit of "
                         f"{_first_clause(focus, 7)}.")
            continue
        detail = focus
        if domains:
            detail += f" (domains: {domains})"
        lines.append(f"- {_LEVEL_LABEL[level]} — {planet}: {detail}.")
        if avoid:
            lines.append(f"  Avoid: {avoid}.")
    if alignment.obstructing:
        lines.append(f"- Obstructing thread: {alignment.obstructing} — include it in the alignment "
                     "instead of dismissing it (work the blocking planet, not all nine).")
    weekday_md = PLANET_WEEKDAY.get(md, "")
    weekday_ad = PLANET_WEEKDAY.get(ad, "")
    weekday_pd = PLANET_WEEKDAY.get(pd, "")
    anchors = ", ".join(part for part in (
        f"{md} day {weekday_md}" if weekday_md else "",
        f"{ad} day {weekday_ad}" if weekday_ad and ad != md else "",
        f"{pd} day {weekday_pd}" if weekday_pd and pd not in (md, ad) else "",
    ) if part)
    if anchors:
        lines.append(f"- Weekday anchors (optional): {anchors} — service/mantra on those days if you keep such practice.")
    if alignment.next_note:
        lines.append(f"- {alignment.next_note}")
    lines.append("- Present as optional conduct guidance; never as classical authority, a guarantee, or a prescription.")
    alignment.lines = lines
    return alignment


def period_alignment_lines(current_md_ad_pd: str, **kwargs) -> List[str]:
    alignment = period_alignment(current_md_ad_pd, **kwargs)
    return alignment.lines if alignment else []


def format_period_line(alignment: PeriodAlignment) -> str:
    """Short user-visible line for the consumer's alignment section."""
    md = alignment.planets.get("MD", "—")
    ad = alignment.planets.get("AD", "—")
    pd = alignment.planets.get("PD", "—")
    note = f" Obstructing thread: {alignment.obstructing}." if alignment.obstructing else ""
    return (f"Period alignment [{SOURCE_LABEL}]: current {md} MD / {ad} AD / {pd} PD — "
            "keep daily conduct aligned with the period lord's nature "
            "(see the answer's period block)." + note + " Optional; no guarantees.")
