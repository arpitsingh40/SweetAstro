"""Event timing engine tests: registry, gating, ranking, determinism, API."""

from datetime import datetime

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import PLANETS, VIMSHOTTARI_ORDER
from SweetAstro.src.interpretation.promise import PromiseAssessment
from SweetAstro.src.prediction.event_timing import (
    EVENT_CONFIGS, MIN_SCORE, find_timing_windows, render_timing_markdown,
)

BIRTH = datetime(1995, 5, 15, 14, 30)


def _chart():
    return calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def test_event_registry_is_valid():
    assert len(EVENT_CONFIGS) >= 6
    for key, config in EVENT_CONFIGS.items():
        assert config.key == key
        assert config.houses and all(1 <= h <= 12 for h in config.houses)
        assert all(k in PLANETS for k in config.karakas)
        assert all(p in PLANETS for p in config.transit_planets)


def test_weak_promise_gates_timing(monkeypatch):
    weak = PromiseAssessment(
        topic="career", level="Weak", score=-2.0, supportive_factors=[],
        limiting_factors=["H10 afflicted"], timing_reliable=False,
        statement="The chart shows a weak promise for career.",
    )
    monkeypatch.setattr("SweetAstro.src.prediction.event_timing.assess_promise",
                        lambda *a, **k: weak)
    result = find_timing_windows(_chart(), BIRTH, "career_change",
                                 datetime(2026, 1, 1), datetime(2028, 1, 1))
    assert result.gated is True
    assert result.windows == []
    assert any("withheld" in n.lower() for n in result.method_notes)


def test_windows_are_ranked_and_in_range():
    result = find_timing_windows(_chart(), BIRTH, "marriage",
                                 datetime(2026, 1, 1), datetime(2028, 1, 1))
    assert result.gated is False
    assert result.windows, "expected at least one window in a 2-year range"
    previous_start = ""
    for w in result.windows:
        assert w.score >= MIN_SCORE
        assert w.tier in ("High", "Medium", "Low")
        assert w.mahadasha in VIMSHOTTARI_ORDER
        assert w.antardasha in VIMSHOTTARI_ORDER
        assert w.pratyantardasha in VIMSHOTTARI_ORDER
        assert w.start_date <= w.end_date
        assert previous_start <= w.start_date  # sorted chronologically
        # windows may overlap the range boundary but must intersect it
        assert datetime.strptime(w.end_date, "%Y-%m-%d") >= datetime(2026, 1, 1)
        assert datetime.strptime(w.start_date, "%Y-%m-%d") <= datetime(2028, 1, 1)
        previous_start = w.start_date


def test_timing_is_deterministic():
    first = find_timing_windows(_chart(), BIRTH, "career_change",
                                datetime(2026, 1, 1), datetime(2028, 1, 1))
    second = find_timing_windows(_chart(), BIRTH, "career_change",
                                 datetime(2026, 1, 1), datetime(2028, 1, 1))
    assert [(w.start_date, w.score) for w in first.windows] == \
           [(w.start_date, w.score) for w in second.windows]


def test_markdown_report_structure():
    result = find_timing_windows(_chart(), BIRTH, "marriage",
                                 datetime(2026, 1, 1), datetime(2028, 1, 1))
    markdown = render_timing_markdown(result)
    assert "# Event timing" in markdown
    assert "Promise" in markdown
    assert "no guarantee" in markdown.lower()


def test_timing_api_endpoint():
    from fastapi.testclient import TestClient
    from SweetAstro.src.api.app import app

    client = TestClient(app)
    payload = {
        "person": {"name": "Native", "dob": "1995-05-15", "tob": "14:30:00",
                   "tz_offset": 5.5, "lat": 26.9124, "lon": 75.7873},
        "event": "marriage",
        "range_start": "2026-01-01",
        "range_end": "2028-01-01",
    }
    response = client.post("/api/timing", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["event"] == "marriage"
    assert "markdown" in body
    bad = dict(payload, event="unknown_event")
    assert client.post("/api/timing", json=bad).status_code == 400


# ---------------------------------------------------------------------------
# F1 resolution fix + birth-time sensitivity disclosure
# ---------------------------------------------------------------------------

def test_method_notes_disclose_window_width_and_time_sensitivity():
    result = find_timing_windows(_chart(), BIRTH, "marriage",
                                 datetime(2026, 1, 1), datetime(2028, 1, 1))
    joined = " ".join(result.method_notes)
    assert "Pratyantardasha span" in joined
    assert "birth-time sensitivity" in joined.lower()
    assert "candidate spans, not precise dates" in joined
    assert any("day(s)" in note for note in result.method_notes), "measured shift missing"


def test_transit_segments_detect_and_bisect_sign_change():
    from datetime import timedelta

    from SweetAstro.src.prediction.event_timing import _signs_in_window, _transit_segments

    start, end = datetime(2025, 1, 1), datetime(2028, 1, 1)
    segments = _transit_segments(["Jupiter"], start, end)
    segs = segments["Jupiter"]
    assert len(segs) >= 2, "Jupiter must change sign inside a 3-year range"
    assert all(start <= seg_start <= end for seg_start, _ in segs)

    change_time = segs[1][0]
    window_signs = _signs_in_window(
        segments, "Jupiter", change_time - timedelta(days=1), change_time + timedelta(days=1))
    assert segs[0][1] in window_signs
    assert segs[1][1] in window_signs

    # A window entirely before the ingress reports only the earlier sign
    before = _signs_in_window(
        segments, "Jupiter", start, change_time - timedelta(days=2))
    assert before == [segs[0][1]]


def test_windows_cite_bav_filtered_transit_evidence():
    result = find_timing_windows(_chart(), BIRTH, "marriage",
                                 datetime(2026, 1, 1), datetime(2028, 1, 1))
    assert result.windows
    evidence = " ".join(item for w in result.windows for item in w.supported_by)
    assert "/8 bindus" in evidence, "transit evidence must carry BAV bindus"
