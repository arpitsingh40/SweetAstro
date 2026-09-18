"""
D9 (Navamsa) Chart Engine.
Deterministic calculation of Navamsa Lagna, Navamsa planetary signs,
dignities in D9, and Vargottama status.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .constants import SIGNS, INDEX_TO_SIGN, SIGN_LORDS
from .chart import D1Chart, _calculate_dignity, _get_sign_and_deg


@dataclass
class NavamsaPlanetState:
    name: str
    d1_sign: str
    d9_sign: str
    d9_sign_index: int       # 1 to 12
    d9_degree_in_sign: float # 0.0 to 30.0 (projected)
    d9_house: int            # 1 to 12 from Navamsa Lagna
    d9_dignity: str          # Exalted, Own, Debilitated, etc.
    is_vargottama: bool      # Same sign in D1 and D9


@dataclass
class NavamsaChart:
    ascendant_d9_sign: str
    ascendant_d9_sign_index: int
    ascendant_is_vargottama: bool
    planets: Dict[str, NavamsaPlanetState]
    houses: Dict[int, List[str]]  # House 1..12 -> list of planet names in D9
    seventh_house_sign: str
    seventh_house_lord: str
    seventh_house_occupants: List[str]


def calculate_navamsa_sign_index(lon_deg: float) -> Tuple[int, float]:
    """
    Returns (navamsa_sign_index_1_based, projected_degree_in_navamsa_sign).
    Each navamsa is exactly 3° 20' = 200 minutes of arc = 3.3333333333 degrees.
    """
    norm = lon_deg % 360.0
    navamsa_span = 30.0 / 9.0  # 3.3333333333333335
    total_navamsa_index = int(norm / navamsa_span)  # 0 to 107
    navamsa_sign_idx = (total_navamsa_index % 12) + 1

    # Exact degree within the 30° span of the Navamsa sign
    remainder_deg = norm - (total_navamsa_index * navamsa_span)
    projected_deg = (remainder_deg / navamsa_span) * 30.0

    return navamsa_sign_idx, projected_deg


def calculate_navamsa_chart(d1: D1Chart) -> NavamsaChart:
    """
    Computes complete D9 Navamsa chart derived from D1 chart.
    """
    # D9 Ascendant
    asc_d9_sign_idx, _ = calculate_navamsa_sign_index(d1.ascendant_deg)
    asc_d9_sign = INDEX_TO_SIGN[asc_d9_sign_idx]
    asc_is_vargottama = (d1.ascendant_sign == asc_d9_sign)

    # Initialize 12 Navamsa houses
    houses: Dict[int, List[str]] = {h: [] for h in range(1, 13)}

    planets: Dict[str, NavamsaPlanetState] = {}
    for p_name, p_state in d1.planets.items():
        d9_sign_idx, d9_deg = calculate_navamsa_sign_index(p_state.longitude)
        d9_sign = INDEX_TO_SIGN[d9_sign_idx]
        d9_house = ((d9_sign_idx - asc_d9_sign_idx + 12) % 12) + 1
        d9_dignity = _calculate_dignity(p_name, d9_sign, d9_deg, allow_moolatrikona=False)
        is_vargottama = (p_state.sign == d9_sign)

        nav_planet = NavamsaPlanetState(
            name=p_name,
            d1_sign=p_state.sign,
            d9_sign=d9_sign,
            d9_sign_index=d9_sign_idx,
            d9_degree_in_sign=d9_deg,
            d9_house=d9_house,
            d9_dignity=d9_dignity,
            is_vargottama=is_vargottama
        )
        planets[p_name] = nav_planet
        houses[d9_house].append(p_name)

    # 7th House in D9
    seventh_sign_idx = ((asc_d9_sign_idx + 6 - 1) % 12) + 1
    seventh_sign = INDEX_TO_SIGN[seventh_sign_idx]
    seventh_lord = SIGN_LORDS[seventh_sign]
    seventh_occupants = houses[7]

    return NavamsaChart(
        ascendant_d9_sign=asc_d9_sign,
        ascendant_d9_sign_index=asc_d9_sign_idx,
        ascendant_is_vargottama=asc_is_vargottama,
        planets=planets,
        houses=houses,
        seventh_house_sign=seventh_sign,
        seventh_house_lord=seventh_lord,
        seventh_house_occupants=seventh_occupants
    )
