"""
Public-domain library CLI — fetch, index, search and audit the book corpus.

Workflow:
    python library.py fetch            download every missing source text
    python library.py build            segment sources into passage indexes
    python library.py search "..."     deterministic passage retrieval
    python library.py stats            per-book passage/character counts
    python library.py verify           catalog integrity + index coverage

The catalog (data/library/catalog.json) records each volume's public-domain
basis; only editions with a recorded basis are admitted. Retrieval is local,
deterministic and offline.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from SweetAstro.src.knowledge.library import (  # noqa: E402
    LibraryError, build_index, fetch_sources, get_library_index, load_catalog,
    passage_line, search_library, source_text_path, validate_catalog,
)


def _run_fetch(args) -> int:
    messages = fetch_sources(only=args.only)
    for message in messages:
        print(message)
    if not messages:
        print("Nothing to do (catalog empty).")
    return 0


def _run_build(args) -> int:
    report = build_index(only=args.only)
    for slug, count in sorted(report["books"].items()):
        print(f"  {slug}: {count} passages")
    print(f"Indexed {report['passages']} passages across "
          f"{len(report['books'])} book(s).")
    if report["skipped"]:
        print("Skipped (source text missing — run `python library.py fetch`): "
              + ", ".join(sorted(report["skipped"])))
    return 0


def _run_search(args) -> int:
    passages = search_library(args.query, topic=args.topic, limit=args.limit,
                              book=args.book, min_score=args.min_score)
    if not passages:
        print("No passage matched (index empty, not built, or query too weak).")
        return 0
    for passage in passages:
        print(f"  [{passage.score:>4}] {passage.citation} — {passage.locator}")
        print(f"        {passage_line(passage, excerpt_chars=args.excerpt)}")
    return 0


def _run_stats(_args) -> int:
    index = get_library_index()
    stats = index.stats()
    print(f"Catalog books: {stats['books']} — indexed: {stats['indexed_books']}")
    print(f"Passages: {stats['passages']} — characters: {stats['chars']}")
    for slug in sorted(stats["per_book"]):
        entry = stats["per_book"][slug]
        print(f"  {slug}: {entry['passages']} passages, {entry['chars']} chars")
    return 0


def _run_verify(_args) -> int:
    problems = validate_catalog()
    catalog = load_catalog()
    missing_sources = [s.slug for s in catalog
                       if not source_text_path(s.slug).exists()]
    index = get_library_index()
    stats = index.stats()
    print(f"Catalog sources: {len(catalog)}")
    print(f"Sources downloaded: {len(catalog) - len(missing_sources)}")
    print(f"Indexed books: {stats['indexed_books']} — passages: {stats['passages']}")
    if missing_sources:
        print("Missing source text (run fetch): " + ", ".join(sorted(missing_sources)))
    if problems:
        print("CATALOG PROBLEMS:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("Catalog OK: every source records a public-domain basis and a fetch target.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SweetAstro public-domain library")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="download missing source texts")
    fetch.add_argument("--only", action="append", help="limit to slug (repeatable)")

    build = sub.add_parser("build", help="segment sources into passage indexes")
    build.add_argument("--only", action="append", help="limit to slug (repeatable)")

    search = sub.add_parser("search", help="search the passage index")
    search.add_argument("query")
    search.add_argument("--topic", default="general")
    search.add_argument("--book", help="restrict to a book slug")
    search.add_argument("--limit", type=int, default=4)
    search.add_argument("--min-score", dest="min_score", type=float, default=1.5)
    search.add_argument("--excerpt", type=int, default=280)

    sub.add_parser("stats", help="per-book passage/character counts")
    sub.add_parser("verify", help="catalog integrity and index coverage")

    args = parser.parse_args()
    try:
        if args.command == "fetch":
            return _run_fetch(args)
        if args.command == "build":
            return _run_build(args)
        if args.command == "search":
            return _run_search(args)
        if args.command == "stats":
            return _run_stats(args)
        if args.command == "verify":
            return _run_verify(args)
    except LibraryError as exc:
        print(f"REFUSED: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
