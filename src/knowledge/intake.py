"""
Research intake gate — source-verified claims for future engine methods.

Purpose (system_report §7): when a classical value or method is missing, the
engine must never guess and the live LLM must never "research" it. Instead a
candidate claim enters this quarantine, and can only become usable through an
explicit human verification that supplies the full citation (source title,
edition, locator) and a verifier name. Drafts are quarantined here and are
never read by the chat/answer layer.

Storage is append-only JSONL (auditable, no rewrite races):
    data/research_intake/drafts.jsonl      — candidate claims (quarantine)
    data/research_intake/decisions.jsonl   — verify/reject decisions

Only ``servable_claim_lines()`` returns verified claims, and nothing in the
chat/answer path calls it automatically: promotion into structured engine data
(rules JSON, knowledge entries) remains a reviewed, tested code change.

CLI:  python research_intake.py add|list|verify|reject|report
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "research_intake"

REQUIRED_DRAFT_FIELDS = ("claim", "target", "source_title", "edition", "locator", "source_class")
REQUIRED_VERIFY_FIELDS = ("source_title", "edition", "locator")

# Reliable-source test (user directive, 2026-09-13):
#   canon  - classical text with an edition and chapter/verse locator; may ground classical values
#   known  - published modern work (author/publisher identifiable); may interpret classical methods
#   tech   - modern technique/teaching (incl. web/video courses); must be labelled modern
#   verify - tradition is real but the edition is unverified: cannot be promoted until reclassified
#   web    - online source (e.g. a YouTube video/lesson) with a URL; modern-labelled only,
#            never authority for a classical value or table
SOURCE_CLASSES = ("canon", "known", "tech", "verify", "web")
CLASSICAL_SOURCE_CLASSES = ("canon", "known")
MODERN_SOURCE_CLASSES = ("tech", "web")

VALID_STATUSES = ("draft", "verified", "rejected")


class ResearchIntakeError(ValueError):
    """Raised when the intake gate refuses an operation."""


@dataclass
class ResearchClaim:
    claim_id: str
    claim: str
    target: str
    source_title: str
    edition: str
    locator: str
    notes: str = ""
    source_class: str = "verify"
    url: str = ""
    status: str = "draft"
    created_utc: str = ""
    verifier: str = ""
    decided_utc: str = ""
    decision_reason: str = ""
    modern_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "target": self.target,
            "source_title": self.source_title,
            "edition": self.edition,
            "locator": self.locator,
            "notes": self.notes,
            "source_class": self.source_class,
            "url": self.url,
            "status": self.status,
            "created_utc": self.created_utc,
            "verifier": self.verifier,
            "decided_utc": self.decided_utc,
            "decision_reason": self.decision_reason,
            "modern_only": self.modern_only,
        }

    def citation(self) -> str:
        base = f"{self.source_title} ({self.edition}), {self.locator}"
        return f"{base} [web: {self.url}]" if self.url else base


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def intake_dir() -> Path:
    override = os.environ.get("SWEETASTRO_RESEARCH_INTAKE_DIR")
    return Path(override) if override else DEFAULT_DIR


def _drafts_path(directory: Optional[Path] = None) -> Path:
    return (directory or intake_dir()) / "drafts.jsonl"


def _decisions_path(directory: Optional[Path] = None) -> Path:
    return (directory or intake_dir()) / "decisions.jsonl"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


def _validate_required(fields: Dict[str, str], required: Sequence[str]) -> None:
    missing = [name for name in required if not _clean(fields.get(name))]
    if missing:
        raise ResearchIntakeError(
            "Missing required field(s): " + ", ".join(missing) +
            ". A claim cannot enter or leave quarantine without a verifiable citation."
        )


def next_claim_id(existing: Sequence[Dict[str, Any]]) -> str:
    highest = 0
    for record in existing:
        raw = str(record.get("claim_id", ""))
        if raw.startswith("RC-"):
            try:
                highest = max(highest, int(raw[3:]))
            except ValueError:
                continue
    return f"RC-{highest + 1:04d}"


def _append_decision(directory: Optional[Path], claim_id: str, action: str,
                     verifier: str, reason: str, citation: str,
                     citation_fields: Optional[Dict[str, str]] = None,
                     modern_only: bool = False) -> None:
    _append_jsonl(_decisions_path(directory), {
        "claim_id": claim_id,
        "action": action,
        "verifier": verifier,
        "reason": reason,
        "citation": citation,
        "citation_fields": citation_fields or {},
        "modern_only": modern_only,
        "decided_utc": _utc_now(),
    })


def add_draft(claim: str, target: str, source_title: str, edition: str,
              locator: str, notes: str = "", source_class: str = "verify",
              url: str = "", directory: Optional[Path] = None) -> ResearchClaim:
    """Add a candidate claim to quarantine. Requires the citation fields up front.

    ``source_class`` applies the reliable-source test: 'verify' means the source
    is real but the edition is unchecked, so the claim cannot be promoted until
    it is reclassified (the default is intentionally strict). A 'web' source
    (e.g. a video/lesson) requires a URL and is modern-labelled only.
    """
    fields = {
        "claim": claim, "target": target, "source_title": source_title,
        "edition": edition, "locator": locator, "source_class": source_class,
    }
    _validate_required(fields, REQUIRED_DRAFT_FIELDS)
    source_class = _clean(source_class).lower()
    if source_class not in SOURCE_CLASSES:
        raise ResearchIntakeError(
            f"Unknown source_class {source_class!r}; use one of: {', '.join(SOURCE_CLASSES)}.")
    url = _clean(url)
    if source_class == "web" and not url:
        raise ResearchIntakeError(
            "source_class 'web' requires a URL (the video/lesson link).")
    drafts = _read_jsonl(_drafts_path(directory))
    record = {
        "claim_id": next_claim_id(drafts),
        "claim": _clean(claim),
        "target": _clean(target),
        "source_title": _clean(source_title),
        "edition": _clean(edition),
        "locator": _clean(locator),
        "notes": _clean(notes),
        "source_class": source_class,
        "url": url,
        "created_utc": _utc_now(),
    }
    _append_jsonl(_drafts_path(directory), record)
    return ResearchClaim(**record)


def _latest_decisions(decisions: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for decision in decisions:
        claim_id = str(decision.get("claim_id", ""))
        if claim_id:
            latest[claim_id] = decision
    return latest


def load_claims(directory: Optional[Path] = None) -> List[ResearchClaim]:
    """All claims with their latest decision applied (draft / verified / rejected)."""
    drafts = _read_jsonl(_drafts_path(directory))
    decisions = _read_jsonl(_decisions_path(directory))
    latest = _latest_decisions(decisions)
    claims: List[ResearchClaim] = []
    for record in drafts:
        claim = ResearchClaim(**record)
        decision = latest.get(claim.claim_id)
        if decision:
            claim.status = str(decision.get("action", "draft"))
            claim.verifier = str(decision.get("verifier", ""))
            claim.decided_utc = str(decision.get("decided_utc", ""))
            claim.decision_reason = str(decision.get("reason", ""))
            claim.modern_only = bool(decision.get("modern_only", False))
            corrected = decision.get("citation_fields") or {}
            if claim.status == "verified" and isinstance(corrected, dict):
                for key in ("source_title", "edition", "locator", "source_class", "url"):
                    if _clean(corrected.get(key)):
                        setattr(claim, key, _clean(corrected.get(key)))
        claims.append(claim)
    return claims


def get_claim(claim_id: str, directory: Optional[Path] = None) -> ResearchClaim:
    for claim in load_claims(directory):
        if claim.claim_id == claim_id:
            return claim
    raise ResearchIntakeError(f"Unknown claim id: {claim_id}")


def verify_claim(claim_id: str, verifier: str, *, source_title: Optional[str] = None,
                 edition: Optional[str] = None, locator: Optional[str] = None,
                 source_class: Optional[str] = None, url: Optional[str] = None,
                 note: str = "", directory: Optional[Path] = None) -> ResearchClaim:
    """Promote a quarantined claim to verified — only with a full citation.

    Reliable-source test: the source class must be resolved (not 'verify') and
    must be one of canon/known/tech/web. 'web' additionally requires a URL and
    is marked modern-only, so it can never ground a classical value.
    """
    if not _clean(verifier):
        raise ResearchIntakeError("A verifier name is required to promote a claim.")
    claim = get_claim(claim_id, directory)
    if claim.status == "verified":
        raise ResearchIntakeError(f"{claim_id} is already verified.")
    fields = {
        "source_title": _clean(source_title) or claim.source_title,
        "edition": _clean(edition) or claim.edition,
        "locator": _clean(locator) or claim.locator,
    }
    _validate_required(fields, REQUIRED_VERIFY_FIELDS)
    effective_class = (_clean(source_class) or claim.source_class).lower()
    if effective_class not in SOURCE_CLASSES:
        raise ResearchIntakeError(
            f"Unknown source_class {effective_class!r}; use one of: {', '.join(SOURCE_CLASSES)}.")
    if effective_class == "verify":
        raise ResearchIntakeError(
            "'verify' cannot be promoted — check the edition and reclassify as "
            "'canon' or 'known' (or 'tech'/'web' for a declared modern practice).")
    url_value = _clean(url) or claim.url
    if effective_class == "web":
        if not url_value.lower().startswith(("http://", "https://")):
            raise ResearchIntakeError(
                "source_class 'web' requires an http(s) URL for verification.")
    citation = f"{fields['source_title']} ({fields['edition']}), {fields['locator']}"
    if url_value:
        citation += f" [web: {url_value}]"
    fields["source_class"] = effective_class
    fields["url"] = url_value
    _append_decision(directory, claim_id, "verified", _clean(verifier),
                     _clean(note), citation, citation_fields=fields,
                     modern_only=(effective_class == "web"))
    return get_claim(claim_id, directory)


def reject_claim(claim_id: str, reason: str, verifier: str = "",
                 directory: Optional[Path] = None) -> ResearchClaim:
    """Reject a claim; a reason is mandatory (no silent deletions)."""
    if not _clean(reason):
        raise ResearchIntakeError("A rejection reason is required.")
    claim = get_claim(claim_id, directory)
    if claim.status == "verified":
        raise ResearchIntakeError(f"{claim_id} is already verified; verified claims are terminal.")
    _append_decision(directory, claim_id, "rejected", _clean(verifier),
                     _clean(reason), claim.citation())
    return get_claim(claim_id, directory)


def servable_claims(target: Optional[str] = None,
                    include_modern: bool = False) -> List[ResearchClaim]:
    """Verified claims only. Quarantined drafts are never included.

    Web/tech claims are modern-only and excluded by default so a video/lesson
    can never ground a classical value; pass ``include_modern=True`` for a
    declared modern-practice context. This is the opt-in entry point: nothing
    in the chat/answer path calls it automatically.
    """
    claims = [c for c in load_claims() if c.status == "verified"]
    if not include_modern:
        claims = [c for c in claims if not c.modern_only]
    if target:
        claims = [c for c in claims if c.target == target]
    return claims


def servable_claim_lines(target: Optional[str] = None,
                         include_modern: bool = False) -> List[str]:
    """Citation lines for verified claims (format matches retrieval lines)."""
    return [
        f'- "{c.claim}" ({c.target}, {c.source_class}) — {c.citation()} [verified by {c.verifier}]'
        for c in servable_claims(target, include_modern=include_modern)
    ]


def claim_report(directory: Optional[Path] = None) -> str:
    claims = load_claims(directory)
    counts = {status: 0 for status in VALID_STATUSES}
    for claim in claims:
        counts[claim.status] = counts.get(claim.status, 0) + 1
    lines = [
        "# Research intake report",
        "",
        f"Total claims: {len(claims)} — draft {counts['draft']}, "
        f"verified {counts['verified']}, rejected {counts['rejected']}",
        "",
        "Only verified claims with a complete citation are servable. "
        "Drafts are quarantined and never reach the chat/answer layer.",
        "",
    ]
    for claim in claims:
        marker = {"draft": "DRAFT", "verified": "VERIFIED", "rejected": "REJECTED"}.get(
            claim.status, claim.status.upper())
        lines.append(f"- [{marker}] {claim.claim_id} · {claim.target}: {claim.claim}")
        modern = " (modern-only)" if claim.modern_only else ""
        lines.append(f"  source class: {claim.source_class}{modern}")
        lines.append(f"  citation: {claim.citation()}")
        if claim.status == "verified":
            lines.append(f"  verified by {claim.verifier} on {claim.decided_utc}")
        elif claim.status == "rejected":
            lines.append(f"  rejected: {claim.decision_reason}")
    return "\n".join(lines)


def content_fingerprint(claim: str, source_title: str, locator: str) -> str:
    """Stable fingerprint for duplicate detection in tooling/tests."""
    payload = "|".join(_clean(part) for part in (claim, source_title, locator))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
