"""
Marriage Knowledge Graph.
Models the structured astrological relational graph connecting 7th House,
7th Lord, Venus, Jupiter, D9 Navamsa, Jaimini Karakas, Dasha, and Transits.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any

from ..core.chart import D1Chart
from ..core.navamsa import NavamsaChart
from ..core.jaimini import JaiminiKarakas, JaiminiPoints
from ..core.dasha import DashaStateAtDate
from ..core.transits import DoubleTransitResult


@dataclass
class KnowledgeNode:
    node_id: str
    node_type: str  # "house", "planet", "sign", "point", "dasha", "transit"
    attributes: Dict[str, Any] = field(default_factory=dict)
    connected_nodes: Dict[str, str] = field(default_factory=dict)  # target_node_id -> relationship_type


class MarriageKnowledgeGraph:
    """
    Relational graph integrating all marriage factors.
    """
    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}

    def add_node(self, node_id: str, node_type: str, **attrs) -> KnowledgeNode:
        node = KnowledgeNode(node_id=node_id, node_type=node_type, attributes=attrs)
        self.nodes[node_id] = node
        return node

    def add_edge(self, source_id: str, target_id: str, relation: str):
        if source_id in self.nodes and target_id in self.nodes:
            self.nodes[source_id].connected_nodes[target_id] = relation

    @classmethod
    def build_graph(
        cls,
        d1: D1Chart,
        d9: NavamsaChart,
        karakas: JaiminiKarakas,
        jaimini_pts: JaiminiPoints,
        dasha: Optional[DashaStateAtDate] = None,
        transits: Optional[DoubleTransitResult] = None
    ) -> "MarriageKnowledgeGraph":
        kg = cls()

        # 1. 7th House Node
        h7 = d1.houses[7]
        kg.add_node(
            "House_7", "house",
            sign=h7.sign,
            lord=h7.lord,
            occupants=h7.occupants,
            aspecting_planets=h7.aspecting_planets
        )

        # 2. 7th Lord Node
        lord_state = d1.seventh_lord
        kg.add_node(
            f"Planet_{h7.lord}", "planet",
            house=lord_state.house,
            sign=lord_state.sign,
            dignity=lord_state.dignity,
            is_combust=lord_state.is_combust,
            is_retrograde=lord_state.is_retrograde
        )
        kg.add_edge("House_7", f"Planet_{h7.lord}", "ruled_by")

        # 3. Venus & Jupiter (Natural Karakas)
        venus_state = d1.planets["Venus"]
        kg.add_node(
            "Planet_Venus", "planet",
            house=venus_state.house,
            sign=venus_state.sign,
            dignity=venus_state.dignity,
            is_combust=venus_state.is_combust
        )
        kg.add_edge("House_7", "Planet_Venus", "signified_by")

        jup_state = d1.planets["Jupiter"]
        kg.add_node(
            "Planet_Jupiter", "planet",
            house=jup_state.house,
            sign=jup_state.sign,
            dignity=jup_state.dignity
        )
        if 7 in jup_state.aspecting_houses:
            kg.add_edge("Planet_Jupiter", "House_7", "aspects_and_blesses")

        # 4. Navamsa Node
        kg.add_node(
            "Navamsa_7th", "navamsa",
            sign=d9.seventh_house_sign,
            lord=d9.seventh_house_lord,
            occupants=d9.seventh_house_occupants
        )
        kg.add_edge("House_7", "Navamsa_7th", "confirmed_by_d9")

        # 5. Jaimini Karaka & Upapada Node
        kg.add_node(
            "Jaimini_DK", "point",
            planet=karakas.darakaraka,
            sign=jaimini_pts.darakaraka_sign,
            navamsa_sign=jaimini_pts.darakaraka_navamsa_sign
        )
        kg.add_edge("House_7", "Jaimini_DK", "jaimini_karaka")

        kg.add_node(
            "Upapada_Lagna", "point",
            sign=jaimini_pts.upapada_lagna_sign,
            index=jaimini_pts.upapada_lagna_index
        )
        kg.add_edge("House_7", "Upapada_Lagna", "manifested_by_upapada")

        # 6. Dasha Node (if active)
        if dasha:
            kg.add_node(
                "Active_Dasha", "dasha",
                mahadasha=dasha.mahadasha,
                antardasha=dasha.antardasha,
                pratyantardasha=dasha.pratyantardasha
            )
            # Link dasha to entities
            if dasha.mahadasha == h7.lord or dasha.antardasha == h7.lord:
                kg.add_edge("Active_Dasha", f"Planet_{h7.lord}", "activates_7th_lord")
            if dasha.mahadasha == "Venus" or dasha.antardasha == "Venus":
                kg.add_edge("Active_Dasha", "Planet_Venus", "activates_venus")
            if dasha.mahadasha == karakas.darakaraka or dasha.antardasha == karakas.darakaraka:
                kg.add_edge("Active_Dasha", "Jaimini_DK", "activates_darakaraka")

        # 7. Transit Node
        if transits:
            kg.add_node(
                "Active_Transit", "transit",
                is_double_transit=transits.is_active,
                jupiter_score=transits.jupiter_score,
                saturn_score=transits.saturn_score,
                total_score=transits.total_transit_score
            )
            if transits.is_active:
                kg.add_edge("Active_Transit", "House_7", "double_transit_sanction")

        # 8. Yoga Node (if present)
        try:
            from ..core.yogas import detect_yogas
            from ..core.navamsa import NavamsaChart as NavType
            yoga_profile = detect_yogas(d1, d9, karakas)
            if yoga_profile.yogas:
                kg.add_node(
                    "Yoga_Profile", "yoga",
                    yoga_count=len(yoga_profile.yogas),
                    rajayoga_count=yoga_profile.rajayoga_count,
                    strongest=yoga_profile.strongest_yoga,
                    planet_boosts=yoga_profile.planet_yoga_boost,
                )
                if yoga_profile.rajayoga_count > 0:
                    kg.add_edge("Yoga_Profile", "House_7", "rajayoga_supports")
        except Exception:
            pass

        # 9. Shadbala Node (for 7th lord and key planets)
        try:
            from ..core.shadbala import calculate_shadbala
            scores = {}
            for pname in ["Venus", "Jupiter", "Saturn", h7.lord]:
                if pname in d1.planets:
                    sb = calculate_shadbala(d1.planets[pname], d1)
                    scores[pname] = sb.strength_category
            if scores:
                kg.add_node(
                    "Shadbala_Profile", "shadbala",
                    planet_strengths=scores,
                )
        except Exception:
            pass

        return kg
