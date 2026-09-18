"""
Multi-System Prediction Ensemble.

The ensemble scores a period from a ConvergenceBreakdown using configurable
weights over the five knowledge systems (Parashari, D9, Dasha, Transit,
Jaimini).

Weight *optimization* is intentionally disabled: the previous grid search
silently fed an invalid dasha object and a None transit result into the
scorer, so every sample raised internally and every configuration scored
identically. Weight fitting now belongs to the pre-registered accuracy
protocol (see `docs/accuracy_protocol.md` and `accuracy_backtest.py`), where
it can be validated out-of-sample instead of being silently broken.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .convergence import ConvergenceBreakdown, calculate_convergence_score


@dataclass
class EnsembleWeights:
    parashari: float = 0.25
    d9: float = 0.20
    dasha: float = 0.25
    transit: float = 0.20
    jaimini: float = 0.10

    def total(self) -> float:
        return sum([self.parashari, self.d9, self.dasha, self.transit, self.jaimini])

    def to_dict(self) -> Dict[str, float]:
        return {
            "parashari": self.parashari,
            "d9": self.d9,
            "dasha": self.dasha,
            "transit": self.transit,
            "jaimini": self.jaimini,
        }


@dataclass
class WeightConfiguration:
    parashari: float
    d9: float
    dasha: float
    transit: float
    jaimini: float


class SystemEnsemble:
    WEIGHT_KEYS = ["parashari", "d9", "dasha", "transit", "jaimini"]

    def __init__(self, weights: Optional[EnsembleWeights] = None):
        self.weights = weights or EnsembleWeights()

    def score_period(
        self, conv: ConvergenceBreakdown,
        weights: Optional[EnsembleWeights] = None
    ) -> float:
        w = weights or self.weights
        norm_parashari = (conv.d1_support / 25.0) * 100.0
        norm_d9 = (conv.d9_support / 20.0) * 100.0
        norm_dasha = (conv.dasha_support / 30.0) * 100.0
        norm_transit = (conv.transit_support / 25.0) * 100.0
        norm_jaimini = (conv.jaimini_support / 15.0) * 100.0

        score = (
            (norm_parashari * w.parashari)
            + (norm_d9 * w.d9)
            + (norm_dasha * w.dasha)
            + (norm_transit * w.transit)
            + (norm_jaimini * w.jaimini)
        )
        obstruction_penalty = (conv.negative_obstruction / 25.0) * 20.0
        yoga_bonus = conv.yoga_bonus * 0.5
        shab_bonus = conv.shadbala_bonus * 0.3
        final_score = max(0.0, min(100.0, score + yoga_bonus + shab_bonus - obstruction_penalty))
        return round(final_score, 1)

    def optimize_weights(self, *args, **kwargs) -> EnsembleWeights:
        """Disabled — see module docstring."""
        raise NotImplementedError(
            "SystemEnsemble.optimize_weights is disabled: the previous implementation "
            "passed a timeline list as the dasha state and a None double-transit result "
            "into the scorer, so every sample errored and every configuration scored "
            "identically. Use the pre-registered protocol in accuracy_backtest.py "
            "(docs/accuracy_protocol.md) for weight evaluation."
        )
