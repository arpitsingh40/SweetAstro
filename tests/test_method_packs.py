"""Method pack tests: loading, gating, capability-gap fallback in the payload."""

import json
from pathlib import Path

from SweetAstro.src.methods.registry import (
    format_method_lines, load_method_packs, method_for_topic, pack_problems,
)

ENABLED_PACK = {
    "version": "1.0.0",
    "slug": "test-method",
    "method": "Test Method",
    "source": {
        "teacher": "T. Teacher",
        "channel": "Test Channel",
        "confidence": "modern",
        "basis": "test basis",
        "research_note": "docs/research/test.md",
        "label": "Test Method (modern — T. Teacher)",
    },
    "enabled": True,
    "allow_quotes": True,
    "source_videos": [{"id": "abcdefghijk", "title": "Method video"}],
    "safety_rules": ["Unvalidated modern method; optional; no guarantees."],
    "topic_map": {
        "career": {
            "label": "Test Method for career",
            "formula": "lagna lord + 10th from it",
            "steps": ["Compute the 10th from the lagna lord",
                      "Compare with the running dasha lord"],
            "quote": "SECRETTRANSCRIPTQUOTE about the method",
            "locator": "00:05:00-00:05:20",
            "adapted": False,
        }
    },
}

DISABLED_PACK = {
    "version": "1.0.0",
    "slug": "disabled-method",
    "method": "Disabled Method",
    "source": {"teacher": "X", "channel": "Y", "confidence": "modern"},
    "enabled": False,
    "safety_rules": ["Unvalidated modern method."],
    "topic_map": {"marriage": {"label": "Disabled for marriage", "steps": ["n/a"]}},
}

CLASSICAL_CONFIDENCE_PACK = {
    "version": "1.0.0",
    "slug": "bad-confidence",
    "method": "Bad Confidence",
    "source": {"teacher": "X", "channel": "Y", "confidence": "classical"},
    "enabled": True,
    "safety_rules": [],
    "topic_map": {},
}


def _write_packs(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "enabled.json").write_text(json.dumps(ENABLED_PACK), encoding="utf-8")
    (root / "disabled.json").write_text(json.dumps(DISABLED_PACK), encoding="utf-8")
    (root / "broken.json").write_text("{not json", encoding="utf-8")
    return root


def test_loader_reads_packs_and_skips_invalid(tmp_path):
    root = _write_packs(tmp_path / "methods")
    packs = load_method_packs(root)
    assert {pack.slug for pack in packs} == {"test-method", "disabled-method"}
    problems = pack_problems(root)
    assert any("broken.json" in problem for problem in problems)


def test_pack_validation_requires_modern_confidence_and_safety(tmp_path):
    root = tmp_path / "methods"
    root.mkdir()
    (root / "bad.json").write_text(json.dumps(CLASSICAL_CONFIDENCE_PACK), encoding="utf-8")
    problems = pack_problems(root)
    assert any("confidence must be 'modern'" in problem for problem in problems)
    assert any("no safety_rules" in problem for problem in problems)


def test_method_for_topic_respects_enabled_flag(tmp_path):
    root = _write_packs(tmp_path / "methods")
    match = method_for_topic("career", directory=root)
    assert match is not None and match.pack.slug == "test-method"
    assert method_for_topic("marriage", directory=root) is None
    forced = method_for_topic("marriage", directory=root, include_disabled=True)
    assert forced is not None and forced.pack.slug == "disabled-method"
    assert method_for_topic("unknown-topic", directory=root) is None


def test_format_lines_are_labelled_and_exclude_quotes_by_default(tmp_path):
    root = _write_packs(tmp_path / "methods")
    match = method_for_topic("career", directory=root)
    lines = format_method_lines(match)
    joined = "\n".join(lines)
    assert "Modern method option" in joined
    assert "not classical authority" in joined
    assert "T. Teacher" in joined and "abcdefghijk" in joined
    assert "SECRETTRANSCRIPTQUOTE" not in joined

    quoted = "\n".join(format_method_lines(match, allow_quotes=True))
    assert "SECRETTRANSCRIPTQUOTE" in quoted
    assert "00:05:00-00:05:20" in quoted


def _build_payload(capability_gap: bool, unfavorable: bool = False, reason_tags=None):
    from SweetAstro.src.chat.payload import build_chart_payload
    from SweetAstro.src.consumer import answer_question

    result = answer_question(year=1995, month=5, day=15, hour=14, minute=30, second=0,
                             tz_offset=5.5, lat=28.6139, lon=77.2090,
                             question="career growth", time_reliable=True)
    return build_chart_payload(
        result, name="Ananya", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="career growth", topic="career", capability_gap=capability_gap,
        unfavorable=unfavorable, reason_tags=reason_tags,
    )


def test_payload_includes_fallback_only_on_capability_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_METHODS_DIR", str(_write_packs(tmp_path / "methods")))
    without_gap = _build_payload(capability_gap=False)
    assert "Modern method option" not in without_gap

    with_gap = _build_payload(capability_gap=True)
    assert "Modern method option" in with_gap
    assert "not classical authority" in with_gap
    assert "SECRETTRANSCRIPTQUOTE" not in with_gap


def test_payload_quotes_require_explicit_personal_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_METHODS_DIR", str(_write_packs(tmp_path / "methods")))
    monkeypatch.delenv("SWEETASTRO_METHOD_QUOTES", raising=False)
    assert "SECRETTRANSCRIPTQUOTE" not in _build_payload(capability_gap=True)

    monkeypatch.setenv("SWEETASTRO_METHOD_QUOTES", "1")
    assert "SECRETTRANSCRIPTQUOTE" in _build_payload(capability_gap=True)


def test_no_methods_dir_means_no_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_METHODS_DIR", str(tmp_path / "missing"))
    payload = _build_payload(capability_gap=True)
    assert "Modern method option" not in payload


TAGGED_PACK = {
    "version": "1.0.0",
    "slug": "reason-tagged",
    "method": "Venus remedy",
    "source": {"teacher": "T", "channel": "C", "confidence": "modern"},
    "enabled": True,
    "safety_rules": ["Unvalidated modern method; optional; no guarantees."],
    "topic_map": {
        "career": {
            "label": "Career remedy for debilitated Venus",
            "steps": ["Assess Venus condition in the chart"],
            "remedies": ["Offer white flowers on Friday"],
            "reason_tags": ["venus_debilitated"],
        }
    },
}


def _write_tagged_pack(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tagged.json").write_text(json.dumps(TAGGED_PACK), encoding="utf-8")
    return root


def test_unfavorable_reason_matched_remedy_reaches_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_METHODS_DIR", str(_write_tagged_pack(tmp_path / "methods")))

    assert "Modern method option" not in _build_payload(capability_gap=False)

    matched = _build_payload(
        capability_gap=False, unfavorable=True,
        reason_tags=["Venus (lord of H10) is Debilitated in H6"])
    assert "Modern method option" in matched
    assert "Offer white flowers on Friday" in matched
    assert "venus_debilitated" in matched

    unrelated = _build_payload(
        capability_gap=False, unfavorable=True,
        reason_tags=["Saturn occupies H10"])
    assert "Modern method option" not in unrelated

    no_reason = _build_payload(capability_gap=True)
    assert "Modern method option" not in no_reason
