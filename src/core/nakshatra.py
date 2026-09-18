"""
Nakshatra deep layer + natal Panchanga.

- NAKSHATRA_DETAILS: classical attributes for all 27 nakshatras (deity, gana,
  yoni, nature, symbol, trait keywords). Source tradition: BPHS / classical
  nakshatra tables as catalogued in docs/knowledge/02_modern_specialized.md.
- compute_natal_panchanga: panchanga elements at the exact birth instant
  (tithi, nakshatra + pada, yoga, karana, vara), computed from sidereal
  Sun/Moon longitudes rather than sunrise.

Interpretation use only — not predictive claims.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .constants import INDEX_TO_SIGN
from .ephemeris import (
    calculate_lahiri_ayanamsha, calculate_planet_positions, datetime_to_julian_day,
)
from .panchanga import YOGA_NAMES, karana_name, tithi_name


@dataclass
class NakshatraDetail:
    name: str
    lord: str
    deity: str
    gana: str          # Deva / Manushya / Rakshasa
    yoni: str          # animal symbol
    nature: str        # Dhruva / Chara / Ugra / Tikshna / Mishra / Kshipra / Mridu
    symbol: str
    traits: List[str]
    watch: str


@dataclass
class NatalPanchanga:
    tithi: str
    paksha: str
    tithi_index: int
    nakshatra: str
    nakshatra_pada: int
    nakshatra_lord: str
    deity: str
    gana: str
    yoni: str
    nature: str
    traits: List[str]
    watch: str
    moon_sign: str
    sun_sign: str
    yoga: str
    karana: str
    vara: str
    vara_sanskrit: str


_NAKSHATRA_ROWS = [
    ("Ashwini", "Ketu", "Ashwini Kumaras", "Deva", "Horse", "Kshipra", "Horse's head",
     ["quick starts", "healing instinct", "pioneering"], "impatience"),
    ("Bharani", "Venus", "Yama", "Manushya", "Elephant", "Ugra", "Yoni",
     ["endurance", "discipline", "creative pressure"], "rigidity or excess"),
    ("Krittika", "Sun", "Agni", "Rakshasa", "Sheep", "Mishra", "Razor / flame",
     ["sharp discrimination", "purification", "drive"], "harshness or criticism"),
    ("Rohini", "Moon", "Brahma", "Manushya", "Serpent", "Dhruva", "Ox-cart",
     ["growth", "charm", "material comfort"], "possessiveness"),
    ("Mrigashira", "Mars", "Soma", "Deva", "Serpent", "Mridu", "Deer's head",
     ["curiosity", "gentle searching", "refreshment"], "restlessness"),
    ("Ardra", "Rahu", "Rudra", "Manushya", "Dog", "Tikshna", "Teardrop / diamond",
     ["insight through storms", "research", "depth"], "turbulence or anxiety"),
    ("Punarvasu", "Jupiter", "Aditi", "Deva", "Cat", "Chara", "Quiver of arrows",
     ["renewal", "generosity", "return of good"], "scattered energy"),
    ("Pushya", "Saturn", "Brihaspati", "Deva", "Sheep", "Kshipra", "Cow's udder / lotus",
     ["nourishment", "teaching", "stability"], "over-caution"),
    ("Ashlesha", "Mercury", "Nagas", "Rakshasa", "Cat", "Tikshna", "Coiled serpent",
     ["penetrating mind", "strategy", "healing skill"], "manipulation or suspicion"),
    ("Magha", "Ketu", "Pitris", "Rakshasa", "Rat", "Ugra", "Royal throne",
     ["lineage", "authority", "pride in roots"], "ego or inherited burdens"),
    ("Purva Phalguni", "Venus", "Bhaga", "Manushya", "Rat", "Ugra", "Front legs of a bed",
     ["charm", "recreation", "warm partnership"], "indulgence"),
    ("Uttara Phalguni", "Sun", "Aryaman", "Manushya", "Cow", "Dhruva", "Back legs of a bed",
     ["service", "loyalty", "steady partnership"], "dependence"),
    ("Hasta", "Moon", "Savitar", "Deva", "Buffalo", "Kshipra", "Hand",
     ["skill", "craftsmanship", "resourcefulness"], "overwork"),
    ("Chitra", "Mars", "Tvashtar", "Rakshasa", "Tiger", "Mridu", "Bright jewel",
     ["design", "charisma", "building visible things"], "vanity"),
    ("Swati", "Rahu", "Vayu", "Deva", "Buffalo", "Chara", "Young sprout in wind",
     ["independence", "trade", "adaptability"], "indecision"),
    ("Vishakha", "Jupiter", "Indragni", "Rakshasa", "Tiger", "Mishra", "Triumphal arch",
     ["determination", "goal focus", "crossing thresholds"], "obsession"),
    ("Anuradha", "Saturn", "Mitra", "Deva", "Deer", "Mridu", "Lotus garland",
     ["friendship", "devotion", "group leadership"], "jealousy"),
    ("Jyeshtha", "Mercury", "Indra", "Rakshasa", "Deer", "Tikshna", "Earring / umbrella",
     ["seniority", "protection", "courage"], "dominance or secrecy"),
    ("Mula", "Ketu", "Nirriti", "Rakshasa", "Dog", "Tikshna", "Tied roots",
     ["root-cause research", "deep inquiry", "transformation"], "upheaval or nihilism"),
    ("Purva Ashadha", "Venus", "Apas", "Manushya", "Monkey", "Ugra", "Winnowing fan",
     ["persuasion", "cleansing", "invincibility"], "pride in speech"),
    ("Uttara Ashadha", "Sun", "Vishvedevas", "Manushya", "Mongoose", "Dhruva", "Elephant tusk",
     ["lasting victory", "leadership", "integrity"], "stubbornness"),
    ("Shravana", "Moon", "Vishnu", "Deva", "Monkey", "Chara", "Three footprints / ear",
     ["listening", "learning", "connection"], "gossip or scattered focus"),
    ("Dhanishta", "Mars", "Vasus", "Rakshasa", "Lion", "Chara", "Drum",
     ["rhythm", "wealth-building", "group music"], "loneliness or material fixation"),
    ("Shatabhisha", "Rahu", "Varuna", "Rakshasa", "Horse", "Chara", "Empty circle / 100 healers",
     ["healing", "research", "unconventional insight"], "isolation or secrecy"),
    ("Purva Bhadrapada", "Jupiter", "Aja Ekapada", "Manushya", "Lion", "Ugra", "Front of a funeral cot",
     ["intensity", "spiritual fire", "transformation"], "extremism"),
    ("Uttara Bhadrapada", "Saturn", "Ahirbudhnya", "Manushya", "Cow", "Dhruva", "Back of a funeral cot",
     ["depth", "patience", "serpent wisdom"], "inertia"),
    ("Revati", "Mercury", "Pushan", "Deva", "Elephant", "Mridu", "Fish / drum",
     ["guidance", "safe journeys", "compassion"], "over-giving or loss"),
]

NAKSHATRA_DETAILS: Dict[str, NakshatraDetail] = {
    row[0]: NakshatraDetail(
        name=row[0], lord=row[1], deity=row[2], gana=row[3], yoni=row[4],
        nature=row[5], symbol=row[6], traits=list(row[7]), watch=row[8],
    )
    for row in _NAKSHATRA_ROWS
}

_VARA_ENGLISH = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_VARA_SANSKRIT = ["Somavara", "Mangalavara", "Budhavara", "Guruvara",
                  "Shukravara", "Shanivara", "Ravivara"]

NAK_SPAN = 360.0 / 27.0


def nakshatra_detail(name: str) -> Optional[NakshatraDetail]:
    return NAKSHATRA_DETAILS.get(name)


def _nakshatra_from_longitude(longitude: float) -> tuple:
    norm = longitude % 360.0
    idx = int(norm // NAK_SPAN) % 27
    detail = NAKSHATRA_DETAILS[_NAKSHATRA_ROWS[idx][0]]
    pada = int((norm % NAK_SPAN) // (NAK_SPAN / 4.0)) + 1
    return detail, pada


def compute_natal_panchanga(
    year: int, month: int, day: int, hour: int, minute: int = 0,
    second: float = 0.0, tz_offset: float = 5.5,
) -> NatalPanchanga:
    """Panchanga elements at the exact birth instant (no sunrise dependency)."""
    jd = datetime_to_julian_day(year, month, day, hour, minute, second, tz_offset_hours=tz_offset)
    ayanamsha = calculate_lahiri_ayanamsha(jd)
    positions = calculate_planet_positions(jd, ayanamsha)
    sun_lon = positions["Sun"]["longitude"] % 360.0
    moon_lon = positions["Moon"]["longitude"] % 360.0

    elongation = (moon_lon - sun_lon) % 360.0
    tithi_index = int(elongation // 12.0) + 1
    paksha, tithi = tithi_name(tithi_index)

    yoga_index = int(((sun_lon + moon_lon) % 360.0) // (360.0 / 27.0)) % 27
    karana = karana_name(int(elongation // 6.0) % 60)

    detail, pada = _nakshatra_from_longitude(moon_lon)
    moon_sign = INDEX_TO_SIGN[int(moon_lon // 30) + 1]
    sun_sign = INDEX_TO_SIGN[int(sun_lon // 30) + 1]

    # Input hour/minute are local civil time — the timezone was already applied
    # for the Julian day, so the weekday must NOT add tz_offset again.
    local_dt = datetime(year, month, day, hour, minute, int(second))
    weekday = local_dt.weekday()

    return NatalPanchanga(
        tithi=tithi, paksha=paksha, tithi_index=tithi_index,
        nakshatra=detail.name, nakshatra_pada=pada, nakshatra_lord=detail.lord,
        deity=detail.deity, gana=detail.gana, yoni=detail.yoni, nature=detail.nature,
        traits=list(detail.traits), watch=detail.watch,
        moon_sign=moon_sign, sun_sign=sun_sign,
        yoga=YOGA_NAMES[yoga_index], karana=karana,
        vara=_VARA_ENGLISH[weekday], vara_sanskrit=_VARA_SANSKRIT[weekday],
    )
