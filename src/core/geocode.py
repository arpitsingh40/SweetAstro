"""
Birth-place geocoding — open-source first, Google optional.

Default provider: OpenStreetMap Nominatim (no API key needed).
  - Usage policy respected: identifying User-Agent, `limit` capped, single
    search endpoint, errors surfaced (never silent fallback coordinates).
  - Endpoint override via env SWEETASTRO_GEOCODER_URL (self-hosted Nominatim).

Optional provider: Google Geocoding API when env GOOGLE_MAPS_API_KEY is set
  and caller passes provider="google". Keeps the "Google or open source"
  requirement without forcing users to buy a key.

Only stdlib is used (urllib) so there is no new dependency.
"""

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

NOMINATIM_URL = os.environ.get(
    "SWEETASTRO_GEOCODER_URL", "https://nominatim.openstreetmap.org/search"
)
USER_AGENT = os.environ.get(
    "SWEETASTRO_GEOCODER_UA", "SweetAstro/1.0 (birth-place geocoding; contact: admin@sweetastro.local)"
)
REQUEST_TIMEOUT = float(os.environ.get("SWEETASTRO_GEOCODER_TIMEOUT", "8"))
_MAX_LIMIT = 10

# Simple in-process cache + politeness throttle (Nominatim asks max ~1 req/s).
# Locks make the throttle and cache safe under the API's threadpool: without
# them, concurrent requests could bypass the 1 req/s policy and refetch the
# same query simultaneously.
_cache: Dict[str, list] = {}
_last_call_ts: float = 0.0
_cache_lock = threading.Lock()
_fetch_lock = threading.Lock()
_throttle_lock = threading.Lock()


class GeocodeError(Exception):
    """Raised when a place string cannot be resolved to coordinates."""


@dataclass
class GeocodeResult:
    lat: float
    lon: float
    display_name: str
    source: str = "nominatim"  # or "google"
    raw: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "display_name": self.display_name,
            "source": self.source,
        }


def _throttle() -> None:
    global _last_call_ts
    with _throttle_lock:
        elapsed = time.monotonic() - _last_call_ts
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _last_call_ts = time.monotonic()


def _http_get_json(url: str, params: Dict[str, str], timeout: float) -> object:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network, HTTP 4xx/5xx, bad JSON
        raise GeocodeError(f"Geocoder request failed: {exc}") from exc


def _parse_nominatim(data: object, query: str) -> List[GeocodeResult]:
    results: List[GeocodeResult] = []
    if isinstance(data, list):
        for item in data:
            try:
                results.append(
                    GeocodeResult(
                        lat=float(item["lat"]),
                        lon=float(item["lon"]),
                        display_name=str(item.get("display_name", query)),
                        source="nominatim",
                        raw=item if isinstance(item, dict) else {},
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return results


def search_places(query: str, limit: int = 5, provider: str = "nominatim") -> List[GeocodeResult]:
    """
    Returns up to `limit` candidate matches for a free-text address.
    Raises GeocodeError on empty query, network failure, or bad provider setup.
    Returns [] when the provider simply has no match (caller decides how to surface).
    """
    query = (query or "").strip()
    if not query:
        raise GeocodeError("Enter a birth place (city, town, or address) to search.")
    limit = max(1, min(int(limit or 5), _MAX_LIMIT))

    if provider == "google":
        return _search_google(query, limit)

    cache_key = f"nominatim|{query.lower()}|{limit}"
    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return list(cached)

    # Serialize cache-miss fetches so the 1 req/s politeness policy holds and
    # the same query is only fetched once under concurrency.
    with _fetch_lock:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached is not None:
                return list(cached)
        _throttle()
        data = _http_get_json(
            NOMINATIM_URL,
            {"q": query, "format": "jsonv2", "limit": str(limit), "addressdetails": "1"},
            REQUEST_TIMEOUT,
        )
        results = _parse_nominatim(data, query)
        with _cache_lock:
            _cache[cache_key] = list(results)
    return results


def _search_google(query: str, limit: int) -> List[GeocodeResult]:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise GeocodeError(
            "Google geocoding needs a GOOGLE_MAPS_API_KEY on the server. "
            "Use the default open-source search instead."
        )

    cache_key = f"google|{query.lower()}|{limit}"
    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        return list(cached)

    with _fetch_lock:
        with _cache_lock:
            cached = _cache.get(cache_key)
            if cached is not None:
                return list(cached)

        _throttle()
        data = _http_get_json(
            "https://maps.googleapis.com/maps/api/geocode/json",
            {"address": query, "key": api_key},
            REQUEST_TIMEOUT,
        )

        # Google returns HTTP 200 even for API-level failures.
        status = data.get("status") if isinstance(data, dict) else None
        if status not in (None, "OK", "ZERO_RESULTS"):
            message = data.get("error_message", "") if isinstance(data, dict) else ""
            raise GeocodeError(f"Google geocoding failed ({status}): {message}".strip())

        results: List[GeocodeResult] = []
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            for item in data["results"][:limit]:
                try:
                    loc = item["geometry"]["location"]
                    results.append(
                        GeocodeResult(
                            lat=float(loc["lat"]),
                            lon=float(loc["lng"]),
                            display_name=str(item.get("formatted_address", query)),
                            source="google",
                            raw=item,
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue

        with _cache_lock:
            _cache[cache_key] = list(results)
    return results


def geocode_place(query: str, provider: str = "nominatim") -> GeocodeResult:
    """
    Resolves a place string to its single best coordinate match.
    Raises GeocodeError when nothing matches (never returns a guessed location).
    """
    matches = search_places(query, limit=1, provider=provider)
    if not matches:
        raise GeocodeError(
            f"No coordinates found for '{query}'. Try 'City, State, Country' "
            "(e.g. 'Jaipur, Rajasthan, India')."
        )
    return matches[0]


def resolve_coordinates(
    place: str,
    lat: Optional[float],
    lon: Optional[float],
    default_lat: float = 28.6139,
    default_lon: float = 77.2090,
    provider: str = "nominatim",
) -> tuple:
    """
    Returns (lat, lon, note). When `place` is non-empty, geocodes it and the
    geocoded coordinates win over any manually passed lat/lon. When `place`
    is empty, returns the passed (or default) coordinates untouched.

    Resilience: if geocoding fails (network outage) but the caller already
    supplied explicit non-default coordinates, those are used with a warning
    note instead of failing. Raises GeocodeError only when `place` was given
    but cannot be resolved AND no usable coordinates exist — never silently
    falls back to defaults.
    """
    if not (place and place.strip()):
        return (
            default_lat if lat is None else float(lat),
            default_lon if lon is None else float(lon),
            "Manual coordinates used.",
        )
    try:
        hit = geocode_place(place.strip(), provider=provider)
        return hit.lat, hit.lon, f"Geocoded '{place.strip()}' -> {hit.display_name} ({hit.source})."
    except GeocodeError as exc:
        have_manual = (
            lat is not None and lon is not None
            and (float(lat) != default_lat or float(lon) != default_lon)
        )
        if have_manual:
            return (float(lat), float(lon),
                    f"Place search failed ({exc}); using the coordinates you entered.")
        raise
