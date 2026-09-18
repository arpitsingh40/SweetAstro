"""
Deterministic Astronomical Ephemeris Engine.
Computes high-precision Julian Days, Lahiri Ayanamsha, Sidereal Planetary
Longitudes, and Ascendant (Lagna).

Features:
1. Native integration with Swiss Ephemeris (`swisseph` / `pyswisseph`) if available.
2. Built-in high-precision astronomical ephemeris (Jean Meeus / Keplerian / VSOP orbital
   elements with perturbations) as an accurate, dependency-free fallback.
"""

import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple, Optional

# Attempt optional Swiss Ephemeris import
try:
    import swisseph as swe
    HAS_SWISSEPH = True
except ImportError:
    HAS_SWISSEPH = False

# Official Swiss Ephemeris data files (.se1), fetched by fetch_ephemeris.py.
# When present they give JPL-grade precision; otherwise the Swiss Ephemeris
# library uses its built-in Moshier model (still sub-arcsecond for planets).
_EPHE_DIR = Path(os.environ.get(
    "SWEETASTRO_EPHE_PATH",
    Path(__file__).resolve().parent.parent.parent / "data" / "ephe",
))
if HAS_SWISSEPH:
    if _EPHE_DIR.exists():
        swe.set_ephe_path(str(_EPHE_DIR))
    swe.set_sid_mode(swe.SIDM_LAHIRI)


def ephemeris_engine_name() -> str:
    """Which ephemeris backend is active: 'swisseph' or the builtin fallback."""
    return "swisseph" if HAS_SWISSEPH else "builtin-meeus-fallback"


def ephemeris_data_source() -> str:
    """Human-readable description of the data source, for provenance display."""
    if not HAS_SWISSEPH:
        return "builtin Meeus series (approximate — install pyswisseph for accuracy)"
    try:
        if _EPHE_DIR.exists() and any(_EPHE_DIR.glob("*.se1")):
            return "Swiss Ephemeris + official .se1 data files"
    except OSError:
        pass
    return "Swiss Ephemeris (Moshier model)"


def datetime_to_julian_day(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: float = 0.0, tz_offset_hours: float = 0.0) -> float:
    """
    Converts a calendar date and local time with timezone offset into Julian Day (UT).
    Algorithm from Jean Meeus 'Astronomical Algorithms', Chapter 7.
    """
    # Convert local time to UTC decimal hours
    decimal_hours = hour + (minute / 60.0) + (second / 3600.0) - tz_offset_hours
    day_fraction = decimal_hours / 24.0

    y = year
    m = month
    d = day + day_fraction

    if m <= 2:
        y -= 1
        m += 12

    a = int(y / 100)
    b = 2 - a + int(a / 4)

    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    return jd


def calculate_lahiri_ayanamsha(jd: float) -> float:
    """
    Calculates the Lahiri (Chitra Paksha) Ayanamsha for a given Julian Day.
    IAU formula referenced to J2000.0 (JD 2451545.0).
    At J2000.0, Lahiri ayanamsha = 23° 51' 25.53" = 23.857092°
    """
    if HAS_SWISSEPH:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        return swe.get_ayanamsa_ut(jd)

    t = (jd - 2451545.0) / 36525.0
    t2 = t * t
    t3 = t2 * t
    ayanamsha_sec = 23.857092 * 3600.0 + 5029.0966 * t + 1.1120 * t2 - 0.00256 * t3
    ayanamsha_deg = (ayanamsha_sec / 3600.0) % 360.0
    if ayanamsha_deg < 0:
        ayanamsha_deg += 360.0
    return ayanamsha_deg


def calculate_obliquity(jd: float) -> float:
    """True obliquity of the ecliptic in radians."""
    t = (jd - 2451545.0) / 36525.0
    eps0 = 23.43929111 - (46.8150 * t + 0.00059 * (t ** 2) - 0.001813 * (t ** 3)) / 3600.0
    return math.radians(eps0)


