"""
SweetAstro Core Astronomical and Astrological Constants.
Frozen specification SA-SPEC-V1.0.
"""

from typing import Dict, List, Tuple

# 12 Signs of the Zodiac (1-indexed: 1 = Aries, 12 = Pisces)
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

SIGN_TO_INDEX: Dict[str, int] = {sign: idx + 1 for idx, sign in enumerate(SIGNS)}
INDEX_TO_SIGN: Dict[int, str] = {idx + 1: sign for idx, sign in enumerate(SIGNS)}

# Sign Rulers (Parashara Standard)
SIGN_LORDS: Dict[str, str] = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

# 9 Planets (Navagrahas)
PLANETS = [
    "Sun", "Moon", "Mars", "Mercury", "Jupiter",
    "Venus", "Saturn", "Rahu", "Ketu"
]

# Physical 7 Planets (for Jaimini Karakas)
PHYSICAL_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

# Natural Classification
NATURAL_BENEFICS = ["Jupiter", "Venus", "Mercury", "Moon"]
NATURAL_MALEFICS = ["Saturn", "Mars", "Rahu", "Ketu", "Sun"]

# Exaltation Sign & Peak Degree (Parashara)
EXALTATION_DATA: Dict[str, Tuple[str, float]] = {
    "Sun": ("Aries", 10.0),
    "Moon": ("Taurus", 3.0),
    "Mars": ("Capricorn", 28.0),
    "Mercury": ("Virgo", 15.0),
    "Jupiter": ("Cancer", 5.0),
    "Venus": ("Pisces", 27.0),
    "Saturn": ("Libra", 20.0),
    "Rahu": ("Taurus", 20.0),  # Some texts say Gemini
    "Ketu": ("Scorpio", 20.0),
}

# Debilitation Sign & Deep Debilitation Degree
DEBILITATION_DATA: Dict[str, Tuple[str, float]] = {
    "Sun": ("Libra", 10.0),
    "Moon": ("Scorpio", 3.0),
    "Mars": ("Cancer", 28.0),
    "Mercury": ("Pisces", 15.0),
    "Jupiter": ("Capricorn", 5.0),
    "Venus": ("Virgo", 27.0),
    "Saturn": ("Aries", 20.0),
    "Rahu": ("Scorpio", 20.0),
    "Ketu": ("Taurus", 20.0),
}

# Moolatrikona Signs & Degree Ranges
MOOLATRIKONA_RANGES: Dict[str, Tuple[str, float, float]] = {
    "Sun": ("Leo", 0.0, 20.0),
    "Moon": ("Taurus", 3.0, 30.0),
    "Mars": ("Aries", 0.0, 12.0),
    "Mercury": ("Virgo", 15.0, 20.0),
    "Jupiter": ("Sagittarius", 0.0, 10.0),
    "Venus": ("Libra", 0.0, 15.0),
    "Saturn": ("Aquarius", 0.0, 20.0),
}

# Own Signs
OWN_SIGNS: Dict[str, List[str]] = {
    "Sun": ["Leo"],
    "Moon": ["Cancer"],
    "Mars": ["Aries", "Scorpio"],
    "Mercury": ["Gemini", "Virgo"],
    "Jupiter": ["Sagittarius", "Pisces"],
    "Venus": ["Taurus", "Libra"],
    "Saturn": ["Capricorn", "Aquarius"],
}

