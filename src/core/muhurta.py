"""
Muhurta (electional) evaluation built on the verified Panchanga engine.

Capabilities:
- Sourced filters (data/rules/muhurta_rules.json): Rikta tithis (4/9/14) and
  Amavasya, Vishti (Bhadra) karana, Rahu Kala, per-event nakshatra lists.
- Personal suitability: Tarabala (birth nakshatra) and Chandrabala (birth Moon
  sign) when birth data is available.
- Candidate windows: Abhijit muhurta intersected with event-appropriate lagna
  windows, excluding Rahu Kala and intraday Bhadra (Vishti) windows.

This module answers "when is a window traditionally suitable?" — it does not
claim to predict outcomes. Rules marked "requires edition verification" in the
rules file should be checked against the cited text before relying on them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .constants import INDEX_TO_SIGN, NAKSHATRAS
from .ephemeris import (
    calculate_ascendant,
    calculate_lahiri_ayanamsha,
    datetime_to_julian_day,
)
from .panchanga import PanchangaDay, compute_panchanga, vishti_windows

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rules" / "muhurta_rules.json"

NAKSHATRA_INDEX = {entry["name"]: idx for idx, entry in enumerate(NAKSHATRAS)}

# Common spelling variants -> canonical engine names (rule data tolerance)
_NAKSHATRA_ALIASES = {
    "dhanishtha": "Dhanishta",
    "mrigashirsha": "Mrigashira",
    "purvashadha": "Purva Ashadha",
    "uttarashadha": "Uttara Ashadha",
    "purvabhadrapada": "Purva Bhadrapada",
    "uttarabhadrapada": "Uttara Bhadrapada",
    "shatabhishak": "Shatabhisha",
    "revathi": "Revati",
}


def canonical_nakshatra(name: str) -> str:
    """Normalize a nakshatra name to the engine's canonical spelling."""
    cleaned = (name or "").strip()
    if cleaned in NAKSHATRA_INDEX:
        return cleaned
    return _NAKSHATRA_ALIASES.get(cleaned.lower(), cleaned)

TARAS = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyari", "Sadhaka", "Vadha",
         "Mitra", "Parama Mitra"]
FAVOURABLE_TARAS = {"Sampat", "Kshema", "Sadhaka", "Mitra", "Parama Mitra"}

CHANDRA_GOOD_POSITIONS = {1, 3, 6, 7, 10, 11}
CHANDRA_BAD_POSITIONS = {4, 8, 12}


# ---------------------------------------------------------------- personal suitability

def tara_for(birth_nakshatra_index: int, day_nakshatra_index: int) -> str:
    """Tarabala: tara of the day counted from the birth nakshatra (inclusive)."""
    count = ((day_nakshatra_index - birth_nakshatra_index) % 27) + 1
    return TARAS[(count - 1) % 9]


def tara_is_favourable(tara: str) -> bool:
    return tara in FAVOURABLE_TARAS


def chandrabala_for(birth_rashi_index: int, moon_rashi_index: int) -> str:
    """Chandrabala: transit Moon sign counted from the natal Moon sign."""
    position = ((moon_rashi_index - birth_rashi_index) % 12) + 1
    if position in CHANDRA_GOOD_POSITIONS:
        return "favourable"
    if position in CHANDRA_BAD_POSITIONS:
        return "unfavourable"
    return "mixed"


# ---------------------------------------------------------------- windows

