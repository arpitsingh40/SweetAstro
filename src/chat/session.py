"""
Chat session state — birth-data slots, conversation history, in-memory store.
Optional disk persistence (opt-in via CHAT_PERSIST) keeps sessions across
restarts; birth data is sensitive, so persistence is off by default.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import CHAT_MAX_SESSIONS, CHAT_PERSIST, CHAT_PERSIST_PATH

logger = logging.getLogger("sweetastro.chat")

KNOWN_TOPICS = [
    "wealth", "career", "business", "marriage", "children",
    "property", "education", "siblings", "health", "spirituality",
    "compatibility", "personality", "general",
]

# Fields that may arrive prefixed (partner_dob, partner_place, ...) and are
# merged into a secondary person's BirthSlots.
_PERSONAL_FIELDS = (
    "name", "dob", "tob", "tob_unknown", "place",
    "tz_offset", "tz_offset_estimate", "lat", "lon",
)


def merge_prefixed(person: "BirthSlots", update: Dict[str, Any], prefix: str) -> List[str]:
    """Merges '{prefix}name/dob/tob/place/...' keys into a person's BirthSlots."""
    mapped = {
        key: update[f"{prefix}{key}"]
        for key in _PERSONAL_FIELDS
        if update.get(f"{prefix}{key}") is not None
    }
    return person.merge(mapped)


@dataclass
class BirthSlots:
    """Everything the engine needs, filled incrementally across turns."""

    name: str = ""
    dob: Optional[str] = None            # YYYY-MM-DD
    tob: Optional[str] = None            # HH:MM:SS
    tob_unknown: bool = False
    place: str = ""
    tz_offset: Optional[float] = None    # decimal hours east of UTC
    tz_estimated: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    time_question_asked: bool = False
    question: str = ""
    topic: Optional[str] = None
    historical_events: List[Dict[str, Any]] = field(default_factory=list)
    resolved_place: str = ""
    resolved_note: str = ""

    # ------------------------------------------------------------------ state
    def time_reliable(self) -> bool:
        return bool(self.tob) and not self.tob_unknown

    def core_ready(self) -> bool:
        return bool(self.dob and self.place)

    def birth_hour_minute(self) -> tuple:
        """Returns (hour, minute, second); noon placeholder when time unknown."""
        if not self.tob:
            return 12, 0, 0
        try:
            parts = [int(float(p)) for p in self.tob.split(":")]
            while len(parts) < 3:
                parts.append(0)
            return parts[0], parts[1], parts[2]
        except (ValueError, TypeError):
            return 12, 0, 0

    def birth_datetime(self) -> Optional[datetime]:
        if not self.dob:
            return None
        try:
            y, m, d = (int(p) for p in self.dob.split("-"))
            hour, minute, second = self.birth_hour_minute()
            return datetime(y, m, d, hour, minute, second)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------ merge
    def merge(self, update: Dict[str, Any]) -> List[str]:
        """Merges a validated extraction result. Returns list of changed fields."""
        changed: List[str] = []
        if not update:
            return changed

        for key in ("name", "question"):
            value = update.get(key)
            if isinstance(value, str) and value.strip() and getattr(self, key) != value.strip():
                setattr(self, key, value.strip())
                changed.append(key)

        topic = update.get("topic")
        if isinstance(topic, str) and topic in KNOWN_TOPICS and topic != self.topic:
            self.topic = topic
            changed.append("topic")

        dob = update.get("dob")
        if isinstance(dob, str) and dob.strip() and dob != self.dob:
            self.dob = dob.strip()
            changed.append("dob")

        if update.get("tob_unknown") is True:
            if not self.tob_unknown:
                changed.append("tob_unknown")
            self.tob_unknown = True
            self.tob = None
        else:
            tob = update.get("tob")
            if isinstance(tob, str) and tob.strip():
                if tob != self.tob:
                    changed.append("tob")
                self.tob = tob.strip()
                self.tob_unknown = False

        place = update.get("place")
        if isinstance(place, str) and place.strip() and place.strip() != self.place:
            self.place = place.strip()
            # New place invalidates previously resolved coordinates
            self.lat = None
            self.lon = None
            self.resolved_place = ""
            self.resolved_note = ""
            # ...and an *estimated* timezone; an explicitly stated one is kept.
            if self.tz_estimated:
                self.tz_offset = None
                self.tz_estimated = False
            changed.append("place")

        if update.get("tz_offset") is not None:
            try:
                tz = float(update["tz_offset"])
            except (TypeError, ValueError):
                tz = None
            if tz is not None and -12.0 <= tz <= 14.0:
                if self.tz_offset is None or abs(tz - self.tz_offset) > 1e-9:
                    changed.append("tz_offset")
                self.tz_offset = tz
                self.tz_estimated = False
        elif update.get("tz_offset_estimate") is not None and self.tz_offset is None:
            try:
                tz = float(update["tz_offset_estimate"])
                if -12.0 <= tz <= 14.0:
                    self.tz_offset = tz
                    self.tz_estimated = True
                    changed.append("tz_offset")
            except (TypeError, ValueError):
                pass

        for coord_key in ("lat", "lon"):
            value = update.get(coord_key)
            if value is not None:
                try:
                    coord = float(value)
                except (TypeError, ValueError):
                    continue
                if -180.0 <= coord <= 180.0 and getattr(self, coord_key) != coord:
                    setattr(self, coord_key, coord)
                    changed.append(coord_key)

        events = update.get("historical_events")
        if isinstance(events, list) and events:
            cleaned = []
            for ev in events[:10]:
                if isinstance(ev, dict) and (ev.get("event") or ev.get("date")):
                    cleaned.append({
                        "event": str(ev.get("event", ""))[:200],
                        "date": str(ev.get("date", ""))[:40],
                    })
            if cleaned:
                self.historical_events = cleaned
                changed.append("historical_events")

        return changed

    # ------------------------------------------------------------------- card
    def to_card(self) -> Dict[str, Any]:
        return {
            "name": self.name or "Native",
            "dob": self.dob,
            "tob": self.tob or ("unknown (neutral noon chart)" if self.tob_unknown else None),
            "place": self.resolved_place or self.place,
            "place_query": self.place,
            "geo_note": self.resolved_note,
            "tz_offset": self.tz_offset,
            "tz_estimated": self.tz_estimated,
            "time_reliable": self.time_reliable(),
            "lat": self.lat,
            "lon": self.lon,
            "topic": self.topic,
        }


