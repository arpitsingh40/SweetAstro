"""
Birth-data + question extraction (DeepSeek JSON mode).

The extractor never computes astrology. It only turns natural conversation
into validated slots. All values are defensively re-validated in Python;
anything the model invents or misformats is discarded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.vastu import ROOM_KEYS, WATER_KEYS, normalize_direction
from .client import DeepSeekClient
from .session import BirthSlots, KNOWN_TOPICS

EXTRACTION_SYSTEM_PROMPT = """You are a precise information extractor for an astrology chat.

Read the conversation and return ONE JSON object containing only birth facts the user has actually stated (now or earlier in the conversation), plus their current astrology question.

Keys:
- "name": string or null
- "dob": "YYYY-MM-DD" or null
- "tob": "HH:MM:SS" in 24-hour time or null
- "tob_unknown": true ONLY if the user says they do not know / cannot provide their birth time; otherwise false
- "place": string (city, state/province, country) or null
- "tz_offset": decimal hours east of UTC, ONLY if the user explicitly states it (e.g. "IST", "+5:30", "UTC-5"); null otherwise
- "tz_offset_estimate": your best estimate of the standard UTC offset for the stated birthplace (e.g. India 5.5, UK 0, New York -5, Tokyo 9); null if the place is unknown or ambiguous
- "lat": number or null (only if the user typed explicit coordinates)
- "lon": number or null
- "question": one concise sentence expressing what the user wants to know astrologically (e.g. "When will I get married?", "How will my career and wealth develop?", "What does my chart say about having children?"), or null
- "topic": one of ["wealth","career","business","marriage","children","property","education","siblings","health","spirituality","compatibility","personality","general"], or null. Use "compatibility" for matching/milan questions about two people, and "personality" for self-understanding asks (nature, strengths, character).
- "partner_name"/"partner_dob"/"partner_tob"/"partner_tob_unknown"/"partner_place"/"partner_tz_offset"/"partner_tz_offset_estimate": the OTHER person's birth details — fill ONLY when the user provides a second person's details for a compatibility/matching question (kundli milan, guna milan, rishta, "are we compatible", "will we marry"); otherwise null.
- "compatibility_request": true ONLY when the user asks about compatibility or matching between themselves and another person; otherwise false.
- "rectify_request": true ONLY when the user says they do not know their birth time and asks to find/estimate it from dated life events (e.g. "I don't know my time, find it from my marriage and job dates"); otherwise false.
- "subjects": list of other people's birth details when the user asks about someone else's chart (e.g. "my son's career", "my father's health"). Items: {"role": "partner"|"child"|"parent"|"sibling"|"other", "name": string or null, "dob": "YYYY-MM-DD" or null, "tob": "HH:MM:SS" or null, "tob_unknown": true/false, "place": string or null, "tz_offset": number or null}. Use [] when nobody else is discussed.
- "historical_events": list of {"event": short label, "date": "YYYY-MM-DD or YYYY-MM"} for past life events the user shares for backtesting, or []
- "muhurta_event": one of ["vivaha","griha_pravesh","business","travel","general"] or null — set ONLY when the user asks to CHOOSE or FIND an auspicious date/time for an event (e.g. "muhurat for marriage", "good date for griha pravesh", "when should we launch", "auspicious day for travel"). Do NOT set it for prediction questions such as "when will I get married".
- "muhurta_start": "YYYY-MM-DD" or null — start of the date range the user wants to search
- "muhurta_end": "YYYY-MM-DD" or null — end of that search range
- "vastu_facing": direction or null — the direction the plot/main door faces (North, North-East, East, South-East, South, South-West, West, North-West)
- "vastu_slope": direction or null — the direction the plot slopes down or water drains toward
- "vastu_plot_shape": one of ["square","rectangle","gomukhi","shermukhi","triangular","irregular","cut"] or null
- "vastu_rooms": object or null — when the user describes their home layout or asks about room directions, map the ROOM KEY to the direction it is in. Allowed room keys: puja, kitchen, master_bedroom, children_bedroom, guest_room, living_room, dining, study, parents_room, store, staircase, toilet, utility, garage. Normalize "NE" to "North-East" etc.
- "vastu_water": object or null — keys "underground_tank" and/or "overhead_tank" mapped to directions
- "answer_mode": "lookup" or "reading" or null — use "lookup" ONLY when the user asks for a single fact about their chart or a date (e.g. "what is my nakshatra", "which rashi am I", "my lagna", "current dasha", "panchang today"). Use "reading" when they ask for interpretation, advice, timing, remedies, analysis, or anything about events.
- "answer_shape": "verdict" | "timing" | "analysis" | "remedy" | "report" or null — shapes the reply length, not the facts. "verdict" for short yes/no-style asks ("can I become rich this month?", "will I get the job?"); "timing" for when-questions ("when will I marry?"); "remedy" for remedy/upay/mantra/gemstone asks; "report" ONLY when the user explicitly asks for a full/detailed/deep reading, "go deeper", "deep mode", or every-planet analysis; "analysis" as the default for why/how/tell-me-about questions. Use null when unsure.
- "outcome": object or null — set ONLY when the user reports the real-world result of a previously discussed event. Format: {"event": short label, "date": "YYYY-MM-DD" or "YYYY-MM" or null, "verdict": "happened" | "did_not_happen" | "partial", "note": short optional detail}. Use null when the user is not reporting an outcome.

