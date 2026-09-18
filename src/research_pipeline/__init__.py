"""
Offline video-knowledge research pipeline (dev-only).

This package ingests publicly available video metadata and captions for
research on modern astrology methods, extracts candidate calculation methods,
and scores their evidence. It is deliberately isolated from the answer path:
``src/chat/*``, ``src/consumer.py`` and ``src/knowledge/*`` must never import
it, and transcripts are never served by the engine. Only curated, labelled
method packs under ``data/methods/`` may reach a payload.
"""

from .captions import Cue, format_timestamp, parse_timestamp, parse_vtt, quote_range
from .store import VideoRecord, VideoStore, video_store_dir

__all__ = [
    "Cue", "format_timestamp", "parse_timestamp", "parse_vtt", "quote_range",
    "VideoRecord", "VideoStore", "video_store_dir",
]
