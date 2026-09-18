"""
Beeja Sphuta & Kshetra Sphuta — classical progeny significators.

Beeja Sphuta (male line)  = Sun + Venus + Jupiter longitudes (mod 360).
Kshetra Sphuta (female line) = Moon + Mars + Jupiter longitudes (mod 360).

Used with Saptamsha (D7) in children-topic delineation. The module returns
the exact longitudes, signs, nakshatras and simple odd/even placement notes;
it deliberately withholds any fertility judgement — that belongs to
practitioner and medical advice, not to software.

Interpretive only — no accuracy claim.
"""

from dataclasses import dataclass
from typing import Dict, List

from .chart import D1Chart, _get_nakshatra_and_pada, _get_sign_and_deg
from .constants import NAKSHATRAS


@dataclass
class SphutaPosition:
    name: str
    longitude: float
    sign: str
    sign_index: int
    degree_in_sign: float
    nakshatra: str
    pada: int
    odd_sign: bool

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "longitude": round(self.longitude, 4),
            "sign": self.sign,
            "degree_in_sign": round(self.degree_in_sign, 4),
            "nakshatra": self.nakshatra,
            "pada": self.pada,
            "odd_sign": self.odd_sign,
        }


@dataclass
class ProgenySphutas:
    beeja: SphutaPosition
    kshetra: SphutaPosition
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "beeja_sphuta": self.beeja.to_dict(),
            "kshetra_sphuta": self.kshetra.to_dict(),
            "note": self.note,
        }


def _sphuta(name: str, longitude: float) -> SphutaPosition:
    norm = longitude % 360.0
    sign, sign_index, deg = _get_sign_and_deg(norm)
    nak, pada, _ = _get_nakshatra_and_pada(norm)
    return SphutaPosition(
        name=name,
        longitude=norm,
        sign=sign,
        sign_index=sign_index,
        degree_in_sign=deg,
        nakshatra=nak,
        pada=pada,
        odd_sign=(sign_index % 2 == 1),
    )


def calculate_progeny_sphutas(d1: D1Chart) -> ProgenySphutas:
    """Computes Beeja and Kshetra Sphuta from the D1 longitudes."""
    sun = d1.planets["Sun"].longitude
    moon = d1.planets["Moon"].longitude
    mars = d1.planets["Mars"].longitude
    jupiter = d1.planets["Jupiter"].longitude
    venus = d1.planets["Venus"].longitude

    beeja = _sphuta("Beeja Sphuta", sun + venus + jupiter)
    kshetra = _sphuta("Kshetra Sphuta", moon + mars + jupiter)

    return ProgenySphutas(
        beeja=beeja,
        kshetra=kshetra,
        note=("Progeny significators only (Beeja = Sun+Venus+Jupiter, "
              "Kshetra = Moon+Mars+Jupiter). No fertility judgement is made; "
              "consult a qualified practitioner and medical advice."),
    )


def format_sphutas(result: ProgenySphutas) -> str:
    """Compact plain-text block for consumer payloads."""
    lines: List[str] = ["Progeny sphutas:"]
    for sphuta in (result.beeja, result.kshetra):
        parity = "odd" if sphuta.odd_sign else "even"
        lines.append(
            f"  {sphuta.name}: {sphuta.sign} {sphuta.degree_in_sign:.2f}deg "
            f"({sphuta.nakshatra} pada {sphuta.pada}, {parity} sign)"
        )
    return "\n".join(lines)
