"""
Vimshopak Bala — 20-point varga-weighted dignity score (classical).

Each scheme splits twenty points across its divisions (Svavisva); the
planet's dignity in each division earns a Vargavisva value out of twenty,
and the contribution is Svavisva x Vargavisva / 20.

Weight tables and dignity values follow the classical published tables
(BPHS varga-strength chapters): own/exaltation 20, moolatrikona 18,
friend 15, neutral 10, enemy 7, debilitated 0. The engine computes natural
friendship only (compound pancha-dha friendship is not yet modelled).

Vaiseshikamsa counts divisions where the planet is exalted, in
moolatrikona, or in its own sign. Nodes are supplementary and excluded
unless requested.

Interpretive strength measure — not an accuracy claim.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .chart import D1Chart, _calculate_dignity
from .constants import INDEX_TO_SIGN, PHYSICAL_PLANETS
from .navamsa import calculate_navamsa_chart
from .vargas import varga_sign_index

VIMSHOPAKA_WEIGHTS: Dict[str, Dict[str, float]] = {
    "shadvarga": {
        "D1": 6.0, "D2": 2.0, "D3": 4.0, "D9": 5.0, "D12": 2.0, "D30": 1.0,
    },
    "saptavarga": {
        "D1": 5.0, "D2": 2.0, "D3": 3.0, "D7": 1.0,
        "D9": 2.5, "D12": 4.5, "D30": 2.0,
    },
    "dashavarga": {
        "D1": 3.0, "D2": 1.5, "D3": 1.5, "D7": 1.5, "D9": 1.5,
        "D10": 1.5, "D12": 1.5, "D16": 1.5, "D30": 1.5, "D60": 5.0,
    },
    "shodashavarga": {
        "D1": 3.5, "D2": 1.0, "D3": 1.0, "D4": 0.5, "D7": 0.5, "D9": 3.0,
        "D10": 0.5, "D12": 0.5, "D16": 2.0, "D20": 0.5, "D24": 0.5,
        "D27": 0.5, "D30": 1.0, "D40": 0.5, "D45": 0.5, "D60": 4.0,
    },
}

VARGAVISVA: Dict[str, float] = {
    "Exalted": 20.0,
    "Own": 20.0,
    "Moolatrikona": 18.0,
    "Friend": 15.0,
    "Neutral": 10.0,
    "Enemy": 7.0,
    "Debilitated": 0.0,
}

VAISESHIKAMSA: Dict[str, Dict[int, str]] = {
    "shadvarga": {
        2: "Kimshuka", 3: "Vyanjana", 4: "Chamara", 5: "Chatra", 6: "Kundala",
    },
    "saptavarga": {
        2: "Kimshuka", 3: "Vyanjana", 4: "Chamara", 5: "Chatra",
        6: "Kundala", 7: "Mukuta",
    },
    "dashavarga": {
        2: "Parijata", 3: "Uttama", 4: "Gopura", 5: "Simhasana",
        6: "Paravata", 7: "Devaloka", 8: "Brahmaloka", 9: "Shakravahana",
        10: "Sridhama",
    },
    "shodashavarga": {
        2: "Bhedaka", 3: "Kusuma", 4: "Nagapushpa", 5: "Kanduka",
        6: "Kerala", 7: "Kalpavriksha", 8: "Chandanavana", 9: "Purnachandra",
        10: "Ucchaishravas", 11: "Dhanvantari", 12: "Suryakanta",
        13: "Vidruma", 14: "Shakrasimhasana", 15: "Goloka", 16: "Sri Vallabha",
    },
}

_HORA_SUN_GROUP = ("Sun", "Mars", "Jupiter")
_HORA_MOON_GROUP = ("Moon", "Venus", "Saturn")


@dataclass
class VimsopakaScore:
    planet: str
    total: float
    per_varga: Dict[str, float] = field(default_factory=dict)
    good_varga_count: int = 0
    vaiseshikamsa: Optional[str] = None
    grade: str = ""


@dataclass
class VimsopakaResult:
    scheme: str
    scores: Dict[str, VimsopakaScore] = field(default_factory=dict)
    note: str = ""


def _grade(total: float) -> str:
    if total < 5.0:
        return "Very weak (below 5)"
    if total < 10.0:
        return "Weak (5-10)"
    if total < 15.0:
        return "Moderate (10-15)"
    return "Strong (15-20)"


def _hora_points(planet: str, hora_sign: str) -> Optional[float]:
    """Classical D2 exception: hora has only solar/lunar ownership."""
    if planet == "Mercury":
        return 20.0
    if hora_sign == "Leo" and planet in _HORA_SUN_GROUP:
        return 20.0
    if hora_sign == "Cancer" and planet in _HORA_MOON_GROUP:
        return 20.0
    if hora_sign == "Cancer" and planet == "Jupiter":
        return 20.0
    return None


def calculate_vimsopaka(
    d1: D1Chart,
    scheme: str = "shodashavarga",
    include_nodes: bool = False,
) -> VimsopakaResult:
    """Computes Vimshopak Bala for a chart under one weight scheme."""
    if scheme not in VIMSHOPAKA_WEIGHTS:
        raise ValueError(f"Unknown scheme: {scheme!r}")

    weights = VIMSHOPAKA_WEIGHTS[scheme]
    navamsa = calculate_navamsa_chart(d1) if "D9" in weights else None
    planets: List[str] = list(PHYSICAL_PLANETS)
    if include_nodes:
        planets += ["Rahu", "Ketu"]

    result = VimsopakaResult(scheme=scheme)
    for planet in planets:
        ps = d1.planets[planet]
        total = 0.0
        per_varga: Dict[str, float] = {}
        good = 0
        for varga, weight in weights.items():
            if varga == "D1":
                sign, dignity = ps.sign, ps.dignity
            elif varga == "D9":
                np = navamsa.planets[planet]
                sign, dignity = np.d9_sign, np.d9_dignity
            else:
                sign_idx = varga_sign_index(
                    varga, ps.longitude, ps.sign_index, ps.degree_in_sign)
                sign = INDEX_TO_SIGN[sign_idx]
                dignity = _calculate_dignity(planet, sign, ps.degree_in_sign,
                                             allow_moolatrikona=False)

            if varga == "D2":
                special = _hora_points(planet, sign)
                if special is not None:
                    dignity = "Own" if special >= 20.0 else dignity

            points = VARGAVISVA.get(dignity, 10.0)
            contribution = weight * points / 20.0
            total += contribution
            per_varga[varga] = round(contribution, 3)
            if dignity in ("Exalted", "Own", "Moolatrikona"):
                good += 1

        result.scores[planet] = VimsopakaScore(
            planet=planet,
            total=round(total, 2),
            per_varga=per_varga,
            good_varga_count=good,
            vaiseshikamsa=VAISESHIKAMSA[scheme].get(good),
            grade=_grade(total),
        )

    result.note = (
        f"Vimshopak Bala ({scheme}); natural friendship only (compound "
        "pancha-dha friendship not modelled); nodes "
        f"{'included as supplementary' if include_nodes else 'excluded'}."
    )
    return result


def format_vimsopaka(result: VimsopakaResult) -> str:
    """Compact plain-text block for consumer payloads."""
    lines = [f"Vimshopak Bala ({result.scheme}):"]
    for planet in PHYSICAL_PLANETS:
        score = result.scores.get(planet)
        if score is None:
            continue
        amsa = f", {score.vaiseshikamsa}" if score.vaiseshikamsa else ""
        lines.append(
            f"  {planet}: {score.total:.2f}/20 — {score.grade} "
            f"({score.good_varga_count} good vargas{amsa})"
        )
    return "\n".join(lines)
