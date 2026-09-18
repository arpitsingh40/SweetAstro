"""
Regression tests for audit round 4 (2026-09-12):

21. Geocoder throttle/cache were not thread-safe: concurrent requests could
    bypass the Nominatim 1 req/s policy and refetch the same query.
22. /api/panchanga accepted impossible coordinates (lon=720 returned 200).
23. /api/backtest/run and /api/tournament/run let FileNotFoundError escape
    as a 500 instead of a clear 404/400.
24. Backtest metrics and rule-data depth were untested.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from SweetAstro.src.api.app import app
from SweetAstro.src.backtest.metrics import (
    SingleEvaluationRecord, calculate_month_delta, compute_summary_metrics,
)


# ---------------------------------------------------------------------------
# Bug 21 — geocoder concurrency
# ---------------------------------------------------------------------------

def test_throttle_serializes_concurrent_calls(monkeypatch):
    from SweetAstro.src.core import geocode

    state = {"t": 1000.0}
    sleeps = []
    monkeypatch.setattr(geocode.time, "monotonic", lambda: state["t"])
    monkeypatch.setattr(geocode.time, "sleep", lambda s: (sleeps.append(s), state.__setitem__("t", state["t"] + s)))
    monkeypatch.setattr(geocode, "_last_call_ts", 0.0)

    barrier = threading.Barrier(8)
    timestamps = []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        geocode._throttle()
        with lock:
            timestamps.append(state["t"])

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    timestamps.sort()
    assert len(sleeps) == 7, "seven of eight calls must wait for the 1 req/s window"
    assert timestamps[-1] - timestamps[0] >= 7.0, "calls must be spaced by the throttle"


def test_concurrent_same_query_fetches_once(monkeypatch):
    import json as _json
    import time as _time

    from SweetAstro.src.core import geocode

    calls = []
    payload = [{"lat": "26.9124", "lon": "75.7873", "display_name": "Jaipur, India"}]

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps(payload).encode("utf-8")

    def fake_urlopen(req, timeout=None):
        calls.append(1)
        _time.sleep(0.05)  # hold the fetch lock long enough for contention
        return FakeResp()

    monkeypatch.setattr(geocode.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(geocode, "_throttle", lambda: None)
    geocode._cache.clear()

    barrier = threading.Barrier(6)
    results = []

    def worker():
        barrier.wait()
        results.append(geocode.search_places("Shared Query City"))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(calls) == 1, "identical concurrent queries must hit the network once"
    assert all(len(r) == 1 for r in results)


# ---------------------------------------------------------------------------
# Bug 22 — panchanga input validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("params", [
    {"date": "2026-09-12", "lon": 720.0},
    {"date": "2026-09-12", "lon": -181.0},
    {"date": "2026-09-12", "lat": 91.0},
    {"date": "2026-09-12", "lat": -91.0},
    {"date": "2026-09-12", "tz_offset": 20.0},
    {"date": "2026-09-12", "elevation": 99999.0},
])
def test_panchanga_rejects_invalid_input(params):
    client = TestClient(app)
    assert client.get("/api/panchanga", params=params).status_code == 400


def test_panchanga_accepts_valid_input():
    client = TestClient(app)
    response = client.get("/api/panchanga", params={"date": "2026-09-12"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Bug 23 — backtest/tournament error handling
# ---------------------------------------------------------------------------

def test_backtest_endpoint_missing_dataset(monkeypatch):
    from SweetAstro.src.api import app as app_module

    def boom(_path):
        raise FileNotFoundError("dataset missing")

    monkeypatch.setattr(app_module.ENGINE, "run_backtest", boom)
    client = TestClient(app_module.app)
    response = client.post("/api/backtest/run")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_tournament_endpoint_error_handling(monkeypatch):
    from SweetAstro.src.api import app as app_module

    def boom(_path):
        raise ValueError("bad dataset")

    monkeypatch.setattr(app_module.ENGINE, "run_tournament", boom)
    client = TestClient(app_module.app)
    response = client.post("/api/tournament/run")
    assert response.status_code == 400
    assert "tournament failed" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Bug 24 — metrics edge cases
# ---------------------------------------------------------------------------

def _record(**overrides) -> SingleEvaluationRecord:
    base = dict(
        prediction_id="SA-MAR-000001", chart_id="C1",
        predicted_year=2020, predicted_month=5, predicted_period_label="May 2020",
        actual_year=2020, actual_month=5, actual_date_str="2020-05-01",
        is_top_1_year=True, is_top_3_year=True, year_error=0, month_error=0.0,
        confidence_score=80.0, stability_score=90.0,
    )
    base.update(overrides)
    return SingleEvaluationRecord(**base)


def test_metrics_empty_dataset():
    metrics = compute_summary_metrics([])
    assert metrics.total_charts_tested == 0
    assert metrics.mean_absolute_error_months == 0.0
    assert metrics.confidence_interval_95 == (0.0, 0.0)


def test_metrics_single_record():
    metrics = compute_summary_metrics([_record()])
    assert metrics.top_1_year_accuracy == 100.0
    assert metrics.mean_absolute_error_months == 0.0
    assert metrics.confidence_interval_95 == (0.0, 0.0)
    assert metrics.high_confidence_top3_year_share == 100.0
    # Machinery-validation claim note ships with every summary
    assert "not an accuracy claim" in metrics.claim_note


def test_metrics_calibration_zero_without_high_confidence():
    metrics = compute_summary_metrics([_record(confidence_score=40.0)])
    assert metrics.high_confidence_top3_year_share == 0.0


def test_month_delta_wraps_years_correctly():
    assert calculate_month_delta(2020, 12, 2021, 1) == 1
    assert calculate_month_delta(2021, 1, 2020, 12) == 1
    assert calculate_month_delta(2020, 1, 2020, 12) == 11


# ---------------------------------------------------------------------------
# Bug 24b — rule-data depth
# ---------------------------------------------------------------------------

def test_muhurta_nakshatra_aliases_are_canonicalized():
    from SweetAstro.src.core.muhurta import canonical_nakshatra

    assert canonical_nakshatra("Dhanishtha") == "Dhanishta"
    assert canonical_nakshatra("Mrigashirsha") == "Mrigashira"
    assert canonical_nakshatra("Revati") == "Revati"
    assert canonical_nakshatra("Unknown Star") == "Unknown Star"


def test_muhurta_rules_data_integrity():
    from SweetAstro.src.core.constants import INDEX_TO_SIGN
    from SweetAstro.src.core.muhurta import NAKSHATRA_INDEX, load_muhurta_rules

    rules = load_muhurta_rules()
    valid_signs = set(INDEX_TO_SIGN.values())
    assert rules["events"], "at least one event must be defined"
    for key, cfg in rules["events"].items():
        assert cfg["label"], key
        assert cfg["source"], key
        assert cfg["avoid_tithis"] and all(1 <= t <= 30 for t in cfg["avoid_tithis"]), key
        for nak in cfg["recommended_nakshatras"]:
            assert nak in NAKSHATRA_INDEX, f"{key}: unknown nakshatra {nak}"
        for lagna in cfg.get("recommended_lagnas", []):
            assert lagna in valid_signs, f"{key}: unknown lagna {lagna}"
        assert isinstance(cfg.get("require_tarabala", False), bool), key
        assert isinstance(cfg.get("require_chandrabala", False), bool), key


def test_kat_topic_map_references_valid_triangles():
    from SweetAstro.src.remedies.kat import load_kat_rules

    rules = load_kat_rules()
    assert rules["topic_map"]
    for topic, entry in rules["topic_map"].items():
        assert entry["triangle"] in rules["triangles"], f"{topic}: unknown triangle"


def test_vastu_reference_directions_are_valid():
    from SweetAstro.src.core.vastu import load_vastu_rules

    rules = load_vastu_rules()
    directions = set(rules["directions"])
    for section in ("stairs", "main_door"):
        block = rules[section]
        for field in ("best", "acceptable", "avoid", "zone"):
            value = block.get(field)
            if isinstance(value, dict):
                for direction in value.get("best", []) + value.get("avoid", []):
                    assert direction in directions, f"{section}/{field}: {direction}"
            elif isinstance(value, list):
                for direction in value:
                    assert direction in directions, f"{section}/{field}: {direction}"
    for planet, direction in rules["planetary_directions"].items():
        if planet == "confidence":
            continue
        assert direction in directions, planet
