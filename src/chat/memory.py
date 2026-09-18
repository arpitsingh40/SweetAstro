"""
Long-term memory store — one profile per birth fingerprint, linked sessions.

Schema: docs/memory_schema.json (schema_version 1.0.0).
Storage: JSON at data/chat_sessions/memory.json (same folder as sessions.json,
git-ignored, created only when persistence is enabled).

A profile deduplicates the same kundali across chats: the fingerprint is
derived from the birth data (not the name), so reopening a chart in a new
chat links to the same profile. Birth data is sensitive — the file stays on
the local machine and respects the CHAT_PERSIST switch via the orchestrator.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sweetastro.chat")

MEMORY_SCHEMA_VERSION = "1.0.0"
DEFAULT_MAX_PROFILES = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def birth_fingerprint(birth: Dict[str, Any]) -> str:
    """
    Stable identity for a kundali: DOB + TOB (or unknown flag) + rounded
    coordinates + timezone. The name is deliberately excluded so the same
    chart links to one profile across chats and name spellings.
    """
    dob = str(birth.get("dob") or "").strip()
    tob = str(birth.get("tob") or "").strip()
    if not tob and birth.get("tob_unknown"):
        tob = "unknown"
    lat = birth.get("lat")
    lon = birth.get("lon")
    lat_key = f"{float(lat):.4f}" if isinstance(lat, (int, float)) else ""
    lon_key = f"{float(lon):.4f}" if isinstance(lon, (int, float)) else ""
    tz = birth.get("tz_offset")
    tz_key = f"{float(tz):.2f}" if isinstance(tz, (int, float)) else ""
    raw = "|".join([dob, tob, lat_key, lon_key, tz_key])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def profile_id_for(fingerprint: str) -> str:
    return "prof_" + fingerprint[:16]


def _clean_birth(birth: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dob": birth.get("dob"),
        "tob": birth.get("tob"),
        "tob_unknown": bool(birth.get("tob_unknown", False)),
        "place": str(birth.get("place") or ""),
        "place_query": str(birth.get("place_query") or ""),
        "lat": birth.get("lat"),
        "lon": birth.get("lon"),
        "tz_offset": birth.get("tz_offset"),
        "tz_estimated": bool(birth.get("tz_estimated", False)),
    }


def _clean_kundali(kundali: Dict[str, Any]) -> Dict[str, Any]:
    chart = kundali.get("chart") or {}
    vargas = chart.get("vargas")
    return {
        "ayanamsha": str(chart.get("ayanamsha") or "Lahiri (Chitrapaksha)"),
        "ascendant": str(chart.get("ascendant") or ""),
        "moon_sign": str(chart.get("moon_sign") or ""),
        "moon_nakshatra": str(chart.get("moon_nakshatra") or ""),
        "moon_nakshatra_pada": int(chart.get("moon_nakshatra_pada") or 1),
        "dasha": str(chart.get("dasha") or ""),
        "vargas": [str(v) for v in vargas] if isinstance(vargas, list) else [],
    }


class MemoryStore:
    """Thread-safe, bounded profile memory with optional JSON persistence."""

    def __init__(self, path: Optional[Path] = None,
                 max_profiles: int = DEFAULT_MAX_PROFILES):
        self.path: Optional[Path] = Path(path) if path is not None else None
        self.max_profiles = max(1, max_profiles)
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            self._load()

    # ------------------------------------------------------------------ write
    def upsert_from_session(self, session: Any) -> Optional[str]:
        """Creates or updates the profile for a session's computed kundali."""
        kundali = getattr(session, "kundali", None)
        if not isinstance(kundali, dict) or not kundali:
            return None
        birth = _clean_birth(kundali.get("birth") or {})
        fingerprint = birth_fingerprint(birth)
        profile_id = profile_id_for(fingerprint)
        now = _now_iso()

        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                profile = {
                    "profile_id": profile_id,
                    "fingerprint": fingerprint,
                    "name": str(kundali.get("birth", {}).get("name") or "Native"),
                    "created_at": now,
                    "updated_at": now,
                    "birth": birth,
                    "kundali": _clean_kundali(kundali),
                    "sessions": [],
                }
                self._profiles[profile_id] = profile
            else:
                profile["name"] = str(kundali.get("birth", {}).get("name") or profile["name"])
                profile["updated_at"] = now
                profile["birth"] = birth
                profile["kundali"] = _clean_kundali(kundali)

            session_id = str(getattr(session, "session_id", "") or "")
            if session_id and session_id not in profile["sessions"]:
                profile["sessions"].append(session_id)

            self._evict_locked()
            self._save_locked()
        return profile_id

    # ------------------------------------------------------------------- read
    def get(self, profile_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            profile = self._profiles.get(profile_id)
            return json.loads(json.dumps(profile)) if profile else None

    def find_matching(self, dob: Optional[str], tob: Optional[str],
                      tob_unknown: bool = False,
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz_offset: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Exact birth-fingerprint lookup (used once coordinates are resolved)."""
        fingerprint = birth_fingerprint({
            "dob": dob, "tob": tob, "tob_unknown": tob_unknown,
            "lat": lat, "lon": lon, "tz_offset": tz_offset,
        })
        with self._lock:
            profile = self._profiles.get(profile_id_for(fingerprint))
            return json.loads(json.dumps(profile)) if profile else None

    def find_by_dob_place(self, dob: Optional[str], place: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Fuzzy pre-recall match: same DOB and a compatible place string (used
        before geocoding resolves coordinates). Most recently updated wins.
        """
        dob_key = str(dob or "").strip()
        place_key = " ".join(str(place or "").lower().split())
        if not dob_key or not place_key:
            return None
        matches = []
        with self._lock:
            for profile in self._profiles.values():
                birth = profile.get("birth") or {}
                if str(birth.get("dob") or "").strip() != dob_key:
                    continue
                stored = " ".join(str(birth.get("place") or "").lower().split())
                query = " ".join(str(birth.get("place_query") or "").lower().split())
                if not stored and not query:
                    continue
                q_first = place_key.split(",")[0].strip()
                s_first = stored.split(",")[0].strip() if stored else ""
                if (place_key in stored or stored in place_key
                        or place_key in query or query in place_key
                        or (q_first and q_first == s_first)):
                    matches.append(profile)
        if not matches:
            return None
        latest = max(matches, key=lambda p: p.get("updated_at", ""))
        return json.loads(json.dumps(latest))

    def link_session(self, profile_id: str, session_id: str) -> bool:
        """Idempotently links an additional session to a profile."""
        if not profile_id or not session_id:
            return False
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return False
            if session_id not in profile["sessions"]:
                profile["sessions"].append(session_id)
                profile["updated_at"] = _now_iso()
                self._save_locked()
            return True

    def list_profiles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Light listing (no kundali) sorted by most recently updated."""
        with self._lock:
            ordered = sorted(self._profiles.values(),
                             key=lambda p: p.get("updated_at", ""), reverse=True)
            return [
                {
                    "profile_id": p["profile_id"],
                    "name": p["name"],
                    "dob": p["birth"].get("dob"),
                    "place": p["birth"].get("place", ""),
                    "session_count": len(p["sessions"]),
                    "updated_at": p["updated_at"],
                }
                for p in ordered[:max(1, limit)]
            ]

    def count(self) -> int:
        with self._lock:
            return len(self._profiles)

    def to_document(self) -> Dict[str, Any]:
        """Full store document matching docs/memory_schema.json."""
        with self._lock:
            return {
                "schema_version": MEMORY_SCHEMA_VERSION,
                "updated_at": _now_iso(),
                "profiles": json.loads(json.dumps(list(self._profiles.values()))),
            }

    # -------------------------------------------------------------- internals
    def _evict_locked(self) -> None:
        while len(self._profiles) > self.max_profiles:
            oldest = min(self._profiles.values(),
                         key=lambda p: p.get("updated_at", ""))
            self._profiles.pop(oldest["profile_id"], None)

    def _save_locked(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": MEMORY_SCHEMA_VERSION,
                "updated_at": _now_iso(),
                "profiles": list(self._profiles.values()),
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.warning("memory persistence failed: %s", exc)

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not load memory store: %s", exc)
            return
        if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), list):
            return
        with self._lock:
            for item in raw["profiles"]:
                if isinstance(item, dict) and item.get("profile_id"):
                    self._profiles[item["profile_id"]] = item
            self._evict_locked()
        logger.info("loaded %d memory profile(s)", len(self._profiles))
