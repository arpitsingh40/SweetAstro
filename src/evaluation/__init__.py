"""
SweetAstro Accuracy Evaluation package.

Pre-registered, baseline-controlled evaluation of the marriage timing engine.
See docs/accuracy_protocol.md. No accuracy claim may be made from an
unfrozen or non-held-out run.
"""

from .protocol import PROTOCOL, PROTOCOL_VERSION
from .dataset import ChartRecord, load_dataset, validate_records, split_records
from .harness import PredictedRecord, EvaluationResult, run_evaluation
from .report import render_markdown

__all__ = [
    "PROTOCOL",
    "PROTOCOL_VERSION",
    "ChartRecord",
    "load_dataset",
    "validate_records",
    "split_records",
    "PredictedRecord",
    "EvaluationResult",
    "run_evaluation",
    "render_markdown",
]
