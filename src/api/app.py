"""
SweetAstro FastAPI Application.
Hosts the web dashboard and REST API for testing Marriage Predictions,
Blind Backtesting Lab, Method Tournaments, and Rule Catalogs.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..service import SweetAstroEngine
from ..core.chart import calculate_d1_chart
from ..core.calendar_export import build_calendar_ics
from ..core.constants import SIGNS, PLANETS
from ..core.dasha import (
    calculate_vimshottari_timeline, get_dasha_at_date, upcoming_periods,
)
from ..core.geocode import GeocodeError, resolve_coordinates, search_places
from ..core.ephemeris import ephemeris_engine_name, ephemeris_data_source
from ..core.matching import match_charts, render_match_markdown
from ..core.nakshatra import compute_natal_panchanga
from ..core.panchanga import compute_panchanga, PanchangaError
from ..prediction.event_timing import (
    EVENT_CONFIGS, find_timing_windows, render_timing_markdown,
)
from ..prediction.rectify import rectify_birth_time
from ..chat.config import API_TOKEN, DEEPSEEK_MODEL, has_api_key
from ..chat.notifications import NotificationStore
from .chat_routes import router as chat_router

app = FastAPI(
    title="SweetAstro Chat — Consumer Astrology Answer Engine",
    description="Chat-based Vedic Jyotish answer engine powered by the deterministic SweetAstro core + DeepSeek",
    version="2.0.0"
)

# Paths that never require the optional API token (UI boot + health checks).
EXEMPT_API_PATHS = {"/api/health", "/api/chat/config"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Optional API-token gate. Active only when SWEETASTRO_API_TOKEN is set."""
    token = API_TOKEN
    path = request.url.path
    if token and path.startswith("/api") and path not in EXEMPT_API_PATHS:
        supplied = request.headers.get("x-auth-token", "").strip()
        if not supplied:
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                supplied = authorization[7:].strip()
        if supplied != token:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API token."})
    return await call_next(request)


app.include_router(chat_router)

# Static assets (self-hosted vendor JS + UI files). Not gated by the API token.
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Initialize engine
ENGINE = SweetAstroEngine()

# In-memory push subscriptions (substance-only notifications; delivery needs VAPID keys)
NOTIFICATIONS = NotificationStore()


class PredictionRequest(BaseModel):
    name: str = "Candidate"
    dob: str = "1995-05-15"       # YYYY-MM-DD
    tob: str = "14:30:00"         # HH:MM:SS
    tz_offset: float = 5.5
    lat: float = 28.6139
    lon: float = 77.2090
    place: str = ""               # free-text birth place; geocoded, wins over lat/lon
    geocode_provider: str = "nominatim"  # or "google" (needs GOOGLE_MAPS_API_KEY)
    search_start_age: Optional[int] = 20
    search_end_age: Optional[int] = 38


class PersonInput(BaseModel):
    """One person's birth data for compatibility matching."""
    name: str = "Person"
    dob: str = "1995-05-15"
    tob: str = "12:00:00"
    place: str = ""
    geocode_provider: str = "nominatim"
    tz_offset: float = 5.5
    lat: float = 28.6139
    lon: float = 77.2090


class MatchingRequest(BaseModel):
    person_a: PersonInput
    person_b: PersonInput


class RectifyRequest(BaseModel):
    """Candidate birth-time ranking from dated life events (deterministic assist)."""
    name: str = "Native"
    dob: str = "1995-05-15"
    tz_offset: float = 5.5
    place: str = ""
    geocode_provider: str = "nominatim"
    lat: float = 28.6139
    lon: float = 77.2090
    topic: str = "general"
    events: List[Dict[str, Any]] = Field(default_factory=list)


class TimingRequest(BaseModel):
    person: PersonInput
    event: str
    range_start: Optional[str] = None
    range_end: Optional[str] = None


