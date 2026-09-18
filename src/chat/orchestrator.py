"""
Chat orchestrator — one user turn end to end:

  extract → validate slots → (ask for missing data | compute chart) →
  build verified payload → stream DeepSeek answer → sanitize → persist.

The orchestrator is deliberately decoupled from FastAPI so it can be tested
with a fake LLM client and reused from CLI tools.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

from ..consumer import answer_question as consumer_answer
from ..core.chart import calculate_d1_chart
from ..core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
from ..core.ephemeris import ephemeris_engine_name, ephemeris_data_source
from ..core.geocode import GeocodeError, resolve_coordinates
from ..core.matching import match_charts
from ..core.muhurta import NAKSHATRA_INDEX, find_muhurta_days, load_muhurta_rules
from ..core.panchanga import PanchangaError, compute_panchanga
from ..core.vastu import assess_layout
from ..knowledge.retrieval import reference_lines, retrieve_references
from ..knowledge.library import library_reference_lines, search_library
from ..methods.reasons import promise_reason_tags
from ..prediction.rectify import rectify_birth_time
from .client import DeepSeekClient, DeepSeekError
from .config import CHAT_HISTORY_LIMIT, DEEPSEEK_ANSWER_THINKING
from .extractor import BirthDataExtractor
from .memory import MemoryStore
from .outcomes import record_outcome
from .payload import (
    build_chart_payload, build_compatibility_payload, build_muhurta_payload,
    build_panchanga_payload, build_rectification_payload, build_vastu_payload,
)
from .prompt import (
    ANSWER_SYSTEM_PROMPT, COMPATIBILITY_SYSTEM_PROMPT, LOOKUP_SYSTEM_PROMPT,
    MUHURTA_SYSTEM_PROMPT, RECTIFICATION_SYSTEM_PROMPT, VASTU_SYSTEM_PROMPT,
    SHAPE_PROMPTS, build_guide_prompt, sanitize_absolute_language,
)
from ..llm.calibrated_language import normalize_confidence_labels
from .expectation import (
    assess_capability, assessment_block, assessment_verdict_from_payload,
    correction_for_verdict, timing_claim_detected,
)
from .session import BirthSlots, ChatSession, SessionStore, merge_prefixed
from .verify import verify_answer

logger = logging.getLogger("sweetastro.chat")

_MUHURTA_PATTERN = re.compile(
    r"\b(muhurat?|muhurtha|panchang|panchanga|auspicious|shubh|rahu\s*kaal|rahu\s*kalam|abhijit|"
    r"good\s+(date|day|time)|best\s+(date|day|time)|favou?rable\s+(date|day)|choghadiya|"
    r"griha\s*pravesh|grihapravesh|bhoomi\s*puja|housewarming|house\s*warming|"
    r"launch\s+(date|time)|wedding\s+(date|muhurat)|marriage\s+muhurat)\b",
    re.IGNORECASE,
)

_VASTU_PATTERN = re.compile(
    r"\b(vastu|vaastu|vasthu|brahmasthan|brahma\s*sthan)\b|"
    r"\b(which|what)\s+direction\b|"
    r"\b(north-?east|north-?west|south-?east|south-?west|north|south|east|west)\b[^.]{0,50}"
    r"\b(kitchen|bedroom|puja|pooja|toilet|bathroom|main\s*door|door|study|dining|staircase|stair|water\s*tank|plot|house|home)\b|"
    r"\b(kitchen|bedroom|puja|pooja|toilet|bathroom|main\s*door|study|dining|staircase|stair|water\s*tank|plot|house|home)\b[^.]{0,50}"
    r"\b(facing|faces|direction|north-?east|north-?west|south-?east|south-?west)\b",
    re.IGNORECASE,
)

_COMPAT_PATTERN = re.compile(
    r"\b(kundli|kundali)\s*milan\b|\bguna\s*milan\b|\bashtakoot\w*\b|\bashtakuta\b|"
    r"\b(match\s*making|matching)\b|"
    r"\b(compatibility|compatible)\b[^.]{0,40}\b(with|match|marriage|partner|chart|kundli|kundali)\b|"
    r"\b(do|will)\s+we\s+(match|be\s+a\s+good\s+match)\b|"
    r"\b(are\s+we|will\s+we\s+be)\s+(a\s+)?(good\s+)?(match|compatible)\b|"
    r"\b(match|milan)\s+(our|the|both)\s+(chart|kundli|kundali|horoscope|patrika)s?\b|"
    r"\b(rishta|melap|milap)\b",
    re.IGNORECASE,
)

_SUBJECT_PATTERN = re.compile(
    r"\bmy\s+(son|daughter|child|kid|father|mother|dad|mom|husband|wife|spouse|"
    r"fianc[eé]e?|boyfriend|girlfriend|brother|sister)\b",
    re.IGNORECASE,
)
_SUBJECT_ROLE_MAP = {
    "son": "child", "daughter": "child", "child": "child", "kid": "child",
    "father": "parent", "mother": "parent", "dad": "parent", "mom": "parent",
    "husband": "partner", "wife": "partner", "spouse": "partner",
    "fiance": "partner", "fiancé": "partner", "fiancee": "partner", "fiancée": "partner",
    "boyfriend": "partner", "girlfriend": "partner",
    "brother": "sibling", "sister": "sibling",
}
_PRONOUN_FOLLOWUP = re.compile(
    r"\b(his|her|hers|their|theirs|he|she|they|him|them)\b", re.IGNORECASE)

_RECTIFY_PATTERN = re.compile(
    r"\b(rectif\w*|find my (birth|janm|janam)\s*time|guess my (birth|janm|janam)\s*time|"
    r"which (birth|janm|janam)\s*time|estimate my (birth|janm|janam)\s*time|"
    r"birth\s*time (nahi|nahin) pata)\b",
    re.IGNORECASE,
)

_ACK_YES = re.compile(r"^(yes|yep|yeah|yup|ok|okay|sure|correct|right|confirmed|confirm)[.!]?$", re.IGNORECASE)
_ACK_NO = re.compile(r"^(no|nope|wrong|incorrect|not correct)[.!]?$", re.IGNORECASE)
_ACK_THANKS = re.compile(r"^(thanks|thank you|thx|ty|great|got it|perfect|dhanyavad|shukriya)[.!]?$", re.IGNORECASE)

_PANCHANGA_ASK = re.compile(r"\bpanchang\w*\b", re.IGNORECASE)
_PANCHANGA_MUHURTA_WORDS = re.compile(
    r"\b(muhurat?\w*|auspicious|shubh|good\s+(date|day|time)|best\s+(date|day|time)|"
    r"dates?\s+for|when\s+should|choghadiya)\b",
    re.IGNORECASE,
)
_LOOKUP_INFER = re.compile(
    r"\b(what|which|tell me)\b[^.?!]{0,40}\b(nakshatra|birth ?star|rashi|moon sign|sun sign|lagna|ascendant|dasha)\b"
    r"|\b(current|running|which|my)\s+dasha\b"
    r"|\b(my|the)\s+(nakshatra|rashi|moon sign|sun sign|lagna|ascendant)\b",
    re.IGNORECASE,
)
_READING_INFER = re.compile(
    r"\b(when|will|should|how|why|predict\w*|remed\w*|upay|mantra|gemstone|ratna|advice|analyse|analyze|analysis)\b",
    re.IGNORECASE,
)


def _infer_answer_mode(message: str) -> str:
    """Heuristic fallback when the extractor omits answer_mode (fail towards reading)."""
    text = (message or "").strip()
    if not text or len(text) > 200 or _READING_INFER.search(text):
        return "reading"
    return "lookup" if _LOOKUP_INFER.search(text) else "reading"


_REPORT_SHAPE = re.compile(
    r"\b(full|detailed|complete|deep|whole|in-depth)\b[^?]{0,30}"
    r"\b(reading|report|analysis|breakdown|kundli|kundali|picture|details?)\b"
    r"|\b(go deeper|in detail|full analysis|deep dive|everything|deep mode|"
    r"deep planetary|every planet|all planets|planet by planet)\b",
    re.IGNORECASE,
)
_REMEDY_SHAPE = re.compile(
    r"\b(remedy|remedies|upay|upaya|mantra|gemstone|ratna|stone|donat\w*|puja|yagya|homa)\b",
    re.IGNORECASE,
)
_TIMING_SHAPE = re.compile(
    r"\bwhen\b[^?]{0,70}\b(will|can|should|could|going|happen|marry|married|get|come|find)\b"
    r"|\btiming\b|\bwhich (year|month|period|age)\b|\bwhat (year|month|period|age)\b",
    re.IGNORECASE,
)
_VERDICT_SHAPE = re.compile(r"^(can|could|will|would|should|is|are|do|does|did|am)\b", re.IGNORECASE)


def _infer_answer_shape(message: str, answer_mode: str = "reading") -> str:
    """
    Chooses the presentation shape for a reading answer:
    verdict | timing | analysis | remedy | report (lookup handled elsewhere).

    Default is 'analysis' — the long 16-section report is produced only when
    explicitly requested. Fail towards concise; the user can ask 'go deeper'.
    """
    if answer_mode == "lookup":
        return "lookup"
    text = (message or "").strip()
    if not text:
        return "analysis"
    if _REPORT_SHAPE.search(text):
        return "report"
    if _REMEDY_SHAPE.search(text):
        return "remedy"
    if _TIMING_SHAPE.search(text):
        return "timing"
    if len(text) <= 140 and _VERDICT_SHAPE.match(text):
        return "verdict"
    return "analysis"


MUHURTA_MAX_DAYS = 120


def _infer_muhurta_event(message: str) -> str:
    text = (message or "").lower()
    if any(k in text for k in ("marriage", "wedding", "vivah", "shaadi", "shadi")):
        return "vivaha"
    if any(k in text for k in ("griha", "housewarming", "house warming", "bhoomi", "home")):
        return "griha_pravesh"
    if any(k in text for k in ("business", "venture", "company", "shop", "launch", "startup", "start-up")):
        return "business"
    if any(k in text for k in ("travel", "journey", "trip", "flight")):
        return "travel"
    return "general"

TOPIC_QUESTION_PREFIX = {
    "wealth": "Wealth, money and financial growth",
    "career": "Career and profession",
    "business": "Business and enterprise",
    "marriage": "Marriage and partnership",
    "children": "Children and family",
    "property": "Property and assets",
    "education": "Education and learning",
    "siblings": "Siblings and courage",
    "health": "Health and difficulties",
    "spirituality": "Spirituality and inner growth",
    "compatibility": "Compatibility between two charts",
    "personality": "Nature, character and natural strengths",
    "general": "General life reading",
}

MISSING_LABELS = {
    "dob": "date of birth (YYYY-MM-DD)",
    "place": "birthplace (City, State/Province, Country)",
    "time": "exact birth time (HH:MM, 24h) — or say you don't know",
    "tz": "time zone / UTC offset (e.g. IST +05:30)",
    "partner": ("the other person's birth details — date of birth and birthplace; "
                "birth time if known (for kundli milan)"),
    "events": ("at least 2 dated life events to fit the birth time against "
               "(e.g. marriage 2018-11, job change 2021-06, relocation 2023-02)"),
    "layout": ("your main room directions (kitchen, master bedroom, puja, toilets), "
               "plot facing/slope and shape — e.g. \"kitchen in the south-east, toilet in the north-west\""),
}


@dataclass
class ChatEvent:
    type: str                      # status | meta | delta | done | error
    data: Dict[str, Any] = field(default_factory=dict)

    def to_sse_payload(self, session_id: str) -> Dict[str, Any]:
        payload = {"type": self.type, "session_id": session_id}
        payload.update(self.data)
        return payload


def _short(text: str, limit: int = 240) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


_LANGUAGE_RE = re.compile(r"^[A-Za-z][A-Za-z \-]{0,39}$")


def _clean_language(language: Optional[str]) -> Optional[str]:
    """Validates a UI-supplied reply-language label; 'auto'/junk clears it."""
    if not language:
        return None
    text = " ".join(str(language).split()).strip()
    if not text or text.lower() in ("auto", "none", "default"):
        return None
    if not _LANGUAGE_RE.match(text):
        return None
    return text


class ChatOrchestrator:
    def __init__(
        self,
        client: Optional[DeepSeekClient] = None,
        store: Optional[SessionStore] = None,
        history_limit: int = CHAT_HISTORY_LIMIT,
        memory: Optional[MemoryStore] = None,
    ):
        self.client = client or DeepSeekClient()
        self.store = store or SessionStore()
        self.extractor = BirthDataExtractor(self.client)
        self.history_limit = history_limit
        self.memory = memory
        if self.memory is None and getattr(self.store, "persist_path", None):
            self.memory = MemoryStore(self.store.persist_path.parent / "memory.json")

    # ------------------------------------------------------------ public API
    def handle_message(self, session_id: Optional[str], message: str,
                       language: Optional[str] = None) -> Iterator[ChatEvent]:
        session = self.store.get_or_create(session_id)
        message = (message or "").strip()
        if not message:
            yield ChatEvent("error", {"message": "Enter a message."})
            return

        session.reply_language = _clean_language(language)
        session.add_message("user", message)
        turn_started = time.monotonic()

        trivial = self._trivial_kind(message)
        skip_extraction = False
        prelude: Optional[str] = None
        if trivial == "yes" and session.awaiting_confirmation:
            session.awaiting_confirmation = False
            skip_extraction = True
        elif trivial == "no" and session.awaiting_confirmation:
            session.awaiting_confirmation = False
            prelude = ("Correct the record: provide the corrected date of birth, exact birth time, or birthplace. "
                       "The chart will be recomputed from the corrected details.")
        elif trivial == "thanks":
            prelude = "Request noted. Ask about the chart, muhurta windows, or vastu at any time."
        if prelude:
            yield ChatEvent("delta", {"channel": "content", "text": prelude})
            session.add_message("assistant", prelude)
            yield ChatEvent("done", {"content": prelude, "topic": session.slots.topic or "general"})
            self.store.save()
            return

        try:
            yield ChatEvent("status", {"stage": "extract", "text": "Reading your details…"})
            if skip_extraction:
                update: Dict[str, Any] = {}
            else:
                update = self.extractor.extract(session.recent_messages(self.history_limit), session.slots)
            changed = session.slots.merge(update)
            if changed:
                logger.info("session %s slots updated: %s", session.session_id, changed)
            partner_changed = merge_prefixed(session.person("partner"), update, "partner_")
            if partner_changed:
                logger.info("session %s partner slots updated: %s", session.session_id, partner_changed)
            subjects = update.get("subjects")
            if isinstance(subjects, list):
                for item in subjects[:5]:
                    role = str(item.get("role") or "").strip().lower()
                    if not role:
                        continue
                    name = str(item.get("name") or "").strip().lower()
                    key = f"{role}:{name}" if name else role
                    merge_prefixed(session.person(key), item, "")
            logger.info("session=%s stage=extract +%.1fs", session.session_id, time.monotonic() - turn_started)

            outcome = update.get("outcome")
            if outcome:
                ack = self._handle_outcome(session, outcome)
                if ack:
                    yield from self._respond_canned(session, ack)
                    return

            panchanga_date = self._detect_panchanga_lookup(update, message)
            if panchanga_date:
                yield from self._answer_panchanga_lookup(session, panchanga_date, turn_started)
                return

            if self._detect_compatibility(session, update, message):
                missing_compat = self._missing_for_compatibility(session)
                if missing_compat:
                    session.last_missing = missing_compat
                    yield from self._respond_guide(session, missing_compat)
                    return
                yield ChatEvent("status", {"stage": "matching",
                                           "text": "Computing both charts and the kuta score…"})
                try:
                    compat_payload, compat_card = self._compute_compatibility(session)
                except GeocodeError as exc:
                    yield from self._respond_canned(
                        session,
                        "One of the birthplaces could not be resolved on the map with confidence. "
                        f"({exc}) Retype both as \"City, State/Province, Country\".",
                    )
                    return
                session.last_missing = []
                logger.info("session=%s stage=compatibility +%.1fs total=%s", session.session_id,
                            time.monotonic() - turn_started, compat_card.get("total"))
                yield ChatEvent("meta", {"birth_data": compat_card, "chart_basis": compat_card,
                                         "topic": "compatibility", "mode": "compatibility"})
                yield ChatEvent("status", {"stage": "answer", "text": "Preparing the milan reading…"})
                compat_started = time.monotonic()
                compat_text = yield from self._stream_compatibility_answer(session, compat_payload)
                logger.info("session=%s stage=compatibility_answer +%.1fs chars=%d",
                            session.session_id, time.monotonic() - compat_started, len(compat_text))
                final_compat = self._finalize(compat_text, compat_payload, session,
                                              allow_confirmation=False, birth_time_relevant=False)
                session.add_message("assistant", final_compat)
                yield ChatEvent("done", {"content": final_compat, "topic": "compatibility",
                                         "birth_data": compat_card, "mode": "compatibility"})
                return

            if self._detect_rectification(session, update, message):
                missing_rect = self._missing_for_rectification(session)
                if missing_rect:
                    session.last_missing = missing_rect
                    yield from self._respond_guide(session, missing_rect)
                    return
                yield ChatEvent("status", {"stage": "rectify",
                                           "text": "Scoring candidate birth times against your events…"})
                try:
                    rect_payload, rect_card = self._compute_rectification(session)
                except ValueError as exc:
                    yield from self._respond_canned(session, str(exc))
                    return
                session.last_missing = []
                logger.info("session=%s stage=rectification +%.1fs windows=%s", session.session_id,
                            time.monotonic() - turn_started, rect_card.get("best_windows"))
                yield ChatEvent("meta", {"birth_data": rect_card, "chart_basis": rect_card,
                                         "topic": "rectification", "mode": "rectification"})
                yield ChatEvent("status", {"stage": "answer", "text": "Preparing the fit summary…"})
                rect_started = time.monotonic()
                rect_text = yield from self._stream_rectification_answer(session, rect_payload)
                logger.info("session=%s stage=rectification_answer +%.1fs chars=%d",
                            session.session_id, time.monotonic() - rect_started, len(rect_text))
                final_rect = self._finalize(rect_text, rect_payload, session,
                                            allow_confirmation=False, birth_time_relevant=False)
                session.add_message("assistant", final_rect)
                yield ChatEvent("done", {"content": final_rect, "topic": "rectification",
                                         "birth_data": rect_card, "mode": "rectification"})
                return

            muhurta_intent = self._detect_muhurta(update, message)
            if muhurta_intent:
                missing_muhurta = self._missing_for_muhurta(session)
                if missing_muhurta:
                    session.last_missing = missing_muhurta
                    yield from self._respond_guide(session, missing_muhurta)
                    return
                yield ChatEvent("status", {"stage": "panchanga", "text": "Computing panchanga and muhurta windows…"})
                try:
                    muhurta_payload, muhurta_card = self._compute_muhurta(session, muhurta_intent)
                except GeocodeError as exc:
                    yield from self._respond_canned(
                        session,
                        "Birthplace could not be resolved on the map with confidence. "
                        f"({exc}) Retype it as \"City, State/Province, Country\" to compute the muhurta.",
                    )
                    return
                session.last_missing = []
                logger.info("session=%s stage=muhurta +%.1fs suitable=%s", session.session_id,
                            time.monotonic() - turn_started, muhurta_card.get("suitable_days"))
                muhurta_card["needs_confirmation"] = self._needs_basis_confirmation(
                    session, birth_time_relevant=False)
                yield ChatEvent("meta", {"birth_data": muhurta_card, "chart_basis": muhurta_card,
                                         "topic": "muhurta", "mode": "muhurta"})
                yield ChatEvent("status", {"stage": "answer", "text": "Selecting the best windows…"})
                muhurta_started = time.monotonic()
                muhurta_text = yield from self._stream_muhurta_answer(session, muhurta_payload)
                logger.info("session=%s stage=muhurta_answer +%.1fs chars=%d", session.session_id,
                            time.monotonic() - muhurta_started, len(muhurta_text))
                final_muhurta = self._finalize(
                    muhurta_text, muhurta_payload, session,
                    allow_confirmation=False, birth_time_relevant=False,
                )
                session.add_message("assistant", final_muhurta)
                yield ChatEvent("done", {"content": final_muhurta, "topic": "muhurta",
                                         "birth_data": muhurta_card, "mode": "muhurta"})
                return

            if self._detect_vastu(update, message):
                self._merge_vastu(session, update)
                if not self._has_vastu_layout(session):
                    session.last_missing = ["layout"]
                    yield from self._respond_guide(session, ["layout"])
                    return
                yield ChatEvent("status", {"stage": "vastu", "text": "Checking your layout against the vastu rules…"})
                vastu_payload, vastu_card = self._compute_vastu(session)
                session.last_missing = []
                logger.info("session=%s stage=vastu +%.1fs score=%s", session.session_id,
                            time.monotonic() - turn_started, vastu_card.get("score"))
                yield ChatEvent("meta", {"birth_data": vastu_card, "chart_basis": vastu_card,
                                         "topic": "vastu", "mode": "vastu"})
                yield ChatEvent("status", {"stage": "answer", "text": "Preparing your vastu review…"})
                vastu_started = time.monotonic()
                vastu_text = yield from self._stream_vastu_answer(session, vastu_payload)
                logger.info("session=%s stage=vastu_answer +%.1fs chars=%d", session.session_id,
                            time.monotonic() - vastu_started, len(vastu_text))
                final_vastu = self._finalize(vastu_text, vastu_payload, session)
                session.add_message("assistant", final_vastu)
                yield ChatEvent("done", {"content": final_vastu, "topic": "vastu",
                                         "birth_data": vastu_card, "mode": "vastu"})
                return

            session.active_subject = self._select_subject(session, message)
            if session.active_subject == "self":
                self._apply_recall(session)
            missing = self._missing_items(session)
            if missing:
                if "time" in missing:
                    self._active_slots(session).time_question_asked = True
                session.last_missing = missing
                yield from self._respond_guide(session, missing)
                logger.info("session=%s stage=guide +%.1fs", session.session_id, time.monotonic() - turn_started)
                return

            if skip_extraction:
                answer_mode = session.pending_answer_mode or _infer_answer_mode(message)
                session.pending_answer_mode = None
                answer_shape = (session.pending_answer_shape
                                or _infer_answer_shape(message, answer_mode))
                session.pending_answer_shape = None
            else:
                answer_mode = update.get("answer_mode") or _infer_answer_mode(message)
                answer_shape = update.get("answer_shape") or _infer_answer_shape(message, answer_mode)
            if answer_mode == "lookup":
                answer_shape = "lookup"
            deep = (answer_shape == "report")

            yield ChatEvent("status", {"stage": "chart", "text": "Calculating your birth chart (Lahiri sidereal)…"})
            try:
                result, card = self._compute_chart(session, deep=deep)
            except GeocodeError as exc:
                yield from self._respond_canned(
                    session,
                    "Birthplace could not be resolved on the map with confidence. "
                    f"({exc}) Retype it as \"City, State/Province, Country\" — "
                    "for example \"Jaipur, Rajasthan, India\" — to compute the chart.",
                )
                return

            session.chart_basis = card
            session.last_missing = []
            card["depth"] = answer_mode
            card["shape"] = answer_shape
            card["deep"] = deep
            card["needs_confirmation"] = self._needs_basis_confirmation(session)
            logger.info("session=%s stage=chart +%.1fs asc=%s mode=%s shape=%s deep=%s",
                        session.session_id, time.monotonic() - turn_started,
                        card.get("ascendant"), answer_mode, answer_shape, deep)
            yield ChatEvent("meta", {"birth_data": card, "chart_basis": card,
                                     "topic": session.slots.topic or "general",
                                     "depth": answer_mode, "shape": answer_shape, "deep": deep})

            if card["needs_confirmation"]:
                ask = self._confirmation_ask(session)
                session.basis_confirmation_sent = True
                session.awaiting_confirmation = True
                session.pending_answer_mode = answer_mode
                session.pending_answer_shape = answer_shape
                yield ChatEvent("delta", {"channel": "content", "text": ask})
                session.add_message("assistant", ask)
                logger.info("session=%s stage=confirm_basis +%.1fs", session.session_id,
                            time.monotonic() - turn_started)
                yield ChatEvent("done", {"content": ask, "topic": session.slots.topic or "general",
                                         "birth_data": card, "confirmation_required": True})
                return

            payload = self._build_chart_payload(session, result)
            yield ChatEvent("status", {"stage": "answer", "text": "Consulting the Jyotish engine…"})
            answer_started = time.monotonic()
            if answer_mode == "lookup":
                answer_text = yield from self._stream_lookup_answer(session, payload)
            else:
                answer_text = yield from self._stream_answer(session, payload, answer_shape)
            logger.info("session=%s stage=answer +%.1fs answer_chars=%d", session.session_id,
                        time.monotonic() - answer_started, len(answer_text))

            final_text = self._finalize(answer_text, payload, session)
            session.add_message("assistant", final_text)
            yield ChatEvent(
                "done",
                {
                    "content": final_text,
                    "topic": session.slots.topic or "general",
                    "birth_data": card,
                    "dasha": card.get("dasha"),
                    "shape": answer_shape,
                },
            )
            logger.info("session=%s stage=done total +%.1fs", session.session_id, time.monotonic() - turn_started)
        except DeepSeekError as exc:
            logger.warning("DeepSeek error on session %s: %s", session.session_id, exc)
            yield ChatEvent("error", {"message": self._api_error_message(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected chat failure on session %s", session.session_id)
            yield ChatEvent("error", {"message": f"Something went wrong while answering: {exc}"})
        finally:
            self.store.save()

    # ------------------------------------------------------------- decisions
    def _detect_muhurta(self, update: Dict[str, Any], message: str) -> Optional[Dict[str, Any]]:
        """Returns an intent dict when the turn is a muhurta/panchanga date-selection ask."""
        event = update.get("muhurta_event")
        keyword_hit = bool(_MUHURTA_PATTERN.search(message or ""))
        if not event and not keyword_hit:
            return None
        return {
            "event": event or _infer_muhurta_event(message),
            "start": update.get("muhurta_start"),
            "end": update.get("muhurta_end"),
        }

    def _missing_for_muhurta(self, session: ChatSession) -> List[str]:
        slots = session.slots
        missing: List[str] = []
        if not slots.place:
            missing.append("place")
        if slots.tz_offset is None:
            missing.append("tz")
        return missing

    def _ensure_coordinates(self, session: ChatSession,
                            slots: Optional[BirthSlots] = None) -> None:
        slots = slots or session.slots
        if slots.lat is None or slots.lon is None:
            lat, lon, note = resolve_coordinates(slots.place, None, None)
            slots.lat, slots.lon = lat, lon
            slots.resolved_note = note
        if not slots.resolved_place:
            slots.resolved_place = slots.place

    def _compute_muhurta(self, session: ChatSession, intent: Dict[str, Any]) -> tuple:
        slots = session.slots
        self._ensure_coordinates(session)
        tz = slots.tz_offset if slots.tz_offset is not None else 5.5
        rules = load_muhurta_rules()
        event_key = intent["event"]
        event_cfg = rules["events"][event_key]

        today = datetime.now(timezone.utc).replace(tzinfo=None).date()
        start_date = (datetime.strptime(intent["start"], "%Y-%m-%d").date()
                      if intent.get("start") else today)
        end_date = (datetime.strptime(intent["end"], "%Y-%m-%d").date()
                    if intent.get("end") else start_date + timedelta(days=45))
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        # Keep the reported range equal to the range actually searched
        if (end_date - start_date).days + 1 > MUHURTA_MAX_DAYS:
            end_date = start_date + timedelta(days=MUHURTA_MAX_DAYS - 1)

        birth_nak = birth_rashi = None
        birth_note = "birth data not provided — Tarabala/Chandrabala not applied"
        if slots.dob:
            birth_dt = slots.birth_datetime()
            if birth_dt:
                natal = calculate_d1_chart(birth_dt.year, birth_dt.month, birth_dt.day,
                                           birth_dt.hour, birth_dt.minute, birth_dt.second,
                                           tz, slots.lat, slots.lon)
                moon = natal.planets["Moon"]
                birth_nak = NAKSHATRA_INDEX[moon.nakshatra]
                birth_rashi = moon.sign_index
                time_note = "birth time given" if slots.time_reliable() else "birth time unavailable (noon used)"
                birth_note = (f"birth nakshatra {moon.nakshatra} (Tarabala), natal Moon sign {moon.sign} "
                              f"(Chandrabala); {time_note}")

        days = find_muhurta_days(
            start_date, end_date, tz, slots.lat, slots.lon, event_key,
            elevation_m=0.0, rules=rules,
            birth_nakshatra_index=birth_nak, birth_rashi_index=birth_rashi,
            include_windows=True, max_days=MUHURTA_MAX_DAYS,
        )

        card = slots.to_card()
        card.update({
            "mode": "muhurta",
            "event": event_cfg["label"],
            "range": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "suitable_days": len(days),
            "birth_note": birth_note,
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        session.chart_basis = card

        payload = build_muhurta_payload(
            event_key=event_key,
            event_label=event_cfg["label"],
            rules_source=event_cfg.get("source", ""),
            place=slots.resolved_place or slots.place,
            geo_note=slots.resolved_note or "Manual coordinates.",
            lat=slots.lat, lon=slots.lon, tz_offset=tz,
            range_start=start_date.isoformat(), range_end=end_date.isoformat(),
            total_days=(end_date - start_date).days + 1,
            days=days,
            birth_note=birth_note,
            recommended_lagnas=event_cfg.get("recommended_lagnas") or [],
            avoid_tithis=[str(t) for t in event_cfg.get("avoid_tithis", [])],
        )
        return payload, card

    def _stream_muhurta_answer(self, session: ChatSession, payload: str) -> Iterator[ChatEvent]:
        messages = [
            {"role": "system", "content": MUHURTA_SYSTEM_PROMPT},
            {"role": "system", "content": payload},
        ] + self._language_directive(session) + session.recent_messages(self.history_limit)
        parts: List[str] = []
        for chunk in self.client.stream(messages, thinking=DEEPSEEK_ANSWER_THINKING):
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        return "".join(parts)

    # ------------------------------------------------------------- compatibility
    def _active_slots(self, session: ChatSession) -> BirthSlots:
        """BirthSlots for the person this turn is about ('self' by default)."""
        return session.person(session.active_subject or "self")

    def _select_subject(self, session: ChatSession, message: str) -> str:
        """Picks which person store a turn is about; follows pronouns, resets otherwise."""
        hit = _SUBJECT_PATTERN.search(message or "")
        if hit:
            role = _SUBJECT_ROLE_MAP.get(hit.group(1).lower(), "other")
            keys = [key for key in session.people
                    if key == role or key.startswith(f"{role}:")]
            if keys:
                named = [key for key in keys if ":" in key]
                return named[-1] if named else keys[0]
            return role
        current = session.active_subject or "self"
        if current != "self" and _PRONOUN_FOLLOWUP.search(message or ""):
            return current
        return "self"

    def _detect_compatibility(self, session: ChatSession, update: Dict[str, Any],
                              message: str) -> bool:
        if update.get("compatibility_request") is True:
            return True
        if session.slots.topic == "compatibility":
            return True
        return bool(_COMPAT_PATTERN.search(message or ""))

    def _missing_for_compatibility(self, session: ChatSession) -> List[str]:
        slots = session.slots
        partner = session.person("partner")
        missing: List[str] = []
        if not slots.dob:
            missing.append("dob")
        if not slots.place:
            missing.append("place")
        if not partner.dob or not partner.place:
            missing.append("partner")
        return missing

    def _compute_compatibility(self, session: ChatSession) -> tuple:
        self._ensure_coordinates(session)
        partner = session.person("partner")
        self._ensure_coordinates(session, partner)

        def _d1(slots: BirthSlots):
            hour, minute, second = slots.birth_hour_minute()
            y, m, d = (int(part) for part in (slots.dob or "").split("-"))
            tz = slots.tz_offset if slots.tz_offset is not None else 5.5
            return calculate_d1_chart(y, m, d, hour, minute, second, tz, slots.lat, slots.lon)

        d1_a, d1_b = _d1(session.slots), _d1(partner)
        label_a = session.slots.name or "You"
        label_b = partner.name or "Partner"
        result = match_charts(d1_a, d1_b, label_a=label_a, label_b=label_b)

        def _note(slots: BirthSlots) -> str:
            return "birth time given" if slots.time_reliable() else "birth time unavailable (noon used)"

        payload = build_compatibility_payload(
            result, label_a=label_a, label_b=label_b,
            birth_note_a=_note(session.slots), birth_note_b=_note(partner),
        )
        data = result.to_dict()
        card = {
            "mode": "compatibility",
            "person_a": {"name": label_a, "dob": session.slots.dob,
                         "place": session.slots.resolved_place or session.slots.place},
            "person_b": {"name": label_b, "dob": partner.dob,
                         "place": partner.resolved_place or partner.place},
            "total": data["total"],
            "max_total": data["max_total"],
            "verdict": data["verdict"],
            "kutas": data["kutas"],
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        session.chart_basis = card
        return payload, card

    def _stream_compatibility_answer(self, session: ChatSession, payload: str) -> Iterator[ChatEvent]:
        messages = [
            {"role": "system", "content": COMPATIBILITY_SYSTEM_PROMPT},
            {"role": "system", "content": payload},
        ] + self._language_directive(session) + session.recent_messages(self.history_limit)
        parts: List[str] = []
        for chunk in self.client.stream(messages, thinking=DEEPSEEK_ANSWER_THINKING):
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        return "".join(parts)

    # ------------------------------------------------------------- rectification
    def _detect_rectification(self, session: ChatSession, update: Dict[str, Any],
                              message: str) -> bool:
        if update.get("rectify_request") is True:
            return True
        if _RECTIFY_PATTERN.search(message or ""):
            return True
        text = (message or "").lower()
        return (session.slots.tob_unknown
                and len(session.slots.historical_events) >= 2
                and any(word in text for word in ("time", "samay", "rectif")))

    def _missing_for_rectification(self, session: ChatSession) -> List[str]:
        slots = session.slots
        missing: List[str] = []
        if not slots.dob:
            missing.append("dob")
        if not slots.place:
            missing.append("place")
        if slots.tz_offset is None:
            missing.append("tz")
        if len(slots.historical_events) < 2:
            missing.append("events")
        return missing

    def _compute_rectification(self, session: ChatSession) -> tuple:
        slots = session.slots
        assert slots.dob, "date of birth validated before rectification"
        self._ensure_coordinates(session)
        topic = session.slots.topic or "general"
        result = rectify_birth_time(
            year=int(slots.dob[:4]), month=int(slots.dob[5:7]), day=int(slots.dob[8:10]),
            tz_offset=slots.tz_offset if slots.tz_offset is not None else 5.5,
            lat=slots.lat, lon=slots.lon,
            events=slots.historical_events,
            topic=topic,
        )
        payload = build_rectification_payload(
            name=slots.name, dob=slots.dob,
            place=slots.resolved_place or slots.place,
            topic=topic, result=result,
        )
        card = {
            "mode": "rectification",
            **result.to_dict(),
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        session.chart_basis = card
        return payload, card

    def _stream_rectification_answer(self, session: ChatSession,
                                     payload: str) -> Iterator[ChatEvent]:
        messages = [
            {"role": "system", "content": RECTIFICATION_SYSTEM_PROMPT},
            {"role": "system", "content": payload},
        ] + self._language_directive(session) + session.recent_messages(self.history_limit)
        parts: List[str] = []
        for chunk in self.client.stream(messages, thinking=DEEPSEEK_ANSWER_THINKING):
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        return "".join(parts)

    # ------------------------------------------------------------- vastu
    def _detect_vastu(self, update: Dict[str, Any], message: str) -> bool:
        if any(update.get(key) for key in ("vastu_facing", "vastu_slope", "vastu_plot_shape",
                                           "vastu_rooms", "vastu_water")):
            return True
        return bool(_VASTU_PATTERN.search(message or ""))

    def _merge_vastu(self, session: ChatSession, update: Dict[str, Any]) -> None:
        layout = session.vastu_layout
        for source_key, layout_key in (("vastu_facing", "facing"),
                                       ("vastu_slope", "slope"),
                                       ("vastu_plot_shape", "plot_shape")):
            value = update.get(source_key)
            if value:
                layout[layout_key] = value
        rooms = update.get("vastu_rooms")
        if isinstance(rooms, dict) and rooms:
            layout.setdefault("rooms", {}).update(rooms)
        water = update.get("vastu_water")
        if isinstance(water, dict) and water:
            layout.setdefault("water", {}).update(water)

    @staticmethod
    def _has_vastu_layout(session: ChatSession) -> bool:
        layout = session.vastu_layout
        return bool(layout.get("rooms") or layout.get("water") or layout.get("slope")
                    or layout.get("plot_shape") or layout.get("facing"))

    def _compute_vastu(self, session: ChatSession) -> tuple:
        layout = session.vastu_layout
        assessment = assess_layout(layout)
        card = {
            "mode": "vastu",
            "score": assessment.score,
            "counts": assessment.counts,
            "rooms_assessed": len(layout.get("rooms") or {}),
            "water_assessed": len(layout.get("water") or {}),
            "defect_count": assessment.counts.get("defect", 0),
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        session.chart_basis = card
        payload = build_vastu_payload(assessment, layout)
        return payload, card

    def _stream_vastu_answer(self, session: ChatSession, payload: str) -> Iterator[ChatEvent]:
        messages = [
            {"role": "system", "content": VASTU_SYSTEM_PROMPT},
            {"role": "system", "content": payload},
        ] + self._language_directive(session) + session.recent_messages(self.history_limit)
        parts: List[str] = []
        for chunk in self.client.stream(messages, thinking=DEEPSEEK_ANSWER_THINKING):
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        return "".join(parts)

    def _apply_recall(self, session: ChatSession) -> None:
        """
        Active memory recall: if the birth data matches a saved profile,
        reuse a stored birth time (never overriding an explicit 'unknown')
        and attach returning-native context for the answer.
        """
        if self.memory is None:
            return
        slots = session.slots
        if not (slots.dob and slots.place):
            return

        profile = None
        if slots.lat is not None and slots.lon is not None:
            profile = self.memory.find_matching(
                slots.dob, slots.tob, slots.tob_unknown,
                slots.lat, slots.lon, slots.tz_offset)
        if profile is None:
            profile = self.memory.find_by_dob_place(slots.dob, slots.resolved_place or slots.place)
        if profile is None:
            return

        birth = profile.get("birth") or {}
        used_saved_time = False
        if (not slots.tob and not slots.tob_unknown
                and birth.get("tob") and not birth.get("tob_unknown")):
            slots.tob = str(birth["tob"])
            used_saved_time = True
            if slots.tz_offset is None and birth.get("tz_offset") is not None:
                slots.tz_offset = birth["tz_offset"]
                slots.tz_estimated = bool(birth.get("tz_estimated", False))
            slots.resolved_note = (slots.resolved_note + " ").strip() + (
                "Birth time recalled from a saved profile — confirm or correct it.")

        last_question = ""
        candidates = [self.store.get(sid) for sid in profile.get("sessions", [])
                      if sid != session.session_id]
        candidates = [s for s in candidates if s is not None and s.messages]
        if candidates:
            latest = max(candidates, key=lambda s: s.updated_at)
            first_user = next(
                (m["content"] for m in latest.messages if m.get("role") == "user"), "")
            last_question = " ".join(first_user.split())[:140]

        session.recalled_profile = {
            "profile_id": profile["profile_id"],
            "name": profile.get("name", "Native"),
            "session_count": len(profile.get("sessions", [])),
            "last_question": last_question,
            "used_saved_time": used_saved_time,
        }
        logger.info("session=%s memory_recall profile=%s used_saved_time=%s",
                    session.session_id, profile["profile_id"], used_saved_time)

    def _missing_items(self, session: ChatSession) -> List[str]:
        """Returns missing-data keys for the active subject (see MISSING_LABELS)."""
        slots = self._active_slots(session)
        missing: List[str] = []
        if not slots.dob:
            missing.append("dob")
        if not slots.place:
            missing.append("place")
        if slots.core_ready():
            if not slots.tob and not slots.tob_unknown and not slots.time_question_asked:
                missing.append("time")
            if slots.tz_offset is None:
                missing.append("tz")
        return missing

    def _known_summary(self, session: ChatSession) -> str:
        slots = self._active_slots(session)
        pieces = []
        if session.active_subject not in ("self", ""):
            pieces.append(f"subject={session.active_subject} "
                          "(details describe this other person, not the user)")
        if slots.name:
            pieces.append(f"name={slots.name}")
        if slots.dob:
            pieces.append(f"DOB={slots.dob}")
        pieces.append(f"time={slots.tob or ('unknown' if slots.tob_unknown else 'not given')}")
        if slots.place:
            pieces.append(f"place={slots.place}")
        if slots.tz_offset is not None:
            pieces.append(f"tz={slots.tz_offset:+.2f}h")
        if session.slots.question:
            pieces.append(f"question={_short(session.slots.question, 120)}")
        return "; ".join(pieces) or "nothing yet"

    # ------------------------------------------------------------- guides
    def _respond_guide(self, session: ChatSession, missing: List[str]) -> Iterator[ChatEvent]:
        labels = [MISSING_LABELS.get(key, key) for key in missing]
        system = build_guide_prompt(self._known_summary(session), labels)
        messages = [{"role": "system", "content": system}] + self._language_directive(session) \
            + session.recent_messages(self.history_limit)
        parts: List[str] = []
        for chunk in self.client.stream(messages, thinking=False):
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        final_text = sanitize_absolute_language("".join(parts)).strip()
        if not final_text:
            final_text = self._canned_missing_text(session, missing)
        session.add_message("assistant", final_text)
        yield ChatEvent("done", {"content": final_text, "topic": session.slots.topic or "general"})

    def _respond_canned(self, session: ChatSession, text: str) -> Iterator[ChatEvent]:
        yield ChatEvent("delta", {"channel": "content", "text": text})
        session.add_message("assistant", text)
        yield ChatEvent("done", {"content": text, "topic": session.slots.topic or "general"})

    @staticmethod
    def _canned_missing_text(session: ChatSession, missing: List[str]) -> str:
        if "dob" in missing:
            return ("To compute the chart, provide: **date of birth** (e.g. 1995-05-15), "
                    "**exact birth time** if known (e.g. 14:30), and **birthplace** "
                    "(e.g. Jaipur, Rajasthan, India).")
        if "place" in missing:
            return "Provide the **birthplace** as \"City, State/Province, Country\" so the chart can be computed."
        if "time" in missing:
            return ("Provide the **exact birth time** (e.g. 14:30) and time zone if known. "
                    "If the time is unknown, state so and a neutral noon chart will be used with reduced confidence.")
        return "Provide the **time zone / UTC offset** of the birthplace (e.g. IST +05:30) so the chart is accurate."

    # ------------------------------------------------------------- compute
    def _compute_chart(self, session: ChatSession, deep: bool = False):
        slots = self._active_slots(session)
        assert slots.dob and slots.place, "core fields validated before compute"

        self._ensure_coordinates(session, slots)

        birth_dt = slots.birth_datetime()
        if birth_dt is None:
            raise ValueError(f"Invalid date of birth: {slots.dob!r}")
        hour, minute, second = slots.birth_hour_minute()
        time_reliable = slots.time_reliable()
        tz = slots.tz_offset if slots.tz_offset is not None else 5.5

        topic = session.slots.topic or "general"
        engine_question = (f"{TOPIC_QUESTION_PREFIX.get(topic, topic)} | "
                           f"{session.slots.question or session.messages[-1]['content'][:400]}")

        result = consumer_answer(
            year=birth_dt.year, month=birth_dt.month, day=birth_dt.day,
            hour=hour, minute=minute, second=float(second),
            tz_offset=tz, lat=slots.lat, lon=slots.lon,
            place=slots.resolved_place,
            question=engine_question,
            time_reliable=time_reliable,
            query_dt=datetime.now(timezone.utc).replace(tzinfo=None),
            historical_events=slots.historical_events or None,
            full_matrix=True,
            deep_planets=deep,
        )

        card = slots.to_card()
        card.update({
            "ascendant": f"{result.d1.ascendant_sign} {result.d1.ascendant_degree_in_sign:.2f}°",
            "moon": (f"{result.d1.planets['Moon'].sign} · {result.d1.planets['Moon'].nakshatra} "
                     f"pada {result.d1.planets['Moon'].nakshatra_pada}"),
            "dasha": result.timing.current_md_ad_pd,
            "vargas": list(result.vargas.keys()),
            "computed_at": datetime.now().isoformat(timespec="seconds"),
        })
        session.chart_basis = card
        session.kundali = self._build_kundali(session, result, card, slots)
        if self.memory is not None and slots is session.slots:
            try:
                self.memory.upsert_from_session(session)
            except Exception:
                logger.warning("memory upsert failed for session %s", session.session_id, exc_info=True)
        session.last_result = result  # cached for the payload step
        session.last_dasha_detail = self._dasha_detail(birth_dt, result)
        return result, card

    @staticmethod
    def _build_kundali(session: ChatSession, result, card: Dict[str, Any],
                       slots: Optional[BirthSlots] = None) -> Dict[str, Any]:
        """Structured kundali record (birth details + verified chart facts)."""
        slots = slots or session.slots
        moon = result.d1.planets["Moon"]
        return {
            "session_id": session.session_id,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "birth": {
                "name": slots.name or "Native",
                "dob": slots.dob,
                "tob": slots.tob,
                "tob_unknown": slots.tob_unknown,
                "place": slots.resolved_place or slots.place,
                "place_query": slots.place,
                "lat": slots.lat,
                "lon": slots.lon,
                "tz_offset": slots.tz_offset,
                "tz_estimated": slots.tz_estimated,
            },
            "chart": {
                "ayanamsha": "Lahiri (Chitrapaksha)",
                "ascendant": card.get("ascendant"),
                "moon_sign": moon.sign,
                "moon_nakshatra": moon.nakshatra,
                "moon_nakshatra_pada": moon.nakshatra_pada,
                "dasha": card.get("dasha"),
                "vargas": card.get("vargas", []),
            },
        }

    @staticmethod
    def _dasha_detail(birth_dt: datetime, result) -> str:
        """Exact MD/AD/PD boundaries + upcoming sub-periods at query time."""
        try:
            timeline = calculate_vimshottari_timeline(birth_dt, result.d1.planets["Moon"].longitude)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            state = get_dasha_at_date(timeline, now)
            if not state:
                return ""
            parts = [
                f"MD {state.mahadasha}: {state.md_period.start_date:%Y-%m-%d} to {state.md_period.end_date:%Y-%m-%d}",
                f"AD {state.antardasha}: {state.ad_period.start_date:%Y-%m-%d} to {state.ad_period.end_date:%Y-%m-%d}",
                f"PD {state.pratyantardasha}: {state.pd_period.start_date:%Y-%m-%d} to {state.pd_period.end_date:%Y-%m-%d}",
            ]
            next_ads = [
                p for p in timeline
                if p.level == "AD" and p.parent_md == state.mahadasha and p.start_date > now
            ][:3]
            if next_ads:
                parts.append("Next Antardashas in the same Mahadasha: " + "; ".join(
                    f"{p.lord} {p.start_date:%Y-%m-%d} to {p.end_date:%Y-%m-%d}" for p in next_ads
                ))
            next_pds = [
                p for p in timeline
                if p.level == "PD" and p.parent_md == state.mahadasha
                and p.parent_ad == state.antardasha and p.start_date > now
            ][:3]
            if next_pds:
                parts.append("Next Pratyantardashas in the current Antardasha: " + "; ".join(
                    f"{p.lord} {p.start_date:%Y-%m-%d} to {p.end_date:%Y-%m-%d}" for p in next_pds
                ))
            return " | ".join(parts)
        except Exception:
            return ""

    # ------------------------------------------------------------- answer
    def _language_directive(self, session: ChatSession) -> List[Dict[str, str]]:
        if not session.reply_language:
            return []
        return [{"role": "system",
                 "content": f"Reply in {session.reply_language}. Keep this language for the whole answer."}]

    def _build_chart_payload(self, session: ChatSession, result) -> str:
        slots = self._active_slots(session)
        question = self._latest_question(session)
        topic = session.slots.topic or "general"
        subject = session.active_subject or "self"
        try:
            source_refs = reference_lines(retrieve_references(question, topic))
        except Exception:
            source_refs = []
        try:
            library_passages = search_library(question, topic=topic, limit=3)
            if library_passages:
                source_refs = source_refs + [
                    "Verbatim passages from the public-domain library "
                    "(quote only from these texts, always with book, edition and locator):"
                ] + library_reference_lines(library_passages)
        except Exception:
            pass
        answer_shape = (session.chart_basis or {}).get("shape") or "report"
        assessment = assess_capability(
            question, answer_shape, result.promise, slots.time_reliable())
        reason_tags = promise_reason_tags(getattr(result, "promise", None))
        return build_chart_payload(
            result,
            name=slots.name,
            dob=slots.dob or "unknown",
            tob=slots.tob or "",
            tz_offset=slots.tz_offset if slots.tz_offset is not None else 5.5,
            place=slots.resolved_place or slots.place,
            geo_note=slots.resolved_note or "Manual coordinates.",
            time_reliable=slots.time_reliable(),
            question=question,
            topic=topic,
            tob_unknown=slots.tob_unknown,
            tz_estimated=slots.tz_estimated,
            dasha_detail=session.last_dasha_detail,
            include_full_matrix=(session.chart_basis or {}).get("depth") == "lookup",
            include_deep_planets=(session.chart_basis or {}).get("deep") is True,
            returning_note=self._returning_note(session),
            source_references=source_refs,
            expectation_block=assessment_block(assessment),
            subject_label="" if subject == "self" else subject,
            capability_gap=assessment.verdict != "full",
            unfavorable=bool(reason_tags),
            reason_tags=reason_tags,
        )

    @staticmethod
    def _returning_note(session: ChatSession) -> str:
        recalled = session.recalled_profile
        if not recalled:
            return ""
        note = (f"Returning native: birth data matches a saved profile "
                f"\"{recalled.get('name', 'Native')}\" "
                f"({recalled.get('session_count', 0)} linked chat(s)).")
        if recalled.get("last_question"):
            note += f" Previous chat asked: \"{recalled['last_question']}\"."
        if recalled.get("used_saved_time"):
            note += (" The birth time was recalled from that saved profile, not stated now — "
                     "say so plainly and invite correction.")
        else:
            note += " Acknowledge the saved profile in one neutral line; no familiarity or sentiment."
        return note

    def _stream_answer(self, session: ChatSession, payload: str,
                       shape: str = "report") -> Iterator[ChatEvent]:
        prompt = SHAPE_PROMPTS.get(shape, ANSWER_SYSTEM_PROMPT)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "system", "content": payload},
        ] + self._language_directive(session) + session.recent_messages(self.history_limit)

        # Thinking tokens count against max_tokens: with reasoning enabled, a
        # 900-token cap can be eaten entirely by the thinking phase, leaving no
        # answer text (reasoning streamed, content empty). Give answers room.
        if shape == "report":
            extra: Dict[str, Any] = {}
        else:
            extra = {"max_tokens": 4096 if DEEPSEEK_ANSWER_THINKING else 900}
        parts: List[str] = []
        stream_started = time.monotonic()
        first_content_logged = False
        for chunk in self.client.stream(messages, thinking=DEEPSEEK_ANSWER_THINKING, **extra):
            if chunk["type"] == "content" and not first_content_logged:
                first_content_logged = True
                logger.info("session=%s stage=answer first_content +%.1fs (reasoning streamed before it)",
                            session.session_id, time.monotonic() - stream_started)
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        return "".join(parts)

    def _stream_lookup_answer(self, session: ChatSession, payload: str) -> Iterator[ChatEvent]:
        messages = [
            {"role": "system", "content": LOOKUP_SYSTEM_PROMPT},
            {"role": "system", "content": payload},
        ] + self._language_directive(session) + session.recent_messages(self.history_limit)
        parts: List[str] = []
        # Lookup answers also need headroom for the reasoning phase.
        lookup_budget = 4096 if DEEPSEEK_ANSWER_THINKING else 700
        for chunk in self.client.stream(messages, max_tokens=lookup_budget,
                                        thinking=DEEPSEEK_ANSWER_THINKING):
            yield ChatEvent("delta", {"channel": chunk["type"], "text": chunk["text"]})
            if chunk["type"] == "content":
                parts.append(chunk["text"])
        return "".join(parts)

    # ------------------------------------------------------------- panchanga lookup
    def _detect_panchanga_lookup(self, update: Dict[str, Any], message: str) -> Optional[str]:
        """Single-date panchanga question → ISO date string; date-selection asks stay muhurta."""
        text = message or ""
        if update.get("muhurta_event"):
            return None
        if not _PANCHANGA_ASK.search(text) or _PANCHANGA_MUHURTA_WORDS.search(text):
            return None
        if _infer_muhurta_event(text) != "general":
            return None
        today = datetime.now(timezone.utc).date()
        if re.search(r"\btomorrow\b", text, re.IGNORECASE):
            return (today + timedelta(days=1)).isoformat()
        if re.search(r"\byesterday\b", text, re.IGNORECASE):
            return (today - timedelta(days=1)).isoformat()
        if update.get("muhurta_start"):
            return str(update["muhurta_start"])
        return today.isoformat()

    def _answer_panchanga_lookup(self, session: ChatSession, day_str: str,
                                 turn_started: float) -> Iterator[ChatEvent]:
        missing = self._missing_for_muhurta(session)
        if missing:
            session.last_missing = missing
            yield from self._respond_guide(session, missing)
            return
        try:
            self._ensure_coordinates(session)
        except GeocodeError as exc:
            yield from self._respond_canned(
                session,
                "Location could not be resolved with confidence. "
                f"({exc}) Retype the place as \"City, State/Province, Country\".",
            )
            return
        slots = session.slots
        tz = slots.tz_offset if slots.tz_offset is not None else 5.5
        try:
            y, m, d = (int(part) for part in day_str.split("-"))
            day = compute_panchanga(y, m, d, tz, slots.lat, slots.lon, 0.0)
        except (PanchangaError, ValueError) as exc:
            yield from self._respond_canned(session, f"Panchanga computation failed for that date: {exc}")
            return
        payload = build_panchanga_payload(day, slots.resolved_place or slots.place,
                                          slots.resolved_note or "Manual coordinates.")
        card = slots.to_card()
        card.update({
            "mode": "panchanga",
            "date": day_str,
            "needs_confirmation": self._needs_basis_confirmation(session, birth_time_relevant=False),
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        session.chart_basis = card
        session.last_missing = []
        logger.info("session=%s stage=panchanga_lookup date=%s +%.1fs", session.session_id, day_str,
                    time.monotonic() - turn_started)
        yield ChatEvent("meta", {"birth_data": card, "chart_basis": card, "topic": "panchanga",
                                 "mode": "panchanga", "depth": "lookup"})
        yield ChatEvent("status", {"stage": "answer", "text": "Preparing the panchanga…"})
        text = yield from self._stream_lookup_answer(session, payload)
        final = self._finalize(text, payload, session, allow_confirmation=False, birth_time_relevant=False)
        session.add_message("assistant", final)
        yield ChatEvent("done", {"content": final, "topic": "panchanga",
                                 "birth_data": card, "mode": "panchanga"})

    # ------------------------------------------------------------- finalize helpers
    @staticmethod
    def _canonical_confidence(payload: str) -> str:
        """Engine confidence level from the payload's canonical block ('' if absent)."""
        match = re.search(r"ASSESSMENT CONFIDENCE[^\n]*\n- Level:\s*(Low|Medium|High)",
                          payload or "")
        return match.group(1) if match else ""

    def _finalize(self, text: str, payload: str, session: ChatSession, *,
                  allow_confirmation: bool = False, birth_time_relevant: bool = True) -> str:
        final = sanitize_absolute_language(text).strip()
        canonical = self._canonical_confidence(payload)
        if canonical:
            normalized = normalize_confidence_labels(final, canonical)
            if normalized != final:
                logger.warning("session=%s normalized hybrid confidence label to %s",
                               session.session_id, canonical)
                final = normalized
        verdict = assessment_verdict_from_payload(payload)
        if verdict == "blocked" and timing_claim_detected(final):
            logger.warning("session=%s reply presented timing although the promise gate blocked it",
                           session.session_id)
            final += "\n\n" + correction_for_verdict(verdict)
        violations = verify_answer(final, payload)
        if violations:
            logger.warning("session=%s unverified figures in answer: %s", session.session_id, violations[:5])
            final += ("\n\n_Note: some figures above could not be cross-checked against the computed "
                      "data — treat those as approximate._")
        try:
            from ..remedies.safety import safety_check
            verdict = safety_check(session.slots.question or "", [final])
            if not verdict.allowed:
                final += ("\n\n_Note: part of this reply may touch on unsafe or treatment-related "
                          "territory; ignore any such advice and consult a qualified professional._")
            for referral in verdict.referrals:
                if referral not in final:
                    final += f"\n\n_{referral}_"
        except Exception:
            pass
        if allow_confirmation and self._needs_basis_confirmation(
                session, birth_time_relevant=birth_time_relevant):
            session.basis_confirmation_sent = True
            session.awaiting_confirmation = True
            final += ("\n\n_If any birth detail above is off — date, exact time, or place — state the "
                      "correction and the chart will be recomputed; timing accuracy depends on it._")
        return final

    def _needs_basis_confirmation(self, session: ChatSession, *,
                                  birth_time_relevant: bool = True) -> bool:
        if session.basis_confirmation_sent:
            return False
        slots = self._active_slots(session)
        if slots.tz_estimated:
            return True
        return birth_time_relevant and not slots.time_reliable()

    def _confirmation_ask(self, session: ChatSession) -> str:
        slots = self._active_slots(session)
        tz = f"{slots.tz_offset:+.2f}h" if slots.tz_offset is not None else "default +05:30"
        if slots.tz_estimated:
            tz += " (estimated)"
        time_txt = slots.tob or "time not given — noon chart"
        return (
            f"Confirm the chart basis before computation: **{slots.name or 'you'}**, born **{slots.dob}** "
            f"at **{time_txt}**, **{slots.resolved_place or slots.place}**, timezone **{tz}**.\n\n"
            "Reply **yes** to proceed, or state the correction (date, exact time, or birthplace)."
        )

    @staticmethod
    def _trivial_kind(message: str) -> Optional[str]:
        text = (message or "").strip()
        if not text or len(text) > 24:
            return None
        if _ACK_YES.fullmatch(text):
            return "yes"
        if _ACK_NO.fullmatch(text):
            return "no"
        if _ACK_THANKS.fullmatch(text):
            return "thanks"
        return None

    @staticmethod
    def _prediction_snapshot(session: ChatSession) -> Dict[str, Any]:
        """Compact 'what was said at report time' record for calibration review."""
        result = getattr(session, "last_result", None)
        answer = getattr(result, "answer", None)
        timing = getattr(result, "timing", None)
        basis = session.chart_basis or {}
        snapshot = {
            "topic": session.slots.topic or "general",
            "dasha_at_report": basis.get("dasha"),
            "current_period": getattr(timing, "current_md_ad_pd", None),
            "confidence": getattr(answer, "confidence", None),
        }
        return {key: value for key, value in snapshot.items() if value}

    @staticmethod
    def _handle_outcome(session: ChatSession, outcome: Dict[str, Any]) -> str:
        """Stores a user-reported outcome and returns an acknowledgement (or '')."""
        verdict = str(outcome.get("verdict", ""))
        if verdict not in ("happened", "did_not_happen", "partial"):
            return ""
        entry = {
            "event": outcome.get("event") or "unspecified event",
            "date": outcome.get("date"),
            "verdict": verdict,
            "note": outcome.get("note") or "",
            "prediction": ChatOrchestrator._prediction_snapshot(session),
        }
        session.outcomes.append(entry)
        record_outcome(session.session_id, entry)
        label = {
            "happened": "has happened",
            "did_not_happen": "did not happen as suggested",
            "partial": "partly happened",
        }[verdict]
        when = f" around {entry['date']}" if entry.get("date") else ""
        return (
            f"Outcome logged: the {entry['event']} {label}{when}. "
            "Outcome feedback is stored separately from the reading, used only to review "
            "calibration over time; it does not change the chart analysis retroactively."
        )

    def _latest_question(self, session: ChatSession) -> str:
        if session.slots.question:
            return session.slots.question
        for msg in reversed(session.messages):
            if msg["role"] == "user":
                return msg["content"][:400]
        return ""

    @staticmethod
    def _api_error_message(exc: DeepSeekError) -> str:
        text = str(exc)
        if "DEEPSEEK_API_KEY" in text:
            return ("The DeepSeek API key is not configured on the server. "
                    "Add DEEPSEEK_API_KEY to SweetAstro/.env and restart the server.")
        return f"The AI service could not be reached: {text}"
