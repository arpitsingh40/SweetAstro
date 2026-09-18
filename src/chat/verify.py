"""
Answer verification — figures stated by the LLM must exist in the verified payload.

The system prompt forbids inventing dates, periods and degrees, but nothing
previously checked the streamed answer. This module extracts checkable tokens
(years, Month-YYYY periods, decimal degrees) and confirms they occur in the
payload; violations are logged and surfaced as a short calibration note.

Deliberately conservative: only checks numeric facts that the payload always
contains, so it produces few false positives.
"""

from __future__ import annotations

import re
from typing import List, Set

_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2}|2100)\b")
_MONTH_YEAR = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(1[89]\d{2}|20\d{2}|2100)\b"
)
_DEGREE = re.compile(r"\b(\d{1,3}(?:\.\d{1,2})?)\s*°")
_ISO_DATE = re.compile(r"\b(1[89]\d{2}|20\d{2})-(\d{2})-\d{2}\b")

_MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


def _payload_years(payload: str) -> Set[str]:
    return {m.group(1) for m in _YEAR.finditer(payload)}


def _payload_month_years(payload: str) -> Set[str]:
    out: Set[str] = set()
    for match in _ISO_DATE.finditer(payload):
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            out.add(f"{_MONTH_NAMES[month]} {year}")
    return out


def _payload_numbers(payload: str) -> Set[float]:
    return {round(float(m.group(0)), 2) for m in re.finditer(r"\d+\.\d+", payload)}


def _numbers_match(value: float, known: Set[float], shown_decimals: int) -> bool:
    """Rounding-tolerant match: a value displayed by the LLM may differ from the
    payload within half a unit of its last shown decimal place.

    E.g. a payload 151.6517 may be restated as 151.7 (tolerance 0.05) or 151.65.
    """
    tolerance = 0.5 * (10.0 ** -shown_decimals) + 1e-9
    return any(abs(value - candidate) <= tolerance for candidate in known)


def verify_answer(answer: str, payload: str) -> List[str]:
    """Returns a list of tokens stated in the answer but absent from the payload."""
    violations: List[str] = []

    known_years = _payload_years(payload)
    for match in _YEAR.finditer(answer):
        if match.group(1) not in known_years:
            violations.append(f"year {match.group(1)}")

    known_periods = _payload_month_years(payload)
    for match in _MONTH_YEAR.finditer(answer):
        period = f"{match.group(1)} {match.group(2)}"
        if period not in known_periods:
            violations.append(f"period {period}")

    known_numbers = _payload_numbers(payload)
    for match in _DEGREE.finditer(answer):
        raw = match.group(1)
        shown_decimals = len(raw.split(".")[1]) if "." in raw else 0
        value = float(raw)
        if not _numbers_match(value, known_numbers, shown_decimals):
            violations.append(f"degree {match.group(1)}°")

    return sorted(set(violations))
