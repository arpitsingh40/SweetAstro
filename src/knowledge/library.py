"""
Public-domain full-text library for classical astrology sources.

The curated corpus in ``docs/knowledge/*.md`` is a metadata index (titles,
summaries, categories). This module adds the actual texts: every volume in
``data/library/catalog.json`` is a verifiably public-domain edition whose scan
or transcription is downloaded to ``data/library/sources/`` and segmented into
passages at ``data/library/index/``.

Design rules
------------
- No copyright-restricted translations are stored; the catalog records the
  public-domain basis for each volume (see ``license_note`` in the catalog).
- Retrieval is deterministic keyword scoring (no embeddings, no network) and
  returns verbatim passages with a citation (book, translator/edition, year)
  and a locator. The locator is an honest text-partition label: ``leaf N`` for
  scan pages separated by form feeds and ``passage N`` (optionally under a
  chapter heading) for continuous transcriptions. It is never a fabricated
  printed page or verse number.
- Nothing is invented: an empty or missing index yields an empty result, so the
  answer path degrades to the curated metadata index alone.

CLI (repository root): ``python library.py fetch|build|search|stats|verify``.
"""

from __future__ import annotations

import json
import math
import re
import urllib.parse
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

from .retrieval import TOPIC_CATEGORY_MAP, _tokenize

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LIBRARY_DIR = _PROJECT_ROOT / "data" / "library"
CATALOG_NAME = "catalog.json"
SOURCES_DIRNAME = "sources"
INDEX_DIRNAME = "index"

DEFAULT_LIMIT = 4
DEFAULT_MIN_SCORE = 2.0
DEFAULT_EXCERPT_CHARS = 280
MAX_PASSAGE_CHARS = 1400
MIN_PASSAGE_CHARS = 200

_USER_AGENT = "SweetAstro/1.0 (public-domain corpus fetch; local research)"
_FETCH_TIMEOUT_SECONDS = 120

GUTENBERG_TXT_URL = "https://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt"
ARCHIVE_METADATA_URL = "https://archive.org/metadata/{ident}"
ARCHIVE_DOWNLOAD_URL = "https://archive.org/download/{ident}/{name}"

