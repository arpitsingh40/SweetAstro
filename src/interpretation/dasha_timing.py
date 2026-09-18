"""
Dasha Timing Separator — Consumer Engine Sec 5.

Separates:
- Natal promise (what horoscope allows)
- Dasha activation (when promise becomes active)
- Transit activation (whether current movement supports it)
- Remedy timing (continuous / Dasha / weekday / hora / transit period)

Never claim transit alone creates event; never claim remedy overrides natal indications.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from ..core.dasha import DashaPeriod, get_dasha_at_date
from ..core.chart import D1Chart


@dataclass
class TimingReading:
    natal_promise: str
    dasha_activation: str
    transit_activation: str
    remedy_timing: str
    current_md_ad_pd: str


def _houses_of(d1: D1Chart, planet: str) -> List[int]:
    return sorted([h for h, hs in d1.houses.items() if hs.lord == planet])


def _house_of_planet(d1: D1Chart, planet: str) -> int:
    return d1.planets[planet].house if planet in d1.planets else -1


def read_timing(d1: D1Chart, timeline: List[DashaPeriod], query_dt: datetime,
                relevant_houses: List[int], transit_note: str) -> TimingReading:
    state = get_dasha_at_date(timeline, query_dt)
    if state:
        md, ad, pd = state.mahadasha, state.antardasha, state.pratyantardasha
        md_h = _house_of_planet(d1, md)
        ad_h = _house_of_planet(d1, ad)
        acts = [h for h in (md_h, ad_h) if h in relevant_houses]
        dasha_txt = (f"Active Vimshottari: {md} MD / {ad} AD / {pd} PD. "
                     f"{md} sits in {md_h}H, {ad} in {ad_h}H. "
                     + (f"These activate relevant house(s) {acts} — timing support present. "
                        if acts else "Neither MD nor AD lord sits in/owns the most relevant houses — timing support is indirect; "
                        "look to lordship/dispositor links before concluding. "))
    else:
        md, ad, pd = "—", "—", "—"
        dasha_txt = "Dasha state could not be resolved for this date; do not time the event from transits alone."

    natal_txt = ("Natal promise is judged from D1 + relevant vargas (lordship, dignity, conjunctions, aspects). "
                 f"Relevant houses for this question: {relevant_houses}. "
                 "Dasha/transit only activate what the natal chart allows — they do not create it.")

    transit_txt = (transit_note + " Transits alone do not create the event; "
                   "they only support it when natal promise + Dasha agree.")

    remedy_txt = ("Remedy timing: alignment conduct is continuous; mantra/service on the planet's weekday/hora "
                  "is supportive during the related Dasha/Antardasha or transit pressure. "
                  "No remedy overrides natal indications or guarantees a result.")

    return TimingReading(
        natal_promise=natal_txt,
        dasha_activation=dasha_txt,
        transit_activation=transit_txt,
        remedy_timing=remedy_txt,
        current_md_ad_pd=f"{md} / {ad} / {pd}",
    )
