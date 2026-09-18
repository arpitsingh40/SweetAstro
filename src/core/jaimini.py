"""
Jaimini Astrology Calculations.
Computes 7 Chara Karakas (including Darakaraka DK for spouse/marriage timing),
Upapada Lagna (UL), and Arudha Lagna (AL).
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .constants import PHYSICAL_PLANETS, INDEX_TO_SIGN, SIGN_LORDS
from .chart import D1Chart
from .navamsa import NavamsaChart


@dataclass
class JaiminiKarakas:
    atmakaraka: str        # AK (Highest degree)
    amatyakaraka: str      # AmK (2nd)
    bhratrukaraka: str     # BK (3rd)
    matrukaraka: str       # MK (4th)
    putrakaraka: str       # PK (5th)
    gnatikaraka: str       # GK (6th)
    darakaraka: str        # DK (Lowest degree - spouse/marriage karaka)
    karaka_map: Dict[str, str]       # planet -> karaka_code
    planet_degrees: Dict[str, float] # planet -> degree_in_sign


@dataclass
class JaiminiPoints:
    arudha_lagna_sign: str
    arudha_lagna_index: int
    upapada_lagna_sign: str
    upapada_lagna_index: int
    darakaraka: str
    darakaraka_sign: str
    darakaraka_navamsa_sign: str


def calculate_chara_karakas(d1: D1Chart) -> JaiminiKarakas:
    """
    Computes 7 Chara Karakas by sorting the 7 physical planets by degree within sign descending.
    The planet with lowest degree is Darakaraka (DK).
    """
    planet_degs: List[Tuple[str, float]] = []
    deg_map: Dict[str, float] = {}

    for p in PHYSICAL_PLANETS:
        p_deg = d1.planets[p].degree_in_sign
        planet_degs.append((p, p_deg))
        deg_map[p] = p_deg

    # Sort descending by degree
    sorted_planets = sorted(planet_degs, key=lambda x: x[1], reverse=True)

    karaka_names = ["AK", "AmK", "BK", "MK", "PK", "GK", "DK"]
    karaka_map: Dict[str, str] = {}
    for idx, (p, _) in enumerate(sorted_planets):
        karaka_map[p] = karaka_names[idx]

    return JaiminiKarakas(
        atmakaraka=sorted_planets[0][0],
        amatyakaraka=sorted_planets[1][0],
        bhratrukaraka=sorted_planets[2][0],
        matrukaraka=sorted_planets[3][0],
        putrakaraka=sorted_planets[4][0],
        gnatikaraka=sorted_planets[5][0],
        darakaraka=sorted_planets[6][0],
        karaka_map=karaka_map,
        planet_degrees=deg_map
    )


def _compute_bhava_arudha(d1: D1Chart, house_num: int) -> int:
    """
    Computes the Arudha (Pada) sign index for a house (1 to 12).

    Single source of truth: delegates to core.arudha.calculate_arudha_pada so
    the Upapada/Arudha Lagna logic cannot drift between modules. The classical
    exception (pada in the same house or 7th from it -> shift to the 10th from
    the pada) lives there.
    """
    from .arudha import calculate_arudha_pada

    pada = calculate_arudha_pada(d1, house_num)
    return pada.sign_index


def calculate_jaimini_points(d1: D1Chart, navamsa: NavamsaChart) -> JaiminiPoints:
    """
    Computes Arudha Lagna (AL), Upapada Lagna (UL, Arudha of 12th house),
    and Darakaraka coordinates in D1 and D9.
    """
    karakas = calculate_chara_karakas(d1)
    dk_planet = karakas.darakaraka

    al_idx = _compute_bhava_arudha(d1, 1)
    ul_idx = _compute_bhava_arudha(d1, 12)

    return JaiminiPoints(
        arudha_lagna_sign=INDEX_TO_SIGN[al_idx],
        arudha_lagna_index=al_idx,
        upapada_lagna_sign=INDEX_TO_SIGN[ul_idx],
        upapada_lagna_index=ul_idx,
        darakaraka=dk_planet,
        darakaraka_sign=d1.planets[dk_planet].sign,
        darakaraka_navamsa_sign=navamsa.planets[dk_planet].d9_sign
    )