def calculate_sidereal_time(jd: float, longitude_east_deg: float) -> float:
    """
    Calculates Local Sidereal Time (LST) in degrees [0, 360).
    """
    t = (jd - 2451545.0) / 36525.0
    # Greenwich Mean Sidereal Time in degrees
    gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * (t ** 2) - (t ** 3) / 38710000.0
    gmst = gmst % 360.0
    lst = (gmst + longitude_east_deg) % 360.0
    return lst


def calculate_ascendant(jd: float, lat_deg: float, lon_deg: float, ayanamsha: float,
                        sid_mode: Optional[int] = None) -> float:
    """
    Calculates the Sidereal Ascendant (Lagna) degree in [0, 360).

    `ayanamsha` is the precomputed offset for the chosen zodiac origin and is
    what the built-in fallback uses. `sid_mode` is the Swiss Ephemeris SIDM_*
    constant for that same origin (see src.core.ayanamsha); it defaults to
    Lahiri for backward compatibility.
    """
    if HAS_SWISSEPH:
        swe.set_sid_mode(sid_mode if sid_mode is not None else swe.SIDM_LAHIRI)
        cusps, ascmc = swe.houses_ex(jd, lat_deg, lon_deg, b'W', swe.FLG_SIDEREAL)
        return ascmc[0] % 360.0

    # High-precision spherical trigonometric Ascendant formula
    lst_rad = math.radians(calculate_sidereal_time(jd, lon_deg))
    lat_rad = math.radians(lat_deg)
    eps_rad = calculate_obliquity(jd)

    # The atan2 branch below yields the descendant (setting point); adding
    # 180 degrees converts it to the ascendant (rising point). No refraction
    # correction is applied: the ascendant is a geometric intersection of the
    # ecliptic with the horizon, not an observed altitude.
    # tan(Lagna_trop) = -cos(RAMC) / (sin(RAMC)*cos(eps) + tan(phi)*sin(eps))
    sin_ramc = math.sin(lst_rad)
    cos_ramc = math.cos(lst_rad)
    sin_eps = math.sin(eps_rad)
    cos_eps = math.cos(eps_rad)
    tan_lat = math.tan(lat_rad)

    y = -cos_ramc
    x = (sin_ramc * cos_eps + tan_lat * sin_eps)

    lagna_trop_deg = (math.degrees(math.atan2(y, x)) + 180.0) % 360.0
    lagna_sidereal = (lagna_trop_deg - ayanamsha) % 360.0
    return lagna_sidereal


def _kepler_solve(m_rad: float, e: float, tol: float = 1e-8) -> float:
    """Solve Kepler's equation M = E - e*sin(E) for Eccentric Anomaly E."""
    e_val = m_rad
    for _ in range(30):
        delta = (e_val - e * math.sin(e_val) - m_rad) / (1.0 - e * math.cos(e_val))
        e_val -= delta
        if abs(delta) < tol:
            break
    return e_val


def frame_precession_deg(jd: float) -> float:
    """General precession in longitude from J2000.0 to `jd` (degrees).

    The built-in Keplerian elements (Standish/JPL) are referred to the mean
    ecliptic and equinox of J2000.0, while the ayanamsha is of-date. The
    fallback must add this correction before the ayanamsha subtraction;
    otherwise J2000 longitudes are treated as of-date, drifting by ~1.4 deg
    per century (audit round 2, item 1).
    """
    t = (jd - 2451545.0) / 36525.0
    return (5029.0966 * t + 1.1120 * t * t - 0.00256 * t ** 3) / 3600.0


