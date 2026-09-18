"""Period alignment tests: rules integrity, direction lines, wiring, labels."""

from datetime import datetime
from types import SimpleNamespace

from SweetAstro.src.methods.reasons import canonical_reason_tags, dasha_reason_tags
from SweetAstro.src.remedies.period import (
    SOURCE_LABEL, format_period_line, load_period_rules, period_alignment,
    period_alignment_lines,
)

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")


def test_period_rules_cover_all_planets_and_are_labelled_modern():
    rules = load_period_rules()
    assert rules["source"]["confidence"] == "modern"
    assert "modern" in rules["source"]["label"].lower()
    assert rules["safety_rules"]
    for planet in PLANETS:
        entry = rules["planets"][planet]
        assert entry["focus"].strip()
        assert entry["avoid"].strip()
        assert entry["domains"].strip()


def test_period_alignment_lines_cover_md_ad_pd_and_labels():
    promise = SimpleNamespace(level="Weak", limiting_factors=[
        "Venus (lord of H7) is Debilitated in H6"])
    upcoming = [SimpleNamespace(level="AD", lord="Saturn",
                                start_date=datetime(2026, 11, 1))]
    lines = period_alignment_lines("Sun / Venus / Saturn", promise=promise,
                                   upcoming=upcoming)
    joined = "\n".join(lines)
    assert "Mahadasha (life chapter) — Sun" in joined
    assert "Antardasha (active channel) — Venus" in joined
    assert "Pratyantardasha (immediate window) — Saturn" in joined
    assert "Obstructing thread: Venus" in joined
    assert "Saturday" in joined
    assert "2026-11-01" in joined and "Saturn Antardasha" in joined
    assert "never as classical authority" in joined
    assert "optional" in joined.lower()


def test_period_alignment_is_deterministic_and_bounded():
    first = period_alignment_lines("Sun / Venus / Saturn")
    second = period_alignment_lines("Sun / Venus / Saturn")
    assert first == second
    assert len(first) <= 12
    assert all(len(line) < 400 for line in first)


def test_unresolved_periods_return_nothing():
    assert period_alignment("— / — / —") is None
    assert period_alignment("") is None
    assert period_alignment("Sun / Venus") is None
    assert period_alignment_lines("Unknown / Venus / Saturn") == []


def test_uncertain_birth_time_gets_reduced_confidence_note():
    lines = period_alignment_lines("Sun / Venus / Saturn", time_reliable=False)
    assert any("lower confidence" in line for line in lines)


def test_format_period_line_is_short_and_labelled():
    alignment = period_alignment("Sun / Venus / Saturn",
                                 promise=SimpleNamespace(level="Weak", limiting_factors=["Saturn in H7"]))
    line = format_period_line(alignment)
    assert "Period alignment" in line
    assert "Sun MD / Venus AD / Saturn PD" in line
    assert "Obstructing thread: Saturn" in line
    assert "no guarantees" in line.lower()
    assert len(line) < 400


def test_consumer_answer_includes_period_alignment_line():
    from SweetAstro.src.consumer import answer_question

    result = answer_question(year=1995, month=5, day=15, hour=14, minute=30, second=0,
                             tz_offset=5.5, lat=28.6139, lon=77.2090,
                             question="career growth", time_reliable=True)
    actions = " | ".join(result.answer.alignment_actions)
    assert "Period alignment" in actions
    assert "modern" in actions.lower()


def test_payload_includes_period_alignment_block():
    from SweetAstro.src.chat.payload import build_chart_payload
    from SweetAstro.src.consumer import answer_question

    result = answer_question(year=1995, month=5, day=15, hour=14, minute=30, second=0,
                             tz_offset=5.5, lat=28.6139, lon=77.2090,
                             question="career growth", time_reliable=True)
    payload = build_chart_payload(
        result, name="Ananya", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="career growth", topic="career",
    )
    assert "Period alignment (modern method" in payload
    assert "Mahadasha (life chapter)" in payload
    assert "Weekday anchors" in payload
    assert "never as classical authority" in payload


def test_dasha_reason_tags_round_trip():
    tags = dasha_reason_tags("Saturn", "Venus", "Rahu")
    assert tags == ["dasha_lord_saturn", "antardasha_venus", "pratyantardasha_rahu"]
    canonical = set(canonical_reason_tags(["saturn mahadasha alignment conduct"]))
    assert "dasha_lord_saturn" in canonical
    assert set(canonical_reason_tags(["venus antardasha delay"])) & {"antardasha_venus"}


def test_deep_search_query_mentions_the_period_level():
    from SweetAstro.src.research_pipeline.deep_search import build_query

    query = build_query("marriage", "saturn mahadasha alignment conduct")
    assert "saturn" in query and "mahadasha" in query
    assert SOURCE_LABEL.startswith("Period alignment")
