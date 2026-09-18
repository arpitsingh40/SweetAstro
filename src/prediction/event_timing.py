"""
Event Timing Engine — multi-layer, promise-gated event windows.

Design (see docs/research/timely_event_prediction.md):
  1. Promise gate   — no event windows are produced when the natal promise is weak.
  2. Dasha layer    — Vimshottari MD/AD/PD periods whose lords connect to the
                      event's houses / lords / karakas (depth agreement counts).
  3. Transit layer  — slow-planet activation of the event axis, filtered by the
                      transiting planet's Bhinnashtakavarga bindus and the
                      event houses' Sarvashtakavarga support.
  4. Annual layer   — Varshaphala Muntha confirming the event houses.
  5. Output         — ranked windows with tier + factors. Never a single date,
                      never a guarantee; cross-layer disagreement lowers score.

Honesty contract: this is an interpretive traditional system. The pre-registered
accuracy protocol (docs/accuracy_protocol.md) governs any accuracy claim; none
is made here.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..core.ashtakavarga import calculate_ashtakavarga, house_support_label
from ..core.chara_dasha import (
    calculate_chara_timeline, chara_house_of_sign, get_chara_at_date,
)
from ..core.chart import D1Chart, calculate_d1_chart
from ..core.constants import INDEX_TO_SIGN
from ..core.dasha import DashaPeriod, calculate_vimshottari_timeline
from ..core.transits import (
    TransitPosition, _get_aspected_signs, get_transit_positions,
)
from ..core.varshaphala import compute_varshaphala
from ..interpretation.promise import PromiseAssessment, assess_promise


@dataclass
class EventConfig:
    key: str
    label: str
    promise_topic: str
    houses: List[int]
    karakas: List[str]
    transit_planets: List[str]
    min_bav: int = 4
    min_sav: int = 25


EVENT_CONFIGS: Dict[str, EventConfig] = {
    "marriage": EventConfig(
        key="marriage", label="Marriage", promise_topic="marriage",
        houses=[7, 2, 11], karakas=["Venus", "Jupiter"],
        transit_planets=["Jupiter", "Saturn"],
    ),
    "career_change": EventConfig(
        key="career_change", label="Career change / promotion", promise_topic="career",
        houses=[10, 6, 7], karakas=["Saturn", "Sun", "Mercury"],
        transit_planets=["Jupiter", "Saturn"],
    ),
    "property": EventConfig(
        key="property", label="Property / home purchase", promise_topic="property",
        houses=[4, 2, 11], karakas=["Mars", "Saturn"],
        transit_planets=["Jupiter", "Saturn"],
    ),
    "child": EventConfig(
        key="child", label="Childbirth / children", promise_topic="children",
        houses=[5, 9], karakas=["Jupiter"],
        transit_planets=["Jupiter"],
    ),
    "travel": EventConfig(
        key="travel", label="Long travel / relocation", promise_topic="general",
        houses=[3, 9, 12], karakas=["Moon", "Mercury"],
        transit_planets=["Jupiter", "Saturn"],
    ),
    "business_launch": EventConfig(
        key="business_launch", label="Business launch", promise_topic="business",
        houses=[7, 10, 11], karakas=["Mercury", "Saturn", "Sun"],
        transit_planets=["Jupiter", "Saturn"],
    ),
}

MIN_SCORE = 4.0


@dataclass
class TimingWindow:
    mahadasha: str
    antardasha: str
    pratyantardasha: str
    start_date: str
    end_date: str
    score: float
    tier: str  # High / Medium / Low
    supported_by: List[str] = field(default_factory=list)
    limited_by: List[str] = field(default_factory=list)
    transit_note: str = ""


@dataclass
class EventTimingResult:
    event: str
    event_label: str
    gated: bool
    promise: PromiseAssessment
    windows: List[TimingWindow]
    method_notes: List[str]
    disclaimer: str

    def to_dict(self) -> Dict:
        return {
            "event": self.event,
            "event_label": self.event_label,
            "gated": self.gated,
            "promise": {
                "topic": self.promise.topic,
                "level": self.promise.level,
                "score": self.promise.score,
                "statement": self.promise.statement,
                "supportive_factors": self.promise.supportive_factors,
                "limiting_factors": self.promise.limiting_factors,
                "timing_reliable": self.promise.timing_reliable,
            },
            "windows": [
                {
                    "mahadasha": w.mahadasha,
                    "antardasha": w.antardasha,
                    "pratyantardasha": w.pratyantardasha,
                    "start_date": w.start_date,
                    "end_date": w.end_date,
                    "score": w.score,
                    "tier": w.tier,
                    "supported_by": w.supported_by,
                    "limited_by": w.limited_by,
                    "transit_note": w.transit_note,
                }
                for w in self.windows
            ],
            "method_notes": self.method_notes,
            "disclaimer": self.disclaimer,
        }


def _period_significance(d1: D1Chart, config: EventConfig, lord: str) -> Tuple[int, List[str], List[str]]:
    """How strongly a dasha lord connects to the event (0-4) with reasons."""
    hits = 0
    supportive: List[str] = []
    limiting: List[str] = []

    owned = [h for h in config.houses if d1.houses[h].lord == lord]
    if owned:
        hits += 1
        supportive.append(f"{lord} owns event house(s) {owned}")
    if d1.planets[lord].house in config.houses:
        hits += 1
        supportive.append(f"{lord} occupies event house H{d1.planets[lord].house}")
    if lord in config.karakas:
        hits += 1
        supportive.append(f"{lord} is an event karaka")
    aspected = [h for h in config.houses if h in d1.planets[lord].aspecting_houses]
    if aspected:
        hits += 1
        supportive.append(f"{lord} aspects event house(s) {aspected}")
    if hits == 0:
        limiting.append(f"{lord} has no direct link to the event houses/karakas")
    return hits, supportive, limiting


def _bisect_sign_change(planet: str, lo: datetime, hi: datetime,
                        lo_sign: int, tol_days: float = 0.02) -> datetime:
    """First instant in (lo, hi] when the transiting planet leaves lo_sign."""
    while (hi - lo).total_seconds() / 86400.0 > tol_days:
        mid = lo + (hi - lo) / 2
        try:
            sign = get_transit_positions(mid, planets=[planet])[planet].sign_index
        except Exception:
            break
        if sign == lo_sign:
            lo = mid
        else:
            hi = mid
    return hi


def _transit_segments(planets: List[str], start: datetime, end: datetime,
                      step_days: int = 5) -> Dict[str, List[Tuple[datetime, int]]]:
    """Per-planet [(segment_start, sign_index)] covering [start, end].

    Audit F1: month-midpoint sampling missed sub-month ingresses. Sign changes
    are detected between 5-day samples and bisected to ~0.02 d, so every
    Pratyantardasha is matched against the signs actually held inside it.
    """
    if end <= start:
        end = start + timedelta(days=1)
    dates: List[datetime] = []
    cursor = start
    while cursor <= end:
        dates.append(cursor)
        cursor += timedelta(days=step_days)
    if dates[-1] < end:
        dates.append(end)

    sampled: List[Tuple[datetime, Dict[str, TransitPosition]]] = []
    for date in dates:
        try:
            sampled.append((date, get_transit_positions(date, planets=planets)))
        except Exception:
            sampled.append((date, {}))

    segments: Dict[str, List[Tuple[datetime, int]]] = {p: [] for p in planets}
    for planet in planets:
        first = sampled[0][1].get(planet) if sampled else None
        if first is None:
            continue
        segments[planet].append((dates[0], first.sign_index))
        for (d_prev, t_prev), (d_cur, t_cur) in zip(sampled, sampled[1:]):
            prev, cur = t_prev.get(planet), t_cur.get(planet)
            if prev is None or cur is None or prev.sign_index == cur.sign_index:
                continue
            segments[planet].append(
                (_bisect_sign_change(planet, d_prev, d_cur, prev.sign_index),
                 cur.sign_index))
    return segments


def _signs_in_window(segments: Dict[str, List[Tuple[datetime, int]]],
                     planet: str, window_start: datetime,
                     window_end: datetime) -> List[int]:
    """Signs the planet holds at any time inside [window_start, window_end]."""
    segs = segments.get(planet) or []
    signs: List[int] = []
    for index, (seg_start, sign) in enumerate(segs):
        seg_end = segs[index + 1][0] if index + 1 < len(segs) else None
        if seg_start <= window_end and (seg_end is None or seg_end >= window_start):
            signs.append(sign)
    return signs


def _transit_layer(d1: D1Chart, config: EventConfig, window_start: datetime,
                   window_end: datetime,
                   segments: Dict[str, List[Tuple[datetime, int]]],
                   ashtakavarga) -> Tuple[float, List[str], List[str], str]:
    score = 0.0
    supportive: List[str] = []
    limiting: List[str] = []
    activated = 0
    switch_notes: List[str] = []
    event_signs = {d1.houses[h].sign_index for h in config.houses}
    event_lord_signs = {d1.planets[d1.houses[h].lord].sign_index for h in config.houses}

    for planet in config.transit_planets:
        signs = _signs_in_window(segments, planet, window_start, window_end)
        if not signs:
            limiting.append(f"no transit sample for {planet} inside this window")
            continue
        touching = [
            sign for sign in signs
            if (event_signs | event_lord_signs) & set(_get_aspected_signs(planet, sign))
        ]
        sign_names = "->".join(INDEX_TO_SIGN[sign] for sign in signs)
        if not touching:
            limiting.append(f"transit {planet} in {sign_names} does not touch the event axis")
            continue
        bav_by_sign = {
            sign: (ashtakavarga.bav[planet][sign - 1]
                   if planet in ashtakavarga.bav else 0)
            for sign in signs
        }
        best = max(touching, key=lambda sign: bav_by_sign.get(sign, 0))
        bav = bav_by_sign.get(best, 0)
        if bav >= config.min_bav:
            activated += 1
            score += 3.0
            supportive.append(
                f"transit {planet} in {INDEX_TO_SIGN[best]} activates the event axis "
                f"with {bav}/8 bindus")
        else:
            score += 1.0
            supportive.append(
                f"transit {planet} in {INDEX_TO_SIGN[best]} touches the event axis "
                f"but only {bav}/8 bindus (weak)")
        if len(signs) > 1:
            switch_notes.append(f"{planet} changes sign inside this window: {sign_names}")

    sav_values = [ashtakavarga.sav_by_house[h] for h in config.houses]
    if sav_values and min(sav_values) >= config.min_sav:
        score += 1.5
        supportive.append("event houses carry strong Sarvashtakavarga support "
                          f"({', '.join(f'H{h}:{v}' for h, v in zip(config.houses, sav_values))})")
    elif sav_values:
        limiting.append("event houses are SAV-weak "
                        f"({', '.join(f'H{h}:{v}' for h, v in zip(config.houses, sav_values))})")

    if config.transit_planets == ["Jupiter", "Saturn"]:
        note = ("double-transit axis both active" if activated >= 2 else
                ("partial transit support" if activated == 1 else "no slow-planet transit support"))
    else:
        note = ("transit support present" if activated >= 1 else "no transit support")
    if switch_notes:
        note += " " + "; ".join(switch_notes) + "."
    return score, supportive, limiting, note


def _birth_time_sensitivity_days(d1: D1Chart, birth_dt: datetime,
                                 range_start: datetime, tz_offset: float,
                                 lat: float, lon: float,
                                 delta_minutes: int = 5) -> Optional[float]:
    """Measured shift of dasha boundaries for a delta-minute birth-time change.

    Window width is the Pratyantardasha span; this number tells the user how
    precise the birth time must be for the window to mean anything.
    """
    try:
        shifted = birth_dt + timedelta(minutes=delta_minutes)
        d1_shifted = calculate_d1_chart(
            shifted.year, shifted.month, shifted.day, shifted.hour, shifted.minute,
            shifted.second, tz_offset, lat, lon)
        base_tl = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)
        shifted_tl = calculate_vimshottari_timeline(
            shifted, d1_shifted.planets["Moon"].longitude)

        def first_boundary(timeline: List[DashaPeriod]) -> Optional[datetime]:
            candidates = [
                p.start_date for p in timeline
                if p.level in ("MD", "AD") and p.start_date >= range_start
            ]
            return min(candidates) if candidates else None

        base, moved = first_boundary(base_tl), first_boundary(shifted_tl)
        if base and moved:
            return abs((moved - base).total_seconds()) / 86400.0
    except Exception:
        return None
    return None


def _chara_cross_check(d1: D1Chart, config: EventConfig, mid: datetime,
                       timeline: List[DashaPeriod]) -> Tuple[float, List[str], List[str]]:
    """
    Independent Jaimini cross-check: the running Chara sign lights up the
    whole-sign house it occupies in the natal chart. Agreement adds a small
    confirmation bonus; disagreement is recorded but never subtracted, so the
    two systems confirm rather than stack.
    """
    state = get_chara_at_date(timeline, mid)
    if state is None:
        return 0.0, [], []
    md_house = chara_house_of_sign(d1, state.mahadasha_sign)
    ad_house = chara_house_of_sign(d1, state.antardasha_sign)
    hits = sorted({h for h in (md_house, ad_house) if h in config.houses})
    if not hits:
        return 0.0, [], [
            f"Chara dasha {state.mahadasha_sign}/{state.antardasha_sign} "
            "does not touch the event houses"
        ]
    bonus = 1.0 if len(hits) == 1 else 1.5
    return bonus, [
        f"Chara dasha {state.mahadasha_sign} MD / {state.antardasha_sign} AD "
        f"activates event house(s) {hits}"
    ], []


def find_timing_windows(
    d1: D1Chart,
    birth_dt: datetime,
    event_key: str,
    range_start: datetime,
    range_end: datetime,
    max_windows: int = 8,
    tz_offset: float = 5.5,
    lat: float = 28.6139,
    lon: float = 77.2090,
) -> EventTimingResult:
    """Ranked, promise-gated timing windows for one event type."""
    config = EVENT_CONFIGS.get(event_key)
    if config is None:
        raise ValueError(f"Unknown event: {event_key!r}")

    promise = assess_promise(d1, config.promise_topic)

    notes = [
        "Layers used: promise gate -> Vimshottari MD/AD/PD -> slow-planet transit with "
        "Ashtakavarga bindus -> Varshaphala Muntha confirmation -> Chara dasha cross-check.",
        "Chara dasha (Jaimini sign dasha, count-minus-one convention) is an independent "
        "cross-check: agreement adds confirmation and is never stacked onto the "
        "Vimshottari lord counts; Narayana dasha is not yet computed.",
        "Windows are interpretive — cross-layer disagreement lowers the score and widens the window.",
    ]
    disclaimer = ("Traditional interpretive timing — no guarantee, not established causation, and no "
                  "accuracy claim. It does not replace the individual's own judgement or professional advice.")

    if not promise.timing_reliable:
        return EventTimingResult(
            event=event_key, event_label=config.label, gated=True, promise=promise,
            windows=[], method_notes=notes + ["Promise gate: weak natal promise — timing withheld."],
            disclaimer=disclaimer,
        )

    timeline = calculate_vimshottari_timeline(birth_dt, d1.planets["Moon"].longitude)
    pd_periods = [
        p for p in timeline
        if p.level == "PD" and p.end_date > range_start and p.start_date < range_end
    ]
    if not pd_periods:
        return EventTimingResult(
            event=event_key, event_label=config.label, gated=False, promise=promise,
            windows=[], method_notes=notes + ["No Pratyantardasha periods inside the requested range."],
            disclaimer=disclaimer,
        )

    ashtakavarga = calculate_ashtakavarga(d1)
    # F1: scan from the earliest intersecting PD so every window has transit
    # evidence at its own boundaries, not just a monthly midpoint sample.
    scan_start = min(range_start, min(p.start_date for p in pd_periods))
    transit_segments = _transit_segments(config.transit_planets, scan_start, range_end)
    chara_timeline = calculate_chara_timeline(d1, birth_dt, cycles=2)

    shift_days = _birth_time_sensitivity_days(
        d1, birth_dt, range_start, tz_offset, lat, lon)
    if shift_days is not None:
        notes.append(
            f"Window width is the Pratyantardasha span. Measured birth-time sensitivity "
            f"for this chart: a ±5-minute TOB change shifts dasha boundaries by about "
            f"{shift_days:.0f} day(s) — treat windows as candidate spans, not precise dates.")
    else:
        notes.append(
            "Window width is the Pratyantardasha span. Small birth-time errors can shift "
            "dasha boundaries by weeks — treat windows as candidate spans, not precise dates.")

    varshaphala_cache: Dict[int, object] = {}

    def _muntha_house(year: int) -> Optional[int]:
        if year not in varshaphala_cache:
            try:
                varshaphala_cache[year] = compute_varshaphala(
                    d1, birth_dt, year, tz_offset=tz_offset, lat=lat, lon=lon)
            except Exception:
                varshaphala_cache[year] = None
        varsh = varshaphala_cache[year]
        return getattr(varsh, "muntha_house_from_lagna", None)

    windows: List[TimingWindow] = []
    scan_limit = 120
    scanned_periods = pd_periods[:scan_limit]
    for pd in scanned_periods:
        connection = 0
        dasha_sup: List[str] = []
        depth_sup: List[str] = []
        limiting: List[str] = []
        for lord in (pd.parent_md, pd.parent_ad, pd.lord):
            hits, sup, lim = _period_significance(d1, config, lord)
            connection += hits
            dasha_sup.extend(sup)
            limiting.extend(lim)
        connection = min(connection, 6)
        same_depth = (pd.parent_ad == pd.lord) or (_period_significance(d1, config, pd.parent_ad)[0] > 0
                                                   and _period_significance(d1, config, pd.lord)[0] > 0)
        if same_depth:
            connection += 1
            depth_sup.append("Antardasha and Pratyantardasha lords both connect to the event")

        transit_score, t_sup, t_lim, transit_note = _transit_layer(
            d1, config, pd.start_date, pd.end_date, transit_segments, ashtakavarga)
        limiting.extend(t_lim)

        mid = pd.start_date + (pd.end_date - pd.start_date) / 2
        annual_sup: List[str] = []
        muntha_bonus = 0.0
        if _muntha_house(mid.year) in config.houses:
            muntha_bonus = 1.5
            annual_sup.append("Varshaphala Muntha falls in an event house this year")

        chara_bonus, c_sup, c_lim = _chara_cross_check(d1, config, mid, chara_timeline)
        limiting.extend(c_lim)

        # Interleave layers so every source of the score stays visible after
        # truncation (transit evidence was previously cut off entirely).
        supportive: List[str] = []
        supportive.extend(dasha_sup[:2])
        supportive.extend(t_sup[:2])
        supportive.extend(depth_sup[:1])
        supportive.extend(annual_sup[:1])
        supportive.extend(c_sup[:1])
        supportive.extend(dasha_sup[2:4])

        score = connection * 1.6 + transit_score + muntha_bonus + chara_bonus
        if score < MIN_SCORE:
            continue
        tier = "High" if score >= 10.5 else ("Medium" if score >= 7.0 else "Low")
        windows.append(TimingWindow(
            mahadasha=pd.parent_md, antardasha=pd.parent_ad, pratyantardasha=pd.lord,
            start_date=pd.start_date.strftime("%Y-%m-%d"),
            end_date=pd.end_date.strftime("%Y-%m-%d"),
            score=round(score, 1), tier=tier,
            supported_by=supportive[:8], limited_by=limiting[:5],
            transit_note=transit_note,
        ))

    windows.sort(key=lambda w: (-w.score, w.start_date))
    windows = windows[:max_windows]
    windows.sort(key=lambda w: w.start_date)

    notes.append(f"Scanned {len(scanned_periods)} Pratyantardasha periods; {len(windows)} cleared the score floor.")
    if len(pd_periods) > scan_limit:
        notes.append(
            f"Range contains {len(pd_periods)} Pratyantardasha periods; only the first "
            f"{scan_limit} were scored — narrow the range for full coverage.")
    return EventTimingResult(
        event=event_key, event_label=config.label, gated=False, promise=promise,
        windows=windows, method_notes=notes, disclaimer=disclaimer,
    )


def render_timing_markdown(result: EventTimingResult) -> str:
    lines = [f"# Event timing — {result.event_label}", ""]
    lines.append(f"**Promise:** {result.promise.level} (score {result.promise.score}) — {result.promise.statement}")
    lines.append("")
    if result.gated:
        lines.append("**Timing withheld:** the natal promise is weak for this event. "
                     "The analysis recommends strengthening the limiting factors instead of timing.")
    elif not result.windows:
        lines.append("No window cleared the score floor inside the requested range.")
    else:
        lines.append(f"## Ranked windows ({len(result.windows)})")
        for w in result.windows:
            lines.append(f"### {w.start_date} → {w.end_date} · {w.tier} (score {w.score})")
            lines.append(f"- Period: {w.mahadasha} MD / {w.antardasha} AD / {w.pratyantardasha} PD")
            lines.append(f"- Transit: {w.transit_note}")
            for s in w.supported_by:
                lines.append(f"  - + {s}")
            for l in w.limited_by:
                lines.append(f"  - − {l}")
        lines.append("")
    lines.append("## Method notes")
    for n in result.method_notes:
        lines.append(f"- {n}")
    lines.append("")
    lines.append(f"_{result.disclaimer}_")
    return "\n".join(lines)
