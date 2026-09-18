"""
Full Varga Matrix — every graha in every supported divisional chart.

Covers the 16 Parashari shodashavarga plus the commonly used non-Parashari
charts D5, D6, D8, D11 and the higher cyclic charts D81/D108/D144
(23 charts in total), with each varga's ascendant,
and each planet's sign, whole-sign house, dignity and same-sign-as-D1 flag.

Built only from `calculate_varga_chart` — one deterministic source of truth.
Interpretive reference only; no accuracy claim.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .chart import D1Chart

PARASHARI_VARGAS: Tuple[str, ...] = (
    "D1", "D2", "D3", "D4", "D7", "D9", "D10", "D12", "D16",
    "D20", "D24", "D27", "D30", "D40", "D45", "D60",
)

NON_PARASHARI_VARGAS: Tuple[str, ...] = ("D5", "D6", "D8", "D11", "D81", "D108", "D144")

ALL_VARGAS: Tuple[str, ...] = PARASHARI_VARGAS + NON_PARASHARI_VARGAS


@dataclass
class MatrixPlanet:
    planet: str
    sign: str
    house: int
    dignity: str
    same_sign_as_d1: bool  # varga sign == D1 sign (classical vargottama only for D9)

    def to_dict(self) -> Dict:
        return {
            "planet": self.planet,
            "sign": self.sign,
            "house": self.house,
            "dignity": self.dignity,
            "same_sign_as_d1": self.same_sign_as_d1,
        }


@dataclass
class MatrixChart:
    varga: str
    family: str  # "parashari" | "non-parashari"
    topic: str
    ascendant: str
    planets: Dict[str, MatrixPlanet] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "varga": self.varga,
            "family": self.family,
            "topic": self.topic,
            "ascendant": self.ascendant,
            "planets": {p: v.to_dict() for p, v in self.planets.items()},
        }


@dataclass
class FullVargaMatrix:
    charts: Dict[str, MatrixChart] = field(default_factory=dict)

    def to_lines(self) -> List[str]:
        """Compact one-line-per-varga block for LLM payloads."""
        lines: List[str] = []
        for varga in ALL_VARGAS:
            chart = self.charts.get(varga)
            if chart is None:
                continue
            rows = []
            for planet, p in chart.planets.items():
                echo = " same-sign-as-D1" if p.same_sign_as_d1 else ""
                rows.append(f"{planet}→{p.sign}(H{p.house},{p.dignity}{echo})")
            lines.append(
                f"- {varga} [{chart.family}; {chart.topic}] lagna {chart.ascendant}: "
                + " | ".join(rows)
            )
        return lines

    def to_dict(self) -> Dict:
        return {v: c.to_dict() for v, c in self.charts.items()}


def calculate_full_varga_matrix(d1: D1Chart) -> FullVargaMatrix:
    """Computes all 23 supported divisional charts for all nine grahas."""
    from .vargas import calculate_varga_chart

    matrix = FullVargaMatrix()
    for varga in ALL_VARGAS:
        vc = calculate_varga_chart(d1, varga)
        family = "parashari" if varga in PARASHARI_VARGAS else "non-parashari"
        planets: Dict[str, MatrixPlanet] = {}
        for name, vp in vc.planets.items():
            same_sign = vp.is_vargottama if varga != "D1" else False
            planets[name] = MatrixPlanet(
                planet=name,
                sign=vp.varga_sign,
                house=vp.varga_house,
                dignity=vp.varga_dignity,
                same_sign_as_d1=same_sign,
            )
        matrix.charts[varga] = MatrixChart(
            varga=varga,
            family=family,
            topic=vc.topic,
            ascendant=vc.ascendant_sign,
            planets=planets,
        )
    return matrix
