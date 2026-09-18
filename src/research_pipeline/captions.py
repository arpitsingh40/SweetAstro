"""
WebVTT caption parsing for research transcripts.

Captions are stored as ordered cues with numeric start/end seconds so that
claims can cite an exact timestamped locator (``12:34-13:20``) and a human can
verify a quote against the video in one click. Auto-captions repeat rolling
lines; consecutive duplicate text is collapsed. Markup tags are stripped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

_TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})(?P<ms>\.\d{1,3})?"
)
_TAG_RE = re.compile(r"<[^>]+>")


class CaptionError(ValueError):
    """Raised when a caption file cannot be parsed."""


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "text": self.text}


def parse_timestamp(value: str) -> float:
    """Parse ``HH:MM:SS(.mmm)`` or ``MM:SS`` into seconds."""
    text = str(value).strip()
    if text.isdigit():
        return float(text)
    if text.count(":") == 1:
        text = "00:" + text
    match = _TIMESTAMP_RE.search(text)
    if not match:
        raise CaptionError(f"Unparseable caption timestamp: {value!r}")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    fraction = float(match.group("ms") or 0.0)
    return hours * 3600 + minutes * 60 + seconds + fraction


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _clean_line(line: str) -> str:
    line = _TAG_RE.sub("", line)
    return " ".join(line.split())


def parse_vtt(text: str) -> List[Cue]:
    """Parse WebVTT text into de-duplicated cues."""
    if not text or "WEBVTT" not in text[:200]:
        raise CaptionError("Not a WebVTT caption document.")
    cues: List[Cue] = []
    block: List[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if line == "":
            _flush_block(block, cues)
            block = []
            continue
        block.append(line)
    _flush_block(block, cues)
    return cues


def _flush_block(block: Sequence[str], cues: List[Cue]) -> None:
    if not block or block[0].startswith(("NOTE", "STYLE", "WEBVTT")):
        return
    timing: Optional[str] = None
    text_lines: List[str] = []
    for line in block:
        if "-->" in line:
            timing = line
            continue
        if timing is not None:
            text_lines.append(_clean_line(line))
    if timing is None:
        return
    left, _, right = timing.partition("-->")
    text = " ".join(part for part in text_lines if part).strip()
    if not text:
        return
    if cues:
        previous = cues[-1]
        if previous.text == text:
            return
        if text.startswith(previous.text):
            cues[-1] = Cue(start=previous.start, end=previous.end, text=text)
            return
        if previous.text.startswith(text):
            return
    end_field = right.strip().split(" ")
    try:
        start = parse_timestamp(left)
        end = parse_timestamp(end_field[0]) if end_field and end_field[0] else start
    except CaptionError:
        return
    cues.append(Cue(start=start, end=end, text=text))


def quote_range(cues: Iterable[Cue], start: float, end: Optional[float] = None,
                max_chars: int = 1200) -> str:
    """Verbatim text of the cues overlapping [start, end], single-spaced."""
    if end is None:
        end = start
    parts = [cue.text for cue in cues if cue.end >= start and cue.start <= end]
    joined = " ".join(parts).strip()
    if len(joined) > max_chars:
        joined = joined[:max_chars].rsplit(" ", 1)[0] + " ..."
    return joined


def cues_to_dicts(cues: Iterable[Cue]) -> List[dict]:
    return [cue.to_dict() for cue in cues]


def cues_from_dicts(records: Iterable[dict]) -> List[Cue]:
    cues: List[Cue] = []
    for record in records:
        try:
            cues.append(Cue(
                start=float(record["start"]),
                end=float(record["end"]),
                text=str(record["text"]),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return cues
