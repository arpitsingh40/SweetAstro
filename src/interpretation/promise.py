"""
Promise assessment (promise-before-timing order, Sec 230).

Classical workflow: natal promise -> strength -> dasha -> transit -> remedy.
This module answers the gate question "does the chart support this topic at
all?" before any timing is presented. Scoring is transparent factor counting,
not an invented probability:

+2  house lord Exalted / Moolatrikona / Own      -2  lord Debilitated
+1  lord Friend                                   -1  lord Enemy
+1  benefic (Jupiter/Venus/Mercury/Moon) occupant -1  malefic (Saturn/Mars/Rahu/Ketu/Sun) occupant
+0.5 benefic aspect on the house                  -0.5 malefic aspect
+1  benefic (karaka) forte for the topic (Venus/Jupiter for marriage)

Levels: >= 3 Supported · >= 0.5 Partial · else Weak.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_DIGNITY_SCORE = {
    "Exalted": 2.0, "Moolatrikona": 2.0, "Own": 2.0,
    "Friend": 1.0, "Neutral": 0.0, "Enemy": -1.0, "Debilitated": -2.0,
}

_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
_MALEFICS = {"Saturn", "Mars", "Rahu", "Ketu", "Sun"}

PRIMARY_HOUSES: Dict[str, List[int]] = {
    "wealth": [2, 11, 5],
    "career": [10, 6, 7],
    "business": [7, 10, 3],
    "marriage": [7, 2, 11],
    "children": [5, 9],
    "property": [4, 2],
    "education": [4, 5, 9],
    "siblings": [3, 11],
    "health": [1, 6],
    "spirituality": [9, 12],
    "general": [1, 9, 10],
}

_KARAKA_DIGNITY = {
    "marriage": ["Venus", "Jupiter"],
    "children": ["Jupiter"],
    "career": ["Saturn", "Mercury"],
    "wealth": ["Jupiter", "Venus"],
    "health": ["Moon", "Saturn"],
    "spirituality": ["Jupiter", "Ketu"],
}


@dataclass
class PromiseAssessment:
    topic: str
    level: str                       # Supported / Partial / Weak
    score: float
    supportive_factors: List[str] = field(default_factory=list)
    limiting_factors: List[str] = field(default_factory=list)
    timing_reliable: bool = True
    statement: str = ""


def _house_factors(d1: Any, house_num: int) -> tuple:
    house = d1.houses[house_num]
    lord = d1.planets[house.lord]
    score = _DIGNITY_SCORE.get(lord.dignity, 0.0)
    supportive: List[str] = []
    limiting: List[str] = []
    if score > 0:
        supportive.append(f"{house.lord} (lord of H{house_num}) is {lord.dignity} in H{lord.house}")
    elif score < 0:
        limiting.append(f"{house.lord} (lord of H{house_num}) is {lord.dignity} in H{lord.house}")

    for occupant in house.occupants:
        if occupant in _BENEFICS:
            score += 1.0
            supportive.append(f"{occupant} occupies H{house_num}")
        elif occupant in _MALEFICS:
            score -= 1.0
            limiting.append(f"{occupant} occupies H{house_num}")

    for aspecter in set(house.aspecting_planets):
        if aspecter in _BENEFICS:
            score += 0.5
            supportive.append(f"{aspecter} aspects H{house_num}")
        elif aspecter in _MALEFICS:
            score -= 0.5
            limiting.append(f"{aspecter} aspects H{house_num}")
    return score, supportive, limiting


def assess_promise(d1: Any, topic: str,
                   upapada_sign_index: Optional[int] = None) -> PromiseAssessment:
    """Transparent promise check for a topic (no guarantee, no probability)."""
    houses = PRIMARY_HOUSES.get(topic, PRIMARY_HOUSES["general"])
    score = 0.0
    supportive: List[str] = []
    limiting: List[str] = []

    for house_num in houses[:2]:
        s, sup, lim = _house_factors(d1, house_num)
        score += s
        supportive.extend(sup)
        limiting.extend(lim)

    for karaka in _KARAKA_DIGNITY.get(topic, []):
        status = _DIGNITY_SCORE.get(d1.planets[karaka].dignity, 0.0)
        if status > 0:
            score += 0.5
            supportive.append(f"{karaka} (karaka) is {d1.planets[karaka].dignity}")
        elif status < 0:
            score -= 0.5
            limiting.append(f"{karaka} (karaka) is {d1.planets[karaka].dignity}")

    if topic == "marriage" and upapada_sign_index:
        distance = ((upapada_sign_index - d1.ascendant_sign_index) % 12) + 1
        if distance in (1, 4, 5, 7, 9, 10):
            score += 0.5
            supportive.append("Upapada Lagna falls in a kendra/trikona from lagna")
        else:
            limiting.append("Upapada Lagna falls outside kendra/trikona (delay/instability signal)")

    n_support = len(supportive)
    n_limit = len(limiting)
    if score >= 3.0:
        level = "Supported"
        statement = (f"The chart gives a supported promise for {topic} "
                     f"({n_support} supporting / {n_limit} limiting factors). "
                     f"Timing windows are interpretively meaningful, though never guaranteed.")
    elif score >= 0.5:
        level = "Partial"
        statement = (f"The chart gives a partial promise for {topic} "
                     f"({n_support} supporting / {n_limit} limiting factors): some factors support it "
                     f"and some obstruct. Timing is indicative only; strengthening the weak links matters.")
    else:
        level = "Weak"
        statement = (f"The chart shows a weak promise for {topic} "
                     f"({n_support} supporting / {n_limit} limiting factors): the primary houses/karakas "
                     f"are under strain. Event-timing should not be relied on — focus on strengthening "
                     f"the indicated factors instead.")

    return PromiseAssessment(
        topic=topic, level=level, score=round(score, 2),
        supportive_factors=supportive, limiting_factors=limiting,
        timing_reliable=(level != "Weak"), statement=statement,
    )