class ConsumerAnswerRequest(BaseModel):
    """Consumer Answer Engine request (Sec 1): never guess positions."""
    name: str = "Native"
    dob: str = "1995-05-15"       # YYYY-MM-DD
    tob: str = "14:30:00"         # HH:MM:SS
    place: str = ""               # free-text birth place; geocoded, wins over lat/lon
    geocode_provider: str = "nominatim"  # or "google" (needs GOOGLE_MAPS_API_KEY)
    tz_offset: float = 5.5
    lat: float = 28.6139
    lon: float = 77.2090
    question: str = "general"
    time_reliable: bool = True    # False when birth time uncertain -> reduced confidence
    historical_events: Optional[List[Dict[str, Any]]] = None  # backtesting mode (Sec 14)


class ChartRequest(BaseModel):
    """Stateless chart snapshot for the web app (no session, no LLM)."""
    name: str = "Native"
    dob: str = "1995-05-15"       # YYYY-MM-DD
    tob: str = "12:00:00"         # HH:MM:SS (noon when the time is unknown)
    place: str = ""
    geocode_provider: str = "nominatim"
    tz_offset: float = 5.5
    lat: float = 28.6139
    lon: float = 77.2090
    time_reliable: bool = True    # False when the birth time is unknown (noon placeholder)


class CalendarRequest(ChartRequest):
    """Dasha-boundary calendar export range."""
    horizon_months: int = 12


class PushSubscribeRequest(BaseModel):
    """Browser push subscription (Web Push endpoint + keys)."""
    endpoint: str
    keys: Dict[str, str] = Field(default_factory=dict)
    profile: str = ""


@app.get("/api/geocode")
def geocode_search_api(q: str, limit: int = 5, provider: str = "nominatim"):
    """
    Birth-place search: type an address/city, get exact coordinates.
    Open-source Nominatim by default (no key); provider="google" uses the
    Google Geocoding API when GOOGLE_MAPS_API_KEY is configured.
    """
    try:
        return [r.to_dict() for r in search_places(q, limit=limit, provider=provider)]
    except GeocodeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/panchanga")