@dataclass
class ChatSession:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: List[Dict[str, str]] = field(default_factory=list)
    slots: BirthSlots = field(default_factory=BirthSlots)
    chart_basis: Optional[Dict[str, Any]] = None
    kundali: Optional[Dict[str, Any]] = None
    recalled_profile: Optional[Dict[str, Any]] = None
    last_missing: List[str] = field(default_factory=list)
    last_result: Any = None
    last_dasha_detail: str = ""
    vastu_layout: Dict[str, Any] = field(default_factory=dict)
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    reply_language: Optional[str] = None
    basis_confirmation_sent: bool = False
    awaiting_confirmation: bool = False
    pending_answer_mode: Optional[str] = None
    pending_answer_shape: Optional[str] = None
    people: Dict[str, BirthSlots] = field(default_factory=dict)
    active_subject: str = "self"

    def person(self, role: str) -> BirthSlots:
        """Returns the BirthSlots for a role; 'self' is always the primary slots."""
        if role in ("", "self"):
            return self.slots
        return self.people.setdefault(role, BirthSlots())

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.touch()

    def recent_messages(self, limit: int = 8) -> List[Dict[str, str]]:
        history = [m for m in self.messages if m["role"] in ("user", "assistant")]
        return [
            {"role": m["role"], "content": m["content"][:6000]}
            for m in history[-limit:]
        ]

    def summary(self) -> Dict[str, Any]:
        """Compact listing entry for the chat-history panel."""
        first_user = next(
            (m.get("content", "") for m in self.messages if m.get("role") == "user"),
            "",
        )
        title = " ".join(first_user.split())
        if len(title) > 80:
            title = title[:77].rstrip() + "..."
        return {
            "session_id": self.session_id,
            "title": title or "New chat",
            "topic": self.slots.topic or "general",
            "dob": self.slots.dob,
            "place": self.slots.resolved_place or self.slots.place,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": self.messages,
            "slots": asdict(self.slots),
            "chart_basis": self.chart_basis,
            "kundali": self.kundali,
            "recalled_profile": self.recalled_profile,
            "last_missing": self.last_missing,
            "vastu_layout": self.vastu_layout,
            "outcomes": self.outcomes,
            "reply_language": self.reply_language,
            "basis_confirmation_sent": self.basis_confirmation_sent,
            "awaiting_confirmation": self.awaiting_confirmation,
            "pending_answer_mode": self.pending_answer_mode,
            "pending_answer_shape": self.pending_answer_shape,
            "people": {key: asdict(value) for key, value in self.people.items()},
            "active_subject": self.active_subject,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        slot_fields = {f.name for f in BirthSlots.__dataclass_fields__.values()}
        slots = BirthSlots(**{k: v for k, v in (data.get("slots") or {}).items()
                              if k in slot_fields})
        messages = [
            {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
            for m in data.get("messages", [])
            if isinstance(m, dict)
        ]
        return cls(
            session_id=str(data.get("session_id") or uuid.uuid4().hex),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            messages=messages,
            slots=slots,
            chart_basis=data.get("chart_basis"),
            kundali=data.get("kundali") if isinstance(data.get("kundali"), dict) else None,
            recalled_profile=(data.get("recalled_profile")
                              if isinstance(data.get("recalled_profile"), dict) else None),
            last_missing=list(data.get("last_missing") or []),
            vastu_layout=dict(data.get("vastu_layout") or {}),
            outcomes=[o for o in (data.get("outcomes") or []) if isinstance(o, dict)],
            reply_language=data.get("reply_language"),
            basis_confirmation_sent=bool(data.get("basis_confirmation_sent", False)),
            awaiting_confirmation=bool(data.get("awaiting_confirmation", False)),
            pending_answer_mode=data.get("pending_answer_mode"),
            pending_answer_shape=data.get("pending_answer_shape"),
            people={
                str(key): BirthSlots(**{k: v for k, v in raw_person.items() if k in slot_fields})
                for key, raw_person in (data.get("people") or {}).items()
                if isinstance(raw_person, dict)
            },
            active_subject=str(data.get("active_subject") or "self"),
        )


class SessionStore:
    """Thread-safe, bounded session store with optional JSON persistence."""

    def __init__(self, max_sessions: int = CHAT_MAX_SESSIONS,
                 persist_path: Optional[Path] = None):
        self.max_sessions = max(1, max_sessions)
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        if persist_path is not None:
            self.persist_path: Optional[Path] = Path(persist_path)
        else:
            self.persist_path = CHAT_PERSIST_PATH if CHAT_PERSIST else None
        if self.persist_path and self.persist_path.exists():
            self._load()

    def get_or_create(self, session_id: Optional[str] = None) -> ChatSession:
        with self._lock:
            sid = (session_id or "").strip() or uuid.uuid4().hex
            session = self._sessions.get(sid)
            if session is None:
                session = ChatSession(session_id=sid)
                self._sessions[sid] = session
                self._evict_locked()
                self._save_locked()
            return session

    def get(self, session_id: str) -> Optional[ChatSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            deleted = self._sessions.pop(session_id, None) is not None
            if deleted:
                self._save_locked()
            return deleted

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Most recently updated sessions first (for the history panel)."""
        with self._lock:
            ordered = sorted(
                self._sessions.values(),
                key=lambda s: s.updated_at,
                reverse=True,
            )
            return [s.summary() for s in ordered[:max(1, limit)]]

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def _evict_locked(self) -> None:
        while len(self._sessions) > self.max_sessions:
            oldest = min(self._sessions.values(), key=lambda s: s.updated_at)
            self._sessions.pop(oldest.session_id, None)

    def _save_locked(self) -> None:
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = [s.to_dict() for s in self._sessions.values()]
            tmp = self.persist_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.persist_path)
        except OSError as exc:
            logger.warning("session persistence failed: %s", exc)

    def _load(self) -> None:
        try:
            raw = json.loads(self.persist_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not load persisted sessions: %s", exc)
            return
        if not isinstance(raw, list):
            return
        with self._lock:
            for item in raw:
                if isinstance(item, dict):
                    session = ChatSession.from_dict(item)
                    self._sessions[session.session_id] = session
            self._evict_locked()
        logger.info("loaded %d persisted chat session(s)", len(self._sessions))


def reset_slot_for_new_chart(slots: BirthSlots) -> None:
    """Clears derived fields when the user asks to start a new chart."""
    slots.lat = None
    slots.lon = None
    slots.resolved_place = ""
    slots.resolved_note = ""
    slots.tz_estimated = False
    slots.time_question_asked = False