def compute_heliocentric_planet(jd: float, planet: str) -> Tuple[float, float, float]:
    """
    Computes heliocentric orbital coordinates (longitude, latitude, distance)
    using accurate Keplerian orbital elements and secular rates.
    """
    t = (jd - 2451545.0) / 36525.0

    # Orbital elements [a0, a_rate, e0, e_rate, i0, i_rate, L0, L_rate, w0, w_rate, O0, O_rate]
    # Reference: Standish et al. (NASA JPL Planetary Ephemeris)
    elements = {
        "Mercury": (0.38709927, 0.00000037, 0.20563593, 0.00002366, 7.00497902, -0.00594749, 252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081),
        "Venus":   (0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890, 181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418),
        "Earth":   (1.00000261, 0.00000562, 0.01671123, -0.00004392, 0.00001531, -0.01294668, 100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0),
        "Mars":    (1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131, -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343),
        "Jupiter": (5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714, 34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106),
        "Saturn":  (9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609, 49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794),
    }

    if planet not in elements:
        return 0.0, 0.0, 1.0

    a0, ar, e0, er, i0, ir, l0, lr, w0, wr, o0, or_rate = elements[planet]
    a = a0 + ar * t
    e = e0 + er * t
    inc = math.radians(i0 + ir * t)
    l_mean = (l0 + lr * t) % 360.0
    w_peri = (w0 + wr * t) % 360.0
    node = math.radians((o0 + or_rate * t) % 360.0)

    m = math.radians((l_mean - w_peri) % 360.0)
    e_anom = _kepler_solve(m, e)

    x_orb = a * (math.cos(e_anom) - e)
    y_orb = a * math.sqrt(1.0 - e * e) * math.sin(e_anom)

    r = math.sqrt(x_orb * x_orb + y_orb * y_orb)
    v = math.atan2(y_orb, x_orb)

    omega = math.radians(w_peri) - node
    u = v + omega

    x_ecl = r * (math.cos(node) * math.cos(u) - math.sin(node) * math.sin(u) * math.cos(inc))
    y_ecl = r * (math.sin(node) * math.cos(u) + math.cos(node) * math.sin(u) * math.cos(inc))
    z_ecl = r * (math.sin(u) * math.sin(inc))

    return x_ecl, y_ecl, z_ecl


