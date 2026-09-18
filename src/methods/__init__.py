"""
Modern method packs — video-derived fallback methods, always labelled.

A pack is a JSON file in ``data/methods/`` describing a non-classical method
(curated from the video research pipeline) and the deterministic server-side
computation the engine applies to a chart. Packs are:

- **excluded from the classical provenance ledger** — they can never be
  presented as classical authority;
- **disabled by default** (``"enabled": false``) until the evidence gate and a
  human review pass;
- **fallback-only** — surfaced when the capability assessment reports that the
  engine cannot fully answer the question, never to override a classical
  answer.

Personal use may enable verbatim transcript quotes per pack
(``"allow_quotes": true``); otherwise only paraphrase + attribution is emitted.
"""

from .registry import (
    MethodMatch, MethodPack, format_method_lines, load_method_packs,
    method_for_topic, methods_dir, pack_problems, quotes_enabled,
)
from .reasons import (
    canonical_reason_tags, dasha_reason_tags, promise_reason_tags, reason_overlap,
)

__all__ = [
    "MethodMatch", "MethodPack", "format_method_lines", "load_method_packs",
    "method_for_topic", "methods_dir", "pack_problems", "quotes_enabled",
    "canonical_reason_tags", "dasha_reason_tags", "promise_reason_tags",
    "reason_overlap",
]
