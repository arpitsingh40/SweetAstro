"""
Video research CLI — ingest YouTube metadata/captions for method curation.

Dev-only tooling: captions and metadata are stored locally under
data/research/videos/ for research; nothing here is served by the engine.
Only curated method packs (data/methods/) may reach answers, always labelled
as modern and unvalidated.

Usage:
    python video_research.py fetch VIDEO [VIDEO ...] [--refresh]
    python video_research.py fetch-channel URL [--limit 10] [--refresh]
    python video_research.py list
    python video_research.py show VIDEO_ID
    python video_research.py quote VIDEO_ID 12:34 13:20 [--chars 800]
    python video_research.py extract VIDEO_ID [--single-pass]
    python video_research.py report [--video VIDEO_ID] [--verdict quarantine]
    python video_research.py draft VC-xxxxxxxxxx [--target marriage]
    python video_research.py pack VC-xxxxxxxxxx --slug my-method [--topic career]
    python video_research.py search "QUERY" [--limit 8] [--ingest]
    python video_research.py research --topic marriage --reason "Venus lord of H7 is Debilitated in H6"
    python video_research.py status
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from SweetAstro.src.research_pipeline.captions import (  # noqa: E402
    CaptionError, format_timestamp, parse_timestamp, quote_range,
)
from SweetAstro.src.research_pipeline.extract import (  # noqa: E402
    dual_pass_extract, extract_claims, load_candidates, save_candidates,
)
from SweetAstro.src.research_pipeline.deep_search import deep_search  # noqa: E402
from SweetAstro.src.research_pipeline.fetch import (  # noqa: E402
    ResearchFetchError, fetch_channel, fetch_videos, search_videos,
)
from SweetAstro.src.research_pipeline.gate import (  # noqa: E402
    evaluate_candidates, format_gate_results,
)
from SweetAstro.src.research_pipeline.pack_writer import (  # noqa: E402
    PackWriterError, write_pack_skeleton,
)
from SweetAstro.src.research_pipeline.store import VideoStore  # noqa: E402


def _run_fetch(args) -> int:
    messages = fetch_videos(args.videos, refresh=args.refresh, langs=tuple(args.langs))
    for message in messages:
        print(message)
    return 0


def _run_fetch_channel(args) -> int:
    messages = fetch_channel(args.url, limit=args.limit, refresh=args.refresh,
                             langs=tuple(args.langs))
    for message in messages:
        print(message)
    return 0


def _run_list(_args) -> int:
    records = VideoStore().list_records()
    if not records:
        print("No videos ingested yet — run: python video_research.py fetch <url>")
        return 0
    for record in records:
        flag = "" if record.caption_kind not in ("", "none") else "  [no captions]"
        print(f"  {record.video_id}  {record.caption_kind or 'none':<15} "
              f"{(record.channel or '?')[:28]:<28}  {record.title[:60]}{flag}")
    return 0


def _run_show(args) -> int:
    store = VideoStore()
    record = store.load_record(args.video_id)
    if record is None:
        print(f"Unknown video id: {args.video_id}")
        return 2
    cues = store.load_cues(args.video_id)
    print(f"{record.title}")
    print(f"  channel: {record.channel} ({record.channel_id})")
    print(f"  url: {record.watch_url}")
    print(f"  uploaded: {record.upload_date}  duration: {record.duration}s  "
          f"views: {record.view_count}")
    print(f"  captions: {record.caption_kind} {record.caption_lang}  "
          f"cues: {len(cues)}")
    return 0


def _run_quote(args) -> int:
    store = VideoStore()
    record = store.load_record(args.video_id)
    if record is None:
        print(f"Unknown video id: {args.video_id}")
        return 2
    try:
        start = parse_timestamp(args.start)
        end = parse_timestamp(args.end) if args.end else start
    except CaptionError as exc:
        print(f"Bad timestamp: {exc}")
        return 2
    cues = store.load_cues(args.video_id)
    text = quote_range(cues, start, end, max_chars=args.chars)
    if not text:
        print("No captions in that range.")
        return 0
    print(f"\"{text}\"")
    print(f"  {record.deep_link(start)}")
    return 0


def _run_status(_args) -> int:
    status = VideoStore().status()
    print(f"Store: {status['root']}")
    print(f"Videos: {status['videos']} — with captions: {status['with_captions']} "
          f"(manual {status['manual']}, auto {status['auto']})")
    if status["channels"]:
        print("Channels: " + ", ".join(status["channels"]))
    return 0


def _run_extract(args) -> int:
    from SweetAstro.src.chat.client import DeepSeekClient

    store = VideoStore()
    client = DeepSeekClient()
    total = 0
    for video_id in args.videos:
        record = store.load_record(video_id)
        if record is None:
            print(f"skip {video_id}: unknown video id")
            continue
        cues = store.load_cues(video_id)
        if not cues:
            print(f"skip {video_id}: no captions stored")
            continue
        try:
            if args.single_pass:
                candidates = extract_claims(record, cues, client,
                                            max_chunks=args.max_chunks,
                                            max_claims=args.max_claims)
            else:
                candidates = dual_pass_extract(record, cues, client,
                                               max_chunks=args.max_chunks,
                                               max_claims=args.max_claims)
        except Exception as exc:
            print(f"error {video_id}: {type(exc).__name__}: {exc}")
            continue
        added, skipped = save_candidates(candidates)
        total += added
        print(f"{video_id}: {len(candidates)} validated claim(s), "
              f"{added} new, {skipped} already known")
    print(f"Total new candidate claims: {total}")
    return 0


def _run_report(args) -> int:
    candidates = load_candidates()
    if args.video:
        candidates = [c for c in candidates if c.video_id == args.video]
    if not candidates:
        print("No candidate claims stored — run: python video_research.py extract <video_id>")
        return 0
    store = VideoStore()
    records = {record.video_id: record for record in store.list_records()}
    results = evaluate_candidates(candidates, records=records)
    if args.verdict:
        results = [r for r in results if r.verdict == args.verdict]
    for line in format_gate_results(results, records):
        print(line)
    print(f"{len(results)} candidate(s) shown.")
    return 0


def _run_draft(args) -> int:
    from SweetAstro.src.knowledge.intake import add_draft

    candidates = {c.candidate_id: c for c in load_candidates()}
    candidate = candidates.get(args.candidate_id)
    if candidate is None:
        print(f"Unknown candidate id: {args.candidate_id}")
        return 2
    store = VideoStore()
    record = store.load_record(candidate.video_id)
    title = record.title if record else f"YouTube video {candidate.video_id}"
    channel = record.channel if record else "YouTube"
    caption_kind = record.caption_kind if record else "auto"
    notes = f"quote: {candidate.quote}"
    if candidate.formula:
        notes += f" | formula: {candidate.formula}"
    if candidate.steps:
        notes += " | steps: " + "; ".join(candidate.steps)
    draft = add_draft(
        candidate.claim,
        args.target or candidate.target,
        title,
        f"{channel} (YouTube, {caption_kind} captions)",
        candidate.locator,
        notes=notes,
        source_class="web",
        url=candidate.deep_link(record),
    )
    print(f"Quarantined {draft.claim_id} (status: draft — not servable).")
    print(f"  citation: {draft.citation()}")
    return 0


def _run_pack(args) -> int:
    candidates = {c.candidate_id: c for c in load_candidates()}
    candidate = candidates.get(args.candidate_id)
    if candidate is None:
        print(f"Unknown candidate id: {args.candidate_id}")
        return 2
    record = VideoStore().load_record(candidate.video_id)
    path = write_pack_skeleton(candidate, record, args.slug, topic=args.topic)
    print(f"Wrote disabled pack skeleton: {path}")
    print("Next: fill in the deterministic computation, add tests, then set \"enabled\": true.")
    return 0


def _run_search(args) -> int:
    results = search_videos(args.query, limit=args.limit)
    if not results:
        print("No videos found.")
        return 0
    for video_id, title, channel in results:
        print(f"  {video_id}  {channel[:30]:<30}  {title[:70]}")
    if args.ingest:
        targets = [f"https://www.youtube.com/watch?v={video_id}"
                   for video_id, _, _ in results]
        for message in fetch_videos(targets):
            print(f"  ingest: {message}")
    return 0


def _run_research(args) -> int:
    outcome = deep_search(args.topic, args.reason, limit=args.limit,
                          max_chunks=args.max_chunks, max_claims=args.max_claims)
    for line in outcome.summary_lines():
        print(line)
    matched = outcome.matched_remedies
    if matched:
        print("")
        print("=== reason-matched remedies and causes ===")
        store = VideoStore()
        records = {record.video_id: record for record in store.list_records()}
        for line in format_gate_results(matched, records):
            print(line)
    print("")
    print("Next steps: `report` for all candidates; `draft VC-...` to quarantine; "
          "`pack VC-... --slug ...` for a disabled pack.")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="SweetAstro video research pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="ingest one or more videos")
    fetch.add_argument("videos", nargs="+")
    fetch.add_argument("--refresh", action="store_true",
                       help="re-ingest even when already stored")
    fetch.add_argument("--lang", dest="langs", action="append",
                       default=["en.*", "hi.*"],
                       help="caption language pattern (repeatable)")

    channel = sub.add_parser("fetch-channel", help="ingest the latest videos of a channel")
    channel.add_argument("url")
    channel.add_argument("--limit", type=int, default=10)
    channel.add_argument("--refresh", action="store_true")
    channel.add_argument("--lang", dest="langs", action="append",
                         default=["en.*", "hi.*"])

    sub.add_parser("list", help="list stored videos")

    show = sub.add_parser("show", help="show one stored video")
    show.add_argument("video_id")

    quote = sub.add_parser("quote", help="print a timestamped caption excerpt")
    quote.add_argument("video_id")
    quote.add_argument("start", help="start timestamp (HH:MM:SS, MM:SS or seconds)")
    quote.add_argument("end", nargs="?", default="")
    quote.add_argument("--chars", type=int, default=1200)

    sub.add_parser("status", help="store summary")

    extract = sub.add_parser("extract", help="extract candidate claims from stored transcripts")
    extract.add_argument("videos", nargs="+")
    extract.add_argument("--max-chunks", dest="max_chunks", type=int, default=3)
    extract.add_argument("--max-claims", dest="max_claims", type=int, default=8)
    extract.add_argument("--single-pass", action="store_true",
                         help="one extraction pass (default: dual-pass self-consistency)")

    report = sub.add_parser("report", help="gate + evidence report for candidate claims")
    report.add_argument("--video", help="limit to one video id")
    report.add_argument("--verdict",
                        choices=("classical_candidate", "modern_candidate", "quarantine"))

    draft = sub.add_parser("draft", help="push a candidate claim into the intake quarantine")
    draft.add_argument("candidate_id")
    draft.add_argument("--target", help="override the engine target")

    pack = sub.add_parser("pack", help="write a disabled method-pack skeleton from a candidate")
    pack.add_argument("candidate_id")
    pack.add_argument("--slug", required=True)
    pack.add_argument("--topic", help="topic key for the pack (default: candidate target)")

    search = sub.add_parser("search", help="YouTube search for research candidates")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--ingest", action="store_true",
                        help="also fetch metadata + captions for every hit")

    research = sub.add_parser(
        "research",
        help="deep search: exact unfavourable reason -> reasons + remedies report")
    research.add_argument("--topic", required=True)
    research.add_argument("--reason", required=True,
                          help="engine limiting reason, e.g. 'Venus lord of H7 is Debilitated in H6'")
    research.add_argument("--limit", type=int, default=5)
    research.add_argument("--max-chunks", dest="max_chunks", type=int, default=2)
    research.add_argument("--max-claims", dest="max_claims", type=int, default=6)

    args = parser.parse_args()
    try:
        if args.command == "fetch":
            return _run_fetch(args)
        if args.command == "fetch-channel":
            return _run_fetch_channel(args)
        if args.command == "list":
            return _run_list(args)
        if args.command == "show":
            return _run_show(args)
        if args.command == "quote":
            return _run_quote(args)
        if args.command == "status":
            return _run_status(args)
        if args.command == "extract":
            return _run_extract(args)
        if args.command == "report":
            return _run_report(args)
        if args.command == "draft":
            return _run_draft(args)
        if args.command == "pack":
            return _run_pack(args)
        if args.command == "search":
            return _run_search(args)
        if args.command == "research":
            return _run_research(args)
    except (ResearchFetchError, CaptionError, PackWriterError) as exc:
        print(f"REFUSED: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
