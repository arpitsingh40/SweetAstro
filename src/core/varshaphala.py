"""
Varshaphala (Tajika annual chart) — core layer.

Provides the solar-return moment, Muntha, Muntha lord and the Varsha (annual)
lagna. Full Tajika year-lord strength (Panchavargiya Bala) and ithasala
aspects are out of scope and documented as such — this module supplies the
verifiable annual frame consumers ask for: "what does this year hold".

Source tradition: Tajika Neelakanthi / Varshaphala as catalogued in
docs/knowledge/01_classical_canon.md (entries 61-64) and
docs/knowledge/02_modern_specialized.md (entries 240, 308-310).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .chart import D1Chart
from .constants import INDEX_TO_SIGN, SIGN_LORDS
from .ephemeris import (
    calculate_ascendant, calculate_lahiri_ayanamsha, calculate_planet_positions,
    datetime_to_julian_day,
)

_SUN_MEAN_MOTION = 0.9856473  # degrees per day


def sun_sidereal_longitude(dt_utc: datetime) -> float:
    jd = datetime_to_julian_day(dt_utc.year, dt_utc.month, dt_utc.day,
                                dt_utc.hour, dt_utc.minute, dt_utc.second,
                                tz_offset_hours=0.0)
    ayanamsha = calculate_lahiri_ayanamsha(jd)
    return calculate_planet_positions(jd, ayanamsha)["Sun"]["longitude"] % 360.0


def solar_return_datetime(natal_sun_lon: float, target_year: int) -> datetime:
    """UTC datetime when the transiting Sun returns to the natal sidereal longitude."""
    target = natal_sun_lon % 360.0
    # Sidereal Sun enters Aries around 14 April -> day ~103 of the year.
    guess = datetime(target_year, 1, 1) + timedelta(days=103 + target / _SUN_MEAN_MOTION)
    # Keep the initial guess inside the target calendar year: for targets above
    # ~258 deg the raw offset overshoots into the next year, which made Newton
    # converge on the following year's return (and mislabel the annual chart).
    if guess.year > target_year:
        guess -= timedelta(days=365.2425)
    for _ in range(10):
        current = sun_sidereal_longitude(guess)
        diff = ((target - current + 180.0) % 360.0) - 180.0
        if abs(diff) < 0.0005:
            break
        guess += timedelta(days=diff / _SUN_MEAN_MOTION)
    return guess


@dataclass
class VarshaphalaReading:
    target_year: int
    solar_return_utc: str
    muntha_sign: str
    muntha_house_from_lagna: int
    muntha_lord: str
    varsha_lagna_sign: str
    theme: str            # supportive / mixed / challenging
    note: str


_SUPPORTIVE_MUNTHA_HOUSES = (1, 5, 9, 10, 11)
_CHALLENGING_MUNTHA_HOUSES = (6, 8, 12)


def compute_varshaphala(d1: D1Chart, birth_dt: datetime, target_year: int,
                        tz_offset: float, lat: float, lon: float) -> VarshaphalaReading:
    """Annual chart frame for target_year (Muntha + Varsha lagna, verified math)."""
    natal_sun_lon = d1.planets["Sun"].longitude % 360.0
    return_utc = solar_return_datetime(natal_sun_lon, target_year)

    age = max(0, target_year - birth_dt.year)
    muntha_sign_index = ((d1.ascendant_sign_index - 1 + age) % 12) + 1
    muntha_sign = INDEX_TO_SIGN[muntha_sign_index]
    muntha_house = ((muntha_sign_index - d1.ascendant_sign_index) % 12) + 1

    jd = datetime_to_julian_day(return_utc.year, return_utc.month, return_utc.day,
                                return_utc.hour, return_utc.minute, return_utc.second,
                                tz_offset_hours=0.0)
    ayanamsha = calculate_lahiri_ayanamsha(jd)
    varsha_asc = calculate_ascendant(jd, lat, lon, ayanamsha)
    varsha_lagna = INDEX_TO_SIGN[int((varsha_asc % 360.0) // 30) + 1]

    if muntha_house in _SUPPORTIVE_MUNTHA_HOUSES:
        theme = "supportive"
    elif muntha_house in _CHALLENGING_MUNTHA_HOUSES:
        theme = "challenging"
    else:
        theme = "mixed"

    note = (f"Annual chart year {target_year}: Muntha in {muntha_sign} "
            f"(H{muntha_house} from lagna, theme {theme}); Muntha lord "
            f"{SIGN_LORDS[muntha_sign]}; Varsha lagna {varsha_lagna}. "
            "Full Tajika year-lord strength (Panchavargiya Bala) is not computed; "
            "treat the annual theme as a planning frame, not a prediction.")

    return VarshaphalaReading(
        target_year=target_year,
        solar_return_utc=return_utc.isoformat(timespec="minutes"),
        muntha_sign=muntha_sign,
        muntha_house_from_lagna=muntha_house,
        muntha_lord=SIGN_LORDS[muntha_sign],
        varsha_lagna_sign=varsha_lagna,
        theme=theme,
        note=note,
    )
