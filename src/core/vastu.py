"""
Vastu scoring engine.

Evaluates a described layout (room directions, water, slope, shape, facing)
against the sourced rules in data/rules/vastu_rules.json and returns
compliant / acceptable / defect findings, a completeness-aware score, and
safe optional remedies. Never advises demolition or structural work; details
that require site measurement are left to professionals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rules" / "vastu_rules.json"

DIRECTIONS = ["North", "North-East", "East", "South-East", "South",
              "South-West", "West", "North-West", "Center"]

_DIRECTION_ALIASES = {
    "n": "North", "north": "North",
    "ne": "North-East", "north-east": "North-East", "north east": "North-East",
    "northeast": "North-East", "n-e": "North-East", "ishan": "North-East", "ishanya": "North-East",
    "e": "East", "east": "East", "purva": "East",
    "se": "South-East", "south-east": "South-East", "south east": "South-East",
    "southeast": "South-East", "s-e": "South-East", "agni": "South-East",
    "s": "South", "south": "South", "dakshina": "South",
    "sw": "South-West", "south-west": "South-West", "south west": "South-West",
    "southwest": "South-West", "s-w": "South-West", "nairutya": "South-West",
    "w": "West", "west": "West", "paschim": "West",
    "nw": "North-West", "north-west": "North-West", "north west": "North-West",
    "northwest": "North-West", "n-w": "North-West", "vayu": "North-West",
    "centre": "Center", "center": "Center", "central": "Center", "middle": "Center", "brahmasthan": "Center",
}

ROOM_KEYS = ["puja", "kitchen", "master_bedroom", "children_bedroom", "guest_room",
             "living_room", "dining", "study", "parents_room", "store",
             "staircase", "toilet", "utility", "garage"]
WATER_KEYS = ["underground_tank", "overhead_tank"]
WATER_LABELS = {"underground_tank": "Underground water tank", "overhead_tank": "Overhead water tank"}

# (layout item, directions triggering the defect, defect id)
_DEFECT_MATCHERS = [
    ("rooms:toilet", {"North-East"}, "V-D01"),
    ("rooms:kitchen", {"North-East", "South-West"}, "V-D02"),
    ("rooms:master_bedroom", {"North-East", "South-East"}, "V-D03"),
    ("water:overhead_tank", {"North-East"}, "V-D04"),
    ("water:underground_tank", {"South-West"}, "V-D05"),
    ("rooms:staircase", {"North-East"}, "V-D09"),
]

_ROOM_SEVERITY = {"puja": "high", "kitchen": "high", "toilet": "high",
                  "master_bedroom": "medium", "staircase": "medium",
                  "store": "medium", "dining": "low"}

_POINTS = {"compliant": 1.0, "acceptable": 0.6, "neutral": 0.4, "defect": 0.0}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def load_vastu_rules(path: Optional[Path] = None) -> Dict:
    return json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))


def normalize_direction(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    key = value.strip().lower().replace("_", " ")
    return _DIRECTION_ALIASES.get(key)


@dataclass
class VastuFinding:
    item: str
    label: str
    direction: str
    status: str                      # compliant | acceptable | neutral | defect | info
    expected: List[str] = field(default_factory=list)
    severity: Optional[str] = None
    defect_id: Optional[str] = None
    note: str = ""
    confidence: str = "traditional"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "label": self.label,
            "direction": self.direction,
            "status": self.status,
            "expected_best": self.expected,
            "severity": self.severity,
            "defect_id": self.defect_id,
            "note": self.note,
            "confidence": self.confidence,
        }


@dataclass
class VastuAssessment:
    findings: List[VastuFinding]
    score: Optional[float]
    counts: Dict[str, int]
    remedies: List[Dict[str, Any]]
    not_assessed: List[str]
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "counts": self.counts,
            "findings": [f.to_dict() for f in self.findings],
            "compliant": [f.to_dict() for f in self.findings if f.status == "compliant"],
            "acceptable": [f.to_dict() for f in self.findings if f.status == "acceptable"],
            "defects": [f.to_dict() for f in self.findings if f.status == "defect"],
            "neutral": [f.to_dict() for f in self.findings if f.status == "neutral"],
            "remedies": self.remedies,
            "not_assessed": self.not_assessed,
            "sources": self.sources,
        }


def _classify(room_key: str, direction: str, rules: Dict) -> VastuFinding:
    room = rules["rooms"][room_key]
    label = room["label"]
    if direction in room["best"]:
        status, severity = "compliant", None
    elif direction in room["acceptable"]:
        status, severity = "acceptable", None
    elif direction in room["avoid"]:
        status, severity = "defect", _ROOM_SEVERITY.get(room_key, "medium")
    else:
        status, severity = "neutral", None

    defect_id = None
    if status == "defect":
        for item, directions, did in _DEFECT_MATCHERS:
            if item == f"rooms:{room_key}" and direction in directions:
                defect_id = did
                break

    note = room.get("notes", "")
    return VastuFinding(item=f"rooms:{room_key}", label=label, direction=direction,
                        status=status, expected=list(room["best"]), severity=severity,
                        defect_id=defect_id, note=note, confidence=room.get("confidence", "traditional"))


def _classify_water(water_key: str, direction: str, rules: Dict) -> VastuFinding:
    spec = rules["water"][water_key]
    label = WATER_LABELS.get(water_key, water_key.replace("_", " ").title())
    if direction in spec["best"]:
        status, severity = "compliant", None
    elif direction in spec["acceptable"]:
        status, severity = "acceptable", None
    elif direction in spec["avoid"]:
        status, severity = "defect", "medium"
    else:
        status, severity = "neutral", None
    defect_id = None
    if status == "defect":
        for item, directions, did in _DEFECT_MATCHERS:
            if item == f"water:{water_key}" and direction in directions:
                defect_id = did
                break
    return VastuFinding(item=f"water:{water_key}", label=label, direction=direction,
                        status=status, expected=list(spec["best"]), severity=severity,
                        defect_id=defect_id, note="", confidence=spec.get("confidence", "traditional"))


def _classify_slope(direction: str, rules: Dict) -> VastuFinding:
    flow = rules["water"]["drainage_flow"]
    if direction in flow["best"]:
        status, severity = "compliant", None
    elif direction in flow.get("avoid", []):
        status, severity = "defect", "medium"
    else:
        status, severity = "neutral", None
    return VastuFinding(item="slope", label="Plot slope / water drainage", direction=direction,
                        status=status, expected=list(flow["best"]), severity=severity,
                        defect_id="V-D06" if status == "defect" else None,
                        note="Water should drain toward the north/east; the south-west stays highest.",
                        confidence="classical")


_SHAPE_STATUS = {
    "square": ("compliant", None, None),
    "rectangle": ("compliant", None, None),
    "gomukhi": ("compliant", None, None),
    "shermukhi": ("defect", "medium", None),
    "triangular": ("defect", "high", None),
    "irregular": ("defect", "medium", "V-D10"),
    "cut": ("defect", "medium", "V-D10"),
}


def _classify_shape(shape: str) -> Optional[VastuFinding]:
    key = shape.strip().lower()
    if key not in _SHAPE_STATUS:
        return None
    status, severity, defect_id = _SHAPE_STATUS[key]
    reason = {
        "square": "Square plots are considered the most auspicious.",
        "rectangle": "Rectangles up to 1:2 are auspicious; keep the long axis north-south.",
        "gomukhi": "Narrow front, wider rear — auspicious.",
        "shermukhi": "Wide front, narrow rear — generally avoided.",
        "triangular": "Triangular plots are avoided.",
        "irregular": "Irregular/cut plots carry a defect; check the north-east corner especially.",
        "cut": "Cut/corner-missing plots carry a defect; check the north-east corner especially.",
    }[key]
    return VastuFinding(item="plot_shape", label="Plot shape", direction=key.title(),
                        status=status, expected=["square", "rectangle", "gomukhi"],
                        severity=severity, defect_id=defect_id, note=reason,
                        confidence="classical" if key in ("square", "rectangle", "triangular") else "traditional")


def _facing_finding(direction: str, rules: Dict) -> VastuFinding:
    door = rules["main_door"]
    if direction in door["best"]:
        status = "compliant"
    elif direction in door["acceptable"]:
        status = "acceptable"
    else:
        status = "neutral"
    return VastuFinding(item="facing", label="Plot / main-door facing", direction=direction,
                        status=status, expected=list(door["best"]),
                        note="East and north facing are preferred; other facings are workable with a correct interior layout.",
                        confidence="traditional")


def assess_layout(layout: Dict[str, Any], rules: Optional[Dict] = None) -> VastuAssessment:
    """Evaluates as much of the layout as is provided; missing items are listed."""
    rules = rules or load_vastu_rules()
    findings: List[VastuFinding] = []
    assessed_rooms: Dict[str, str] = {}

    rooms = layout.get("rooms") or {}
    if isinstance(rooms, dict):
        for key, raw in rooms.items():
            if key not in ROOM_KEYS:
                continue
            direction = normalize_direction(raw)
            if not direction:
                continue
            findings.append(_classify(key, direction, rules))
            assessed_rooms[key] = direction

    assessed_water: Dict[str, str] = {}
    water = layout.get("water") or {}
    if isinstance(water, dict):
        for key, raw in water.items():
            if key not in WATER_KEYS:
                continue
            direction = normalize_direction(raw)
            if not direction:
                continue
            findings.append(_classify_water(key, direction, rules))
            assessed_water[key] = direction

    slope = normalize_direction(layout.get("slope"))
    if slope:
        findings.append(_classify_slope(slope, rules))

    shape = layout.get("plot_shape")
    if isinstance(shape, str):
        shape_finding = _classify_shape(shape)
        if shape_finding:
            findings.append(shape_finding)

    facing = normalize_direction(layout.get("facing"))
    if facing:
        findings.append(_facing_finding(facing, rules))

    # remedies from triggered defects (deduplicated, ordered by severity)
    defect_by_id = {d["id"]: d for d in rules["defects"]}
    remedies: List[Dict[str, Any]] = []
    seen: set = set()
    defect_findings = [f for f in findings if f.status == "defect"]
    defect_findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity or "medium", 1))
    for finding in defect_findings:
        if not finding.defect_id or finding.defect_id in seen:
            continue
        seen.add(finding.defect_id)
        defect = defect_by_id.get(finding.defect_id)
        if not defect:
            continue
        remedies.append({
            "defect_id": finding.defect_id,
            "pattern": defect["pattern"],
            "severity": defect.get("severity", finding.severity),
            "actions": defect["remedies"],
            "confidence": defect.get("confidence", "traditional"),
        })

    counts = {status: sum(1 for f in findings if f.status == status)
              for status in ("compliant", "acceptable", "neutral", "defect", "info")}
    scored = [f for f in findings if f.status in _POINTS]
    score = round(100.0 * sum(_POINTS[f.status] for f in scored) / len(scored), 1) if scored else None

    not_assessed = [rules["rooms"][key]["label"] for key in ROOM_KEYS if key not in assessed_rooms]
    not_assessed += [WATER_LABELS[key] for key in WATER_KEYS if key not in assessed_water]

    # order: defects by severity first, then acceptable/neutral/compliant/info
    findings.sort(key=lambda f: (0 if f.status == "defect" else 1,
                                 _SEVERITY_ORDER.get(f.severity or "medium", 1) if f.status == "defect" else 0,
                                 f.label))

    return VastuAssessment(findings=findings, score=score, counts=counts,
                           remedies=remedies, not_assessed=not_assessed,
                           sources=rules.get("sources", []))
