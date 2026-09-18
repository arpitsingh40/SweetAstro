"""
Word-boundary keyword matching for free-text routing.

Substring matching caused real misroutes: "ill" inside "will" made
"When will I get married?" a *health* question (a consumer topic and a varga
set both wrong). Routing keywords now match whole words with an optional
suffix, so "pregnan" still catches "pregnancy" while "will" never matches
"ill".
"""

import re
from functools import lru_cache
from typing import Iterable, Sequence


@lru_cache(maxsize=256)
def _pattern(words: tuple) -> re.Pattern:
    parts = [re.escape(word) + r"\w*" for word in words]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


def matches_any(text: str, words: Sequence[str]) -> bool:
    """True when any keyword occurs as a whole word (suffixes allowed)."""
    if not text or not words:
        return False
    return bool(_pattern(tuple(words)).search(text))


def first_group(text: str, groups: Iterable[Sequence[str]]) -> int:
    """Index of the first group with a match, or -1 (group priority order)."""
    for index, words in enumerate(groups):
        if matches_any(text, words):
            return index
    return -1
