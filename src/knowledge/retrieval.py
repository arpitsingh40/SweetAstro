"""
Deterministic knowledge retrieval for source citations.

Parses the numbered entries of docs/knowledge/01_classical_canon.md,
02_modern_specialized.md and 03_applied_systems.md:

    N. **Title** — summary. → category, category. [status]

and builds an in-memory keyword index. Given a question + topic it returns the
most relevant entries, which the chat payload exposes as the ONLY citable
sources. No network, no embeddings, fully deterministic.

The retrieval returns existing metadata only — titles, one-line summaries and
category/status labels from the project's own corpus. It never fabricates
verses, pages, or quotations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_DIR = _PROJECT_ROOT / "docs" / "knowledge"

KNOWLEDGE_FILES: Sequence[str] = (
    "01_classical_canon.md",
    "02_modern_specialized.md",
    "03_applied_systems.md",
)

_ENTRY_RE = re.compile(r"^(\d+)\.\s+\*\*(?P<title>[^*]+)\*\*\s+—\s+(?P<rest>.+)$")
_STATUS_RE = re.compile(r"\[(?P<status>canon|known|tech|verify)\]\s*$")
_ARROW = "\u2192"  # →
_TIER_RE = re.compile(r"^##\s+(T\d+)\b")

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "is", "are", "was",
    "my", "me", "i", "will", "when", "how", "what", "which", "who", "to", "do",
    "does", "did", "can", "could", "should", "would", "about", "with", "at",
    "by", "from", "it", "this", "that", "be", "been", "get", "got", "have",
    "has", "had", "am", "please", "tell", "know", "want", "need", "there",
}

TOPIC_CATEGORY_MAP: Dict[str, List[str]] = {
    "marriage": ["marriage", "promise", "delay", "timing_dasha", "jaimini", "stability"],
    "wealth": ["promise", "timing_dasha", "strength", "timing_transit"],
    "career": ["promise", "timing_dasha", "strength", "timing_transit"],
    "business": ["promise", "timing_dasha", "strength"],
    "children": ["promise", "timing_dasha"],
    "property": ["promise", "timing_dasha", "vastu"],
    "education": ["promise", "timing_dasha"],
    "siblings": ["promise", "timing_dasha"],
    "health": ["health", "stability", "longevity"],
    "spirituality": ["moksha", "jaimini", "promise"],
    "general": ["promise", "stability", "timing_dasha"],
}


@dataclass
class KnowledgeEntry:
    entry_id: int
    title: str
    summary: str
    categories: List[str] = field(default_factory=list)
    status: str = ""
    tier: str = ""
    source_file: str = ""

    @property
    def category_text(self) -> str:
        return ", ".join(self.categories)

    def to_line(self) -> str:
        parts = [f'"{self.title}"']
        meta = ", ".join(x for x in (self.status, self.category_text) if x)
        if meta:
            parts.append(f"({meta})")
        text = " ".join(parts)
        if self.summary:
            text += f" — {self.summary}"
        if self.source_file:
            text += f" [{self.source_file}]"
        return text


class KnowledgeIndex:
    """In-memory keyword index over the curated knowledge entries."""

    def __init__(self, entries: Sequence[KnowledgeEntry]):
        self.entries: List[KnowledgeEntry] = list(entries)

    @classmethod
    def from_directory(cls, directory: Path = KNOWLEDGE_DIR,
                       files: Sequence[str] = KNOWLEDGE_FILES) -> "KnowledgeIndex":
        entries: List[KnowledgeEntry] = []
        for name in files:
            path = directory / name
            if not path.exists():
                continue
            entries.extend(_parse_file(path))
        return cls(entries)

    def search(self, query: str, *, topic: str = "general",
               limit: int = 6) -> List[KnowledgeEntry]:
        tokens = _tokenize(query)
        topic_categories = TOPIC_CATEGORY_MAP.get(topic, [])
        scored: List[Tuple[float, int, KnowledgeEntry]] = []
        for entry in self.entries:
            score = 0.0
            title_lower = entry.title.lower()
            summary_lower = entry.summary.lower()
            categories_lower = [c.lower() for c in entry.categories]
            for token in tokens:
                if token in title_lower:
                    score += 3.0
                if token in summary_lower:
                    score += 1.0
                if any(token in c for c in categories_lower):
                    score += 2.0
            for category in topic_categories:
                if any(category in c for c in categories_lower):
                    score += 1.5
                if category in summary_lower:
                    score += 0.5
            if score > 0:
                scored.append((score, -entry.entry_id, entry))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [entry for _, _, entry in scored[:max(1, limit)]]


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _parse_file(path: Path) -> List[KnowledgeEntry]:
    entries: List[KnowledgeEntry] = []
    tier = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        tier_match = _TIER_RE.match(line)
        if tier_match:
            tier = tier_match.group(1)
            continue
        entry_match = _ENTRY_RE.match(line)
        if not entry_match:
            continue

        rest = entry_match.group("rest").strip()
        status = ""
        status_match = _STATUS_RE.search(rest)
        if status_match:
            status = status_match.group("status")
            rest = rest[:status_match.start()].strip()

        categories: List[str] = []
        if _ARROW in rest:
            summary_part, _, category_part = rest.partition(_ARROW)
            summary = summary_part.strip().rstrip(".")
            categories = [
                c.strip().rstrip(".")
                for c in category_part.split(",")
                if c.strip().rstrip(".")
            ]
        else:
            summary = rest.strip().rstrip(".")

        entries.append(KnowledgeEntry(
            entry_id=int(entry_match.group(1)),
            title=entry_match.group("title").strip(),
            summary=summary,
            categories=categories,
            status=status,
            tier=tier,
            source_file=path.name,
        ))
    return entries


@lru_cache(maxsize=1)
def get_knowledge_index() -> KnowledgeIndex:
    return KnowledgeIndex.from_directory()


def retrieve_references(question: str, topic: str = "general",
                        limit: int = 6) -> List[KnowledgeEntry]:
    """Most relevant curated sources for a question + topic (deterministic)."""
    return get_knowledge_index().search(question, topic=topic, limit=limit)


def reference_lines(entries: Iterable[KnowledgeEntry]) -> List[str]:
    return [f"- {entry.to_line()}" for entry in entries]
