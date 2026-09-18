"""
Deterministic Panchanga engine (drik ganita).

Computes the five limbs — Tithi, Vara, Nakshatra, Yoga, Karana — plus sunrise/
sunset, Rahu Kalam, Yamaganda, Gulika Kalam and Abhijit muhurta for a given
civil date, location and timezone.

Verification: outputs are tested against authentic reference values extracted
from DrikPanchang.com (drik ganita, Lahiri ayanamsha) in
data/reference/panchanga_drikpanchang.json.

Conventions (matching the reference):
- Panchang day runs sunrise to sunrise; Vara is the weekday of the civil date.
- Sunrise/sunset follow the Swiss Ephemeris default convention (upper limb
  with refraction), which reproduces the reference to the minute.
- Tithi/Karana use Moon-Sun elongation (ayanamsha-independent); Nakshatra uses
  the sidereal Moon longitude (Lahiri); Yoga uses Sun+Moon (ayanamsha-independent).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional, Tuple

from .constants import INDEX_TO_SIGN, NAKSHATRAS
from .ephemeris import (
    HAS_SWISSEPH,
    calculate_lahiri_ayanamsha,
    calculate_obliquity,
    calculate_planet_positions,
    calculate_sidereal_time,
    datetime_to_julian_day,
)

if HAS_SWISSEPH:
    import swisseph as swe

TITHI_NAMES_SHUKLA = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Purnima",
]
TITHI_NAMES_KRISHNA = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Amavasya",
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarman", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
]

KARANA_MOVABLE = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
VARA_SANSKRIT = ["Somawara", "Mangalawara", "Budhawara", "Guruwara", "Shukrawara", "Shaniwara", "Raviwara"]

# Segment (1-8) of the sunrise-to-sunset day for each weekday (Mon=0 .. Sun=6)
_RAHU_SEGMENT = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}
_YAMAGANDA_SEGMENT = {0: 4, 1: 3, 2: 2, 3: 1, 4: 7, 5: 6, 6: 5}
_GULIKA_SEGMENT = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 7}

TITHI_SPAN = 12.0
NAKSHATRA_SPAN = 360.0 / 27.0
YOGA_SPAN = 360.0 / 27.0
KARANA_SPAN = 6.0


class PanchangaError(RuntimeError):
    pass


@dataclass
class PanchangaDay:
    date: date
    latitude: float
    longitude: float
    tz_offset: float
    sunrise: datetime
    sunset: datetime
    vara: str
    vara_sanskrit: str
    tithi_index: int            # 1..30
    tithi_name: str
    paksha: str
    tithi_ends: Optional[datetime]
    nakshatra: str
    nakshatra_pada: int
    nakshatra_ends: Optional[datetime]
    yoga: str
    yoga_ends: Optional[datetime]
    karana: str
    karana_ends: Optional[datetime]
    moon_sign: str
    sun_sign: str
    ayanamsha: float
    rahu_kalam: Tuple[datetime, datetime]
    yamaganda: Tuple[datetime, datetime]
    gulika_kalam: Tuple[datetime, datetime]
    abhijit: Tuple[datetime, datetime]

    @property
    def day_length_minutes(self) -> float:
        return (self.sunset - self.sunrise).total_seconds() / 60.0

    def to_dict(self) -> dict:
        def iso(dt: Optional[datetime]) -> Optional[str]:
            return None if dt is None else dt.isoformat(sep=" ", timespec="seconds")

        return {
            "date": self.date.isoformat(),
            "location": {"latitude": self.latitude, "longitude": self.longitude, "tz_offset": self.tz_offset},
            "sunrise": iso(self.sunrise),
            "sunset": iso(self.sunset),
            "vara": self.vara,
            "vara_sanskrit": self.vara_sanskrit,
            "tithi": f"{self.paksha} {self.tithi_name}",
            "tithi_index": self.tithi_index,
            "tithi_ends": iso(self.tithi_ends),
            "nakshatra": self.nakshatra,
            "nakshatra_pada": self.nakshatra_pada,
            "nakshatra_ends": iso(self.nakshatra_ends),
            "yoga": self.yoga,
            "yoga_ends": iso(self.yoga_ends),
            "karana": self.karana,
            "karana_ends": iso(self.karana_ends),
            "moon_sign": self.moon_sign,
            "sun_sign": self.sun_sign,
            "ayanamsha": round(self.ayanamsha, 6),
            "rahu_kalam": [iso(self.rahu_kalam[0]), iso(self.rahu_kalam[1])],
            "yamaganda": [iso(self.yamaganda[0]), iso(self.yamaganda[1])],
            "gulika_kalam": [iso(self.gulika_kalam[0]), iso(self.gulika_kalam[1])],
            "abhijit": [iso(self.abhijit[0]), iso(self.abhijit[1])],
        }


# --------------------------------------------------------------------------- utils

def _jd_to_calendar(jd: float) -> Tuple[int, int, int, float]:
    """Julian day -> (year, month, day, hours) using the Meeus inverse method."""
    z = math.floor(jd + 0.5)
    f = (jd + 0.5) - z
    if z >= 2299161:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4.0)
    else:
        a = z
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day_int = int(day)
    return int(year), int(month), day_int, (day - day_int) * 24.0


def _jd_to_local(jd_ut: float, tz_offset: float) -> datetime:
    if HAS_SWISSEPH:
        y, m, d, hour_frac = swe.revjul(jd_ut + tz_offset / 24.0)
        total_seconds = round(hour_frac * 3600.0)
        return datetime(y, m, d) + timedelta(seconds=total_seconds)
    y, m, d, hours = _jd_to_calendar(jd_ut)
    return datetime(y, m, d) + timedelta(hours=hours + tz_offset)


def _elongation(jd: float) -> float:
    ayan = calculate_lahiri_ayanamsha(jd)
    positions = calculate_planet_positions(jd, ayan)
    return (positions["Moon"]["longitude"] - positions["Sun"]["longitude"]) % 360.0


def _moon_lon(jd: float) -> float:
    ayan = calculate_lahiri_ayanamsha(jd)
    return calculate_planet_positions(jd, ayan)["Moon"]["longitude"]


def _sun_moon_sum(jd: float) -> float:
    ayan = calculate_lahiri_ayanamsha(jd)
    positions = calculate_planet_positions(jd, ayan)
    return (positions["Sun"]["longitude"] + positions["Moon"]["longitude"]) % 360.0


def _find_crossing(start_jd: float, target_deg: float, value_fn: Callable[[float], float],
                   max_days: float = 2.5, coarse_minutes: float = 20.0) -> float:
    """First time after start_jd where value_fn crosses target_deg (rising value)."""
    def progress(jd: float) -> float:
        return ((value_fn(jd) - target_deg + 540.0) % 360.0) - 180.0

    step = coarse_minutes / 1440.0
    lo = start_jd
    hi = lo + step
    limit = int(max_days * 24 * 60 / coarse_minutes) + 10
    for _ in range(limit):
        if progress(hi) >= 0.0:
            break
        lo = hi
        hi = lo + step
    else:
        raise PanchangaError(f"crossing for target {target_deg} not found within {max_days} days")

    for _ in range(45):
        mid = (lo + hi) / 2.0
        if progress(mid) >= 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def tithi_name(index: int) -> Tuple[str, str]:
    """1-based tithi index -> (paksha, name)."""
    if not 1 <= index <= 30:
        raise ValueError(f"tithi index out of range: {index}")
    if index <= 15:
        return "Shukla", TITHI_NAMES_SHUKLA[index - 1]
    return "Krishna", TITHI_NAMES_KRISHNA[index - 16]


def karana_name(index: int) -> str:
    """0-based karana index (0..59) -> name."""
    if index == 0:
        return "Kimstughna"
    if 1 <= index <= 56:
        return KARANA_MOVABLE[(index - 1) % 7]
    return {57: "Shakuni", 58: "Chatushpada", 59: "Naga"}[index]


def _segment_window(sunrise: datetime, sunset: datetime, segment: int) -> Tuple[datetime, datetime]:
    day_seconds = (sunset - sunrise).total_seconds()
    start = sunrise + timedelta(seconds=day_seconds * (segment - 1) / 8.0)
    end = sunrise + timedelta(seconds=day_seconds * segment / 8.0)
    return start, end


def _abhijit_window(sunrise: datetime, sunset: datetime) -> Tuple[datetime, datetime]:
    day_seconds = (sunset - sunrise).total_seconds()
    start = sunrise + timedelta(seconds=day_seconds * 7.0 / 15.0)
    end = sunrise + timedelta(seconds=day_seconds * 8.0 / 15.0)
    return start, end


def _sun_times_fallback(y: int, m: int, d: int, tz_offset: float, lat: float,
                        lon: float, elevation_m: float) -> Tuple[datetime, datetime]:
    """
    Built-in sunrise/sunset (used only when pyswisseph is unavailable).

    Standard solar position (apparent tropical longitude -> RA/dec), iterated
    local transit (LST == RA), then the hour angle for the upper-limb +
    refraction altitude (-0.833 deg, adjusted for elevation). Documented
    envelope ~1-2 minutes vs Swiss Ephemeris; the panchanga tests assert a
    5-minute tolerance on the fallback path.
    """
    jd_midnight = datetime_to_julian_day(y, m, d, 0, 0, 0, tz_offset)

    def sun_ra_dec(jd: float) -> Tuple[float, float]:
        ayan = calculate_lahiri_ayanamsha(jd)
        sid = calculate_planet_positions(jd, ayan)["Sun"]["longitude"] % 360.0
        lam = math.radians((sid + ayan) % 360.0)
        eps = calculate_obliquity(jd)
        ra = math.degrees(math.atan2(math.sin(lam) * math.cos(eps), math.cos(lam))) % 360.0
        dec = math.asin(math.sin(lam) * math.sin(eps))
        return ra, dec

    transit_hours_ut = 12.0 - tz_offset - lon / 15.0
    for _ in range(4):
        jd_guess = jd_midnight + transit_hours_ut / 24.0
        ra, _dec = sun_ra_dec(jd_guess)
        lst = calculate_sidereal_time(jd_guess, lon)
        offset_deg = ((ra - lst + 540.0) % 360.0) - 180.0
        transit_hours_ut += offset_deg / 15.0410686
    jd_transit = jd_midnight + transit_hours_ut / 24.0
    _ra, dec = sun_ra_dec(jd_transit)

    depression_deg = -0.833 - 0.0347 * math.sqrt(max(0.0, elevation_m))
    lat_r = math.radians(lat)
    cos_h = ((math.sin(math.radians(depression_deg)) - math.sin(lat_r) * math.sin(dec))
             / (math.cos(lat_r) * math.cos(dec)))
    if cos_h < -1.0:
        raise PanchangaError(f"sun never sets for {y}-{m:02d}-{d:02d} (polar day)")
    if cos_h > 1.0:
        raise PanchangaError(f"sunrise not found for {y}-{m:02d}-{d:02d} (polar day/night?)")
    hour_angle_hours = math.degrees(math.acos(cos_h)) / 15.0
    sunrise = _jd_to_local(jd_transit - hour_angle_hours / 24.0, tz_offset)
    sunset = _jd_to_local(jd_transit + hour_angle_hours / 24.0, tz_offset)
    return sunrise, sunset


def sun_times(y: int, m: int, d: int, tz_offset: float, lat: float, lon: float,
              elevation_m: float = 0.0) -> Tuple[datetime, datetime]:
    """Local sunrise/sunset (Swiss Ephemeris convention, built-in fallback)."""
    if not HAS_SWISSEPH:
        return _sun_times_fallback(y, m, d, tz_offset, lat, lon, elevation_m)
    jd_start = datetime_to_julian_day(y, m, d, 0, 0, 0, tz_offset)
    rc_r, tr = swe.rise_trans(jd_start, swe.SUN, swe.CALC_RISE, (lon, lat, elevation_m))
    rc_s, ts = swe.rise_trans(jd_start, swe.SUN, swe.CALC_SET, (lon, lat, elevation_m))
    if rc_r != 0:
        raise PanchangaError(f"sunrise not found for {y}-{m:02d}-{d:02d} (polar day/night?)")
    if rc_s != 0:
        raise PanchangaError(f"sunset not found for {y}-{m:02d}-{d:02d} (polar day/night?)")
    return _jd_to_local(tr[0], tz_offset), _jd_to_local(ts[0], tz_offset)


# --------------------------------------------------------------------------- engine

def compute_panchanga(y: int, m: int, d: int, tz_offset: float, lat: float, lon: float,
                      elevation_m: float = 0.0,
                      at: Optional[datetime] = None,
                      include_end_times: bool = True) -> PanchangaDay:
    """
    Computes the panchanga for the given civil date at the location.

    `at` (local, naive) selects the reference instant for the five limbs;
    when omitted, sunrise is used (the traditional panchanga instant).
    `include_end_times=False` skips the boundary-crossing searches (much faster);
    end-time fields are then None. Use it for day-level filtering and compute the
    full panchanga only for candidate days.
    """
    sunrise, sunset = sun_times(y, m, d, tz_offset, lat, lon, elevation_m)
    panchanga_date = date(y, m, d)

    ref_local = at or sunrise
    ref_jd = datetime_to_julian_day(ref_local.year, ref_local.month, ref_local.day,
                                    ref_local.hour, ref_local.minute, ref_local.second,
                                    tz_offset)
    ayan = calculate_lahiri_ayanamsha(ref_jd)
    positions = calculate_planet_positions(ref_jd, ayan)
    sun_lon = positions["Sun"]["longitude"]
    moon_lon = positions["Moon"]["longitude"]
    elong = (moon_lon - sun_lon) % 360.0

    t_index = int(elong / TITHI_SPAN) + 1
    paksha, t_name = tithi_name(t_index)
    tithi_ends = _jd_to_local(
        _find_crossing(ref_jd, (int(elong / TITHI_SPAN) + 1) * TITHI_SPAN, _elongation),
        tz_offset) if include_end_times else None

    nak_index = int(moon_lon / NAKSHATRA_SPAN) % 27
    nakshatra = NAKSHATRAS[nak_index]["name"]
    pada = int((moon_lon % NAKSHATRA_SPAN) / (NAKSHATRA_SPAN / 4.0)) + 1
    nakshatra_ends = _jd_to_local(
        _find_crossing(ref_jd, (nak_index + 1) * NAKSHATRA_SPAN, _moon_lon),
        tz_offset) if include_end_times else None

    sum_lon = (sun_lon + moon_lon) % 360.0
    yoga_index = int(sum_lon / YOGA_SPAN) % 27
    yoga = YOGA_NAMES[yoga_index]
    yoga_ends = _jd_to_local(
        _find_crossing(ref_jd, (yoga_index + 1) * YOGA_SPAN, _sun_moon_sum),
        tz_offset) if include_end_times else None

    karana_index = int(elong / KARANA_SPAN) % 60
    karana = karana_name(karana_index)
    karana_ends = _jd_to_local(
        _find_crossing(ref_jd, (karana_index + 1) * KARANA_SPAN, _elongation),
        tz_offset) if include_end_times else None

    wd = panchanga_date.weekday()
    vara = WEEKDAY_NAMES[wd]
    vara_sk = VARA_SANSKRIT[wd]

    return PanchangaDay(
        date=panchanga_date,
        latitude=lat,
        longitude=lon,
        tz_offset=tz_offset,
        sunrise=sunrise,
        sunset=sunset,
        vara=vara,
        vara_sanskrit=vara_sk,
        tithi_index=t_index,
        tithi_name=t_name,
        paksha=paksha,
        tithi_ends=tithi_ends,
        nakshatra=nakshatra,
        nakshatra_pada=pada,
        nakshatra_ends=nakshatra_ends,
        yoga=yoga,
        yoga_ends=yoga_ends,
        karana=karana,
        karana_ends=karana_ends,
        moon_sign=INDEX_TO_SIGN[int(moon_lon // 30) + 1],
        sun_sign=INDEX_TO_SIGN[int(sun_lon // 30) + 1],
        ayanamsha=ayan,
        rahu_kalam=_segment_window(sunrise, sunset, _RAHU_SEGMENT[wd]),
        yamaganda=_segment_window(sunrise, sunset, _YAMAGANDA_SEGMENT[wd]),
        gulika_kalam=_segment_window(sunrise, sunset, _GULIKA_SEGMENT[wd]),
        abhijit=_abhijit_window(sunrise, sunset),
    )


def vishti_windows(day: PanchangaDay) -> List[Tuple[datetime, datetime]]:
    """
    Intraday Vishti (Bhadra) karana windows between sunrise and sunset.

    Bhadra is avoided for auspicious beginnings; windows that fall inside the
    day are returned so muhurta searches can exclude them.
    """
    windows: List[Tuple[datetime, datetime]] = []

    jd = datetime_to_julian_day(day.sunrise.year, day.sunrise.month, day.sunrise.day,
                                day.sunrise.hour, day.sunrise.minute, day.sunrise.second,
                                day.tz_offset)
    elong = _elongation(jd)
    index = int(elong / KARANA_SPAN) % 60
    current = day.sunrise

    for _ in range(6):  # at most ~5 karana boundaries per daylight span
        if current >= day.sunset:
            break
        end_jd = _find_crossing(jd, (index + 1) * KARANA_SPAN, _elongation)
        end_dt = _jd_to_local(end_jd, day.tz_offset)
        if karana_name(index) == "Vishti":
            windows.append((current, min(end_dt, day.sunset)))
        current = end_dt
        jd = end_jd
        index = (index + 1) % 60
    return [(s, e) for s, e in windows if e > s]
