"""
Per-planet classical factors (P0 of docs/research/planetary_analysis.md).

Deterministic computations that complete the planet picture beyond dignity and
aspects:

- Tatkalika (temporal) friendship and Panchadha compound maitri
- Avasthas: Baladi (5 age states), Jagradadi (3 states), Deeptadi (9 states)
- Sandhi (sign-junction weakness) and Gandanta (water->fire junction)
- Graha Yuddha (planetary war within 1 degree among the five non-luminaries)
- Parivartana (mutual sign exchange: Maha / Dainya / Khala)
- Own Bhinnashtakavarga bindus in the occupied sign

Declared conventions (variants exist in the tradition):
- Temporal friendship: planets in the 2nd/3rd/4th/10th/11th/12th from a planet
  are temporal friends; 1st/5th/6th/7th/8th/9th are temporal enemies.
- Graha Yuddha winner: the lower longitude (documented convention); only the
  five non-luminary physical planets can go to war.
- Deeptadi precedence follows the classical best-to-worst order: Deepta >
  Swastha > Mudita > Shanta > Dina > Duhkhita > Vikala > Khala > Kopita.
- Mrityu bhaga and Pushkara navamsa/bhaga are intentionally NOT implemented
  yet: their tables have competing published traditions and need a verified
  edition (P2 in the research note).

Interpretive only — no accuracy claim.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ashtakavarga import calculate_ashtakavarga
from .chart import D1Chart
from .constants import (
    NATURAL_BENEFICS, NATURAL_MALEFICS, OWN_SIGNS, PERMANENT_FRIENDSHIPS,
    PHYSICAL_PLANETS, PLANETS, SIGN_LORDS,
)

# Temporal friendship: house-distance groups (1-based inclusive count)
_TEMPORAL_FRIEND_HOUSES = (2, 3, 4, 10, 11, 12)

BALADI_STATES = ("Bala", "Kumara", "Yuva", "Vriddha", "Mrita")
_GOOD_HOUSES = (1, 2, 3, 4, 5, 7, 9, 10, 11)
_BAD_HOUSES = (6, 8, 12)
_WAR_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
_GANDANTA_DEG = 80.0 / 3.0  # 26°40'
_SANDHI_DEG = 1.0


def natural_relation(subject: str, other: str) -> str:
    """Naisargika maitri (Friend / Neutral / Enemy). Nodes default to Neutral."""
    table = PERMANENT_FRIENDSHIPS.get(subject)
    if table is None:
        return "Neutral"
    if other in table.get("friends", []):
        return "Friend"
    if other in table.get("enemies", []):
        return "Enemy"
    return "Neutral"


def temporal_relation(subject_sign: int, other_sign: int) -> str:
    """Tatkalika maitri from whole-sign distance (1-based inclusive)."""
    distance = ((other_sign - subject_sign) % 12) + 1
    return "Friend" if distance in _TEMPORAL_FRIEND_HOUSES else "Enemy"


def compound_relation(natural: str, temporal: str) -> str:
    """Panchadha maitri from natural x temporal friendship."""
    if natural == "Friend":
        return "Adhimitra" if temporal == "Friend" else "Sama"
    if natural == "Enemy":
        return "Sama" if temporal == "Friend" else "Adhishatru"
    return "Mitra" if temporal == "Friend" else "Shatru"


def baladi_avastha(sign_index: int, deg_in_sign: float) -> str:
    """Five age states by 6-degree part; reversed in even signs (BPHS)."""
    deg = deg_in_sign if (sign_index % 2 == 1) else (30.0 - deg_in_sign)
    index = min(4, max(0, int(deg // 6.0)))
    return BALADI_STATES[index]


def jagradadi_avastha(dignity: str) -> str:
    """Awake / Dreaming / Sleeping by dignity class."""
    if dignity in ("Exalted", "Moolatrikona", "Own"):
        return "Jagrat"
    if dignity in ("Friend", "Neutral"):
        return "Swapna"
    return "Supta"


def deeptadi_avastha(dignity: str, *, is_combust: bool,
                     has_malefic_conj: bool, has_benefic_conj: bool) -> str:
    """Nine-state Deeptadi avastha in classical best-to-worst precedence."""
    if dignity == "Exalted":
        return "Deepta"
    if dignity in ("Own", "Moolatrikona"):
        return "Swastha"
    if dignity == "Friend":
        return "Mudita"
    if has_benefic_conj and not has_malefic_conj:
        return "Shanta"
    if dignity == "Neutral":
        return "Dina"
    if dignity == "Enemy":
        return "Duhkhita"
    if is_combust:
        return "Vikala"
    if has_malefic_conj:
        return "Khala"
    return "Kopita"  # debilitated fallback


def is_sandhi(deg_in_sign: float) -> bool:
    """Weak at the sign junction (first/last degree)."""
    return deg_in_sign < _SANDHI_DEG or deg_in_sign >= (30.0 - _SANDHI_DEG)


def is_gandanta(sign_index: int, deg_in_sign: float) -> bool:
    """Water-sign end / fire-sign start junction (26°40' spans)."""
    if sign_index in (4, 8, 12):  # Cancer, Scorpio, Pisces (water endings)
        return deg_in_sign >= _GANDANTA_DEG
    if sign_index in (1, 5, 9):   # Aries, Leo, Sagittarius (fire beginnings)
        return deg_in_sign <= _GANDANTA_DEG
    return False


def graha_yuddha_pairs(positions: Dict[str, float]) -> Dict[str, str]:
    """
    Planetary war among non-luminary planets: same sign within 1 degree.
    Returns planet -> "won vs X" / "lost to X" (lower longitude wins).
    """
    results: Dict[str, str] = {}
    names = [p for p in _WAR_PLANETS if p in positions]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            lon_a, lon_b = positions[a], positions[b]
            if int(lon_a // 30) != int(lon_b // 30):
                continue
            separation = abs((lon_a - lon_b + 180.0) % 360.0 - 180.0)
            if separation > 1.0:
                continue
            if lon_a == lon_b:
                continue
            winner, loser = (a, b) if lon_a < lon_b else (b, a)
            results[winner] = f"won planetary war vs {loser}"
            results[loser] = f"lost planetary war to {winner}"
    return results


def parivartana_type(house_a: int, house_b: int) -> str:
    """Mahadainya classes: both good houses = Maha, both bad = Khala, else Dainya."""
    a_good = house_a in _GOOD_HOUSES
    b_good = house_b in _GOOD_HOUSES
    if a_good and b_good:
        return "Maha"
    if house_a in _BAD_HOUSES and house_b in _BAD_HOUSES:
        return "Khala"
    return "Dainya"


def detect_parivartana(planet_signs: Dict[str, int],
                       planet_houses: Optional[Dict[str, int]] = None) -> List[str]:
    """Mutual sign exchanges among the seven physical planets."""
    exchanges: List[str] = []
    seven = [p for p in PHYSICAL_PLANETS if p in planet_signs]
    for i, a in enumerate(seven):
        for b in seven[i + 1:]:
            sign_a = planet_signs[a]
            sign_b = planet_signs[b]
            if SIGN_LORDS.get(_sign_name(sign_a)) != b:
                continue
            if SIGN_LORDS.get(_sign_name(sign_b)) != a:
                continue
            if planet_houses:
                kind = parivartana_type(planet_houses[a], planet_houses[b])
                exchanges.append(
                    f"{a}<->{b} ({kind}, H{planet_houses[a]}/H{planet_houses[b]})")
            else:
                exchanges.append(f"{a}<->{b}")
    return exchanges


def _sign_name(sign_index: int) -> str:
    from .constants import INDEX_TO_SIGN
    return INDEX_TO_SIGN[sign_index]


@dataclass
class PlanetFactors:
    planet: str
    tatkalika: Dict[str, str] = field(default_factory=dict)
    compound: Dict[str, str] = field(default_factory=dict)
    baladi: str = ""
    jagradadi: str = ""
    deeptadi: str = ""
    sandhi: bool = False
    gandanta: bool = False
    bav_bindus: Optional[int] = None
    yuddha: Optional[str] = None
    parivartana: List[str] = field(default_factory=list)


def compute_planet_factors(d1: D1Chart, planet: str) -> PlanetFactors:
    """Assembles the P0 factor set for one planet."""
    ps = d1.planets[planet]
    factors = PlanetFactors(planet=planet)

    for other in PLANETS:
        if other == planet:
            continue
        nat = natural_relation(planet, other)
        if other in d1.planets:
            temp = temporal_relation(ps.sign_index, d1.planets[other].sign_index)
        else:
            temp = "Enemy"
        factors.tatkalika[other] = temp
        factors.compound[other] = compound_relation(nat, temp)

    factors.baladi = baladi_avastha(ps.sign_index, ps.degree_in_sign)
    factors.jagradadi = jagradadi_avastha(ps.dignity)
    malefic_conj = any(o in NATURAL_MALEFICS for o in d1.houses[ps.house].occupants if o != planet)
    benefic_conj = any(o in NATURAL_BENEFICS for o in d1.houses[ps.house].occupants if o != planet)
    factors.deeptadi = deeptadi_avastha(
        ps.dignity, is_combust=ps.is_combust,
        has_malefic_conj=malefic_conj, has_benefic_conj=benefic_conj,
    )
    factors.sandhi = is_sandhi(ps.degree_in_sign)
    factors.gandanta = is_gandanta(ps.sign_index, ps.degree_in_sign)

    try:
        ashtaka = calculate_ashtakavarga(d1)
        bav = ashtaka.bav.get(planet)
        if bav and 1 <= ps.sign_index <= 12:
            factors.bav_bindus = int(bav[ps.sign_index - 1])
    except Exception:
        factors.bav_bindus = None

    if planet in _WAR_PLANETS:
        factors.yuddha = graha_yuddha_pairs(
            {p: d1.planets[p].longitude for p in _WAR_PLANETS}).get(planet)

    factors.parivartana = [
        ex for ex in detect_parivartana(
            {p: d1.planets[p].sign_index for p in PHYSICAL_PLANETS},
            {p: d1.planets[p].house for p in PHYSICAL_PLANETS},
        )
        if ex.startswith(f"{planet}<->") or f"<->{planet} " in ex
    ]

    return factors
