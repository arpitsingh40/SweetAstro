"""
Tests for Marriage Timing Prediction Engine
"""

import pytest
from datetime import datetime, timedelta

from SweetAstro.src.prediction.marriage_timing import (
    MarriageTimingEngine, predict_marriage, get_marriage_summary,
    MarriageStrength, MarriageIndicator
)
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart


@pytest.fixture
def sample_chart():
    """Create a sample chart for testing"""
    d1 = calculate_d1_chart(
        year=1990, month=5, day=15,
        hour=10, minute=30, second=0,
        tz_offset_hours=5.5,
        lat=28.6139, lon=77.2090
    )
    d9 = calculate_navamsa_chart(d1)
    birth_dt = datetime(1990, 5, 15, 10, 30, 0)
    return d1, d9, birth_dt


@pytest.fixture
def engine(sample_chart):
    """Create marriage timing engine"""
    d1, d9, birth_dt = sample_chart
    return MarriageTimingEngine(d1, d9, birth_dt)


class TestMarriagePromise:
    """Test natal promise analysis"""

    def test_natal_promise_returns_structure(self, engine):
        promise = engine.analyze_natal_promise()
        assert hasattr(promise, 'promise_exists')
        assert hasattr(promise, 'strength')
        assert hasattr(promise, 'seventh_lord')
        assert hasattr(promise, 'venus_house')
        assert promise.seventh_lord in ["Sun", "Moon", "Mars", "Mercury",
                                         "Jupiter", "Venus", "Saturn"]
        assert 1 <= promise.venus_house <= 12

    def test_natal_promise_strength_is_valid(self, engine):
        promise = engine.analyze_natal_promise()
        assert isinstance(promise.strength, MarriageStrength)

    def test_delay_factors_are_list(self, engine):
        promise = engine.analyze_natal_promise()
        assert isinstance(promise.delay_factors, list)

    def test_manglik_detection(self, engine):
        promise = engine.analyze_natal_promise()
        assert isinstance(promise.manglik_dosha, bool)


class TestNavamsaConfirmation:
    """Test Navamsa confirmation"""

    def test_navamsa_returns_structure(self, engine):
        navamsa = engine.confirm_with_navamsa()
        assert hasattr(navamsa, 'confirmed')
        assert hasattr(navamsa, 'd9_7th_lord')
        assert hasattr(navamsa, 'vargottama_7th_lord')
        assert isinstance(navamsa.confirmed, bool)

    def test_navamsa_strength_is_valid(self, engine):
        navamsa = engine.confirm_with_navamsa()
        assert isinstance(navamsa.strength, MarriageStrength)


class TestTransitAnalysis:
    """Test transit analysis"""

    def test_transit_returns_structure(self, engine):
        transit = engine.analyze_transits(datetime.now())
        assert hasattr(transit, 'jupiter_transit_active')
        assert hasattr(transit, 'saturn_transit_active')
        assert hasattr(transit, 'double_transit_active')
        assert isinstance(transit.jupiter_transit_active, bool)

    def test_transit_at_different_dates(self, engine):
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 6, 15),
            datetime(2025, 3, 20),
        ]
        for date in dates:
            transit = engine.analyze_transits(date)
            assert isinstance(transit.double_transit_active, bool)


class TestDashaWindows:
    """Test Vimshottari Dasha window finding"""

    def test_find_dashas_returns_list(self, engine):
        windows = engine.find_marriage_dashas(
            datetime(2024, 1, 1),
            datetime(2030, 12, 31)
        )
        assert isinstance(windows, list)

    def test_windows_have_required_fields(self, engine):
        windows = engine.find_marriage_dashas(
            datetime(2024, 1, 1),
            datetime(2030, 12, 31)
        )
        for window in windows:
            assert hasattr(window, 'start_date')
            assert hasattr(window, 'end_date')
            assert hasattr(window, 'confidence')
            assert hasattr(window, 'mahadasha_lord')
            assert isinstance(window.confidence, MarriageStrength)


class TestMonthPrediction:
    """Test marriage month prediction"""

    def test_predict_month_returns_list(self, engine):
        months = engine.predict_month(2025)
        assert isinstance(months, list)

    def test_months_are_valid(self, engine):
        months = engine.predict_month(2025)
        for month_num, reason in months:
            assert 1 <= month_num <= 12
            assert isinstance(reason, str)


class TestFullPrediction:
    """Test complete marriage prediction"""

    def test_predict_marriage_returns_structure(self, engine, sample_chart):
        _, _, birth_dt = sample_chart
        prediction = engine.predict_marriage_timing(birth_dt)
        assert hasattr(prediction, 'promise')
        assert hasattr(prediction, 'navamsa')
        assert hasattr(prediction, 'windows')
        assert hasattr(prediction, 'best_window')
        assert hasattr(prediction, 'overall_strength')
        assert hasattr(prediction, 'recommendations')

    def test_predict_marriage_convenience_function(self, sample_chart):
        d1, d9, birth_dt = sample_chart
        prediction = predict_marriage(d1, d9, birth_dt)
        assert prediction is not None
        assert isinstance(prediction.overall_strength, MarriageStrength)

    def test_get_marriage_summary(self, sample_chart):
        d1, d9, birth_dt = sample_chart
        prediction = predict_marriage(d1, d9, birth_dt)
        summary = get_marriage_summary(prediction)
        assert isinstance(summary, str)
        assert "MARRIAGE TIMING PREDICTION" in summary
        assert "NATAL PROMISE" in summary
        assert "NAVAMSA CONFIRMATION" in summary


class TestEdgeCases:
    """Test edge cases"""

    def test_very_young_person(self):
        d1 = calculate_d1_chart(
            year=2010, month=1, day=1,
            hour=12, minute=0, second=0,
            tz_offset_hours=5.5,
            lat=28.6139, lon=77.2090
        )
        d9 = calculate_navamsa_chart(d1)
        birth_dt = datetime(2010, 1, 1, 12, 0, 0)
        engine = MarriageTimingEngine(d1, d9, birth_dt)
        prediction = engine.predict_marriage_timing(birth_dt, datetime.now())
        assert prediction is not None

    def test_different_locations(self):
        locations = [
            (28.6139, 77.2090),   # Delhi
            (40.7128, -74.0060),  # New York
            (51.5074, -0.1278),   # London
        ]
        birth_dt = datetime(1990, 5, 15, 10, 30, 0)
        for lat, lon in locations:
            d1 = calculate_d1_chart(
                year=1990, month=5, day=15,
                hour=10, minute=30, second=0,
                tz_offset_hours=5.5,
                lat=lat, lon=lon
            )
            d9 = calculate_navamsa_chart(d1)
            engine = MarriageTimingEngine(d1, d9, birth_dt)
            promise = engine.analyze_natal_promise()
            assert promise is not None
