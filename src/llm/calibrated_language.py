"""
Calibrated language contract (single source of truth).

The banned-phrase list and the sanitizer were maintained separately in the
chat prompt and the evaluation rubric, so they could drift (audit round 2,
MEDIUM: "unify sanitizer + rubric banned-phrase list"). Both now derive from
this module:

- ``BANNED_ABSOLUTE`` is what the rubric flags.
- ``ABSOLUTE_PATTERNS`` is what the final-text sanitizer rewrites.

Every phrase in ``BANNED_ABSOLUTE`` has a sanitizer replacement, so text that
survives the sanitizer cannot be flagged by the rubric for a phrase the
sanitizer knows about.

Confidence labels: the engine emits exactly one of Low / Medium / High. The
LLM is forbidden from writing hybrid ranges ("Low to Medium") — the helpers
here detect and normalize them against the payload's canonical level.
"""

import re
from typing import List, Tuple

BANNED_ABSOLUTE: List[str] = [
    "definitely",
    "guaranteed",
    "100%",
    "will surely",
    "you will certainly",
    "you will get married in",
    "for certain",
]

ABSOLUTE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bnot\s+guaranteed\b", re.IGNORECASE), "not assured"),
    (re.compile(r"\bguaranteed\b", re.IGNORECASE), "traditionally indicated without any assurance"),
    (re.compile(r"\bdefinitely\b", re.IGNORECASE), "very likely"),
    (re.compile(r"\bwill surely\b", re.IGNORECASE), "is likely to"),
    (re.compile(r"\byou will certainly\b", re.IGNORECASE), "the chart indicates you may"),
    (re.compile(r"\bfor certain\b", re.IGNORECASE), "with reasonable confidence"),
    (re.compile(r"\b100%\s*", re.IGNORECASE), "high confidence "),
    (re.compile(r"you will get married in", re.IGNORECASE),
     "the chart points to a marriage window around"),
]

VALID_CONFIDENCE = ("Low", "Medium", "High")

# Hybrid ranges the LLM must never use: "Low to Medium", "Medium-High", "Low/High".
_HYBRID_CONFIDENCE = re.compile(
    r"\b(Low|Medium|High)\s*(?:to|or|/|[-–—])\s*(Low|Medium|High)\b",
    re.IGNORECASE,
)


def hybrid_confidence_labels(text: str) -> List[str]:
    """Return any hybrid confidence ranges found in the text (rubric use)."""
    return [m.group(0) for m in _HYBRID_CONFIDENCE.finditer(text or "")]


def normalize_confidence_labels(text: str, canonical: str) -> str:
    """Rewrite hybrid confidence ranges to the engine's canonical level.

    Called with the level from the payload's canonical confidence block, so a
    drifted LLM label can never overstate (or understate) the engine value.
    """
    if canonical not in VALID_CONFIDENCE:
        return text
    return _HYBRID_CONFIDENCE.sub(canonical, text or "")


def sanitize_absolute_language(text: str) -> str:
    """Final safety net against certainty phrasing in LLM output.

    Collapses repeated spaces/tabs after replacements but preserves newlines,
    so paragraph and section formatting survives the sanitizer.
    """
    fixed = text or ""
    for pattern, replacement in ABSOLUTE_PATTERNS:
        fixed = pattern.sub(replacement, fixed)
    fixed = re.sub(r"[ \t]{2,}", " ", fixed)
    return fixed
