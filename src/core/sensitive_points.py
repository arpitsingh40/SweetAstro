"""
Sensitive natal degrees (P2, sourced tables).

- Pushkara Navamsa — the nourishing 3°20' divisions. Degree framework follows
  C. S. Patel, *Navamsa in Astrology* (library entry 200): two ranges per sign,
  grouped by element (fire 20°00'–23°20' & 26°40'–30°00'; earth 6°40'–10°00' &
  13°20'–16°40'; air 16°40'–20°00' & 23°20'–26°40'; water 0°00'–3°20' &
  6°40'–10°00').
- Pushkara Bhaga — a single sensitive degree. Two declared traditions:
    * "jataka_parijata" (Ch. 1 v. 58): Aries 21, Taurus 14, Gemini 18,
      Cancer 8, Leo 19, Virgo 9, Libra 24, Scorpio 11, Sagittarius 23,
      Capricorn 14, Aquarius 19, Pisces 9.
    * "patel" grouped: fire 21, earth 14, air 24, water 7.
  A hit occupies the whole numbered degree (e.g. 21°00'–21°59').
- Mrityu Bhaga is NOT implemented: the Jataka Parijata per-sign table
  (Adhyaya 1, Shloka 57) was not obtainable in full; the circulating
  per-planet fixed-degree lists conflict across sources. Never guess.

Interpretive only — a Pushkara placement modifies, never guarantees.
"""

from dataclasses import dataclass
from typing import Dict

_FIRE = (1, 5, 9)
_EARTH = (2, 6, 10)
_AIR = (3, 7, 11)
_WATER = (4, 8, 12)

_PUSHKARA_RANGES = {
    "fire": ((20.0, 23.3333), (26.6667, 30.0)),
    "earth": ((6.6667, 10.0), (13.3333, 16.6667)),
    "air": ((16.6667, 20.0), (23.3333, 26.6667)),
    "water": ((0.0, 3.3333), (6.6667, 10.0)),
}

_PUSHKARA_BHAGA_JP: Dict[int, int] = {
    1: 21, 2: 14, 3: 18, 4: 8, 5: 19, 6: 9,
    7: 24, 8: 11, 9: 23, 10: 14, 11: 19, 12: 9,
}

_PUSHKARA_BHAGA_PATEL = {"fire": 21, "earth": 14, "air": 24, "water": 7}


def _element(sign_index: int) -> str:
    if sign_index in _FIRE:
        return "fire"
    if sign_index in _EARTH:
        return "earth"
    if sign_index in _AIR:
        return "air"
    return "water"


def is_pushkara_navamsa(sign_index: int, deg_in_sign: float) -> bool:
    for low, high in _PUSHKARA_RANGES[_element(sign_index)]:
        if low <= deg_in_sign < high:
            return True
    return False


def is_pushkara_bhaga(sign_index: int, deg_in_sign: float,
                      convention: str = "jataka_parijata") -> bool:
    whole_degree = int(deg_in_sign)
    if convention == "patel":
        return whole_degree == _PUSHKARA_BHAGA_PATEL[_element(sign_index)]
    return whole_degree == _PUSHKARA_BHAGA_JP.get(sign_index)


@dataclass
class SensitivePlacement:
    planet: str
    pushkara_navamsa: bool
    pushkara_bhaga: bool
    bhaga_convention: str = "jataka_parijata"

    def to_note(self) -> str:
        tags = []
        if self.pushkara_navamsa:
            tags.append("Pushkara Navamsa")
        if self.pushkara_bhaga:
            tags.append(f"Pushkara Bhaga ({self.bhaga_convention})")
        return ", ".join(tags)


def sensitive_placement(d1, planet: str) -> SensitivePlacement:
    ps = d1.planets[planet]
    return SensitivePlacement(
        planet=planet,
        pushkara_navamsa=is_pushkara_navamsa(ps.sign_index, ps.degree_in_sign),
        pushkara_bhaga=is_pushkara_bhaga(ps.sign_index, ps.degree_in_sign),
    )
