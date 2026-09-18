"""
Reason-tag vocabulary shared by the engine and the video research pipeline.

The promise assessment emits human-readable limiting factors ("Venus (lord of
H7) is Debilitated in H6"). Video research tags are free-form snake_case
("venus debilitated", "saturn occupies 7th house"). Both are canonicalised
into the same small tag set so a method pack can be matched to the exact
reason an event-reading is unfavourable.

This module is answer-path safe: it imports nothing from the research
pipeline.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Set

_PLANETS = {"sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"}
_MALEFICS = {"saturn", "mars", "rahu", "ketu", "sun"}
_CONDITIONS = {"debilitated", "combust", "enemy", "occupies", "aspects", "afflicted", "weak"}
_LORDSHIP_WORDS = {"lord", "lordship", "owner", "significator"}
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _parse(reason: str) -> Set[str]:
    tokens = [token for token in _TOKEN_SPLIT.split((reason or "").lower()) if token]
    if not tokens:
        return set()
    planets = [token for token in tokens if token in _PLANETS]
    houses: Set[int] = set()
    for index, token in enumerate(tokens):
        if token in ("h", "house") and index + 1 < len(tokens) and tokens[index + 1].isdigit():
            houses.add(int(tokens[index + 1]))
        elif token.startswith("h") and token[1:].isdigit():
            houses.add(int(token[1:]))
        elif token[:-2].isdigit() and token.endswith(("st", "nd", "rd", "th")):
            houses.add(int(token[:-2]))
        elif (token.isdigit() and 1 <= int(token) <= 12
              and ("house" in tokens or "bhava" in tokens)):
            houses.add(int(token))
    conditions = {token for token in tokens if token in _CONDITIONS}

    tags: Set[str] = set()
    for planet in planets:
        tags.add(planet)
        for condition in conditions:
            tags.add(f"{planet}_{condition}")
        for house in houses:
            tags.add(f"{planet}_house_{house}")
    for house in houses:
        if conditions & {"occupies", "afflicted"} or "in" in tokens:
            if any(planet in _MALEFICS for planet in planets) or not planets:
                tags.add(f"malefic_house_{house}")
    if any(token in _LORDSHIP_WORDS for token in tokens):
        for planet in planets:
            for house in houses:
                tags.add(f"{planet}_lord_{house}")
    if "upapada" in tokens or "ul" in tokens:
        if "outside" in tokens or "afflicted" in tokens or "weak" in tokens:
            tags.add("ul_afflicted")
    if not planets and not houses:
        for condition in conditions:
            tags.add(condition)
    antardasha = "antardasha" in tokens
    pratyantardasha = "pratyantardasha" in tokens
    mahadasha = "mahadasha" in tokens or (
        "dasha" in tokens and not antardasha and not pratyantardasha)
    for planet in planets:
        if mahadasha:
            tags.add(f"dasha_lord_{planet}")
        if antardasha:
            tags.add(f"antardasha_{planet}")
        if pratyantardasha:
            tags.add(f"pratyantardasha_{planet}")
    return tags


def dasha_reason_tags(md: str = "", ad: str = "", pd: str = "") -> List[str]:
    """Canonical tags for the engine's running period lords."""
    tags: List[str] = []
    if md:
        tags.append(f"dasha_lord_{md.lower()}")
    if ad:
        tags.append(f"antardasha_{ad.lower()}")
    if pd:
        tags.append(f"pratyantardasha_{pd.lower()}")
    return tags


def canonical_reason_tags(reasons: Iterable[str]) -> List[str]:
    """Canonical tag set for engine factor strings or free-form video tags."""
    tags: Set[str] = set()
    for reason in reasons:
        tags |= _parse(str(reason))
    return sorted(tags)


def reason_overlap(left: Sequence[str], right: Sequence[str]) -> int:
    return len(set(canonical_reason_tags(left)) & set(canonical_reason_tags(right)))


def promise_reason_tags(promise) -> List[str]:
    """Reason tags when the promise assessment is unfavourable, else empty.

    Weak and Partial commitments are where an event answer is not in the
    native's favour; the limiting factors name the exact reasons.
    """
    level = str(getattr(promise, "level", "") or "").strip()
    if level not in ("Weak", "Partial"):
        return []
    tags = canonical_reason_tags(getattr(promise, "limiting_factors", []) or [])
    return tags or [f"{level.lower()}_promise"]
