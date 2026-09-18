"""
Explainability helper for the legacy progressive prediction model (LEGACY).

Produces "why this period" and "why not other months" text for the CLI demo
and the legacy dashboard. Language is calibrated: scores are model convergence
summaries, not probabilities, and no outcome is guaranteed. This module was
rewritten in audit round 2 (MEDIUM) because it previously asserted "clear
fruition", "genuine marital union", and planetary "grace/karma" as facts.
"""

from typing import Any, Dict, List
from ..prediction.hierarchy import ProgressivePrediction
from ..prediction.sensitivity import SensitivityReport

DISCLAIMER = ("These are interpretive model statements, not predictions: the "
              "model has no demonstrated out-of-sample skill (docs/accuracy_protocol.md).")


class PredictionExplainability:
    @staticmethod
    def generate_why_this_period(
        pred: ProgressivePrediction,
        sensitivity: SensitivityReport
    ) -> List[str]:
        """Structured reasons the model ranks this period highest."""
        reasons = []

        if not pred.promise_indicated:
            reasons.append(
                f"1. Promise gate: the natal promise reads '{pred.promise_strength}' in this model, "
                "so no timing period is presented. Review the limiting factors and strengthening guidance."
            )
            reasons.append(
                f"2. Birth-time stability ({sensitivity.overall_stability_score}%): the withheld reading "
                f"does not depend on a ±{sensitivity.window_minutes} minute birth-time window."
            )
            reasons.append(DISCLAIMER)
            return reasons

        reasons.append(
            f"1. Natal promise (model level): '{pred.promise_strength}'. The 7th-house/karaka network "
            "is scored as indicated; this is a convergence reading, not proof."
        )
        reasons.append(
            "2. Navamsa (D9) input: the D9 layer contributes to the convergence score; it is one "
            "weighted input among several, not independent confirmation of an outcome."
        )
        top_cand = pred.top_months[0] if pred.top_months else None
        dasha_info = top_cand.dasha_summary if top_cand else "operating sub-periods"
        reasons.append(
            f"3. Dasha input: the operative Vimshottari period ({dasha_info}) is weighted with the "
            "other systems as a timing input only."
        )
        transit_info = top_cand.transit_summary if top_cand else "no active double transit noted"
        reasons.append(
            f"4. Transit input: {transit_info} — transits are treated as scheduling support, never as "
            "a trigger that creates an event."
        )
        reasons.append(
            f"5. Birth-time stability ({sensitivity.overall_stability_score}%): the ranking holds across "
            f"a ±{sensitivity.window_minutes} minute birth-time variance window."
        )
        reasons.append(DISCLAIMER)
        return reasons

    @staticmethod
    def generate_why_not_other_months(pred: ProgressivePrediction) -> Dict[str, Any]:
        """"Why not other months?" — relative model scores across the candidate year."""
        if not pred.all_monthly_scores:
            return {
                "top_month": "",
                "top_score": 0.0,
                "monthly_breakdown": [],
                "summary": "Timing withheld: the natal promise gate did not clear, so no monthly scores were produced.",
            }

        sorted_months = sorted(pred.all_monthly_scores.items(), key=lambda x: x[1], reverse=True)
        top_month, top_score = sorted_months[0]

        comparison = []
        for m_name, score in pred.all_monthly_scores.items():
            is_winner = (m_name == top_month)
            comparison.append({
                "month": m_name,
                "score": score,
                "is_strongest": is_winner,
                "margin_from_peak": round(top_score - score, 1)
            })

        summary_text = (
            f"{top_month} scores {top_score}/100 on the model's convergence scale — a relative score "
            "share within this year, not a probability. Adjacent months score lower because the "
            "weighted dasha/transit inputs differ."
        )

        return {
            "top_month": top_month,
            "top_score": top_score,
            "monthly_breakdown": comparison,
            "summary": summary_text
        }
