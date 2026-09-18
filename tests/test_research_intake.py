"""
Research intake gate tests.

Locks the workflow: claims enter quarantine with a citation, only a human
verification with a complete citation promotes them, drafts are never servable,
and rejections require a reason.
"""

import pytest

from SweetAstro.src.knowledge.intake import (
    ResearchIntakeError, add_draft, claim_report, content_fingerprint,
    get_claim, load_claims, next_claim_id, reject_claim, servable_claim_lines,
    servable_claims, verify_claim,
)


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SWEETASTRO_RESEARCH_INTAKE_DIR", str(tmp_path / "intake"))
    yield tmp_path / "intake"


def _draft(**overrides):
    base = dict(
        claim="Moon in Capricorn Mrityu Bhaga is 20° (not 25°).",
        target="mrityu_bhaga",
        source_title="Jataka Parijata",
        edition="Subrahmanya Sastri translation",
        locator="Ch. 1 v. 58",
        source_class="canon",
    )
    base.update(overrides)
    return add_draft(**base)


# ---------------------------------------------------------------------------
# Quarantine requires a citation up front
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["claim", "target", "source_title", "edition", "locator"])
def test_add_requires_full_citation(missing):
    fields = dict(
        claim="X", target="t", source_title="Book", edition="1st", locator="p.1",
    )
    fields[missing] = "  "
    with pytest.raises(ResearchIntakeError, match="Missing required field"):
        add_draft(**fields)


def test_claim_ids_are_sequential():
    assert _draft().claim_id == "RC-0001"
    assert _draft().claim_id == "RC-0002"
    assert next_claim_id([{"claim_id": "RC-0007"}]) == "RC-0008"


# ---------------------------------------------------------------------------
# Drafts are quarantined, never servable
# ---------------------------------------------------------------------------

def test_draft_is_quarantined_and_never_servable():
    claim = _draft()
    assert claim.status == "draft"
    assert get_claim(claim.claim_id).status == "draft"
    assert servable_claims() == []
    assert servable_claim_lines() == []
    report = claim_report()
    assert "[DRAFT]" in report and "draft 1, verified 0" in report


def test_retrieval_ignores_quarantined_claims():
    _draft(claim="Zorblax unique unverified marker claim")
    from SweetAstro.src.knowledge.retrieval import retrieve_references

    joined = " ".join(e.to_line() for e in retrieve_references("zorblax marker", topic="general"))
    assert "zorblax" not in joined.lower()


# ---------------------------------------------------------------------------
# Verification gate
# ---------------------------------------------------------------------------

def test_verify_requires_verifier_name():
    claim = _draft()
    with pytest.raises(ResearchIntakeError, match="verifier name"):
        verify_claim(claim.claim_id, "   ")


