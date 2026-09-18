"""
Varga (Divisional Chart) Selector & Calculator — Consumer Engine Sec 3.

Implements:
- Question -> relevant varga mapping (Wealth, Career, Marriage, Children,
  Property, Education, Siblings, Health, Spirituality, General).
- Parashara varga sign computation for Shodashavarga subset.
- Birth-time reliability gating for remedy use.

Notes on provenance:
- D9 reuses the dedicated Navamsa engine (src/core/navamsa.py) as source of truth.
- Other vargas follow widely published Parashara mappings (BPHS Ch.6-7).
  Where schools differ (e.g. D2 Hora variants, D10 Parashara vs Jaimini),
  we use the Parashara variant and document it. Higher vargas (D40/D45/D60)
  are structural placements for pattern confirmation only and are gated
  behind birth-time reliability.
- Whole-sign houses from the varga Lagna are used (consistent with D1 engine).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .constants import SIGNS, INDEX_TO_SIGN, SIGN_TO_INDEX, SIGN_LORDS
from .chart import D1Chart, _calculate_dignity
from .keywords import matches_any
from .navamsa import calculate_navamsa_chart

# ---------------------------------------------------------------------------
# Question -> varga mapping (Sec 3)
# ---------------------------------------------------------------------------

QUESTION_TO_VARGAS: Dict[str, List[str]] = {
    "wealth": ["D1", "D2", "D9", "D10", "D11"],
    "career": ["D1", "D9", "D10"],
    "business": ["D1", "D2", "D9", "D10", "D11"],
    "marriage": ["D1", "D9"],
    "children": ["D1", "D7"],
    "property": ["D1", "D4"],
    "education": ["D1", "D24"],
    "siblings": ["D1", "D3"],
    "health": ["D1", "D6", "D30"],
    "difficulties": ["D1", "D6", "D8", "D30"],
    "spirituality": ["D1", "D5", "D9", "D20"],
    "compatibility": ["D1", "D9"],
    "personality": ["D1", "D9", "D27"],
    "general": ["D1", "D5", "D9", "D10", "D30"],
}

# Varga -> life-topic label (for explanations)
VARGA_TOPICS: Dict[str, str] = {
    "D1": "overall natal promise (Rashi)",
    "D2": "wealth / resources (Hora)",
    "D3": "siblings / initiative (Drekkana)",
    "D4": "property / fixed assets (Chaturthamsha)",
    "D5": "fame / authority / spiritual merit (Panchamsha)",
    "D6": "health / enemies / debts / service (Shashtamsha)",
    "D7": "children (Saptamsha)",
    "D8": "sudden change / hidden crises / endurance (Ashtamsha)",
    "D9": "dharma / marriage / underlying strength (Navamsa)",
    "D10": "profession / status (Dashamsha)",
    "D11": "gains / income / fulfilment of desires (Ekadashamsha)",
    "D12": "parents / lineage (Dwadashamsha)",
    "D16": "conveyances / comforts (Shodashamsha)",
    "D20": "spiritual progress (Vimshamsha)",
    "D24": "education (Chaturvimshamsha)",
    "D27": "strengths / weaknesses (Bhamsha)",
    "D30": "difficulties / health pattern (Trimshamsha)",
    "D40": "maternal legacy (Khavedamsha)",
    "D45": "paternal legacy (Akshavedamsha)",
    "D60": "past-karma pattern (Shashtiamsha)",
    "D81": "deeper dharma / in-law layer (Nav-Navamsha)",
    "D108": "cumulative merit / refined dharma (Navamsha-Dwadashamsha)",
    "D144": "minute karma pattern (Dwadashamsha-Dwadashamsha)",
}


def vargas_for_question(question: str) -> List[str]:
    """Returns relevant vargas for a free-text question (Sec 3)."""
    q = (question or "").lower()
    for key in QUESTION_TO_VARGAS:
        if matches_any(q, [key]):
            return QUESTION_TO_VARGAS[key]
    # keyword fallbacks (word-boundary: "ill" must not match inside "will")
    if matches_any(q, ["money", "income", "finance", "rich", "debt", "gain"]):
        return QUESTION_TO_VARGAS["wealth"]
    if matches_any(q, ["job", "profession", "promotion", "work"]):
        return QUESTION_TO_VARGAS["career"]
    if matches_any(q, ["wife", "husband", "partner", "divorce", "wedding",
                       "marry", "married", "shaadi", "shadi", "vivah"]):
        return QUESTION_TO_VARGAS["marriage"]
    if matches_any(q, ["child", "baby", "pregnan"]):
        return QUESTION_TO_VARGAS["children"]
    if matches_any(q, ["house", "land", "flat", "plot", "vehicle"]):
        return QUESTION_TO_VARGAS["property"]
    if matches_any(q, ["study", "exam", "degree", "school", "college"]):
        return QUESTION_TO_VARGAS["education"]
    if matches_any(q, ["brother", "sister"]):
        return QUESTION_TO_VARGAS["siblings"]
    if matches_any(q, ["disease", "ill", "surgery", "health", "legal", "enemy"]):
        return QUESTION_TO_VARGAS["health"]
    if matches_any(q, ["moksha", "sadhana", "meditat", "spirit"]):
        return QUESTION_TO_VARGAS["spirituality"]
    if matches_any(q, ["compatibility", "compatible", "milan", "kuta", "koot"]):
        return QUESTION_TO_VARGAS["compatibility"]
    if matches_any(q, ["personality", "character", "swabhav", "swabhava"]):
        return QUESTION_TO_VARGAS["personality"]
    return QUESTION_TO_VARGAS["general"]


@dataclass
class VargaPlanetState:
    name: str
    d1_sign: str
    varga_sign: str
    varga_sign_index: int
    varga_house: int  # from varga Lagna
    varga_dignity: str
    is_vargottama: bool


@dataclass
class VargaChart:
    varga: str  # e.g. "D10"
    topic: str
    ascendant_sign: str
    ascendant_sign_index: int
    planets: Dict[str, VargaPlanetState] = field(default_factory=dict)
    houses: Dict[int, List[str]] = field(default_factory=dict)


def _odd_sign(sign_index: int) -> bool:
    # Odd = Aries(1), Gemini(3), ... — i.e. odd-numbered signs
    return (sign_index % 2) == 1


# Sign groups (BPHS): movable (chara), fixed (sthira), dual (dvisvabhava)
_MOVABLE = (1, 4, 7, 10)    # Aries, Cancer, Libra, Capricorn
_FIXED = (2, 5, 8, 11)      # Taurus, Leo, Scorpio, Aquarius
_DUAL = (3, 6, 9, 12)       # Gemini, Virgo, Sagittarius, Pisces


def _group_start(sign_index: int, movable: int, fixed: int, dual: int) -> int:
    """Start sign for a movable/fixed/dual progression (classical varga rule)."""
    if sign_index in _MOVABLE:
        return movable
    if sign_index in _FIXED:
        return fixed
    return dual


def varga_sign_index(varga: str, longitude: float, sign_index: int, deg_in_sign: float) -> int:
    """
    Varga sign index (1-12) for a sidereal longitude.
    Covers the 16 Parashari shodashavarga (D2, D3, D4, D7, D10, D12, D16, D20,
    D24, D27, D30, D40, D45, D60) plus the commonly used non-Parashari charts
    D5 (Panchamsha), D6 (Shashtamsha), D8 (Ashtamsha), D11 (Ekadashamsha) and
    the higher cyclic charts D81, D108, D144.
    D1/D9 are handled by their dedicated engines.

    Declared conventions where traditions differ:
    - D5: lord-sign sequence (odd: Aries/Aquarius/Sagittarius/Gemini/Libra;
      even: Taurus/Virgo/Pisces/Capricorn/Scorpio) — the D30 sign set.
    - D6: odd signs count from Aries, even signs from Libra (Rao §6.2.6).
    - D8: movable from Aries, fixed from Sagittarius, dual from Leo.
    - D11: movable from the sign itself, fixed from the 9th, dual from the 5th.
    - D81/D108/D144: parivritti (cyclic) method — continuous count of the
      divisions from Aries; D81 equals D9-of-D9 under the continuous rule.
    """
    s = sign_index  # 1..12
    d = deg_in_sign  # 0..30

    if varga == "D2":  # Hora: 2 x 15 deg
        half = 0 if d < 15.0 else 1
        if _odd_sign(s):
            # odd: Sun Hora (Leo) then Moon Hora (Cancer)
            return 5 if half == 0 else 4
        else:
            # even: Moon Hora then Sun Hora
            return 4 if half == 0 else 5

    if varga == "D3":  # Drekkana: 3 x 10 deg -> same, 5th, 9th from sign
        part = int(d // 10.0)  # 0,1,2
        offset = (part * 4) % 12
        return ((s - 1 + offset) % 12) + 1

    if varga == "D4":  # Chaturthamsha: 4 x 7.5 deg
        part = int(d // 7.5)  # 0..3
        if _odd_sign(s):
            # same, 4th, 7th, 10th
            offsets = [0, 3, 6, 9]
        else:
            # even: 7th, 10th, same, 4th (reverse cycle per Parashara)
            offsets = [6, 9, 0, 3]
        return ((s - 1 + offsets[part]) % 12) + 1

    if varga == "D5":  # Panchamsha: 5 x 6 deg (non-Parashari; declared scheme)
        part = min(int(d // 6.0), 4)
        odd_signs = [1, 11, 9, 3, 7]      # Aries, Aquarius, Sagittarius, Gemini, Libra
        even_signs = [2, 6, 12, 10, 8]    # Taurus, Virgo, Pisces, Capricorn, Scorpio
        return odd_signs[part] if _odd_sign(s) else even_signs[part]

    if varga == "D6":  # Shashtamsha: 6 x 5 deg (odd from Aries, even from Libra)
        part = min(int(d // 5.0), 5)
        start = 1 if _odd_sign(s) else 7
        return ((start - 1 + part) % 12) + 1

    if varga == "D8":  # Ashtamsha: 8 x 3.75 deg (movable Aries, fixed Sagittarius, dual Leo)
        part = min(int(d // 3.75), 7)
        start = _group_start(s, 1, 9, 5)
        return ((start - 1 + part) % 12) + 1

    if varga == "D11":  # Ekadashamsha / Rudramsa: 11 parts (relative start signs)
        span = 30.0 / 11.0
        part = min(int(d / span), 10)
        if s in _MOVABLE:
            start = s
        elif s in _FIXED:
            start = ((s - 1 + 8) % 12) + 1   # 9th from sign
        else:
            start = ((s - 1 + 4) % 12) + 1   # 5th from sign
        return ((start - 1 + part) % 12) + 1

    if varga == "D7":  # Saptamsha: 7 x ~4.2857 deg
        part = int(d / (30.0 / 7.0))  # 0..6
        part = min(part, 6)
        if _odd_sign(s):
            start = s
        else:
            start = ((s - 1 + 6) % 12) + 1  # 7th from sign
        return ((start - 1 + part) % 12) + 1

    if varga == "D10":  # Dashamsha (Parashara): 10 x 3 deg
        part = int(d // 3.0)  # 0..9
        part = min(part, 9)
        if _odd_sign(s):
            start = s
        else:
            start = ((s - 1 + 8) % 12) + 1  # 9th from sign
        return ((start - 1 + part) % 12) + 1

    if varga == "D12":  # Dwadashamsha: 12 x 2.5 deg, sequential from sign
        part = int(d // 2.5)
        part = min(part, 11)
        return ((s - 1 + part) % 12) + 1

    if varga == "D16":  # Shodashamsha / Kalamsa: 16 parts
        span = 30.0 / 16.0
        part = min(int(d // span), 15)
        # Parashara: movable signs from Aries, fixed from Leo, dual from Sagittarius
        start = _group_start(s, 1, 5, 9)
        return ((start - 1 + part) % 12) + 1

    if varga == "D20":  # Vimshamsha: 20 x 1.5 deg
        part = min(int(d // 1.5), 19)
        # Parashara: movable signs from Aries, fixed from Sagittarius, dual from Leo
        start = _group_start(s, 1, 9, 5)
        return ((start - 1 + part) % 12) + 1

    if varga == "D24":  # Chaturvimshamsha: 24 x 1.25 deg
        part = min(int(d // 1.25), 23)
        # odd: from Leo; even: from Cancer (Siddhamsha variant is common).
        # We use sequential-from-sign here and document it.
        start = 5 if _odd_sign(s) else 4
        # offset within that cycle by part
        return ((start - 1 + part) % 12) + 1

    if varga == "D27":  # Bhamsha / Nakshatramsha: 27 parts
        span = 30.0 / 27.0
        part = min(int(d // span), 26)
        # Parashara: fiery from Aries, earthy from Cancer, airy from Libra, watery from Capricorn
        start = ((s - 1) % 4) * 3 + 1  # element index -> Aries/Cancer/Libra/Capricorn
        return ((start - 1 + part) % 12) + 1

    if varga == "D30":  # Trimshamsha (Parashara, degree-range based, odd/even differ)
        # Odd signs: Mars 0-5 (Aries), Saturn 5-10 (Aquarius), Jupiter 10-18 (Sagittarius),
        #            Mercury 18-25 (Gemini), Venus 25-30 (Libra)
        # Even signs: Venus 0-5 (Taurus), Mercury 5-12 (Virgo), Jupiter 12-20 (Pisces),
        #             Saturn 20-25 (Capricorn), Mars 25-30 (Scorpio)
        if _odd_sign(s):
            bounds = [(5.0, 1), (10.0, 11), (18.0, 9), (25.0, 3), (30.5, 7)]
        else:
            bounds = [(5.0, 2), (12.0, 6), (20.0, 12), (25.0, 10), (30.5, 8)]
        for lim, sg in bounds:
            if d < lim:
                return sg
        return bounds[-1][1]

    if varga == "D40":  # Khavedamsha: odd signs from Aries, even from Libra
        n = 40
        span = 30.0 / n
        part = min(int(d // span), n - 1)
        start = 1 if _odd_sign(s) else 7
        return ((start - 1 + part) % 12) + 1

    if varga == "D45":  # Akshavedamsha: movable from Aries, fixed from Leo, dual from Sagittarius
        n = 45
        span = 30.0 / n
        part = min(int(d // span), n - 1)
        start = _group_start(s, 1, 5, 9)
        return ((start - 1 + part) % 12) + 1

    if varga == "D60":  # Shashtiamsha: Parashara standard counts from the same sign
        n = 60
        span = 30.0 / n
        part = min(int(d // span), n - 1)
        return ((s - 1 + part) % 12) + 1

    if varga in ("D81", "D108", "D144"):  # higher cyclic charts (parivritti method)
        n = int(varga[1:])
        span = 30.0 / n
        part = min(int(d / span), n - 1)
        return (int((s - 1) * n + part) % 12) + 1

    raise ValueError(f"Unsupported varga: {varga}")


def calculate_varga_chart(d1: D1Chart, varga: str) -> VargaChart:
    """Builds a varga chart (whole-sign houses from varga Lagna)."""
    if varga == "D1":
        asc_sign = d1.ascendant_sign
        asc_idx = d1.ascendant_sign_index
        planets: Dict[str, VargaPlanetState] = {}
        houses: Dict[int, List[str]] = {h: [] for h in range(1, 13)}
        for name, ps in d1.planets.items():
            h = ps.house
            planets[name] = VargaPlanetState(
                name=name, d1_sign=ps.sign, varga_sign=ps.sign,
                varga_sign_index=ps.sign_index, varga_house=h,
                varga_dignity=ps.dignity, is_vargottama=True,
            )
            houses[h].append(name)
        return VargaChart(varga="D1", topic=VARGA_TOPICS["D1"],
                          ascendant_sign=asc_sign, ascendant_sign_index=asc_idx,
                          planets=planets, houses=houses)

    if varga == "D9":
        nav = calculate_navamsa_chart(d1)
        planets = {}
        houses = {h: list(v) for h, v in nav.houses.items()}
        for name, np in nav.planets.items():
            planets[name] = VargaPlanetState(
                name=name, d1_sign=np.d1_sign, varga_sign=np.d9_sign,
                varga_sign_index=np.d9_sign_index,
                varga_house=np.d9_house, varga_dignity=np.d9_dignity,
                is_vargottama=np.is_vargottama,
            )
        return VargaChart(varga="D9", topic=VARGA_TOPICS["D9"],
                          ascendant_sign=nav.ascendant_d9_sign,
                          ascendant_sign_index=nav.ascendant_d9_sign_index,
                          planets=planets, houses=houses)

    # Ascendant for generic vargas
    asc_idx = varga_sign_index(varga, d1.ascendant_deg, d1.ascendant_sign_index,
                               d1.ascendant_degree_in_sign)
    asc_sign = INDEX_TO_SIGN[asc_idx]
    planets = {}
    houses = {h: [] for h in range(1, 13)}
    for name, ps in d1.planets.items():
        vs_idx = varga_sign_index(varga, ps.longitude, ps.sign_index, ps.degree_in_sign)
        vs = INDEX_TO_SIGN[vs_idx]
        vh = ((vs_idx - asc_idx + 12) % 12) + 1
        # dignity of planet in that varga sign (moolatrikona is a D1 concept,
        # so repeated degree ranges must not be applied to varga positions)
        vd = _calculate_dignity(name, vs, ps.degree_in_sign, allow_moolatrikona=False)
        is_varg = (ps.sign == vs)
        st = VargaPlanetState(name=name, d1_sign=ps.sign, varga_sign=vs,
                              varga_sign_index=vs_idx, varga_house=vh,
                              varga_dignity=vd, is_vargottama=is_varg)
        planets[name] = st
        houses[vh].append(name)
    return VargaChart(varga=varga, topic=VARGA_TOPICS.get(varga, varga),
                      ascendant_sign=asc_sign, ascendant_sign_index=asc_idx,
                      planets=planets, houses=houses)


def select_vargas(question: str, time_reliable: bool) -> Tuple[List[str], str]:
    """
    Returns (relevant_vargas, note). Sec 3: do not give every varga equal weight;
    Sec 1: gate remedy use of fine vargas behind birth-time reliability.
    """
    vargas = vargas_for_question(question)
    note = f"Relevant charts for this question: {' + '.join(vargas)}."
    if not time_reliable:
        note += (" Birth time is uncertain, so fine divisional placements "
                 "(especially D5/D6/D8/D11/D20/D24/D27/D30/D40/D45/D60 and house-based remedies) "
                 "carry reduced confidence.")
    return vargas, note
