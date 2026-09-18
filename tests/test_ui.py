"""UI contract tests: accessibility, resilience, and calibrated dashboard copy."""

from fastapi.testclient import TestClient

from SweetAstro.src.api.app import app

client = TestClient(app)


def test_chat_page_has_accessibility_hooks():
    html = client.get("/").text
    assert 'role="log"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-label="Send message"' in html
    assert 'aria-label="Stop generating"' in html
    assert "prefers-reduced-motion" in html
    assert 'id="sr-status"' in html
    assert 'role="alert"' in html


def test_chat_page_is_cdn_resilient_and_neutral_brand():
    html = client.get("/").text
    assert "/static/vendor/marked.min.js" in html
    assert "/static/vendor/purify.min.js" in html
    assert "cdnjs.cloudflare.com/ajax/libs/marked" not in html
    assert "no-cdn" in html
    assert "🪐" in html
    assert "💍" not in html


def test_vendor_assets_are_served():
    marked = client.get("/static/vendor/marked.min.js")
    purify = client.get("/static/vendor/purify.min.js")
    assert marked.status_code == 200 and len(marked.text) > 5000
    assert purify.status_code == 200 and len(purify.text) > 5000
    assert "javascript" in marked.headers.get("content-type", "")


def test_chat_page_has_answer_navigation_and_history_restore():
    html = client.get("/").text
    assert "enhanceAnswer" in html
    assert "answer-toc" in html
    assert "Copy answer" in html
    assert "restoreHistory" in html
    assert "renderTimer" in html                 # throttled streaming render
    assert "session-expired-note" in html        # expired session notice


def test_chat_page_covers_all_engine_modes_and_calibration_loop():
    html = client.get("/").text
    for marker in ("Muhurta / auspicious date", "Panchang today", "Vastu check",
                   "My chart basics",
                   "history-btn", "history-panel", "loadSessions", "openSession",
                   "addConfirmActions", "confirm-actions",
                   "Did this happen?", "Outcome update",
                   "lang-select", "selectedLanguage",
                   "card-edit-btn", "extractPeriod",
                   'href="/match"',
                   "Verified muhurta basis", "Vastu assessment basis",
                   "Verified panchanga basis"):
        assert marker in html, f"missing UI feature marker: {marker}"


def test_dashboard_uses_calibrated_language():
    html = client.get("/dashboard").text
    assert "Calibrated Window" in html
    assert "You will get married in May 2024" not in html
    assert "Direct Prediction Mode" not in html


def test_pages_are_mobile_responsive():
    for path in ("/", "/match", "/dashboard"):
        html = client.get(path).text
        assert "width=device-width" in html, path
        assert "-webkit-text-size-adjust" in html, path
        assert "@media (max-width: 640px)" in html, path

    chat = client.get("/").text
    assert "flex-wrap" in chat
    assert "table-wrap" in chat                          # answer tables scroll on small screens
    assert "wrapTables" in chat
    assert "max-w-[calc(100vw-2rem)]" in chat            # history dropdown fits phones
    assert "env(safe-area-inset-bottom)" in chat         # notched-device footer

    match = client.get("/match").text
    assert "flex-wrap" in match
    assert "hidden sm:block" in match
