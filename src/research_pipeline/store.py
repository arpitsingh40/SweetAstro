"""
Local store for ingested video metadata and caption cues.

Layout under ``data/research/videos/``:

    <video_id>.json        distilled metadata (title, channel, caption kind, ...)
    <video_id>.cues.jsonl  parsed caption cues (start, end, text)
    <video_id>.<lang>.vtt  original caption file, kept for audit

Everything stays local; nothing here is ever served by the answer path.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .captions import Cue, cues_from_dicts, cues_to_dicts

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DIR = _PROJECT_ROOT / "data" / "research" / "videos"

DESCRIPTION_LIMIT = 4000


def video_store_dir() -> Path:
    override = os.environ.get("SWEETASTRO_VIDEO_RESEARCH_DIR")
    return Path(override) if override else DEFAULT_DIR


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class VideoRecord:
    video_id: str
    title: str = ""
    channel: str = ""
    channel_id: str = ""
    url: str = ""
    upload_date: str = ""
    duration: Optional[float] = None
    view_count: Optional[int] = None
    caption_kind: str = "none"
    caption_lang: str = ""
    description: str = ""
    vtt_file: str = ""
    fetched_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel": self.channel,
            "channel_id": self.channel_id,
            "url": self.url or f"https://www.youtube.com/watch?v={self.video_id}",
            "upload_date": self.upload_date,
            "duration": self.duration,
            "view_count": self.view_count,
            "caption_kind": self.caption_kind,
            "caption_lang": self.caption_lang,
            "description": self.description,
            "vtt_file": self.vtt_file,
            "fetched_utc": self.fetched_utc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoRecord":
        return cls(
            video_id=str(data.get("video_id", "")),
            title=str(data.get("title", "")),
            channel=str(data.get("channel", "")),
            channel_id=str(data.get("channel_id", "")),
            url=str(data.get("url", "")),
            upload_date=str(data.get("upload_date", "")),
            duration=data.get("duration"),
            view_count=data.get("view_count"),
            caption_kind=str(data.get("caption_kind", "none")),
            caption_lang=str(data.get("caption_lang", "")),
            description=str(data.get("description", "")),
            vtt_file=str(data.get("vtt_file", "")),
            fetched_utc=str(data.get("fetched_utc", "")),
        )

    @property
    def watch_url(self) -> str:
        return self.url or f"https://www.youtube.com/watch?v={self.video_id}"

    def deep_link(self, seconds: float) -> str:
        return f"{self.watch_url}&t={int(max(0, seconds))}s"


class VideoStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else video_store_dir()

    def metadata_path(self, video_id: str) -> Path:
        return self.root / f"{video_id}.json"

    def cues_path(self, video_id: str) -> Path:
        return self.root / f"{video_id}.cues.jsonl"

    def exists(self, video_id: str) -> bool:
        return self.metadata_path(video_id).exists() and self.cues_path(video_id).exists()

    def save(self, record: VideoRecord, cues: Iterable[Cue],
             vtt_text: Optional[str] = None, vtt_name: str = "") -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if vtt_text and vtt_name:
            (self.root / vtt_name).write_text(vtt_text, encoding="utf-8")
            record.vtt_file = vtt_name
        self.metadata_path(record.video_id).write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        with open(self.cues_path(record.video_id), "w", encoding="utf-8") as handle:
            for entry in cues_to_dicts(cues):
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_record(self, video_id: str) -> Optional[VideoRecord]:
        path = self.metadata_path(video_id)
        if not path.exists():
            return None
        try:
            return VideoRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError):
            return None

    def load_cues(self, video_id: str) -> List[Cue]:
        path = self.cues_path(video_id)
        if not path.exists():
            return []
        records: List[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return cues_from_dicts(records)

    def list_records(self) -> List[VideoRecord]:
        if not self.root.exists():
            return []
        records: List[VideoRecord] = []
        for path in sorted(self.root.glob("*.json")):
            if path.name.endswith(".cues.jsonl"):
                continue
            record = self.load_record(path.stem)
            if record:
                records.append(record)
        return records

    def status(self) -> Dict[str, Any]:
        records = self.list_records()
        with_captions = sum(1 for r in records if r.caption_kind not in ("", "none"))
        return {
            "root": str(self.root),
            "videos": len(records),
            "with_captions": with_captions,
            "auto": sum(1 for r in records if r.caption_kind == "auto"),
            "manual": sum(1 for r in records if r.caption_kind == "manual"),
            "channels": sorted({r.channel for r in records if r.channel}),
        }
