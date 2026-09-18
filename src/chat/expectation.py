"""
Expectation–capability assessment and delivery check.

The engine should never pretend it can meet an expectation it cannot. Before
the LLM writes anything, the payload states:

    - what the user actually asked for (the expectation),
    - what the engine can deliver truthfully,
    - what cannot be delivered and the concrete reason,
    - what would unlock the missing part.

After streaming, ``timing_claim_detected`` lets the finalizer catch a reply
that presents a timing window although the promise gate withheld timing — the
answer is corrected deterministically instead of shipping the mismatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

_EXACT_DATE_ASK = re.compile(
    r"\b(exact|specific|which|what)\s+(date|day)\b|\bconfirm\b[^?]{0,30}\bdate\b",
    re.IGNORECASE,
)
_WHEN_ASK = re.compile(r"\bwhen\b|\bby when\b|\bhow soon\b|\bwhat time\b", re.IGNORECASE)
_PAST_EVENT_ASK = re.compile(
    r"\bwhen\s+did\b|\bdid\s+(he|she|they|i|you)\b[^?]{0,40}\b"
    r"(marry|married|happen|happened|get\s+married|got\s+married)\b",
    re.IGNORECASE,
)
# Concrete timing windows (month+year, quarter, year range) — not a bare year.
_TIMING_CLAIM = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+20\d{2}\b|\bQ[1-4]\s+20\d{2}\b|\b20\d{2}\s*[-\u2013]\s*20\d{2}\b",
    re.IGNORECASE,
)


@dataclass
class CapabilityAssessment:
    asked: str
    verdict: str                       # full | partial | blocked
    deliverable: List[str] = field(default_factory=list)
    limits: List[str] = field(default_factory=list)
    unlock: List[str] = field(default_factory=list)

    @property
    def timing_blocked(self) -> bool:
        return any("timing" in limit.lower() and "withheld" in limit.lower()
                   for limit in self.limits)


def assess_capability(question: str, answer_shape: str, promise,
                      time_reliable: bool) -> CapabilityAssessment:
    """Classify the request: what we can deliver, what we cannot, and why."""
    q = question or ""
    asked = "a chart-based reading"
    if answer_shape == "timing" or _WHEN_ASK.search(q):
        asked = "an event-timing window"
    elif answer_shape == "verdict":
        asked = "a direct yes/no-style verdict"
    elif _EXACT_DATE_ASK.search(q):
        asked = "an exact date"

    deliverable: List[str] = []
    limits: List[str] = []
    unlock: List[str] = []

    # Timing deliverability (promise gate)
    timing_ok = promise is None or getattr(promise, "timing_reliable", True)
    weak_promise = promise is not None and not timing_ok
    if timing_ok:
        deliverable.append("dasha/transit timing windows (interpretive, never a guaranteed date)")
    else:
        limits.append(f"timing is withheld because the natal promise for {getattr(promise, 'topic', 'this topic')} is weak")
        unlock.append("strengthen the limiting factors named in the promise assessment, "
                      "then re-check after the next dasha change")
    if _EXACT_DATE_ASK.search(q):
        limits.append("an exact/confirmed date cannot be determined from the chart alone")
        deliverable.append("the strongest candidate window and its basis")
        unlock.append("treat the window as scheduling support; report the actual date "
                      "afterwards for calibration review")
    if not time_reliable:
        limits.append("birth time is uncertain, so house/varga-based claims are reduced")
        deliverable.append("sign-level and planet-level facts that do not depend on the exact minute")
        unlock.append("provide a verified birth time to unlock house and divisional-chart claims")

    # Past-event retrieval is not a capability of the engine.
    past_blocked = bool(_PAST_EVENT_ASK.search(q))
    if past_blocked:
        limits.append("the recorded date of a past event cannot be retrieved from a chart")
        deliverable.append("the chart's activation windows and natal promise (candidate evidence, not verification)")
        unlock.append("provide the actual event date (logged for calibration), plus the person's "
                      "verified birth data if the chart is not the asker's")

    if not deliverable:
        deliverable.append("the natal promise, chart factors and practical guidance")

    # Verdict severity
    if past_blocked or (weak_promise and (answer_shape == "timing" or _WHEN_ASK.search(q))):
        verdict = "blocked"
    elif limits:
        verdict = "partial"
    else:
        verdict = "full"
        deliverable = ["the requested reading with calibrated confidence and declared sources"]
        limits = []
        unlock = []

    return CapabilityAssessment(
        asked=asked, verdict=verdict,
        deliverable=deliverable, limits=limits, unlock=unlock,
    )


def assessment_block(assessment: CapabilityAssessment) -> str:
    """Payload block that forces the reply to acknowledge the gap honestly."""
    parts = [
        "EXPECTATION-CAPABILITY ASSESSMENT (plan the reply around this; never fake a deliverable):",
        f"- Asked: {assessment.asked}",
        f"- Verdict: {assessment.verdict}",
        f"- Deliverable: {'; '.join(assessment.deliverable)}",
    ]
    if assessment.limits:
        parts.append(f"- Cannot deliver: {'; '.join(assessment.limits)}")
    if assessment.unlock:
        parts.append(f"- Unlock: {'; '.join(assessment.unlock)}")
    if assessment.verdict != "full":
        parts.append("- Required opening: state plainly what cannot be delivered and why, "
                     "then give the closest truthful reading; do not bury it or imply otherwise.")
    return "\n".join(parts)


def assessment_verdict_from_payload(payload: str) -> str:
    match = re.search(r"EXPECTATION-CAPABILITY ASSESSMENT[^\n]*\n- Asked:[^\n]*\n- Verdict:\s*(\w+)",
                      payload or "")
    return match.group(1).lower() if match else ""


def timing_claim_detected(text: str) -> bool:
    return bool(_TIMING_CLAIM.search(text or ""))


def gap_correction(assessment: CapabilityAssessment) -> str:
    """Deterministic correction when the reply drifted past the capability."""
    return correction_for_verdict(assessment.verdict, assessment.timing_blocked)


def correction_for_verdict(verdict: str, timing_blocked: bool = True) -> str:
    if verdict == "blocked" and timing_blocked:
        return ("_Correction: timing is withheld for this chart (weak natal promise) — disregard any "
                "date or window above; the engine did not compute one._")
    return ("_Correction: part of the request above cannot be delivered as stated; treat only the "
            "engine-computed factors as the reading._")