def test_verify_refuses_incomplete_citation_even_with_verifier(tmp_path):
    # Malformed draft written directly: edition missing.
    (tmp_path / "intake").mkdir(parents=True)
    (tmp_path / "intake" / "drafts.jsonl").write_text(
        '{"claim_id": "RC-0001", "claim": "X", "target": "t", '
        '"source_title": "Book", "edition": "", "locator": "p.1", "notes": "", '
        '"created_utc": "2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ResearchIntakeError, match="edition"):
        verify_claim("RC-0001", "curator")


def test_verify_promotes_and_only_verified_claims_are_servable():
    first = _draft()
    second = _draft(claim="A different unresolved claim", target="chesta_kendra")
    verified = verify_claim(first.claim_id, "A. Curator",
                            note="checked physical copy")
    assert verified.status == "verified"
    assert verified.verifier == "A. Curator"

    servable = servable_claims()
    assert [c.claim_id for c in servable] == [first.claim_id]
    assert servable_claims(target="chesta_kendra") == []
    lines = servable_claim_lines()
    assert len(lines) == 1
    assert "Jataka Parijata" in lines[0] and "verified by A. Curator" in lines[0]
    assert second.claim_id not in lines[0]


def test_verify_can_correct_citation_fields():
    claim = _draft(locator="draft guess")
    verified = verify_claim(claim.claim_id, "curator", locator="Ch. 2 v. 14")
    assert "Ch. 2 v. 14" in verified.citation()
    assert "draft guess" not in verified.citation()


def test_verified_claim_is_terminal():
    claim = _draft()
    verify_claim(claim.claim_id, "curator")
    with pytest.raises(ResearchIntakeError, match="already verified"):
        verify_claim(claim.claim_id, "someone else")
    with pytest.raises(ResearchIntakeError, match="already verified"):
        reject_claim(claim.claim_id, "changed my mind")


# ---------------------------------------------------------------------------
# Reliable-source test
# ---------------------------------------------------------------------------

def test_default_source_class_is_verify_and_cannot_be_promoted():
    claim = add_draft("Claim", "mrityu_bhaga", "Book", "1st", "v.1")
    assert claim.source_class == "verify"
    with pytest.raises(ResearchIntakeError, match="cannot be promoted"):
        verify_claim(claim.claim_id, "curator")


def test_unknown_source_class_is_refused():
    with pytest.raises(ResearchIntakeError, match="Unknown source_class"):
        add_draft("c", "t", "Book", "1st", "v.1", source_class="blog")


def test_web_source_requires_url():
    with pytest.raises(ResearchIntakeError, match="requires a URL"):
        add_draft("c", "t", "Video", "channel", "00:12", source_class="web")


def test_web_source_verifies_but_is_modern_only():
    claim = add_draft(
        "Modern KAT triangle note", "modern_kat", "KAT lesson", "online course",
        "lesson 3", source_class="web", url="https://example.com/kat",
    )
    verified = verify_claim(claim.claim_id, "curator")
    assert verified.status == "verified"
    assert verified.modern_only is True
    assert servable_claims() == []                          # excluded by default
    assert len(servable_claims(include_modern=True)) == 1
    assert servable_claim_lines() == []
    assert "web: https://example.com/kat" in servable_claim_lines(include_modern=True)[0]


def test_verify_can_reclassify_verify_to_canon():
    claim = add_draft("Claim", "mrityu_bhaga", "Book", "1st", "v.1")  # default verify
    verified = verify_claim(claim.claim_id, "curator", source_class="canon")
    assert verified.source_class == "canon"
    assert servable_claims()


# ---------------------------------------------------------------------------
# Rejection requires a reason and stays auditable
# ---------------------------------------------------------------------------

def test_reject_requires_reason():
    claim = _draft()
    with pytest.raises(ResearchIntakeError, match="rejection reason"):
        reject_claim(claim.claim_id, "  ")


def test_reject_keeps_claim_auditable_and_unservable():
    claim = _draft()
    rejected = reject_claim(claim.claim_id, "Edition could not be located", verifier="curator")
    assert rejected.status == "rejected"
    assert rejected.decision_reason == "Edition could not be located"
    assert servable_claims() == []
    assert "[REJECTED]" in claim_report()


def test_load_claims_applies_latest_decision_only():
    claim = _draft()
    reject_claim(claim.claim_id, "wrong edition")
    verify_claim(claim.claim_id, "curator")
    assert get_claim(claim.claim_id).status == "verified"
    assert len(load_claims()) == 1


def test_fingerprint_is_stable():
    a = content_fingerprint("X", "Book", "v.1")
    b = content_fingerprint(" X ", "Book", "v.1")
    assert a == b and len(a) == 16


# ---------------------------------------------------------------------------
# Guard: the intake module is not part of the answer path
# ---------------------------------------------------------------------------

def test_answer_path_does_not_import_intake():
    import SweetAstro.src.chat.payload as payload_mod
    import SweetAstro.src.chat.orchestrator as orch_mod

    for module in (payload_mod, orch_mod):
        source = open(module.__file__, "r", encoding="utf-8").read()
        assert "knowledge.intake" not in source, f"{module.__name__} must not read the quarantine"


def test_cli_smoke_add_and_verify(monkeypatch, capsys):
    import importlib.util
    import sys
    from pathlib import Path

    cli_path = Path(__file__).parent.parent / "research_intake.py"
    spec = importlib.util.spec_from_file_location("research_intake_cli", cli_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(sys, "argv", [
        "research_intake.py", "add", "--claim", "Moon row conflict",
        "--target", "mrityu_bhaga", "--source", "Jataka Parijata",
        "--edition", "Sastri trans.", "--locator", "Ch. 1 v. 58",
    ])
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "RC-0001" in out and "not servable" in out

    monkeypatch.setattr(sys, "argv", [
        "research_intake.py", "verify", "RC-0001", "--verifier", "curator",
        "--source-class", "canon",
    ])
    assert module.main() == 0
    assert "now servable" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", [
        "research_intake.py", "reject", "RC-0001", "--reason", "no",
    ])
    assert module.main() == 2
    assert "already verified" in capsys.readouterr().out
