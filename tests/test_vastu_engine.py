"""
Vastu engine tests: rule evaluation, scoring, remedies, and chat routing.
"""

import json
from pathlib import Path

import pytest

from SweetAstro.src.core.vastu import (
    ROOM_KEYS, assess_layout, load_vastu_rules, normalize_direction,
)


# ---------------------------------------------------------------- direction normalization

def test_normalize_direction_aliases():
    assert normalize_direction("NE") == "North-East"
    assert normalize_direction("north east") == "North-East"
    assert normalize_direction("south-west") == "South-West"
    assert normalize_direction("SW") == "South-West"
    assert normalize_direction("middle") == "Center"
    assert normalize_direction("somewhere") is None
    assert normalize_direction(None) is None


def test_room_keys_match_rules_file():
    rules = load_vastu_rules()
    assert set(ROOM_KEYS) == set(rules["rooms"])


# ---------------------------------------------------------------- assessment

def test_all_compliant_scores_100():
    layout = {
        "rooms": {"puja": "North-East", "kitchen": "South-East", "master_bedroom": "South-West",
                  "toilet": "North-West", "staircase": "South"},
        "water": {"underground_tank": "North-East", "overhead_tank": "South-West"},
        "slope": "North-East", "plot_shape": "square", "facing": "East",
    }
    assessment = assess_layout(layout)
    assert assessment.score == 100.0
    assert assessment.counts["defect"] == 0
    assert assessment.counts["compliant"] >= 6


def test_defects_detected_with_ids_and_remedies():
    layout = {"rooms": {"kitchen": "North-East", "toilet": "North-East",
                        "master_bedroom": "South-East", "staircase": "North-East"},
              "water": {"overhead_tank": "North-East"}}
    assessment = assess_layout(layout)
    defect_ids = {f.defect_id for f in assessment.findings if f.status == "defect"}
    assert {"V-D02", "V-D01", "V-D03", "V-D09", "V-D04"} <= defect_ids
    assert assessment.findings[0].status == "defect"          # defects sorted first
    assert assessment.findings[0].severity == "high"
    remedy_ids = {r["defect_id"] for r in assessment.remedies}
    assert "V-D01" in remedy_ids and "V-D02" in remedy_ids
    assert assessment.score is not None and assessment.score < 60


def test_slope_and_shape_defects():
    assessment = assess_layout({"slope": "South-West", "plot_shape": "triangular"})
    defect_ids = {f.defect_id for f in assessment.findings if f.status == "defect"}
    assert "V-D06" in defect_ids
    assert any(f.item == "plot_shape" and f.status == "defect" for f in assessment.findings)


def test_unmapped_direction_is_neutral():
    assessment = assess_layout({"rooms": {"garage": "South"}})
    assert len(assessment.findings) == 1
    assert assessment.findings[0].status == "neutral"
    assert assessment.findings[0].severity is None


def test_not_assessed_lists_missing_items():
    assessment = assess_layout({"rooms": {"kitchen": "South-East"}})
    assert "Master bedroom" in assessment.not_assessed
    assert "Underground water tank" in assessment.not_assessed
    assert "Overhead water tank" in assessment.not_assessed
    assert "Kitchen (fire)" not in assessment.not_assessed


def test_empty_layout_scores_none():
    assessment = assess_layout({})
    assert assessment.score is None
    assert not assessment.findings
    assert assessment.not_assessed


def test_to_dict_serializable_and_safe():
    assessment = assess_layout({"rooms": {"toilet": "North-East"}})
    blob = json.dumps(assessment.to_dict())
    assert "V-D01" in blob
    lowered = blob.lower()
    assert "demolish the" not in lowered


# ---------------------------------------------------------------- chat routing

class _FakeClient:
    def __init__(self, extractions, reply="🏠 Vastu Overview\n\nAssessment ready."):
        self.extractions = list(extractions)
        self.reply = reply
        self.stream_calls = []

    def complete_json(self, messages, **kwargs):
        return self.extractions.pop(0) if self.extractions else {}

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        for word in self.reply.split(" "):
            yield {"type": "content", "text": word + " "}


def _events(orch, session_id, message):
    return list(orch.handle_message(session_id, message))


def test_orchestrator_vastu_flow():
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    extraction = {"vastu_rooms": {"kitchen": "South-East", "toilet": "North-West"},
                  "vastu_slope": "South-West"}
    client = _FakeClient([extraction])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "v1", "Please check the vastu of my house.")
    types = [e.type for e in events]
    assert "meta" in types and "done" in types

    meta = next(e for e in events if e.type == "meta")
    assert meta.data["mode"] == "vastu"
    assert meta.data["birth_data"]["defect_count"] == 1   # slope defect

    payload = client.stream_calls[-1][1]["content"]
    assert payload.startswith("=== VASTU ASSESSMENT")
    assert "Kitchen" in payload and "South-East" in payload

    done = next(e for e in events if e.type == "done")
    assert "Vastu Overview" in done.data["content"]
    assert done.data["mode"] == "vastu"


def test_orchestrator_vastu_asks_for_layout():
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    client = _FakeClient([{}], reply="Which directions are your kitchen and bedrooms in?")
    orch = ChatOrchestrator(client=client, store=SessionStore())

    events = _events(orch, "v2", "Tell me about vastu.")
    assert "meta" not in [e.type for e in events]
    guide_system = client.stream_calls[0][0]["content"]
    assert "room directions" in guide_system


def test_orchestrator_vastu_accumulates_followups():
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    client = _FakeClient([
        {"vastu_rooms": {"kitchen": "South-East"}},
        {"vastu_rooms": {"toilet": "North-East"}},
    ])
    orch = ChatOrchestrator(client=client, store=SessionStore())

    _events(orch, "v3", "My kitchen is in the south-east — vastu check.")
    events = _events(orch, "v3", "And the toilet is in the north-east.")
    payload = client.stream_calls[-1][1]["content"]
    assert "kitchen=South-East" in payload and "toilet=North-East" in payload
    meta = next(e for e in events if e.type == "meta")
    assert meta.data["birth_data"]["rooms_assessed"] == 2
    assert meta.data["birth_data"]["defect_count"] >= 1
