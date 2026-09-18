"""
Evidence gate for extracted claims.

Nothing extracted from a video may influence the engine on its own. Each
candidate is scored by what *independent* support exists:

    classical_candidate  — the public-domain library contains a matching rule
                           (the classical locus becomes the authority)
    modern_candidate     — two or more independent videos describe it the same way
    quarantine           — single-source; stays quarantined until more support

Human verification via research_intake.py remains the only path to promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .extract import CandidateClaim, claims_match

LibrarySearch = Callable[[str, int], List[str]]

VERDICT_ORDER = ("classical_candidate", "modern_candidate", "quarantine")


def _cluster(candidates: Sequence[CandidateClaim]) -> List[List[CandidateClaim]]:
    """Union-find clustering by same-rule similarity (quotes or wording)."""
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            if claims_match(candidates[i], candidates[j]):
                union(i, j)

    clusters: Dict[int, List[CandidateClaim]] = {}
    for index, candidate in enumerate(candidates):
        clusters.setdefault(find(index), []).append(candidate)
    return list(clusters.values())


@dataclass
class GateResult:
    candidate: CandidateClaim
    convergence: int
    verdict: str
    classical_hits: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


def default_library_search(query: str, limit: int = 2) -> List[str]:
    try:
        from ..knowledge.library import search_library
        passages = search_library(query, limit=limit)
    except Exception:
        return []
    return [f"{passage.citation}, {passage.locator} (score {passage.score})"
            for passage in passages]


def evaluate_candidates(candidates: Sequence[CandidateClaim], *,
                        library_search: Optional[LibrarySearch] = None,
                        records: Optional[Dict[str, object]] = None) -> List[GateResult]:
    """Classify candidates by classical support and independent convergence.

    ``records`` maps video_id -> VideoRecord; when present, convergence counts
    distinct channels instead of distinct videos (same-channel repeats are not
    independent evidence).
    """
    library_search = library_search or default_library_search
    groups = _cluster(candidates)

    def _independent_count(group: Sequence[CandidateClaim]) -> int:
        if records:
            keys = set()
            for candidate in group:
                record = records.get(candidate.video_id)
                channel = getattr(record, "channel", "") if record else ""
                keys.add(channel.strip().lower() or candidate.video_id)
            return len(keys)
        return len({candidate.video_id for candidate in group})

    results: List[GateResult] = []
    for group in groups:
        convergence = _independent_count(group)
        representative = max(
            group,
            key=lambda item: (item.passes, item.confidence == "high", len(item.claim)))
        hits = library_search(representative.claim, 2)
        reasons: List[str] = []
        if hits:
            verdict = "classical_candidate"
            reasons.append("classical locus found in the public-domain library")
        elif convergence >= 2:
            verdict = "modern_candidate"
            reasons.append(f"described consistently by {convergence} independent sources")
        else:
            verdict = "quarantine"
            reasons.append("single-source claim; needs a second independent source or a classical locus")
        if representative.kind == "calculation":
            reasons.append("calculation — reproduce every worked example before use")
        if representative.confidence == "low":
            reasons.append("extractor confidence low (auto-caption noise)")
        results.append(GateResult(
            candidate=representative,
            convergence=convergence,
            verdict=verdict,
            classical_hits=hits,
            reasons=reasons,
        ))

    results.sort(key=lambda item: (
        VERDICT_ORDER.index(item.verdict), -item.convergence, item.candidate.target))
    return results


def format_gate_results(results: Iterable[GateResult],
                        records: Optional[Dict[str, object]] = None) -> List[str]:
    records = records or {}
    lines: List[str] = []
    for result in results:
        candidate = result.candidate
        record = records.get(candidate.video_id)
        lines.append(
            f"[{result.verdict}] {candidate.candidate_id} · {candidate.target} · "
            f"{candidate.kind} · {candidate.locator} · videos={result.convergence}")
        lines.append(f"  claim: {candidate.claim}")
        lines.append(f"  quote: \"{candidate.quote[:200]}\"")
        if candidate.formula:
            lines.append(f"  formula: {candidate.formula}")
        for step in candidate.steps:
            lines.append(f"  step: {step}")
        for hit in result.classical_hits:
            lines.append(f"  classical: {hit}")
        for reason in result.reasons:
            lines.append(f"  note: {reason}")
        lines.append(f"  link: {candidate.deep_link(record)}")
        lines.append("")
    return lines