def lagna_windows(day: PanchangaDay, wanted_signs: Sequence[str],
                  step_minutes: int = 4) -> List[Tuple[datetime, datetime, str]]:
    """Contiguous windows between sunrise and sunset where the lagna is in `wanted_signs`."""
    wanted = set(wanted_signs)
    windows: List[Tuple[datetime, datetime, str]] = []
    current = day.sunrise
    start: Optional[datetime] = None
    start_sign = ""

    while current <= day.sunset:
        jd = datetime_to_julian_day(current.year, current.month, current.day,
                                    current.hour, current.minute, current.second,
                                    day.tz_offset)
        ayan = calculate_lahiri_ayanamsha(jd)
        asc = calculate_ascendant(jd, day.latitude, day.longitude, ayan)
        sign = INDEX_TO_SIGN[int(asc // 30) + 1]

        if sign in wanted and start is None:
            start = current
            start_sign = sign
        elif sign not in wanted and start is not None:
            windows.append((start, current, start_sign))
            start = None
        current += timedelta(minutes=step_minutes)

    if start is not None:
        windows.append((start, day.sunset, start_sign))
    if wanted:
        tail = [w for w in windows if w[2] in wanted]
        return tail
    return windows


def _overlaps(a: Tuple[datetime, datetime], b: Tuple[datetime, datetime]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def candidate_windows(day: PanchangaDay, cfg: Dict, common: Dict,
                      min_minutes: int = 15) -> List[Tuple[datetime, datetime, str]]:
    """
    Event windows for the day:

    - When the event defines recommended lagnas, their sunrise-to-sunset windows
      are the candidates.
    - Abhijit muhurta is always added when it does not overlap a candidate.
    - Rahu Kala and intraday Bhadra (Vishti) windows are excluded.
    """
    raw: List[Tuple[datetime, datetime, str]] = []

    wanted_lagnas = cfg.get("recommended_lagnas") or []
    if wanted_lagnas:
        raw.extend((s, e, f"{sign} lagna") for s, e, sign in lagna_windows(day, wanted_lagnas))

    a_start, a_end = day.abhijit
    if not any(_overlaps((a_start, a_end), (s, e)) for s, e, _ in raw):
        raw.append((a_start, a_end, "Abhijit muhurta"))

    blocked: List[Tuple[datetime, datetime]] = []
    if common.get("avoid_rahu_kalam"):
        blocked.append(day.rahu_kalam)
    if common.get("exclude_bhadra_windows"):
        blocked.extend(vishti_windows(day))

    clean = [(s, e, label) for s, e, label in raw
             if not any(_overlaps((s, e), b) for b in blocked)]
    clean = [(s, e, label) for s, e, label in clean
             if (e - s).total_seconds() >= min_minutes * 60]
    return sorted(clean, key=lambda w: w[0])


# ---------------------------------------------------------------- rules + assessment

@dataclass
class DayAssessment:
    day: PanchangaDay
    event: str
    label: str
    suitable: bool
    reasons: List[str]
    tara: Optional[str] = None
    chandrabala: Optional[str] = None
    windows: List[Tuple[datetime, datetime, str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "date": self.day.date.isoformat(),
            "event": self.event,
            "label": self.label,
            "suitable": self.suitable,
            "reasons": self.reasons,
            "tithi": f"{self.day.paksha} {self.day.tithi_name}",
            "nakshatra": self.day.nakshatra,
            "vara": self.day.vara,
            "karana": self.day.karana,
            "tara": self.tara,
            "chandrabala": self.chandrabala,
            "windows": [[w[0].isoformat(sep=" ", timespec="minutes"),
                         w[1].isoformat(sep=" ", timespec="minutes"), w[2]] for w in self.windows],
        }


def load_muhurta_rules(path: Optional[Path] = None) -> Dict:
    return json.loads(Path(path or DEFAULT_RULES_PATH).read_text(encoding="utf-8"))


def assess_day(day: PanchangaDay, event: str, rules: Optional[Dict] = None,
               birth_nakshatra_index: Optional[int] = None,
               birth_rashi_index: Optional[int] = None,
               include_windows: bool = False) -> DayAssessment:
    rules = rules or load_muhurta_rules()
    if event not in rules["events"]:
        raise ValueError(f"unknown muhurta event '{event}' (have: {', '.join(rules['events'])})")
    cfg = rules["events"][event]
    common = rules["common"]

    reasons: List[str] = []
    tithi_ok = day.tithi_index not in cfg["avoid_tithis"]
    if not tithi_ok:
        reasons.append(f"{day.paksha} {day.tithi_name} is an avoided tithi (Rikta/Amavasya)")

    recommended = {canonical_nakshatra(n) for n in (cfg.get("recommended_nakshatras") or [])}
    nakshatra_ok = (not recommended) or (canonical_nakshatra(day.nakshatra) in recommended)
    if not nakshatra_ok:
        reasons.append(f"{day.nakshatra} is not in the recommended nakshatras for {cfg['label']}")

    karana_ok = day.karana not in common["avoid_karana"]
    if not karana_ok:
        reasons.append(f"{day.karana} karana (Bhadra) is avoided")

    tara: Optional[str] = None
    chandrabala: Optional[str] = None
    personal_ok = True
    if birth_nakshatra_index is not None and cfg.get("require_tarabala"):
        day_index = NAKSHATRA_INDEX[day.nakshatra]
        tara = tara_for(birth_nakshatra_index, day_index)
        if not tara_is_favourable(tara):
            personal_ok = False
            reasons.append(f"Tarabala from your birth nakshatra is {tara} (inauspicious)")
    if birth_rashi_index is not None and cfg.get("require_chandrabala"):
        chandrabala = chandrabala_for(birth_rashi_index, INDEX_TO_SIGN_LIST.index(day.moon_sign) + 1)
        if chandrabala == "unfavourable":
            personal_ok = False
            reasons.append(f"Chandrabala is unfavourable (Moon in {day.moon_sign})")

    suitable = tithi_ok and nakshatra_ok and karana_ok and personal_ok
    if suitable:
        reasons.append("Tithi, nakshatra and karana pass the sourced filters"
                       + ("; personal tarabala/chandrabala favourable" if (tara or chandrabala) else ""))

    windows: List[Tuple[datetime, datetime, str]] = []
    if suitable:
        windows = candidate_windows(day, cfg, common) if include_windows else []
        if include_windows and not windows:
            reasons.append("No clean Abhijit/lagna window free of Rahu Kala or Bhadra on this day")

    return DayAssessment(day=day, event=event, label=cfg["label"], suitable=suitable,
                         reasons=reasons, tara=tara, chandrabala=chandrabala, windows=windows)


INDEX_TO_SIGN_LIST = [INDEX_TO_SIGN[i] for i in range(1, 13)]


def find_muhurta_days(start: date, end: date, tz_offset: float, lat: float, lon: float,
                      event: str, elevation_m: float = 0.0,
                      rules: Optional[Dict] = None,
                      birth_nakshatra_index: Optional[int] = None,
                      birth_rashi_index: Optional[int] = None,
                      include_windows: bool = True,
                      max_days: int = 120) -> List[DayAssessment]:
    """
    Assess each civil day in [start, end] and return the suitable ones.

    Day-level filtering uses the fast panchanga path; days that pass are
    recomputed with full end times and candidate windows.
    """
    rules = rules or load_muhurta_rules()
    results: List[DayAssessment] = []
    current = start
    span = (end - start).days + 1
    if span > max_days:
        end = start + timedelta(days=max_days - 1)

    while current <= end:
        light = compute_panchanga(current.year, current.month, current.day,
                                  tz_offset, lat, lon, elevation_m,
                                  include_end_times=False)
        quick = assess_day(light, event, rules, birth_nakshatra_index, birth_rashi_index,
                           include_windows=False)
        if quick.suitable:
            if include_windows:
                full = compute_panchanga(current.year, current.month, current.day,
                                         tz_offset, lat, lon, elevation_m,
                                         include_end_times=True)
                results.append(assess_day(full, event, rules, birth_nakshatra_index,
                                          birth_rashi_index, include_windows=True))
            else:
                results.append(quick)
        current += timedelta(days=1)
    return results