Rules:
1. NEVER invent or guess a date, time, place, coordinates, or room direction. Use null when not provided.
2. Normalize "15 May 1995" to "1995-05-15"; "2:30 pm" to "14:30:00".
3. If the user corrects an earlier value, return the corrected value.
4. If the user's message is only a greeting or unrelated chatter, return all nulls/empty list.
5. If the user's message is a follow-up (asking for remedies, more detail, timing, or a related aspect of the SAME subject), keep the established "question" subject and the established "topic" instead of switching. Only set a new "topic" when the user clearly asks about a different life area.
6. For muhurta date ranges: "this month"/"next month"/"in October" must be converted to concrete YYYY-MM-DD start/end dates using the conversation context; if no range is stated, return null for both.
7. Set vastu fields only for home-layout descriptions or direction questions (vastu shastra). Do not set them for chart questions such as "will I buy a house".
8. Never mix people: the unprefixed keys (dob, tob, place, ...) always describe the user; partner_* keys always describe the other person in a compatibility question; subjects[] items describe third people. Never copy one person's details into another's keys.
9. Return ONLY the JSON object, no commentary."""

# Keys allowed through merge(); guards against prompt-injected extra fields.
_ALLOWED_KEYS = {
    "name", "dob", "tob", "tob_unknown", "place", "tz_offset",
    "tz_offset_estimate", "lat", "lon", "question", "topic", "historical_events",
    "muhurta_event", "muhurta_start", "muhurta_end",
    "vastu_facing", "vastu_slope", "vastu_plot_shape", "vastu_rooms", "vastu_water",
    "answer_mode", "answer_shape", "outcome",
    "partner_name", "partner_dob", "partner_tob", "partner_tob_unknown", "partner_place",
    "partner_tz_offset", "partner_tz_offset_estimate",
    "compatibility_request", "subjects", "rectify_request",
}

MUHURTA_EVENTS = {"vivaha", "griha_pravesh", "business", "travel", "general"}
PLOT_SHAPES = {"square", "rectangle", "gomukhi", "shermukhi", "triangular", "irregular", "cut"}
SUBJECT_ROLES = {"partner", "child", "parent", "sibling", "other"}

_PARTNER_FIELDS = (
    "name", "dob", "tob", "tob_unknown", "place",
    "tz_offset", "tz_offset_estimate",
)


def _clean_direction_map(value: Any, allowed_keys: List[str]) -> Optional[Dict[str, str]]:
    if not isinstance(value, dict):
        return None
    cleaned: Dict[str, str] = {}
    for key, raw in value.items():
        key_norm = str(key).strip().lower().replace(" ", "_")
        if key_norm not in allowed_keys:
            continue
        direction = normalize_direction(raw)
        if direction:
            cleaned[key_norm] = direction
    return cleaned or None


def clean_date(value: Any, min_year: int = 1800, max_year: int = 2100) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%Y.%m.%d"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if min_year <= parsed.year <= max_year:
            return parsed.strftime("%Y-%m-%d")
        return None
    return None


def clean_time(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip().upper().replace(" ", "")
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S%p", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    return None


def clean_float(value: Any, low: float, high: float) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if low <= number <= high:
        return number
    return None


def clean_person_fields(raw: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """Validates one person's birth fields ('partner_dob' style with a prefix)."""
    cleaned: Dict[str, Any] = {}
    name = raw.get(f"{prefix}name")
    if isinstance(name, str) and name.strip():
        cleaned[f"{prefix}name"] = name.strip()[:300]

    dob = clean_date(raw.get(f"{prefix}dob"), min_year=1800, max_year=datetime.now().year)
    if dob and datetime.strptime(dob, "%Y-%m-%d").date() <= datetime.now().date():
        cleaned[f"{prefix}dob"] = dob

    tob = clean_time(raw.get(f"{prefix}tob"))
    if tob:
        cleaned[f"{prefix}tob"] = tob
        cleaned[f"{prefix}tob_unknown"] = False
    elif raw.get(f"{prefix}tob_unknown") is True:
        cleaned[f"{prefix}tob_unknown"] = True

    place = raw.get(f"{prefix}place")
    if isinstance(place, str) and place.strip():
        cleaned[f"{prefix}place"] = place.strip()[:300]

    tz = clean_float(raw.get(f"{prefix}tz_offset"), -12.0, 14.0)
    if tz is not None:
        cleaned[f"{prefix}tz_offset"] = tz
    tz_est = clean_float(raw.get(f"{prefix}tz_offset_estimate"), -12.0, 14.0)
    if tz_est is not None:
        cleaned[f"{prefix}tz_offset_estimate"] = tz_est
    return cleaned


