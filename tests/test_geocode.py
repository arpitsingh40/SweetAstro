"""
Tests for open-source birth-place geocoding (no network: urlopen is mocked).
"""

import io
import json
import pytest

from SweetAstro.src.core import geocode
from SweetAstro.src.core.geocode import (
    GeocodeError, GeocodeResult, geocode_place, resolve_coordinates, search_places,
)


FAKE_NOMINATIM = [
    {"lat": "26.9124", "lon": "75.7873", "display_name": "Jaipur, Rajasthan, India"},
    {"lat": "26.9000", "lon": "75.8000", "display_name": "Jaipur District, Rajasthan, India"},
]


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    monkeypatch.setattr(geocode, "_throttle", lambda: None)
    geocode._cache.clear()


def _fake_urlopen_factory(payload):
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(payload).encode("utf-8")
    def _fake(req, timeout=None):
        return FakeResp()
    return _fake


def test_search_places_parses_nominatim(monkeypatch):
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _fake_urlopen_factory(FAKE_NOMINATIM))
    hits = search_places("Jaipur, Rajasthan, India", limit=5)
    assert len(hits) == 2
    assert hits[0].lat == pytest.approx(26.9124)
    assert hits[0].lon == pytest.approx(75.7873)
    assert "Jaipur" in hits[0].display_name
    assert hits[0].source == "nominatim"


def test_search_places_empty_query_raises():
    with pytest.raises(GeocodeError):
        search_places("   ")


def test_geocode_place_no_match_raises(monkeypatch):
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _fake_urlopen_factory([]))
    with pytest.raises(GeocodeError, match="No coordinates found"):
        geocode_place("Nowhere XYZ 123")


def test_geocode_place_network_failure_raises(monkeypatch):
    def _boom(req, timeout=None):
        raise OSError("offline")
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _boom)
    with pytest.raises(GeocodeError, match="Geocoder request failed"):
        geocode_place("Jaipur")


def test_resolve_empty_place_uses_manual():
    lat, lon, note = resolve_coordinates("", 19.0760, 72.8777)
    assert (lat, lon) == (19.0760, 72.8777)
    assert "Manual" in note


def test_resolve_place_wins_over_manual(monkeypatch):
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _fake_urlopen_factory(FAKE_NOMINATIM))
    lat, lon, note = resolve_coordinates("Jaipur", 19.0760, 72.8777)
    assert lat == pytest.approx(26.9124)
    assert "Geocoded" in note


def test_resolve_place_failure_falls_back_to_explicit_coords(monkeypatch):
    def _boom(req, timeout=None):
        raise OSError("offline")
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _boom)
    lat, lon, note = resolve_coordinates("Jaipur", 19.0760, 72.8777)
    assert (lat, lon) == (19.0760, 72.8777)
    assert "failed" in note.lower()


def test_resolve_place_failure_with_defaults_raises(monkeypatch):
    def _boom(req, timeout=None):
        raise OSError("offline")
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _boom)
    with pytest.raises(GeocodeError):
        resolve_coordinates("Jaipur", 28.6139, 77.2090)


def test_google_without_key_raises():
    with pytest.raises(GeocodeError, match="GOOGLE_MAPS_API_KEY"):
        search_places("Jaipur", provider="google")


def test_service_answer_with_place_mocked(monkeypatch):
    from pathlib import Path
    from SweetAstro.src.service import SweetAstroEngine
    monkeypatch.setattr(
        "SweetAstro.src.service.resolve_coordinates",
        lambda place, lat, lon, provider="nominatim": (26.9124, 75.7873, "Geocoded (mock)."),
    )
    engine = SweetAstroEngine(rules_dir=Path(__file__).parent.parent / "data" / "rules")
    res = engine.answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        place="Jaipur, Rajasthan, India", question="career",
    )
    assert res.answer.confidence in ("Low", "Medium", "High")


def test_api_geocode_endpoint_mocked(monkeypatch):
    from fastapi.testclient import TestClient
    from SweetAstro.src.api import app as app_module
    monkeypatch.setattr(
        app_module, "search_places",
        lambda q, limit=5, provider="nominatim": [
            GeocodeResult(lat=26.9124, lon=75.7873,
                          display_name="Jaipur, Rajasthan, India", source="nominatim")
        ],
    )
    client = TestClient(app_module.app)
    r = client.get("/api/geocode", params={"q": "Jaipur"})
    assert r.status_code == 200
    data = r.json()
    assert data[0]["lat"] == pytest.approx(26.9124)
    assert data[0]["source"] == "nominatim"


def test_api_answer_uses_geocoded_coords(monkeypatch):
    from fastapi.testclient import TestClient
    from SweetAstro.src.api import app as app_module
    monkeypatch.setattr(
        app_module, "resolve_coordinates",
        lambda place, lat, lon, provider="nominatim": (26.9124, 75.7873, "Geocoded (mock)."),
    )
    client = TestClient(app_module.app)
    r = client.post("/api/answer", json={"dob": "1995-05-15", "tob": "14:30:00",
                                         "place": "Jaipur, Rajasthan, India",
                                         "question": "career"})
    assert r.status_code == 200
    body = r.json()
    assert body["resolved_location"]["lat"] == pytest.approx(26.9124)
    assert "Geocoded" in body["resolved_location"]["note"]
