"""Kundli Milan (Ashtakoota) engine tests."""

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.matching import (
    MAX_TOTAL, _bhakoot, _nadi, _varna, _yoni, mangal_dosha, match_charts,
    render_match_markdown,
)


def _chart_a():
    return calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart_b():
    return calculate_d1_chart(1992, 11, 3, 9, 15, 0, 5.5, 19.0760, 72.8777)


def test_kuta_bounds_and_structure():
    result = match_charts(_chart_a(), _chart_b())
    assert len(result.kutas) == 8
    assert [k.kuta for k in result.kutas] == [
        "Varna", "Vashya", "Tara", "Yoni", "Graha Maitri", "Gana", "Bhakoot", "Nadi"]
    for k in result.kutas:
        assert 0.0 <= k.points <= k.max_points
    assert 0.0 <= result.total <= MAX_TOTAL
    assert abs(sum(k.points for k in result.kutas) - result.total) < 0.01
    assert result.verdict
    assert result.notes


def test_nadi_same_is_dosha_different_is_full():
    assert _nadi(0, 0).points == 0.0
    assert _nadi(0, 1).points == 8.0


def test_bhakoot_dosha_axes():
    assert _bhakoot(1, 6).points == 0.0   # 6th distance
    assert _bhakoot(1, 2).points == 0.0   # 2nd distance
    assert _bhakoot(1, 9).points == 0.0   # 9th distance
    assert _bhakoot(1, 7).points == 7.0   # 7th distance


def test_yoni_enemy_pair_scores_zero_same_scores_four():
    assert _yoni(0, 12).points == 0.0     # Ashwini (Horse) vs Hasta (Buffalo)
    assert _yoni(0, 23).points == 4.0     # Ashwini vs Shatabhisha (both Horse)


def test_varna_is_directional():
    assert _varna(4, 3).points == 0.0     # bride Brahmin (Cancer), groom Shudra (Gemini)
    assert _varna(3, 4).points == 1.0     # bride Shudra, groom Brahmin


def test_identical_chart_scores_with_known_zeros():
    result = match_charts(_chart_a(), _chart_a())
    by_name = {k.kuta: k.points for k in result.kutas}
    assert by_name["Tara"] == 0.0   # Janma tara both ways
    assert by_name["Nadi"] == 0.0   # same nadi
    assert by_name["Yoni"] == 4.0   # same yoni
    assert by_name["Gana"] == 6.0   # same gana


def test_mangal_dosha_structure():
    reading = mangal_dosha(_chart_a())
    assert isinstance(reading.active, bool)
    assert set(reading.houses) == {"from_lagna", "from_moon"}
    assert all(1 <= h <= 12 for h in reading.houses.values())
    assert reading.note


def test_markdown_report_contains_score_and_disclaimer():
    markdown = render_match_markdown(match_charts(_chart_a(), _chart_b()),
                                     "Bride", "Groom")
    assert "Ashtakoota total" in markdown
    assert "Kuta breakdown" in markdown
    assert "Mangal dosha" in markdown
    assert "not a guarantee" in markdown.lower()


def test_matching_api_endpoint():
    from fastapi.testclient import TestClient
    from SweetAstro.src.api.app import app

    client = TestClient(app)
    payload = {
        "person_a": {"name": "Bride", "dob": "1995-05-15", "tob": "14:30:00",
                     "tz_offset": 5.5, "lat": 26.9124, "lon": 75.7873},
        "person_b": {"name": "Groom", "dob": "1992-11-03", "tob": "09:15:00",
                     "tz_offset": 5.5, "lat": 19.0760, "lon": 72.8777},
    }
    response = client.post("/api/matching", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["result"]["total"] <= 36.0
    assert len(body["result"]["kutas"]) == 8
    assert "Ashtakoota total" in body["markdown"]

    bad = {"person_a": dict(payload["person_a"], dob="not-a-date"), "person_b": payload["person_b"]}
    assert client.post("/api/matching", json=bad).status_code == 400


def test_match_page_served():
    from fastapi.testclient import TestClient
    from SweetAstro.src.api.app import app

    client = TestClient(app)
    page = client.get("/match")
    assert page.status_code == 200
    assert "Kundli Milan" in page.text
    assert "/api/matching" in page.text
    assert "Ashtakoota" in page.text
