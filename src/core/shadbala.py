"""
SweetAstro Analytical Strength Index (approximation of Shadbala concepts).

NOTE: This is NOT the classical six-fold Shadbala system. It is a transparent
analytical model using six simplified factors scored 0-60 each, for a maximum
of **360** marks. The dig-bala factor follows the classical directional
proportions (Jupiter/Mercury east, Sun/Mars south, Saturn west, Moon/Venus
north); the other factors are stand-ins. Always label output as an
"analytical strength index", never as classical Shadbala.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import (
    SIGN_LORDS, OWN_SIGNS, EXALTATION_DATA, DEBILITATION_DATA, PLANETS,
    NATURAL_BENEFICS, NATURAL_MALEFICS, INDEX_TO_SIGN, MOOLATRIKONA_RANGES,
)
from .chart import D1Chart, PlanetState

MAX_SHADBALA = 360.0

# Classical dig-bala directions: the kendra (house) of maximum directional strength
_DIGBALA_KENDRA = {
    "Jupiter": 1, "Mercury": 1,   # East — Lagna
    "Sun": 10, "Mars": 10,        # South — 10th house
    "Saturn": 7,                  # West — 7th house
    "Moon": 4, "Venus": 4,        # North — 4th house
}


@dataclass
class ShadbalaScore:
    planet: str
    sthanabala: float
    digbala: float
    ksepanabala: float
    debanalibala: float
    ayanalibala: float
    vayanalibala: float
    total_bala: float
    strength_category: str
    is_exalted: bool
    is_moolatrikona: bool
    is_own_sign: bool
    is_debilitated: bool
    is_fire_sign: bool


def _is_fire_sign(sign_index: int) -> bool:
    return sign_index in (1, 5, 9)


def _ksepa_bala(house: int, sign_index: int, deg_in_sign: float,
                is_retrograde: bool, speed: float) -> float:
    """Motional proxy: triangular peak at 19.5 deg within the sign, continuous
    across sign boundaries, falling to zero 15 deg away."""
    offset = abs(deg_in_sign - 19.5)
    if offset > 15.0:
        offset = 30.0 - offset if offset <= 30.0 else offset
    score = max(0.0, 60.0 * (1.0 - offset / 15.0))
    if is_retrograde:
        score *= 0.5
    speed_factor = min(1.0, abs(speed) / 1.0)
    score *= (0.5 + 0.5 * speed_factor)
    return round(min(60.0, max(0.0, score)), 1)


def sthana_bala(house: int, sign_index: int, lord_of_sign: str,
                planet: str, house_of_planet: int, is_in_own_sign: bool) -> float:
    score = 30.0
    house_score_map = {
        1: 60.0, 4: 40.0, 5: 35.0, 7: 30.0, 9: 40.0, 10: 45.0,
        2: 15.0, 3: 10.0, 6: 5.0, 8: 5.0, 11: 15.0, 12: 10.0,
    }
    score = house_score_map.get(house_of_planet, 30.0)
    if is_in_own_sign:
        score += 15.0
    elif lord_of_sign == planet:
        score += 10.0
    if house in (1, 4, 5, 7, 9, 10) and score > 30:
        score = min(60.0, score + 5.0)
    return round(min(60.0, max(0.0, score)), 1)


def digbala(planet: str, house: int) -> float:
    """Classical directional strength: 60 in the planet's directional kendra,
    falling linearly to 0 at the opposite point (6 signs away)."""
    strongest_house = _DIGBALA_KENDRA.get(planet)
    if strongest_house is None:
        return 0.0
    distance = min((house - strongest_house) % 12, (strongest_house - house) % 12)
    return round(60.0 * (1.0 - distance / 6.0), 1)


def debanalibala(sign_index: int, is_daytime: bool, is_benefic: bool) -> float:
    if is_daytime:
        return 60.0 if is_benefic else 20.0
    else:
        return 60.0 if not is_benefic else 20.0


def ayanalibala(month: int, sign_index: int, is_benefic: bool) -> float:
    if 3 <= month <= 5:
        if sign_index in (2, 5, 10):
            return 60.0 if is_benefic else 20.0
    elif 6 <= month <= 8:
        if sign_index in (1, 4, 7):
            return 60.0 if is_benefic else 20.0
    elif 9 <= month <= 11:
        if sign_index in (3, 6, 9):
            return 60.0 if is_benefic else 20.0
    else:
        if sign_index in (8, 11, 12):
            return 60.0 if is_benefic else 20.0
    return 40.0 if is_benefic else 25.0


def vayanalibala(house: int, is_retrograde: bool, is_combust: bool) -> float:
    score = 60.0
    if is_combust:
        score -= 30.0
    if house in (6, 8, 12):
        score -= 20.0
    if is_retrograde:
        score -= 10.0
    return round(max(0.0, score), 1)


def calculate_shadbala(planet_state: PlanetState, d1: D1Chart,
                       month: int = 6, is_daytime: bool = True
                       ) -> ShadbalaScore:
    p = planet_state
    sign_idx = p.sign_index
    lord = SIGN_LORDS.get(p.sign, "Unknown")
    is_in_own = p.sign in OWN_SIGNS.get(p.name, [])
    is_exalted = False
    if p.name in EXALTATION_DATA:
        ex_sign, _ = EXALTATION_DATA[p.name]
        is_exalted = (p.sign == ex_sign)
    is_mool = False
    if p.name in MOOLATRIKONA_RANGES:
        m_sign, m_start, m_end = MOOLATRIKONA_RANGES[p.name]
        is_mool = (p.sign == m_sign and m_start <= p.degree_in_sign <= m_end)
    is_debilitated = False
    if p.name in DEBILITATION_DATA:
        deb_sign, _ = DEBILITATION_DATA[p.name]
        is_debilitated = (p.sign == deb_sign)
    is_fire = _is_fire_sign(sign_idx)
    is_benefic = p.name in NATURAL_BENEFICS

    sthana = sthana_bala(p.house, sign_idx, lord, p.name,
                         d1.planets[lord].house if lord in d1.planets else p.house, is_in_own)
    dig = digbala(p.name, p.house)
    ksepa = _ksepa_bala(p.house, sign_idx, p.degree_in_sign, p.is_retrograde, p.speed)
    debana = debanalibala(sign_idx, is_daytime, is_benefic)
    ayanal = ayanalibala(month, sign_idx, is_benefic)
    vayana = vayanalibala(p.house, p.is_retrograde, p.is_combust)

    total = sthana + dig + ksepa + debana + ayanal + vayana
    if total >= 0.70 * MAX_SHADBALA:
        category = "Strong"
    elif total >= 0.50 * MAX_SHADBALA:
        category = "Moderate"
    elif total >= 0.30 * MAX_SHADBALA:
        category = "Weak"
    else:
        category = "Very Weak"

    return ShadbalaScore(
        planet=p.name, sthanabala=sthana, digbala=dig, ksepanabala=ksepa,
        debanalibala=debana, ayanalibala=ayanal, vayanalibala=vayana,
        total_bala=round(total, 1), strength_category=category,
        is_exalted=is_exalted, is_moolatrikona=is_mool, is_own_sign=is_in_own,
        is_debilitated=is_debilitated, is_fire_sign=is_fire,
    )
