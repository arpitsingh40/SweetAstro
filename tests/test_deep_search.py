"""Reason-tag vocabulary + deep-search pipeline tests (offline)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from SweetAstro.src.methods.reasons import (
    canonical_reason_tags, promise_reason_tags, reason_overlap,
)
from SweetAstro.src.methods.registry import method_for_topic
from SweetAstro.src.research_pipeline.deep_search import build_query, deep_search
from SweetAstro.src.research_pipeline.extract import load_candidates
from SweetAstro.src.research_pipeline.fetch import search_videos

VTT_FIXTURE = """WEBVTT

00:00:10.000 --> 00:00:20.000
For Venus debilitated in the seventh house, offer white flowers on Friday.

00:00:20.000 --> 00:00:30.000
This strengthens Venus and softens the marriage delay.
"""


def test_reason_tags_align_engine_factors_and_video_tags():
    engine = set(canonical_reason_tags([
        "Venus (lord of H7) is Debilitated in H6",
        "Saturn occupies H7",
    ]))
    video = set(canonical_reason_tags(["venus_debilitated", "saturn in 7th house"]))
    assert "venus_debilitated" in engine
    assert "venus_debilitated" in video
    assert {"saturn", "saturn_house_7"} <= engine
    assert {"saturn", "saturn_house_7"} <= video
    assert engine & video
    assert reason_overlap(["Venus debilitated"], ["venus_debilitated"]) >= 1
    assert canonical_reason_tags([]) == []


def test_promise_reason_tags_only_when_unfavourable():
    weak = SimpleNamespace(level="Weak", limiting_factors=["Venus (lord of H7) is Debilitated in H6"])
    partial = SimpleNamespace(level="Partial", limiting_factors=["Saturn occupies H7"])
    supported = SimpleNamespace(level="Supported", limiting_factors=[])
    assert "venus_debilitated" in promise_reason_tags(weak)
    assert "saturn_house_7" in promise_reason_tags(partial)
    assert promise_reason_tags(supported) == []
    empty = SimpleNamespace(level="Weak", limiting_factors=[])
    assert promise_reason_tags(empty) == ["weak_promise"]


def test_registry_prefers_reason_matched_entry(tmp_path):
    tagged = {
        "slug": "tagged-pack", "method": "Tagged", "enabled": True,
        "source": {"teacher": "T", "channel": "C", "confidence": "modern"},
        "safety_rules": ["Unvalidated modern method."],
        "topic_map": {
            "marriage": {
                "label": "Venus remedy", "steps": ["Offer white flowers on Friday"],
                "reason_tags": ["venus_debilitated"],
            }
        },
    }
    generic = {
        "slug": "generic-pack", "method": "Generic", "enabled": True,
        "source": {"teacher": "T", "channel": "C", "confidence": "modern"},
        "safety_rules": ["Unvalidated modern method."],
        "topic_map": {"marriage": {"label": "General marriage method", "steps": ["step"]}},
    }
    root = tmp_path / "methods"
    root.mkdir()
    (root / "tagged.json").write_text(json.dumps(tagged), encoding="utf-8")
    (root / "generic.json").write_text(json.dumps(generic), encoding="utf-8")

    matched = method_for_topic("marriage", directory=root,
                               reason_tags=["Venus lord of H7 is Debilitated in H6"])
    assert matched is not None and matched.pack.slug == "tagged-pack"

    unmatched = method_for_topic("marriage", directory=root,
                                 reason_tags=["Saturn occupies H10"])
    assert unmatched is not None and unmatched.pack.slug == "generic-pack"

    no_reason = method_for_topic("marriage", directory=root)
    assert no_reason is not None and no_reason.pack.slug == "generic-pack"


def _fake_searcher(query, limit):
    return [("videoaaaaaa", "Venus remedies for marriage", "Test Channel")]


def _fake_extractor(url, outdir):
    (outdir / "videoaaaaaa.en.vtt").write_text(VTT_FIXTURE, encoding="utf-8")
    return {
        "id": "videoaaaaaa", "title": "Venus remedies for marriage",
        "channel": "Test Channel", "channel_id": "UC1", "upload_date": "20260101",
        "duration": 60.0, "view_count": 10, "description": "desc",
        "webpage_url": url,
        "subtitles": {"en": [{"ext": "vtt"}]}, "automatic_captions": {},
    }


class _FakeClient:
    def complete_json(self, messages, **kwargs):
        return {"claims": [{
            "claim": "For Venus debilitated in the seventh house, offer white flowers on Friday.",
            "target": "marriage",
            "kind": "remedy",
            "steps": ["Offer white flowers on Friday"],
            "remedies": ["White flowers offered on Friday"],
            "reason_tags": ["venus_debilitated", "seventh house"],
            "quote": "For Venus debilitated in the seventh house, offer white flowers on Friday.",
            "start": "00:10",
            "end": "00:20",
            "confidence": "medium",
        }]}


def test_search_videos_uses_injected_searcher():
    calls = {}

    def searcher(query, limit):
        calls["query"] = query
        calls["limit"] = limit
        return [("videoaaaaaa", "Title", "Channel")]

    results = search_videos("venus remedy", limit=3, searcher=searcher)
    assert results == [("videoaaaaaa", "Title", "Channel")]
    assert calls == {"query": "venus remedy", "limit": 3}


def test_build_query_is_search_friendly():
    rich = build_query("marriage", "Venus (lord of H7) is Debilitated in H6")
    assert "venus" in rich and "debilitated" in rich
    assert "7th lord" in rich
    assert "marriage" in rich and "remedy" in rich
    compact = build_query("marriage", "Venus (lord of H7) is Debilitated in H6",
                          compact=True)
    assert "7th lord" not in compact
    assert "venus" in compact and "debilitated" in compact


def test_deep_search_falls_back_to_compact_query(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_VIDEO_RESEARCH_DIR", str(tmp_path / "videos"))
    seen = []

    def searcher(query, limit):
        seen.append(query)
        if len(seen) == 1:
            return []
        return [("videoaaaaaa", "Venus remedies", "Test Channel")]

    outcome = deep_search("marriage", "Venus (lord of H7) is Debilitated in H6",
                          limit=1, searcher=searcher, extractor=_fake_extractor,
                          client=_FakeClient(), library_search=lambda q, n: [])
    assert len(seen) == 2
    assert outcome.videos and outcome.videos[0][0] == "videoaaaaaa"
    assert outcome.query == seen[1]


def test_deep_search_runs_full_offline_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_VIDEO_RESEARCH_DIR", str(tmp_path / "videos"))
    outcome = deep_search(
        "marriage", "Venus (lord of H7) is Debilitated in H6",
        limit=1, searcher=_fake_searcher, extractor=_fake_extractor,
        client=_FakeClient(), library_search=lambda q, n: [],
    )
    assert outcome.query == build_query("marriage", "Venus (lord of H7) is Debilitated in H6")
    assert "remedy" in outcome.query and "jyotish" in outcome.query
    assert "venus_debilitated" in outcome.reason_tags
    assert outcome.videos and outcome.videos[0][0] == "videoaaaaaa"
    assert outcome.candidates
    matched = outcome.matched_remedies
    assert matched and matched[0].candidate.kind == "remedy"
    assert "venus_debilitated" in matched[0].candidate.reason_tags
    lines = outcome.summary_lines()
    assert any("Reason-matched remedies" in line for line in lines)
    assert any("videoaaaaaa" in line for line in lines)

    stored = load_candidates()
    assert any(claim.candidate_id == outcome.candidates[0].candidate_id for claim in stored)


def test_deep_search_propagates_search_errors(tmp_path, monkeypatch):
    from SweetAstro.src.research_pipeline.fetch import ResearchFetchError

    monkeypatch.setenv("SWEETASTRO_VIDEO_RESEARCH_DIR", str(tmp_path / "videos"))

    def failing_searcher(query, limit):
        raise ResearchFetchError("network down")

    with pytest.raises(ResearchFetchError):
        deep_search("marriage", "reason", limit=1, searcher=failing_searcher,
                    extractor=_fake_extractor, client=_FakeClient())
