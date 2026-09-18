"""
Jaimini Arudha Pada System.
Calculates Arudha Padas (AL, UL, A7, etc.) and Upapada Lagna analysis
for marriage prediction.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import (
    SIGNS, SIGN_TO_INDEX, INDEX_TO_SIGN, SIGN_LORDS,
    NATURAL_BENEFICS, NATURAL_MALEFICS
)
from .chart import D1Chart
from .navamsa import NavamsaChart


@dataclass
class ArudhaPada:
    name: str
    house_from_lagna: int
    sign: str
    sign_index: int
    lord: str
    lord_house: int
    lord_dignity: str
    planets_in: List[str] = field(default_factory=list)
    benefics_in: List[str] = field(default_factory=list)
    malefics_in: List[str] = field(default_factory=list)
    aspects_from: List[str] = field(default_factory=list)


@dataclass
class UpapadaAnalysis:
    ul_sign: str
    ul_sign_index: int
    ul_house_from_lagna: int
    ul_lord: str
    ul_lord_house: int
    ul_lord_dignity: str
    ul_lord_d9_dignity: str
    ul2_sign: str
    ul2_sign_index: int
    ul2_house_from_lagna: int
    ul2_lord: str
    ul2_lord_house: int
    ul2_lord_dignity: str
    planets_in_ul: List[str] = field(default_factory=list)
    benefics_in_ul: List[str] = field(default_factory=list)
    malefics_in_ul: List[str] = field(default_factory=list)
    aspects_to_ul: List[str] = field(default_factory=list)
    planets_in_ul2: List[str] = field(default_factory=list)
    benefics_in_ul2: List[str] = field(default_factory=list)
    malefics_in_ul2: List[str] = field(default_factory=list)
    marriage_sustained: bool = False
    delay_factors: List[str] = field(default_factory=list)
    strength_factors: List[str] = field(default_factory=list)
    overall_assessment: str = ""


def calculate_arudha_pada(
    d1: D1Chart,
    house_num: int,
    pada_name: str = "A"
) -> ArudhaPada:
    """
    Calculate Arudha Pada of any house.

    Algorithm:
    1. Find the house sign and its lord
    2. Count from house sign to lord's position (inclusive)
    3. Count the same number forward from lord -> raw pada
    4. Classical exception: if the raw pada falls in the house itself or the
       7th from that house, take the 10th sign from the pada.
    """
    house_sign_idx = d1.houses[house_num].sign_index
    house_lord = d1.houses[house_num].lord

    if house_lord not in d1.planets:
        return ArudhaPada(
            name=pada_name,
            house_from_lagna=0,
            sign="Unknown",
            sign_index=0,
            lord="Unknown",
            lord_house=0,
            lord_dignity="Unknown"
        )

    lord_sign_idx = d1.planets[house_lord].sign_index

    # Count from house sign to lord (inclusive)
    if lord_sign_idx >= house_sign_idx:
        count = lord_sign_idx - house_sign_idx + 1
    else:
        count = (12 - house_sign_idx) + lord_sign_idx + 1

    # Count the same number forward from the lord (1-based inclusive arithmetic)
    raw_pada_idx = (lord_sign_idx + count - 2) % 12 + 1

    # Classical exception: the pada may not fall in the same bhava or the 7th
    # from it; in that case take the 10th sign from the pada itself.
    seventh_from_house = (house_sign_idx + 5) % 12 + 1
    if raw_pada_idx == house_sign_idx or raw_pada_idx == seventh_from_house:
        raw_pada_idx = (raw_pada_idx + 8) % 12 + 1  # 10th sign from the pada

    lagna_idx = d1.ascendant_sign_index

    pada_sign = INDEX_TO_SIGN[raw_pada_idx]
    pada_lord = SIGN_LORDS[pada_sign]

    # Calculate house from Lagna
    if raw_pada_idx >= lagna_idx:
        house_from_lagna = raw_pada_idx - lagna_idx + 1
    else:
        house_from_lagna = (12 - lagna_idx) + raw_pada_idx + 1

    # Lord's house and dignity
    lord_house = d1.planets[pada_lord].house if pada_lord in d1.planets else 0
    lord_dignity = d1.planets[pada_lord].dignity if pada_lord in d1.planets else "Unknown"

    # Planets in the pada sign
    planets_in = [
        p for p, state in d1.planets.items()
        if state.sign_index == raw_pada_idx
    ]
    benefics_in = [p for p in planets_in if p in NATURAL_BENEFICS]
    malefics_in = [p for p in planets_in if p in NATURAL_MALEFICS]

    # Planets aspecting the pada's house (per-planet classical aspects)
    pada_house = next((h for h, hs in d1.houses.items() if hs.sign_index == raw_pada_idx), 0)
    aspects_from = [
        p for p, state in d1.planets.items()
        if pada_house and pada_house in state.aspecting_houses
    ]

    return ArudhaPada(
        name=pada_name,
        house_from_lagna=house_from_lagna,
        sign=pada_sign,
        sign_index=raw_pada_idx,
        lord=pada_lord,
        lord_house=lord_house,
        lord_dignity=lord_dignity,
        planets_in=planets_in,
        benefics_in=benefics_in,
        malefics_in=malefics_in,
        aspects_from=aspects_from
    )


def calculate_upapada(d1: D1Chart, d9: NavamsaChart) -> UpapadaAnalysis:
    """
    Calculate Upapada Lagna (UL) and UL2 analysis for marriage.

    UL = Arudha Pada of 12th house
    UL2 = 2nd sign from UL (marriage sustainability indicator)
    """
    # Calculate UL (Arudha Pada of 12th house)
    ul = calculate_arudha_pada(d1, 12, "UL")

    # Calculate UL2 (2nd sign from UL)
    ul2_sign_idx = (ul.sign_index % 12) + 1
    ul2_sign = INDEX_TO_SIGN[ul2_sign_idx]
    ul2_lord = SIGN_LORDS[ul2_sign]

    lagna_idx = d1.ascendant_sign_index
    if ul2_sign_idx >= lagna_idx:
        ul2_house = ul2_sign_idx - lagna_idx + 1
    else:
        ul2_house = (12 - lagna_idx) + ul2_sign_idx + 1

    ul2_lord_house = d1.planets[ul2_lord].house if ul2_lord in d1.planets else 0
    ul2_lord_dignity = d1.planets[ul2_lord].dignity if ul2_lord in d1.planets else "Unknown"

    # Planets in UL
    planets_in_ul = [
        p for p, state in d1.planets.items()
        if state.sign_index == ul.sign_index
    ]
    benefics_in_ul = [p for p in planets_in_ul if p in NATURAL_BENEFICS]
    malefics_in_ul = [p for p in planets_in_ul if p in NATURAL_MALEFICS]

    # Planets in UL2
    planets_in_ul2 = [
        p for p, state in d1.planets.items()
        if state.sign_index == ul2_sign_idx
    ]
    benefics_in_ul2 = [p for p in planets_in_ul2 if p in NATURAL_BENEFICS]
    malefics_in_ul2 = [p for p in planets_in_ul2 if p in NATURAL_MALEFICS]

    # Aspects to UL (per-planet classical aspects on the UL's house)
    ul_house = ul.house_from_lagna
    aspects_to_ul = [
        p for p, state in d1.planets.items()
        if ul_house and ul_house in state.aspecting_houses
    ]

    # UL lord's dignity in D9
    ul_lord_d9_dignity = "Unknown"
    if ul.lord in d9.planets:
        ul_lord_d9_dignity = d9.planets[ul.lord].d9_dignity

    # Assessment
    delay_factors = []
    strength_factors = []

    # UL2 analysis (marriage sustainability)
    if malefics_in_ul2:
        delay_factors.append(f"Malefics in UL2: {', '.join(malefics_in_ul2)}")
    if benefics_in_ul2:
        strength_factors.append(f"Benefics in UL2: {', '.join(benefics_in_ul2)}")

    # UL lord dignity
    if ul.lord_dignity in ["Debilitated", "Enemy"]:
        delay_factors.append(f"UL lord {ul.lord} {ul.lord_dignity} in D1")
    elif ul.lord_dignity in ["Exalted", "Own", "Moolatrikona"]:
        strength_factors.append(f"UL lord {ul.lord} {ul.lord_dignity} in D1")

    if ul_lord_d9_dignity in ["Debilitated", "Enemy"]:
        delay_factors.append(f"UL lord {ul.lord} {ul_lord_d9_dignity} in D9")
    elif ul_lord_d9_dignity in ["Exalted", "Own", "Moolatrikona"]:
        strength_factors.append(f"UL lord {ul.lord} {ul_lord_d9_dignity} in D9")

    # UL2 lord dignity
    if ul2_lord_dignity in ["Debilitated", "Enemy"]:
        delay_factors.append(f"UL2 lord {ul2_lord} {ul2_lord_dignity}")
    elif ul2_lord_dignity in ["Exalted", "Own", "Moolatrikona"]:
        strength_factors.append(f"UL2 lord {ul2_lord} {ul2_lord_dignity}")

    # Malefics aspecting UL
    ul_aspects = [p for p in aspects_to_ul if p in NATURAL_MALEFICS]
    if ul_aspects:
        delay_factors.append(f"Malefics aspect UL: {', '.join(ul_aspects)}")

    # Assessment
    marriage_sustained = len(delay_factors) == 0 or len(strength_factors) > len(delay_factors)

    if len(strength_factors) > len(delay_factors):
        overall = "Strong marriage potential"
    elif len(delay_factors) > len(strength_factors):
        overall = "Marriage challenges indicated"
    else:
        overall = "Mixed indicators"

    return UpapadaAnalysis(
        ul_sign=ul.sign,
        ul_sign_index=ul.sign_index,
        ul_house_from_lagna=ul.house_from_lagna,
        ul_lord=ul.lord,
        ul_lord_house=ul.lord_house,
        ul_lord_dignity=ul.lord_dignity,
        ul_lord_d9_dignity=ul_lord_d9_dignity,
        planets_in_ul=planets_in_ul,
        benefics_in_ul=benefics_in_ul,
        malefics_in_ul=malefics_in_ul,
        aspects_to_ul=aspects_to_ul,

        ul2_sign=ul2_sign,
        ul2_sign_index=ul2_sign_idx,
        ul2_house_from_lagna=ul2_house,
        ul2_lord=ul2_lord,
        ul2_lord_house=ul2_lord_house,
        ul2_lord_dignity=ul2_lord_dignity,
        planets_in_ul2=planets_in_ul2,
        benefics_in_ul2=benefics_in_ul2,
        malefics_in_ul2=malefics_in_ul2,

        marriage_sustained=marriage_sustained,
        delay_factors=delay_factors,
        strength_factors=strength_factors,
        overall_assessment=overall
    )
