"""
SweetAstro Top-Level Service API.
Unified interface for:
- Consumer Answer Engine (general questions, Sec 1-16) via `answer_question`
- Legacy Marriage Prediction (kept for backward compat) via `predict_marriage`
- Sensitivity Testing, Backtesting, and Method Tournaments.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .core.chart import calculate_d1_chart
from .core.navamsa import calculate_navamsa_chart
from .core.jaimini import calculate_chara_karakas, calculate_jaimini_points
from .core.dasha import calculate_vimshottari_timeline
from .rules.loader import RuleCatalog
from .rules.evaluator import RuleEvaluator
from .prediction.hierarchy import PredictionHierarchy, ProgressivePrediction
from .prediction.sensitivity import evaluate_birth_time_sensitivity, SensitivityReport
from .backtest.runner import BlindBacktestRunner
from .backtest.tournament import MethodTournamentRunner, MethodTournamentResult
from .backtest.metrics import BacktestSummaryMetrics
from .llm.answer_engine import AnswerSynthesisEngine, DecisiveUserAnswer
from .consumer import answer_question as _answer_question, ConsumerResult
from .core.geocode import resolve_coordinates


class SweetAstroEngine:
    def __init__(self, rules_dir: Optional[Path] = None):
        self.catalog = RuleCatalog()
        if rules_dir is None:
            # Default to data/rules relative to this file
            rules_dir = Path(__file__).parent.parent / "data" / "rules"

        if rules_dir.exists():
            self.catalog.load_from_directory(rules_dir)

        self.evaluator = RuleEvaluator(self.catalog)
        self.hierarchy = PredictionHierarchy(self.evaluator)
        self.synthesis = AnswerSynthesisEngine()
        self.backtest_runner = BlindBacktestRunner(self.catalog)
        self.tournament_runner = MethodTournamentRunner(self.backtest_runner)

    def predict_marriage(
        self,
        year: int, month: int, day: int,
        hour: int, minute: int, second: float = 0.0,
        tz_offset: float = 5.5,
        lat: float = 28.6139, lon: float = 77.2090,
        name: str = "Native",
        search_start_age: Optional[int] = None,
        search_end_age: Optional[int] = None,
        place: str = "",
        geocode_provider: str = "nominatim",
    ) -> DecisiveUserAnswer:
        """
        Executes complete prediction workflow:
        Chart Engine -> D1/D9/Dasha/Transits/Jaimini -> Progressive Hierarchy -> Sensitivity -> Bold Answer

        When `place` is non-empty it is geocoded (open-source Nominatim by
        default, Google when geocode_provider="google") and the resolved
        coordinates win over `lat`/`lon`.
        """
        lat, lon, _geo_note = resolve_coordinates(place, lat, lon, provider=geocode_provider)
        birth_dt = datetime(year, month, day, hour, minute, int(second))

        # 1. Deterministic Chart Engine
        d1 = calculate_d1_chart(year, month, day, hour, minute, second, tz_offset, lat, lon)
        d9 = calculate_navamsa_chart(d1)
        karakas = calculate_chara_karakas(d1)
        jaimini_pts = calculate_jaimini_points(d1, d9)
        timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)

        # 2. Prediction Hierarchy
        pred = self.hierarchy.predict(
            d1, d9, karakas, jaimini_pts, birth_dt, timeline,
            search_start_age=search_start_age,
            search_end_age=search_end_age
        )

        # 3. Birth-Time Uncertainty Engine (±10 minutes)
        sensitivity = evaluate_birth_time_sensitivity(
            year, month, day, hour, minute, second,
            tz_offset, lat, lon,
            window_minutes=10, step_minutes=2
        )

        # 4. Decisive Bold-Answer Synthesis (legacy; prefer answer_question for new code)
        answer = self.synthesis.generate_decisive_answer(pred, sensitivity)
        return answer

    def answer_question(
        self,
        year: int, month: int, day: int,
        hour: int, minute: int, second: float = 0.0,
        tz_offset: float = 5.5,
        lat: float = 28.6139, lon: float = 77.2090,
        place: str = "",
        question: str = "general",
        time_reliable: bool = True,
        query_dt: Optional[datetime] = None,
        historical_events: Optional[List[Dict[str, Any]]] = None,
        geocode_provider: str = "nominatim",
    ) -> ConsumerResult:
        """
        Consumer Answer Engine (Sec 1-16): any question, calibrated language,
        chart-specific remedies, safety-gated. Never guesses positions.

        When `place` is non-empty it is geocoded (open-source Nominatim by
        default, Google when geocode_provider="google") and the resolved
        coordinates win over `lat`/`lon`.
        """
        lat, lon, _geo_note = resolve_coordinates(place, lat, lon, provider=geocode_provider)
        return _answer_question(
            year=year, month=month, day=day, hour=hour, minute=minute,
            second=second, tz_offset=tz_offset, lat=lat, lon=lon,
            place=place, question=question, time_reliable=time_reliable,
            query_dt=query_dt, historical_events=historical_events,
        )

    def run_backtest(self, dataset_path: Path) -> Tuple[BacktestSummaryMetrics, Any]:
        """Runs blind backtesting on a historical dataset."""
        return self.backtest_runner.run_dataset_backtest(dataset_path)

    def run_tournament(self, dataset_path: Path) -> List[MethodTournamentResult]:
        """Runs method tournaments comparing multiple astrology models."""
        return self.tournament_runner.run_tournament(dataset_path)
