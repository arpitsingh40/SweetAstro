"""
Classical Shadbala (six-fold strength) — corrected components.

This is the *classical* system, kept separate from the existing 360-point
`shadbala.py` analytical index (which stays labelled as an approximation).

Implemented components (formulas: BPHS Shadbala chapters as standardised in
B. V. Raman, *Graha and Bhava Balas*; values in virupas, 60 virupas = 1 rupa):

- Sthana Bala: Uchcha + Saptavargaja + Ojhayugma + Kendradi + Drekkana
- Dig Bala (longitude-based, equal-house cusps from the Lagna degree)
- Kala Bala: Natonnata + Paksha + Tribhaga + Dina + Hora + Ayana
- Chesta Bala (motional; speed-ratio convention, documented)
- Naisargika Bala (fixed natural order)
- Drik Bala (net benefic/malefic aspect value on the planet)

Deliberately NOT computed yet (documented, never guessed):
- Varsha Bala and Masa Bala (year/month lord require the solar-year frame
  conventions of a specific panchanga tradition; see P2 open questions)
- Chesta Kendra from true mean longitudes (needs mean elements; the
  speed-ratio convention below is declared instead).

Ishta/Kashta phala:
    Ishta  = sqrt(Uchcha x Chesta)
    Kashta = sqrt((60 - Uchcha) x (60 - Chesta))

Minimum strength (Rashmi Bala, rupas; commonly cited BPHS values):
    Sun 6.5 · Moon 6.0 · Mars 5.0 · Mercury 7.0 · Jupiter 6.5 · Venus 5.5 · Saturn 5.0

Interpretive only — no accuracy claim.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Optional

from .chart import D1Chart
from .constants import (
    DEBILITATION_DATA, EXALTATION_DATA, INDEX_TO_SIGN, NATURAL_BENEFICS,
    OWN_SIGNS, PLANETS, PHYSICAL_PLANETS, SIGN_LORDS,
)
from .planet_factors import natural_relation

NAISARGIKA_BALA: Dict[str, float] = {
    "Sun": 60.0, "Moon": 51.43, "Venus": 42.86, "Jupiter": 34.29,
    "Mercury": 25.71, "Mars": 17.14, "Saturn": 8.57,
}

# Minimum required strength in rupas (commonly cited classical values)
RASHMI_MINIMUM: Dict[str, float] = {
    "Sun": 6.5, "Moon": 6.0, "Mars": 5.0, "Mercury": 7.0,
    "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0,
}

_SAPTAVARGA = ("D1", "D2", "D3", "D7", "D9", "D12", "D30")

# Dignity values for Saptavargaja Bala (virupas)
_DIGNITY_POINTS = {
    "Moolatrikona": 45.0, "Own": 30.0, "Exalted": 30.0,
    "Adhimitra": 22.5, "Mitra": 15.0, "Sama": 7.5,
    "Shatru": 3.75, "Adhishatru": 1.875,
}

# Mean daily geocentric motions (deg/day) for the Chesta speed-ratio convention
_MEAN_MOTION = {
    "Mars": 0.524, "Mercury": 1.383, "Jupiter": 0.0831,
    "Venus": 1.602, "Saturn": 0.0335,
}

_DIG_STRONG_POINT = {
    "Jupiter": 0.0, "Mercury": 0.0,      # Lagna
    "Sun": 270.0, "Mars": 270.0,          # 10th
    "Saturn": 180.0,                       # 7th
    "Moon": 90.0, "Venus": 90.0,          # 4th
}

# Ayana preference: True = strong in northern declination
_AYANA_NORTH = {"Moon": True, "Mercury": True, "Jupiter": True, "Venus": True,
                "Sun": False, "Mars": False, "Saturn": False}

_DAY_STRONG = ("Sun", "Jupiter", "Venus")
_NIGHT_STRONG = ("Moon", "Mars", "Saturn")

# Drik Bala: aspect value by house distance from the aspecting planet
_DRISHTI_VALUE = {7: 60.0, 4: 45.0, 8: 45.0, 5: 30.0, 9: 30.0, 3: 15.0, 10: 15.0}
_SPECIAL_FULL = {"Mars": (4, 8), "Jupiter": (5, 9), "Saturn": (3, 10)}

# Planetary hour (hora) sequence from the day lord (Chaldean order)
_HORA_ORDER = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
_WEEKDAY_LORD = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]


def _angular_distance(a: float, b: float) -> float:
    """Shortest angular separation in degrees (0..180)."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _absolute_longitude(sign: str, deg: float) -> float:
    from .constants import SIGN_TO_INDEX
    return ((SIGN_TO_INDEX[sign] - 1) * 30.0 + deg) % 360.0


