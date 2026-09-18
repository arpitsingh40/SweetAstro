"""
Regression tests for audit round 5 (2026-09-12):

25. Google geocoder: no caching, no concurrency guard, and API-level failures
    (REQUEST_DENIED etc.) were silently reported as "No coordinates found".
26. DeepSeek client retried non-retryable errors (401/400) and silently
    returned empty content when a response hit the token limit.
27. Extractor accepted impossible dates (future birth dates, absurd ranges).
28. Money breakdown: behavior locked with tests (audited clean).
"""

import json
from datetime import datetime

import httpx
import pytest

from SweetAstro.src.chat.client import DeepSeekClient, DeepSeekError, DeepSeekHTTPError
from SweetAstro.src.core import geocode
from SweetAstro.src.core.geocode import GeocodeError, search_places
from SweetAstro.src.core.chart import calculate_d1_chart


# ---------------------------------------------------------------------------
# Bug 25 — Google geocoding path
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(geocode, "_throttle", lambda: None)
    geocode._cache.clear()
    yield
    geocode._cache.clear()


def _google_response(payload):
    def handler(request: httpx.Request) -> httpx.Response:  # not used; urlopen is mocked below
        return httpx.Response(200, json=payload)
    return handler


def _fake_urlopen(payload, calls):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    def _fake(req, timeout=None):
        calls.append(req.full_url)
        return FakeResp()

    return _fake


def test_google_zero_results_returns_empty(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(geocode.urllib.request, "urlopen",
                        _fake_urlopen({"status": "ZERO_RESULTS", "results": []}, calls))
    assert search_places("Nowhere", provider="google") == []
    assert len(calls) == 1


def test_google_request_denied_raises_with_message(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(geocode.urllib.request, "urlopen",
                        _fake_urlopen({"status": "REQUEST_DENIED",
                                       "error_message": "API key restricted"}, calls))
    with pytest.raises(GeocodeError, match="REQUEST_DENIED"):
        search_places("Jaipur", provider="google")


def test_google_success_is_cached_and_parsed(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    calls = []
    payload = {"status": "OK", "results": [
        {"geometry": {"location": {"lat": 26.91, "lng": 75.79}},
         "formatted_address": "Jaipur, Rajasthan, India"}]}
    monkeypatch.setattr(geocode.urllib.request, "urlopen", _fake_urlopen(payload, calls))

    first = search_places("Jaipur", provider="google")
    second = search_places("Jaipur", provider="google")
    assert len(calls) == 1, "the Google path must cache like the Nominatim path"
    assert first[0].lat == pytest.approx(26.91)
    assert first[0].source == "google"
    assert [r.display_name for r in second] == ["Jaipur, Rajasthan, India"]


# ---------------------------------------------------------------------------
# Bug 26 — DeepSeek client retry semantics
# ---------------------------------------------------------------------------

def _client_with_handler(handler, monkeypatch):
    monkeypatch.setattr("SweetAstro.src.chat.client.time.sleep", lambda _s: None)
    return DeepSeekClient(api_key="test-key", transport=httpx.MockTransport(handler))


def test_client_retries_server_errors(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]})

    client = _client_with_handler(handler, monkeypatch)
    assert client.complete([{"role": "user", "content": "x"}], retries=1) == "OK"
    assert calls["n"] == 2


def test_client_does_not_retry_auth_errors(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    client = _client_with_handler(handler, monkeypatch)
    with pytest.raises(DeepSeekHTTPError) as excinfo:
        client.complete([{"role": "user", "content": "x"}], retries=2)
    assert excinfo.value.status_code == 401
    assert calls["n"] == 1, "4xx errors must fail fast without retries"


def test_client_retries_network_errors(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]})

    client = _client_with_handler(handler, monkeypatch)
    assert client.complete([{"role": "user", "content": "x"}], retries=1) == "OK"
    assert calls["n"] == 2


def test_client_reports_truncated_response(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "", "reasoning_content": "..."}, "finish_reason": "length"}]
        })

    client = _client_with_handler(handler, monkeypatch)
    with pytest.raises(DeepSeekError, match="truncated"):
        client.complete([{"role": "user", "content": "x"}], retries=1)
    assert calls["n"] == 1, "truncation is not retryable"


# ---------------------------------------------------------------------------
# Bug 27 — extractor date sanity
# ---------------------------------------------------------------------------

def test_extractor_rejects_future_and_ancient_birth_dates():
    from SweetAstro.src.chat.extractor import clean_extraction

    future = f"{datetime.now().year + 5}-01-01"
    assert "dob" not in clean_extraction({"dob": future})
    assert "dob" not in clean_extraction({"dob": "1700-01-01"})
    assert clean_extraction({"dob": "1995-05-15"})["dob"] == "1995-05-15"


def test_extractor_rejects_absurd_muhurta_ranges():
    from SweetAstro.src.chat.extractor import clean_extraction

    cleaned = clean_extraction({"muhurta_start": "1800-01-01", "muhurta_end": "2999-01-01"})
    assert "muhurta_start" not in cleaned
    assert "muhurta_end" not in cleaned
    ok = clean_extraction({"muhurta_start": "2026-09-01", "muhurta_end": "2026-12-31"})
    assert ok["muhurta_start"] == "2026-09-01"
    assert ok["muhurta_end"] == "2026-12-31"


# ---------------------------------------------------------------------------
# Bug 28 — money breakdown locks
# ---------------------------------------------------------------------------

def test_money_breakdown_covers_all_wealth_houses():
    from SweetAstro.src.interpretation.money import analyse_money

    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)
    breakdown = analyse_money(d1)
    assert set(breakdown.per_house) == {2, 5, 6, 8, 10, 11, 12}
    for house, note in breakdown.per_house.items():
        assert "lord" in note and "sign" in note, house
    assert "discipline" in breakdown.discipline_first_note.lower()
    assert breakdown.business_note == ""

    business = analyse_money(d1, for_business=True)
    assert "3H" in business.business_note and "7H" in business.business_note
