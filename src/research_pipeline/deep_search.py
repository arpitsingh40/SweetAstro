"""
Deep search — targeted YouTube research for an exact unfavourable reason.

Given a topic and the engine's exact limiting reason (from the promise
assessment, e.g. "Venus (lord of H7) is Debilitated in H6"), this runs:

    search -> ingest -> dual-pass extract -> evidence gate -> report

Remedy and cause candidates whose reason tags overlap the engine's tags are
ranked first. Output feeds the normal curation path: quarantine drafts and
disabled method packs; nothing here reaches an answer directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .extract import CandidateClaim, dual_pass_extract, load_candidates, save_candidates
from .fetch import Searcher, Extractor, fetch_videos, search_videos
from .gate import GateResult, evaluate_candidates
from .store import VideoStore
from ..methods.reasons import canonical_reason_tags


@dataclass
class DeepSearchOutcome:
    topic: str
    reason: str
    query: str
    reason_tags: List[str]
    videos: List[Tuple[str, str, str]] = field(default_factory=list)
    fetch_messages: List[str] = field(default_factory=list)
    candidates: List[CandidateClaim] = field(default_factory=list)
    results: List[GateResult] = field(default_factory=list)

    @property
    def matched_remedies(self) -> List[GateResult]:
        wanted = set(self.reason_tags)
        matched: List[GateResult] = []
        for result in self.results:
            if result.candidate.kind not in ("remedy", "cause"):
                continue
            tags = set(canonical_reason_tags(result.candidate.reason_tags))
            if tags & wanted:
                matched.append(result)
        return matched

    def summary_lines(self) -> List[str]:
        lines = [
            f"Deep search: topic={self.topic!r} reason={self.reason!r}",
            f"Query: {self.query}",
            f"Reason tags: {', '.join(self.reason_tags) or '(none)'}",
            f"Videos found: {len(self.videos)}",
        ]
        for video_id, title, channel in self.videos:
            lines.append(f"  {video_id}  {channel[:30]:<30}  {title[:70]}")
        lines.extend(f"  fetch: {message}" for message in self.fetch_messages)
        lines.append(f"Candidates extracted: {len(self.candidates)}")
        matched = self.matched_remedies
        lines.append(f"Reason-matched remedies/causes: {len(matched)}")
        return lines


_PLANET_TAGS = {"sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"}
_CONDITION_WORDS = {"debilitated", "combust", "afflicted", "enemy", "weak"}


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def build_query(topic: str, reason: str, compact: bool = False) -> str:
    """Search-friendly query derived from the engine's reason tags."""
    tags = canonical_reason_tags([reason])
    planets: List[str] = []
    conditions: List[str] = []
    houses: List[str] = []
    lords: List[str] = []
    for tag in tags:
        if tag in _PLANET_TAGS:
            planets.append(tag)
            continue
        pieces = tag.split("_")
        if len(pieces) == 1 and pieces[0] in _CONDITION_WORDS:
            conditions.append(pieces[0])
            continue
        if len(pieces) == 2 and pieces[0] in _PLANET_TAGS \
                and pieces[1] in _CONDITION_WORDS:
            conditions.append(pieces[1])
            continue
        if len(pieces) == 3 and pieces[0] in _PLANET_TAGS and pieces[2].isdigit():
            if pieces[1] == "house":
                houses.append(f"{_ordinal(int(pieces[2]))} house")
            elif pieces[1] == "lord":
                lords.append(f"{_ordinal(int(pieces[2]))} lord")
    parts: List[str] = []
    for part in planets + conditions:
        if part not in parts:
            parts.append(part)
    if any(tag.startswith("dasha_lord_") for tag in tags) and "mahadasha" not in parts:
        parts.append("mahadasha")
    if any(tag.startswith("antardasha_") for tag in tags) and "antardasha" not in parts:
        parts.append("antardasha")
    if any(tag.startswith("pratyantardasha_") for tag in tags) and "pratyantardasha" not in parts:
        parts.append("pratyantardasha")
    if compact:
        if topic and topic.lower() != "general":
            parts.append(topic)
        parts.append("remedy")
    else:
        for part in (lords or houses):
            if part not in parts:
                parts.append(part)
        for part in (topic, "remedy", "jyotish"):
            if part and part.lower() != "general" and part not in parts:
                parts.append(part)
    return " ".join(part for part in parts if part and part.strip())


def deep_search(topic: str, reason: str, *, limit: int = 5,
                store: Optional[VideoStore] = None,
                searcher: Optional[Searcher] = None,
                extractor: Optional[Extractor] = None,
                client=None, library_search: Optional[Callable] = None,
                max_chunks: int = 2, max_claims: int = 6) -> DeepSearchOutcome:
    store = store or VideoStore()
    queries = [build_query(topic, reason), build_query(topic, reason, compact=True)]
    videos: List[Tuple[str, str, str]] = []
    used_query = queries[0]
    for query in queries:
        videos = search_videos(query, limit=limit, searcher=searcher)
        used_query = query
        if videos:
            break
    query = used_query

    targets = [f"https://www.youtube.com/watch?v={video_id}"
               for video_id, _, _ in videos]
    messages = fetch_videos(targets, store=store, extractor=extractor)

    if client is None:
        from ..chat.client import DeepSeekClient
        client = DeepSeekClient()

    extracted: List[CandidateClaim] = []
    for video_id, title, _ in videos:
        record = store.load_record(video_id)
        if record is None or not store.load_cues(video_id):
            continue
        try:
            claims = dual_pass_extract(record, store.load_cues(video_id), client,
                                       max_chunks=max_chunks, max_claims=max_claims)
        except Exception as exc:
            messages.append(f"extract error {video_id}: {type(exc).__name__}: {exc}")
            continue
        extracted.extend(claims)
    save_candidates(extracted)

    video_ids = {video_id for video_id, _, _ in videos}
    selected = [claim for claim in load_candidates() if claim.video_id in video_ids]
    results = evaluate_candidates(selected, library_search=library_search)

    wanted = set(canonical_reason_tags([reason]))

    def rank(result: GateResult) -> Tuple[int, int]:
        tags = set(canonical_reason_tags(result.candidate.reason_tags))
        overlap = len(tags & wanted)
        remedy = 1 if result.candidate.kind in ("remedy", "cause") else 0
        return (-overlap, -remedy)

    results.sort(key=rank)
    return DeepSearchOutcome(
        topic=topic, reason=reason, query=query,
        reason_tags=sorted(wanted), videos=videos,
        fetch_messages=messages, candidates=extracted, results=results,
    )
