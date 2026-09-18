"""
Startup preflight checks for the SweetAstro server.

The server must never run "continuously but not working": every critical
dependency is verified before uvicorn starts, and failures abort startup
with an actionable message.

Checks:
  1. Python dependencies (fastapi/uvicorn/pydantic/httpx)
  2. Swiss Ephemeris engine (pyswisseph)          [critical]
  3. Ephemeris data files (.se1)                  [warning if absent]
  4. Chart engine self-test against a frozen SE reference [critical]
  5. DeepSeek API key configured                  [critical]
  6. DeepSeek API reachable + key valid           [critical]
  7. Listening port free (or already our server)  [critical]
  8. Geocoder reachable (optional)                [warning]

Bypass the network check with SWEETASTRO_SKIP_NET_CHECK=1.
"""

from __future__ import annotations

import importlib
import os
import socket
import threading
import time
from typing import Any, Dict, Tuple

import httpx

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

Level = str  # "ok" | "warn" | "fail" | "info"


def _deps_check() -> Tuple[Level, str]:
    missing = []
    for module in ("fastapi", "uvicorn", "pydantic", "httpx"):
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    if missing:
        return "fail", f"missing packages: {', '.join(missing)} — run: pip install -r requirements.txt"
    return "ok", "fastapi, uvicorn, pydantic, httpx present"


def _ephemeris_check() -> Tuple[Level, str]:
    from ..core import ephemeris

    if not ephemeris.HAS_SWISSEPH:
        return "fail", ("pyswisseph not installed — charts would be approximate. "
                        "Fix: pip install pyswisseph")
    return "ok", f"{ephemeris.ephemeris_data_source()}"


def _ephemeris_data_check() -> Tuple[Level, str]:
    from ..core.ephemeris import ephemeris_data_source

    if "se1" in ephemeris_data_source():
        return "ok", "official .se1 files in data/ephe/"
    return "warn", "official .se1 files not found — using Moshier model (still sub-arcsecond). Run: python fetch_ephemeris.py"


def _chart_selftest() -> Tuple[Level, str]:
    """Compute a reference chart and compare against Swiss Ephemeris values."""
    try:
        from ..core.chart import calculate_d1_chart

        chart = calculate_d1_chart(1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090)
        expected_asc = 151.6517   # [SE] frozen reference, see tests/test_calculation_backtest.py
        if abs(chart.ascendant_deg - expected_asc) > 0.01:
            return "fail", (f"ascendant {chart.ascendant_deg:.4f} != reference {expected_asc} — "
                            "chart engine is not trustworthy; aborting")
        if chart.planets["Moon"].nakshatra != "Anuradha":
            return "fail", "Moon nakshatra self-test failed"
        return "ok", f"reference chart OK (Asc {chart.ascendant_sign} {chart.ascendant_degree_in_sign:.2f}°)"
    except Exception as exc:  # pragma: no cover - defensive
        return "fail", f"chart self-test crashed: {exc}"


def _api_key_check() -> Tuple[Level, str]:
    if not DEEPSEEK_API_KEY:
        return "fail", "DEEPSEEK_API_KEY missing — add it to SweetAstro/.env"
    return "ok", f"key configured (…{DEEPSEEK_API_KEY[-4:]})"


def _deepseek_check() -> Tuple[Level, str]:
    if os.environ.get("SWEETASTRO_SKIP_NET_CHECK") == "1":
        return "warn", "skipped (SWEETASTRO_SKIP_NET_CHECK=1)"
    started = time.monotonic()

    # Hard deadline: DNS/handshake stalls on this platform can outlive the
    # httpx timeout, so the probe runs in a daemon thread and is abandoned
    # after 8s (the deploy loop must never hang on a network check).
    result: Dict[str, Any] = {}

    def _probe() -> None:
        try:
            result["response"] = httpx.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 8,
                    "thinking": {"type": "disabled"},
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            result["error"] = exc

    probe_thread = threading.Thread(target=_probe, daemon=True)
    probe_thread.start()
    probe_thread.join(timeout=8.0)
    if probe_thread.is_alive():
        return "fail", ("DeepSeek reachability probe exceeded 8s — chat may be slow. "
                        "Bypass with SWEETASTRO_SKIP_NET_CHECK=1 (or .\\dev.ps1 deploy -SkipNet).")
    if "error" in result:
        exc = result["error"]
        return "fail", (f"cannot reach {DEEPSEEK_BASE_URL} ({exc.__class__.__name__}) — "
                        "chat would hang. Check internet/DNS or set SWEETASTRO_SKIP_NET_CHECK=1 to bypass")
    resp = result["response"]
    elapsed = time.monotonic() - started
    if resp.status_code in (401, 403):
        return "fail", f"API key rejected (HTTP {resp.status_code}) — fix DEEPSEEK_API_KEY in .env"
    if resp.status_code >= 500:
        return "fail", f"DeepSeek server error HTTP {resp.status_code}"
    if resp.status_code >= 400:
        return "fail", f"DeepSeek request rejected HTTP {resp.status_code}: {resp.text[:160]}"
    return "ok", f"model '{DEEPSEEK_MODEL}' responded in {elapsed:.1f}s"


