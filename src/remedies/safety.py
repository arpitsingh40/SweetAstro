"""
Remedy Safety & Ethics Gate — Consumer Engine Sec 11.

Blocks: medical/legal/financial replacement, dangerous fasting, substances,
animal harm, pollution, manipulation, overspending, guarantees.
Adds professional-guidance referrals for health/legal/crisis/relationship-abuse.
No finance referral is produced (retired by product decision — the referral
could not be implemented as a concrete service).

Matching notes:
- Short unsafe words (harm, kill, ill) are matched with word boundaries so
  "harmony", "skills" and "will" do not trip the gate.
- "guarantee" is blocked only when used as a positive claim; negated forms
  ("no guarantees", "not guaranteed", "never guarantee") are allowed.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple

BANNED_SUBSTRINGS = [
    "stop prescribed medication",
    "replace medical care",
    "must buy",
    "expensive gemstone is necessary",
    "definitely will",
    "100%",
]

UNSAFE_SUBSTRINGS = [
    "fast for",
    "consume ",
    "dispose in river",
    "throw in water",
    "bury in another",
]

UNSAFE_PATTERNS = [
    re.compile(r"\bkill(s|ing|ed)?\b", re.IGNORECASE),
    re.compile(r"\bdeceiv(e|es|ing|ed)\b", re.IGNORECASE),
    re.compile(r"\bthreaten(s|ing|ed)?\b", re.IGNORECASE),
]

_GUARANTEE_PATTERN = re.compile(r"guarantee\w*", re.IGNORECASE)
_HARM_PATTERN = re.compile(r"\bharm\b", re.IGNORECASE)
_NEGATION_WINDOW = 40
_NEGATIONS = ("not", "no ", "no,", "never", "without", "cannot", "can't", "n't", "does not", "do not", "isn't", "aren't")
_HARM_NEGATIONS = _NEGATIONS + ("avoid ", "prevent ")

PROFESSIONAL_REFERRALS = {
    "health": "Please consult a qualified doctor/mental-health professional alongside any optional traditional practice.",
    "legal": "Please consult a licensed lawyer; do not act on astrology alone for legal matters.",
    "crisis": "If you feel unsafe or in crisis, contact local emergency services or a trusted helpline immediately.",
    "relationship-abuse": "If there is abuse/control, prioritise safety and professional support over any remedy.",
}

_REFERRAL_PATTERNS = {
    "health": re.compile(r"\b(health|disease|depress\w*|anxiety|surgery|pregnan\w*|ill)\b", re.IGNORECASE),
    "legal": re.compile(r"\b(court|case|legal|divorce|custody)\b", re.IGNORECASE),
    "crisis": re.compile(r"\b(suicid\w*|self[- ]harm|abuse|violence|crisis)\b", re.IGNORECASE),
    "relationship-abuse": re.compile(r"\b(abuse|beating|dowry|harass\w*)\b", re.IGNORECASE),
}


def _has_positive_guarantee(text: str) -> bool:
    for match in _GUARANTEE_PATTERN.finditer(text):
        context = text[max(0, match.start() - _NEGATION_WINDOW):match.start()].lower()
        if not any(neg in context for neg in _NEGATIONS):
            return True
    return False


def _has_positive_harm(text: str) -> bool:
    """True only for an unnegated instruction to harm ('never harm' is safe)."""
    for match in _HARM_PATTERN.finditer(text):
        context = text[max(0, match.start() - _NEGATION_WINDOW):match.start()].lower()
        if not any(neg in context for neg in _HARM_NEGATIONS):
            return True
    return False


@dataclass
class SafetyVerdict:
    allowed: bool
    reasons: List[str]
    referrals: List[str]


def safety_check(question: str, remedy_texts: List[str]) -> SafetyVerdict:
    q = (question or "").lower()
    reasons: List[str] = []
    referrals: List[str] = []
    allowed = True

    for text in remedy_texts:
        lowered = text.lower()
        for banned in BANNED_SUBSTRINGS:
            if banned in lowered:
                allowed = False
                reasons.append(f"Blocked phrasing: '{banned}'. Remedies must never guarantee results.")
        if _has_positive_guarantee(text):
            allowed = False
            reasons.append("Blocked phrasing: 'guarantee'. Remedies must never guarantee results.")
        if _has_positive_harm(text):
            allowed = False
            reasons.append("Blocked unsafe practice pattern: 'harm'. Choose a safe alternative.")
        for bad in UNSAFE_SUBSTRINGS:
            if bad in lowered:
                allowed = False
                reasons.append(f"Blocked unsafe practice pattern: '{bad}'. Choose a safe alternative.")
        for pattern in UNSAFE_PATTERNS:
            if pattern.search(text):
                allowed = False
                reasons.append(f"Blocked unsafe practice pattern: '{pattern.pattern}'. Choose a safe alternative.")

    for key, pattern in _REFERRAL_PATTERNS.items():
        if pattern.search(q):
            referrals.append(PROFESSIONAL_REFERRALS[key])

    if not reasons:
        reasons.append("Remedies are optional traditional practices, not medical/legal/financial treatment.")
    return SafetyVerdict(allowed=allowed, reasons=reasons, referrals=referrals)