_GUTENBERG_START_RE = re.compile(
    r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG", re.IGNORECASE)
_GUTENBERG_END_RE = re.compile(
    r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG", re.IGNORECASE)
_CHAPTER_RE = re.compile(
    r"^\s*(chapter|book|part|section|adhyaya)\b[.:\s]*([IVXLCDM]+|\d+)\b",
    re.IGNORECASE)
_PAGE_NUMBER_LINE_RE = re.compile(r"^\s*[-–—. ]*\d{1,4}[-–—. ]*\s*$")
_FORM_FEED = "\f"

QUERY_VARIANTS: Dict[str, Tuple[str, ...]] = {
    "marriage": ("marriage", "marry", "married", "wife", "husband", "spouse", "wedding"),
    "married": ("marry", "married", "marriage", "wife", "husband", "spouse"),
    "wife": ("wife", "marriage", "spouse"),
    "husband": ("husband", "marriage", "spouse"),
    "children": ("children", "child", "issue", "progeny", "son", "daughter"),
    "child": ("child", "children", "progeny"),
    "career": ("career", "profession", "occupation", "livelihood"),
    "wealth": ("wealth", "money", "riches", "fortune", "gain", "prosperity"),
    "education": ("education", "learning", "knowledge", "study"),
    "health": ("health", "disease", "sickness", "illness", "infirmity"),
    "longevity": ("longevity", "life", "death", "span"),
    "dasha": ("dasha", "dasa", "period", "bhukti"),
    "dasa": ("dasa", "dasha", "period"),
    "antardasha": ("antardasha", "bhukti", "subperiod"),
    "transit": ("transit", "gochara", "passes", "enters"),
    "gochara": ("gochara", "transit"),
    "saturn": ("saturn", "sani"),
    "sani": ("sani", "saturn"),
    "jupiter": ("jupiter", "guru"),
    "guru": ("guru", "jupiter"),
    "moon": ("moon", "chandra"),
    "chandra": ("chandra", "moon"),
    "sun": ("sun", "surya"),
    "surya": ("surya", "sun"),
    "mercury": ("mercury", "budha"),
    "venus": ("venus", "sukra"),
    "mars": ("mars", "kuja", "mangal"),
    "first": ("first", "1st", "lagna", "ascendant"),
    "second": ("second", "2nd"),
    "third": ("third", "3rd"),
    "fourth": ("fourth", "4th"),
    "fifth": ("fifth", "5th"),
    "sixth": ("sixth", "6th"),
    "seventh": ("seventh", "7th"),
    "8th": ("8th", "eighth"),
    "eighth": ("eighth", "8th"),
    "ninth": ("ninth", "9th"),
    "tenth": ("tenth", "10th"),
    "eleventh": ("eleventh", "11th"),
    "twelfth": ("twelfth", "12th"),
}


def _expand_tokens(tokens: Sequence[str]) -> Dict[str, float]:
    """Query token -> match multiplier, with edition-spelling/house variants."""
    expanded: Dict[str, float] = {}
    for token in tokens:
        expanded[token] = max(expanded.get(token, 0.0), 1.0)
        for variant in QUERY_VARIANTS.get(token, ()):
            if variant != token:
                expanded[variant] = max(expanded.get(variant, 0.0), 0.6)
    return expanded


class LibraryError(RuntimeError):
    """Raised when the library catalog or a fetch operation is invalid."""


@dataclass(frozen=True)
class LibrarySource:
    slug: str
    title: str
    short_title: str = ""
    author: str = ""
    translator: str = ""
    edition: str = ""
    year: str = ""
    language: str = "en"
    format: str = "archive"
    remote_id: str = ""
    source_url: str = ""
    rights: str = ""
    pd_basis: str = ""
    categories: Tuple[str, ...] = ()
    note: str = ""

    @property
    def display_title(self) -> str:
        return self.short_title or self.title

    @property
    def citation(self) -> str:
        bits: List[str] = []
        if self.translator:
            bits.append(f"trans. {self.translator}")
        if self.year:
            bits.append(self.year)
        suffix = ", ".join(bits)
        return f"{self.display_title} ({suffix})" if suffix else self.display_title


@dataclass(frozen=True)
class LibraryPassage:
    book_slug: str
    book_title: str
    citation: str
    locator: str
    text: str
    seq: int = 0
    score: float = 0.0


def library_dir() -> Path:
    import os
    override = os.environ.get("SWEETASTRO_LIBRARY_DIR")
    return Path(override) if override else LIBRARY_DIR


def load_catalog(directory: Optional[Path] = None) -> List[LibrarySource]:
    path = (directory or library_dir()) / CATALOG_NAME
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LibraryError(f"Invalid catalog JSON at {path}: {exc}") from exc
    sources: List[LibrarySource] = []
    for record in raw.get("sources", []):
        if not isinstance(record, dict):
            continue
        categories = record.get("categories") or []
        sources.append(LibrarySource(
            slug=str(record.get("slug", "")).strip(),
            title=str(record.get("title", "")).strip(),
            short_title=str(record.get("short_title", "")).strip(),
            author=str(record.get("author", "")).strip(),
            translator=str(record.get("translator", "")).strip(),
            edition=str(record.get("edition", "")).strip(),
            year=str(record.get("year", "")).strip(),
            language=str(record.get("language", "en")).strip() or "en",
            format=str(record.get("format", "")).strip(),
            remote_id=str(record.get("remote_id", "")).strip(),
            source_url=str(record.get("source_url", "")).strip(),
            rights=str(record.get("rights", "")).strip(),
            pd_basis=str(record.get("pd_basis", "")).strip(),
            categories=tuple(str(c).strip() for c in categories if str(c).strip()),
            note=str(record.get("note", "")).strip(),
        ))
    return sources


def validate_catalog(directory: Optional[Path] = None) -> List[str]:
    """Problems that make the catalog inadmissible (empty list means valid)."""
    problems: List[str] = []
    sources = load_catalog(directory)
    if not sources:
        problems.append("catalog is missing or contains no sources")
        return problems
    seen = set()
    for source in sources:
        if not source.slug:
            problems.append("source with empty slug")
            continue
        if source.slug in seen:
            problems.append(f"duplicate slug: {source.slug}")
        seen.add(source.slug)
        if not source.title:
            problems.append(f"{source.slug}: missing title")
        if source.format not in ("gutenberg", "archive"):
            problems.append(f"{source.slug}: unknown format {source.format!r}")
        if not source.remote_id:
            problems.append(f"{source.slug}: missing remote_id")
        if not source.rights:
            problems.append(f"{source.slug}: missing rights statement")
        if not source.pd_basis:
            problems.append(f"{source.slug}: missing public-domain basis")
    return problems


def source_text_path(slug: str, directory: Optional[Path] = None) -> Path:
    return (directory or library_dir()) / SOURCES_DIRNAME / f"{slug}.txt"


def index_path(slug: str, directory: Optional[Path] = None) -> Path:
    return (directory or library_dir()) / INDEX_DIRNAME / f"{slug}.jsonl"


def _http_get(url: str) -> bytes:
    try:
        response = httpx.get(url, headers={"User-Agent": _USER_AGENT},
                             timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as exc:
        raise LibraryError(f"fetch failed for {url}: {exc}") from exc


def _archive_text_url(remote_id: str) -> str:
    payload = json.loads(_http_get(ARCHIVE_METADATA_URL.format(ident=remote_id)).decode("utf-8"))
    for entry in payload.get("files", []):
        name = str(entry.get("name", ""))
        if name.endswith("_djvu.txt"):
            return ARCHIVE_DOWNLOAD_URL.format(ident=remote_id, name=urllib.parse.quote(name))
    raise LibraryError(
        f"archive item {remote_id!r} exposes no *_djvu.txt text file; "
        "only text-extractable items can join the corpus.")


def remote_text_url(source: LibrarySource) -> str:
    if source.format == "gutenberg":
        return GUTENBERG_TXT_URL.format(eid=source.remote_id)
    if source.format == "archive":
        return _archive_text_url(source.remote_id)
    raise LibraryError(f"{source.slug}: unknown format {source.format!r}")


def fetch_sources(directory: Optional[Path] = None,
                  only: Optional[Sequence[str]] = None) -> List[str]:
    """Download missing source texts; existing files are left untouched."""
    directory = directory or library_dir()
    messages: List[str] = []
    wanted = set(only) if only else None
    for source in load_catalog(directory):
        if wanted is not None and source.slug not in wanted:
            continue
        destination = source_text_path(source.slug, directory)
        if destination.exists() and destination.stat().st_size > 0:
            messages.append(f"skip {source.slug} (already present, "
                            f"{destination.stat().st_size} bytes)")
            continue
        url = remote_text_url(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_http_get(url))
        messages.append(f"fetched {source.slug} <- {url} "
                        f"({destination.stat().st_size} bytes)")
    return messages


def _strip_gutenberg(text: str) -> str:
    start = _GUTENBERG_START_RE.search(text)
    if start:
        text = text[start.end():]
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1:]
    end = _GUTENBERG_END_RE.search(text)
    if end:
        text = text[:end.start()]
    return text


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = text.replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _paragraphs(block: str) -> List[str]:
    parts = re.split(r"\n\s*\n", block)
    return [" ".join(part.split()) for part in parts if part.strip()]


def _is_garbled_line(line: str) -> bool:
    """OCR-noise heuristic: replacement chars or mostly punctuation/symbols."""
    stripped = line.strip()
    if not stripped:
        return False
    if "\ufffd" in stripped:
        return True
    readable = sum(1 for ch in stripped if ch.isalpha() or ch.isspace())
    return readable / len(stripped) < 0.55


def _chapter_label(line: str) -> str:
    if len(line) > 90:
        return ""
    match = _CHAPTER_RE.match(line)
    if not match:
        return ""
    return f"ch. {match.group(2).upper()}"


def _emit_passages(paragraphs: Sequence[str], prefix: str,
                   start_index: int = 0) -> List[Tuple[str, str]]:
    emitted: List[Tuple[str, str]] = []
    buffer = ""
    counter = start_index
    for paragraph in paragraphs:
        if not paragraph:
            continue
        candidate = f"{buffer} {paragraph}".strip() if buffer else paragraph
        if len(candidate) <= MAX_PASSAGE_CHARS:
            buffer = candidate
            continue
        if buffer:
            counter += 1
            label = f"{prefix}, passage {counter}" if prefix else f"passage {counter}"
            emitted.append((label, buffer))
        buffer = paragraph
        while len(buffer) > MAX_PASSAGE_CHARS:
            cut = buffer.rfind(" ", 0, MAX_PASSAGE_CHARS)
            if cut < MAX_PASSAGE_CHARS // 2:
                cut = MAX_PASSAGE_CHARS
            piece, buffer = buffer[:cut].strip(), buffer[cut:].strip()
            if piece:
                counter += 1
                label = f"{prefix}, passage {counter}" if prefix else f"passage {counter}"
                emitted.append((label, piece))
    if buffer:
        counter += 1
        label = f"{prefix}, passage {counter}" if prefix else f"passage {counter}"
        emitted.append((label, buffer))
    return emitted


def segment_gutenberg(text: str) -> List[Tuple[str, str]]:
    text = _clean_text(_strip_gutenberg(text))
    sections: List[Tuple[str, List[str]]] = []
    current_label = ""
    current: List[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        label = _chapter_label(line)
        if label:
            if current:
                sections.append((current_label, current))
                current = []
            current_label = label
            continue
        if not line:
            if current:
                sections.append((current_label, current))
                current = []
            continue
        current.append(line)
    if current:
        sections.append((current_label, current))

    emitted: List[Tuple[str, str]] = []
    counter = 0
    for label, lines in sections:
        paragraphs = [" ".join(line.split()) for line in lines if line.strip()]
        pieces = _emit_passages(paragraphs, label, start_index=counter)
        emitted.extend(pieces)
        counter += len(pieces)
    return emitted


def segment_archive(text: str) -> List[Tuple[str, str]]:
    text = _clean_text(text)
    if text.count(_FORM_FEED) >= 3:
        emitted: List[Tuple[str, str]] = []
        for page_index, page in enumerate(text.split(_FORM_FEED)):
            lines = [
                line for line in page.split("\n")
                if not _PAGE_NUMBER_LINE_RE.match(line) and not _is_garbled_line(line)
            ]
            paragraphs = _paragraphs("\n".join(lines))
            if not paragraphs:
                continue
            emitted.extend(_emit_passages(paragraphs, f"leaf {page_index + 1}"))
        return emitted
    lines = [line for line in text.split("\n") if not _is_garbled_line(line)]
    return _emit_passages(_paragraphs("\n".join(lines)), "")


def segment_source(text: str, source: LibrarySource) -> List[Tuple[str, str]]:
    if source.format == "gutenberg":
        return segment_gutenberg(text)
    return segment_archive(text)


def build_index(directory: Optional[Path] = None,
                only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Segment downloaded sources into per-book JSONL passage indexes."""
    directory = directory or library_dir()
    wanted = set(only) if only else None
    report: Dict[str, Any] = {"books": {}, "passages": 0, "skipped": []}
    for source in load_catalog(directory):
        if wanted is not None and source.slug not in wanted:
            continue
        text_path = source_text_path(source.slug, directory)
        if not text_path.exists() or text_path.stat().st_size == 0:
            report["skipped"].append(source.slug)
            continue
        text = text_path.read_text(encoding="utf-8", errors="replace")
        passages = segment_source(text, source)
        destination = index_path(source.slug, directory)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            for locator, passage_text in passages:
                handle.write(json.dumps(
                    {"slug": source.slug, "locator": locator, "text": passage_text},
                    ensure_ascii=False) + "\n")
        report["books"][source.slug] = len(passages)
        report["passages"] += len(passages)
    return report


class LibraryIndex:
    """In-memory passage index over the segmented public-domain corpus."""

    def __init__(self, sources: Sequence[LibrarySource],
                 passages_by_slug: Dict[str, List[LibraryPassage]]):
        self.sources: List[LibrarySource] = list(sources)
        self._by_slug: Dict[str, LibrarySource] = {s.slug: s for s in self.sources}
        self._passages: List[LibraryPassage] = []
        self._lower: List[str] = []
        for source in self.sources:
            for passage in passages_by_slug.get(source.slug, []):
                self._passages.append(passage)
                self._lower.append(passage.text.lower())

    def __len__(self) -> int:
        return len(self._passages)

    @classmethod
    def from_directory(cls, directory: Optional[Path] = None) -> "LibraryIndex":
        directory = directory or library_dir()
        sources = load_catalog(directory)
        passages_by_slug: Dict[str, List[LibraryPassage]] = {}
        for source in sources:
            path = index_path(source.slug, directory)
            if not path.exists():
                continue
            passages: List[LibraryPassage] = []
            seq = 0
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = str(record.get("text", "")).strip()
                if not text:
                    continue
                passages.append(LibraryPassage(
                    book_slug=source.slug,
                    book_title=source.display_title,
                    citation=source.citation,
                    locator=str(record.get("locator", "")).strip() or f"passage {seq + 1}",
                    text=text,
                    seq=seq,
                ))
                seq += 1
            if passages:
                passages_by_slug[source.slug] = passages
        return cls(sources, passages_by_slug)

    def search(self, query: str, *, topic: str = "general", limit: int = DEFAULT_LIMIT,
               book: Optional[str] = None, min_score: float = DEFAULT_MIN_SCORE
               ) -> List[LibraryPassage]:
        tokens = sorted(set(_tokenize(query)))
        if not tokens or not self._passages:
            return []
        expanded = _expand_tokens(tokens)
        total = len(self._passages)
        document_frequency = {token: 0 for token in expanded}
        for text_lower in self._lower:
            for token in expanded:
                if token in text_lower:
                    document_frequency[token] += 1
        weights = {
            token: multiplier * (1.0 + math.log(total / max(document_frequency[token], 1)))
            for token, multiplier in expanded.items() if document_frequency[token]
        }
        if not weights:
            return []
        topic_categories = {c.lower() for c in TOPIC_CATEGORY_MAP.get(topic, [])}
        scored: List[Tuple[float, int, LibraryPassage]] = []
        for passage, text_lower in zip(self._passages, self._lower):
            if book and passage.book_slug != book:
                continue
            token_score = 0.0
            for token, weight in weights.items():
                count = text_lower.count(token)
                if count:
                    token_score += weight * (1.0 + 0.25 * min(count - 1, 3))
            if token_score <= 0:
                continue
            source = self._by_slug.get(passage.book_slug)
            if source and topic_categories:
                overlap = topic_categories.intersection(c.lower() for c in source.categories)
                token_score += 0.5 * min(len(overlap), 2)
            if token_score < min_score:
                continue
            scored.append((token_score, passage.seq, passage))
        scored.sort(key=lambda item: (-item[0], item[2].book_slug, item[1]))
        results: List[LibraryPassage] = []
        for score, _, passage in scored[:max(1, limit)]:
            results.append(LibraryPassage(
                book_slug=passage.book_slug,
                book_title=passage.book_title,
                citation=passage.citation,
                locator=passage.locator,
                text=passage.text,
                seq=passage.seq,
                score=round(score, 3),
            ))
        return results

    def stats(self) -> Dict[str, Any]:
        per_book: Dict[str, Dict[str, int]] = {}
        for passage, text_lower in zip(self._passages, self._lower):
            entry = per_book.setdefault(passage.book_slug, {"passages": 0, "chars": 0})
            entry["passages"] += 1
            entry["chars"] += len(text_lower)
        return {
            "books": len(self.sources),
            "indexed_books": len(per_book),
            "passages": len(self._passages),
            "chars": sum(entry["chars"] for entry in per_book.values()),
            "per_book": per_book,
        }


@lru_cache(maxsize=8)
def _cached_index(directory: str) -> LibraryIndex:
    return LibraryIndex.from_directory(Path(directory))


def get_library_index(directory: Optional[Path] = None) -> LibraryIndex:
    return _cached_index(str((directory or library_dir()).resolve()))


def search_library(query: str, *, topic: str = "general", limit: int = DEFAULT_LIMIT,
                   book: Optional[str] = None, directory: Optional[Path] = None,
                   min_score: float = DEFAULT_MIN_SCORE) -> List[LibraryPassage]:
    """Verbatim public-domain passages for a question (empty when not built)."""
    if not query or not query.strip():
        return []
    return get_library_index(directory).search(
        query, topic=topic, limit=limit, book=book, min_score=min_score)


def passage_line(passage: LibraryPassage, excerpt_chars: int = DEFAULT_EXCERPT_CHARS) -> str:
    excerpt = " ".join(passage.text.split())
    if len(excerpt) > excerpt_chars:
        cut = excerpt.rfind(" ", 0, excerpt_chars)
        if cut < excerpt_chars // 2:
            cut = excerpt_chars
        excerpt = excerpt[:cut].strip() + " ..."
    return f'- {passage.citation}, {passage.locator}: "{excerpt}"'


def library_reference_lines(passages: Iterable[LibraryPassage],
                            excerpt_chars: int = DEFAULT_EXCERPT_CHARS) -> List[str]:
    return [passage_line(passage, excerpt_chars) for passage in passages]
