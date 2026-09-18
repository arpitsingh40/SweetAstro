"""Extraction and evidence-gate tests (offline; fake LLM client, fake library)."""

import json
from pathlib import Path

import pytest

from SweetAstro.src.research_pipeline.captions import Cue
from SweetAstro.src.research_pipeline.extract import (
    CandidateClaim, dual_pass_extract, extract_claims, load_candidates,
    save_candidates,
)
from SweetAstro.src.research_pipeline.gate import (
    evaluate_candidates, format_gate_results,
)
from SweetAstro.src.research_pipeline.store import VideoRecord, VideoStore

CUE_TEXT = (
    "Take the sign occupied by the Atmakaraka and count twelve signs forward. "
    "That sign becomes the Karakamsha and its lord shows the profession."
)


def _record(video_id: str = "abcdefghijk") -> VideoRecord:
    return VideoRecord(video_id=video_id, title="Jaimini Lesson",
                       channel="Test Channel", caption_kind="auto", caption_lang="en")


def _cues() -> list:
    return [
        Cue(start=60.0, end=70.0, text="Now about the Karakamsha method."),
        Cue(start=70.0, end=95.0, text=CUE_TEXT),
    ]


def _claim_payload(**overrides):
    base = {
        "claim": "The Karakamsha is twelve signs forward from the Atmakaraka sign.",
        "target": "career",
        "kind": "calculation",
        "formula": "AK sign + 12 signs",
        "steps": ["Find Atmakaraka", "Count 12 signs forward"],
        "examples": ["Sun as AK in Aries gives Karakamsha in Aries"],
        "quote": "Take the sign occupied by the Atmakaraka and count twelve signs forward",
        "start": "01:10",
        "end": "01:35",
        "confidence": "medium",
    }
    base.update(overrides)
    return base


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete_json(self, messages, **kwargs):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return {"claims": []}


def test_extract_keeps_only_verbatim_supported_claims():
    hallucinated = _claim_payload(quote="This sentence is not in the transcript at all.")
    outside_window = _claim_payload(claim="A distinct timing claim transcribed early in the video.",
                                    quote="Now about the Karakamsha method.",
                                    start="00:01", end="00:02")
    good = _claim_payload()
    client = _FakeClient([{"claims": [good, hallucinated, outside_window]}])

    claims = extract_claims(_record(), _cues(), client, max_chunks=1)
    assert len(claims) == 2
    assert all(claim.video_id == "abcdefghijk" for claim in claims)

    karakamsha = next(c for c in claims if c.claim.startswith("The Karakamsha"))
    assert karakamsha.kind == "calculation"
    assert karakamsha.locator == "00:01:10-00:01:35"
    assert karakamsha.formula and karakamsha.steps
    assert karakamsha.candidate_id.startswith("VC-")

    early = next(c for c in claims if "Now about" in c.quote)
    assert early.start <= 60.0


def test_extract_drops_out_of_range_timestamps_to_chunk_bounds():
    claim = _claim_payload(start="99:00", end="99:30")
    client = _FakeClient([{"claims": [claim]}])
    claims = extract_claims(_record(), _cues(), client, max_chunks=1)
    assert claims and claims[0].end <= 95.0


def test_quote_support_tolerates_rolling_caption_duplicates():
    from SweetAstro.src.research_pipeline.extract import _quote_supported

    transcript = "a b a b c d c d e f"
    assert _quote_supported("a b c d e f", transcript)
    assert not _quote_supported("totally unrelated words about planets", transcript)


def test_extract_carries_reason_tags_and_remedies():
    remedy = _claim_payload(
        kind="remedy",
        remedies=["Offer white flowers on Friday"],
        reason_tags=["venus_debilitated", "seventh house"],
    )
    claims = extract_claims(_record(), _cues(), _FakeClient([{"claims": [remedy]}]),
                            max_chunks=1)
    assert len(claims) == 1
    assert claims[0].kind == "remedy"
    assert claims[0].remedies == ("Offer white flowers on Friday",)
    assert claims[0].reason_tags == ("venus_debilitated", "seventh house")

    unknown_kind = extract_claims(
        _record(), _cues(),
        _FakeClient([{"claims": [_claim_payload(kind="advice")]}]), max_chunks=1)
    assert unknown_kind[0].kind == "rule"


