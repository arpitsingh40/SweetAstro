"""Outcome calibration tests: aggregation, rendering, prediction snapshots."""

from SweetAstro.src.evaluation.outcome_calibration import (
    build_calibration_report, render_calibration_report,
)


def _records():
    return [
        {"event": "marriage", "verdict": "happened", "date": "2026-11",
         "prediction": {"topic": "marriage", "confidence": "Medium"}},
        {"event": "marriage", "verdict": "partial", "date": "2027-02",
         "prediction": {"topic": "marriage"}},
        {"event": "job change", "verdict": "did_not_happen",
         "prediction": {"topic": "career"}},
        {"event": "property", "verdict": "happened", "date": "2026-06",
         "prediction": {"topic": "property"}},
        {"event": "noise", "verdict": "maybe"},  # invalid verdict ignored
    ]


def test_report_aggregates_by_verdict_and_topic():
    report = build_calibration_report(_records())
    assert report["total"] == 4
    assert report["overall"] == {"happened": 2, "did_not_happen": 1, "partial": 1}
    assert report["happened_rate"] == 0.5

    topics = {t["topic"]: t for t in report["topics"]}
    assert topics["marriage"]["total"] == 2
    assert topics["marriage"]["counts"]["happened"] == 1
    assert topics["career"]["counts"]["did_not_happen"] == 1
    assert topics["property"]["happened_rate"] == 1.0


def test_report_is_claim_gated():
    report = build_calibration_report(_records())
    readiness = report["readiness"]
    assert readiness["ready_for_calibration_claims"] is False
    assert "pre-registered" in readiness["note"]


def test_dated_reports_are_sorted():
    report = build_calibration_report(_records())
    dates = [item["date"] for item in report["dated"]]
    assert dates == sorted(dates)
    assert all(item["date"] for item in report["dated"])


def test_empty_dataset_is_safe():
    report = build_calibration_report([])
    assert report["total"] == 0
    assert report["happened_rate"] is None
    assert report["topics"] == []


def test_render_contains_table_and_honesty_note():
    text = render_calibration_report(build_calibration_report(_records()))
    assert "# Outcome calibration review" in text
    assert "| marriage |" in text
    assert "No accuracy claim" in text


def test_outcome_entry_carries_prediction_snapshot(monkeypatch):
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    captured = []
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.record_outcome",
        lambda session_id, entry: captured.append((session_id, entry)) or True,
    )
    monkeypatch.setattr(
        "SweetAstro.src.chat.orchestrator.resolve_coordinates",
        lambda place, lat, lon: (26.9124, 75.7873, "Geocoded (mock)."),
    )

    class _FakeClient:
        def complete_json(self, messages, **kwargs):
            return {
                "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
                "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
                "question": "When will I get married?", "topic": "marriage",
            }

        def stream(self, messages, **kwargs):
            yield {"type": "content", "text": "ok"}

    orch = ChatOrchestrator(client=_FakeClient(), store=SessionStore())
    list(orch.handle_message("oc1", "When will I get married? Born 15 May 1995 14:30 in Jaipur."))
    session = orch.store.get("oc1")
    assert session is not None

    ack = orch._handle_outcome(session, {
        "event": "marriage", "date": "2026-11", "verdict": "happened",
    })
    assert "logged" in ack
    assert captured, "record_outcome was not called"

    _, entry = captured[0]
    snapshot = entry["prediction"]
    assert snapshot["topic"] == "marriage"
    assert snapshot["dasha_at_report"]
    assert snapshot["current_period"]
    assert snapshot["confidence"] in ("Low", "Medium", "High")
