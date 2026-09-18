"""
Decisive Bold-Answer and Synthesis Engine (LEGACY).

Retained only for backward compatibility (CLI demo, `/api/predict`, tests).
It emits the deprecated bold headline ("You will get married in ...") and does
not apply the calibrated consumer language; new integrations must use
`SweetAstroEngine.answer_question` instead.

Internal payload strengths are reported honestly: legacy mode does not run the
rule evaluator per factor, so only the transit signal (derived from the actual
transit summary) is populated; the rest are marked "Not assessed".
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from ..prediction.hierarchy import ProgressivePrediction
from ..prediction.ensemble import SystemEnsemble
from ..prediction.sensitivity import SensitivityReport
from .explainability import PredictionExplainability


@dataclass
class InternalPredictionPayload:
    """Internal statistical and astrological bookkeeping (Points 22 & 30)."""
    event: str = "Marriage"
    best_period: str = ""
    year_score: float = 0.0
    month_score: float = 0.0
    parashari_strength: str = "Strong"
    d9_strength: str = "Strong"
    vimshottari_strength: str = "Strong"
    transit_strength: str = "Strong"
    jaimini_strength: str = "Moderate"
    birth_time_stability_pct: float = 0.0
    stability_classification: str = "High"
    negative_evidence_score: float = 0.0
    why_not_other_months: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisiveUserAnswer:
    """The clean, bold user-facing answer layer (Point 50)."""
    bold_headline: str
    why_saying_this: str
    what_happens_before_then: str
    partner_and_marriage_profile: str
    why_the_delay: str
    what_to_do_now: str
    closing_question: str
    internal_payload: InternalPredictionPayload


class AnswerSynthesisEngine:
    def __init__(self):
        self.explainer = PredictionExplainability()

    def generate_decisive_answer(
        self,
        pred: ProgressivePrediction,
        sensitivity: SensitivityReport
    ) -> DecisiveUserAnswer:
        """
        Synthesizes the bold direct prediction while preserving rigorous internal state.
        """
        ensemble = SystemEnsemble()
        gated = not pred.promise_indicated
        best_period = pred.best_month if not gated else "withheld (weak natal promise)"
        best_cand = pred.top_months[0] if (not gated and pred.top_months) else None
        # Unified ensemble scale (same score used by hierarchy levels 3-5).
        month_score = ensemble.score_period(best_cand.convergence) if best_cand else 0.0
        year_score = (ensemble.score_period(pred.top_years[0].convergence)
                      if (not gated and pred.top_years) else 0.0)

        # Build internal payload (honest legacy signals only)
        why_not = self.explainer.generate_why_not_other_months(pred)
        transit_active = bool(best_cand and "Double Transit" in best_cand.transit_summary)
        internal = InternalPredictionPayload(
            event="Marriage",
            best_period=best_period,
            year_score=year_score,
            month_score=month_score,
            parashari_strength="Not assessed (legacy mode)",
            d9_strength="Not assessed (legacy mode)",
            vimshottari_strength="Not assessed (legacy mode)",
            transit_strength="Double transit active" if transit_active else "No double transit in best window",
            jaimini_strength="Not assessed (legacy mode)",
            birth_time_stability_pct=sensitivity.overall_stability_score,
            stability_classification=sensitivity.stability_classification,
            negative_evidence_score=best_cand.convergence.negative_obstruction if best_cand else 0.0,
            why_not_other_months=why_not
        )

        # Build decisive user-facing sections (Point 50) — calibrated language only.
        # The legacy absolute headline is retired per docs/accuracy_protocol.md:
        # no date claim is made until the pre-registered evaluation demonstrates skill.
        if gated:
            headline = (f"💍 Timing withheld — the natal promise reads as {pred.promise_strength.lower()} "
                        "in this legacy model, so no marriage window is presented "
                        "(interpretive only; not a prediction or guarantee).")
        else:
            headline = (f"💍 The clearest marriage window this model indicates is around {best_period} "
                        f"(interpretive estimate — not a prediction or guarantee).")

        why_reasons = self.explainer.generate_why_this_period(pred, sensitivity)
        why_text = (
            "The strongest marriage indicators in this model converge around this period across the birth "
            "chart (D1), Navamsa (D9), Vimshottari Dasha, and transit inputs:\n"
            + "\n".join(why_reasons)
        )

        if gated:
            before_then = (
                "Because the natal promise is obstructed in this model, no pre-window timeline is "
                "presented. The limiting factors below are where attention goes first; if they "
                "change, re-run the model for a fresh reading. Interpretive guidance, not a schedule."
            )
        else:
            before_then = (
                f"Traditionally, the 12 to 18 months leading up to {best_period} are described as a shift away from "
                f"ambiguity and toward emotional readiness; connections and conversations about partnership often "
                f"intensify 6 to 9 months before this window as the planetary sub-periods change. Treat this as "
                f"interpretive guidance, not a scheduled event."
            )

        partner_profile = (
            f"The 7th house configuration and Navamsa alignment suggest a partner who is intellectually grounded, "
            f"values stability, and brings a calm, balancing presence. The traditional reading favours a relationship "
            f"built on mutual respect and shared practical goals rather than superficial excitement."
        )

        delay_explanation = (
            f"If marriage has felt distant so far, the traditional explanation is that Saturn and the planetary "
            f"maturity cycles call for solidifying career, emotional boundaries, and self-definition first. "
            f"Whether that delay was protective preparation is for you to judge — the chart does not prove it."
        )

        actionable_advice = (
            f"Clarify what non-negotiable partnership means to you now. Do not force premature commitments, but remain open "
            f"and socially receptive—the foundation for this milestone is already being laid."
        )

        closing_q = "What are you more afraid of—never finding the right person, or choosing the wrong person?"

        return DecisiveUserAnswer(
            bold_headline=headline,
            why_saying_this=why_text,
            what_happens_before_then=before_then,
            partner_and_marriage_profile=partner_profile,
            why_the_delay=delay_explanation,
            what_to_do_now=actionable_advice,
            closing_question=closing_q,
            internal_payload=internal
        )
