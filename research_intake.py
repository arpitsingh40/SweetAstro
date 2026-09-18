"""
Research intake CLI — quarantine, verify, or reject sourced claims.

Workflow (docs/system_report.md §7):
    1. add     → candidate claim enters quarantine (citation fields required)
    2. verify  → human confirms source + edition + locator; claim becomes servable
    3. reject  → reason required; claim stays auditable, never usable

Drafts are never read by the chat/answer engine. Verified claims become
available to developers through ``servable_claim_lines()`` for encoding into
structured engine data (with tests) — never by live LLM research.

Usage:
    python research_intake.py add --claim "..." --target mrityu_bhaga \
        --source "Jataka Parijata" --edition "Subrahmanya Sastri trans." --locator "Ch. 1 v. 58"
    python research_intake.py list
    python research_intake.py verify RC-0001 --verifier "curator" --locator "Ch. 1 v. 58"
    python research_intake.py reject RC-0002 --reason "Edition could not be located"
    python research_intake.py report
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from SweetAstro.src.knowledge.intake import (  # noqa: E402
    ResearchIntakeError, add_draft, claim_report, load_claims, reject_claim, verify_claim,
)


def _print_claim(claim) -> None:
    print(f"  {claim.claim_id} [{claim.status.upper()}] {claim.target}: {claim.claim}")
    modern = " (modern-only)" if claim.modern_only else ""
    print(f"    source class: {claim.source_class}{modern}")
    print(f"    citation: {claim.citation()}")
    if claim.status == "verified":
        print(f"    verified by {claim.verifier} on {claim.decided_utc}")
    elif claim.status == "rejected":
        print(f"    rejected: {claim.decision_reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SweetAstro research intake gate")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="quarantine a candidate claim")
    add.add_argument("--claim", required=True)
    add.add_argument("--target", required=True,
                     help="engine area the claim would inform (e.g. mrityu_bhaga)")
    add.add_argument("--source", required=True)
    add.add_argument("--edition", required=True)
    add.add_argument("--locator", required=True, help="chapter/verse or page passage")
    add.add_argument("--source-class", dest="source_class",
                     choices=("canon", "known", "tech", "verify", "web"), default="verify",
                     help="reliable-source class (default: verify = cannot be promoted yet)")
    add.add_argument("--url", default="", help="required when --source-class web")
    add.add_argument("--notes", default="")

    lst = sub.add_parser("list", help="list claims and their status")
    lst.add_argument("--status", choices=("draft", "verified", "rejected", "all"),
                     default="all")

    verify = sub.add_parser("verify", help="promote a claim (full citation + verifier)")
    verify.add_argument("claim_id")
    verify.add_argument("--verifier", required=True)
    verify.add_argument("--source", dest="source_title")
    verify.add_argument("--edition")
    verify.add_argument("--locator")
    verify.add_argument("--source-class", dest="source_class",
                        choices=("canon", "known", "tech", "web"),
                        help="must be reclassified from 'verify'")
    verify.add_argument("--url", help="required for a web source")
    verify.add_argument("--note", default="")

    reject = sub.add_parser("reject", help="reject a claim (reason required)")
    reject.add_argument("claim_id")
    reject.add_argument("--reason", required=True)
    reject.add_argument("--verifier", default="")

    sub.add_parser("report", help="full markdown report")

    args = parser.parse_args()
    try:
        if args.command == "add":
            claim = add_draft(args.claim, args.target, args.source, args.edition,
                              args.locator, notes=args.notes,
                              source_class=args.source_class, url=args.url)
            print(f"Quarantined {claim.claim_id} (status: draft — not servable).")
            _print_claim(claim)
        elif args.command == "list":
            claims = load_claims()
            if args.status != "all":
                claims = [c for c in claims if c.status == args.status]
            if not claims:
                print("No claims.")
            for claim in claims:
                _print_claim(claim)
        elif args.command == "verify":
            claim = verify_claim(
                args.claim_id, args.verifier, source_title=args.source_title,
                edition=args.edition, locator=args.locator,
                source_class=args.source_class, url=args.url, note=args.note,
            )
            print(f"Verified {claim.claim_id} — now servable via servable_claim_lines().")
            _print_claim(claim)
        elif args.command == "reject":
            claim = reject_claim(args.claim_id, args.reason, verifier=args.verifier)
            print(f"Rejected {claim.claim_id}.")
            _print_claim(claim)
        elif args.command == "report":
            print(claim_report())
    except ResearchIntakeError as exc:
        print(f"REFUSED: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
