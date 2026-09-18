"""
KAT (Karma Alignment Technique) module tests.

KAT is a labelled modern method (Rahul Kaushik, based on Bhrigu Nandi Nadi).
These tests enforce: correct triangle mapping, honest labelling, zero-cost
alignment options, and no guarantee language.
"""

import json
from pathlib import Path

import pytest

from SweetAstro.src.remedies.kat import (
    SOURCE_LABEL, format_kat_line, kat_alignment_for_topic, load_kat_rules,
)

RULES_PATH = Path(__file__).parent.parent / "data" / "rules" / "remedies_kat.json"


def test_rules_file_loads_and_is_tagged():
    rules = load_kat_rules()
    assert rules["version"]
    assert "KAT" in rules["method"]
    assert rules["source"]["confidence"] == "modern"
    assert "Bhrigu Nandi Nadi" in rules["source"]["basis"]
    assert rules["safety_rules"]
    assert any("never a guarantee" in rule.lower() for rule in rules["safety_rules"])


def test_triangles_are_complete_and_consistent():
    rules = load_kat_rules()
    triangles = rules["triangles"]
    assert set(triangles) == {"dharma", "artha", "kama", "moksha"}
    valid_planets = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}
    for key, triangle in triangles.items():
        assert len(triangle["houses"]) == 3
        assert triangle["planets"], key
        assert set(triangle["planets"]) <= valid_planets, key
        assert triangle["focus_note"], key
    assert triangles["artha"]["planets"] == ["Venus", "Mercury", "Saturn"]
    assert triangles["moksha"]["planets"] == ["Moon", "Mars", "Jupiter"]
    assert triangles["dharma"]["planets"] == ["Mars", "Sun", "Jupiter"]


def test_topic_mapping():
    assert kat_alignment_for_topic("career").triangle == "artha"
    assert kat_alignment_for_topic("wealth").triangle == "artha"
    assert kat_alignment_for_topic("business").triangle == "kama"
    assert kat_alignment_for_topic("spirituality").triangle == "moksha"
    assert kat_alignment_for_topic("general").triangle == "dharma"
    assert kat_alignment_for_topic("unknown_topic") is None


def test_alignment_contents_and_labelling():
    kat = kat_alignment_for_topic("career")
    assert kat.planets == ["Venus", "Mercury", "Saturn"]
    assert all(action.startswith(planet) for action, planet in zip(kat.actions, kat.planets))
    assert kat.source_label == SOURCE_LABEL
    assert "KAT" in kat.source_label and "modern" in kat.source_label
    assert kat.adapted is False


def test_adapted_topics_are_flagged():
    kat = kat_alignment_for_topic("health")
    assert kat.adapted is True
    assert "SweetAstro adaptation" in kat.adapted_note or "adapt" in kat.adapted_note.lower()


def test_obstructing_planet_note():
    with_note = kat_alignment_for_topic("career", obstructing_planet="Saturn")
    assert "Saturn" in with_note.focus_note and "blocked thread" in with_note.focus_note
    without = kat_alignment_for_topic("career", obstructing_planet="Moon")
    assert "blocked thread" not in without.focus_note


def test_format_line_is_calibrated():
    line = format_kat_line(kat_alignment_for_topic("career"))
    assert "KAT" in line
    assert "non-guaranteeing" in line
    assert "optional" in line.lower()


def test_no_positive_guarantee_language_in_module_data():
    blob = (json.dumps(load_kat_rules()) + format_kat_line(kat_alignment_for_topic("career"))).lower()
    for bad in ["guarantees results", "will give you", "assured results", "100%"]:
        assert bad not in blob


def test_consumer_answer_includes_kat_line():
    from SweetAstro.src.consumer import answer_question
    result = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question="career growth", time_reliable=True,
    )
    joined = " ".join(result.answer.alignment_actions)
    assert "KAT" in joined
    assert "Domain alignment" in joined


def test_chart_payload_includes_kat_section():
    from SweetAstro.src.chat.payload import build_chart_payload
    from SweetAstro.src.consumer import answer_question

    result = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question="career growth", time_reliable=True,
    )
    payload = build_chart_payload(
        result, name="Test", dob="1995-05-15", tob="14:30:00", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="career growth", topic="career",
    )
    assert "KAT domain alignment" in payload
    assert "Rahul Kaushik" in payload
    assert "never as a guarantee" in payload


def test_classical_rule_catalog_skips_kat_file():
    from SweetAstro.src.rules.loader import RuleCatalog
    catalog = RuleCatalog()
    loaded = catalog.load_from_directory(RULES_PATH.parent)
    assert loaded == 52
    assert all(rule.rule_id.startswith("MAR-") for rule in catalog.rules.values())
