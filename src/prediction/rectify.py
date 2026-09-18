"""
Birth-time rectification assist — deterministic candidate-time ranking.

Given a birth date, an approximate time (or none) and 2-6 dated life events,
score each candidate birth time (10-minute grid) by whether the Vimshottari
Mahadasha/Antardasha lords active at the event dates signify the event topic's
houses and significators. The output is a *ranking assist* — the times that
best fit the events the user gave — never a verified birth time, and never an
accuracy claim (see docs/accuracy_protocol.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..consumer import TOPIC_HOUSES, TOPIC_SIGNIFICATORS
from ..core.chart import calculate_d1_chart
from ..core.dasha import calculate_vimshottari_timeline, get_dasha_at_date

STEP_MINUTES = 10
MIN_EVENTS = 2
MAX_EVENTS = 6
TOP_CANDIDATES = 8


@dataclass
class CandidateScore:
    time: str          # "HH:MM"
    score: float
    events_matched: int

    def to_dict(self) -> Dict[str, Any]:
        return {"time": self.time, "score": self.score, "events_matched": self.events_matched}


@dataclass
class RectificationResult:
    candidates: List[CandidateScore]
    best_windows: List[Tuple[str, str]]
    event_count: int
    topic: str
    method_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ranked": [c.to_dict() for c in self.candidates[:TOP_CANDIDATES]],
            "best_windows": [{"start": start, "end": end} for start, end in self.best_windows],
            "event_count": self.event_count,
            "topic": self.topic,
            "method_note": self.method_note,
        }


def _event_datetime(date_str: str) -> Optional[datetime]:
    parts = (date_str or "").strip().split("-")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    year, month = int(parts[0]), int(parts[1])
    day = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 15
    if not (1800 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 28):
        return None
    return datetime(year, month, day)


def dasha_relevance(lord: str, d1, topic_houses: List[int],
                    relevant_lords: set, significators: set) -> float:
    """How strongly a dasha lord signifies the topic for this chart (0 if unrelated)."""
    score = 0.0
    if lord in relevant_lords:
        score += 1.0
    if lord in significators:
        score += 0.5
    planet = d1.planets.get(lord)
    if planet is not None and planet.house in topic_houses:
        score += 0.5
    return score


def _topic_context(d1, topic: str) -> Tuple[List[int], set, set]:
    houses = TOPIC_HOUSES.get(topic, TOPIC_HOUSES["general"])
    relevant_lords = {d1.houses[h].lord for h in houses if h in d1.houses}
    significators = set(TOPIC_SIGNIFICATORS.get(topic, []))
    return houses, relevant_lords, significators


def rectify_birth_time(
    *,
    year: int,
    month: int,
    day: int,
    tz_offset: float,
    lat: float,
    lon: float,
    events: List[Dict[str, Any]],
    topic: str = "general",
    step_minutes: int = STEP_MINUTES,
) -> RectificationResult:
    """Ranks candidate birth times against dated events. Raises ValueError with <2 valid events."""
    dated: List[Tuple[str, datetime]] = []
    for event in events or []:
        label = str((event or {}).get("event") or "event")[:120]
        when = _event_datetime(str((event or {}).get("date") or ""))
        if when is not None:
            dated.append((label, when))
    dated = dated[:MAX_EVENTS]
    if len(dated) < MIN_EVENTS:
        raise ValueError(f"At least {MIN_EVENTS} dated events are required for rectification assistance.")

    candidates: List[CandidateScore] = []
    for minute_of_day in range(0, 24 * 60, step_minutes):
        hour, minute = divmod(minute_of_day, 60)
        d1 = calculate_d1_chart(year, month, day, hour, minute, 0, tz_offset, lat, lon)
        timeline = calculate_vimshottari_timeline(
            datetime(year, month, day, hour, minute), d1.planets["Moon"].longitude)
        topic_houses, relevant_lords, significators = _topic_context(d1, topic)
        total = 0.0
        matched = 0
        for _, event_dt in dated:
            state = get_dasha_at_date(timeline, event_dt)
            if state is None:
                continue
            event_score = (
                dasha_relevance(state.mahadasha, d1, topic_houses, relevant_lords, significators)
                + dasha_relevance(state.antardasha, d1, topic_houses, relevant_lords, significators)
            )
            if event_score > 0:
                matched += 1
            total += event_score
        candidates.append(CandidateScore(f"{hour:02d}:{minute:02d}", round(total, 2), matched))

    best_score = max(candidate.score for candidate in candidates)
    best_matched = max(candidate.events_matched for candidate in candidates)
    top_indices = [
        index for index, candidate in enumerate(candidates)
        if candidate.events_matched == best_matched and candidate.score >= best_score - 0.5
    ]
    windows: List[Tuple[str, str]] = []
    previous = -2
    for index in top_indices:
        if index == previous + 1:
            windows[-1] = (windows[-1][0], candidates[index].time)
        else:
            windows.append((candidates[index].time, candidates[index].time))
        previous = index

    candidates = sorted(candidates, key=lambda c: (-c.events_matched, -c.score, c.time))
    return RectificationResult(
        candidates=candidates,
        best_windows=windows,
        event_count=len(dated),
        topic=topic,
        method_note=(
            "Candidate birth times were scored by whether the Vimshottari Mahadasha and "
            "Antardasha lords active at each event date signify the event topic's houses, "
            "house-lords and significators on the candidate chart. The best-fit windows are "
            "the times that fit the events the user gave — an assist, not a verified birth time."
        ),
    )
