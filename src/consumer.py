"""
Consumer Orchestrator — wires calculation -> interpretation -> remedies -> answer.

Covers Sec 1-16 end-to-end for ANY question (not just marriage):
- validates birth data, reduces confidence when time uncertain
- full-chain strength (Sec 4), varga relevance (Sec 3), Rahu/Ketu (Sec 8)
- money split (Sec 7), dasha separation (Sec 5), structured predictions (Sec 6)
- remedy framework + gemstone gate + safety (Sec 9/10/11)
- calibrated consumer format (Sec 12/13/16), backtest mode (Sec 14), no generics (Sec 15)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .core.arudha import UpapadaAnalysis, calculate_upapada
from .core.ashtakavarga import (
    AshtakavargaResult, calculate_ashtakavarga, house_support_label, transit_bindu_note,
)
from .core.chart import calculate_d1_chart, D1Chart
from .core.ephemeris import ephemeris_engine_name, ephemeris_data_source
from .core.keywords import matches_any
from .core.navamsa import calculate_navamsa_chart
from .core.jaimini import JaiminiKarakas, JaiminiPoints, calculate_chara_karakas, calculate_jaimini_points
from .core.dasha import (
    DashaPeriod, DeepDashaState, calculate_vimshottari_timeline, get_dasha_at_date,
    get_deep_dasha_at_date, upcoming_periods,
)
from .core.nakshatra import NatalPanchanga, compute_natal_panchanga
from .core.transits import GocharaReading, evaluate_double_transit, evaluate_gochara
from .core.time_sensitivity import TimeStability, assess_birth_time_stability
from .core.vargas import select_vargas, calculate_varga_chart, VargaChart
from .core.varga_matrix import FullVargaMatrix, calculate_full_varga_matrix
from .core.varshaphala import VarshaphalaReading, compute_varshaphala
from .core.strength import assess_planet_strength, StrengthAssessment
from .core.rahu_ketu import NodeAnalysis, analyze_node
from .core.yogas import YogaProfile, detect_yogas
from .interpretation.money import analyse_money
from .interpretation.dasha_timing import read_timing, TimingReading
from .interpretation.prediction_logic import Prediction, calibrate_confidence, safe_statement
from .interpretation.promise import PromiseAssessment, assess_promise
from .remedies.catalog import (
    Remedy, alignment_remedy, mantra_remedy, donation_remedy,
    modern_conduct_remedy, reference_remedy,
)
from .remedies.gemstone import evaluate_gemstone, format_gemstone_note
from .remedies.kat import kat_alignment_for_topic, format_kat_line
from .remedies.period import format_period_line, period_alignment
from .llm.consumer_answer_engine import ConsumerAnswer, ConsumerAnswerBuilder

# Topic -> relevant houses + significators
TOPIC_HOUSES = {
    "wealth": [2, 5, 6, 8, 10, 11, 12],
    "career": [6, 7, 10, 11],
    "business": [3, 7, 10, 11],
    "marriage": [1, 2, 5, 7, 8, 12],
    "children": [1, 5, 7, 9],
    "property": [1, 4, 8, 11],
    "education": [2, 4, 5, 9],
    "siblings": [1, 3, 11],
    "health": [1, 6, 8, 12],
    "spirituality": [1, 5, 9, 12],
    "compatibility": [1, 2, 5, 7, 12],
    "personality": [1, 2, 3, 5, 9, 10],
    "general": [1, 5, 9, 10],
}

TOPIC_SIGNIFICATORS = {
    "wealth": ["Jupiter", "Venus", "Mercury"],
    "career": ["Saturn", "Sun", "Mercury"],
    "business": ["Mercury", "Saturn", "Sun"],
    "marriage": ["Venus", "Jupiter"],
    "children": ["Jupiter"],
    "property": ["Mars", "Saturn", "Moon"],
    "education": ["Mercury", "Jupiter"],
    "siblings": ["Mars"],
    "health": ["Moon", "Saturn", "Mars"],
    "spirituality": ["Ketu", "Jupiter"],
    "compatibility": ["Venus", "Moon", "Jupiter"],
    "personality": ["Sun", "Moon", "Mercury", "Jupiter"],
    "general": ["Jupiter"],
}


# Fallback keywords when the topic word itself is absent (word-boundary match;
# "ill" must not fire inside "will" — audit finding).
_TOPIC_KEYWORDS = [
    ("wealth", ["money", "income", "finance", "financial", "rich", "debt", "gain", "invest"]),
    ("career", ["job", "profession", "promotion", "work"]),
    ("marriage", ["wife", "husband", "partner", "divorce", "wedding", "marry",
                  "married", "marriage", "shaadi", "shadi", "vivah"]),
    ("children", ["child", "baby", "pregnan"]),
    ("property", ["house", "land", "flat", "plot", "vehicle", "property"]),
    ("education", ["study", "exam", "degree", "school", "college", "education"]),
    ("siblings", ["brother", "sister", "siblings"]),
    ("health", ["disease", "ill", "surgery", "health", "legal", "enemy", "court"]),
    ("spirituality", ["moksha", "sadhana", "meditat", "spirituality", "spiritual"]),
    ("personality", ["personality", "character", "swabhav", "swabhava", "my strengths"]),
]


def _topic_key(question: str) -> str:
    q = (question or "").lower()
    for topic in TOPIC_HOUSES:
        if matches_any(q, [topic]):
            return topic
    for topic, words in _TOPIC_KEYWORDS:
        if matches_any(q, words):
            return topic
    return "general"


@dataclass
class ConsumerResult:
    answer: ConsumerAnswer
    d1: D1Chart
    vargas: Dict[str, VargaChart]
    strengths: Dict[str, StrengthAssessment]
    timing: TimingReading
    topic: str
    gochara: Optional[GocharaReading] = None
    ashtakavarga: Optional[AshtakavargaResult] = None
    panchanga: Optional[NatalPanchanga] = None
    varshaphala: Optional[VarshaphalaReading] = None
    promise: Optional[PromiseAssessment] = None
    stability: Optional[TimeStability] = None
    deep_dasha: Optional[DeepDashaState] = None
    upcoming: List[DashaPeriod] = field(default_factory=list)
    yogas: Optional[YogaProfile] = None
    nodes: Dict[str, NodeAnalysis] = field(default_factory=dict)
    karakas: Optional[JaiminiKarakas] = None
    jaimini: Optional[JaiminiPoints] = None
    upapada: Optional[UpapadaAnalysis] = None
    full_varga_matrix: Optional[FullVargaMatrix] = None


def answer_question(*, year: int, month: int, day: int, hour: int, minute: int,
                    second: float = 0.0, tz_offset: float = 5.5,
                    lat: float = 28.6139, lon: float = 77.2090,
                    place: str = "", question: str = "general",
                    time_reliable: bool = True,
                    query_dt: Optional[datetime] = None,
                    historical_events: Optional[List[Dict]] = None,
                    full_matrix: bool = False,
                    deep_planets: bool = False) -> ConsumerResult:
    """
    Main Consumer Engine entry point.
    - Never guesses positions: all longitudes come from the deterministic chart engine.
    - Reduces confidence + gates fine vargas/remedies when time_reliable=False.
    - full_matrix=True computes all 23 supported vargas x all 9 grahas
      (deep-dive/lookup reference; used by the chat lookup mode).
    - deep_planets=True assesses every physical graha through the full strength
      chain (deep mode / full report) instead of the topic focus set.
    """
    topic = _topic_key(question)
    relevant_houses = TOPIC_HOUSES[topic]
    # Transits are computed in UT; use UTC "now" when no explicit query time.
    query_dt = query_dt or datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Calculate + validate (Sec 1)
    d1 = calculate_d1_chart(year, month, day, hour, minute, second, tz_offset, lat, lon)
    birth_dt = datetime(year, month, day, hour, minute, int(second))
    moon_lon = d1.planets["Moon"].longitude
    timeline = calculate_vimshottari_timeline(birth_dt, moon_lon)

    varga_names, varga_note = select_vargas(question, time_reliable)
    vargas: Dict[str, VargaChart] = {}
    for v in varga_names:
        try:
            vargas[v] = calculate_varga_chart(d1, v)
        except Exception:
            continue
    full_varga_matrix = calculate_full_varga_matrix(d1) if full_matrix else None

    # 2. Focus planets: house lords + significators (Sec 2: never one placement)
    lagna_lord = d1.houses[1].lord
    focus: List[str] = []
    for h in relevant_houses[:4]:
        lord = d1.houses[h].lord
        if lord not in focus:
            focus.append(lord)
    for sig in TOPIC_SIGNIFICATORS[topic]:
        if sig not in focus:
            focus.append(sig)
    if lagna_lord not in focus:
        focus.append(lagna_lord)
    focus = focus[:5]
    if deep_planets:
        # Deep mode: assess every physical graha through the full chain.
        # Topic-relevant planets stay first so remedies/alignment keep their
        # topical primary; Rahu/Ketu are covered by the full node analysis.
        from .core.constants import PHYSICAL_PLANETS
        focus = list(dict.fromkeys(focus + PHYSICAL_PLANETS))

    relevant_lords = [d1.houses[h].lord for h in relevant_houses]
    birth_month = birth_dt.month
    is_daytime = (6 <= hour < 18)
    strengths: Dict[str, StrengthAssessment] = {}
    for p in focus:
        try:
            strengths[p] = assess_planet_strength(
                d1, p, vargas, relevant_lords,
                month=birth_month, is_daytime=is_daytime,
                birth_dt=birth_dt, classical=deep_planets, tz_offset=tz_offset,
            )
        except Exception:
            continue

    # 3. Rahu/Ketu when relevant (wealth/career/spirituality/general or nodes in focus houses)
    node_notes: List[str] = []
    node_analyses: Dict[str, NodeAnalysis] = {}
    for node in ("Rahu", "Ketu"):
        try:
            na = analyze_node(d1, node, vargas, time_reliable)
            node_analyses[node] = na
            if topic in ("wealth", "career", "business", "spirituality", "general") or \
               d1.planets[node].house in relevant_houses:
                node_notes.append(f"{node} in {na.house}H/{na.sign} (lord {na.sign_lord} in {na.dispositor_house}H, "
                                  f"Nak {na.nakshatra}-Pada{na.nakshatra_pada}/{na.nakshatra_lord}): {na.where_instability}")
        except Exception:
            continue

    # 4. Timing separation (Sec 5) — marriage axis only for marriage; else generic transit positions
    from .core.transits import get_transit_positions
    try:
        if topic == "marriage":
            dt_res = evaluate_double_transit(d1, query_dt)
            transit_note = dt_res.description
            transit_supports = dt_res.is_active or dt_res.total_transit_score >= 30
        else:
            tp = get_transit_positions(query_dt)
            transit_note = ("Current transits: Jupiter in "
                            f"{tp['Jupiter'].sign}, Saturn in {tp['Saturn'].sign}, "
                            f"Rahu/Ketu in {tp['Rahu'].sign}/{tp['Ketu'].sign}. "
                            "Used only as scheduling support.")
            # Generic support: Jupiter/Saturn aspecting any relevant house sign
            rel_signs = {d1.houses[h].sign_index for h in relevant_houses}
            j_sup = bool(rel_signs & set(tp["Jupiter"].aspected_sign_indices))
            s_sup = bool(rel_signs & set(tp["Saturn"].aspected_sign_indices))
            transit_supports = bool(j_sup and s_sup)
    except Exception:
        transit_note, transit_supports = "Transit check unavailable.", False
    timing = read_timing(d1, timeline, query_dt, relevant_houses, transit_note)

    # 5. Structured predictions (Sec 6) — one per focus planet (cap 3), each with confirmations
    from .core.dasha import get_dasha_at_date
    dasha_state = get_dasha_at_date(timeline, query_dt)
    md_ad = f"{timing.current_md_ad_pd}" if timing else ""
    predictions: List[Prediction] = []
    for p in list(strengths.keys())[:3]:
        sa = strengths[p]
        # Natal evidence classes (timing is counted separately, never double-counted).
        natal_names: List[str] = []
        if sa.sign_dignity in ("Exalted", "Moolatrikona", "Own", "Friend"):
            natal_names.append("dignity")
        if sa.dispositor_dignity in ("Exalted", "Moolatrikona", "Own", "Friend"):
            natal_names.append("dispositor")
        if any(v == sa.sign_dignity or v in ("Exalted", "Own") for v in sa.varga_dignities.values()):
            natal_names.append("varga")
        if sa.house in relevant_houses or any(h in relevant_houses for h in sa.functional_lordship):
            natal_names.append("house-lordship")
        natal_factors = len(natal_names)
        dasha_sup = bool(dasha_state and (dasha_state.mahadasha == p or dasha_state.antardasha == p))
        strength_lbl = ("Strong" if natal_factors + int(dasha_sup) >= 4 else
                        "Moderate" if natal_factors + int(dasha_sup) >= 2 else "Weak")
        conf = calibrate_confidence(natal_factors, time_reliable, dasha_sup, transit_supports)
        houses_owned = ",".join(str(h) for h in sa.functional_lordship) or "—"
        signal = (f"{p} owns {houses_owned}H, sits in {sa.house}H/{sa.sign} ({sa.sign_dignity}), "
                  f"Nak {sa.nakshatra}-P{sa.nakshatra_pada} ({sa.nakshatra_lord}), dispositor {sa.dispositor} ({sa.dispositor_dignity}); "
                  f"vargas {', '.join(f'{k}:{v}' for k, v in list(sa.varga_dignities.items())[:3]) or 'D1 only'}.")
        mechanism = (f"{p} connects to the question via {'house placement' if sa.house in relevant_houses else ''} "
                     f"{'lordship of ' + houses_owned if any(h in relevant_houses for h in sa.functional_lordship) else ''} "
                     f"and dispositor/Nakshatra links ({sa.dispositor}/{sa.nakshatra_lord}).")
        stmt = safe_statement(topic, strength_lbl, f"during {md_ad}", "steady effort and supporting conditions continue")
        natal_txt = ", ".join(natal_names) if natal_names else "none"
        predictions.append(Prediction(
            topic=f"{topic} via {p}", signal=signal, mechanism=mechanism.strip(),
            timing=f"MD/AD/PD {md_ad}; {transit_note}",
            strength=strength_lbl,
            risk=("Dasha shift, malefic pressure, or overextension could delay/reverse; " +
                  ("afflictions: " + "; ".join(sa.affliction_reasons) if sa.afflicted else "no major affliction noted.")),
            confidence=conf,
            confidence_reason=(f"{natal_factors}/4 natal evidence checks support ({natal_txt}); "
                               f"Dasha {'supports' if dasha_sup else 'is indirect'}; "
                               f"transits {'support' if transit_supports else 'are neutral'}; "
                               f"birth time {'reliable' if time_reliable else 'uncertain (reduced confidence)'}." +
                               (" Vargottama adds stability." if sa.vargottama else "")),
            statement=stmt,
        ))

    # Money split when relevant (Sec 7) — consumer summary only (detail stays in key factors)
    money_summary = ""
    if topic in ("wealth", "business"):
        mb = analyse_money(d1, for_business=(topic == "business"))
        h2 = d1.houses[2]; h11 = d1.houses[11]; h10 = d1.houses[10]
        money_summary = (f"Wealth lens: 2nd lord {h2.lord} in {d1.planets[h2.lord].house}H, "
                         f"11th lord {h11.lord} in {d1.planets[h11.lord].house}H, "
                         f"10th lord {h10.lord} in {d1.planets[h10.lord].house}H. "
                         f"{mb.discipline_first_note[:140]}")

    # 6. Key factors (3-5, chart-specific, Sec 15: never generic)
    key_factors: List[str] = []
    for p in list(strengths.keys())[:3]:
        sa = strengths[p]
        key_factors.append(
            f"{p} (lord of {','.join(str(h) for h in sa.functional_lordship) or '—'}H) in {sa.house}H/{sa.sign} "
            f"as {sa.sign_dignity}, Nak {sa.nakshatra} Pada {sa.nakshatra_pada} ({sa.nakshatra_lord}), "
            f"dispositor {sa.dispositor} ({sa.dispositor_dignity})"
            + (", Vargottama" if sa.vargottama else "")
            + (f"; afflicted: {'; '.join(sa.affliction_reasons)}" if sa.afflicted else "; unafflicted")
            + f" — recommendation: {sa.recommendation}."
        )
    key_factors.append(f"Varga confirmation: {varga_note} Dasha now {md_ad}.")
    if node_notes:
        key_factors.append(node_notes[0])
    key_factors = key_factors[:5]

    # 7. Bottom line (3-5 sentences, calibrated)
    best = predictions[0] if predictions else None
    if best:
        bottom_line = (f"{best.statement} {best.confidence_reason} "
                       f"The strongest thread runs through {best.topic}. {money_summary[:260]} "
                       f"Birth-time reliability: {'good — house/varga use is reasonable' if time_reliable else 'limited — houses and fine vargas carry low confidence'}.").strip()
    else:
        bottom_line = ("The chart suggests a mixed picture for this question; no single strong thread dominates, "
                       "so timing and remedies stay conservative.")

    # 8. Opportunity / Risk
    opportunity = ("Take advantage of steady, rule-based effort in the significations of "
                   + ", ".join(list(strengths.keys())[:3]) + f" while {md_ad} is active. "
                   + ("Wealth lens: build via 2nd/11th (save/gain) and 10th (profession) rather than 5th speculation. " if topic in ("wealth", "business") else "")
                   + transit_note)
    risk = ("Avoid forcing outcomes from one placement; " +
            ("noted afflictions: " + "; ".join(sum([s.affliction_reasons for s in strengths.values()], []))[:300] if any(s.afflicted for s in strengths.values()) else "no single major affliction dominates") +
            ". Overleverage, rushed commitments, or transit-only timing are the main reversers.")

    # 9. Alignment (Sec 9)
    primary_planet = list(strengths.keys())[0] if strengths else lagna_lord
    alignment_title = f"Develop {primary_planet}-linked qualities through practical conduct (continuous, no cost)."
    alignment_actions = []
    for p in list(strengths.keys())[:2]:
        from .remedies.catalog import PLANET_ALIGNMENT, PLANET_WEEKDAY
        alignment_actions.append(f"{p} ({PLANET_WEEKDAY.get(p, '')}): {PLANET_ALIGNMENT.get(p, 'balanced conduct')}.")
    if node_notes:
        alignment_actions.append("Nodes: keep methods transparent; avoid shortcuts and abrupt exits.")
    obstructing_planet = next(
        (p for p, sa in strengths.items() if sa.recommendation in ("pacify", "balance")), None)
    kat = kat_alignment_for_topic(topic, obstructing_planet)
    if kat:
        alignment_actions.append(format_kat_line(kat))

    # 10. Remedies — chart-specific, proportionate, max 3 (Sec 9)
    remedies: List[Remedy] = []
    if strengths:
        sa0 = strengths[primary_planet]
        reason0 = (f"{primary_planet} is the lead thread ({sa0.house}H/{sa0.sign}, {sa0.sign_dignity}, lord of {sa0.functional_lordship}); "
                   f"assessment says '{sa0.recommendation}' — {sa0.recommendation_reason[:160]}")
        remedies.append(alignment_remedy(primary_planet, reason0, "High"))
        # Supporting: mantra OR donation depending on recommendation
        if sa0.recommendation in ("balance", "pacify"):
            remedies.append(mantra_remedy(primary_planet, f"Pacifying support for {primary_planet} pressure shown by " +
                                           ("; ".join(sa0.affliction_reasons)[:150] if sa0.afflicted else "mixed dignity"), "Moderate"))
        else:
            remedies.append(donation_remedy(primary_planet, f"Service to stabilise {primary_planet} gains without transactional expectation.", "Moderate"))
        # Third: practical conduct support ONLY if time reliable + house reliable + safe.
        # Declared "modern conduct" — no Lal Kitab/classical source is claimed.
        if time_reliable and len(list(strengths.keys())) > 1:
            p2 = list(strengths.keys())[1]
            sa2 = strengths[p2]
            remedies.append(modern_conduct_remedy(
                title=f"{p2} house steadiness",
                practice="Keep a small, clean, dedicated workspace for the significations of the relevant house; serve an elder connected with the house theme weekly.",
                purpose=f"Modern practical support to steady {p2} house themes (not a classical prescription).",
                chart_reason=f"{p2} links to relevant house(s) {sa2.functional_lordship} and sits in {sa2.house}H; used only because house placement is reliable here.",
                suitability="Moderate"))

    # Gemstone: evaluate but do NOT auto-add; compose the note from the verdict
    gem_note = ""
    if strengths:
        sa0 = strengths[primary_planet]
        in_dasha = bool(dasha_state and (dasha_state.mahadasha == primary_planet or dasha_state.antardasha == primary_planet))
        gv = evaluate_gemstone(sa0, in_dasha)
        gem_note = format_gemstone_note(gv)

    # 11. Practical actions (non-superstitious)
    practical = [
        f"Track effort in {primary_planet}-ruled areas weekly; review at each Antardasha change.",
        "Put financial/professional discipline first (budget, savings, written agreements, expert advice).",
        "Avoid one-factor decisions; require natal + Dasha agreement before big commitments.",
        "Use transits as scheduling support, not as the trigger.",
        "Keep one alignment habit daily for 4–8 weeks, then review — drop what does not help.",
    ]
    if topic == "marriage":
        practical.insert(2, "Clarify non-negotiable partnership values; stay socially receptive without forcing timelines.")
    if topic in ("wealth", "business"):
        practical.insert(2, "Separate saving (2nd), earning (10th/11th), and risk (5th/8th) money; cap speculative exposure.")

    # 12. Confidence + remedy suitability
    overall_conf = predictions[0].confidence if predictions else "Low"
    # Deduplicate identical per-topic bases so the canonical block never repeats
    # the same sentence twice (the "everywhere" complaint).
    unique_bases = list(dict.fromkeys(p.confidence_reason for p in predictions[:2]))
    conf_reason = " | ".join(unique_bases) + \
        ("" if time_reliable else " Reduced one level for uncertain birth time.")
    if not time_reliable and overall_conf == "High":
        overall_conf = "Medium"
    rem_suit = "Moderate" if time_reliable else "Low"
    primary_recommendation = (strengths[primary_planet].recommendation
                              if primary_planet in strengths else "not assessed")
    rem_reason = (f"Remedies are optional/supportive. Primary alignment is suitable ({rem_suit.lower()}) because "
                  f"{primary_planet} assessment says '{primary_recommendation}' for this chart. {gem_note} "
                  + ("" if time_reliable else "House-based/conduct remedies carry low suitability until birth time is verified."))

    calc_note = (f"Engine: {ephemeris_engine_name()} ({ephemeris_data_source()}). "
                 f"Sidereal Lahiri, Asc {d1.ascendant_sign} {d1.ascendant_degree_in_sign:.2f}°, "
                 f"Moon {d1.planets['Moon'].nakshatra}-P{d1.planets['Moon'].nakshatra_pada}, "
                 f"MD/AD/PD {md_ad}; relevant {', '.join(varga_names)}.")

    backtest_note = ""
    if historical_events:
        # Sec 14: rule first, then test — table rows
        rows = []
        for ev in historical_events[:5]:
            rows.append(f"{ev.get('event', '?')} | rule: natal+Dasha agreement | Dasha: {md_ad} | Transit: {transit_note[:60]} | Match: needs manual review (in-sample — not proof).")
        backtest_note = ("Backtesting mode: rules were fixed before seeing events. " + " || ".join(rows) +
                         " In-sample matches are not proof of accuracy; out-of-sample testing required.")

    # =====================================================================
    # 13. Depth layer: gochara, ashtakavarga, natal panchanga, varshaphala,
    #     promise gate, time stability, deep dasha, yogas, Jaimini.
    # =====================================================================
    try:
        deep_dasha = get_deep_dasha_at_date(timeline, query_dt)
    except Exception:
        deep_dasha = None
    try:
        upcoming = upcoming_periods(timeline, query_dt, levels=("MD", "AD"), limit=6)
    except Exception:
        upcoming = []
    try:
        gochara = evaluate_gochara(d1, query_dt)
    except Exception:
        gochara = None
    try:
        ashtakavarga = calculate_ashtakavarga(d1)
    except Exception:
        ashtakavarga = None
    try:
        birth_panchanga = compute_natal_panchanga(year, month, day, hour, minute, second, tz_offset)
    except Exception:
        birth_panchanga = None
    try:
        varshaphala = compute_varshaphala(d1, birth_dt, query_dt.year, tz_offset, lat, lon)
    except Exception:
        varshaphala = None

    d9_chart = None
    try:
        d9_chart = calculate_navamsa_chart(d1)
    except Exception:
        d9_chart = None

    karakas = None
    jaimini_pts = None
    upapada = None
    try:
        karakas = calculate_chara_karakas(d1)
        if d9_chart is not None:
            jaimini_pts = calculate_jaimini_points(d1, d9_chart)
            upapada = calculate_upapada(d1, d9_chart)
    except Exception:
        pass

    promise = assess_promise(
        d1, topic,
        upapada_sign_index=jaimini_pts.upapada_lagna_index if jaimini_pts else None,
    )

    # Sensitivity window follows the stated precision: a user-provided time is
    # tested at minute-level robustness (±5 min); an unknown/estimated time is
    # tested at the wide window (±30 min) because no exact claim exists.
    stability_window = 5 if time_reliable else 30
    try:
        stability = assess_birth_time_stability(
            year, month, day, hour, minute, tz_offset, lat, lon,
            window_minutes=stability_window,
        )
    except Exception:
        stability = None

    # Chart-sensitivity cap: a High reading cannot survive an unstable lagna or
    # D9 lagna *at the stated precision*. This is a property of the chart (a
    # boundary-sensitive ascendant), not a claim that the user's time is wrong.
    if stability is not None and (not stability.lagna_stable or not stability.d9_lagna_stable):
        if overall_conf == "High":
            overall_conf = "Medium"
            conf_reason += (" Sensitivity cap (Medium): " + stability.summary +
                            " This reflects chart sensitivity, not doubt about the time provided.")

    try:
        yoga_profile = detect_yogas(d1, d9_chart, karakas)
    except Exception:
        yoga_profile = None

    # Promise gate: never present event timing when the natal promise is weak.
    predictions_for_answer = predictions
    if not promise.timing_reliable:
        predictions_for_answer = []
        overall_conf = "Low"
        conf_reason = (promise.statement + " Timing language is withheld because the natal promise is weak. "
                       + conf_reason)
        bottom_line = promise.statement + " " + bottom_line

    promise_note = promise.statement
    if promise.supportive_factors:
        promise_note += " Supporting: " + "; ".join(promise.supportive_factors[:3]) + "."
    if promise.limiting_factors:
        promise_note += " Limiting: " + "; ".join(promise.limiting_factors[:3]) + "."

    period = period_alignment(
        timing.current_md_ad_pd, promise=promise, upcoming=upcoming,
        time_reliable=time_reliable,
    )
    if period:
        alignment_actions.append(format_period_line(period))

    # ---- Personal timeline -------------------------------------------------
    timeline_lines: List[str] = []
    if deep_dasha is not None:
        timeline_lines.append(
            f"Current: {deep_dasha.mahadasha} MD / {deep_dasha.antardasha} AD / "
            f"{deep_dasha.pratyantardasha} PD / {deep_dasha.sookshma} SD / {deep_dasha.prana} PrD "
            f"(Sukshma/Prana are proportional sub-periods, indicative)."
        )
    for p in upcoming:
        timeline_lines.append(f"{p.start_date:%Y-%m-%d}: enters {p.lord} {p.level}")

    # ---- Gochara + Sade Sati ----------------------------------------------
    gochara_note = ""
    if gochara is not None:
        gochara_note = gochara.summary + " " + gochara.sade_sati.note

    # ---- Ashtakavarga ------------------------------------------------------
    ashtakavarga_note = ""
    if ashtakavarga is not None:
        from .core.constants import SIGN_TO_INDEX
        sav_bits = ", ".join(
            f"H{h} {ashtakavarga.sav_by_house[h]}/56 ({house_support_label(ashtakavarga.sav_by_house[h])})"
            for h in relevant_houses[:4]
        )
        ashtakavarga_note = f"House support (Sarvashtakavarga): {sav_bits}."
        if gochara is not None:
            for planet in ("Jupiter", "Saturn"):
                sign_name = gochara.entries[planet].sign
                ashtakavarga_note += " " + transit_bindu_note(d1, planet, SIGN_TO_INDEX[sign_name])

    # ---- Natal panchanga / nakshatra --------------------------------------
    panchanga_note = ""
    if birth_panchanga is not None:
        panchanga_note = (
            f"Born on {birth_panchanga.vara} ({birth_panchanga.vara_sanskrit}), "
            f"{birth_panchanga.paksha} {birth_panchanga.tithi} tithi, "
            f"{birth_panchanga.nakshatra} pada {birth_panchanga.nakshatra_pada} "
            f"(lord {birth_panchanga.nakshatra_lord}; deity {birth_panchanga.deity}; "
            f"gana {birth_panchanga.gana}; yoni {birth_panchanga.yoni}; nature {birth_panchanga.nature}). "
            f"Moon-nakshatra themes: {', '.join(birth_panchanga.traits)}; watch for {birth_panchanga.watch}. "
            f"Yoga {birth_panchanga.yoga}; karana {birth_panchanga.karana}."
        )

    # ---- Yogas -------------------------------------------------------------
    yoga_notes: List[str] = []
    if yoga_profile is not None and yoga_profile.yogas:
        seen_yogas = set()
        for y in sorted(yoga_profile.yogas, key=lambda x: abs(x.strength_impact), reverse=True):
            if y.yoga_name in seen_yogas:
                continue
            seen_yogas.add(y.yoga_name)
            yoga_notes.append(f"{y.yoga_name} ({y.planet}): {y.description}")
            if len(yoga_notes) >= 6:
                break
        if yoga_profile.kala_sarpa_active:
            yoga_notes.append("Kala Sarpa pattern flagged — favour transparent methods and avoid shortcuts.")
    else:
        yoga_notes.append("No major named yoga dominates this chart; strength rests on the chain below.")

    # ---- Rahu/Ketu guidance ------------------------------------------------
    node_guidance: List[str] = []
    for node_name, na in node_analyses.items():
        node_guidance.append(
            f"{node_name} in H{na.house}/{na.sign}: wants — {na.wants} "
            f"Gains — {na.where_gains} Instability — {na.where_instability} "
            f"Constructive channel — {na.constructive_channel} Reduce — {na.reducing_behaviour}"
        )

    # ---- Jaimini marriage layer -------------------------------------------
    jaimini_note = ""
    if topic == "marriage" and karakas is not None and jaimini_pts is not None:
        jaimini_note = (
            f"Atmakaraka {karakas.atmakaraka}; Darakaraka {jaimini_pts.darakaraka} "
            f"({jaimini_pts.darakaraka_sign}; navamsa {jaimini_pts.darakaraka_navamsa_sign}); "
            f"Arudha Lagna {jaimini_pts.arudha_lagna_sign}; "
            f"Upapada Lagna {jaimini_pts.upapada_lagna_sign}."
        )
        if upapada is not None:
            jaimini_note += f" UL assessment: {upapada.overall_assessment}."
            if upapada.delay_factors:
                jaimini_note += " Delay factors: " + "; ".join(upapada.delay_factors[:3]) + "."
            if upapada.strength_factors:
                jaimini_note += " Strength factors: " + "; ".join(upapada.strength_factors[:3]) + "."

    builder = ConsumerAnswerBuilder()
    answer = builder.build(
        question=question, bottom_line=bottom_line, key_factors=key_factors,
        timing_reading=timing, opportunity=opportunity, risk=risk,
        alignment_title=alignment_title, alignment_actions=alignment_actions,
        remedies=remedies, practical_actions=practical,
        predictions=predictions_for_answer, confidence=overall_conf, confidence_reason=conf_reason,
        remedy_suitability=rem_suit, remedy_suitability_reason=rem_reason,
        calculation_note=calc_note, backtest_note=backtest_note,
        promise_note=promise_note,
        timeline=timeline_lines,
        gochara_note=gochara_note,
        ashtakavarga_note=ashtakavarga_note,
        yoga_notes=yoga_notes,
        node_guidance=node_guidance,
        panchanga_note=panchanga_note,
        varshaphala_note=varshaphala.note if varshaphala else "",
        jaimini_note=jaimini_note,
        stability_note=stability.summary if stability else "",
    )
    return ConsumerResult(
        answer=answer, d1=d1, vargas=vargas, strengths=strengths, timing=timing, topic=topic,
        gochara=gochara, ashtakavarga=ashtakavarga, panchanga=birth_panchanga,
        varshaphala=varshaphala, promise=promise, stability=stability,
        deep_dasha=deep_dasha, upcoming=upcoming, yogas=yoga_profile,
        nodes=node_analyses, karakas=karakas, jaimini=jaimini_pts, upapada=upapada,
        full_varga_matrix=full_varga_matrix,
    )
