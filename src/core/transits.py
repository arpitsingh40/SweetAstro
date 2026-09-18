"""
Transit (Gochara) Engine.
Calculates historical and future positions of slow-moving planets (Jupiter, Saturn, Rahu, Ketu)
and determines Double Transit activations on the marriage axis.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .constants import INDEX_TO_SIGN, SIGN_LORDS
from .ephemeris import (
    datetime_to_julian_day, calculate_lahiri_ayanamsha,
    calculate_planet_positions
)
from .chart import D1Chart, _get_sign_and_deg


@dataclass
class TransitPosition:
    planet: str
    sign: str
    sign_index: int          # 1 to 12
    degree_in_sign: float
    is_retrograde: bool
    aspected_sign_indices: List[int]


@dataclass
class DoubleTransitResult:
    is_active: bool
    jupiter_aspects_7th_house: bool
    jupiter_aspects_7th_lord: bool
    jupiter_aspects_lagna: bool
    jupiter_aspects_lagna_lord: bool
    jupiter_aspects_venus: bool
    saturn_aspects_7th_house: bool
    saturn_aspects_7th_lord: bool
    saturn_aspects_lagna: bool
    saturn_aspects_lagna_lord: bool
    jupiter_score: float
    saturn_score: float
    total_transit_score: float
    description: str


def _get_aspected_signs(planet: str, sign_idx: int) -> List[int]:
    """Returns the list of 1-based sign indices aspected by the planet (including its own sign)."""
    # Planet always activates the sign it is transiting
    aspects = [sign_idx]
    # 7th aspect
    aspects.append(((sign_idx + 6 - 1) % 12) + 1)

    if planet == "Mars":
        aspects.append(((sign_idx + 3 - 1) % 12) + 1)  # 4th sign
        aspects.append(((sign_idx + 7 - 1) % 12) + 1)  # 8th sign
    elif planet == "Jupiter":
        aspects.append(((sign_idx + 4 - 1) % 12) + 1)  # 5th sign
        aspects.append(((sign_idx + 8 - 1) % 12) + 1)  # 9th sign
    elif planet == "Saturn":
        aspects.append(((sign_idx + 2 - 1) % 12) + 1)  # 3rd sign
        aspects.append(((sign_idx + 9 - 1) % 12) + 1)  # 10th sign
    elif planet in ["Rahu", "Ketu"]:
        aspects.append(((sign_idx + 4 - 1) % 12) + 1)  # 5th sign
        aspects.append(((sign_idx + 8 - 1) % 12) + 1)  # 9th sign

    return sorted(list(set(aspects)))


def get_transit_positions(target_date: datetime,
                          planets: Optional[List[str]] = None,
                          tz_offset_hours: float = 0.0) -> Dict[str, TransitPosition]:
    """
    Computes sidereal transit positions. Defaults to all nine grahas.

    Timezone contract: `target_date` is treated as UTC unless
    `tz_offset_hours` is supplied (pass the local offset when handing in a
    local civil time). Internal callers pass UTC.
    """
    if planets is None:
        planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
                   "Saturn", "Rahu", "Ketu"]
    jd = datetime_to_julian_day(
        target_date.year, target_date.month, target_date.day,
        target_date.hour, target_date.minute, target_date.second,
        tz_offset_hours=tz_offset_hours
    )
    ayanamsha = calculate_lahiri_ayanamsha(jd)
    positions = calculate_planet_positions(jd, ayanamsha)

    transits: Dict[str, TransitPosition] = {}
    for p in planets:
        p_data = positions[p]
        sign, sign_idx, deg = _get_sign_and_deg(p_data["longitude"])
        aspected_signs = _get_aspected_signs(p, sign_idx)
        transits[p] = TransitPosition(
            planet=p,
            sign=sign,
            sign_index=sign_idx,
            degree_in_sign=deg,
            is_retrograde=p_data["is_retrograde"],
            aspected_sign_indices=aspected_signs
        )

    return transits


def evaluate_double_transit(d1: D1Chart, target_date: datetime,
                            tz_offset_hours: float = 0.0) -> DoubleTransitResult:
    """
    Evaluates whether the classical Double Transit (Jupiter + Saturn) is activating
    the marriage axis for the given natal chart at target_date.
    `target_date` is treated as UTC unless `tz_offset_hours` is supplied.
    """
    transits = get_transit_positions(target_date, tz_offset_hours=tz_offset_hours)
    jup = transits["Jupiter"]
    sat = transits["Saturn"]

    lagna_sign_idx = d1.ascendant_sign_index
    seventh_sign_idx = d1.houses[7].sign_index
    lagna_lord = d1.houses[1].lord
    seventh_lord = d1.houses[7].lord

    lagna_lord_sign_idx = d1.planets[lagna_lord].sign_index
    seventh_lord_sign_idx = d1.planets[seventh_lord].sign_index
    venus_sign_idx = d1.planets["Venus"].sign_index

    # Check Jupiter activations
    j_7th_house = seventh_sign_idx in jup.aspected_sign_indices
    j_7th_lord = seventh_lord_sign_idx in jup.aspected_sign_indices
    j_lagna = lagna_sign_idx in jup.aspected_sign_indices
    j_lagna_lord = lagna_lord_sign_idx in jup.aspected_sign_indices
    j_venus = venus_sign_idx in jup.aspected_sign_indices

    # Check Saturn activations
    s_7th_house = seventh_sign_idx in sat.aspected_sign_indices
    s_7th_lord = seventh_lord_sign_idx in sat.aspected_sign_indices
    s_lagna = lagna_sign_idx in sat.aspected_sign_indices
    s_lagna_lord = lagna_lord_sign_idx in sat.aspected_sign_indices

    # Jupiter activates marriage if it impacts 7th house/lord, Lagna/lord, or Venus
    jupiter_active = j_7th_house or j_7th_lord or j_lagna or j_lagna_lord or j_venus
    # Saturn activates marriage if it impacts 7th house/lord or Lagna/lord
    saturn_active = s_7th_house or s_7th_lord or s_lagna or s_lagna_lord

    is_double_transit = jupiter_active and saturn_active

    # Compute continuous scores (0 to 100)
    jup_score = 0.0
    if j_7th_house: jup_score += 40.0
    if j_7th_lord: jup_score += 25.0
    if j_lagna: jup_score += 15.0
    if j_lagna_lord: jup_score += 10.0
    if j_venus: jup_score += 10.0
    jup_score = min(jup_score, 100.0)

    sat_score = 0.0
    if s_7th_house: sat_score += 45.0
    if s_7th_lord: sat_score += 30.0
    if s_lagna: sat_score += 15.0
    if s_lagna_lord: sat_score += 10.0
    sat_score = min(sat_score, 100.0)

    total_score = 0.0
    if is_double_transit:
        total_score = (jup_score * 0.55) + (sat_score * 0.45)
    elif jupiter_active:
        total_score = jup_score * 0.4
    elif saturn_active:
        total_score = sat_score * 0.3

    desc_parts = []
    if is_double_transit:
        desc_parts.append(f"Double Transit fulfilled: Transit Jupiter in {jup.sign} and Saturn in {sat.sign} both aspect the marriage axis.")
    elif jupiter_active:
        desc_parts.append(f"Partial Transit: Transit Jupiter in {jup.sign} aspects marriage axis, but Saturn in {sat.sign} does not.")
    elif saturn_active:
        desc_parts.append(f"Partial Transit: Transit Saturn in {sat.sign} aspects marriage axis, but Jupiter in {jup.sign} does not.")
    else:
        desc_parts.append(f"No transit support on marriage axis (Jupiter in {jup.sign}, Saturn in {sat.sign}).")

    return DoubleTransitResult(
        is_active=is_double_transit,
        jupiter_aspects_7th_house=j_7th_house,
        jupiter_aspects_7th_lord=j_7th_lord,
        jupiter_aspects_lagna=j_lagna,
        jupiter_aspects_lagna_lord=j_lagna_lord,
        jupiter_aspects_venus=j_venus,
        saturn_aspects_7th_house=s_7th_house,
        saturn_aspects_7th_lord=s_7th_lord,
        saturn_aspects_lagna=s_lagna,
        saturn_aspects_lagna_lord=s_lagna_lord,
        jupiter_score=jup_score,
        saturn_score=sat_score,
        total_transit_score=total_score,
        description=" ".join(desc_parts)
    )


# ---------------------------------------------------------------------------
# Full Gochara: all grahas judged from the natal Moon, with vedha and Sade Sati
# (classical Gochara tables; see docs/knowledge/02_modern_specialized.md #233)
# ---------------------------------------------------------------------------

GOOD_HOUSES_FROM_MOON: Dict[str, List[int]] = {
    "Sun": [3, 6, 10, 11],
    "Moon": [1, 3, 6, 7, 10, 11],
    "Mars": [3, 6, 11],
    "Mercury": [2, 4, 6, 8, 10, 11],
    "Jupiter": [2, 5, 7, 9, 11],
    "Venus": [1, 2, 3, 4, 5, 8, 9, 11, 12],
    "Saturn": [3, 6, 11],
}

# Gochara vedha: planet transiting a good house X is "pierced" (cancelled)
# when another planet transits the paired house (counted from the Moon).
VEDHA_MAP: Dict[str, Dict[int, int]] = {
    "Sun": {3: 9, 6: 12, 10: 4, 11: 5},
    "Moon": {1: 5, 3: 9, 6: 12, 7: 2, 10: 4, 11: 8},
    "Mars": {3: 12, 6: 9, 11: 5},
    "Mercury": {2: 5, 4: 3, 6: 9, 8: 1, 10: 8, 11: 12},
    "Jupiter": {2: 12, 5: 4, 7: 3, 9: 10, 11: 8},
    "Venus": {1: 8, 2: 7, 3: 1, 4: 10, 5: 9, 8: 5, 9: 11, 11: 12},
    "Saturn": {3: 12, 6: 9, 11: 5},
}


@dataclass
class GocharaEntry:
    planet: str
    sign: str
    house_from_moon: int
    house_from_lagna: int
    favourable: bool
    vedha_by: List[str]
    note: str


@dataclass
class SadeSatiReading:
    active: bool
    phase: str
    saturn_house_from_moon: int
    note: str


@dataclass
class GocharaReading:
    entries: Dict[str, GocharaEntry]
    sade_sati: SadeSatiReading
    summary: str


def _house_from(reference_sign_index: int, sign_index: int) -> int:
    return ((sign_index - reference_sign_index) % 12) + 1


def evaluate_gochara(d1: D1Chart, target_date: datetime,
                     tz_offset_hours: float = 0.0) -> GocharaReading:
    """Judges all nine graha transits from the natal Moon (and lagna), with vedha.
    `target_date` is treated as UTC unless `tz_offset_hours` is supplied."""
    transits = get_transit_positions(target_date, tz_offset_hours=tz_offset_hours)
    moon_sign_idx = d1.planets["Moon"].sign_index
    lagna_sign_idx = d1.ascendant_sign_index

    houses_from_moon = {p: _house_from(moon_sign_idx, t.sign_index)
                        for p, t in transits.items()}

    entries: Dict[str, GocharaEntry] = {}
    favourable_planets: List[str] = []
    for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        t = transits[planet]
        h_moon = houses_from_moon[planet]
        h_lagna = _house_from(lagna_sign_idx, t.sign_index)
        favourable = h_moon in GOOD_HOUSES_FROM_MOON[planet]
        vedha_by: List[str] = []
        if favourable:
            vedha_house = VEDHA_MAP.get(planet, {}).get(h_moon)
            if vedha_house is not None:
                vedha_by = [p for p in VEDHA_MAP if p != planet
                            and houses_from_moon.get(p) == vedha_house]
        effective = favourable and not vedha_by
        if effective:
            favourable_planets.append(planet)
        if effective:
            note = f"{planet} transits H{h_moon} from Moon — supportive gochara."
        elif favourable and vedha_by:
            note = (f"{planet} transits H{h_moon} from Moon (normally supportive) "
                    f"but vedha from {', '.join(vedha_by)} cancels it.")
        else:
            note = f"{planet} transits H{h_moon} from Moon — watchful gochara."
        entries[planet] = GocharaEntry(
            planet=planet, sign=t.sign, house_from_moon=h_moon,
            house_from_lagna=h_lagna, favourable=effective,
            vedha_by=vedha_by, note=note,
        )
    for node in ("Rahu", "Ketu"):
        t = transits[node]
        entries[node] = GocharaEntry(
            planet=node, sign=t.sign,
            house_from_moon=houses_from_moon[node],
            house_from_lagna=_house_from(lagna_sign_idx, t.sign_index),
            favourable=False, vedha_by=[],
            note=f"{node} transits H{houses_from_moon[node]} from Moon (karmic pressure point).",
        )

    saturn_house = houses_from_moon["Saturn"]
    if saturn_house == 12:
        phase = "Rising phase (Saturn in 12th from Moon)"
    elif saturn_house == 1:
        phase = "Peak phase (Saturn over the natal Moon)"
    elif saturn_house == 2:
        phase = "Setting phase (Saturn in 2nd from Moon)"
    else:
        phase = "Not active"
    sade_sati = SadeSatiReading(
        active=saturn_house in (12, 1, 2),
        phase=phase,
        saturn_house_from_moon=saturn_house,
        note=("Sade Sati is active — " + phase + ". Traditionally a restructuring period: "
              "discipline, health routines and patience matter more than expansion.")
        if saturn_house in (12, 1, 2) else
        f"Sade Sati is not active (Saturn in H{saturn_house} from the natal Moon).",
    )

    if favourable_planets:
        summary = ("Supportive gochara now: " + ", ".join(favourable_planets) +
                   f". Saturn is in H{saturn_house} from the Moon." )
    else:
        summary = (f"No planet is giving clean supportive gochara from the Moon right now; "
                   f"Saturn is in H{saturn_house} from the Moon.")
    return GocharaReading(entries=entries, sade_sati=sade_sati, summary=summary)
