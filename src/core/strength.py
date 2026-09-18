"""
Improved Planet Strength Assessment — Consumer Engine Sec 4.
Now integrates Shadbala, Yogas, combustion severity, and aspector chain.

Evaluates the complete chain (never from one placement):
Planet -> house -> sign -> lordship -> dispositor -> Nakshatra lord ->
conjunction -> aspects -> dignities -> Shadbala -> Yogas ->
varga -> Dasha -> transit -> remedy suitability.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .chart import D1Chart
from .constants import NATURAL_BENEFICS, NATURAL_MALEFICS, SIGN_LORDS, OWN_SIGNS, EXALTATION_DATA, DEBILITATION_DATA, COMBUSTION_ORBS
from .vargas import VargaChart
from .planet_factors import PlanetFactors, compute_planet_factors
from .classical_shadbala import ClassicalShadbala, calculate_classical_shadbala
from .sensitive_points import sensitive_placement
from .shadbala import calculate_shadbala, ShadbalaScore
from .yogas import detect_yogas, YogaProfile


@dataclass
class StrengthAssessment:
    planet: str
    functional_lordship: List[int]
    sign: str
    sign_dignity: str
    house: int
    natural_nature: str
    conjunctions: List[str]
    aspects_received_from: List[str]
    dispositor: str
    dispositor_dignity: str
    nakshatra: str
    nakshatra_pada: int
    nakshatra_lord: str
    vargottama: bool
    varga_dignities: Dict[str, str]
    relation_with_lagna_lord: str
    relation_with_relevant_lords: Dict[str, str]
    afflicted: bool
    affliction_reasons: List[str]
    recommendation: str
    recommendation_reason: str
    shadbala: Optional[Dict[str, float]]
    yogas: List[str]
    qualitative_model_note: str = ""
    compound_friendship: Dict[str, str] = field(default_factory=dict)
    avasthas: Dict[str, str] = field(default_factory=dict)
    sandhi: bool = False
    gandanta: bool = False
    bav_bindus: Optional[int] = None
    graha_yuddha: Optional[str] = None
    parivartana: List[str] = field(default_factory=list)
    classical_shadbala: Optional[Dict[str, float]] = None
    sensitive: Optional[str] = None


def _houses_owned(d1: D1Chart, planet: str) -> List[int]:
    owned = []
    for h, hs in d1.houses.items():
        if hs.lord == planet:
            owned.append(h)
    return sorted(owned)


def _relation(p1: str, p2: str) -> str:
    if p1 == p2:
        return "Self"
    from .constants import PERMANENT_FRIENDSHIPS
    fr = PERMANENT_FRIENDSHIPS.get(p1, {})
    if p2 in fr.get("friends", []):
        return "Friend"
    if p2 in fr.get("enemies", []):
        return "Enemy"
    return "Neutral"


def _combustion_severity(planet: str, d1: D1Chart) -> Tuple[str, float]:
    """Returns (severity_level, severity_score)."""
    if planet in ["Sun", "Rahu", "Ketu"]:
        return "none", 0.0
    ps = d1.planets[planet]
    sun_lon = d1.planets["Sun"].longitude
    diff = abs((ps.longitude - sun_lon + 180.0) % 360.0 - 180.0)
    orb = COMBUSTION_ORBS.get(planet, 12.0)
    if planet in ("Mercury", "Venus") and ps.is_retrograde:
        orb = 12.0 if planet == "Mercury" else 8.0
    if diff <= orb * 0.5:
        return "severe", 1.0
    elif diff <= orb:
        return "moderate", 0.5
    return "none", 0.0


def assess_planet_strength(
    d1: D1Chart,
    planet: str,
    vargas: Optional[Dict[str, VargaChart]] = None,
    relevant_house_lords: Optional[List[str]] = None,
    month: int = 6,
    is_daytime: bool = True,
    birth_dt: Optional["datetime"] = None,
    classical: bool = False,
    tz_offset: float = 5.5,
) -> StrengthAssessment:
    if planet not in d1.planets:
        raise ValueError(f"Unknown planet: {planet}")
    ps = d1.planets[planet]
    lagna_lord = d1.houses[1].lord
    conjunctions = [o for o in d1.houses[ps.house].occupants if o != planet]
    received = [p for p, q in d1.planets.items()
                if ps.house in q.aspecting_houses and p != planet]
    dispositor = SIGN_LORDS[ps.sign]
    disp_dignity = d1.planets[dispositor].dignity if dispositor in d1.planets else "Unknown"

    vargottama = False
    varga_dignities: Dict[str, str] = {}
    if vargas:
        for vname, vc in vargas.items():
            if planet in vc.planets:
                vps = vc.planets[planet]
                varga_dignities[vname] = vps.varga_dignity
                if vname == "D9":
                    vargottama = vps.is_vargottama

    nature = "Benefic" if planet in NATURAL_BENEFICS else ("Malefic" if planet in NATURAL_MALEFICS else "Neutral")
    rel_lagna = _relation(planet, lagna_lord)
    rel_map: Dict[str, str] = {}
    for lord in (relevant_house_lords or []):
        if lord in d1.planets:
            rel_map[lord] = _relation(planet, lord)

    reasons: List[str] = []
    combust_severity, _ = _combustion_severity(planet, d1)
    if ps.is_combust:
        if combust_severity == "severe":
            reasons.append("severely combust (very close to Sun)")
        else:
            reasons.append("combust (close to Sun)")
    if ps.dignity == "Debilitated" and not vargottama:
        reasons.append("debilitated in D1 without Vargottama support")
    malefic_conj = [c for c in conjunctions if c in NATURAL_MALEFICS]
    if malefic_conj:
        reasons.append(f"conjunct malefic(s): {', '.join(malefic_conj)}")
    malefic_asp = [a for a in received if a in ("Saturn", "Mars", "Rahu", "Ketu")]
    if malefic_asp:
        reasons.append(f"aspected by malefic(s): {', '.join(malefic_asp)}")
    if disp_dignity in ("Debilitated", "Enemy"):
        reasons.append(f"dispositor {dispositor} is {disp_dignity}")
    if ps.is_retrograde and planet in ("Saturn", "Mars"):
        reasons.append("retrograde malefic — intensified/uneven expression")

    factors: Optional[PlanetFactors] = None
    try:
        factors = compute_planet_factors(d1, planet)
    except Exception:
        factors = None
    if factors is not None:
        if factors.sandhi:
            reasons.append("in sign sandhi (junction degree — weak)")
        if factors.gandanta:
            reasons.append("in gandanta (water–fire junction)")
        if factors.yuddha and "lost" in factors.yuddha:
            reasons.append(factors.yuddha)
        if factors.bav_bindus is not None and factors.bav_bindus < 4:
            reasons.append(f"low Ashtakavarga bindus in its sign ({factors.bav_bindus}/8)")
    afflicted = len(reasons) > 0

    lordship = _houses_owned(d1, planet)
    owns_dusthana = any(h in (6, 8, 12) for h in lordship)
    owns_kendra_trikona = any(h in (1, 4, 5, 7, 9, 10) for h in lordship)

    yogas: List[str] = []
    try:
        yoga_profile = detect_yogas(d1, None, None)
        yogas = [y.yoga_name for y in yoga_profile.yogas if y.planet == planet]
    except Exception:
        pass

    shadbala: Optional[Dict[str, float]] = None
    try:
        sb = calculate_shadbala(ps, d1, month=month, is_daytime=is_daytime)
        shadbala = {
            "total": sb.total_bala,
            "category": sb.strength_category,
            "sthana": sb.sthanabala,
            "dig": sb.digbala,
            "ksepa": sb.ksepanabala,
            "debana": sb.debanalibala,
            "ayana": sb.ayanalibala,
            "vayana": sb.vayanalibala,
        }
    except Exception:
        pass

    if planet in ("Rahu", "Ketu"):
        recommendation = "balance"
        reason = (f"{planet} is a shadow graha; default is channel/pacify, not blind strengthening.")
    elif owns_dusthana and not owns_kendra_trikona and afflicted:
        recommendation = "pacify"
        reason = (f"{planet} owns dusthana house(s) {lordship} without kendra/trikona ownership "
                  "and shows affliction; strengthening could intensify difficult results.")
    elif afflicted and disp_dignity in ("Debilitated", "Enemy"):
        recommendation = "balance"
        reason = (f"{planet} is afflicted and dispositor {dispositor} is weak; "
                  "stabilise through conduct/service before strengthening.")
    elif ps.dignity in ("Debilitated", "Enemy") and owns_kendra_trikona:
        recommendation = "balance"
        reason = (f"{planet} owns supportive houses {lordship} but is dignity-weak; "
                  "prefer steady alignment.")
    elif ps.dignity in ("Exalted", "Moolatrikona", "Own") and not afflicted:
        recommendation = "leave-alone"
        reason = (f"{planet} is dignified ({ps.dignity}) and unafflicted; no strengthening needed.")
    elif not afflicted and rel_lagna in ("Friend", "Self"):
        recommendation = "strengthen"
        reason = (f"{planet} is friendly to Lagna lord {lagna_lord}, unafflicted, relevant — "
                  "gentle strengthening is suitable.")
    else:
        recommendation = "balance"
        reason = "Mixed indications; default to balanced alignment."

    if yogas:
        reason += f" Yogas: {', '.join(yogas)}."
    if shadbala:
        reason += (f" Strength index (SweetAstro analytical model, not classical Shadbala): "
                   f"{shadbala['category']} ({shadbala['total']}/360).")
    if factors is not None and factors.bav_bindus is not None and factors.bav_bindus >= 5:
        reason += f" Strong own-sign Ashtakavarga support ({factors.bav_bindus}/8 bindus)."

    classical_data: Optional[Dict[str, float]] = None
    sensitive_note: Optional[str] = None
    if classical:
        try:
            weekday = birth_dt.weekday() if birth_dt else 0
            hour_local = ((birth_dt.hour + birth_dt.minute / 60.0)
                          if birth_dt else 12.0)
            sun = d1.planets["Sun"].longitude
            moon = d1.planets["Moon"].longitude
            elongation = (moon - sun) % 360.0
            if elongation > 180.0:
                elongation = 360.0 - elongation
            vm_lords = None
            if birth_dt is not None:
                from .strength_extras import varsha_masa_lords
                vm_lords = varsha_masa_lords(birth_dt, tz_offset, sun)
            cb = calculate_classical_shadbala(
                d1, planet, is_daytime=is_daytime, hour_local=hour_local,
                weekday=weekday, sun_moon_elongation=elongation,
                varsha_lord=vm_lords.get("varsha_lord") if vm_lords else None,
                masa_lord=vm_lords.get("masa_lord") if vm_lords else None,
            )
            classical_data = {
                "rupas": cb.total_rupas, "minimum": cb.minimum_rupas,
                "ratio": cb.ratio, "category": cb.category,
                "ishta": cb.ishta_phala, "kashta": cb.kashta_phala,
                "sthana": cb.sthana, "dig": cb.dig, "kala": cb.kala,
                "chesta": cb.chesta, "naisargika": cb.naisargika, "drik": cb.drik,
                "varsha_lord": (vm_lords or {}).get("varsha_lord"),
                "masa_lord": (vm_lords or {}).get("masa_lord"),
            }
            sp = sensitive_placement(d1, planet)
            sensitive_note = sp.to_note() or None
        except Exception:
            classical_data = None
            sensitive_note = None

    return StrengthAssessment(
        planet=planet, functional_lordship=lordship, sign=ps.sign,
        sign_dignity=ps.dignity, house=ps.house, natural_nature=nature,
        conjunctions=conjunctions, aspects_received_from=received,
        dispositor=dispositor, dispositor_dignity=disp_dignity,
        nakshatra=ps.nakshatra, nakshatra_pada=ps.nakshatra_pada,
        nakshatra_lord=ps.nakshatra_lord, vargottama=vargottama,
        varga_dignities=varga_dignities, relation_with_lagna_lord=rel_lagna,
        relation_with_relevant_lords=rel_map, afflicted=afflicted,
        affliction_reasons=reasons, recommendation=recommendation,
        recommendation_reason=reason, shadbala=shadbala, yogas=yogas,
        compound_friendship=dict(factors.compound) if factors else {},
        avasthas=({
            "baladi": factors.baladi,
            "jagradadi": factors.jagradadi,
            "deeptadi": factors.deeptadi,
        } if factors else {}),
        sandhi=bool(factors and factors.sandhi),
        gandanta=bool(factors and factors.gandanta),
        bav_bindus=factors.bav_bindus if factors else None,
        graha_yuddha=factors.yuddha if factors else None,
        parivartana=list(factors.parivartana) if factors else [],
        classical_shadbala=classical_data,
        sensitive=sensitive_note,
    )