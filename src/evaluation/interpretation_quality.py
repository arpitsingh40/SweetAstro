"""
Interpretation quality rubric.

Evaluates a ConsumerAnswer (optionally with its ConsumerResult) on five
dimensions so we can measure whether changes improve the reading itself:

1. completeness   — all required sections present
2. calibration    — no absolute/certainty language
3. evidence       — key factors and predictions carry chart-specific reasons
4. gate_consistency — weak promise => no timing predictions; unstable time => no High confidence
5. safety_hygiene — remedy cap respected, referrals surfaced when the topic needs them

Score: 100 minus weighted deductions (high 25, medium 10, low 5).
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from ..llm.calibrated_language import BANNED_ABSOLUTE, hybrid_confidence_labels

REQUIRED_HEADINGS = [
    "Bottom Line", "Key Chart Factors", "Timing", "Opportunity", "Risk",
    "Recommended Alignment", "Traditional Remedies", "What You Should Do",
    "Confidence", "Remedy Suitability",
]

_SEVERITY_WEIGHT = {"high": 25, "medium": 10, "low": 5}


def _iter_phrase(text: str, phrase: str):
    start = 0
    while True:
        index = text.find(phrase, start)
        if index == -1:
            return
        yield index
        start = index + len(phrase)


@dataclass
class QualityIssue:
    dimension: str
    severity: str
    detail: str


@dataclass
class QualityReport:
    score: int
    issues: List[QualityIssue] = field(default_factory=list)
    dimensions_covered: List[str] = field(default_factory=list)

    @property
    def high_issues(self) -> List[QualityIssue]:
        return [i for i in self.issues if i.severity == "high"]


def score_answer(answer: Any, result: Optional[Any] = None) -> QualityReport:
    issues: List[QualityIssue] = []
    dimensions: List[str] = []

    markdown = answer.to_markdown() if hasattr(answer, "to_markdown") else str(answer)
    lower = markdown.lower()

    # 1. completeness
    missing = [h for h in REQUIRED_HEADINGS if h.lower() not in lower]
    if missing:
        issues.append(QualityIssue("completeness", "high", f"missing sections: {', '.join(missing)}"))
    dimensions.append("completeness")

    # 2. calibration
    for phrase in BANNED_ABSOLUTE:
        for match in _iter_phrase(lower, phrase):
            window = lower[max(0, match - 14):match]
            if any(neg in window for neg in ("not ", "no ", "never ", "n't ")):
                continue
            issues.append(QualityIssue("calibration", "high", f"absolute language: '{phrase}'"))
    for label in hybrid_confidence_labels(markdown):
        issues.append(QualityIssue("calibration", "medium",
                                   f"hybrid confidence range: '{label}' (use only Low/Medium/High)"))
    dimensions.append("calibration")

    # 3. evidence density
    factors = list(getattr(answer, "key_factors", []) or [])
    if len(factors) < 3:
        issues.append(QualityIssue("evidence", "medium",
                                   f"only {len(factors)} key factors (want >= 3)"))
    short_factors = [f for f in factors if len(str(f)) < 40]
    if short_factors:
        issues.append(QualityIssue("evidence", "low",
                                   f"{len(short_factors)} key factor(s) lack chart-specific detail"))
    predictions = list(getattr(answer, "predictions", []) or [])
    for pred in predictions:
        confidence_reason = getattr(pred, "confidence_reason", "")
        if not confidence_reason:
            issues.append(QualityIssue("evidence", "medium",
                                       f"prediction '{getattr(pred, 'topic', '?')}' has no confidence reason"))
            break
    dimensions.append("evidence")

    # 4. gate consistency (needs the ConsumerResult)
    if result is not None:
        promise = getattr(result, "promise", None)
        if promise is not None and not promise.timing_reliable:
            if predictions:
                issues.append(QualityIssue(
                    "gate_consistency", "high",
                    "timing predictions present despite a weak natal promise"))
            if str(getattr(answer, "confidence", "")).lower() == "high":
                issues.append(QualityIssue(
                    "gate_consistency", "high",
                    "confidence High despite a weak natal promise"))
        stability = getattr(result, "stability", None)
        if stability is not None and not stability.lagna_stable:
            if str(getattr(answer, "confidence", "")).lower() == "high":
                issues.append(QualityIssue(
                    "gate_consistency", "high",
                    "confidence High although the lagna sign is unstable within the time window"))
    dimensions.append("gate_consistency")

    # 5. safety hygiene
    remedy_count = (1 if getattr(answer, "primary_remedy", None) else 0) + \
        len(getattr(answer, "supporting_remedies", []) or [])
    if remedy_count > 3:
        issues.append(QualityIssue("safety_hygiene", "high",
                                   f"{remedy_count} remedies exceeds the cap of 3"))
    topic = str(getattr(result, "topic", "") or "") if result is not None else ""
    if topic == "health" and not (getattr(answer, "referrals", None) or []):
        issues.append(QualityIssue("safety_hygiene", "medium",
                                   "health topic without professional referral note"))
    dimensions.append("safety_hygiene")

    score = 100 - sum(_SEVERITY_WEIGHT.get(i.severity, 0) for i in issues)
    return QualityReport(score=max(0, score), issues=issues, dimensions_covered=dimensions)


def summarize_outcomes(records: List[dict]) -> dict:
    """Aggregates outcome-feedback records for calibration review."""
    counts = {"happened": 0, "did_not_happen": 0, "partial": 0}
    for record in records:
        verdict = record.get("verdict")
        if verdict in counts:
            counts[verdict] += 1
    total = sum(counts.values())
    return {
        "total": total,
        "counts": counts,
        "happened_rate": round(counts["happened"] / total, 3) if total else None,
    }


def outcome_dataset_ready(records: List[dict], minimum: int = 500) -> dict:
    """Outcome feedback is only usable for claims at sufficient scale."""
    total = len(records)
    return {
        "total": total,
        "minimum": minimum,
        "ready_for_calibration_claims": total >= minimum,
        "note": ("Outcome feedback is used for calibration review only. "
                 "No accuracy claim is valid without a pre-registered evaluation "
                 "(docs/accuracy_protocol.md)."),
    }
