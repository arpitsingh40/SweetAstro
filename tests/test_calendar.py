"""
Dasha calendar (.ics) export tests — deterministic, no LLM.
"""

from fastapi.testclient import TestClient

from SweetAstro.src.api.app import app
from SweetAstro.src.core.calendar_export import build_calendar_ics

client = TestClient(app)

BIRTH = {
    "name": "Test Native", "dob": "1995-05-15", "tob": "14:30:00",
    "tz_offset": 5.5, "lat": 28.6139, "lon": 77.209, "place": "",
}


def test_ics_builder_folds_lines_and_escapes_values():
    ics = build_calendar_ics(calendar_name="Test; Calendar", events=[
        {
            "uid": "u1",
            "summary": "A very " + "long " * 30 + "summary, with commas; and semicolons",
            "start": "2026-10-02",
            "description": "Line1\nLine2",
        },
    ])
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    for line in ics.split("\r\n"):
        assert len(line.encode("utf-8")) <= 76, line
    assert "SUMMARY:A very" in ics
    assert "\\," in ics and "\\;" in ics
    assert "Line1\\nLine2" in ics
    assert "DTSTART;VALUE=DATE:20261002" in ics
    assert "DTEND;VALUE=DATE:20261003" in ics


def test_calendar_api_returns_ics_with_upcoming_boundaries():
    response = client.post("/api/calendar", json={**BIRTH, "horizon_months": 60})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = response.text
    assert body.count("BEGIN:VEVENT") >= 1
    assert body.count("BEGIN:VEVENT") == body.count("END:VEVENT")
    assert "SUMMARY:" in body
    assert "attachment" in response.headers.get("content-disposition", "")


def test_calendar_api_rejects_invalid_input():
    assert client.post("/api/calendar", json={"dob": "not-a-date"}).status_code == 400
