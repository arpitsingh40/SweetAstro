"""Public-domain library tests: catalog integrity, segmentation, retrieval, citations."""

import json
from pathlib import Path

import pytest

from SweetAstro.src.knowledge.library import (
    LibraryIndex, library_reference_lines, load_catalog, search_library,
    segment_archive, segment_gutenberg, validate_catalog,
)

REAL_CATALOG = Path(__file__).resolve().parents[1] / "data" / "library"

GUTENBERG_FIXTURE = """The Project Gutenberg eBook of Test Classic
*** START OF THE PROJECT GUTENBERG EBOOK TEST CLASSIC ***

CHAPTER I.

Saturn in the seventh house delays marriage and makes the native
cautious. Venus, when well placed, softens the result.

A second paragraph explaining the same matter further, with enough
words to form a meaningful passage for retrieval.

CHAPTER II.

Jupiter transits the tenth house and protects the career of the
native when the dasha lord is friendly.

*** END OF THE PROJECT GUTENBERG EBOOK TEST CLASSIC ***
"""

ARCHIVE_FIXTURE = (
    "The Testament of Saturn\n\n"
    "Saturn in the ascendant gives a lean body and a serious mind.\n\n"
    "\f"
    "The native suffers when Saturn transits the moon.\n\n"
    "5r^T ^fi\u005ekr 7&*#@ ;:| 9\u00a7\n\n"
    "\f"
    "Jupiter protects the house it occupies by aspect.\n\n"
    "\f"
    "Venus grants comfort and artistic taste to the native.\n"
)

MINI_CATALOG = {
    "version": 1,
    "license_note": "fixture",
    "sources": [
        {
            "slug": "test_classic",
            "title": "Test Classic",
            "short_title": "Test Classic",
            "author": "Anonymous",
            "translator": "A. Translator",
            "edition": "Fixture Press",
            "year": "1899",
            "language": "en",
            "format": "gutenberg",
            "remote_id": "99999",
            "rights": "Public domain in the USA",
            "pd_basis": "Fixture published before 1930.",
            "categories": ["promise", "stability"],
        },
        {
            "slug": "test_archive",
            "title": "Test Archive Classic",
            "short_title": "Test Archive",
            "author": "Anonymous",
            "translator": "",
            "edition": "Scan Press",
            "year": "1875",
            "language": "en",
            "format": "archive",
            "remote_id": "fixture-id",
            "rights": "Public domain",
            "pd_basis": "Fixture published before 1930.",
            "categories": ["timing_transit"],
        },
    ],
}


def _write_mini_library(root: Path) -> Path:
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "catalog.json").write_text(json.dumps(MINI_CATALOG), encoding="utf-8")
    (root / "sources" / "test_classic.txt").write_text(GUTENBERG_FIXTURE, encoding="utf-8")
    (root / "sources" / "test_archive.txt").write_text(ARCHIVE_FIXTURE, encoding="utf-8")
    return root


def test_catalog_declares_public_domain_sources():
    sources = load_catalog(REAL_CATALOG)
    assert len(sources) >= 8
    slugs = [s.slug for s in sources]
    assert len(slugs) == len(set(slugs))
    for source in sources:
        assert source.format in ("gutenberg", "archive")
        assert source.remote_id
        assert source.rights
        assert source.pd_basis
        assert source.language
    assert validate_catalog(REAL_CATALOG) == []


def test_validate_catalog_flags_missing_metadata(tmp_path):
    bad = {"version": 1, "sources": [{"slug": "x", "title": "X"}]}
    (tmp_path / "catalog.json").write_text(json.dumps(bad), encoding="utf-8")
    problems = validate_catalog(tmp_path)
    assert any("format" in p for p in problems)
    assert any("rights" in p for p in problems)
    assert any("public-domain basis" in p for p in problems)


