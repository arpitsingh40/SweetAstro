"""
Validation tests for the Vastu knowledge base data file (data/rules/vastu_rules.json).

These tests guard the data contract the planned Vastu engine will rely on:
valid directions, no self-contradictory placements, unique defect IDs, safe
remedies, and complete construction/muhurta links.
"""

import json
from pathlib import Path

import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "rules" / "vastu_rules.json"
VASTU = json.loads(DATA_PATH.read_text(encoding="utf-8"))

VALID_DIRECTIONS = {"North", "North-East", "East", "South-East", "South",
                    "South-West", "West", "North-West", "Center"}
VALID_CONFIDENCE = {"classical", "traditional", "modern", "verify"}
CORE_DIRECTIONS = VALID_DIRECTIONS - {"Center"}


def test_schema_basics():
    assert VASTU["version"]
    assert VASTU["domain"] == "Vastu"
    assert len(VASTU["sources"]) >= 8
    assert VASTU["safety_rules"]
    assert any("demolition" in rule.lower() for rule in VASTU["safety_rules"])


def test_directions_complete_and_tagged():
    directions = VASTU["directions"]
    assert set(directions) == VALID_DIRECTIONS
    for name, info in directions.items():
        assert info["element"], name
        assert info["deity"], name
        assert info["qualities"], name
        assert info["confidence"] in VALID_CONFIDENCE, name
        assert isinstance(info.get("planet"), (str, type(None))), name


def test_room_placements_are_consistent():
    rooms = VASTU["rooms"]
    assert len(rooms) >= 12
    for key, room in rooms.items():
        assert room["label"], key
        for field in ("best", "acceptable", "avoid"):
            assert isinstance(room.get(field), list), f"{key}/{field}"
            for direction in room[field]:
                assert direction in VALID_DIRECTIONS, f"{key}/{field}/{direction}"
        assert not (set(room["best"]) & set(room["avoid"])), f"{key}: best intersects avoid"
        assert not (set(room["acceptable"]) & set(room["avoid"])), f"{key}: acceptable intersects avoid"
        assert room["notes"], key
        assert room["confidence"] in VALID_CONFIDENCE, key


def test_expected_core_rooms_present():
    for key in ("puja", "kitchen", "master_bedroom", "toilet", "staircase", "store"):
        assert key in VASTU["rooms"]
    assert VASTU["rooms"]["puja"]["best"] == ["North-East"]
    assert VASTU["rooms"]["kitchen"]["best"] == ["South-East"]
    assert VASTU["rooms"]["master_bedroom"]["best"] == ["South-West"]
    assert "North-East" in VASTU["rooms"]["toilet"]["avoid"]


def test_water_and_construction_links():
    water = VASTU["water"]
    assert water["underground_tank"]["best"] == ["North-East"]
    assert "North-East" in water["overhead_tank"]["avoid"]
    assert {"bhoomi_puja", "shilanyasa", "griha_pravesh"} <= set(VASTU["construction_muhurta"])
    assert "griha_pravesh" in VASTU["construction_muhurta"]["griha_pravesh"]["use"]


def test_defects_unique_and_safe():
    defects = VASTU["defects"]
    assert len(defects) >= 15
    ids = [d["id"] for d in defects]
    assert len(ids) == len(set(ids)), "duplicate defect IDs"
    for defect in defects:
        assert defect["id"].startswith("V-D")
        assert defect["severity"] in {"low", "medium", "high"}
        assert defect["remedies"], defect["id"]
        blob = " ".join(defect["remedies"]).lower()
        assert "demolish the" not in blob, defect["id"]
        assert defect["confidence"] in VALID_CONFIDENCE


def test_planetary_directions_and_ayadi_status():
    planets = VASTU["planetary_directions"]
    for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"):
        assert planet in planets
        assert planets[planet] in CORE_DIRECTIONS, planet
    assert VASTU["ayadi"]["status"].startswith("formulas disabled")
    assert len(VASTU["ayadi"]["limbs"]) == 6


def test_classical_rule_catalog_skips_vastu_file():
    from SweetAstro.src.rules.loader import RuleCatalog
    catalog = RuleCatalog()
    loaded = catalog.load_from_directory(DATA_PATH.parent)
    assert loaded == 52  # the classical MAR-* rules only
    assert all(rule.rule_id.startswith("MAR-") for rule in catalog.rules.values())