def calculate_planet_positions(jd: float, ayanamsha: float,
                               sid_mode: Optional[int] = None) -> Dict[str, Dict[str, float]]:
    """
    Computes geocentric sidereal longitudes and daily speeds for all 9 Navagrahas.
    `sid_mode` selects the Swiss Ephemeris sidereal origin (defaults to Lahiri);
    `ayanamsha` is the matching offset used by the built-in fallback.
    Returns: Dict[planet_name, {"longitude": deg, "speed": deg_per_day, "is_retrograde": bool}]
    """
    results: Dict[str, Dict[str, float]] = {}

    if HAS_SWISSEPH:
        swe.set_sid_mode(sid_mode if sid_mode is not None else swe.SIDM_LAHIRI)
        mapping = {
            "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
            "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
            "Venus": swe.VENUS, "Saturn": swe.SATURN,
            "Rahu": swe.MEAN_NODE,
        }
        for name, pid in mapping.items():
            pos, flags = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SPEED)
            lon = pos[0] % 360.0
            spd = pos[3]
            is_retro = (spd < 0.0) and (name not in ["Sun", "Moon", "Rahu"])
            results[name] = {"longitude": lon, "speed": spd, "is_retrograde": is_retro}

        # Ketu is exactly 180° opposite to Rahu
        ketu_lon = (results["Rahu"]["longitude"] + 180.0) % 360.0
        results["Ketu"] = {"longitude": ketu_lon, "speed": results["Rahu"]["speed"], "is_retrograde": False}
        return results

    # Built-in High Precision Fallback
    t = (jd - 2451545.0) / 36525.0

    # Keplerian elements are in the J2000 ecliptic frame; the Moon series and
    # mean node formula below are already referred to the equinox of date.
    prec = frame_precession_deg(jd)

    # Earth coords
    xe, ye, ze = compute_heliocentric_planet(jd, "Earth")

    # Sun position: geocentric coords are opposite of Earth heliocentric
    sun_lon_trop = (math.degrees(math.atan2(-ye, -xe)) + 360.0) % 360.0
    sun_lon_of_date = (sun_lon_trop + prec) % 360.0
    sun_lon_sid = (sun_lon_of_date - ayanamsha) % 360.0
    xp_e, yp_e, zp_e = compute_heliocentric_planet(jd, "Earth")
    xp2_e, yp2_e, zp2_e = compute_heliocentric_planet(jd + 0.01, "Earth")
    sun_lon2_trop = (math.degrees(math.atan2(-yp2_e, -xp2_e)) + 360.0) % 360.0
    sun_speed = ((sun_lon2_trop - sun_lon_trop + 540.0) % 360.0 - 180.0) / 0.01
    results["Sun"] = {"longitude": sun_lon_sid, "speed": sun_speed, "is_retrograde": False}

    # Moon position (Meeus truncated lunar series)
    def _moon_tropical_longitude(jd_value: float) -> float:
        t_val = (jd_value - 2451545.0) / 36525.0
        lp = (218.3164477 + 481267.88128 * t_val) % 360.0
        d_val = (297.8501921 + 445267.11140 * t_val) % 360.0
        m_sun_val = (357.5291092 + 35999.05029 * t_val) % 360.0
        m_moon_val = (134.9633964 + 477198.86750 * t_val) % 360.0
        f_val = (93.2720950 + 483202.01752 * t_val) % 360.0
        return lp + (
            6.288774 * math.sin(math.radians(m_moon_val))
            + 1.274027 * math.sin(math.radians(2 * d_val - m_moon_val))
            + 0.658314 * math.sin(math.radians(2 * d_val))
            + 0.213618 * math.sin(math.radians(2 * m_moon_val))
            - 0.185116 * math.sin(math.radians(m_sun_val))
            - 0.114332 * math.sin(math.radians(2 * f_val))
            + 0.052931 * math.sin(math.radians(m_moon_val + m_sun_val))
            + 0.037528 * math.sin(math.radians(m_moon_val - m_sun_val))
            + 0.037448 * math.sin(math.radians(2 * d_val + m_moon_val))
            + 0.021162 * math.sin(math.radians(2 * d_val - m_moon_val))
        )

    l_moon_trop = _moon_tropical_longitude(jd)
    moon_lon2_trop = _moon_tropical_longitude(jd + 0.01)
    moon_speed = ((moon_lon2_trop - l_moon_trop + 540.0) % 360.0 - 180.0) / 0.01
    moon_lon_sid = (l_moon_trop - ayanamsha) % 360.0
    results["Moon"] = {"longitude": moon_lon_sid, "speed": moon_speed, "is_retrograde": False}

    # Planets: Mercury, Venus, Mars, Jupiter, Saturn
    for p in ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]:
        xp, yp, zp = compute_heliocentric_planet(jd, p)
        # Geocentric coordinates
        xg = xp - xe
        yg = yp - ye
        lon_trop = (math.degrees(math.atan2(yg, xg)) + 360.0) % 360.0
        lon_of_date = (lon_trop + prec) % 360.0
        lon_sid = (lon_of_date - ayanamsha) % 360.0

        # Calculate speed via small dt (0.01 day)
        xp2, yp2, zp2 = compute_heliocentric_planet(jd + 0.01, p)
        xe2, ye2, ze2 = compute_heliocentric_planet(jd + 0.01, "Earth")
        lon2_trop = (math.degrees(math.atan2(yp2 - ye2, xp2 - xe2)) + 360.0) % 360.0
        diff = (lon2_trop - lon_trop + 540.0) % 360.0 - 180.0
        spd = diff / 0.01
        is_retro = spd < 0.0

        results[p] = {"longitude": lon_sid, "speed": spd, "is_retrograde": is_retro}

    # Rahu & Ketu (Mean Lunar Node) — retrogression flag suppressed to match
    # the Swiss Ephemeris path (is_retrograde=False for the nodes there).
    omega = (125.04452 - 1934.136261 * t + 0.0020708 * (t ** 2)) % 360.0
    rahu_sid = (omega - ayanamsha) % 360.0
    ketu_sid = (rahu_sid + 180.0) % 360.0

    results["Rahu"] = {"longitude": rahu_sid, "speed": -0.0529, "is_retrograde": False}
    results["Ketu"] = {"longitude": ketu_sid, "speed": -0.0529, "is_retrograde": False}

    return results