def test_gutenberg_segmentation_strips_boilerplate_and_tracks_chapters():
    passages = segment_gutenberg(GUTENBERG_FIXTURE)
    assert passages
    locators = [locator for locator, _ in passages]
    assert any(locator.startswith("ch. I,") for locator in locators)
    assert any(locator.startswith("ch. II,") for locator in locators)
    joined = " ".join(text for _, text in passages)
    assert "PROJECT GUTENBERG" not in joined
    assert "seventh house" in joined


def test_archive_segmentation_uses_leaf_locators_and_drops_garble():
    passages = segment_archive(ARCHIVE_FIXTURE)
    assert passages
    assert all(locator.startswith("leaf ") for locator, _ in passages)
    joined = " ".join(text for _, text in passages)
    assert "Saturn in the ascendant" in joined
    assert "^fi" not in joined


def test_build_index_and_search_roundtrip(tmp_path):
    from SweetAstro.src.knowledge.library import build_index

    _write_mini_library(tmp_path)
    report = build_index(directory=tmp_path)
    assert report["books"] == {"test_classic": report["books"]["test_classic"],
                               "test_archive": report["books"]["test_archive"]}

    index = LibraryIndex.from_directory(tmp_path)
    assert len(index) == report["passages"]

    hits = index.search("saturn seventh house marriage", topic="marriage", limit=3)
    assert hits
    top = hits[0]
    assert top.citation == "Test Classic (trans. A. Translator, 1899)"
    assert top.locator.startswith("ch. I,")
    assert "Saturn" in top.text

    again = index.search("saturn seventh house marriage", topic="marriage", limit=3)
    assert [p.locator for p in hits] == [p.locator for p in again]


def test_search_library_respects_book_filter_and_min_score(tmp_path):
    from SweetAstro.src.knowledge.library import build_index

    _write_mini_library(tmp_path)
    build_index(directory=tmp_path)
    archive_hits = search_library("saturn moon transit", directory=tmp_path, book="test_archive")
    assert archive_hits
    assert all(hit.book_slug == "test_archive" for hit in archive_hits)

    weak = search_library("zorblax quasar", directory=tmp_path, min_score=1.5)
    assert weak == []


def test_missing_index_is_safe(tmp_path):
    assert search_library("saturn", directory=tmp_path) == []
    assert LibraryIndex.from_directory(tmp_path).stats()["passages"] == 0
    assert search_library("", directory=tmp_path) == []


def test_reference_lines_are_citable_and_bounded(tmp_path):
    from SweetAstro.src.knowledge.library import build_index

    _write_mini_library(tmp_path)
    build_index(directory=tmp_path)
    passages = search_library("saturn seventh house", directory=tmp_path, limit=2)
    lines = library_reference_lines(passages, excerpt_chars=80)
    assert len(lines) == len(passages)
    for line in lines:
        assert line.startswith("- ")
        assert "(trans." in line or "1875" in line
        assert len(line) < 400
        assert "\n" not in line


def test_real_corpus_retrieval_when_index_built():
    index = LibraryIndex.from_directory(REAL_CATALOG)
    if len(index) == 0:
        return
    hits = search_library("saturn transit moon", limit=3)
    assert hits
    assert all(hit.citation and hit.locator and hit.text for hit in hits)


def test_chat_payload_includes_library_passages_when_built(monkeypatch):
    if len(LibraryIndex.from_directory(REAL_CATALOG)) == 0:
        pytest.skip("public-domain index not built")

    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    class _FakeClient:
        def complete_json(self, messages, **kwargs):
            return {
                "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
                "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
                "question": "Saturn marriage timing?", "topic": "marriage",
            }

        def stream(self, messages, **kwargs):
            yield {"type": "content", "text": "ok"}

    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (26.9124, 75.7873, "Geocoded (mock)."),
    )
    orch = ChatOrchestrator(client=_FakeClient(), store=SessionStore())
    list(orch.handle_message(
        "src-lib", "Saturn marriage timing. Born 15 May 1995 14:30 in Jaipur."))
    session = orch.store.get("src-lib")
    assert session is not None and session.last_result is not None
    payload = orch._build_chart_payload(session, session.last_result)
    assert "public-domain library" in payload
    assert "Source references" in payload
