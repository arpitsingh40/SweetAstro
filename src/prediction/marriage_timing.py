"""
Marriage Timing Prediction Engine (LEGACY — reference only).

Audit round 2, MEDIUM: this module is exported for backward compatibility and
analysis scripts but is **not used by any production path** (the consumer chat
engine uses `interpretation/promise.py` + `prediction/hierarchy.py`, and the
pre-registered accuracy protocol scores `PredictionHierarchy.predict`). Do not
build new features here; treat its outputs as unvalidated legacy heuristics.

Implements the 4-Layer Framework:
1. Natal Promise (7th house, Venus, Navamsa)
2. Vimshottari Dasha (timing windows)
3. Double Transit (Jupiter + Saturn triggers)
4. Month/Precise Timing (Mars/Sun transits)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from enum import Enum

from ..core.chart import D1Chart, PlanetState
from ..core.navamsa import NavamsaChart, NavamsaPlanetState
from ..core.arudha import calculate_upapada, UpapadaAnalysis
from ..core.constants import (
    PLANETS, SIGNS, SIGN_LORDS, NATURAL_BENEFICS, NATURAL_MALEFICS,
    VIMSHOTTARI_ORDER, VIMSHOTTARI_YEARS, INDEX_TO_SIGN, SIGN_TO_INDEX
)


class MarriageStrength(Enum):
    VERY_HIGH = "Very High"
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"
    DELAYED = "Delayed"
    DENIED = "Denied"


# Ordinal rank for merging windows (higher = stronger evidence).
_STRENGTH_RANK = {
    MarriageStrength.DENIED: 0,
    MarriageStrength.DELAYED: 1,
    MarriageStrength.LOW: 2,
    MarriageStrength.MODERATE: 3,
    MarriageStrength.HIGH: 4,
    MarriageStrength.VERY_HIGH: 5,
}


class MarriageIndicator(Enum):
    DASHA_7TH_LORD = "7th Lord Dasha"
    DASHA_VENUS = "Venus Dasha"
    DASHA_PLANET_IN_7TH = "Planet in 7th Dasha"
    DASHA_DARAKARAKA = "Darakaraka Dasha"
    DASHA_UPAPADA_LORD = "Upapada Lord Dasha"
    TRANSIT_JUPITER = "Jupiter Transit"
    TRANSIT_SATURN = "Saturn Transit"
    DOUBLE_TRANSIT = "Double Transit"
    NAVAMSA_CONFIRMATION = "Navamsa Confirmation"
    KP_2_7_11 = "KP 2-7-11 Signification"


@dataclass
class MarriageWindow:
    start_date: datetime
    end_date: datetime
    confidence: MarriageStrength
    indicators: List[MarriageIndicator]
    mahadasha_lord: str
    antardasha_lord: str
    pratyantardasha_lord: Optional[str] = None
    transit_jupiter_sign: Optional[str] = None
    transit_saturn_sign: Optional[str] = None
    predicted_month: Optional[int] = None
    predicted_year: Optional[int] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class MarriagePromise:
    promise_exists: bool
    strength: MarriageStrength
    seventh_house_sign: str
    seventh_lord: str
    seventh_lord_house: int
    seventh_lord_dignity: str
    venus_house: int
    venus_dignity: str
    venus_combust: bool
    planet_in_7th: List[str]
    benefics_in_7th: List[str]
    malefics_in_7th: List[str]
    manglik_dosha: bool
    delay_factors: List[str]
    early_marriage_factors: List[str]
    upapada: Optional[UpapadaAnalysis] = None


@dataclass
class NavamsaConfirmation:
    confirmed: bool
    d9_7th_lord: str
    d9_7th_lord_dignity: str
    d9_venus_dignity: str
    d9_jupiter_dignity: str
    vargottama_7th_lord: bool
    strength: MarriageStrength


@dataclass
class TransitTrigger:
    jupiter_transit_active: bool
    saturn_transit_active: bool
    double_transit_active: bool
    jupiter_aspecting_7th: bool
    saturn_aspecting_7th: bool
    rahu_transit_active: bool
    trigger_month: Optional[int] = None
    trigger_year: Optional[int] = None


@dataclass
class MarriagePrediction:
    promise: MarriagePromise
    navamsa: NavamsaConfirmation
    windows: List[MarriageWindow]
    best_window: Optional[MarriageWindow]
    earliest_marriage_age: Optional[float]
    latest_marriage_age: Optional[float]
    predicted_age_range: Tuple[float, float]
    overall_strength: MarriageStrength
    recommendations: List[str]
    upapada: Optional[UpapadaAnalysis] = None


class MarriageTimingEngine:

    def __init__(self, d1: D1Chart, d9: NavamsaChart, birth_date: datetime):
        self.d1 = d1
        self.d9 = d9
        self.birth_date = birth_date
        self.seventh_lord = self.d1.houses[7].lord
        self.seventh_house_sign = self.d1.houses[7].sign
        self.seventh_lord_house = self.d1.planets[self.seventh_lord].house if self.seventh_lord in self.d1.planets else 0
        self.upapada = calculate_upapada(d1, d9)

    def _is_planet_in_house(self, planet: str, house: int) -> bool:
        if planet in self.d1.planets:
            return self.d1.planets[planet].house == house
        return False

    def _get_planets_in_house(self, house: int) -> List[str]:
        return [
            p for p, state in self.d1.planets.items()
            if state.house == house
        ]

    def _get_d1_dignity(self, planet: str) -> str:
        if planet in self.d1.planets:
            return self.d1.planets[planet].dignity
        return "Unknown"

    def _get_d9_dignity(self, planet: str) -> str:
        if planet in self.d9.planets:
            return self.d9.planets[planet].d9_dignity
        return "Unknown"

    def _is_combust(self, planet: str) -> bool:
        if planet in self.d1.planets:
            return self.d1.planets[planet].is_combust
        return False

    def _get_aspecting_planets(self, house: int) -> List[str]:
        aspecting = []
        for planet, state in self.d1.planets.items():
            if house in state.aspecting_houses:
                aspecting.append(planet)
        return aspecting

    def _check_manglik_dosha(self) -> bool:
        manglik_houses = [1, 2, 4, 7, 8, 12]
        if "Mars" in self.d1.planets:
            return self.d1.planets["Mars"].house in manglik_houses
        return False

    def _get_darakaraka(self) -> str:
        # Spec: order by degree within sign (SA-SPEC-V1.0 Sec 6.1), matching
        # core.jaimini.calculate_chara_karakas. Rahu/Ketu excluded (7 physical grahas).
        lowest_degree = float('inf')
        darakaraka = None
        for planet, state in self.d1.planets.items():
            if planet in ["Rahu", "Ketu"]:
                continue
            if state.degree_in_sign < lowest_degree:
                lowest_degree = state.degree_in_sign
                darakaraka = planet
        return darakaraka

    # ========================================================================
    # LAYER 1: NATAL PROMISE ANALYSIS
    # ========================================================================

    def analyze_natal_promise(self) -> MarriagePromise:
        planets_in_7th = self._get_planets_in_house(7)
        benefics_in_7th = [p for p in planets_in_7th if p in NATURAL_BENEFICS]
        malefics_in_7th = [p for p in planets_in_7th if p in NATURAL_MALEFICS]

        seventh_lord_state = self.d1.planets.get(self.seventh_lord)
        seventh_lord_house = seventh_lord_state.house if seventh_lord_state else 0
        seventh_lord_dignity = self._get_d1_dignity(self.seventh_lord)

        venus_state = self.d1.planets.get("Venus")
        venus_house = venus_state.house if venus_state else 0
        venus_dignity = self._get_d1_dignity("Venus")
        venus_combust = self._is_combust("Venus")

        manglik = self._check_manglik_dosha()
        delay_factors = self._identify_delay_factors(seventh_lord_house)
        early_factors = self._identify_early_factors(seventh_lord_house)

        promise_exists, strength = self._assess_promise_strength(
            seventh_lord_house, seventh_lord_dignity,
            venus_house, venus_dignity, venus_combust,
            benefics_in_7th, malefics_in_7th, manglik
        )

        if self.upapada.delay_factors:
            delay_factors.extend(self.upapada.delay_factors)
        if self.upapada.strength_factors:
            early_factors.extend(self.upapada.strength_factors)

        return MarriagePromise(
            promise_exists=promise_exists,
            strength=strength,
            seventh_house_sign=self.seventh_house_sign,
            seventh_lord=self.seventh_lord,
            seventh_lord_house=seventh_lord_house,
            seventh_lord_dignity=seventh_lord_dignity,
            venus_house=venus_house,
            venus_dignity=venus_dignity,
            venus_combust=venus_combust,
            planet_in_7th=planets_in_7th,
            benefics_in_7th=benefics_in_7th,
            malefics_in_7th=malefics_in_7th,
            manglik_dosha=manglik,
            delay_factors=delay_factors,
            early_marriage_factors=early_factors,
            upapada=self.upapada
        )

    def _identify_delay_factors(self, seventh_lord_house: int) -> List[str]:
        delays = []

        saturn_in_7th = self._is_planet_in_house("Saturn", 7)
        saturn_aspecting_7th = "Saturn" in self._get_aspecting_planets(7)
        if saturn_in_7th or saturn_aspecting_7th:
            delays.append("Saturn influence on 7th house")

        if self._check_manglik_dosha():
            delays.append("Manglik Dosha (Mars in 1/2/4/7/8/12)")

        if seventh_lord_house in [6, 8, 12]:
            delays.append(f"7th lord in {seventh_lord_house}th house (dusthana)")

        if self._is_combust(self.seventh_lord):
            delays.append("7th lord combust")

        if self.seventh_lord in self.d1.planets:
            if self.d1.planets[self.seventh_lord].is_retrograde:
                delays.append("7th lord retrograde")

        if self.upapada and self.upapada.delay_factors:
            delays.extend(self.upapada.delay_factors)

        return delays

    def _identify_early_factors(self, seventh_lord_house: int) -> List[str]:
        factors = []

        if seventh_lord_house in [1, 2, 7, 11]:
            factors.append(f"7th lord in {seventh_lord_house}th house (favorable)")

        venus_in_7th = self._is_planet_in_house("Venus", 7)
        if venus_in_7th:
            factors.append("Venus in 7th house")

        jupiter_in_7th = self._is_planet_in_house("Jupiter", 7)
        if jupiter_in_7th:
            factors.append("Jupiter in 7th house")

        venus_state = self.d1.planets.get("Venus")
        if venus_state:
            if venus_state.dignity in ["Exalted", "Own", "Moolatrikona"]:
                factors.append(f"Venus {venus_state.dignity}")

        if self.upapada and self.upapada.strength_factors:
            factors.extend(self.upapada.strength_factors)

        return factors

    def _assess_promise_strength(
        self, seventh_lord_house: int, seventh_lord_dignity: str,
        venus_house: int, venus_dignity: str, venus_combust: bool,
        benefics_in_7th: List[str], malefics_in_7th: List[str],
        manglik: bool
    ) -> Tuple[bool, MarriageStrength]:
        score = 0

        if seventh_lord_house in [1, 2, 7, 11]:
            score += 3
        elif seventh_lord_house in [4, 5, 9, 10]:
            score += 2
        elif seventh_lord_house in [3, 6, 8, 12]:
            score += 1

        if seventh_lord_dignity in ["Exalted", "Own", "Moolatrikona"]:
            score += 3
        elif seventh_lord_dignity in ["Friend"]:
            score += 2
        elif seventh_lord_dignity in ["Neutral"]:
            score += 1
        elif seventh_lord_dignity in ["Debilitated", "Enemy"]:
            score -= 1

        if venus_house in [1, 2, 7, 11]:
            score += 3
        elif venus_house in [4, 5, 9, 10]:
            score += 2
        elif venus_house in [3, 6, 8, 12]:
            score += 1

        if venus_dignity in ["Exalted", "Own", "Moolatrikona"]:
            score += 3
        elif venus_dignity in ["Friend"]:
            score += 2
        elif venus_dignity in ["Neutral"]:
            score += 1
        elif venus_dignity in ["Debilitated", "Enemy"]:
            score -= 1

        if venus_combust:
            score -= 2

        score += len(benefics_in_7th)
        score -= len(malefics_in_7th)

        if manglik:
            score -= 1

        if self.upapada:
            if self.upapada.ul_lord_dignity in ["Exalted", "Own", "Moolatrikona"]:
                score += 2
            elif self.upapada.ul_lord_dignity in ["Debilitated", "Enemy"]:
                score -= 1
            if self.upapada.malefics_in_ul2:
                score -= 1
            if self.upapada.benefics_in_ul2:
                score += 1

        promise_exists = score >= 2

        if score >= 10:
            strength = MarriageStrength.VERY_HIGH
        elif score >= 7:
            strength = MarriageStrength.HIGH
        elif score >= 4:
            strength = MarriageStrength.MODERATE
        elif score >= 2:
            strength = MarriageStrength.LOW
        else:
            strength = MarriageStrength.DENIED

        return promise_exists, strength

    # ========================================================================
    # LAYER 2: VIMSHOTTARI DASHA ANALYSIS — RULE-BASED
    # ========================================================================

    def _is_marriage_lord(self, planet: str) -> List[str]:
        """
        Check if a planet is a 'Marriage Lord' — has direct connection to marriage.
        Returns list of connection types (empty = not a marriage lord).
        """
        connections = []
        sev_lord = self.seventh_lord
        dk = self._get_darakaraka()
        d1 = self.d1

        # Connection 1: IS the 7th lord
        if planet == sev_lord:
            connections.append("7th_lord")

        # Connection 2: IS Venus (natural karaka)
        if planet == "Venus":
            connections.append("venus")

        # Connection 3: IS Darakaraka (spouse significator)
        if planet == dk:
            connections.append("darakaraka")

        # Connection 4: IS UL lord (marriage institution)
        if planet == self.upapada.ul_lord:
            connections.append("ul_lord")

        # Connection 5: IS UL2 lord (marriage sustainability)
        if planet == self.upapada.ul2_lord:
            connections.append("ul2_lord")

        # Connection 6: Sits IN the 7th house
        if planet in d1.planets and d1.planets[planet].house == 7:
            connections.append("in_7th")

        # Connection 7: ASPECTS the 7th house
        if planet in d1.planets and 7 in d1.planets[planet].aspecting_houses:
            connections.append("aspects_7th")

        # Connection 8: ASPECTS the 7th lord
        if planet in d1.planets and sev_lord in d1.planets:
            sev_house = d1.planets[sev_lord].house
            if sev_house > 0 and sev_house in d1.planets[planet].aspecting_houses:
                connections.append("aspects_7th_lord")

        # Connection 9: In house 2, 7, or 11 (marriage houses)
        if planet in d1.planets and d1.planets[planet].house in [2, 7, 11]:
            connections.append(f"in_house_{d1.planets[planet].house}")

        # Connection 10: ASPECTS the UL sign
        if planet in d1.planets:
            ul_sign_idx = SIGN_TO_INDEX.get(self.upapada.ul_sign, 0)
            if ul_sign_idx in d1.planets[planet].aspecting_houses:
                connections.append("aspects_ul")

        # Connection 11: ASPECTS the UL lord
        if planet in d1.planets and self.upapada.ul_lord in d1.planets:
            ul_lord_house = d1.planets[self.upapada.ul_lord].house
            if ul_lord_house > 0 and ul_lord_house in d1.planets[planet].aspecting_houses:
                connections.append("aspects_ul_lord")

        # Connection 12: Sits IN the UL sign
        if planet in d1.planets:
            ul_sign_idx = SIGN_TO_INDEX.get(self.upapada.ul_sign, 0)
            if d1.planets[planet].sign_index == ul_sign_idx:
                connections.append("in_ul_sign")

        # Connection 13: In house 4, 10 (kendra from UL)
        if planet in d1.planets and d1.planets[planet].house in [4, 10]:
            connections.append(f"in_house_{d1.planets[planet].house}")

        return connections

    def _check_dasha_denial(self, md_lord: str, ad_lord: str) -> bool:
        """
        Hard denial check — returns True if marriage is blocked.
        """
        d1 = self.d1
        sev_lord = self.seventh_lord

        # HARD DENIAL: 7th lord combust running its own dasha
        if md_lord == sev_lord:
            if sev_lord in d1.planets and d1.planets[sev_lord].is_combust:
                return True

        # HARD DENIAL: Venus combust running Venus dasha
        if md_lord == "Venus":
            if "Venus" in d1.planets and d1.planets["Venus"].is_combust:
                return True

        # HARD DENIAL: Venus between Sun and Moon (classical)
        if "Venus" in d1.planets and "Sun" in d1.planets and "Moon" in d1.planets:
            ven_lon = d1.planets["Venus"].longitude
            sun_lon = d1.planets["Sun"].longitude
            moon_lon = d1.planets["Moon"].longitude
            if abs(ven_lon - sun_lon) < 15 and abs(ven_lon - moon_lon) < 15:
                if md_lord == "Venus" or ad_lord == "Venus":
                    return True

        return False

    def _check_dasha_for_marriage(self, state, check_date: datetime) -> Optional[MarriageWindow]:
        md_lord = state.mahadasha
        ad_lord = state.antardasha
        pd_lord = state.pratyantardasha

        md_period = state.md_period
        ad_period = state.ad_period

        # Hard denial check
        if self._check_dasha_denial(md_lord, ad_lord):
            return None

        # Check if MD or AD lord is a marriage lord
        md_connections = self._is_marriage_lord(md_lord)
        ad_connections = self._is_marriage_lord(ad_lord)

        # Rule: at least one of MD or AD must be a marriage lord
        if not md_connections and not ad_connections:
            return None

        # Build indicators
        indicators = []
        for conn in md_connections:
            indicators.append(self._get_indicator_for_connection(conn))
        for conn in ad_connections:
            ind = self._get_indicator_for_connection(conn)
            if ind not in indicators:
                indicators.append(ind)

        # Confidence based on connection count
        total_connections = len(md_connections) + len(ad_connections)
        if total_connections >= 4:
            confidence = MarriageStrength.VERY_HIGH
        elif total_connections >= 3:
            confidence = MarriageStrength.HIGH
        elif total_connections >= 2:
            confidence = MarriageStrength.MODERATE
        else:
            confidence = MarriageStrength.LOW

        window_start = ad_period.start_date
        window_end = ad_period.end_date

        if window_start < check_date:
            window_start = check_date

        return MarriageWindow(
            start_date=window_start,
            end_date=window_end,
            confidence=confidence,
            indicators=indicators if indicators else [MarriageIndicator.DASHA_7TH_LORD],
            mahadasha_lord=md_lord,
            antardasha_lord=ad_lord,
            pratyantardasha_lord=pd_lord,
            predicted_year=check_date.year
        )

    def _get_indicator_for_connection(self, conn: str) -> MarriageIndicator:
        mapping = {
            "7th_lord": MarriageIndicator.DASHA_7TH_LORD,
            "venus": MarriageIndicator.DASHA_VENUS,
            "darakaraka": MarriageIndicator.DASHA_DARAKARAKA,
            "ul_lord": MarriageIndicator.DASHA_UPAPADA_LORD,
            "ul2_lord": MarriageIndicator.DASHA_UPAPADA_LORD,
            "in_7th": MarriageIndicator.DASHA_PLANET_IN_7TH,
            "aspects_7th": MarriageIndicator.DASHA_PLANET_IN_7TH,
            "aspects_7th_lord": MarriageIndicator.DASHA_PLANET_IN_7TH,
            "in_house_2": MarriageIndicator.DASHA_PLANET_IN_7TH,
            "in_house_11": MarriageIndicator.DASHA_PLANET_IN_7TH,
        }
        return mapping.get(conn, MarriageIndicator.DASHA_7TH_LORD)

    def find_marriage_dashas(
        self,
        start_date: datetime,
        end_date: datetime,
        search_from_birth: bool = False
    ) -> List[MarriageWindow]:
        from ..core.dasha import calculate_vimshottari_timeline, get_dasha_at_date

        moon_lon = self.d1.planets["Moon"].longitude

        timeline = calculate_vimshottari_timeline(
            birth_dt=self.birth_date,
            moon_lon=moon_lon,
            max_years=120.0
        )

        windows = []

        if search_from_birth:
            effective_start = self.birth_date
        else:
            effective_start = start_date

        current = effective_start
        while current <= end_date:
            state = get_dasha_at_date(timeline, current)
            if state:
                window = self._check_dasha_for_marriage(state, current)
                if window:
                    windows.append(window)

            try:
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            except ValueError:
                current = current.replace(day=28, month=current.month + 1 if current.month < 12 else 1,
                                          year=current.year if current.month < 12 else current.year + 1)

        merged = self._merge_overlapping_windows(windows)

        min_age_years = 15
        min_age_date = self.birth_date.replace(year=self.birth_date.year + min_age_years)

        max_gap_days = 120
        extended = []
        for w in merged:
            ext_start = w.start_date - timedelta(days=max_gap_days)
            ext_end = w.end_date + timedelta(days=max_gap_days)
            if ext_end >= min_age_date:
                extended.append(MarriageWindow(
                    start_date=max(ext_start, min_age_date),
                    end_date=ext_end,
                    confidence=w.confidence,
                    indicators=w.indicators,
                    mahadasha_lord=w.mahadasha_lord,
                    antardasha_lord=w.antardasha_lord,
                    pratyantardasha_lord=w.pratyantardasha_lord,
                    predicted_year=w.predicted_year,
                    notes=w.notes
                ))

        return extended

    def _merge_overlapping_windows(self, windows: List[MarriageWindow]) -> List[MarriageWindow]:
        if not windows:
            return []

        sorted_windows = sorted(windows, key=lambda w: w.start_date)
        merged = [sorted_windows[0]]

        for current in sorted_windows[1:]:
            last = merged[-1]
            gap = (current.start_date - last.end_date).days
            if gap <= 7:
                stronger = (current
                            if _STRENGTH_RANK.get(current.confidence, 0)
                            > _STRENGTH_RANK.get(last.confidence, 0)
                            else last)
                merged[-1] = MarriageWindow(
                    start_date=last.start_date,
                    end_date=max(last.end_date, current.end_date),
                    confidence=stronger.confidence,
                    indicators=list(set(last.indicators + current.indicators)),
                    mahadasha_lord=last.mahadasha_lord,
                    antardasha_lord=last.antardasha_lord,
                    pratyantardasha_lord=last.pratyantardasha_lord,
                    predicted_year=last.predicted_year
                )
            else:
                merged.append(current)

        return merged

    # ========================================================================
    # LAYER 3: TRANSIT ANALYSIS
    # ========================================================================

    def analyze_transits(self, marriage_date: datetime) -> TransitTrigger:
        from ..core.transits import get_transit_positions

        transits = get_transit_positions(marriage_date)

        seventh_sign_idx = SIGNS.index(self.seventh_house_sign)

        jup_aspects_7th = False
        for asp in transits["Jupiter"].aspected_sign_indices:
            if asp == seventh_sign_idx:
                jup_aspects_7th = True
                break

        sat_aspects_7th = False
        for asp in transits["Saturn"].aspected_sign_indices:
            if asp == seventh_sign_idx:
                sat_aspects_7th = True
                break

        jup_active = jup_aspects_7th
        sat_active = sat_aspects_7th
        double_transit = jup_active and sat_active

        rahu_active = False
        for asp in transits["Rahu"].aspected_sign_indices:
            if asp == seventh_sign_idx:
                rahu_active = True
                break

        return TransitTrigger(
            jupiter_transit_active=jup_active,
            saturn_transit_active=sat_active,
            double_transit_active=double_transit,
            jupiter_aspecting_7th=jup_aspects_7th,
            saturn_aspecting_7th=sat_aspects_7th,
            rahu_transit_active=rahu_active,
            trigger_month=marriage_date.month,
            trigger_year=marriage_date.year
        )

    # ========================================================================
    # LAYER 4: MONTH PREDICTION
    # ========================================================================

    def predict_month(self, year: int) -> List[tuple]:
        from ..core.transits import get_transit_positions

        seventh_sign_idx = SIGNS.index(self.seventh_house_sign)
        months = []

        for month in range(1, 13):
            dt = datetime(year, month, 15)
            transits = get_transit_positions(dt)

            triggers = []

            jup_aspects = any(asp == seventh_sign_idx for asp in transits["Jupiter"].aspected_sign_indices)
            if jup_aspects:
                triggers.append("Jupiter aspects 7th house")

            sat_aspects = any(asp == seventh_sign_idx for asp in transits["Saturn"].aspected_sign_indices)
            if sat_aspects:
                triggers.append("Saturn aspects 7th house")

            rahu_aspects = any(asp == seventh_sign_idx for asp in transits["Rahu"].aspected_sign_indices)
            if rahu_aspects:
                triggers.append("Rahu aspects 7th house")

            if triggers:
                months.append((month, "; ".join(triggers)))

        return months

    def predict_marriage_months(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> List[Dict]:
        from ..core.transits import get_transit_positions

        seventh_sign_idx = SIGNS.index(self.seventh_house_sign)
        months = []
        current = window_start.replace(day=1)

        while current <= window_end:
            transits = get_transit_positions(current)

            trigger_score = 0
            triggers = []

            jup_aspects = any(asp == seventh_sign_idx for asp in transits["Jupiter"].aspected_sign_indices)
            if jup_aspects:
                trigger_score += 2
                triggers.append("Jupiter aspects 7th")

            sat_aspects = any(asp == seventh_sign_idx for asp in transits["Saturn"].aspected_sign_indices)
            if sat_aspects:
                trigger_score += 1
                triggers.append("Saturn aspects 7th")

            rahu_aspects = any(asp == seventh_sign_idx for asp in transits["Rahu"].aspected_sign_indices)
            if rahu_aspects:
                trigger_score += 1
                triggers.append("Rahu aspects 7th")

            if trigger_score >= 2:
                months.append({
                    "date": current,
                    "score": trigger_score,
                    "triggers": triggers
                })

            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return months

    # ========================================================================
    # FULL PREDICTION
    # ========================================================================

    def predict_marriage_timing(
        self,
        current_date=None,
        end_date=None
    ) -> MarriagePrediction:
        if current_date is None:
            current_date = datetime.now()

        promise = self.analyze_natal_promise()
        navamsa = self._confirm_navamsa()

        search_end = datetime(current_date.year + 30, 12, 31)
        windows = self.find_marriage_dashas(
            current_date, search_end, search_from_birth=True
        )

        best_window = None
        for w in windows:
            if w.confidence in [MarriageStrength.VERY_HIGH, MarriageStrength.HIGH]:
                best_window = w
                break
        if not best_window and windows:
            best_window = windows[0]

        earliest_age = None
        latest_age = None
        if windows:
            earliest_age = (windows[0].start_date - self.birth_date).days / 365.25
            latest_age = (windows[-1].end_date - self.birth_date).days / 365.25

        recommendations = self._generate_recommendations(promise, windows)

        return MarriagePrediction(
            promise=promise,
            navamsa=navamsa,
            windows=windows,
            best_window=best_window,
            earliest_marriage_age=earliest_age,
            latest_marriage_age=latest_age,
            predicted_age_range=(earliest_age or 0, latest_age or 0),
            overall_strength=promise.strength,
            recommendations=recommendations,
            upapada=self.upapada
        )

    def _confirm_navamsa(self) -> NavamsaConfirmation:
        d9_seventh_lord = self._get_d9_dignity(self.seventh_lord)
        d9_venus = self._get_d9_dignity("Venus")
        d9_jupiter = self._get_d9_dignity("Jupiter")

        vargottama = False
        if self.seventh_lord in self.d1.planets:
            d1_sign = self.d1.planets[self.seventh_lord].sign
            if self.seventh_lord in self.d9.planets:
                d9_sign = self.d9.planets[self.seventh_lord].d9_sign
                if d1_sign == d9_sign:
                    vargottama = True

        score = 0
        if d9_seventh_lord in ["Exalted", "Own", "Moolatrikona", "Friend"]:
            score += 2
        if d9_venus in ["Exalted", "Own", "Moolatrikona", "Friend"]:
            score += 2
        if d9_jupiter in ["Exalted", "Own", "Moolatrikona", "Friend"]:
            score += 1
        if vargottama:
            score += 2

        if score >= 5:
            strength = MarriageStrength.VERY_HIGH
        elif score >= 3:
            strength = MarriageStrength.HIGH
        elif score >= 1:
            strength = MarriageStrength.MODERATE
        else:
            strength = MarriageStrength.LOW

        return NavamsaConfirmation(
            confirmed=score >= 2,
            d9_7th_lord=self.seventh_lord,
            d9_7th_lord_dignity=d9_seventh_lord,
            d9_venus_dignity=d9_venus,
            d9_jupiter_dignity=d9_jupiter,
            vargottama_7th_lord=vargottama,
            strength=strength
        )

    def confirm_with_navamsa(self) -> NavamsaConfirmation:
        return self._confirm_navamsa()

    def _generate_recommendations(
        self,
        promise: MarriagePromise,
        windows: List[MarriageWindow]
    ) -> List[str]:
        recs = []

        if not promise.promise_exists:
            recs.append("Marriage promise is weak — remedies for 7th house recommended")

        if promise.manglik_dosha:
            recs.append("Manglik Dosha present — Mars remedies recommended")

        if promise.venus_combust:
            recs.append("Venus combust — Venus remedies (Friday fasting, white flowers)")

        if promise.seventh_lord_dignity in ["Debilitated", "Enemy"]:
            recs.append(f"7th lord {promise.seventh_lord} debilitated — strengthening remedies needed")

        if self.upapada:
            if self.upapada.ul_lord_dignity in ["Debilitated", "Enemy"]:
                recs.append(f"UL lord {self.upapada.ul_lord} debilitated — marriage institution challenges")
            if self.upapada.malefics_in_ul2:
                recs.append(f"Malefics in UL2: {', '.join(self.upapada.malefics_in_ul2)} — marriage sustainability concerns")

        if not windows:
            recs.append("No strong marriage dasha windows found — delayed marriage indicated")
        elif len(windows) > 20:
            recs.append("Many dasha windows — narrow down with transit confirmation")

        return recs


def predict_marriage(d1: D1Chart, d9: NavamsaChart, birth_date: datetime) -> MarriagePrediction:
    engine = MarriageTimingEngine(d1, d9, birth_date)
    return engine.predict_marriage_timing(birth_date)


def get_marriage_summary(prediction: MarriagePrediction) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("MARRIAGE TIMING PREDICTION SUMMARY")
    lines.append("=" * 60)

    p = prediction.promise
    lines.append(f"\nNATAL PROMISE: {'YES' if p.promise_exists else 'NO'} ({p.strength.value})")
    lines.append(f"  7th House: {p.seventh_house_sign} (lord {p.seventh_lord} in {p.seventh_lord_house}th)")
    lines.append(f"  Venus: {p.venus_dignity} in {p.venus_house}th" + (" [COMBUST]" if p.venus_combust else ""))
    lines.append(f"  Manglik: {'YES' if p.manglik_dosha else 'NO'}")

    if prediction.upapada:
        ul = prediction.upapada
        lines.append(f"  UL: {ul.ul_sign} (lord {ul.ul_lord} {ul.ul_lord_dignity})")
        lines.append(f"  UL2: {ul.ul2_sign} (lord {ul.ul2_lord} {ul.ul2_lord_dignity})")

    n = prediction.navamsa
    lines.append(f"\nNAVAMSA CONFIRMATION: {'CONFIRMED' if n.confirmed else 'NOT CONFIRMED'}")
    lines.append(f"  D9 7th lord dignity: {n.d9_7th_lord_dignity}")
    lines.append(f"  D9 Venus dignity: {n.d9_venus_dignity}")
    lines.append(f"  Vargottama 7th lord: {'YES' if n.vargottama_7th_lord else 'NO'}")

    lines.append(f"\nWindows: {len(prediction.windows)} found")
    if prediction.best_window:
        w = prediction.best_window
        lines.append(f"  Best: {w.mahadasha_lord}/{w.antardasha_lord}")
        lines.append(f"    Period: {w.start_date.strftime('%Y-%m-%d')} to {w.end_date.strftime('%Y-%m-%d')}")
        lines.append(f"    Confidence: {w.confidence.value}")
        lines.append(f"    Indicators: {[i.value for i in w.indicators]}")

    lines.append(f"\nMarriage Age Range: {prediction.predicted_age_range[0]:.1f} - {prediction.predicted_age_range[1]:.1f} years")

    if prediction.recommendations:
        lines.append("\nRecommendations:")
        for r in prediction.recommendations:
            lines.append(f"  - {r}")

    return "\n".join(lines)
