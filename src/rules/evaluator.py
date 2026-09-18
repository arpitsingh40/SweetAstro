"""
Rule Evaluator Engine.
Evaluates classical rules against natal chart, Navamsa, Dasha state,
transits, and Jaimini parameters at an exact target date.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..core.chart import D1Chart, PlanetState
from ..core.navamsa import NavamsaChart
from ..core.dasha import DashaStateAtDate
from ..core.transits import DoubleTransitResult, TransitPosition, get_transit_positions
from ..core.jaimini import JaiminiKarakas, JaiminiPoints
from ..core.constants import INDEX_TO_SIGN, SIGN_LORDS
from .schema import ClassicalRule, RuleCondition
from .loader import RuleCatalog

logger = logging.getLogger("sweetastro.rules")

# Transit condition entities -> transit planet names
_TRANSIT_ENTITY_MAP = {
    "transit_jupiter": "Jupiter",
    "transit_saturn": "Saturn",
    "transit_rahu": "Rahu",
    "transit_ketu": "Ketu",
}

_DIGNITY_RANK = {
    "Debilitated": 1, "Enemy": 2, "Neutral": 3,
    "Friend": 4, "Own": 5, "Moolatrikona": 6, "Exalted": 7,
}


@dataclass
class RuleActivation:
    rule_id: str
    category: str
    weight: float
    interpretation: str
    book_source: str
    matched_conditions: List[str]


@dataclass
class EvaluationReport:
    target_date: datetime
    matched_rules: List[RuleActivation]
    positive_score: float
    negative_score: float
    net_score: float
    promise_score: float
    delay_score: float
    dasha_score: float
    transit_score: float
    jaimini_score: float
    stability_score: float = 0.0


class RuleEvaluator:
    def __init__(self, catalog: RuleCatalog):
        self.catalog = catalog

    def _check_condition(
        self,
        cond: RuleCondition,
        d1: D1Chart,
        d9: NavamsaChart,
        dasha: Optional[DashaStateAtDate],
        dt_result: Optional[DoubleTransitResult],
        transits: Optional[Dict[str, TransitPosition]],
        karakas: JaiminiKarakas,
        jaimini_pts: JaiminiPoints,
        month: Optional[int] = None,
        is_daytime: Optional[bool] = None,
    ) -> bool:
        c_type = cond.condition_type
        entity = cond.entity

        # Resolve entity object
        planet_obj: Optional[PlanetState] = None
        if entity in d1.planets:
            planet_obj = d1.planets[entity]
        elif entity == "7th_lord":
            planet_obj = d1.seventh_lord
        elif entity == "lagna_lord":
            planet_obj = d1.planets[d1.houses[1].lord]
        elif entity == "darakaraka" and karakas is not None:
            planet_obj = d1.planets.get(karakas.darakaraka)
        elif entity == "atmakaraka" and karakas is not None:
            planet_obj = d1.planets.get(karakas.atmakaraka)

        # 1. in_house
        if c_type == "in_house":
            if entity == "active_dasha_lord":
                if not dasha: return False
                # Check if MD or AD lord is in the specified houses
                md_p = d1.planets.get(dasha.mahadasha)
                ad_p = d1.planets.get(dasha.antardasha)
                target_houses = [int(v) for v in (cond.values or [])]
                md_match = md_p and (md_p.house in target_houses)
                ad_match = ad_p and (ad_p.house in target_houses)
                return bool(md_match or ad_match)
            elif planet_obj:
                target_houses = [int(v) for v in (cond.values or [])]
                return planet_obj.house in target_houses

        # 2. aspects_house
        elif c_type == "aspects_house":
            target_house = int(cond.target or 7)
            if entity == "active_dasha_lord":
                if not dasha: return False
                md_p = d1.planets.get(dasha.mahadasha)
                ad_p = d1.planets.get(dasha.antardasha)
                md_match = md_p and (target_house in md_p.aspecting_houses)
                ad_match = ad_p and (target_house in ad_p.aspecting_houses)
                return bool(md_match or ad_match)
            elif planet_obj:
                return target_house in planet_obj.aspecting_houses

        # 3. dignity_is
        elif c_type == "dignity_is":
            allowed_dignities = cond.values or []
            if entity == "7th_lord_d9":
                d9_7th_lord = d9.seventh_house_lord
                if d9_7th_lord in d9.planets:
                    return d9.planets[d9_7th_lord].d9_dignity in allowed_dignities
                return False
            elif planet_obj:
                return planet_obj.dignity in allowed_dignities
            return False

        # 4. is_combust
        elif c_type == "is_combust":
            if planet_obj:
                return planet_obj.is_combust
            return False

        # 5. is_retrograde
        elif c_type == "is_retrograde":
            if planet_obj:
                return planet_obj.is_retrograde
            return False

        # 6. is_lord_of_house
        elif c_type == "is_lord_of_house":
            target_str = cond.target or "7"
            if target_str == "7_d9":
                target_lord = d9.seventh_house_lord
            elif target_str == "upapada_lagna":
                if jaimini_pts is None:
                    return False
                target_lord = SIGN_LORDS[INDEX_TO_SIGN[jaimini_pts.upapada_lagna_index]]
            else:
                target_lord = d1.houses[int(target_str)].lord

            if entity == "active_dasha_lord":
                if not dasha:
                    return False
                return (dasha.mahadasha == target_lord) or (dasha.antardasha == target_lord)
            if entity == "darakaraka" and karakas is not None:
                return karakas.darakaraka == target_lord
            if entity == "atmakaraka" and karakas is not None:
                return karakas.atmakaraka == target_lord
            resolved = self._resolve_planet_name(d1, entity)
            return resolved is not None and resolved == target_lord

        # 7. dasha_lord_is
        elif c_type == "dasha_lord_is":
            if not dasha: return False
            allowed_lords = cond.values or []
            return (dasha.mahadasha in allowed_lords) or (dasha.antardasha in allowed_lords)

        # 8. jaimini_karaka_is
        elif c_type == "jaimini_karaka_is":
            if not dasha: return False
            target_karaka = cond.target or "DK"
            if target_karaka == "DK":
                dk_planet = karakas.darakaraka
                return (dasha.mahadasha == dk_planet) or (dasha.antardasha == dk_planet)
            elif target_karaka == "AK":
                ak_planet = karakas.atmakaraka
                return (dasha.mahadasha == ak_planet) or (dasha.antardasha == ak_planet)
            return False

        # 9. transit_aspects_house
        elif c_type == "transit_aspects_house":
            target = cond.target or "7"
            if target == "double_transit_marriage_axis":
                return bool(dt_result and dt_result.is_active)
            entity_planet = _TRANSIT_ENTITY_MAP.get(entity)
            if transits and target.isdigit():
                target_sign_idx = d1.houses[int(target)].sign_index
                if entity_planet:
                    return (entity_planet in transits
                            and target_sign_idx in transits[entity_planet].aspected_sign_indices)
                if entity == "transit_system":
                    return any(p in transits and target_sign_idx in transits[p].aspected_sign_indices
                               for p in ("Jupiter", "Saturn"))
            if transits and target == "7_d9_lord":
                lord = d9.seventh_house_lord
                if lord in d1.planets:
                    target_sign_idx = d1.planets[lord].sign_index
                    planet = entity_planet or "Jupiter"
                    return (planet in transits
                            and target_sign_idx in transits[planet].aspected_sign_indices)
            return False

        # 10. aspects_planet (extended: any planet aspects target planet)
        elif c_type == "aspects_planet":
            target_p = self._resolve_planet_name(d1, cond.target or "Venus")
            entity_planet = _TRANSIT_ENTITY_MAP.get(entity)
            if entity == "active_dasha_lord":
                if not dasha or not target_p:
                    return False
                target_house = d1.planets[target_p].house
                for lord in (dasha.mahadasha, dasha.antardasha):
                    lord_state = d1.planets.get(lord)
                    if lord_state and target_house in lord_state.aspecting_houses:
                        return True
                return False
            if entity_planet:
                if transits and entity_planet in transits and target_p:
                    target_sign_idx = d1.planets[target_p].sign_index
                    return target_sign_idx in transits[entity_planet].aspected_sign_indices
                return False
            if planet_obj and target_p:
                return d1.planets[target_p].house in planet_obj.aspecting_houses
            return False

        # 11. has_conjunction
        elif c_type == "has_conjunction":
            if planet_obj:
                conj = d1.houses[planet_obj.house].occupants
                targets = [self._resolve_planet_name(d1, t) for t in (cond.values or [])]
                return any(c in targets for c in conj)
            return False

        # 12. shadbala_is
        elif c_type == "shadbala_is":
            if planet_obj:
                from ..core.shadbala import calculate_shadbala
                try:
                    sb = calculate_shadbala(
                        planet_obj, d1,
                        month=month if month is not None else 6,
                        is_daytime=is_daytime if is_daytime is not None else True,
                    )
                    allowed = cond.values or []
                    return sb.strength_category in allowed
                except Exception:
                    return False
            return False

        # 13. yoga_present
        elif c_type == "yoga_present":
            yoga_name = cond.target or ""
            try:
                from ..core.yogas import detect_yogas
                profile = detect_yogas(d1, d9, karakas)
                return any(y.yoga_name == yoga_name for y in profile.yogas)
            except Exception:
                return False

        # 14. nakshatra_is
        elif c_type == "nakshatra_is":
            if planet_obj:
                allowed = cond.values or []
                return planet_obj.nakshatra in allowed
            return False

        # 15. house_free_of_malefics (e.g. MAR-0009: 7th free of malefic occupation)
        elif c_type == "house_free_of_malefics":
            try:
                target_house = int(cond.target or 7)
            except (TypeError, ValueError):
                return False
            if target_house not in d1.houses:
                return False
            malefics = set(cond.values or ["Saturn", "Mars", "Rahu", "Ketu", "Sun"])
            return not (set(d1.houses[target_house].occupants) & malefics)

        # 16. in_sign
        elif c_type == "in_sign":
            target_signs = [str(v).strip().lower() for v in (cond.values or [])]
            if entity == "active_dasha_lord":
                if not dasha:
                    return False
                states = [d1.planets.get(dasha.mahadasha), d1.planets.get(dasha.antardasha)]
                return any(p and p.sign.lower() in target_signs for p in states)
            return bool(planet_obj and planet_obj.sign.lower() in target_signs)

        # 17. conjunct_with (explicit alias of has_conjunction)
        elif c_type == "conjunct_with":
            if planet_obj:
                conj = d1.houses[planet_obj.house].occupants
                targets = [self._resolve_planet_name(d1, t) for t in (cond.values or [])]
                return any(c in targets for c in conj)
            return False

        # 18. dignity_at_least (values[0] = minimum dignity, e.g. "Friend")
        elif c_type == "dignity_at_least":
            threshold = str((cond.values or ["Friend"])[0])
            min_rank = _DIGNITY_RANK.get(threshold, 4)
            if planet_obj:
                return _DIGNITY_RANK.get(planet_obj.dignity, 0) >= min_rank
            return False

        # 19. transit_in_house
        elif c_type == "transit_in_house":
            entity_planet = _TRANSIT_ENTITY_MAP.get(entity)
            if entity_planet and transits and cond.target and str(cond.target).isdigit():
                target_house = int(cond.target)
                if target_house in d1.houses:
                    return transits[entity_planet].sign_index == d1.houses[target_house].sign_index
            return False

        else:
            logger.warning("Unsupported rule condition type %r (entity=%r) — treated as unmet",
                           c_type, entity)

        return False

    @staticmethod
    def _resolve_planet_name(d1: D1Chart, name: Optional[str]) -> Optional[str]:
        """Resolves planet aliases used in rule targets (7th_lord, lagna_lord)."""
        if not name:
            return None
        if name in d1.planets:
            return name
        if name == "7th_lord":
            return d1.houses[7].lord
        if name == "lagna_lord":
            return d1.houses[1].lord
        return None

    def evaluate(
        self,
        d1: D1Chart,
        d9: NavamsaChart,
        karakas: JaiminiKarakas,
        jaimini_pts: JaiminiPoints,
        target_date: datetime,
        dasha: Optional[DashaStateAtDate] = None,
        dt_result: Optional[DoubleTransitResult] = None,
        transits: Optional[Dict[str, TransitPosition]] = None,
        month: Optional[int] = None,
        is_daytime: Optional[bool] = None,
    ) -> EvaluationReport:
        """
        Evaluates all catalog rules for the given chart and target date.
        """
        matched_rules: List[RuleActivation] = []
        pos_score = 0.0
        neg_score = 0.0

        promise_score = 0.0
        delay_score = 0.0
        dasha_score = 0.0
        transit_score = 0.0
        jaimini_score = 0.0
        stability_score = 0.0

        for r_id, rule in self.catalog.rules.items():
            if rule.exception_conditions and any(
                self._check_condition(exc, d1, d9, dasha, dt_result, transits,
                                      karakas, jaimini_pts, month, is_daytime)
                for exc in rule.exception_conditions
            ):
                continue

            all_conditions_met = True
            matched_cond_descs = []

            for cond in rule.conditions:
                met = self._check_condition(
                    cond, d1, d9, dasha, dt_result, transits, karakas, jaimini_pts,
                    month, is_daytime,
                )
                if not met:
                    all_conditions_met = False
                    break
                matched_cond_descs.append(f"{cond.entity} {cond.condition_type}")

            if all_conditions_met and rule.conditions:
                act = RuleActivation(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    weight=rule.base_weight,
                    interpretation=rule.interpretation,
                    book_source=f"{rule.source.book} Ch.{rule.source.chapter}:{rule.source.verse}",
                    matched_conditions=matched_cond_descs
                )
                matched_rules.append(act)

                if rule.base_weight >= 0:
                    pos_score += rule.base_weight
                else:
                    neg_score += abs(rule.base_weight)

                # Category breakdown
                if rule.category == "promise":
                    promise_score += rule.base_weight
                elif rule.category == "delay":
                    delay_score += abs(rule.base_weight)
                elif rule.category == "timing_dasha":
                    dasha_score += rule.base_weight
                elif rule.category == "timing_transit":
                    transit_score += rule.base_weight
                elif rule.category == "jaimini":
                    jaimini_score += rule.base_weight
                elif rule.category == "stability":
                    stability_score += rule.base_weight

        net_score = max(0.0, pos_score - neg_score)

        return EvaluationReport(
            target_date=target_date,
            matched_rules=matched_rules,
            positive_score=pos_score,
            negative_score=neg_score,
            net_score=net_score,
            promise_score=promise_score,
            delay_score=delay_score,
            dasha_score=dasha_score,
            transit_score=transit_score,
            jaimini_score=jaimini_score,
            stability_score=stability_score,
        )
