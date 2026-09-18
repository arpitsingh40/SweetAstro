"""
Yoga Detection — Classical Planetary Yogas for Vedic Astrology.
Detects major yogas that indicate specific life patterns.
Critical for prediction accuracy: yogas modify how planets express.

Implements:
- Pancha Mahapurusha Yogas (Ruchaka, Bhadra, Hamsa, Malavya, Sasa)
- Rajayoga (simplified: dispositor placement + own/exaltation proxy)
- Gajakesari Yoga (Moon-Jupiter)
- Chandra-Mangal Yoga (Moon-Mars)
- Venus-Mars conjunction (modern combination, distinct from Malavya)
- Budha-Aditya (Mercury-Sun)
- Kala Sarpa Yoga (all seven planets in one nodal semicircle)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple

from .chart import D1Chart
from .constants import (
    SIGN_LORDS, INDEX_TO_SIGN, SIGN_TO_INDEX,
    NATURAL_BENEFICS, NATURAL_MALEFICS, OWN_SIGNS, EXALTATION_DATA,
    PLANETS, PHYSICAL_PLANETS,
)
from .navamsa import NavamsaChart
from .jaimini import JaiminiKarakas


@dataclass
class YogaResult:
    yoga_name: str
    yoga_type: str        # "mahabala" / "rajayoga" / "special" / "kala"
    planet: str           # Primary planet
    strength_impact: float  # +1.0 to -1.0 modifier on planet's effectiveness
    description: str


@dataclass
class YogaProfile:
    yogas: List[YogaResult]
    rajayoga_count: int
    mahapuranayoga_count: int
    kala_sarpa_active: bool
    strongest_yoga: Optional[str]
    planet_yoga_boost: Dict[str, float]  # planet -> cumulative boost from yogas


def _is_kendra(house: int) -> bool:
    return house in (1, 4, 7, 10)


def _is_trikona(house: int) -> bool:
    return house in (1, 5, 9)


# Pancha Mahapurusha Yogas (BPHS): the five planets other than the luminaries
# and the nodes, in own/exaltation sign AND in a kendra.
_MAHAPURUSHA = {
    "Mars": "Ruchaka Yoga",
    "Mercury": "Bhadra Yoga",
    "Jupiter": "Hamsa Yoga",
    "Venus": "Malavya Yoga",
    "Saturn": "Sasa Yoga",
}


def _separation(lon_a: float, lon_b: float) -> float:
    """Shortest angular separation between two longitudes in degrees."""
    return abs((lon_a - lon_b + 180.0) % 360.0 - 180.0)


def _sign_contains_planet(d1: D1Chart, sign_name: str, planet: str) -> bool:
    return d1.planets[planet].sign == sign_name


_KALA_SARPA_PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")


def kala_sarpa_planets(planet_signs: Dict[str, int], rahu_sign: int,
                       ketu_sign: int) -> List[str]:
    """
    Returns the planets caught in Kala Sarpa yoga (empty when the pattern is
    absent). Classical test: no planet may sit in a node's sign, and ALL seven
    planets must lie inside ONE of the two arcs between Rahu and Ketu.
    """
    node_signs = {rahu_sign, ketu_sign}
    if any(sign in node_signs for sign in planet_signs.values()):
        return []
    arc_rahu_to_ketu = {((rahu_sign - 1 + i) % 12) + 1 for i in range(1, 6)}
    arc_ketu_to_rahu = {((ketu_sign - 1 + i) % 12) + 1 for i in range(1, 6)}
    signs = set(planet_signs.values())
    if signs <= arc_rahu_to_ketu or signs <= arc_ketu_to_rahu:
        return [p for p in _KALA_SARPA_PLANETS if p in planet_signs]
    return []


def detect_yogas(d1: D1Chart, d9: NavamsaChart, karakas: JaiminiKarakas
                 ) -> YogaProfile:
    """
    Detects all classical yogas for the given chart.
    Returns structured profile with strength modifiers.
    """
    yogas: List[YogaResult] = []
    planet_yoga_boost: Dict[str, float] = {p: 0.0 for p in PLANETS}
    rajayoga_count = 0
    mahapura_count = 0
    kala_sarpa_active = False

    asc_sign = d1.ascendant_sign
    asc_lord = d1.houses[1].lord
    seventh_lord = d1.houses[7].lord
    lagna_sign_idx = d1.ascendant_sign_index

    for planet in PHYSICAL_PLANETS:
        ps = d1.planets[planet]
        lord = SIGN_LORDS.get(ps.sign, planet)
        house = ps.house

        # ---- Pancha Mahapurusha Yogas ----
        mahapurusha = _MAHAPURUSHA.get(planet)
        if mahapurusha:
            is_kendra = _is_kendra(house)
            is_own_exalt = (ps.sign in OWN_SIGNS.get(planet, [])
                            or (planet in EXALTATION_DATA and ps.sign == EXALTATION_DATA[planet][0]))

            if is_kendra and is_own_exalt:
                yogas.append(YogaResult(
                    yoga_name=mahapurusha, yoga_type="mahabala",
                    planet=planet, strength_impact=0.5,
                    description=f"{mahapurusha}: {planet} in {ps.sign} ({house}H) in own/exaltation "
                                f"sign within a kendra. Strong {planet} to give its promises."
                ))
                planet_yoga_boost[planet] = planet_yoga_boost.get(planet, 0.0) + 0.5
                mahapura_count += 1

        # ---- Special Yogas ----
        # Budha Aditya (Mercury conjunct Sun: same sign, tight separation)
        if planet == "Mercury":
            sun = d1.planets["Sun"]
            if sun.sign == ps.sign and _separation(sun.longitude, ps.longitude) <= 15.0:
                yogas.append(YogaResult(
                    yoga_name="Budha Aditya Yoga", yoga_type="special",
                    planet="Mercury", strength_impact=0.3,
                    description="Mercury conjunct Sun: intellect and communication elevated."
                ))
                planet_yoga_boost["Mercury"] += 0.3

        # Gajakesari (Jupiter conjunct Moon or in a kendra from the Moon)
        if planet == "Moon":
            jup = d1.planets["Jupiter"]
            same_sign = (jup.sign == ps.sign)
            relative_from_moon = ((jup.house - ps.house) % 12) + 1
            if same_sign or relative_from_moon in (1, 4, 7, 10):
                yogas.append(YogaResult(
                    yoga_name="Gajakesari Yoga", yoga_type="special",
                    planet="Moon", strength_impact=0.25,
                    description="Moon-Jupiter connection: wisdom and prosperity indicators."
                ))
                planet_yoga_boost["Moon"] += 0.25

        # Chandra-Mangal (Moon + Mars conjunction)
        if planet == "Moon":
            mars = d1.planets["Mars"]
            if mars.sign == ps.sign:
                yogas.append(YogaResult(
                    yoga_name="Chandra-Mangal Yoga", yoga_type="special",
                    planet="Moon", strength_impact=0.2,
                    description="Moon-Mars conjunction: courage and determination heightened."
                ))
                planet_yoga_boost["Moon"] += 0.2

        # Venus + Mars conjunction (modern combination; distinct from the
        # Malavya Mahapurusha yoga and from Chandra-Mangal)
        if planet == "Venus":
            mars = d1.planets["Mars"]
            if mars.sign == ps.sign:
                yogas.append(YogaResult(
                    yoga_name="Venus-Mars Conjunction", yoga_type="special",
                    planet="Venus", strength_impact=0.2,
                    description="Venus-Mars conjunction: passion and creative drive amplified."
                ))
                planet_yoga_boost["Venus"] += 0.2

        # ---- Rajayoga ----
        # ---- Rajayoga / Neecha Bhanga are evaluated once after the loop ----

    # ---- Rajayoga (lord-based kendra-trikona connections) ----
    kendra = {d1.houses[h].lord for h in (1, 4, 7, 10)}
    trikona = {d1.houses[h].lord for h in (1, 5, 9)}
    kendra -= {"Rahu", "Ketu"}
    trikona -= {"Rahu", "Ketu"}
    in_raja: Set[str] = set()
    for k in sorted(kendra):
        for t in sorted(trikona):
            if k == t or k in in_raja and t in in_raja:
                continue
            kp, tp = d1.planets[k], d1.planets[t]
            connection = ""
            if kp.sign == tp.sign:
                connection = "conjunction"
            elif kp.house in tp.aspecting_houses and tp.house in kp.aspecting_houses:
                connection = "mutual aspect"
            elif SIGN_LORDS[kp.sign] == t and SIGN_LORDS[tp.sign] == k:
                connection = "exchange"
            if not connection:
                continue
            in_raja.update({k, t})
            rajayoga_count += 1
            for p in (k, t):
                yogas.append(YogaResult(
                    yoga_name=f"Rajayoga ({k} + {t})", yoga_type="rajayoga",
                    planet=p, strength_impact=0.4,
                    description=(f"Rajayoga: kendra lord {k} and trikona lord {t} "
                                 f"linked by {connection}. Fulfillment through "
                                 f"status and purpose.")
                ))
                planet_yoga_boost[p] = planet_yoga_boost.get(p, 0.0) + 0.4
    for p in sorted((kendra | trikona) - in_raja):
        house = d1.planets[p].house
        if (_is_trikona(house) and p in kendra) or (_is_kendra(house) and p in trikona):
            yogas.append(YogaResult(
                yoga_name="Partial Rajayoga", yoga_type="rajayoga",
                planet=p, strength_impact=0.15,
                description=(f"Partial Rajayoga: {'kendra' if p in kendra else 'trikona'} "
                             f"lord {p} placed in a "
                             f"{'trikona' if p in kendra else 'kendra'} house ({house}H).")
            ))
            planet_yoga_boost[p] = planet_yoga_boost.get(p, 0.0) + 0.15

    # ---- Neecha Bhanga (cancellation of debilitation) ----
    for planet in PHYSICAL_PLANETS:
        ps = d1.planets[planet]
        if ps.dignity != "Debilitated":
            continue
        dispositor = SIGN_LORDS[ps.sign]
        if dispositor not in d1.planets or dispositor == planet:
            continue
        d_house = d1.planets[dispositor].house
        moon_house = d1.planets["Moon"].house
        reasons = []
        if _is_kendra(d_house) or ((d_house - moon_house) % 12) + 1 in (1, 4, 7, 10):
            reasons.append("dispositor in kendra from lagna or Moon")
        if dispositor in d1.houses[ps.house].occupants:
            reasons.append("conjunct its dispositor")
        if d1.planets[dispositor].dignity in ("Exalted", "Own", "Moolatrikona"):
            reasons.append("dispositor dignified")
        if _is_kendra(ps.house):
            reasons.append("debilitated planet in a kendra")
        if reasons:
            yogas.append(YogaResult(
                yoga_name=f"Neecha Bhanga ({planet})", yoga_type="cancellation",
                planet=planet, strength_impact=0.2,
                description=(f"Neecha Bhanga for {planet}: " + "; ".join(reasons) +
                             ". Debilitation is partially cancelled.")
            ))
            planet_yoga_boost[planet] = planet_yoga_boost.get(planet, 0.0) + 0.2

    kala_planets = kala_sarpa_planets(
        {p: d1.planets[p].sign_index for p in _KALA_SARPA_PLANETS},
        d1.planets["Rahu"].sign_index,
        d1.planets["Ketu"].sign_index,
    )
    if kala_planets:
        kala_sarpa_active = True
        for planet in kala_planets:
            if planet == "Sun":
                continue
            yogas.append(YogaResult(
                yoga_name=f"Kala Sarpa (affects {planet})", yoga_type="kala",
                planet=planet, strength_impact=-0.15,
                description=f"{planet} eclipsed by Kala Sarpa: delays and "
                            f"karmic lessons in {planet} themes."
            ))
            planet_yoga_boost[planet] -= 0.15

    strongest = None
    if yogas:
        sorted_y = sorted(yogas, key=lambda y: abs(y.strength_impact), reverse=True)
        strongest = sorted_y[0].yoga_name

    return YogaProfile(
        yogas=yogas,
        rajayoga_count=rajayoga_count,
        mahapuranayoga_count=mahapura_count,
        kala_sarpa_active=kala_sarpa_active,
        strongest_yoga=strongest,
        planet_yoga_boost=planet_yoga_boost,
    )
