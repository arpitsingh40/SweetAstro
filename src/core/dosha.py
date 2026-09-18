"""
Kendrapati (Kendradhipatya) Dosha — functional-malefic lordship check.

Classical rule (BPHS): a natural benefic that owns kendra houses (1/4/7/10)
but no trine (1/5/9) loses its benefic delivery and acts as a functional
malefic; owning a trine as well restores balance. The classical
"kendradhipati" case is strongest for Jupiter and Venus (the two great
benefics); Mercury and the Moon follow the same test with their standard
caveats (Mercury takes the nature of its association; a waning Moon is
already weak), which are noted rather than resolved here.

Interpretive only — no accuracy claim; used as a strength/limitation note,
never as a standalone judgement.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from .chart import D1Chart
from .constants import NATURAL_BENEFICS

KENDRAS = (1, 4, 7, 10)
TRINES = (1, 5, 9)


@dataclass
class KendrapatiFinding:
    planet: str
    owned_houses: List[int] = field(default_factory=list)
    kendra_houses: List[int] = field(default_factory=list)
    trine_houses: List[int] = field(default_factory=list)
    verdict: str = "clear"  # dosha / mixed / clear
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "planet": self.planet,
            "owned_houses": self.owned_houses,
            "kendra_houses": self.kendra_houses,
            "trine_houses": self.trine_houses,
            "verdict": self.verdict,
            "note": self.note,
        }


@dataclass
class KendrapatiResult:
    findings: Dict[str, KendrapatiFinding] = field(default_factory=dict)
    dosha_planets: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "findings": {p: f.to_dict() for p, f in self.findings.items()},
            "dosha_planets": self.dosha_planets,
            "note": self.note,
        }


def assess_kendrapati(d1: D1Chart) -> KendrapatiResult:
    """
    Evaluates the kendrapati rule for the natural benefics.
    Trines include the 1st (both a kendra and a trine).
    """
    result = KendrapatiResult()
    for planet in NATURAL_BENEFICS:
        owned = sorted(h for h, hs in d1.houses.items() if hs.lord == planet)
        kendra = [h for h in owned if h in KENDRAS]
        trine = [h for h in owned if h in TRINES]

        if not kendra:
            verdict, note = "clear", "No kendra lordship — rule not applicable."
        elif trine:
            verdict, note = "mixed", (
                "Owns a trine alongside a kendra; the kendrapati weakness is "
                "balanced and the benefic delivery is retained."
            )
        else:
            verdict, note = "dosha", (
                "Owns kendra(s) without a trine; acts as a functional malefic "
                "for this nativity — results come with delay or conditionality."
            )

        finding = KendrapatiFinding(
            planet=planet, owned_houses=owned, kendra_houses=kendra,
            trine_houses=trine, verdict=verdict, note=note,
        )
        result.findings[planet] = finding
        if verdict == "dosha":
            result.dosha_planets.append(planet)

    result.note = (
        "Natural-benefic kendra lordship only; Mercury/Moon caveats "
        "(association and paksha bala) are noted, not resolved."
    )
    return result


def kendrapati_summary(d1: D1Chart) -> str:
    """One-line plain-text summary for consumer payloads."""
    result = assess_kendrapati(d1)
    if not result.dosha_planets:
        return "Kendrapati dosha: none of the natural benefics is kendra-only."
    return ("Kendrapati dosha: " + ", ".join(result.dosha_planets) +
            " own kendra(s) without a trine — functional-malefic condition.")
