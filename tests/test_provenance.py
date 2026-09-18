"""
Sourced-reasoning contract tests (user directive, 2026-09-13).

Answers should explain *why* a conclusion is drawn and *on what declared
authority* — instead of repeating generic no-guarantee lines. The payload
carries a method-provenance block built only from the project's declared
ledger; the prompts require citing it and forbid inventing sources.
"""

from SweetAstro.src.chat.payload import build_chart_payload
from SweetAstro.src.consumer import answer_question

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30, second=0,
             tz_offset=5.5, lat=28.6139, lon=77.2090)


def _payload(**kwargs):
    result = answer_question(**BIRTH, question="career growth", time_reliable=True)
    return build_chart_payload(
        result, name="Ananya", dob="1995-05-15", tob="14:30", tz_offset=5.5,
        place="Delhi", geo_note="Manual.", time_reliable=True,
        question="career growth", topic="career", **kwargs,
    )


def test_payload_includes_method_provenance_for_used_techniques():
    payload = _payload()
    assert "Method provenance for this answer" in payload
    assert "Vimshottari dasha" in payload and "BPHS" in payload
    # Declared bases only; explicit invention guard in the same block
    assert "never invent other verses" in payload


def test_provenance_block_lists_only_declared_methods():
    from SweetAstro.src.knowledge.provenance import METHOD_SOURCES, lines_for

    lines = lines_for(["vimshottari", "ashtakavarga", "not_a_method"])
    assert len(lines) == 2
    assert all(line.startswith("- ") for line in lines)
    assert lines_for([]) == []
    for label, source in METHOD_SOURCES.values():
        assert label and source


def test_varga_matrix_citation_only_when_full_matrix_requested():
    plain = _payload()
    full = _payload(include_full_matrix=True)
    assert "Shodashavarga" not in plain
    assert "Shodashavarga" in full


def test_prompts_require_sourced_reasoning():
    from SweetAstro.src.chat import prompt as P

    assert "method provenance" in P._COMMON_SHAPE_RULES.lower()
    assert "sourced reasoning" in P._COMMON_SHAPE_RULES.lower()
    assert "sourced reasoning" in P.ANSWER_SYSTEM_PROMPT.lower()
    assert "youtube/website authority" in P.ANSWER_SYSTEM_PROMPT.lower()
    # Disclaimers are stated once, not scattered
    assert "do not repeat no-guarantee disclaimers" in P.ANSWER_SYSTEM_PROMPT.lower()


def test_provenance_has_no_modern_authority_for_classical_methods():
    """Every classical technique maps to a classical/modern-published source."""
    from SweetAstro.src.knowledge.provenance import METHOD_SOURCES

    forbidden = ("youtube", "video", "blog", "wikipedia")
    for label, source in METHOD_SOURCES.values():
        low = source.lower()
        assert not any(bad in low for bad in forbidden), f"{label}: {source}"