def _clean_subject(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    role = str(item.get("role", "")).strip().lower()
    if role not in SUBJECT_ROLES:
        return None
    person = clean_person_fields(item, "")
    if not any(key in person for key in ("name", "dob", "tob", "tob_unknown", "place", "tz_offset")):
        return None
    return {"role": role, **person}


def clean_extraction(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and normalizes a model extraction into slot-update form."""
    cleaned: Dict[str, Any] = {}

    for key in ("name", "place", "question"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            cleaned[key] = value.strip()[:300]

    dob = clean_date(raw.get("dob"), min_year=1800, max_year=datetime.now().year)
    if dob and datetime.strptime(dob, "%Y-%m-%d").date() > datetime.now().date():
        dob = None  # future birth dates are impossible
    if dob:
        cleaned["dob"] = dob

    tob = clean_time(raw.get("tob"))
    if tob:
        cleaned["tob"] = tob
        cleaned["tob_unknown"] = False
    elif raw.get("tob_unknown") is True:
        cleaned["tob_unknown"] = True

    tz = clean_float(raw.get("tz_offset"), -12.0, 14.0)
    if tz is not None:
        cleaned["tz_offset"] = tz
    tz_est = clean_float(raw.get("tz_offset_estimate"), -12.0, 14.0)
    if tz_est is not None:
        cleaned["tz_offset_estimate"] = tz_est

    lat = clean_float(raw.get("lat"), -90.0, 90.0)
    lon = clean_float(raw.get("lon"), -180.0, 180.0)
    if lat is not None and lon is not None:
        cleaned["lat"] = lat
        cleaned["lon"] = lon

    topic = raw.get("topic")
    if isinstance(topic, str) and topic.strip().lower() in KNOWN_TOPICS:
        cleaned["topic"] = topic.strip().lower()

    event = raw.get("muhurta_event")
    if isinstance(event, str) and event.strip().lower() in MUHURTA_EVENTS:
        cleaned["muhurta_event"] = event.strip().lower()
    muhurta_start = clean_date(raw.get("muhurta_start"), min_year=1900, max_year=2100)
    muhurta_end = clean_date(raw.get("muhurta_end"), min_year=1900, max_year=2100)
    if muhurta_start:
        cleaned["muhurta_start"] = muhurta_start
    if muhurta_end:
        cleaned["muhurta_end"] = muhurta_end

    facing = normalize_direction(raw.get("vastu_facing"))
    if facing:
        cleaned["vastu_facing"] = facing
    slope = normalize_direction(raw.get("vastu_slope"))
    if slope:
        cleaned["vastu_slope"] = slope
    shape = raw.get("vastu_plot_shape")
    if isinstance(shape, str) and shape.strip().lower() in PLOT_SHAPES:
        cleaned["vastu_plot_shape"] = shape.strip().lower()
    rooms = _clean_direction_map(raw.get("vastu_rooms"), ROOM_KEYS)
    if rooms:
        cleaned["vastu_rooms"] = rooms
    water = _clean_direction_map(raw.get("vastu_water"), WATER_KEYS)
    if water:
        cleaned["vastu_water"] = water

    answer_mode = raw.get("answer_mode")
    if isinstance(answer_mode, str) and answer_mode.strip().lower() in ("lookup", "reading"):
        cleaned["answer_mode"] = answer_mode.strip().lower()

    answer_shape = raw.get("answer_shape")
    if isinstance(answer_shape, str) and answer_shape.strip().lower() in (
            "verdict", "timing", "analysis", "remedy", "report"):
        cleaned["answer_shape"] = answer_shape.strip().lower()

    outcome = raw.get("outcome")
    if isinstance(outcome, dict):
        verdict = str(outcome.get("verdict", "")).strip().lower()
        if verdict in ("happened", "did_not_happen", "partial"):
            date_val = outcome.get("date")
            date_str: Optional[str] = None
            if isinstance(date_val, str):
                candidate = date_val.strip()
                parts = candidate.split("-")
                if (len(parts) in (2, 3) and parts[0].isdigit() and len(parts[0]) == 4
                        and parts[1].isdigit() and 1 <= int(parts[1]) <= 12):
                    date_str = candidate
            cleaned["outcome"] = {
                "event": str(outcome.get("event", "")).strip()[:120] or "unspecified event",
                "date": date_str,
                "verdict": verdict,
                "note": str(outcome.get("note", "")).strip()[:300],
            }

    events = raw.get("historical_events")
    if isinstance(events, list):
        valid_events: List[Dict[str, str]] = []
        for item in events[:10]:
            if not isinstance(item, dict):
                continue
            event = str(item.get("event", "")).strip()
            date = str(item.get("date", "")).strip()
            if event or date:
                valid_events.append({"event": event[:200], "date": date[:40]})
        if valid_events:
            cleaned["historical_events"] = valid_events

    if raw.get("compatibility_request") is True:
        cleaned["compatibility_request"] = True
    if raw.get("rectify_request") is True:
        cleaned["rectify_request"] = True
    cleaned.update(clean_person_fields(raw, "partner_"))

    subjects = raw.get("subjects")
    if isinstance(subjects, list):
        valid_subjects = [subject for subject in (_clean_subject(item) for item in subjects[:5])
                          if subject is not None]
        if valid_subjects:
            cleaned["subjects"] = valid_subjects

    return {k: v for k, v in cleaned.items() if k in _ALLOWED_KEYS}


class BirthDataExtractor:
    def __init__(self, client: DeepSeekClient):
        self.client = client

    def extract(
        self,
        messages: List[Dict[str, str]],
        slots: BirthSlots,
    ) -> Dict[str, Any]:
        known = (
            f"Already known: name={slots.name or '—'}, dob={slots.dob or '—'}, "
            f"tob={slots.tob or ('unknown' if slots.tob_unknown else '—')}, "
            f"place={slots.place or '—'}, tz_offset={slots.tz_offset if slots.tz_offset is not None else '—'}, "
            f"established question={slots.question or '—'}, established topic={slots.topic or '—'}."
        )
        convo = messages[-10:]
        convo_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:3000]}" for m in convo
        )
        user_prompt = f"{known}\n\nConversation:\n{convo_text}\n\nReturn the JSON object now."
        raw = self.client.complete_json(
            [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
        )
        if not isinstance(raw, dict):
            return {}
        return clean_extraction(raw)
