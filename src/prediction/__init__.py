"""
SweetAstro Prediction Engine.
"""

from .convergence import ConvergenceBreakdown, calculate_convergence_score
from .sensitivity import SensitivityReport, evaluate_birth_time_sensitivity
from .hierarchy import (
    CandidatePeriod, ProgressivePrediction, PredictionHierarchy
)
from .ensemble import EnsembleWeights, SystemEnsemble
# LEGACY (reference only; unused by production paths — see module docstring).
from .marriage_timing import (
    MarriageTimingEngine, MarriagePrediction, MarriagePromise,
    NavamsaConfirmation, TransitTrigger, MarriageWindow,
    MarriageStrength, MarriageIndicator,
    predict_marriage, get_marriage_summary
)

__all__ = [
    "ConvergenceBreakdown",
    "calculate_convergence_score",
    "SensitivityReport",
    "evaluate_birth_time_sensitivity",
    "CandidatePeriod",
    "ProgressivePrediction",
    "PredictionHierarchy",
    "EnsembleWeights",
    "SystemEnsemble",
    "MarriageTimingEngine",
    "MarriagePrediction",
    "MarriagePromise",
    "NavamsaConfirmation",
    "TransitTrigger",
    "MarriageWindow",
    "MarriageStrength",
    "MarriageIndicator",
    "predict_marriage",
    "get_marriage_summary",
]