def panchanga_api(date: str, lat: float = 28.635556, lon: float = 77.224444,
                  tz_offset: float = 5.5, elevation: float = 212.0):
    """
    Deterministic panchanga (drik ganita) for a civil date and location:
    sunrise/sunset, tithi, vara, nakshatra, yoga, karana, Rahu/Yamaganda/Gulika
    and Abhijit windows. Verified against DrikPanchang reference data.
    """
    if not -90.0 <= lat <= 90.0:
        raise HTTPException(status_code=400, detail="lat must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise HTTPException(status_code=400, detail="lon must be between -180 and 180.")
    if not -12.0 <= tz_offset <= 14.0:
        raise HTTPException(status_code=400, detail="tz_offset must be between -12 and 14 hours.")
    if not -500.0 <= elevation <= 9000.0:
        raise HTTPException(status_code=400, detail="elevation (metres) is out of range.")
    try:
        y, m, d = (int(p) for p in date.split("-"))
        day = compute_panchanga(y, m, d, tz_offset, lat, lon, elevation)
        return day.to_dict()
    except (ValueError, PanchangaError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/health")
def health_check():
    import os
    return {
        "status": "healthy",
        "engine": "SweetAstro Consumer Engine v2 (deterministic core + calibrated articulation)",
        "ayanamsha": "Lahiri (Chitra Paksha)",
        "ephemeris_engine": ephemeris_engine_name(),
        "ephemeris_data": ephemeris_data_source(),
        "ephemeris_ok": ephemeris_engine_name() == "swisseph",
        "chat_ready": has_api_key(),
        "rules_loaded": len(ENGINE.catalog.rules),
        "chat_model": DEEPSEEK_MODEL,
        "deepseek_key_configured": has_api_key(),
        "geocoder": "nominatim (open-source, no key)",
        "google_geocoding": "configured" if os.environ.get("GOOGLE_MAPS_API_KEY") else "not configured",
        "push_configured": bool(os.environ.get("SWEETASTRO_VAPID_PUBLIC_KEY")),
    }


@app.post("/api/predict")
def predict_marriage_api(req: PredictionRequest):
    try:
        dob_parts = [int(p) for p in req.dob.split("-")]
        tob_parts = [int(float(p)) for p in req.tob.split(":")]
        lat, lon, geo_note = resolve_coordinates(
            req.place, req.lat, req.lon, provider=req.geocode_provider
        )

        answer = ENGINE.predict_marriage(
            year=dob_parts[0], month=dob_parts[1], day=dob_parts[2],
            hour=tob_parts[0], minute=tob_parts[1], second=tob_parts[2] if len(tob_parts) > 2 else 0.0,
            tz_offset=req.tz_offset,
            lat=lat, lon=lon,
            name=req.name,
            search_start_age=req.search_start_age,
            search_end_age=req.search_end_age,
        )

        p = answer.internal_payload
        return {
            "resolved_location": {
                "place": req.place,
                "lat": lat,
                "lon": lon,
                "note": geo_note,
            },
            "user_answer": {
                "headline": answer.bold_headline,
                "why_saying_this": answer.why_saying_this,
                "what_happens_before_then": answer.what_happens_before_then,
                "partner_and_marriage_profile": answer.partner_and_marriage_profile,
                "why_the_delay": answer.why_the_delay,
                "what_to_do_now": answer.what_to_do_now,
                "closing_question": answer.closing_question
            },
            "internal_bookkeeping": {
                "event": p.event,
                "best_period": p.best_period,
                "year_score": p.year_score,
                "month_score": p.month_score,
                "temporal_stability_pct": p.birth_time_stability_pct,
                "stability_classification": p.stability_classification,
                "parashari": p.parashari_strength,
                "d9": p.d9_strength,
                "vimshottari": p.vimshottari_strength,
                "transit": p.transit_strength,
                "jaimini": p.jaimini_strength,
                "negative_evidence": p.negative_evidence_score,
                "monthly_breakdown": p.why_not_other_months["monthly_breakdown"],
                "monthly_summary": p.why_not_other_months["summary"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/answer")
def answer_question_api(req: ConsumerAnswerRequest):
    """
    Consumer Answer Engine (Sec 12/16): any question, calibrated language,
    chart-specific optional remedies, safety-gated.
    """
    try:
        dob_parts = [int(p) for p in req.dob.split("-")]
        tob_parts = [int(float(p)) for p in req.tob.split(":")]
        lat, lon, geo_note = resolve_coordinates(
            req.place, req.lat, req.lon, provider=req.geocode_provider
        )
        result = ENGINE.answer_question(
            year=dob_parts[0], month=dob_parts[1], day=dob_parts[2],
            hour=tob_parts[0], minute=tob_parts[1],
            second=float(tob_parts[2]) if len(tob_parts) > 2 else 0.0,
            tz_offset=req.tz_offset, lat=lat, lon=lon,
            place=req.place, question=req.question,
            time_reliable=req.time_reliable,
            historical_events=req.historical_events,
        )
        payload = result.answer.to_dict()
        payload["resolved_location"] = {
            "place": req.place,
            "lat": lat,
            "lon": lon,
            "note": geo_note,
        }
        return payload
    except GeocodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _build_person_chart(person: PersonInput):
    dob_parts = [int(p) for p in person.dob.split("-")]
    tob_parts = [int(float(p)) for p in person.tob.split(":")]
    lat, lon, geo_note = resolve_coordinates(
        person.place, person.lat, person.lon, provider=person.geocode_provider
    )
    d1 = calculate_d1_chart(
        dob_parts[0], dob_parts[1], dob_parts[2],
        tob_parts[0], tob_parts[1],
        float(tob_parts[2]) if len(tob_parts) > 2 else 0.0,
        person.tz_offset, lat, lon,
    )
    return d1, {"place": person.place, "lat": lat, "lon": lon, "note": geo_note}


@app.post("/api/matching")
def matching_api(req: MatchingRequest):
    """Kundli Milan (Ashtakoota 36-point + Mangal dosha) for two birth records."""
    try:
        d1_a, loc_a = _build_person_chart(req.person_a)
        d1_b, loc_b = _build_person_chart(req.person_b)
    except GeocodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid birth data: {e}")

    label_a = req.person_a.name or "Person A"
    label_b = req.person_b.name or "Person B"
    result = match_charts(d1_a, d1_b, label_a=label_a, label_b=label_b)
    return {
        "result": result.to_dict(),
        "markdown": render_match_markdown(result, label_a, label_b),
        "locations": {"a": loc_a, "b": loc_b},
    }


@app.post("/api/calendar")
def calendar_api(req: CalendarRequest):
    """Dasha-boundary calendar (.ics) for the next N months — deterministic dates."""
    try:
        year, month, day = (int(part) for part in req.dob.split("-"))
        parts = [int(float(part)) for part in req.tob.split(":")]
        while len(parts) < 3:
            parts.append(0)
        if not -12.0 <= req.tz_offset <= 14.0:
            raise HTTPException(status_code=400, detail="tz_offset must be between -12 and 14 hours.")
        lat, lon, geo_note = resolve_coordinates(
            req.place, req.lat, req.lon, provider=req.geocode_provider)
        d1 = calculate_d1_chart(year, month, day, parts[0], parts[1], parts[2],
                                req.tz_offset, lat, lon)
        birth_dt = datetime(year, month, day, parts[0], parts[1], parts[2])
        timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        horizon = now + timedelta(days=30 * max(1, min(req.horizon_months, 60)))

        events = []
        for period in timeline:
            if period.level not in ("MD", "AD"):
                continue
            if not (now <= period.start_date <= horizon):
                continue
            label = "Mahadasha" if period.level == "MD" else "Antardasha"
            parent = ""
            if period.level == "AD" and getattr(period, "parent_md", None):
                parent = f" (in {period.parent_md} MD)"
            events.append({
                "uid": f"{period.level}-{period.lord}-{period.start_date:%Y%m%d}",
                "summary": f"{label} begins: {period.lord}{parent}",
                "start": period.start_date.strftime("%Y-%m-%d"),
                "description": (
                    f"Vimshottari {label.lower()} boundary for {req.name or 'Native'}, computed "
                    "deterministically from the natal Moon nakshatra (Lahiri sidereal). "
                    "Boundaries shift with birth-time precision."
                ),
            })
        events.sort(key=lambda item: item["start"])
        ics = build_calendar_ics(
            calendar_name=f"SweetAstro dasha — {req.name or 'Native'}", events=events)
        slug = (req.name or "native").strip().replace(" ", "-").lower() or "native"
        return Response(
            content=ics,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="sweetastro-dasha-{slug}.ics"'},
        )
    except GeocodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid input: {exc}")


@app.post("/api/notifications/subscribe")
def notifications_subscribe(req: PushSubscribeRequest):
    """Stores a browser push subscription (delivery needs SWEETASTRO_VAPID_PUBLIC_KEY)."""
    endpoint = (req.endpoint or "").strip()
    if not endpoint.startswith("https://") or len(endpoint) > 1000:
        raise HTTPException(status_code=400, detail="Invalid push endpoint.")
    created = NOTIFICATIONS.subscribe(endpoint, req.keys, req.profile[:200])
    return {
        "ok": True,
        "created": created,
        "subscriptions": NOTIFICATIONS.count(),
        "push_configured": bool(os.environ.get("SWEETASTRO_VAPID_PUBLIC_KEY")),
    }


@app.post("/api/notifications/unsubscribe")
def notifications_unsubscribe(req: PushSubscribeRequest):
    removed = NOTIFICATIONS.unsubscribe(req.endpoint or "")
    return {"ok": True, "removed": removed}


@app.post("/api/rectify")
def rectify_api(req: RectifyRequest):
    """Rank candidate birth times against dated events (assist; never a verified time)."""
    try:
        year, month, day = (int(part) for part in req.dob.split("-"))
        lat, lon, geo_note = resolve_coordinates(
            req.place, req.lat, req.lon, provider=req.geocode_provider)
        result = rectify_birth_time(
            year=year, month=month, day=day, tz_offset=req.tz_offset,
            lat=lat, lon=lon, events=req.events or [], topic=req.topic,
        )
    except GeocodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "result": result.to_dict(),
        "location": {"place": req.place, "lat": lat, "lon": lon, "note": geo_note},
    }


@app.post("/api/timing")
def timing_api(req: TimingRequest):
    """Promise-gated event timing windows (interpretive, no guarantee)."""
    if req.event not in EVENT_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event {req.event!r}. Choose one of: {', '.join(EVENT_CONFIGS)}",
        )
    try:
        d1, loc = _build_person_chart(req.person)
        dob_parts = [int(p) for p in req.person.dob.split("-")]
        tob_parts = [int(float(p)) for p in req.person.tob.split(":")]
        birth_dt = datetime(
            dob_parts[0], dob_parts[1], dob_parts[2],
            tob_parts[0], tob_parts[1],
            int(float(tob_parts[2])) if len(tob_parts) > 2 else 0,
        )
        range_start = (datetime.strptime(req.range_start, "%Y-%m-%d")
                       if req.range_start else datetime.now())
        range_end = (datetime.strptime(req.range_end, "%Y-%m-%d")
                     if req.range_end else range_start + timedelta(days=365 * 3))
        result = find_timing_windows(
            d1, birth_dt, req.event, range_start, range_end,
            tz_offset=req.person.tz_offset, lat=loc["lat"], lon=loc["lon"],
        )
    except GeocodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    return {
        "result": result.to_dict(),
        "markdown": render_timing_markdown(result),
        "location": loc,
    }


@app.get("/api/backtest/dataset")
def get_backtest_dataset():
    data_file = Path(__file__).parent.parent.parent / "data" / "test_charts" / "historical_verified.json"
    if not data_file.exists():
        return []
    import json
    with open(data_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/backtest/run")
def run_backtest_api():
    data_file = Path(__file__).parent.parent.parent / "data" / "test_charts" / "historical_verified.json"
    try:
        metrics, records = ENGINE.run_backtest(data_file)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Backtest dataset not found.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Backtest failed: {exc}")
    return {
        "metrics": {
            "total_charts_tested": metrics.total_charts_tested,
            "top_1_year_accuracy": metrics.top_1_year_accuracy,
            "top_3_year_accuracy": metrics.top_3_year_accuracy,
            "mean_absolute_error_months": metrics.mean_absolute_error_months,
            "median_absolute_error_months": metrics.median_absolute_error_months,
            "confidence_interval_95": metrics.confidence_interval_95,
            "within_2_months_share": metrics.within_2_months_share,
            "high_confidence_top3_year_share": metrics.high_confidence_top3_year_share,
            "accuracy_claim": False,
            "claim_note": metrics.claim_note,
        },
        "records": [
            {
                "prediction_id": r.prediction_id,
                "chart_id": r.chart_id,
                "actual_date": r.actual_date_str,
                "predicted_period": r.predicted_period_label,
                "is_top_1": r.is_top_1_year,
                "is_top_3": r.is_top_3_year,
                "year_error": r.year_error,
                "month_error": r.month_error,
                "confidence_score": r.confidence_score,
                "stability_score": r.stability_score,
                "withheld": r.withheld
            }
            for r in records
        ]
    }


@app.post("/api/tournament/run")
def run_tournament_api():
    data_file = Path(__file__).parent.parent.parent / "data" / "test_charts" / "historical_verified.json"
    try:
        tourney = ENGINE.run_tournament(data_file)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tournament dataset not found.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Tournament failed: {exc}")
    return [
        {
            "model_name": t.model_name,
            "description": t.description,
            "top_1_yr": t.metrics.top_1_year_accuracy,
            "top_3_yr": t.metrics.top_3_year_accuracy,
            "mae_months": t.metrics.mean_absolute_error_months,
            "weights": {
                "parashari": t.weights.parashari,
                "d9": t.weights.d9,
                "dasha": t.weights.dasha,
                "transit": t.weights.transit,
                "jaimini": t.weights.jaimini
            }
        }
        for t in tourney
    ]


@app.get("/api/rules")
def get_rules_catalog():
    return [
        {
            "rule_id": r.rule_id,
            "category": r.category,
            "source": f"{r.source.book} Ch.{r.source.chapter}:{r.source.verse}",
            "interpretation": r.interpretation,
            "weight": r.base_weight,
            "timing_capability": r.timing_capability
        }
        for r in ENGINE.catalog.rules.values()
    ]


def _planet_row(state) -> Dict[str, Any]:
    return {
        "name": state.name,
        "sign": state.sign,
        "sign_index": state.sign_index,
        "house": state.house,
        "degree": round(state.degree_in_sign, 4),
        "retrograde": bool(state.is_retrograde),
        "combust": bool(state.is_combust),
        "dignity": state.dignity,
        "nakshatra": state.nakshatra,
        "nakshatra_pada": state.nakshatra_pada,
        "nakshatra_lord": state.nakshatra_lord,
    }


@app.post("/api/chart")
def chart_api(req: ChartRequest):
    """Deterministic chart snapshot for the web app: planets, houses, dasha, panchanga."""
    try:
        year, month, day = (int(part) for part in req.dob.split("-"))
        parts = [int(float(part)) for part in req.tob.split(":")]
        while len(parts) < 3:
            parts.append(0)
        hour, minute = parts[0], parts[1]
        second = min(max(parts[2], 0), 59)
        if not -12.0 <= req.tz_offset <= 14.0:
            raise HTTPException(status_code=400, detail="tz_offset must be between -12 and 14 hours.")
        if not -90.0 <= req.lat <= 90.0 or not -180.0 <= req.lon <= 180.0:
            raise HTTPException(status_code=400, detail="Invalid coordinates.")
        lat, lon, geo_note = resolve_coordinates(
            req.place, req.lat, req.lon, provider=req.geocode_provider)
        d1 = calculate_d1_chart(year, month, day, hour, minute, second, req.tz_offset, lat, lon)
        birth_dt = datetime(year, month, day, hour, minute, second)
        timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state = get_dasha_at_date(timeline, now)

        if state is not None:
            dasha = {
                "mahadasha": state.mahadasha,
                "antardasha": state.antardasha,
                "pratyantardasha": state.pratyantardasha,
                "md_start": state.md_period.start_date.isoformat(timespec="seconds"),
                "md_end": state.md_period.end_date.isoformat(timespec="seconds"),
                "ad_start": state.ad_period.start_date.isoformat(timespec="seconds"),
                "ad_end": state.ad_period.end_date.isoformat(timespec="seconds"),
                "pd_start": state.pd_period.start_date.isoformat(timespec="seconds"),
                "pd_end": state.pd_period.end_date.isoformat(timespec="seconds"),
            }
        else:
            dasha = {
                "mahadasha": "—", "antardasha": "—", "pratyantardasha": "—",
                "md_start": "", "md_end": "", "ad_start": "", "ad_end": "",
                "pd_start": "", "pd_end": "",
            }

        try:
            natal_panchanga = compute_natal_panchanga(
                year, month, day, hour, minute, second, req.tz_offset)
            panchanga = {
                "vara": natal_panchanga.vara,
                "tithi": natal_panchanga.tithi,
                "paksha": natal_panchanga.paksha,
                "nakshatra": natal_panchanga.nakshatra,
                "nakshatra_pada": natal_panchanga.nakshatra_pada,
                "yoga": natal_panchanga.yoga,
                "karana": natal_panchanga.karana,
            }
        except Exception:
            panchanga = None

        upcoming = []
        try:
            for period in upcoming_periods(timeline, now, levels=("MD", "AD"), limit=6):
                upcoming.append({
                    "lord": period.lord,
                    "level": period.level,
                    "start": period.start_date.isoformat(timespec="seconds"),
                    "end": period.end_date.isoformat(timespec="seconds"),
                })
        except Exception:
            upcoming = []

        def _period_row(period, level: str, current: bool) -> Dict[str, Any]:
            return {
                "lord": period.lord,
                "level": level,
                "start": period.start_date.isoformat(timespec="seconds"),
                "end": period.end_date.isoformat(timespec="seconds"),
                "current": current,
            }

        current_md = state.mahadasha if state is not None else None
        timeline_rows = [
            _period_row(p, "MD", bool(current_md and p.lord == current_md))
            for p in timeline if p.level == "MD"
        ]
        current_ads = [
            _period_row(p, "AD", bool(p.start_date <= now <= p.end_date))
            for p in timeline
            if p.level == "AD" and current_md and p.parent_md == current_md
        ]

        return {
            "birth": {
                "name": req.name or "Native",
                "dob": req.dob,
                "tob": req.tob,
                "place": req.place or f"{lat:.4f}, {lon:.4f}",
                "tz_offset": req.tz_offset,
                "lat": lat,
                "lon": lon,
                "geo_note": geo_note,
            },
            "chart": {
                "ascendant_sign": d1.ascendant_sign,
                "ascendant_sign_index": d1.ascendant_sign_index,
                "ascendant_degree": round(d1.ascendant_degree_in_sign, 4),
                "ayanamsha": round(d1.ayanamsha, 6),
                "planets": [_planet_row(d1.planets[name]) for name in PLANETS],
                "houses": [
                    {
                        "house": house.house_num,
                        "sign": house.sign,
                        "sign_index": house.sign_index,
                        "lord": house.lord,
                        "occupants": list(house.occupants),
                    }
                    for house in d1.houses.values()
                ],
            },
            "dasha": dasha,
            "panchanga": panchanga,
            "upcoming": upcoming,
            "timeline": timeline_rows,
            "current_ads": current_ads,
            "birth_time_reliable": req.time_reliable,
            "calculation": (
                f"{ephemeris_engine_name()} ({ephemeris_data_source()}); "
                f"Lahiri ayanamsha {d1.ayanamsha:.4f}°; Vimshottari 365.2425 days/year; "
                f"whole-sign houses."
                + ("" if req.time_reliable else
                   " Birth time uncertain (noon placeholder): lagna, houses and "
                   "house-based / divisional readings carry reduced confidence.")
            ),
        }
    except GeocodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (ValueError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid input: {exc}")


_APP_INDEX = Path(__file__).parent / "static" / "app" / "index.html"
_APP_SW = Path(__file__).parent / "static" / "app" / "sw.js"


@app.get("/app/sw.js", include_in_schema=False)
def app_service_worker():
    """Service worker for the SPA, scoped to the whole origin so it can cache app assets."""
    if _APP_SW.exists():
        return FileResponse(_APP_SW, media_type="application/javascript",
                            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="Service worker not built.")


@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
@app.get("/app/{subpath:path}", response_class=HTMLResponse, include_in_schema=False)
def app_page(subpath: str = ""):
    """New web app (Phase 0/1): React SPA served under /app with client-side routing."""
    if _APP_INDEX.exists():
        return HTMLResponse(_APP_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>SweetAstro app is not built yet</h1>"
        "<p>Run <code>.\\dev.ps1 ui-build</code> (or <code>cd frontend; npm install; npm run build</code>).</p>",
        status_code=503,
    )


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Chat-first UI (primary experience)."""
    chat_file = Path(__file__).parent / "static" / "chat.html"
    if chat_file.exists():
        with open(chat_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SweetAstro Chat is running. Static UI not found.</h1>"


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    """Legacy testing dashboard (predict / backtest / tournament / rules)."""
    html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SweetAstro API running. Static UI not found.</h1>"


@app.get("/match", response_class=HTMLResponse)
def match_page():
    """Kundli Milan (compatibility) UI."""
    html_file = Path(__file__).parent / "static" / "match.html"
    if html_file.exists():
        with open(html_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SweetAstro matching UI not found.</h1>"
