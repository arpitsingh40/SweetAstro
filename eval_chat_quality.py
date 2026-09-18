"""
Chat answer-quality evaluation runner.

Default (deterministic, no API key required):
  - golden payload cases through the real orchestrator with a fake LLM
  - engine rubric scores for representative topics via score_answer

Opt-in live mode (requires DEEPSEEK_API_KEY, costs tokens):
  - runs the golden questions through the real chat pipeline and scores the
    final answers with the chat rubric (heuristic checks, not an accuracy claim)

Usage:
    python eval_chat_quality.py
    python eval_chat_quality.py --live

Reports are written to reports/chat_quality_<timestamp>.md / .json.
Exit code 0 = all deterministic checks passed.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from SweetAstro.src.consumer import answer_question
from SweetAstro.src.evaluation.chat_quality import (
    GOLDEN_CASES, ChatQualityContext, render_golden_report, run_golden_cases,
    score_chat_answer,
)
from SweetAstro.src.evaluation.interpretation_quality import score_answer

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

ENGINE_TOPICS = [
    ("marriage timing", "marriage"),
    ("wealth and income", "wealth"),
    ("health and energy", "health"),
    ("career and job", "career"),
]


def run_deterministic() -> dict:
    golden = run_golden_cases()
    golden_passed = sum(1 for r in golden if r.passed)

    engine = []
    for question, topic in ENGINE_TOPICS:
        result = answer_question(
            year=1995, month=5, day=15, hour=14, minute=30, second=0.0,
            tz_offset=5.5, lat=26.9124, lon=75.7873,
            place="Jaipur, India", question=question, time_reliable=True,
        )
        report = score_answer(result.answer, result)
        engine.append({
            "topic": topic,
            "score": report.score,
            "high_issues": [(i.dimension, i.detail) for i in report.high_issues],
        })

    return {
        "mode": "deterministic",
        "golden": [
            {"key": r.key, "passed": r.passed, "failures": r.failures}
            for r in golden
        ],
        "golden_passed": golden_passed,
        "golden_total": len(golden),
        "engine": engine,
    }


def run_live() -> dict:
    from SweetAstro.src.chat.client import DeepSeekClient, DeepSeekError
    from SweetAstro.src.chat.orchestrator import ChatOrchestrator
    from SweetAstro.src.chat.session import SessionStore

    client = DeepSeekClient()
    if not client.api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY is not configured — cannot run live evaluation.")

    orchestrator = ChatOrchestrator(client=client, store=SessionStore())
    results = []
    for case in GOLDEN_CASES:
        answer = ""
        for event in orchestrator.handle_message(f"eval-{case.key}", case.question):
            if event.type == "done":
                answer = str(event.data.get("content", ""))
        context = ChatQualityContext(topic=case.extraction.get("topic", "general"))
        report = score_chat_answer(answer, context=context)
        results.append({
            "key": case.key,
            "score": report.score,
            "issues": [(i.dimension, i.severity, i.detail) for i in report.issues],
        })
    return {"mode": "live", "results": results}


def main() -> int:
    live = "--live" in sys.argv
    started = time.time()
    data = run_live() if live else run_deterministic()
    data["generated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["runtime_seconds"] = round(time.time() - started, 2)

    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"chat_quality_{stamp}.json"
    md_path = REPORTS_DIR / f"chat_quality_{stamp}.md"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    if not live:
        golden = run_golden_cases()
        lines = [render_golden_report(golden), "", "## Engine rubric (ConsumerAnswer)"]
        for item in data["engine"]:
            lines.append(f"- {item['topic']}: {item['score']}/100"
                         + (f" — HIGH: {item['high_issues']}" if item["high_issues"] else ""))
        md_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Golden payload cases: {data['golden_passed']}/{data['golden_total']} passed")
        for item in data["engine"]:
            print(f"Engine rubric [{item['topic']}]: {item['score']}/100")
        print(f"Report: {md_path}")
        return 0 if data["golden_passed"] == data["golden_total"] else 1

    lines = ["# Chat quality — live run", ""]
    for item in data["results"]:
        lines.append(f"- {item['key']}: {item['score']}/100")
        for dim, severity, detail in item["issues"]:
            lines.append(f"  - [{severity}] {dim}: {detail}")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Live evaluation written to {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
