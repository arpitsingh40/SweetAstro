"""
Jaimini Argala — planetary intervention on a sign/house.

Classical rule (BPHS ch. 31; Jaimini Sutras I.1.5-12):
- Argala (intervention) is caused by occupants of the 2nd, 4th, and 11th
  signs from the reference, with the 5th as a special (sutra) argala.
- Virodha argala (counter-intervention) comes from the 12th, 10th, and 3rd
  respectively (9th counters the 5th).
- Occupants are counted per planet; more occupants wins the pair, equal
  counts are contested, fewer are blocked. Net argala = sum of pair results.

Only planetary occupancy is counted (sign-as-argala variants are not
applied). Interpretive only — no accuracy claim.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .chart import D1Chart
from .constants import INDEX_TO_SIGN

ARGALA_PAIRS: List[Tuple[int, int]] = [(2, 12), (4, 10), (11, 3), (5, 9)]


@dataclass
class ArgalaPair:
    argala_house: int
    virodha_house: int
    argala_planets: List[str] = field(default_factory=list)
    virodha_planets: List[str] = field(default_factory=list)
    outcome: str = "none"  # argala / virodha / contested / none


@dataclass
class ArgalaResult:
    reference_house: int
    reference_sign: str
    pairs: List[ArgalaPair] = field(default_factory=list)
    net_score: int = 0
    verdict: str = "neutral"
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "reference_house": self.reference_house,
            "reference_sign": self.reference_sign,
            "net_score": self.net_score,
            "verdict": self.verdict,
            "pairs": [
                {
                    "argala_house": p.argala_house,
                    "virodha_house": p.virodha_house,
                    "argala_planets": p.argala_planets,
                    "virodha_planets": p.virodha_planets,
                    "outcome": p.outcome,
                }
                for p in self.pairs
            ],
            "note": self.note,
        }


def _house_occupants(d1: D1Chart, house: int) -> List[str]:
    return list(d1.houses[house].occupants)


def compute_argala(d1: D1Chart, reference_house: int = 1) -> ArgalaResult:
    """
    Computes Argala and Virodha Argala on a reference house (1-12).
    The 5th/9th pair is the special argala recorded in the Jaimini Sutras.
    """
    if not 1 <= reference_house <= 12:
        raise ValueError("reference_house must be 1..12")

    ref_sign = d1.houses[reference_house].sign
    pairs: List[ArgalaPair] = []
    net = 0

    for argala_offset, virodha_offset in ARGALA_PAIRS:
        argala_house = ((reference_house - 1 + argala_offset - 1) % 12) + 1
        virodha_house = ((reference_house - 1 + virodha_offset - 1) % 12) + 1
        argala_planets = _house_occupants(d1, argala_house)
        virodha_planets = _house_occupants(d1, virodha_house)

        if len(argala_planets) > len(virodha_planets):
            outcome = "argala"
            net += 1
        elif len(argala_planets) < len(virodha_planets):
            outcome = "virodha"
            net -= 1
        elif argala_planets:
            outcome = "contested"
        else:
            outcome = "none"

        pairs.append(ArgalaPair(
            argala_house=argala_house,
            virodha_house=virodha_house,
            argala_planets=argala_planets,
            virodha_planets=virodha_planets,
            outcome=outcome,
        ))

    if net >= 2:
        verdict = "strong support"
    elif net == 1:
        verdict = "mild support"
    elif net == 0:
        verdict = "balanced"
    elif net == -1:
        verdict = "mild obstruction"
    else:
        verdict = "strong obstruction"

    return ArgalaResult(
        reference_house=reference_house,
        reference_sign=ref_sign,
        pairs=pairs,
        net_score=net,
        verdict=verdict,
        note=("Planetary-occupancy argala only; sign-as-argala variants and "
              "node-specific exceptions are not applied."),
    )


def argala_summary(d1: D1Chart, reference_house: int = 1) -> str:
    """One-line plain-text summary for consumer payloads."""
    result = compute_argala(d1, reference_house)
    return (f"Argala on H{result.reference_house} ({result.reference_sign}): "
            f"{result.verdict} (net {result.net_score:+d}).")