def _port_check(host: str, port: int) -> Tuple[Level, str]:
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host

    # Fast TCP probe first: only speak HTTP if something is actually listening
    # (a bound-but-not-listening port otherwise costs a full HTTP timeout).
    listening = False
    probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe_socket.settimeout(0.25)
    try:
        listening = probe_socket.connect_ex((probe_host, port)) == 0
    finally:
        probe_socket.close()

    if listening:
        try:
            resp = httpx.get(f"http://{probe_host}:{port}/api/health", timeout=2.0)
            if resp.status_code == 200 and "SweetAstro" in resp.text:
                return "info", f"SweetAstro already running on {probe_host}:{port}"
            return "fail", (f"{probe_host}:{port} is in use by another process — "
                            "stop it or change SWEETASTRO_PORT")
        except httpx.HTTPError:
            return "fail", (f"{probe_host}:{port} is in use by another process that is not SweetAstro — "
                            "stop it or change SWEETASTRO_PORT")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # NOTE: no SO_REUSEADDR — on Windows it would allow binding an in-use port
        sock.bind((probe_host, port))
        return "ok", f"{probe_host}:{port} free"
    except OSError as exc:
        return "fail", f"{probe_host}:{port} already in use ({exc}) — stop the other process or change SWEETASTRO_PORT"
    finally:
        sock.close()


def _geocoder_check() -> Tuple[Level, str]:
    if os.environ.get("SWEETASTRO_SKIP_NET_CHECK") == "1":
        return "warn", "skipped"
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": "London", "format": "jsonv2", "limit": "1"},
            headers={"User-Agent": "SweetAstro/1.0 (startup check)"},
            timeout=6.0,
        )
        if resp.status_code == 200:
            return "ok", "Nominatim reachable"
        return "warn", f"Nominatim HTTP {resp.status_code} — place search may fail"
    except httpx.HTTPError:
        return "warn", "Nominatim unreachable — users must enter coordinates manually"


CHECKS = [
    ("Python dependencies", _deps_check, True),
    ("Swiss Ephemeris engine", _ephemeris_check, True),
    ("Ephemeris data files", _ephemeris_data_check, False),
    ("Chart engine self-test", _chart_selftest, True),
    ("DeepSeek API key", _api_key_check, True),
    ("DeepSeek reachability", _deepseek_check, True),
    ("Listening port", None, True),   # handled specially (needs host/port)
    ("Geocoder (optional)", _geocoder_check, False),
]

_SYMBOL = {"ok": "PASS", "warn": "WARN", "fail": "FAIL", "info": "INFO"}


def run_preflight(host: str = "127.0.0.1", port: int = 8088, verbose: bool = True) -> Tuple[bool, bool]:
    """
    Runs all checks. Returns (ok_to_start, already_running).
    ok_to_start is False when any critical check fails.
    """
    ok = True
    already_running = False

    if verbose:
        print("SweetAstro preflight checks")
        print("-" * 66)

    for name, fn, critical in CHECKS:
        if name == "Listening port":
            level, detail = _port_check(host, port)
            if level == "info":
                already_running = True
        else:
            level, detail = fn()
        if level == "fail" and critical:
            ok = False
        if verbose:
            tag = _SYMBOL.get(level, level.upper())
            print(f"  [{tag}] {name}: {detail}")

    if verbose:
        print("-" * 66)
        if already_running:
            print("Result: SweetAstro is already running (no second instance started).")
        elif ok:
            print("Result: all critical checks passed.")
        else:
            print("Result: ABORTED — fix the FAIL items above, then start again.")

    if already_running:
        ok = False  # caller should exit without starting, but softly
    return ok, already_running
