"""
Chat answer-quality evaluation.

Two layers, both deterministic by default:

1. `score_chat_answer` — rubric over the final chat answer text, scored with
   the same QualityReport used by interpretation_quality (100 minus weighted
   deductions). Dimensions: completeness, calibration, grounding, promise
   gate, safety hygiene, recall disclosure.

2. Golden payload cases — scripted chat turns run through the real orchestrator
   with a fake LLM, asserting the verified payload contains the required blocks
   for the topic (and never leaks optional/reading-only blocks into lookup).

This measures the *engine's* contract. Judging live LLM prose requires the
opt-in `--live` mode of eval_chat_quality.py; no accuracy claim is made.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .interpretation_quality import (
    BANNED_ABSOLUTE, QualityIssue, QualityReport, _SEVERITY_WEIGHT,
)
from ..llm.calibrated_language import hybrid_confidence_labels

REQUIRED_SECTIONS = [
    "🔮 Bottom Line", "🧩 Key Chart Factors", "⏳ Timing", "📈 Opportunity",
    "⚠️ Risk", "🪐 Recommended Alignment", "🕉️ Traditional Remedies",
    "🎯 What You Should Do", "Confidence", "Remedy Suitability",
]

OPTIONAL_SECTIONS = [
    "🌐 Transits & This Year", "✨ Yogas & Birth Star", "☊ Rahu–Ketu Guidance",
]

_TIMING_WINDOW = ("january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november", "december",
                  "20", "q1", "q2", "q3", "q4")

_REFERRAL_WORDS = ("professional", "doctor", "medical", "physician",
                   "legal", "lawyer", "crisis", "helpline")

_DISCLOSURE_WORDS = ("saved", "stored", "previous", "earlier", "recalled", "on file")


@dataclass
class ChatQualityContext:
    topic: str = "general"
    timing_withheld: bool = False
    used_saved_time: bool = False
    referrals_expected: bool = False
    has_transits: bool = True
    has_yogas: bool = False
    has_nodes: bool = False
    mode: str = "reading"

    @classmethod
    def from_result(cls, result: Any, used_saved_time: bool = False) -> "ChatQualityContext":
        promise = getattr(result, "promise", None)
        return cls(
            topic=str(getattr(result, "topic", "general") or "general"),
            timing_withheld=bool(promise is not None and not promise.timing_reliable),
            used_saved_time=used_saved_time,
            referrals_expected=bool(getattr(result.answer, "referrals", None)),
            has_transits=getattr(result, "gochara", None) is not None,
            has_yogas=bool(getattr(result, "yogas", None)),
            has_nodes=bool(getattr(result, "nodes", None)),
        )


def _timing_section(answer_text: str) -> str:
    start = answer_text.find("⏳")
    if start == -1:
        return ""
    rest = answer_text[start + 1:]
    end = len(rest)
    for marker in ("📈", "⚠️", "🪐", "🕉️", "🎯", "✨", "☊", "Confidence"):
        idx = rest.find(marker)
        if idx != -1:
            end = min(end, idx)
    return rest[:end]


def score_chat_answer(answer_text: str, *, payload: str = "",
                      context: Optional[ChatQualityContext] = None) -> QualityReport:
    """Scores a final chat answer; `payload` is the verified chart data it saw."""
    ctx = context or ChatQualityContext()
    text = answer_text or ""
    lower = text.lower()
    issues: List[QualityIssue] = []
    dimensions: List[str] = []

    # 1. completeness
    missing = [s for s in REQUIRED_SECTIONS if s.lower() not in lower]
    if missing:
        issues.append(QualityIssue("completeness", "high",
                                   f"missing sections: {', '.join(missing)}"))
    dimensions.append("completeness")

    # 2. calibration
    for phrase in BANNED_ABSOLUTE:
        start = 0
        while True:
            idx = lower.find(phrase, start)
            if idx == -1:
                break
            window = lower[max(0, idx - 14):idx]
            if not any(neg in window for neg in ("not ", "no ", "never ", "n't ")):
                issues.append(QualityIssue("calibration", "high",
                                           f"absolute language: '{phrase}'"))
            start = idx + len(phrase)
    for label in hybrid_confidence_labels(text):
        issues.append(QualityIssue("calibration", "medium",
                                   f"hybrid confidence range: '{label}' (use only Low/Medium/High)"))
    dimensions.append("calibration")

    # 3. grounding: echo at least two verified facts when a payload was given
    if payload:
        facts = []
        for line in payload.splitlines():
            if line.startswith("Ascendant:"):
                facts.append(line.split(":", 1)[1].strip().split(" ")[0])
            elif line.startswith("Moon:"):
                facts.append(line.split(":", 1)[1].strip().split(" ")[0])
            elif line.startswith("Current Vimshottari dasha:"):
                facts.extend(line.split(":", 1)[1].strip().split("/")[:2])
        echoes = [f.strip().lower() for f in facts if f.strip() and f.strip().lower() in lower]
        if len(echoes) < 2:
            issues.append(QualityIssue("grounding", "medium",
                                       f"answer echoes only {len(echoes)} verified chart fact(s)"))
    dimensions.append("grounding")

    # 4. promise gate
    if ctx.timing_withheld:
        timing = _timing_section(text).lower()
        if timing and any(token in timing for token in _TIMING_WINDOW):
            issues.append(QualityIssue(
                "promise_gate", "high",
                "timing window presented although the engine withheld timing"))
    dimensions.append("promise_gate")

    # 5. safety hygiene
    if ctx.referrals_expected and not any(word in lower for word in _REFERRAL_WORDS):
        issues.append(QualityIssue(
            "safety_hygiene", "high",
            "payload required professional referrals but the answer omits them"))
    dimensions.append("safety_hygiene")

    # 6. recall disclosure
    if ctx.used_saved_time:
        disclosed = ("birth time" in lower and any(w in lower for w in _DISCLOSURE_WORDS))
        if not disclosed:
            issues.append(QualityIssue(
                "disclosure", "medium",
                "birth time was recalled from memory but the answer does not disclose it"))
    dimensions.append("disclosure")

    score = 100 - sum(_SEVERITY_WEIGHT.get(i.severity, 0) for i in issues)
    return QualityReport(score=max(0, score), issues=issues, dimensions_covered=dimensions)


# ---------------------------------------------------------------------------
# Golden payload cases
# ---------------------------------------------------------------------------

@dataclass
class GoldenCase:
    key: str
    question: str
    extraction: Dict[str, Any]
    must_contain: List[str]
    must_not_contain: List[str] = field(default_factory=list)


GOLDEN_CASES: List[GoldenCase] = [
    GoldenCase(
        key="marriage-reading",
        question="When will I get married? Born 15 May 1995 at 2:30 pm in Jaipur.",
        extraction={
            "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
            "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
            "question": "When will I get married?", "topic": "marriage",
        },
        must_contain=["VERIFIED CHART DATA", "Current Vimshottari dasha:", "D9", "Dasha period boundaries"],
        must_not_contain=["Full varga matrix"],
    ),
    GoldenCase(
        key="wealth-reading",
        question="How will my wealth and income grow? Born 15 May 1995 14:30 in Jaipur.",
        extraction={
            "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
            "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
            "question": "How will my wealth grow?", "topic": "wealth",
        },
        must_contain=["VERIFIED CHART DATA", "D2", "D10", "D11"],
        must_not_contain=["Full varga matrix"],
    ),
    GoldenCase(
        key="health-referral-reading",
        question="Any health problems indicated? Born 15 May 1995 14:30 in Jaipur.",
        extraction={
            "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
            "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
            "question": "Any health problems indicated?", "topic": "health",
        },
        must_contain=["VERIFIED CHART DATA", "D6", "D30", "Professional referrals required"],
        must_not_contain=["Full varga matrix"],
    ),
    GoldenCase(
        key="lookup-matrix",
        question="What is my nakshatra?",
        extraction={
            "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
            "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
            "question": "What is my nakshatra?", "topic": "general",
        },
        must_contain=["VERIFIED CHART DATA", "Full varga matrix", "- D81 [", "- D144 ["],
    ),
    GoldenCase(
        key="deep-report",
        question="Give me a deep mode reading covering every planet. Born 15 May 1995 14:30 in Jaipur.",
        extraction={
            "name": "Ananya", "dob": "1995-05-15", "tob": "14:30:00",
            "place": "Jaipur, Rajasthan, India", "tz_offset": 5.5,
            "question": "Give me a deep mode reading", "topic": "general",
        },
        must_contain=["VERIFIED CHART DATA", "Deep node dossier",
                      "deep mode: all seven physical grahas"],
        must_not_contain=["Full varga matrix"],
    ),
    GoldenCase(
        key="unknown-time",
        question="How is my career? I don't know my birth time. Born 15 May 1995 in Jaipur.",
        extraction={
            "dob": "1995-05-15", "tob_unknown": True,
            "place": "Jaipur, Rajasthan, India", "tz_offset_estimate": 5.5,
            "question": "How is my career?", "topic": "career",
        },
        must_contain=["VERIFIED CHART DATA", "UNCERTAIN"],
        must_not_contain=["Full varga matrix"],
    ),
]


@dataclass
class GoldenResult:
    key: str
    passed: bool
    failures: List[str] = field(default_factory=list)


def evaluate_payload(case: GoldenCase, payload: str) -> GoldenResult:
    failures = [f"missing: {marker}" for marker in case.must_contain
                if marker not in payload]
    failures += [f"leaked: {marker}" for marker in case.must_not_contain
                 if marker in payload]
    return GoldenResult(key=case.key, passed=not failures, failures=failures)


def _last_verified_payload(client: "_GoldenFakeClient") -> str:
    payload = ""
    for messages in client.stream_calls:
        for message in messages:
            if (message.get("role") == "system"
                    and str(message.get("content", "")).startswith("=== VERIFIED")):
                payload = message["content"]
    return payload


def run_golden_cases(cases: Optional[List[GoldenCase]] = None) -> List[GoldenResult]:
    """
    Runs every golden case through the real orchestrator with a fake LLM and
    checks the verified payload. No network, no API key required.
    """
    from ..chat.orchestrator import ChatOrchestrator
    from ..chat.session import SessionStore

    results: List[GoldenResult] = []
    for case in cases or GOLDEN_CASES:
        client = _GoldenFakeClient(case.extraction)
        orchestrator = ChatOrchestrator(client=client, store=SessionStore())
        list(orchestrator.handle_message(case.key, case.question))
        payload = _last_verified_payload(client)
        if not payload:
            # Basis-confirmation turns ask "yes" before the reading is produced.
            list(orchestrator.handle_message(case.key, "yes"))
            payload = _last_verified_payload(client)
        if not payload:
            results.append(GoldenResult(key=case.key, passed=False,
                                        failures=["no verified payload produced"]))
            continue
        results.append(evaluate_payload(case, payload))
    return results


class _GoldenFakeClient:
    """Deterministic stand-in for the LLM: one extraction, canned stream."""

    def __init__(self, extraction: Dict[str, Any]):
        self._extraction = extraction
        self.stream_calls: List[List[Dict[str, str]]] = []

    def complete_json(self, messages, **kwargs):
        return dict(self._extraction)

    def stream(self, messages, **kwargs):
        self.stream_calls.append(messages)
        for word in ("This is a deterministic evaluation reply.").split(" "):
            yield {"type": "content", "text": word + " "}


def render_golden_report(results: List[GoldenResult]) -> str:
    lines = ["# Chat payload golden cases", ""]
    passed = sum(1 for r in results if r.passed)
    lines.append(f"**{passed}/{len(results)} passed**")
    lines.append("")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- [{status}] {result.key}")
        for failure in result.failures:
            lines.append(f"  - {failure}")
    return "\n".join(lines)
