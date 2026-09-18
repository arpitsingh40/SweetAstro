"""
Gemstone Gate — Consumer Engine Sec 10, extended with suitability scoring.

Never automatic. Checks lordship, ownership, placement, dignity, affliction,
Dasha relevance, risk of intensifying negatives, and prefers non-gemstone
alternatives. Any mention must include why considered + why unsuitable +
verification need + lower-risk alternative, plus a transparent suitability
score and safety class.

Safety classes:
- "avoid-as-strengthening" — mentioning is allowed, but strengthening here is
  discouraged (default for the nodes and for afflicted/dusthana planets).
- "mention-only" — may be mentioned with full caveats; not recommended.
- "consider-with-verification" — the only class where a gemstone may be
  considered, still optional and requiring professional verification.

The score is an analytical heuristic (0–100), not classical Shadbala/gem
proportionality; it must never be presented as a prescription.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ..core.strength import StrengthAssessment

PLANET_GEMS = {
    "Sun": "Ruby (Manik)", "Moon": "Pearl (Moti)", "Mars": "Red Coral (Moonga)",
    "Mercury": "Emerald (Panna)", "Jupiter": "Yellow Sapphire (Pukhraj)",
    "Venus": "Diamond/Opal (Heera/Opal)", "Saturn": "Blue Sapphire (Neelam)",
    "Rahu": "Hessonite (Gomed)", "Ketu": "Cat's Eye (Lehsunia)",
}


@dataclass
class GemstoneVerdict:
    mention_allowed: bool
    gem: str
    why_considered: str
    why_unsuitable: str
    alternative: str
    note: str
    suitability_score: int = 0
    safety: str = "mention-only"
    reasons: List[str] = field(default_factory=list)


def _reasons(assessment: StrengthAssessment, in_relevant_dasha: bool) -> List[str]:
    reasons = [
        f"functional lordship: {assessment.functional_lordship or 'none'}",
        f"placement: house {assessment.house}, dignity {assessment.sign_dignity}",
        f"assessment recommendation: {assessment.recommendation}",
        f"afflicted: {'yes' if assessment.afflicted else 'no'}",
        f"relevant dasha active: {'yes' if in_relevant_dasha else 'no'}",
    ]
    owns_dusthana = any(h in (6, 8, 12) for h in assessment.functional_lordship)
    if owns_dusthana:
        reasons.append("owns dusthana house(s) 6/8/12")
    if assessment.vargottama:
        reasons.append("vargottama (stable across D1/D9)")
    return reasons


def evaluate_gemstone(assessment: StrengthAssessment, in_relevant_dasha: bool) -> GemstoneVerdict:
    planet = assessment.planet
    gem = PLANET_GEMS.get(planet, "traditional gem")
    owns_dusthana = any(h in (6, 8, 12) for h in assessment.functional_lordship)
    reasons = _reasons(assessment, in_relevant_dasha)

    if planet in ("Rahu", "Ketu"):
        return GemstoneVerdict(
            mention_allowed=True, gem=gem,
            why_considered=f"{planet} gemstone is traditionally linked to {planet}, sometimes discussed during {planet} periods.",
            why_unsuitable=(f"Nodes default to pacify/balance ({assessment.recommendation}); strengthening {planet} "
                            "with gemstones/yantras/intense ritual can intensify instability without multi-factor support."),
            alternative=f"Prefer {planet} alignment conduct + service + optional pacifying mantra.",
            note="Requires professional verification; never a necessary or expensive purchase; no guaranteed results.",
            suitability_score=15, safety="avoid-as-strengthening", reasons=reasons,
        )

    if assessment.recommendation in ("pacify", "leave-alone") or (owns_dusthana and assessment.afflicted):
        return GemstoneVerdict(
            mention_allowed=True, gem=gem,
            why_considered=f"{planet} ({assessment.sign_dignity}, {assessment.house}H) is sometimes considered for strengthening.",
            why_unsuitable=(f"Assessment says '{assessment.recommendation}': {assessment.recommendation_reason} "
                            "Strengthening could intensify difficult results."),
            alternative="Prefer alignment conduct, donation/service, or mantra as lower-risk alternative.",
            note="Requires professional verification; never present as necessary or result-guaranteeing.",
            suitability_score=20, safety="mention-only", reasons=reasons,
        )

    if assessment.recommendation == "strengthen" and in_relevant_dasha and not assessment.afflicted:
        return GemstoneVerdict(
            mention_allowed=True, gem=gem,
            why_considered=(f"{planet} is friendly, unafflicted, relevant, and in active Dasha — "
                            "traditional texts sometimes discuss strengthening here."),
            why_unsuitable="Even here: cost, suitability, lifestyle fit, and affliction re-checks may rule it out.",
            alternative="A non-gemstone option (mantra/donation/disciplined conduct) is usually sufficient and lower-risk.",
            note="Requires professional verification of weight/metal/finger/muhurta; optional only; no guarantees.",
            suitability_score=70, safety="consider-with-verification", reasons=reasons,
        )

    if assessment.recommendation == "strengthen" and not assessment.afflicted:
        return GemstoneVerdict(
            mention_allowed=True, gem=gem,
            why_considered=f"{planet} is unafflicted and assessed for strengthening, though not currently in Dasha.",
            why_unsuitable="Outside the active period the traditional rationale is weaker; wait for the Dasha/transit support.",
            alternative="Prefer conduct alignment now; revisit at the next Dasha change.",
            note="Optional; no guarantees; verification with a qualified practitioner required.",
            suitability_score=40, safety="mention-only", reasons=reasons,
        )

    return GemstoneVerdict(
        mention_allowed=False, gem=gem,
        why_considered="",
        why_unsuitable=f"Recommendation is '{assessment.recommendation}'; gemstone strengthening is not appropriate now.",
        alternative="Use alignment + service/mantra instead.",
        note="Not recommended at this time.",
        suitability_score=25, safety="mention-only", reasons=reasons,
    )


_SAFETY_PHRASES = {
    "avoid-as-strengthening": "Gemstone strengthening is not advised in this chart; mention only.",
    "mention-only": "Mention only — not recommended now.",
    "consider-with-verification": ("May be considered with professional verification only; "
                                   "optional and never necessary."),
}


def format_gemstone_note(v: GemstoneVerdict) -> str:
    """Compose the consumer note from the verdict fields (never a hardcoded label).

    The gate's safety class decides the wording; a verdict that disallows
    mention never presents the gemstone as a candidate.
    """
    if not v.mention_allowed:
        return (f"Gemstone ({v.gem}): not presented — {v.why_unsuitable} "
                f"Alternative: {v.alternative} "
                f"(Suitability score {v.suitability_score}/100; safety: {v.safety}.)")
    parts = [f"Gemstone ({v.gem}): {_SAFETY_PHRASES.get(v.safety, v.safety)}"]
    if v.why_considered:
        parts.append(v.why_considered)
    if v.why_unsuitable:
        parts.append(v.why_unsuitable)
    if v.alternative:
        parts.append(f"Alternative: {v.alternative}")
    if v.note:
        parts.append(v.note)
    parts.append(f"Suitability score {v.suitability_score}/100; safety: {v.safety}.")
    return " ".join(parts)
