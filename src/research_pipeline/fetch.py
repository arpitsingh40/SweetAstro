"""
Caption/metadata ingestion via yt-dlp (dev-only dependency).

Only captions and metadata are retrieved — never the video media itself
(``skip_download`` is always set). Every target is idempotent: an existing
record is skipped unless ``refresh=True``. Network failures are reported per
target and never abort a batch.
"""

from __future__ import annotations

import re
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import httpx

from .captions import parse_vtt
from .store import DESCRIPTION_LIMIT, VideoRecord, VideoStore

DEFAULT_LANGS: Tuple[str, ...] = ("en.*", "hi.*")

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

Extractor = Callable[[str, Path], Dict]


class ResearchFetchError(RuntimeError):
    """Raised when a target cannot be normalized, fetched or parsed."""


def normalize_target(target: str) -> str:
    value = (target or "").strip()
    if not value:
        raise ResearchFetchError("empty target")
    if _VIDEO_ID_RE.match(value):
        return f"https://www.youtube.com/watch?v={value}"
    if value.startswith(("http://", "https://")):
        return value
    raise ResearchFetchError(f"not a video URL or 11-character video id: {target!r}")


def video_id_from_url(url: str, info: Optional[Dict] = None) -> str:
    if info and info.get("id"):
        return str(info["id"])
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.endswith("youtu.be"):
        candidate = parsed.path.lstrip("/").split("/")[0]
        if _VIDEO_ID_RE.match(candidate):
            return candidate
    if parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
        candidate = parsed.path.split("/")[2]
        if _VIDEO_ID_RE.match(candidate):
            return candidate
    query = urllib.parse.parse_qs(parsed.query)
    candidate = (query.get("v") or [""])[0]
    if _VIDEO_ID_RE.match(candidate):
        return candidate
    raise ResearchFetchError(f"cannot determine video id from {url!r}")


def build_ytdlp_extractor(langs: Sequence[str] = DEFAULT_LANGS) -> Extractor:
    def extractor(url: str, outdir: Path) -> Dict:
        import yt_dlp

        options = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(langs),
            "subtitlesformat": "vtt",
            "outtmpl": str(outdir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 3,
            "socket_timeout": 30,
        }
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
            if isinstance(info, dict) and _choose_caption_file(
                    str(info.get("id") or ""), outdir, info) is not None:
                return info
        except Exception:
            pass
        plain_options = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "socket_timeout": 30,
        }
        with yt_dlp.YoutubeDL(plain_options) as downloader:
            info = downloader.extract_info(url, download=False)
        if not isinstance(info, dict):
            raise ResearchFetchError("yt-dlp returned no metadata")
        _download_caption_direct(info, outdir, langs)
        return info

    return extractor


def _caption_candidates(info: Dict, langs: Sequence[str]) -> List[Tuple[str, str, str]]:
    """(kind, lang, url) candidates ordered by language preference, manual first."""
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    ordered: List[Tuple[str, str, str]] = []
    for pattern in langs:
        try:
            matcher = re.compile(pattern)
        except re.error:
            continue
        for kind, tracks in (("manual", manual), ("auto", automatic)):
            for lang in sorted(tracks):
                if not matcher.fullmatch(lang):
                    continue
                for entry in tracks.get(lang) or []:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("ext", "vtt")) != "vtt":
                        continue
                    url = str(entry.get("url") or "")
                    if url:
                        ordered.append((kind, lang, url))
    return ordered


def _download_caption_direct(info: Dict, outdir: Path, langs: Sequence[str]) -> None:
    video_id = str(info.get("id") or "")
    candidates = _caption_candidates(info, langs)
    if not video_id or not candidates:
        return
    last_error = ""
    for _, lang, url in candidates:
        for attempt in range(3):
            try:
                response = httpx.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    timeout=30,
                    follow_redirects=True,
                )
                if response.status_code == 429:
                    last_error = "HTTP 429 (rate limited)"
                    time.sleep(2 + 4 * attempt)
                    continue
                response.raise_for_status()
                text = response.text
                if "WEBVTT" not in text[:200]:
                    last_error = "caption body was not WebVTT"
                    break
                (outdir / f"{video_id}.{lang}.vtt").write_text(text, encoding="utf-8")
                return
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(2 + 4 * attempt)
    raise ResearchFetchError(f"caption download failed ({last_error or 'no tracks'})")


