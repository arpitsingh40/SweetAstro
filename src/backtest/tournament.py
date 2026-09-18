"""
Method Tournaments and Rule Leaderboard Engine.
Implements Point 26 and Point 39: Empirically compares different astrology models
and ranks individual rules based on predictive precision.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from pathlib import Path

from ..prediction.ensemble import EnsembleWeights
from .runner import BlindBacktestRunner
from .metrics import BacktestSummaryMetrics, SingleEvaluationRecord


@dataclass
class MethodTournamentResult:
    model_name: str
    description: str
    weights: EnsembleWeights
    metrics: BacktestSummaryMetrics


@dataclass
class RulePerformanceRecord:
    rule_id: str
    rule_interpretation: str
    category: str
    total_evaluations: int
    triggered_count: int
    true_positive_timing: int     # When rule fired and marriage was within predicted top 3
    precision_pct: float


class MethodTournamentRunner:
    def __init__(self, runner: BlindBacktestRunner):
        self.runner = runner

    def run_tournament(self, dataset_path: Path) -> List[MethodTournamentResult]:
        """
        Tests multiple methodology configurations against the same historical dataset.
        """
        configurations = [
            ("Model 1: Parashari Only", "D1 7th house and planetary aspects only", EnsembleWeights(parashari=1.0, d9=0.0, dasha=0.0, transit=0.0, jaimini=0.0)),
            ("Model 2: Parashari + D9", "D1 foundation confirmed by Navamsa D9", EnsembleWeights(parashari=0.55, d9=0.45, dasha=0.0, transit=0.0, jaimini=0.0)),
            ("Model 3: Parashari + D9 + Dasha", "Adds Vimshottari timing activation", EnsembleWeights(parashari=0.35, d9=0.30, dasha=0.35, transit=0.0, jaimini=0.0)),
            ("Model 4: Parashari + D9 + Dasha + Transit", "Adds Jupiter-Saturn double transit", EnsembleWeights(parashari=0.25, d9=0.25, dasha=0.25, transit=0.25, jaimini=0.0)),
            ("Model 5: Full Ensemble (+ Jaimini)", "Complete Parashari, D9, Dasha, Transit, and Jaimini ensemble", EnsembleWeights(parashari=0.25, d9=0.20, dasha=0.25, transit=0.20, jaimini=0.10)),
        ]

        results: List[MethodTournamentResult] = []
        for name, desc, weights in configurations:
            # Run backtest with these ensemble weights
            summary, _ = self.runner.run_dataset_backtest(dataset_path, ensemble_weights=weights)
            results.append(
                MethodTournamentResult(
                    model_name=name,
                    description=desc,
                    weights=weights,
                    metrics=summary
                )
            )

        # Sort descending by top-3 year accuracy
        results.sort(key=lambda x: (x.metrics.top_3_year_accuracy, -x.metrics.mean_absolute_error_months), reverse=True)
        return results
