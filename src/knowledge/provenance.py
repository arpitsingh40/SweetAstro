"""
Method provenance for answer payloads.

Every technique the engine uses has a declared source in the provenance ledger
(docs/system_report.md §2). This module maps the techniques actually used in a
reading to their citation lines, so the LLM can say *why* a conclusion is drawn
and *on what authority* — instead of repeating generic no-guarantee lines.

Only declared sources are emitted; nothing is invented, and no verse is quoted
beyond what the ledger states.
"""

from typing import Dict, List, Optional, Sequence, Tuple

# technique key -> (label, declared source)
METHOD_SOURCES: Dict[str, Tuple[str, str]] = {
    "vimshottari": ("Vimshottari dasha (MD/AD/PD)", "BPHS; balance arithmetic hand-verified"),
    "navamsa": ("Navamsa (D9) analysis", "BPHS Ch. 6-7 (parity-tested)"),
    "planet_factors": ("Panchadha maitri / avasthas / sandhi / gandanta / graha yuddha / parivartana",
                       "BPHS (conventions declared per factor)"),
    "shadbala": ("Shadbala six components, Ishta/Kashta, Rashmi minimums",
                 "BPHS as standardised by B.V. Raman, Graha and Bhava Balas"),
    "jaimini": ("Jaimini chara karakas / arudha / Upapada / argala",
                "Jaimini Sutras (exception rules spec-frozen)"),
    "ashtakavarga": ("Ashtakavarga bindu counts (BAV/SAV)", "BPHS Ch. 66"),
    "gochara": ("Gochara, vedha pairs, Sade Sati", "B.V. Raman standard"),
    "varshaphala": ("Varshaphala (solar return, Muntha, Varsha lagna)",
                    "Tajika (declared partial - year-lord strength omitted)"),
    "panchanga": ("Natal panchanga (drik ganita limbs and windows)",
                  "verified against frozen DrikPanchang dataset (10 cases)"),
    "yogas": ("Yoga detection (named combinations)",
              "classical yoga texts; names carried by the engine detections"),
    "remedies": ("Remedy catalog, safety gate, KAT, gemstone gate",
                 "T7 sources; KAT research note; gemstone gate by design conservative"),
    "varga_matrix": ("Shodashavarga and declared non-Parashari vargas",
                     "BPHS Ch. 6-7; non-Parashari conventions declared per chart"),
}

# Methods that are explicitly modern/testable-claim adjacent and therefore
# labelled rather than presented as classical authority.
MODERN_LABELS = {
    "remedies": "remedy safety is modern governance, not a classical guarantee",
}


def lines_for(techniques: Sequence[str]) -> List[str]:
    """Citation lines for the techniques used, in declared-ledger wording."""
    lines: List[str] = []
    seen = set()
    for key in techniques:
        if key in seen or key not in METHOD_SOURCES:
            continue
        seen.add(key)
        label, source = METHOD_SOURCES[key]
        lines.append(f"- {label}: {source}")
    return lines


def techniques_from_result(result) -> List[str]:
    """Which declared methods this ConsumerResult actually used."""
    techniques: List[str] = ["vimshottari"]
    vargas = getattr(result, "vargas", None) or {}
    if "D9" in vargas:
        techniques.append("navamsa")
    if getattr(result, "strengths", None):
        techniques.append("planet_factors")
        for strength in result.strengths.values():
            if getattr(strength, "shadbala", None):
                techniques.append("shadbala")
                break
    if getattr(result, "karakas", None) is not None and getattr(result, "jaimini", None) is not None:
        techniques.append("jaimini")
    if getattr(result, "ashtakavarga", None) is not None:
        techniques.append("ashtakavarga")
    if getattr(result, "gochara", None) is not None:
        techniques.append("gochara")
    if getattr(result, "varshaphala", None) is not None:
        techniques.append("varshaphala")
    if getattr(result, "panchanga", None) is not None:
        techniques.append("panchanga")
    yogas = getattr(result, "yogas", None)
    if yogas is not None and getattr(yogas, "yogas", None):
        techniques.append("yogas")
    answer = getattr(result, "answer", None)
    if answer is not None and (getattr(answer, "primary_remedy", None)
                               or getattr(answer, "supporting_remedies", None)):
        techniques.append("remedies")
    return techniques


def provenance_block(result, include_full_matrix: bool = False) -> List[str]:
    """Payload block: the declared bases for the techniques actually used."""
    techniques = techniques_from_result(result)
    if include_full_matrix:
        techniques.append("varga_matrix")
    lines = lines_for(techniques)
    if not lines:
        return []
    header = ("Method provenance for this answer (declared bases - cite these when "
              "explaining a conclusion; never invent other verses or sources):")
    body = [header]
    body.extend(lines)
    for key in techniques:
        if key in MODERN_LABELS:
            body.append(f"- Note ({key}): {MODERN_LABELS[key]}")
            break
    return body