# Permanent Planetary Friendships (Naisargika Sambandha)
PERMANENT_FRIENDSHIPS: Dict[str, Dict[str, List[str]]] = {
    "Sun": {
        "friends": ["Moon", "Mars", "Jupiter"],
        "neutrals": ["Mercury"],
        "enemies": ["Venus", "Saturn", "Rahu", "Ketu"],
    },
    "Moon": {
        "friends": ["Sun", "Mercury"],
        "neutrals": ["Mars", "Jupiter", "Venus", "Saturn"],
        "enemies": ["Rahu", "Ketu"],
    },
    "Mars": {
        "friends": ["Sun", "Moon", "Jupiter"],
        "neutrals": ["Venus", "Saturn"],
        "enemies": ["Mercury", "Rahu", "Ketu"],
    },
    "Mercury": {
        "friends": ["Sun", "Venus"],
        "neutrals": ["Mars", "Jupiter", "Saturn"],
        "enemies": ["Moon"],
    },
    "Jupiter": {
        "friends": ["Sun", "Moon", "Mars"],
        "neutrals": ["Saturn"],
        "enemies": ["Mercury", "Venus"],
    },
    "Venus": {
        "friends": ["Mercury", "Saturn", "Rahu"],
        "neutrals": ["Mars", "Jupiter"],
        "enemies": ["Sun", "Moon"],
    },
    "Saturn": {
        "friends": ["Mercury", "Venus", "Rahu"],
        "neutrals": ["Jupiter"],
        "enemies": ["Sun", "Moon", "Mars"],
    },
}

# 27 Nakshatras (13°20' each) and their Vimshottari Lords
NAKSHATRAS = [
    {"name": "Ashwini", "lord": "Ketu"},
    {"name": "Bharani", "lord": "Venus"},
    {"name": "Krittika", "lord": "Sun"},
    {"name": "Rohini", "lord": "Moon"},
    {"name": "Mrigashira", "lord": "Mars"},
    {"name": "Ardra", "lord": "Rahu"},
    {"name": "Punarvasu", "lord": "Jupiter"},
    {"name": "Pushya", "lord": "Saturn"},
    {"name": "Ashlesha", "lord": "Mercury"},
    {"name": "Magha", "lord": "Ketu"},
    {"name": "Purva Phalguni", "lord": "Venus"},
    {"name": "Uttara Phalguni", "lord": "Sun"},
    {"name": "Hasta", "lord": "Moon"},
    {"name": "Chitra", "lord": "Mars"},
    {"name": "Swati", "lord": "Rahu"},
    {"name": "Vishakha", "lord": "Jupiter"},
    {"name": "Anuradha", "lord": "Saturn"},
    {"name": "Jyeshtha", "lord": "Mercury"},
    {"name": "Mula", "lord": "Ketu"},
    {"name": "Purva Ashadha", "lord": "Venus"},
    {"name": "Uttara Ashadha", "lord": "Sun"},
    {"name": "Shravana", "lord": "Moon"},
    {"name": "Dhanishta", "lord": "Mars"},
    {"name": "Shatabhisha", "lord": "Rahu"},
    {"name": "Purva Bhadrapada", "lord": "Jupiter"},
    {"name": "Uttara Bhadrapada", "lord": "Saturn"},
    {"name": "Revati", "lord": "Mercury"},
]

# Vimshottari Dasha Order and Duration in Solar Years (Total = 120.0)
VIMSHOTTARI_YEARS: Dict[str, float] = {
    "Ketu": 7.0,
    "Venus": 20.0,
    "Sun": 6.0,
    "Moon": 10.0,
    "Mars": 7.0,
    "Rahu": 18.0,
    "Jupiter": 16.0,
    "Saturn": 19.0,
    "Mercury": 17.0,
}

VIMSHOTTARI_ORDER = [
    "Ketu", "Venus", "Sun", "Moon", "Mars",
    "Rahu", "Jupiter", "Saturn", "Mercury"
]

# True Solar Year Days
DAYS_PER_YEAR = 365.2425

# Combustion Orbs (Degrees from Sun, classical Parashara)
COMBUSTION_ORBS: Dict[str, float] = {
    "Moon": 12.0,
    "Mars": 17.0,
    "Mercury": 14.0,  # 12 when retrograde
    "Jupiter": 11.0,
    "Venus": 10.0,    # 8 when retrograde
    "Saturn": 15.0,
}