def test_dual_pass_intersection_keeps_only_consistent_claims():
    stable = _claim_payload()
    unstable = _claim_payload(claim="A different claim only pass two produces here.")
    client = _FakeClient([
        {"claims": [stable]},
        {"claims": [stable, unstable]},
    ])
    claims = dual_pass_extract(_record(), _cues(), client, max_chunks=1)
    assert len(claims) == 1
    assert claims[0].passes == 2
    assert "Karakamsha" in claims[0].claim


def test_dual_pass_survives_reworded_claim_with_same_quote():
    reworded = _claim_payload(
        claim="Count forward twelve signs from the Atmakaraka to reach the Karakamsha.")
    client = _FakeClient([
        {"claims": [_claim_payload()]},
        {"claims": [reworded]},
    ])
    claims = dual_pass_extract(_record(), _cues(), client, max_chunks=1)
    assert len(claims) == 1
    assert claims[0].passes == 2


def test_gate_clusters_reworded_claims_across_videos():
    first = extract_claims(_record("videoaaaaaa"), _cues(),
                           _FakeClient([{"claims": [_claim_payload()]}]), max_chunks=1)[0]
    reworded = extract_claims(
        _record("videobbbbbb"), _cues(),
        _FakeClient([{"claims": [_claim_payload(
            claim="The Karakamsha lies twelve signs ahead of the Atmakaraka occupation sign.")]}]),
        max_chunks=1)[0]
    assert first.key != reworded.key
    results = evaluate_candidates([first, reworded], library_search=lambda q, n: [])
    assert len(results) == 1
    assert results[0].verdict == "modern_candidate"
    assert results[0].convergence == 2


def test_candidates_roundtrip_and_dedupe(tmp_path):
    path = tmp_path / "candidates.jsonl"
    claims = extract_claims(_record(), _cues(), _FakeClient([{"claims": [_claim_payload()]}]),
                            max_chunks=1)
    added, skipped = save_candidates(claims, path)
    assert (added, skipped) == (1, 0)
    again, skipped = save_candidates(claims, path)
    assert (again, skipped) == (0, 1)
    loaded = load_candidates(path)
    assert len(loaded) == 1
    assert loaded[0].candidate_id == claims[0].candidate_id


def test_gate_classifies_by_convergence_and_classical_support():
    first = extract_claims(_record("videoaaaaaa"), _cues(),
                           _FakeClient([{"claims": [_claim_payload()]}]), max_chunks=1)[0]
    second = extract_claims(_record("videobbbbbb"), _cues(),
                            _FakeClient([{"claims": [_claim_payload()]}]), max_chunks=1)[0]
    single = extract_claims(_record("videocccccc"), _cues(),
                            _FakeClient([{"claims": [_claim_payload(
                                claim="A unique single-source claim about Rahu here.",
                                quote="Now about the Karakamsha method.")]}]), max_chunks=1)[0]

    results = evaluate_candidates([first, second, single], library_search=lambda q, n: [])
    verdicts = {result.candidate.video_id: result.verdict for result in results}
    assert verdicts["videoaaaaaa"] == "modern_candidate"
    assert verdicts["videocccccc"] == "quarantine"

    third = extract_claims(_record("videodddddd"), _cues(),
                           _FakeClient([{"claims": [_claim_payload(
                               claim="A unique single-source claim about Rahu here.",
                               quote="Now about the Karakamsha method.")]}]), max_chunks=1)[0]
    classical = evaluate_candidates(
        [single, third],
        library_search=lambda q, n: ["Jaimini Sutras (trans. B. Suryanarain Rao, 1955), leaf 12 (score 7.5)"])
    assert classical[0].verdict == "classical_candidate"
    assert classical[0].classical_hits


def test_gate_report_lines_include_links_and_hits():
    claims = extract_claims(_record(), _cues(), _FakeClient([{"claims": [_claim_payload()]}]),
                            max_chunks=1)
    results = evaluate_candidates(
        claims, library_search=lambda q, n: ["Phaladeepika (1937), leaf 9 (score 5.0)"])
    lines = format_gate_results(results, {"abcdefghijk": _record()})
    joined = "\n".join(lines)
    assert "[classical_candidate]" in joined
    assert "&t=70s" in joined
    assert "Phaladeepika" in joined


