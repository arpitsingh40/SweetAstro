"""
iCalendar (RFC 5545) export for dasha boundaries.

Pure string builder: no external dependencies, CRLF line endings, 75-octet
line folding, all-day events (DTEND exclusive). Used by POST /api/calendar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

PROD_ID = "-//SweetAstro//Dasha Calendar//EN"


def _escape(value: str) -> str:
    text = str(value or "")
    text = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 line folding: max 75 octets, continuations start with a space."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts: List[str] = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            parts.append(current)
            current = char
        else:
            current += char
    parts.append(current)
    return "\r\n ".join(parts)


def build_calendar_ics(*, calendar_name: str, events: List[Dict[str, Any]]) -> str:
    """Builds an all-day-event VCALENDAR. Events need uid, summary, start (YYYY-MM-DD)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: List[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PROD_ID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
    ]
    for event in events:
        start = str(event.get("start") or "")
        if not start:
            continue
        end_date = str(event.get("end") or start)
        try:
            exclusive_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            exclusive_end = datetime.strptime(start, "%Y-%m-%d") + timedelta(days=1)
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_escape(event.get('uid') or start)}@sweetastro")
        lines.append(f"DTSTAMP:{stamp}")
        lines.append(f"DTSTART;VALUE=DATE:{start.replace('-', '')}")
        lines.append(f"DTEND;VALUE=DATE:{exclusive_end:%Y%m%d}")
        lines.append(f"SUMMARY:{_escape(event.get('summary') or 'Dasha change')}")
        if event.get("description"):
            lines.append(f"DESCRIPTION:{_escape(event['description'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
