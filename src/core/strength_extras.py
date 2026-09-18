"""
P3 completions: Varsha/Masa Bala, Bhava Bala, dasha cross-system agreement.

Declared conventions (variants exist; never silently mixed):

- **Varsha Bala (15 virupas)** goes to the weekday lord of the Mesha Sankranti
  (sidereal Sun ingress into Aries) that opened the solar year containing the
  birth. **Masa Bala (30 virupas)** goes to the weekday lord of the ingress
  that opened the sidereal solar month containing the birth.
- **Bhava Bala**: Bhavadhipati Bala = the house lord's classical Shadbala
  (virupas); Bhava Drishti Bala = net aspect value falling on the house
  (benefic add, malefic subtract, using the standard drishti-value scheme).
  Bhava Digbala (direction of the house itself) is NOT computed: the classical
  rule keys off bhava madhya and rasi classifications that need a declared
  source edition; omitted rather than guessed.
- **Dasha cross-system agreement** counts whether the planet matches the
  Vimshottari MD lord, the Yogini dasha lord, and the Chara sign (occupant or
  sign lord). It is an independent cross-check, never stacked as a claim.

Interpretive only — no accuracy claim.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .chart import D1Chart
from .classical_shadbala import (
    _DRISHTI_VALUE, _SPECIAL_FULL, _WEEKDAY_LORD, calculate_classical_shadbala,
)
from .constants import NATURAL_BENEFICS, PHYSICAL_PLANETS, SIGN_LORDS


# --------------------------------------------------------------- Varsha/Masa

def _ingress_local(target_lon: float, year: int, tz_offset: float) -> datetime:
    from .varshaphala import solar_return_datetime
    return solar_return_datetime(target_lon, year) + timedelta(hours=tz_offset)


def varsha_masa_lords(birth_dt: datetime, tz_offset: float,
                      sun_sidereal_lon: float) -> Dict[str, str]:
    """Weekday lords of the solar-year and solar-month ingresses before birth."""
    year = birth_dt.year

    def _latest_ingress(target: float) -> datetime:
        candidates = [
            _ingress_local(target, year, tz_offset),
            _ingress_local(target, year - 1, tz_offset),
        ]
        past = [c for c in candidates if c <= birth_dt]
        return max(past) if past else min(candidates)

    year_ingress = _latest_ingress(0.0)
    month_start = float(int(sun_sidereal_lon // 30) * 30)
    month_ingress = _latest_ingress(month_start)
    return {
        "varsha_lord": _WEEKDAY_LORD[year_ingress.weekday()],
        "masa_lord": _WEEKDAY_LORD[month_ingress.weekday()],
        "varsha_ingress": year_ingress.strftime("%Y-%m-%d"),
        "masa_ingress": month_ingress.strftime("%Y-%m-%d"),
    }


# ------------------------------------------------------------------ Bhava Bala

@dataclass
class BhavaStrength:
    house: int
    bhavadhipati: float
    drishti: float
    total: float
    category: str


def _house_drishti(d1: D1Chart, house: int) -> float:
    target_sign = d1.houses[house].sign_index
    total = 0.0
    for other in PHYSICAL_PLANETS:
        distance = ((target_sign - d1.planets[other].sign_index) % 12) + 1
        value = _DRISHTI_VALUE.get(distance, 0.0)
        if other in _SPECIAL_FULL and distance in _SPECIAL_FULL[other]:
            value = 60.0
        if value:
            total += value if other in NATURAL_BENEFICS else -value
    return round(total, 2)


def calculate_bhava_bala(
    d1: D1Chart,
    lord_virupas: Optional[Dict[str, float]] = None,
) -> List[BhavaStrength]:
    """
    Bhavadhipati + Bhava Drishti Bala per house (Bhava Digbala omitted,
    documented). `lord_virupas` optionally supplies each lord's classical
    Shadbala total; otherwise it is computed with standard defaults.
    """
    if lord_virupas is None:
        lord_virupas = {}
        for lord in set(d1.houses[h].lord for h in range(1, 13)):
            try:
                lord_virupas[lord] = calculate_classical_shadbala(
                    d1, lord).total_virupas
            except Exception:
                lord_virupas[lord] = 0.0

    results: List[BhavaStrength] = []
    for house in range(1, 13):
        lord = d1.houses[house].lord
        bhavadhipati = float(lord_virupas.get(lord, 0.0))
        drishti = _house_drishti(d1, house)
        total = round(bhavadhipati + drishti, 2)
        if total >= 400.0:
            category = "Strong"
        elif total >= 300.0:
            category = "Moderate"
        else:
            category = "Weak"
        results.append(BhavaStrength(
            house=house, bhavadhipati=round(bhavadhipati, 2),
            drishti=drishti, total=total, category=category,
        ))
    return results


# --------------------------------------------------------- Dasha agreement

@dataclass
class DashaAgreement:
    planet: str
    vimshottari_match: bool
    yogini_match: bool
    chara_match: bool
    agreement_count: int
    verdict: str
    note: str = ""


def dasha_agreement_for_planet(d1: D1Chart, birth_dt: datetime,
                               query_dt: datetime, planet: str) -> DashaAgreement:
    """Independent cross-check across Vimshottari, Yogini and Chara dasha."""
    from .chara_dasha import calculate_chara_timeline, get_chara_at_date
    from .dasha import calculate_vimshottari_timeline, get_dasha_at_date
    from .yogini import calculate_yogini_timeline, get_yogini_at_date

    moon = d1.planets["Moon"].longitude
    vim = get_dasha_at_date(calculate_vimshottari_timeline(birth_dt, moon), query_dt)
    vim_match = bool(vim and (planet in (vim.mahadasha, vim.antardasha, vim.pratyantardasha)))

    yog = get_yogini_at_date(calculate_yogini_timeline(birth_dt, moon), query_dt)
    yog_match = bool(yog and planet in (yog.mahadasha_lord, yog.antardasha_lord))

    chara = get_chara_at_date(calculate_chara_timeline(d1, birth_dt), query_dt)
    chara_match = False
    if chara:
        sign = chara.mahadasha_sign
        chara_match = (d1.planets[planet].sign == sign) or (SIGN_LORDS[sign] == planet)

    count = sum((vim_match, yog_match, chara_match))
    verdict = ("cross-confirmed" if count >= 2 else
               ("single-system" if count == 1 else "not activated"))
    return DashaAgreement(
        planet=planet, vimshottari_match=vim_match, yogini_match=yog_match,
        chara_match=chara_match, agreement_count=count, verdict=verdict,
        note=("Independent cross-check only; systems are never stacked into "
              "a combined probability."),
    )