def build_ytdlp_flat_extractor() -> Callable[[str, int], List[Tuple[str, str]]]:
    def extractor(channel_url: str, limit: int) -> List[Tuple[str, str]]:
        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(channel_url, download=False)
        entries = (info or {}).get("entries") or []
        videos: List[Tuple[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            video_id = str(entry.get("id") or "")
            if _VIDEO_ID_RE.match(video_id):
                videos.append((video_id, str(entry.get("title") or "")))
            if len(videos) >= limit:
                break
        return videos

    return extractor


Searcher = Callable[[str, int], List[Tuple[str, str, str]]]


def build_ytdlp_searcher() -> Searcher:
    def searcher(query: str, limit: int) -> List[Tuple[str, str, str]]:
        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(f"ytsearch{limit}:{query}", download=False)
        entries = (info or {}).get("entries") or []
        results: List[Tuple[str, str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            video_id = str(entry.get("id") or "")
            if not _VIDEO_ID_RE.match(video_id):
                continue
            results.append((
                video_id,
                str(entry.get("title") or ""),
                str(entry.get("channel") or entry.get("uploader") or ""),
            ))
        return results

    return searcher


def search_videos(query: str, limit: int = 8,
                  searcher: Optional[Searcher] = None) -> List[Tuple[str, str, str]]:
    """YouTube search for (video_id, title, channel) candidates."""
    if not (query or "").strip():
        raise ResearchFetchError("empty search query")
    searcher = searcher or build_ytdlp_searcher()
    return searcher(query, limit)


def _choose_caption_file(video_id: str, outdir: Path,
                         info: Dict) -> Optional[Tuple[Path, str, str]]:
    manual = set((info.get("subtitles") or {}).keys())
    automatic = set((info.get("automatic_captions") or {}).keys())
    original = str(info.get("language") or "")
    candidates: List[Tuple[Path, str]] = []
    for path in sorted(outdir.glob(f"{video_id}.*.vtt")):
        lang = path.name[len(video_id) + 1:-len(".vtt")]
        candidates.append((path, lang))
    if not candidates:
        return None

    def rank(item: Tuple[Path, str]) -> Tuple[int, int, str]:
        _, lang = item
        base = lang.split("-")[0]
        if lang in manual:
            return (0, 0 if base == "en" else 1, lang)
        if lang in automatic or lang not in manual:
            if base == "en":
                return (1, 0 if lang == "en" else 1, lang)
            if original and base == original.split("-")[0]:
                return (1, 2, lang)
            return (2, 0, lang)
        return (3, 0, lang)

    path, lang = sorted(candidates, key=rank)[0]
    base = lang.split("-")[0]
    if lang in manual:
        kind = "manual"
    elif base == "en" or (original and base == original.split("-")[0]):
        kind = "auto"
    else:
        kind = "auto-translated"
    return path, lang, kind


def _record_from_info(info: Dict, url: str, caption_kind: str, caption_lang: str) -> VideoRecord:
    return VideoRecord(
        video_id=video_id_from_url(url, info),
        title=str(info.get("title") or ""),
        channel=str(info.get("channel") or info.get("uploader") or ""),
        channel_id=str(info.get("channel_id") or ""),
        url=str(info.get("webpage_url") or url),
        upload_date=str(info.get("upload_date") or ""),
        duration=info.get("duration"),
        view_count=info.get("view_count"),
        caption_kind=caption_kind,
        caption_lang=caption_lang,
        description=str(info.get("description") or "")[:DESCRIPTION_LIMIT],
    )


def fetch_videos(targets: Sequence[str], store: Optional[VideoStore] = None,
                 extractor: Optional[Extractor] = None, refresh: bool = False,
                 langs: Sequence[str] = DEFAULT_LANGS) -> List[str]:
    store = store or VideoStore()
    extractor = extractor or build_ytdlp_extractor(langs)
    messages: List[str] = []
    for target in targets:
        try:
            url = normalize_target(target)
        except ResearchFetchError as exc:
            messages.append(f"error {target}: {exc}")
            continue
        try:
            cached_id = video_id_from_url(url)
        except ResearchFetchError:
            cached_id = ""
        if cached_id and store.exists(cached_id) and not refresh:
            messages.append(f"skip {cached_id} (already stored; use --refresh to redo)")
            continue
        with tempfile.TemporaryDirectory(prefix="sweetastro-video-") as tmp:
            outdir = Path(tmp)
            try:
                info = extractor(url, outdir)
            except Exception as exc:
                messages.append(f"error {target}: {type(exc).__name__}: {exc}")
                continue
            try:
                video_id = video_id_from_url(url, info)
            except ResearchFetchError as exc:
                messages.append(f"error {target}: {exc}")
                continue
            chosen = _choose_caption_file(video_id, outdir, info)
            if store.exists(video_id) and not refresh:
                messages.append(f"skip {video_id} (already stored; use --refresh to redo)")
                continue
            if chosen is None:
                record = _record_from_info(info, url, "none", "")
                store.save(record, [], None, "")
                messages.append(f"stored {video_id} metadata (no captions available)")
                continue
            vtt_path, lang, kind = chosen
            vtt_text = vtt_path.read_text(encoding="utf-8", errors="replace")
            try:
                cues = parse_vtt(vtt_text)
            except Exception as exc:
                messages.append(f"error {video_id}: caption parse failed: {exc}")
                continue
            record = _record_from_info(info, url, kind, lang)
            vtt_name = vtt_path.name
            store.save(record, cues, vtt_text, vtt_name)
            messages.append(
                f"stored {video_id} ({kind} captions {lang}, {len(cues)} cues) — "
                f"{record.title[:70]}")
    return messages


def fetch_channel(channel_url: str, limit: int = 10,
                  store: Optional[VideoStore] = None,
                  extractor: Optional[Extractor] = None,
                  flat_extractor: Optional[Callable[[str, int], List[Tuple[str, str]]]] = None,
                  refresh: bool = False,
                  langs: Sequence[str] = DEFAULT_LANGS) -> List[str]:
    flat_extractor = flat_extractor or build_ytdlp_flat_extractor()
    try:
        videos = flat_extractor(channel_url, limit)
    except Exception as exc:
        return [f"error {channel_url}: {type(exc).__name__}: {exc}"]
    if not videos:
        return [f"no videos listed for {channel_url}"]
    messages = [f"channel {channel_url}: {len(videos)} video(s) selected"]
    targets = [f"https://www.youtube.com/watch?v={video_id}" for video_id, _ in videos]
    messages.extend(fetch_videos(targets, store=store, extractor=extractor,
                                 refresh=refresh, langs=langs))
    return messages
