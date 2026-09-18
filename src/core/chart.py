"""
D1 (Rashi) Chart Engine.
Deterministic calculation of Ascendant, Houses, House Lords, Planetary Placements,
Dignities, Combustion, Retrogression, and Parashara Aspects.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import (
    SIGNS, SIGN_TO_INDEX, INDEX_TO_SIGN, SIGN_LORDS, PLANETS,
    NATURAL_BENEFICS, NATURAL_MALEFICS, EXALTATION_DATA, DEBILITATION_DATA,
    MOOLATRIKONA_RANGES, OWN_SIGNS, PERMANENT_FRIENDSHIPS, COMBUSTION_ORBS,
    NAKSHATRAS
)
from .ephemeris import (
    datetime_to_julian_day, calculate_lahiri_ayanamsha,
    calculate_ascendant, calculate_planet_positions
)


@dataclass
class PlanetState:
    name: str
    longitude: float
    sign: str
    sign_index: int          # 1 to 12
    degree_in_sign: float    # 0.0 to 30.0
    house: int               # 1 to 12 from Lagna
    speed: float
    is_retrograde: bool
    is_combust: bool
    dignity: str             # Exalted, Moolatrikona, Own, Friend, Neutral, Enemy, Debilitated
    nakshatra: str
    nakshatra_pada: int
    nakshatra_lord: str
    aspecting_houses: List[int] = field(default_factory=list)
    aspecting_planets: List[str] = field(default_factory=list)


@dataclass
class HouseState:
    house_num: int           # 1 to 12
    sign: str
    sign_index: int          # 1 to 12
    lord: str
    occupants: List[str] = field(default_factory=list)
    aspecting_planets: List[str] = field(default_factory=list)


@dataclass
class D1Chart:
    jd: float
    ayanamsha: float
    ascendant_deg: float
    ascendant_sign: str
    ascendant_sign_index: int
    ascendant_degree_in_sign: float
    planets: Dict[str, PlanetState]
    houses: Dict[int, HouseState]

    @property
    def seventh_house(self) -> HouseState:
        return self.houses[7]

    @property
    def seventh_lord(self) -> PlanetState:
        return self.planets[self.houses[7].lord]


def _get_sign_and_deg(lon: float) -> Tuple[str, int, float]:
    """Returns (sign_name, 1-based sign_index, degree_in_sign)."""
    norm = lon % 360.0
    sign_idx = int(norm // 30) + 1
    deg = norm % 30.0
    return INDEX_TO_SIGN[sign_idx], sign_idx, deg


def _get_nakshatra_and_pada(lon: float) -> Tuple[str, int, str]:
    """Returns (nakshatra_name, pada_number (1-4), nakshatra_lord)."""
    norm = lon % 360.0
    total_minutes = norm * 60.0
    nak_minutes = 800.0  # 13° 20' = 800 minutes
    nak_idx = int(total_minutes // nak_minutes) % 27
    rem_minutes = total_minutes % nak_minutes
    pada = int(rem_minutes // 200.0) + 1

    nak = NAKSHATRAS[nak_idx]
    return nak["name"], pada, nak["lord"]


def _calculate_dignity(planet: str, sign: str, deg_in_sign: float,
                       allow_moolatrikona: bool = True) -> str:
    """
    Calculates planetary dignity (Exalted, Moolatrikona, Own, Friend, Neutral,
    Enemy, Debilitated).

    `allow_moolatrikona=False` is used for divisional charts, where the D1
    degree range is meaningless (moolatrikona is a D1 concept).
    """
    if planet in ["Rahu", "Ketu"]:
        if planet in EXALTATION_DATA and sign == EXALTATION_DATA[planet][0]:
            return "Exalted"
        if planet in DEBILITATION_DATA and sign == DEBILITATION_DATA[planet][0]:
            return "Debilitated"
        return "Neutral"

    # 1. Exaltation
    ex_sign, ex_deg = EXALTATION_DATA[planet]
    if sign == ex_sign:
        return "Exalted"

    # 2. Debilitation
    deb_sign, deb_deg = DEBILITATION_DATA[planet]
    if sign == deb_sign:
        return "Debilitated"

    # 3. Moolatrikona
    if allow_moolatrikona and planet in MOOLATRIKONA_RANGES:
        m_sign, m_start, m_end = MOOLATRIKONA_RANGES[planet]
        if sign == m_sign and (m_start <= deg_in_sign <= m_end):
            return "Moolatrikona"

    # 4. Own Sign
    if planet in OWN_SIGNS and sign in OWN_SIGNS[planet]:
        return "Own"

    # 5. Friendship with Sign Lord
    sign_lord = SIGN_LORDS[sign]
    if sign_lord == planet:
        return "Own"

    friendships = PERMANENT_FRIENDSHIPS.get(planet, {})
    if sign_lord in friendships.get("friends", []):
        return "Friend"
    elif sign_lord in friendships.get("enemies", []):
        return "Enemy"
    else:
        return "Neutral"


def _calculate_aspects(planet: str, house: int) -> List[int]:
    """Returns the list of 1-based house numbers aspected by the planet."""
    aspects = []
    # All planets aspect 7th from their position
    aspects.append(((house + 6 - 1) % 12) + 1)

    # Special aspects
    if planet == "Mars":
        aspects.append(((house + 3 - 1) % 12) + 1)  # 4th house
        aspects.append(((house + 7 - 1) % 12) + 1)  # 8th house
    elif planet == "Jupiter":
        aspects.append(((house + 4 - 1) % 12) + 1)  # 5th house
        aspects.append(((house + 8 - 1) % 12) + 1)  # 9th house
    elif planet == "Saturn":
        aspects.append(((house + 2 - 1) % 12) + 1)  # 3rd house
        aspects.append(((house + 9 - 1) % 12) + 1)  # 10th house
    elif planet in ["Rahu", "Ketu"]:
        aspects.append(((house + 4 - 1) % 12) + 1)  # 5th house
        aspects.append(((house + 8 - 1) % 12) + 1)  # 9th house

    return sorted(list(set(aspects)))


def calculate_d1_chart(
    year: int, month: int, day: int,
    hour: int, minute: int, second: float = 0.0,
    tz_offset_hours: float = 5.5,
    lat: float = 28.6139, lon: float = 77.2090
) -> D1Chart:
    """
    Computes complete deterministic D1 natal chart.
    Default coords: New Delhi, India (+5.5 UTC).
    """
    jd = datetime_to_julian_day(year, month, day, hour, minute, second, tz_offset_hours)
    ayanamsha = calculate_lahiri_ayanamsha(jd)
    asc_deg = calculate_ascendant(jd, lat, lon, ayanamsha)
    asc_sign, asc_sign_idx, asc_deg_in_sign = _get_sign_and_deg(asc_deg)

    # Calculate raw planetary positions
    raw_planets = calculate_planet_positions(jd, ayanamsha)

    # Calculate Sun position for combustion checks
    sun_lon = raw_planets["Sun"]["longitude"]

    # Initialize Houses (Whole Sign: House 1 = Lagna sign)
    houses: Dict[int, HouseState] = {}
    for h in range(1, 13):
        h_sign_idx = ((asc_sign_idx + (h - 1) - 1) % 12) + 1
        h_sign = INDEX_TO_SIGN[h_sign_idx]
        h_lord = SIGN_LORDS[h_sign]
        houses[h] = HouseState(
            house_num=h,
            sign=h_sign,
            sign_index=h_sign_idx,
            lord=h_lord,
            occupants=[],
            aspecting_planets=[]
        )

    # Compute Planet States
    planets: Dict[str, PlanetState] = {}
    for p_name, p_data in raw_planets.items():
        lon = p_data["longitude"]
        sign, sign_idx, deg_in_sign = _get_sign_and_deg(lon)
        # House calculation from Lagna sign
        house_num = ((sign_idx - asc_sign_idx + 12) % 12) + 1

        # Combustion
        is_combust = False
        if p_name not in ["Sun", "Rahu", "Ketu"]:
            orb = COMBUSTION_ORBS.get(p_name, 12.0)
            if p_name in ("Mercury", "Venus") and p_data["is_retrograde"]:
                orb = 12.0 if p_name == "Mercury" else 8.0
            diff = abs((lon - sun_lon + 180.0) % 360.0 - 180.0)
            if diff <= orb:
                is_combust = True

        dignity = _calculate_dignity(p_name, sign, deg_in_sign)
        nak_name, pada, nak_lord = _get_nakshatra_and_pada(lon)
        aspected_houses = _calculate_aspects(p_name, house_num)

        planet_state = PlanetState(
            name=p_name,
            longitude=lon,
            sign=sign,
            sign_index=sign_idx,
            degree_in_sign=deg_in_sign,
            house=house_num,
            speed=p_data["speed"],
            is_retrograde=p_data["is_retrograde"],
            is_combust=is_combust,
            dignity=dignity,
            nakshatra=nak_name,
            nakshatra_pada=pada,
            nakshatra_lord=nak_lord,
            aspecting_houses=aspected_houses,
            aspecting_planets=[]
        )
        planets[p_name] = planet_state
        houses[house_num].occupants.append(p_name)

    # Link Aspects between planets and houses
    for p_name, p_state in planets.items():
        for h_num in p_state.aspecting_houses:
            houses[h_num].aspecting_planets.append(p_name)
            # All planets residing in that house are aspected by this planet
            for occ in houses[h_num].occupants:
                if occ != p_name:
                    p_state.aspecting_planets.append(occ)

    return D1Chart(
        jd=jd,
        ayanamsha=ayanamsha,
        ascendant_deg=asc_deg,
        ascendant_sign=asc_sign,
        ascendant_sign_index=asc_sign_idx,
        ascendant_degree_in_sign=asc_deg_in_sign,
        planets=planets,
        houses=houses
    )
