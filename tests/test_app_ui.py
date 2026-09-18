"""
Web app (Phase 0/1) contract tests: /app SPA shell and /api/chart snapshot.

The React app is built into src/api/static/app by `npm --prefix frontend run build`
(or `.\dev.ps1 ui-build`). Tests accept either state: built (200 + #root) or not
built (503 + build hint), so a fresh checkout stays green either way.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from SweetAstro.src.api.app import app
from SweetAstro.src.core.constants import VIMSHOTTARI_ORDER

client = TestClient(app)

APP_INDEX = Path(__file__).parent.parent / "src" / "api" / "static" / "app" / "index.html"


def test_app_spa_shell_and_deep_links():
    response = client.get("/app")
    deep = client.get("/app/chart")
    if APP_INDEX.exists():
        assert response.status_code == 200
        assert 'id="root"' in response.text
        # client-side routing: deep links must serve the same shell
        assert deep.status_code == 200
        assert 'id="root"' in deep.text
        assert "/static/app/assets/" in response.text
    else:
        assert response.status_code == 503
        assert "not built" in response.text.lower()


def test_app_does_not_leak_legacy_dashboard_copy():
    html = client.get("/app").text
    assert "You will get married in" not in html
    assert "Direct Prediction Mode" not in html


def test_app_routes_serve_spa_shell_for_new_pages():
    if not APP_INDEX.exists():
        pytest.skip("web app not built")
    for route in ("/app/chat", "/app/muhurta", "/app/timeline", "/app/today", "/app/match"):
        response = client.get(route)
        assert response.status_code == 200, route
        assert 'id="root"' in response.text, route


def test_pwa_assets_are_served():
    if not APP_INDEX.exists():
        pytest.skip("web app not built")

    manifest = client.get("/static/app/manifest.webmanifest")
    assert manifest.status_code == 200
    assert "SweetAstro" in manifest.text
    assert "/app/" in manifest.text

    icon = client.get("/static/app/icon.svg")
    assert icon.status_code == 200 and "<svg" in icon.text

    sw = client.get("/app/sw.js")
    assert sw.status_code == 200
    assert sw.headers.get("service-worker-allowed") == "/"
    assert "addEventListener" in sw.text


def test_chart_api_returns_verified_snapshot():
    response = client.post("/api/chart", json={
        "name": "Test Native",
        "dob": "1995-05-15",
        "tob": "14:30:00",
        "place": "",
        "tz_offset": 5.5,
        "lat": 28.6139,
        "lon": 77.2090,
    })
    assert response.status_code == 200
    body = response.json()

    chart = body["chart"]
    assert chart["ascendant_sign"] == "Virgo"
    assert 0.0 <= chart["ascendant_degree"] < 30.0
    assert len(chart["planets"]) == 9
    assert len(chart["houses"]) == 12
    for planet in chart["planets"]:
        assert 1 <= planet["house"] <= 12
        assert 0.0 <= planet["degree"] < 30.0
        assert planet["nakshatra"]
    for house in chart["houses"]:
        assert house["lord"] and house["sign"]

    assert body["dasha"]["mahadasha"] in VIMSHOTTARI_ORDER
    assert body["dasha"]["antardasha"] in VIMSHOTTARI_ORDER
    assert body["panchanga"]["nakshatra"]
    assert "swisseph" in body["calculation"].lower() or "builtin" in body["calculation"].lower()


def test_chart_api_matches_engine_determinism():
    payload = {
        "dob": "1995-05-15", "tob": "14:30:00", "tz_offset": 5.5,
        "lat": 28.6139, "lon": 77.2090,
    }
    first = client.post("/api/chart", json=payload).json()
    second = client.post("/api/chart", json=payload).json()
    assert first["chart"] == second["chart"]
    assert first["dasha"] == second["dasha"]


def test_chart_api_includes_ordered_upcoming_periods():
    body = client.post("/api/chart", json={
        "dob": "1995-05-15", "tob": "14:30:00", "tz_offset": 5.5,
        "lat": 28.6139, "lon": 77.2090,
    }).json()
    upcoming = body["upcoming"]
    assert upcoming, "expected upcoming MD/AD periods"
    assert all(p["level"] in ("MD", "AD") for p in upcoming)
    assert all(p["lord"] and p["start"] and p["end"] for p in upcoming)
    assert [p["start"] for p in upcoming] == sorted(p["start"] for p in upcoming)


def test_chart_api_includes_life_timeline_and_current_antardashas():
    body = client.post("/api/chart", json={
        "dob": "1995-05-15", "tob": "14:30:00", "tz_offset": 5.5,
        "lat": 28.6139, "lon": 77.2090,
    }).json()

    timeline = body["timeline"]
    assert len(timeline) == 9, "Vimshottari has 9 mahadashas"
    assert all(p["level"] == "MD" for p in timeline)
    assert sum(1 for p in timeline if p["current"]) == 1
    assert timeline[0]["start"] < timeline[-1]["end"]
    assert all(p["end"] > p["start"] for p in timeline)

    ads = body["current_ads"]
    assert len(ads) == 9, "each mahadasha has 9 antardashas"
    assert all(p["level"] == "AD" for p in ads)
    assert sum(1 for p in ads if p["current"]) == 1
    assert all(p["start"] < p["end"] for p in ads)


def test_chart_api_rejects_invalid_input():
    assert client.post("/api/chart", json={"dob": "not-a-date"}).status_code == 400
    assert client.post(
        "/api/chart",
        json={"dob": "1995-05-15", "tob": "14:30:00", "tz_offset": 99.0},
    ).status_code == 400


def test_chart_api_flags_uncertain_birth_time():
    uncertain = client.post("/api/chart", json={
        "dob": "1995-05-15", "tob": "12:00:00", "tz_offset": 5.5,
        "lat": 28.6139, "lon": 77.2090, "time_reliable": False,
    }).json()
    assert uncertain["birth_time_reliable"] is False
    assert "reduced confidence" in uncertain["calculation"].lower()

    reliable = client.post("/api/chart", json={
        "dob": "1995-05-15", "tob": "14:30:00", "tz_offset": 5.5,
        "lat": 28.6139, "lon": 77.2090,
    }).json()
    assert reliable["birth_time_reliable"] is True
    assert "reduced confidence" not in reliable["calculation"].lower()