def test_gate_counts_distinct_channels_not_repeat_videos():
    def _candidate(video_id: str) -> CandidateClaim:
        return CandidateClaim(
            candidate_id=f"VC-{video_id}", video_id=video_id, claim="Shared claim text.",
            target="career", kind="rule", quote="q", locator="00:01-00:02",
            start=1.0, end=2.0, passes=2)

    pair = [_candidate("videoaaaaaa"), _candidate("videobbbbbb")]
    same_channel = {v: VideoRecord(video_id=v, channel="One Channel") for v in
                    ("videoaaaaaa", "videobbbbbb")}
    results = evaluate_candidates(pair, library_search=lambda q, n: [],
                                  records=same_channel)
    assert results[0].verdict == "quarantine"
    assert results[0].convergence == 1

    cross_channel = {
        "videoaaaaaa": VideoRecord(video_id="videoaaaaaa", channel="One Channel"),
        "videobbbbbb": VideoRecord(video_id="videobbbbbb", channel="Other Channel"),
    }
    results = evaluate_candidates(pair, library_search=lambda q, n: [],
                                  records=cross_channel)
    assert results[0].verdict == "modern_candidate"
    assert results[0].convergence == 2


def test_zero_candidates_is_reported_not_an_error():
    client = _FakeClient([{"claims": []}, {"claims": []}])
    assert dual_pass_extract(_record(), _cues(), client, max_chunks=1) == []
    assert evaluate_candidates([], library_search=lambda q, n: []) == []


def test_candidate_claim_roundtrip_dict():
    claim = CandidateClaim(
        candidate_id="VC-test", video_id="abcdefghijk", claim="C", target="marriage",
        kind="rule", quote="q", locator="00:01-00:02", start=1.0, end=2.0,
        steps=("one",), examples=("ex",), confidence="high", passes=2,
        evidence={"note": "x"})
    restored = CandidateClaim.from_dict(json.loads(json.dumps(claim.to_dict())))
    assert restored == claim


def test_pack_skeleton_is_disabled_and_registry_compatible(tmp_path):
    from SweetAstro.src.methods.registry import load_method_packs, method_for_topic
    from SweetAstro.src.research_pipeline.pack_writer import write_pack_skeleton

    claims = extract_claims(_record(), _cues(), _FakeClient([{"claims": [_claim_payload()]}]),
                            max_chunks=1)
    claims[0].passes = 2
    claims[0].remedies = ("Offer white flowers on Friday",)
    claims[0].reason_tags = ("venus_debilitated",)
    path = write_pack_skeleton(claims[0], _record(), "karakamsha-career",
                               directory=tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["enabled"] is False
    assert data["source"]["confidence"] == "modern"
    assert data["safety_rules"]
    assert data["evidence"]["candidate_id"] == claims[0].candidate_id
    entry = data["topic_map"]["career"]
    assert entry["remedies"] == ["Offer white flowers on Friday"]
    assert "venus_debilitated" in entry["reason_tags"]

    packs = load_method_packs(tmp_path)
    assert [pack.slug for pack in packs] == ["karakamsha-career"]
    assert method_for_topic("career", directory=tmp_path) is None
    assert method_for_topic("career", directory=tmp_path,
                            include_disabled=True) is None
    forced = method_for_topic("career", directory=tmp_path, include_disabled=True,
                              reason_tags=["venus_debilitated"])
    assert forced is not None and forced.pack.enabled is False


def test_pack_skeleton_refuses_duplicates_and_bad_slugs(tmp_path):
    from SweetAstro.src.research_pipeline.pack_writer import (
        PackWriterError, write_pack_skeleton,
    )

    claim = CandidateClaim(
        candidate_id="VC-x", video_id="abcdefghijk", claim="C", target="career",
        kind="rule", quote="q", locator="00:01-00:02", start=1.0, end=2.0)
    write_pack_skeleton(claim, _record(), "valid-slug", directory=tmp_path)
    with pytest.raises(PackWriterError, match="already exists"):
        write_pack_skeleton(claim, _record(), "valid-slug", directory=tmp_path)
    with pytest.raises(PackWriterError, match="slug"):
        write_pack_skeleton(claim, _record(), "Bad Slug!", directory=tmp_path)
