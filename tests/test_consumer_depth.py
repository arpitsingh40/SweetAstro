"""Consumer depth integration: gochara, ashtakavarga, panchanga, promise gate."""

from datetime import datetime

from SweetAstro.src.consumer import answer_question
from SweetAstro.src.interpretation.promise import PromiseAssessment

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30, second=0,
             tz_offset=5.5, lat=26.9124, lon=75.7873, place="Jaipur, India")


def _result(question="marriage timing and career pattern"):
    return answer_question(**BIRTH, question=question, time_reliable=True)


def test_consumer_returns_depth_fields():
    r = _result()
    assert r.promise is not None and r.promise.level in ("Supported", "Partial", "Weak")
    assert r.gochara is not None and r.gochara.sade_sati is not None
    assert r.ashtakavarga is not None and sum(r.ashtakavarga.sav) == 337
    assert r.panchanga is not None and r.panchanga.nakshatra
    assert r.varshaphala is not None and r.varshaphala.target_year
    assert r.stability is not None
    assert r.deep_dasha is not None and r.deep_dasha.prana
    assert r.yogas is not None
    assert set(r.nodes) == {"Rahu", "Ketu"}
    assert r.karakas is not None and r.jaimini is not None
    assert r.upapada is not None


def test_markdown_contains_new_sections():
    md = _result("marriage timing please").answer.to_markdown()
    for heading in ("Promise Assessment", "Personal Timeline", "Transit Strength",
                    "Yogas & Special Combinations", "Rahu–Ketu Guidance",
                    "Birth Panchanga & Nakshatra", "Annual Chart (Varshaphala)",
                    "Marriage Layer (Jaimini)", "Birth-Time Stability"):
        assert heading in md, f"missing section: {heading}"


def test_weak_promise_gates_timing(monkeypatch):
    weak = PromiseAssessment(
        topic="career", level="Weak", score=-2.0,
        supportive_factors=[], limiting_factors=["Saturn occupies H10"],
        timing_reliable=False, statement="The chart shows a weak promise for career.",
    )
    monkeypatch.setattr("SweetAstro.src.consumer.assess_promise", lambda *a, **k: weak)
    r = _result("Career growth?")
    assert r.answer.confidence == "Low"
    assert r.answer.predictions == []
    assert "weak promise" in r.answer.bottom_line.lower()
    assert "Timing language is withheld" in r.answer.confidence_reason


def test_promise_gate_not_applied_when_supported(monkeypatch):
    supported = PromiseAssessment(
        topic="career", level="Supported", score=4.0,
        supportive_factors=["Jupiter aspects H10"], limiting_factors=[],
        timing_reliable=True, statement="The chart gives a supported promise for career.",
    )
    monkeypatch.setattr("SweetAstro.src.consumer.assess_promise", lambda *a, **k: supported)
    r = _result("Career growth?")
    assert r.answer.confidence in ("High", "Medium", "Low")
    assert "Timing language is withheld" not in r.answer.confidence_reason


def test_chat_payload_includes_depth_blocks():
    from SweetAstro.src.chat.payload import build_chart_payload

    r = _result("marriage timing please")
    payload = build_chart_payload(
        r, name="Native", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Jaipur, India", geo_note="Geocoded (mock).", time_reliable=True,
        question="marriage timing", topic="marriage", tob_unknown=False,
        tz_estimated=False, dasha_detail="",
    )
    for block in ("Promise assessment", "Personal timeline", "Gochara",
                  "Ashtakavarga", "Yogas and special combinations",
                  "Rahu/Ketu deep guidance", "Natal panchanga",
                  "Annual chart (Varshaphala", "Jaimini marriage layer",
                  "Birth-time stability"):
        assert block in payload, f"payload missing block: {block}"
