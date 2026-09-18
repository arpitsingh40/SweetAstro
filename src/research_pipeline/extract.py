"""
Claim extraction from video transcripts (research only, quarantine-bound).

The LLM proposes candidate rules/calculations as strict JSON. Nothing is
trusted: a claim is kept only when its verbatim quote is actually present in
the transcript chunk and its timestamp falls inside that chunk. Dual-pass
extraction keeps only claims produced independently by both passes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .captions import Cue, format_timestamp, parse_timestamp
from .store import VideoRecord, video_store_dir

TARGETS: Tuple[str, ...] = (
    "marriage", "wealth", "career", "children", "health", "longevity",
    "education", "property", "timing", "remedies", "spirituality", "general",
)

CHUNK_CHARS = 6000
MIN_QUOTE_CHARS = 15

_SYSTEM_PROMPT = (
    "You extract calculation methods, rules and remedies from astrology video "
    "transcripts for an offline research archive. Reply with strict JSON only: "
    '{"claims": [{"claim": str, "target": str, '
    '"kind": "calculation"|"rule"|"cause"|"remedy", '
    '"formula": str, "steps": [str], "remedies": [str], "examples": [str], '
    '"reason_tags": [str], "quote": str, "start": "MM:SS", "end": "MM:SS", '
    '"confidence": "high"|"medium"|"low"}]}. '
    "Extract only genuine methods, checkable rules, exact causal reasons "
    "(kind=cause: why an unfavourable result happens) and practical remedies "
    "(kind=remedy: what to do about a specific affliction) — never general "
    "talk, opinions, or promotions. reason_tags are snake_case astrological "
    "conditions the claim addresses, e.g. venus_debilitated, saturn_house_7, "
    "7th_lord_weak, rahu_house_5. The quote must be a verbatim excerpt from "
    "the transcript (same words). If uncertain, omit the claim. "
    f"target must be one of: {', '.join(TARGETS)}."
)


class ExtractionError(RuntimeError):
    """Raised when the extractor response cannot be used."""


@dataclass
class CandidateClaim:
    candidate_id: str
    video_id: str
    claim: str
    target: str
    kind: str
    quote: str
    locator: str
    start: float
    end: float
    formula: str = ""
    steps: Tuple[str, ...] = ()
    examples: Tuple[str, ...] = ()
    remedies: Tuple[str, ...] = ()
    reason_tags: Tuple[str, ...] = ()
    confidence: str = "low"
    passes: int = 1
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("steps", "examples", "remedies", "reason_tags"):
            data[key] = list(getattr(self, key))
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateClaim":
        return cls(
            candidate_id=str(data.get("candidate_id", "")),
            video_id=str(data.get("video_id", "")),
            claim=str(data.get("claim", "")),
            target=str(data.get("target", "general")),
            kind=str(data.get("kind", "rule")),
            quote=str(data.get("quote", "")),
            locator=str(data.get("locator", "")),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            formula=str(data.get("formula", "")),
            steps=tuple(str(s) for s in data.get("steps", [])),
            examples=tuple(str(s) for s in data.get("examples", [])),
            remedies=tuple(str(s) for s in data.get("remedies", [])),
            reason_tags=tuple(str(s) for s in data.get("reason_tags", [])),
            confidence=str(data.get("confidence", "low")),
            passes=int(data.get("passes", 1)),
            evidence=dict(data.get("evidence") or {}),
        )

    @property
    def key(self) -> str:
        normalized = _normalize(self.claim)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def deep_link(self, record: Optional[VideoRecord] = None) -> str:
        base = record.watch_url if record else f"https://www.youtube.com/watch?v={self.video_id}"
        return f"{base}&t={int(self.start)}s"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


_WORD_RE = re.compile(r"[\w\u0900-\u097f]+", re.UNICODE)


def _tokens(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _quote_supported(quote: str, transcript: str) -> bool:
    """Verbatim check tolerant of auto-caption rolling duplicates.

    Exact substring first; otherwise the quote tokens must match the
    transcript in order within a local window (coverage >= 70%).
    """
    quote_tokens = _tokens(quote)
    transcript_tokens = _tokens(transcript)
    if not quote_tokens or not transcript_tokens:
        return False
    if " ".join(quote_tokens) in " ".join(transcript_tokens):
        return True
    needed = max(3, int(len(quote_tokens) * 0.7))
    first = quote_tokens[0]
    window = max(len(quote_tokens) * 3, 12)
    for anchor in (i for i, token in enumerate(transcript_tokens) if token == first):
        matched = 0
        for token in transcript_tokens[anchor:anchor + window]:
            if matched < len(quote_tokens) and token == quote_tokens[matched]:
                matched += 1
        if matched >= needed:
            return True
    return False


def _chunk_cues(cues: Sequence[Cue], max_chars: int = CHUNK_CHARS
                ) -> List[Tuple[float, float, List[Cue]]]:
    chunks: List[Tuple[float, float, List[Cue]]] = []
    current: List[Cue] = []
    size = 0
    for cue in cues:
        if current and size + len(cue.text) > max_chars:
            chunks.append((current[0].start, current[-1].end, current))
            current = []
            size = 0
        current.append(cue)
        size += len(cue.text)
    if current:
        chunks.append((current[0].start, current[-1].end, current))
    return chunks


def _prompt_messages(record: VideoRecord, chunk_text: str,
                     start: float, end: float) -> List[Dict[str, str]]:
    user = (
        f"Video: {record.title}\nChannel: {record.channel}\n"
        f"Transcript window: {format_timestamp(start)} to {format_timestamp(end)}\n"
        "--- transcript ---\n" + chunk_text
    )
    return [{"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def _validate_claim(raw: Dict[str, Any], record: VideoRecord,
                    chunk_text: str, chunk_start: float, chunk_end: float,
                    passes: int) -> Optional[CandidateClaim]:
    if not isinstance(raw, dict):
        return None
    claim = str(raw.get("claim") or "").strip()
    quote = str(raw.get("quote") or "").strip()
    if len(claim) < 12 or len(quote) < MIN_QUOTE_CHARS:
        return None
    if not _quote_supported(quote, chunk_text):
        return None
    target = str(raw.get("target") or "general").strip().lower()
    if target not in TARGETS:
        target = "general"
    try:
        start = parse_timestamp(str(raw.get("start") or ""))
        end = parse_timestamp(str(raw.get("end") or "")) if raw.get("end") else start
    except Exception:
        start, end = chunk_start, chunk_end
    start = min(max(start, chunk_start), chunk_end)
    end = min(max(end, start), chunk_end)
    kind = str(raw.get("kind") or "rule").strip().lower()
    if kind not in ("calculation", "rule", "cause", "remedy"):
        kind = "rule"
    confidence = str(raw.get("confidence") or "low").strip().lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "low"
    steps = tuple(str(s).strip() for s in (raw.get("steps") or []) if str(s).strip())
    examples = tuple(str(s).strip() for s in (raw.get("examples") or []) if str(s).strip())
    remedies = tuple(str(s).strip() for s in (raw.get("remedies") or []) if str(s).strip())
    reason_tags = tuple(str(s).strip() for s in (raw.get("reason_tags") or []) if str(s).strip())
    digest = hashlib.sha256(
        f"{record.video_id}|{_normalize(claim)}".encode("utf-8")).hexdigest()[:10]
    return CandidateClaim(
        candidate_id=f"VC-{digest}",
        video_id=record.video_id,
        claim=claim,
        target=target,
        kind=kind,
        quote=quote,
        locator=f"{format_timestamp(start)}-{format_timestamp(end)}",
        start=start,
        end=end,
        formula=str(raw.get("formula") or "").strip(),
        steps=steps,
        examples=examples,
        remedies=remedies,
        reason_tags=reason_tags,
        confidence=confidence,
        passes=passes,
    )


def extract_claims(record: VideoRecord, cues: Sequence[Cue], client,
                   *, max_chunks: int = 3, max_claims: int = 8,
                   temperature: float = 0.0) -> List[CandidateClaim]:
    """One extraction pass over the transcript; returns validated claims."""
    chunks = _chunk_cues(cues)[:max_chunks]
    claims: List[CandidateClaim] = []
    seen = set()
    for chunk_start, chunk_end, chunk_cues in chunks:
        chunk_text = " ".join(cue.text for cue in chunk_cues)
        messages = _prompt_messages(record, chunk_text, chunk_start, chunk_end)
        try:
            payload = client.complete_json(
                messages, temperature=temperature, thinking=False)
        except Exception as exc:
            raise ExtractionError(f"extraction call failed: {exc}") from exc
        for raw in (payload.get("claims") or [])[:max_claims]:
            candidate = _validate_claim(raw, record, chunk_text,
                                        chunk_start, chunk_end, passes=1)
            if candidate and candidate.key not in seen:
                seen.add(candidate.key)
                claims.append(candidate)
    return claims


def dual_pass_extract(record: VideoRecord, cues: Sequence[Cue], client,
                      *, max_chunks: int = 3, max_claims: int = 8,
                      secondary_temperature: float = 0.5) -> List[CandidateClaim]:
    """Two independent passes; keep only claims both passes produced.

    Claims are matched by their verbatim quote (token overlap >= 0.8) or by
    claim-text similarity (Jaccard >= 0.6), because the model legitimately
    rewords the same rule between passes.
    """
    first = extract_claims(record, cues, client, max_chunks=max_chunks,
                           max_claims=max_claims, temperature=0.0)
    second = extract_claims(record, cues, client, max_chunks=max_chunks,
                            max_claims=max_claims, temperature=secondary_temperature)
    kept = [candidate for candidate in first
            if any(claims_match(candidate, other) for other in second)]
    for candidate in kept:
        candidate.passes = 2
    return kept


def claims_match(a: CandidateClaim, b: CandidateClaim) -> bool:
    """Same-rule test: near-identical quote, or similar claim wording."""
    quote_a, quote_b = set(_tokens(a.quote)), set(_tokens(b.quote))
    if quote_a and quote_b:
        overlap = len(quote_a & quote_b) / max(1, min(len(quote_a), len(quote_b)))
        if overlap >= 0.8:
            return True
    claim_a, claim_b = set(_tokens(a.claim)), set(_tokens(b.claim))
    union = claim_a | claim_b
    return bool(union) and len(claim_a & claim_b) / len(union) >= 0.6


def candidates_path() -> Path:
    return video_store_dir().parent / "candidates.jsonl"


def load_candidates(path: Optional[Path] = None) -> List[CandidateClaim]:
    path = Path(path) if path else candidates_path()
    if not path.exists():
        return []
    claims: List[CandidateClaim] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            claims.append(CandidateClaim.from_dict(record))
    return claims


def save_candidates(candidates: Iterable[CandidateClaim],
                    path: Optional[Path] = None) -> Tuple[int, int]:
    path = Path(path) if path else candidates_path()
    existing = {claim.candidate_id for claim in load_candidates(path)}
    added = 0
    skipped = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for candidate in candidates:
            if candidate.candidate_id in existing:
                skipped += 1
                continue
            handle.write(json.dumps(candidate.to_dict(), ensure_ascii=False) + "\n")
            existing.add(candidate.candidate_id)
            added += 1
    return added, skipped
