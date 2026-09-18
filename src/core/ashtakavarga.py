"""
Ashtakavarga (Bhinnashtakavarga + Sarvashtakavarga).

Classical Parashari bindu system: for each of the seven planets, eight
contributors (the seven planets + Lagna) donate bindus to specific houses
counted from their own sign. The resulting 12-sign bindu map measures how
much support each sign (and therefore each natal house) has for that planet
and, in the Sarvashtakavarga, overall.

Sources: BPHS Ch. 66 (Ashtakavarga Adhyaya); standard published tables.
Invariant checks (tests): BAV totals Sun 48, Moon 49, Mars 39, Mercury 54,
Jupiter 56, Venus 52, Saturn 39; SAV total = 337.

Transit use: a transit planet passing a sign with more bindus for itself
(BAV) or a high SAV value traditionally gives more supportive results.
"""

from dataclasses import dataclass
from typing import Dict, List

from .chart import D1Chart
from .constants import SIGNS

BAV_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

# Canonical BAV totals (used as an internal integrity test)
BAV_TOTALS: Dict[str, int] = {
    "Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
    "Jupiter": 56, "Venus": 52, "Saturn": 39,
}
SAV_TOTAL = 337

# House offsets counted from each contributor's own sign.
# ASHTAKA_TABLES[target_planet][contributor] -> list of houses (1-12)
ASHTAKA_TABLES: Dict[str, Dict[str, List[int]]] = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus": [6, 7, 12],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11],
        "Moon": [1, 3, 6, 7, 10, 11],
        "Mars": [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus": [3, 4, 5, 7, 9, 10, 11],
        "Saturn": [3, 5, 6, 11],
        "Lagna": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12],
        "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus": [2, 5, 6, 9, 10, 11],
        "Saturn": [3, 5, 6, 12],
        "Lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12],
        "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 4, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11, 12],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 8, 9, 10, 11],
        "Lagna": [1, 2, 3, 4, 5, 8, 9],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus": [6, 11, 12],
        "Saturn": [3, 5, 6, 11],
        "Lagna": [1, 3, 4, 6, 10, 11],
    },
}

CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]


@dataclass
class AshtakavargaResult:
    bav: Dict[str, List[int]]        # planet -> 12 sign values (Aries..Pisces)
    sav: List[int]                   # 12 sign values
    sav_by_house: Dict[int, int]     # house -> SAV bindus in its sign
    bav_by_house: Dict[str, Dict[int, int]]  # planet -> house -> BAV bindus

    def sav_of_sign(self, sign_index: int) -> int:
        return self.sav[(sign_index - 1) % 12]

    def bav_of_sign(self, planet: str, sign_index: int) -> int:
        return self.bav[planet][(sign_index - 1) % 12]


def _contributor_sign_indices(d1: D1Chart) -> Dict[str, int]:
    out = {name: d1.planets[name].sign_index for name in BAV_PLANETS}
    out["Lagna"] = d1.ascendant_sign_index
    return out


def bhinnashtakavarga(d1: D1Chart, planet: str) -> List[int]:
    """Returns 12 bindu values (0-8) indexed from Aries for one planet."""
    if planet not in ASHTAKA_TABLES:
        raise ValueError(f"Ashtakavarga is not defined for {planet!r}")
    table = ASHTAKA_TABLES[planet]
    sign_of = _contributor_sign_indices(d1)
    bindus = [0] * 12
    for contributor in CONTRIBUTORS:
        base = sign_of[contributor]
        for house in table[contributor]:
            bindus[(base - 1 + house - 1) % 12] += 1
    return bindus


def sarvashtakavarga(bav: Dict[str, List[int]]) -> List[int]:
    sav = [0] * 12
    for planet in BAV_PLANETS:
        values = bav[planet]
        for i, v in enumerate(values):
            sav[i] += v
    return sav


def calculate_ashtakavarga(d1: D1Chart) -> AshtakavargaResult:
    """Full BAV + SAV for the chart (houses are whole-sign from lagna)."""
    bav = {planet: bhinnashtakavarga(d1, planet) for planet in BAV_PLANETS}
    sav = sarvashtakavarga(bav)

    sav_by_house: Dict[int, int] = {}
    bav_by_house: Dict[str, Dict[int, int]] = {}
    for planet in BAV_PLANETS:
        bav_by_house[planet] = {}
    for house_num in range(1, 13):
        sign_idx = d1.houses[house_num].sign_index
        sav_by_house[house_num] = sav[(sign_idx - 1) % 12]
        for planet in BAV_PLANETS:
            bav_by_house[planet][house_num] = bav[planet][(sign_idx - 1) % 12]

    return AshtakavargaResult(bav=bav, sav=sav,
                              sav_by_house=sav_by_house, bav_by_house=bav_by_house)


def house_support_label(sav_value: int) -> str:
    """Qualitative banding for SAV values (classical guidance: 25+ good, <20 weak)."""
    if sav_value >= 30:
        return "very strong"
    if sav_value >= 25:
        return "strong"
    if sav_value >= 20:
        return "moderate"
    return "weak"


def transit_bindu_note(d1: D1Chart, planet: str, transit_sign_index: int) -> str:
    """One-line BAV strength note for a transit planet entering a sign."""
    if planet not in ASHTAKA_TABLES:
        return ""
    bindus = bhinnashtakavarga(d1, planet)[(transit_sign_index - 1) % 12]
    sav = sarvashtakavarga({p: bhinnashtakavarga(d1, p) for p in BAV_PLANETS})[(transit_sign_index - 1) % 12]
    label = "strong" if bindus >= 5 else ("average" if bindus >= 4 else "weak")
    return (f"Transit {planet} in {SIGNS[(transit_sign_index - 1) % 12]}: "
            f"{bindus}/8 bindus for {planet} ({label}), SAV {sav}/56.")
