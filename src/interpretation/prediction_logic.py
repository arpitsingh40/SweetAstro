"""
Structured Prediction Logic — Consumer Engine Sec 6.

Every major prediction carries:
Signal / Mechanism / Timing / Strength / Risk / Confidence.
No 100% certainty. Calibrated language only.
"""

from dataclasses import dataclass, field
from typing import List, Literal

Strength = Literal["Strong", "Moderate", "Weak"]
Confidence = Literal["Low", "Medium", "High"]


@dataclass
class Prediction:
    topic: str
    signal: str              # astrological combination
    mechanism: str           # how combination connects to subject
    timing: str              # Dasha/transit activation
    strength: Strength
    risk: str                # what could prevent/reverse
    confidence: Confidence
    confidence_reason: str
    statement: str           # consumer-safe phrasing (no guarantees)

    def to_dict(self):
        return {
            "topic": self.topic,
            "signal": self.signal,
            "mechanism": self.mechanism,
            "timing": self.timing,
            "strength": self.strength,
            "risk": self.risk,
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "statement": self.statement,
        }


def calibrate_confidence(n_independent_factors: int, time_reliable: bool,
                         dasha_supports: bool, transit_supports: bool) -> Confidence:
    """
    Transparent calibration:
    - High needs >=3 independent factors + Dasha support (+ transit ideally)
      AND a reliable birth time; uncertain time caps confidence at Medium.
    - Medium: 2+ factors with Dasha support (or 3 without).
    - Else Low.
    """
    score = n_independent_factors
    if dasha_supports:
        score += 1
    if transit_supports:
        score += 1
    if not time_reliable:
        score -= 1
    if score >= 5:
        return "High" if time_reliable else "Medium"
    if score >= 3:
        return "Medium"
    return "Low"


def safe_statement(template_topic: str, strength: Strength, timing: str, condition: str) -> str:
    """
    Builds non-absolute phrasing. Never 'definitely/will surely/guaranteed'.
    """
    strength_word = {"Strong": "strong potential", "Moderate": "moderate potential", "Weak": "limited indication"}[strength]
    return (f"Jyotish indicates {strength_word} for {template_topic}, "
            f"with the clearest activation {timing}, provided {condition}.")
