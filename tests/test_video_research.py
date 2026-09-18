"""Video research pipeline tests: caption parsing, store round-trip, fetch idempotency."""

import json
from pathlib import Path

import pytest

from SweetAstro.src.research_pipeline.captions import (
    CaptionError, format_timestamp, parse_timestamp, parse_vtt, quote_range,
)
from SweetAstro.src.research_pipeline.fetch import (
    ResearchFetchError, fetch_videos, normalize_target, video_id_from_url,
)
from SweetAstro.src.research_pipeline.store import VideoStore, video_store_dir

VTT_FIXTURE = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.000
<c>Welcome to the class.</c>

00:00:04.000 --> 00:00:07.000
Welcome to the class.

00:00:07.000 --> 00:00:12.500
Today we discuss the calculation of
the chara dasha periods.

NOTE this is a note block

00:00:12.500 --> 00:00:18.000
Take the sign of the lagna and count backwards.
"""


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_VIDEO_RESEARCH_DIR", str(tmp_path / "videos"))
    yield tmp_path / "videos"


def _fake_extractor(vtt_text: str, write_vtt: bool = True, video_id: str = "abcdefghijk"):
    def extractor(url: str, outdir: Path):
        if write_vtt:
            (outdir / f"{video_id}.en.vtt").write_text(vtt_text, encoding="utf-8")
        return {
            "id": video_id,
            "title": "Chara Dasha Explained",
            "channel": "Test Jyotish Channel",
            "channel_id": "UC-test",
            "upload_date": "20260115",
            "duration": 120.0,
            "view_count": 1234,
            "description": "A test video description.",
            "webpage_url": url,
            "subtitles": {"en": [{"ext": "vtt"}]},
            "automatic_captions": {},
        }
    return extractor


def test_parse_vtt_collapses_repeats_and_strips_markup():
    cues = parse_vtt(VTT_FIXTURE)
    assert len(cues) == 3
    assert cues[0].text == "Welcome to the class."
    assert cues[0].start == 1.0 and cues[1].end == 12.5
    assert "<c>" not in cues[0].text
    assert "chara dasha" in cues[1].text


def test_timestamp_helpers_roundtrip():
    assert parse_timestamp("01:02:03") == 3723.0
    assert parse_timestamp("02:03") == 123.0
    assert parse_timestamp("45") == 45.0
    assert format_timestamp(3723) == "01:02:03"
    with pytest.raises(CaptionError):
        parse_timestamp("not-a-time")


def test_quote_range_is_verbatim_and_bounded():
    cues = parse_vtt(VTT_FIXTURE)
    text = quote_range(cues, 7, 13)
    assert "chara dasha" in text
    assert "Welcome" not in text
    bounded = quote_range(cues, 0, 30, max_chars=40)
    assert bounded.endswith("...")


def test_normalize_and_id_parsing():
    assert normalize_target("abcdefghijk") == "https://www.youtube.com/watch?v=abcdefghijk"
    assert video_id_from_url("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert video_id_from_url("https://www.youtube.com/shorts/abcdefghijk") == "abcdefghijk"
    assert video_id_from_url("https://www.youtube.com/watch?v=abcdefghijk&t=30") == "abcdefghijk"
    with pytest.raises(ResearchFetchError):
        normalize_target("not a url")


def test_fetch_stores_captions_and_is_idempotent():
    store = VideoStore()
    messages = fetch_videos(["https://www.youtube.com/watch?v=abcdefghijk"],
                            store=store, extractor=_fake_extractor(VTT_FIXTURE))
    assert any("stored abcdefghijk" in m and "manual captions en" in m for m in messages)

    record = store.load_record("abcdefghijk")
    assert record is not None
    assert record.channel == "Test Jyotish Channel"
    assert record.caption_kind == "manual"
    assert record.caption_lang == "en"
    assert record.vtt_file == "abcdefghijk.en.vtt"
    assert len(store.load_cues("abcdefghijk")) == 3

    messages = fetch_videos(["abcdefghijk"], store=store,
                            extractor=_fake_extractor(VTT_FIXTURE))
    assert any("skip abcdefghijk" in m for m in messages)

    messages = fetch_videos(["abcdefghijk"], store=store, refresh=True,
                            extractor=_fake_extractor(VTT_FIXTURE))
    assert any("stored abcdefghijk" in m for m in messages)


def test_fetch_without_captions_stores_metadata_only():
    store = VideoStore()
    messages = fetch_videos(["abcdefghijk"], store=store,
                            extractor=_fake_extractor("", write_vtt=False))
    assert any("no captions available" in m for m in messages)
    record = store.load_record("abcdefghijk")
    assert record is not None and record.caption_kind == "none"
    assert store.load_cues("abcdefghijk") == []


def test_fetch_reports_bad_targets_without_aborting():
    store = VideoStore()
    messages = fetch_videos(["definitely not a target"], store=store,
                            extractor=_fake_extractor(VTT_FIXTURE))
    assert messages and messages[0].startswith("error")


def test_store_status_summarizes_records():
    store = VideoStore()
    fetch_videos(["abcdefghijk"], store=store, extractor=_fake_extractor(VTT_FIXTURE))
    status = store.status()
    assert status["videos"] == 1
    assert status["with_captions"] == 1
    assert status["manual"] == 1
    assert "Test Jyotish Channel" in status["channels"]


def test_env_override_controls_store_location(tmp_path, monkeypatch):
    target = tmp_path / "custom-videos"
    monkeypatch.setenv("SWEETASTRO_VIDEO_RESEARCH_DIR", str(target))
    assert video_store_dir() == target
    assert VideoStore().root == target


def test_answer_path_never_imports_the_research_pipeline():
    root = Path(__file__).resolve().parents[1] / "src"
    guarded = [
        root / "chat" / "payload.py",
        root / "chat" / "orchestrator.py",
        root / "chat" / "prompt.py",
        root / "consumer.py",
        root / "knowledge" / "library.py",
    ]
    for path in guarded:
        source = path.read_text(encoding="utf-8")
        assert "research_pipeline" not in source, f"{path.name} must not import the pipeline"
        assert "video_research" not in source, f"{path.name} must not import the CLI"


def test_cli_smoke_status_and_quote(monkeypatch, capsys):
    import importlib.util
    import sys

    store = VideoStore()
    fetch_videos(["abcdefghijk"], store=store, extractor=_fake_extractor(VTT_FIXTURE))

    cli_path = Path(__file__).parent.parent / "video_research.py"
    spec = importlib.util.spec_from_file_location("video_research_cli", cli_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(sys, "argv", ["video_research.py", "status"])
    assert module.main() == 0
    assert "Videos: 1" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["video_research.py", "quote", "abcdefghijk", "7", "13"])
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "chara dasha" in out
    assert "&t=7s" in out

    monkeypatch.setattr(sys, "argv", ["video_research.py", "show", "unknownvideo"])
    assert module.main() == 2