def uchcha_bala(planet: str, longitude: float) -> float:
    """Distance of the planet from its deep-debilitation point / 3 (0..60)."""
    if planet not in DEBILITATION_DATA:
        return 0.0
    sign, deg = DEBILITATION_DATA[planet]
    deb_point = _absolute_longitude(sign, deg)
    return round(min(60.0, _angular_distance(longitude % 360.0, deb_point) / 3.0), 2)


def ojhayugma_bala(planet: str, sign_index: int) -> float:
    """15 virupas when the sign parity suits the planet (Moon/Venus even)."""
    odd = (sign_index % 2) == 1
    prefer_even = planet in ("Moon", "Venus")
    return 15.0 if (odd != prefer_even) else 0.0


def kendradi_bala(house: int) -> float:
    if house in (1, 4, 7, 10):
        return 60.0
    if house in (2, 5, 8, 11):
        return 30.0
    return 15.0


def drekkana_bala(planet: str, deg_in_sign: float) -> float:
    third = min(2, int(deg_in_sign // 10.0))
    if planet in ("Sun", "Mars", "Jupiter"):
        return 15.0 if third == 0 else 0.0
    if planet in ("Mercury", "Saturn"):
        return 15.0 if third == 1 else 0.0
    return 15.0 if third == 2 else 0.0  # Moon, Venus


def dig_bala_classical(planet: str, longitude: float, ascendant_deg: float) -> float:
    """Longitude-based Dig Bala (equal-house cusps from the Lagna degree)."""
    strong = (ascendant_deg + _DIG_STRONG_POINT.get(planet, 0.0)) % 360.0
    zero_point = (strong + 180.0) % 360.0
    return round(min(60.0, _angular_distance(longitude % 360.0, zero_point) / 3.0), 2)


def saptavargaja_bala(d1: D1Chart, planet: str) -> float:
    """
    Strength across the seven vargas (D1, D2, D3, D7, D9, D12, D30).

    Per varga: sign ownership/exaltation counts directly; otherwise the
    compound (panchadha) relationship with the varga sign lord is used.
    Temporal friendship is taken from the D1 positions (declared convention:
    compound maitri is a D1 relationship).
    """
    from .navamsa import calculate_navamsa_chart
    from .vargas import calculate_varga_chart

    d9 = None
    if "D9" in _SAPTAVARGA:
        d9 = calculate_navamsa_chart(d1)

    total = 0.0
    for varga in _SAPTAVARGA:
        if varga == "D1":
            sign = d1.planets[planet].sign
            deg = d1.planets[planet].degree_in_sign
        elif varga == "D9":
            sign = d9.planets[planet].d9_sign
            deg = None  # type: ignore[assignment]  # moolatrikona is D1-only
        else:
            vc = calculate_varga_chart(d1, varga)
            sign = vc.planets[planet].varga_sign
            deg = None  # type: ignore[assignment]
        total += _varga_dignity_points(d1, planet, sign, deg)
    return round(total, 2)


def _varga_dignity_points(d1: D1Chart, planet: str, sign: str,
                          deg: Optional[float]) -> float:
    # Moolatrikona is only meaningful in D1 (with degree range)
    if deg is not None:
        from .constants import MOOLATRIKONA_RANGES
        if planet in MOOLATRIKONA_RANGES:
            m_sign, m_start, m_end = MOOLATRIKONA_RANGES[planet]
            if sign == m_sign and m_start <= deg <= m_end:
                return _DIGNITY_POINTS["Moolatrikona"]
    if planet in OWN_SIGNS and sign in OWN_SIGNS[planet]:
        return _DIGNITY_POINTS["Own"]
    if planet in EXALTATION_DATA and sign == EXALTATION_DATA[planet][0]:
        return _DIGNITY_POINTS["Exalted"]

    lord = SIGN_LORDS[sign]
    natural = natural_relation(planet, lord)
    from .planet_factors import temporal_relation
    temporal = temporal_relation(d1.planets[planet].sign_index,
                                 d1.planets[lord].sign_index)
    if natural == "Friend":
        key = "Adhimitra" if temporal == "Friend" else "Sama"
    elif natural == "Enemy":
        key = "Sama" if temporal == "Friend" else "Adhishatru"
    else:
        key = "Mitra" if temporal == "Friend" else "Shatru"
    return _DIGNITY_POINTS[key]


def natonnata_bala(planet: str, is_daytime: bool) -> float:
    if planet == "Mercury":
        return 60.0
    if is_daytime:
        return 60.0 if planet in _DAY_STRONG else 0.0
    return 60.0 if planet in _NIGHT_STRONG else 0.0


def paksha_bala(planet: str, sun_moon_elongation: float) -> float:
    """Waxing strength: benefics (elongation/3), malefics inverted; Moon x2."""
    elong = min(180.0, abs(sun_moon_elongation) % 360.0)
    if elong > 180.0:
        elong = 360.0 - elong
    value = elong / 3.0 if planet in NATURAL_BENEFICS else (180.0 - elong) / 3.0
    if planet == "Moon":
        value *= 2.0
    return round(value, 2)


def tribhaga_bala(planet: str, hour_local: float) -> float:
    """Which third of the day/night the birth falls in (Jupiter always 60)."""
    if planet == "Jupiter":
        return 60.0
    daytime = 6.0 <= hour_local < 18.0
    if daytime:
        third = min(2, int((hour_local - 6.0) // 4.0))
        holders = ("Mercury", "Sun", "Saturn")
    else:
        night_hour = (hour_local - 18.0) % 24.0
        third = min(2, int(night_hour // 4.0))
        holders = ("Moon", "Venus", "Mars")
    return 60.0 if planet == holders[third] else 0.0


def dina_bala(planet: str, weekday: int) -> float:
    """45 virupas to the weekday lord (weekday: 0=Monday .. 6=Sunday)."""
    return 45.0 if planet == _WEEKDAY_LORD[weekday % 7] else 0.0


def hora_lord(weekday: int, hour_local: float) -> str:
    """Planetary hour lord (approx. sunrise 06:00 convention, declared)."""
    day_lord = _WEEKDAY_LORD[weekday % 7]
    index = (hour_local - 6.0) % 24.0
    step = int(index // 1.0)
    start = _HORA_ORDER.index(day_lord)
    return _HORA_ORDER[(start + step) % 7]


def hora_bala(planet: str, weekday: int, hour_local: float) -> float:
    return 60.0 if planet == hora_lord(weekday, hour_local) else 0.0


def ayana_bala(planet: str, tropical_longitude: float, obliquity_rad: float) -> float:
    """Declination-based strength (0..60) using the planet's ayana preference."""
    lam = math.radians(tropical_longitude % 360.0)
    declination = math.degrees(math.asin(math.sin(lam) * math.sin(obliquity_rad)))
    north = declination >= 0.0
    favourable = (north == _AYANA_NORTH.get(planet, True))
    signed = declination if favourable else -declination
    value = 60.0 * (23.45 + signed) / 46.9
    return round(min(60.0, max(0.0, value)), 2)


def chesta_bala(planet: str, speed: float, is_retrograde: bool) -> float:
    """
    Motional strength — speed-ratio convention (declared approximation of the
    classical Chesta Kendra): retrograde = 60; direct = 60 x (1 - speed/mean).
    """
    if planet not in _MEAN_MOTION:
        return 0.0
    if is_retrograde:
        return 60.0
    ratio = min(1.0, abs(speed) / _MEAN_MOTION[planet])
    return round(60.0 * (1.0 - ratio), 2)


def drik_bala(d1: D1Chart, planet: str) -> float:
    """Net aspectual strength: benefic aspects add, malefic aspects subtract."""
    total = 0.0
    target_sign = d1.planets[planet].sign_index
    for other in PHYSICAL_PLANETS:
        if other == planet:
            continue
        distance = ((target_sign - d1.planets[other].sign_index) % 12) + 1
        value = _DRISHTI_VALUE.get(distance, 0.0)
        if other in _SPECIAL_FULL and distance in _SPECIAL_FULL[other]:
            value = 60.0
        if value == 0.0:
            continue
        total += value if other in NATURAL_BENEFICS else -value
    return round(total, 2)


@dataclass
class ClassicalShadbala:
    planet: str
    sthana: float
    uchcha: float
    saptavargaja: float
    ojhayugma: float
    kendradi: float
    drekkana: float
    dig: float
    kala: float
    natonnata: float
    paksha: float
    tribhaga: float
    dina: float
    hora: float
    ayana: float
    varsha: float
    masa: float
    chesta: float
    naisargika: float
    drik: float
    total_virupas: float
    total_rupas: float
    minimum_rupas: float
    ratio: float
    category: str
    ishta_phala: float
    kashta_phala: float
    components: Dict[str, float] = field(default_factory=dict)
    notes: str = ""


def calculate_classical_shadbala(
    d1: D1Chart,
    planet: str,
    *,
    is_daytime: bool = True,
    hour_local: float = 12.0,
    weekday: int = 0,
    sun_moon_elongation: float = 0.0,
    obliquity_rad: float = 0.409,
    varsha_lord: Optional[str] = None,
    masa_lord: Optional[str] = None,
) -> ClassicalShadbala:
    """Assembles the six classical components for one planet."""
    ps = d1.planets[planet]
    uchcha = uchcha_bala(planet, ps.longitude)
    sapta = saptavargaja_bala(d1, planet)
    ojha = ojhayugma_bala(planet, ps.sign_index)
    kendra = kendradi_bala(ps.house)
    drekkana = drekkana_bala(planet, ps.degree_in_sign)
    sthana = uchcha + sapta + ojha + kendra + drekkana

    dig = dig_bala_classical(planet, ps.longitude, d1.ascendant_deg)

    natonnata = natonnata_bala(planet, is_daytime)
    paksha = paksha_bala(planet, sun_moon_elongation)
    tribhaga = tribhaga_bala(planet, hour_local)
    dina = dina_bala(planet, weekday)
    hora = hora_bala(planet, weekday, hour_local)
    tropical = (ps.longitude + d1.ayanamsha) % 360.0
    ayana = ayana_bala(planet, tropical, obliquity_rad)
    varsha = 15.0 if varsha_lord and planet == varsha_lord else 0.0
    masa = 30.0 if masa_lord and planet == masa_lord else 0.0
    kala = (natonnata + paksha + tribhaga + dina + hora + ayana + varsha + masa)

    chesta = chesta_bala(planet, ps.speed, ps.is_retrograde)
    naisargika = NAISARGIKA_BALA.get(planet, 0.0)
    drik = drik_bala(d1, planet)

    total = sthana + dig + kala + chesta + naisargika + drik
    minimum = RASHMI_MINIMUM.get(planet, 0.0)
    ratio = round(total / 60.0 / minimum, 3) if minimum else 0.0
    if ratio >= 1.0:
        category = "Strong"
    elif ratio >= 0.9:
        category = "Borderline"
    else:
        category = "Weak"

    ishta = round(math.sqrt(max(0.0, uchcha) * max(0.0, chesta)), 2)
    kashta = round(math.sqrt(max(0.0, 60.0 - uchcha) * max(0.0, 60.0 - chesta)), 2)

    return ClassicalShadbala(
        planet=planet, sthana=round(sthana, 2), uchcha=uchcha,
        saptavargaja=sapta, ojhayugma=ojha, kendradi=kendra, drekkana=drekkana,
        dig=dig, kala=round(kala, 2), natonnata=natonnata, paksha=paksha,
        tribhaga=tribhaga, dina=dina, hora=hora, ayana=ayana,
        varsha=varsha, masa=masa, chesta=chesta,
        naisargika=naisargika, drik=drik,
        total_virupas=round(total, 2), total_rupas=round(total / 60.0, 2),
        minimum_rupas=minimum, ratio=ratio, category=category,
        ishta_phala=ishta, kashta_phala=kashta,
        components={
            "sthana": round(sthana, 2), "dig": dig, "kala": round(kala, 2),
            "chesta": chesta, "naisargika": naisargika, "drik": drik,
        },
        notes=("Varsha/Masa Bala not computed (needs a declared solar-year "
               "convention); Chesta uses the documented speed-ratio convention."),
    )
