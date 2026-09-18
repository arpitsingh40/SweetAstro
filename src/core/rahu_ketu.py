"""
Rahu / Ketu Deep Analysis — Consumer Engine Sec 8.

Never judge nodes from D1 house alone. Chain:
sign lord -> dispositor -> Nakshatra lord -> conjunctions -> aspects ->
D1 + relevant vargas (gated by birth-time accuracy).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .chart import D1Chart
from .vargas import VargaChart


@dataclass
class NodeAnalysis:
    node: str  # Rahu | Ketu
    house: int
    sign: str
    sign_lord: str
    dispositor: str
    dispositor_dignity: str
    dispositor_house: int
    nakshatra: str
    nakshatra_pada: int
    nakshatra_lord: str
    nakshatra_lord_house: int
    conjunctions: List[str]
    aspects_received_from: List[str]
    varga_positions: Dict[str, str]  # varga -> sign
    wants: str
    where_gains: str
    where_instability: str
    dasha_note: str
    constructive_channel: str
    reducing_behaviour: str
    recommendation: str  # pacify | balance (nodes are rarely 'strengthen')
    recommendation_reason: str


def analyze_node(
    d1: D1Chart,
    node: str,
    vargas: Optional[Dict[str, VargaChart]] = None,
    time_reliable: bool = True,
) -> NodeAnalysis:
    """Full-chain node analysis. `vargas` should already be question-relevant."""
    if node not in ("Rahu", "Ketu"):
        raise ValueError("node must be Rahu or Ketu")
    from .constants import SIGN_LORDS
    ps = d1.planets[node]
    sign_lord = SIGN_LORDS[ps.sign]
    disp = d1.planets[sign_lord]
    nk_lord_name = ps.nakshatra_lord
    nk_lord = d1.planets.get(nk_lord_name)

    conjunctions = [o for o in d1.houses[ps.house].occupants if o != node]
    received = [p for p, q in d1.planets.items()
                if ps.house in q.aspecting_houses and p != node]

    vpos: Dict[str, str] = {}
    if vargas and time_reliable:
        for vname, vc in vargas.items():
            if node in vc.planets:
                vpos[vname] = vc.planets[node].varga_sign
    elif vargas:
        # Birth time uncertain: only D1 (+ D9 with caveat) — mark reduced confidence
        if "D9" in vargas and node in vargas["D9"].planets:
            vpos["D9?"] = vargas["D9"].planets[node].varga_sign + " (low confidence)"

    disp_strong = disp.dignity in ("Exalted", "Moolatrikona", "Own", "Friend")
    conj_benefic = any(c in ("Jupiter", "Venus", "Mercury", "Moon") for c in conjunctions)

    if node == "Rahu":
        wants = (f"Rahu in {ps.house}H / {ps.sign} wants unconventional gains through "
                 f"{sign_lord}-ruled themes; obsessive focus where it sits.")
        gains = (f"Gains possible where Rahu's controller {sign_lord} ({disp.dignity} in {disp.house}H) "
                 "is connected to kendra/trikona/labha themes and where transits/Dasha activate them.")
        instability = (f"Instability where Rahu sits ({ps.house}H) via overreach, shortcuts, or foreign/irregular means; "
                       f"stronger if dispositor afflicted or with malefics {conjunctions}.")
        channel = ("Channel Rahu constructively: structured experimentation, technology/systems skill, "
                   "transparent rules, steady routine; avoid speculation/grey areas.")
        reducing = ("Reduce negative expression: avoid impulsive risk, misrepresentation, "
                    "late-night irregularity, and mixing Rahu Dasha ambition with debt/leverage.")
        dasha_note = ("During Rahu Dasha/Antardasha, results follow the dispositor and Nakshatra lord "
                      f"({sign_lord}/{nk_lord_name}); judge the period by their houses, not Rahu's house alone.")
    else:
        wants = (f"Ketu in {ps.house}H / {ps.sign} wants detachment/simplification in "
                 f"{sign_lord}-ruled themes; insight through withdrawal.")
        gains = (f"Gains via technical depth, intuition, and precision where Ketu's controller {sign_lord} "
                 f"({disp.dignity} in {disp.house}H) supports it.")
        instability = (f"Sudden separation/isolation risk in {ps.house}H themes, especially if dispositor weak "
                       f"or Ketu with malefics {conjunctions}.")
        channel = ("Channel Ketu: focused technical work, meditation, minimalism, service without display.")
        reducing = ("Reduce negative expression: avoid abrupt exits, ghosting duties, or confusing detachment with neglect.")
        dasha_note = ("During Ketu periods, detachment/spiritualisation and technical ability rise; "
                      f"material outcomes follow dispositor {sign_lord} and Nakshatra lord {nk_lord_name}.")

    if not disp_strong or nk_lord is None or getattr(nk_lord, "dignity", "") in ("Debilitated", "Enemy"):
        rec, why = "pacify", (f"Controller {sign_lord} ({disp.dignity}) or Nakshatra lord {nk_lord_name} is not strong; "
                              "pacify/balance the node rather than strengthen it.")
    elif conj_benefic and disp_strong:
        rec, why = "balance", (f"Controller {sign_lord} is dignified and node has benefic association; "
                               "balanced alignment is enough — no gemstone/intense strengthening by default.")
    else:
        rec, why = "pacify", "Default for nodes is pacify/balance; strengthening requires exceptional multi-factor support."

    return NodeAnalysis(
        node=node, house=ps.house, sign=ps.sign, sign_lord=sign_lord,
        dispositor=sign_lord, dispositor_dignity=disp.dignity, dispositor_house=disp.house,
        nakshatra=ps.nakshatra, nakshatra_pada=ps.nakshatra_pada,
        nakshatra_lord=nk_lord_name,
        nakshatra_lord_house=nk_lord.house if nk_lord else -1,
        conjunctions=conjunctions, aspects_received_from=received,
        varga_positions=vpos, wants=wants, where_gains=gains,
        where_instability=instability, dasha_note=dasha_note,
        constructive_channel=channel, reducing_behaviour=reducing,
        recommendation=rec, recommendation_reason=why,
    )
