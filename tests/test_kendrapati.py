"""Kendrapati dosha tests: rule verdicts, structure, summary."""

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import NATURAL_BENEFICS
from SweetAstro.src.core.dosha import (
    KENDRAS, TRINES, assess_kendrapati, kendrapati_summary,
)

BIRTH_ARGS = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart():
    return calculate_d1_chart(*BIRTH_ARGS)


def test_rule_constants():
    assert KENDRAS == (1, 4, 7, 10)
    assert TRINES == (1, 5, 9)


def test_findings_cover_natural_benefics():
    result = assess_kendrapati(_chart())
    assert set(result.findings) == set(NATURAL_BENEFICS)
    for planet, finding in result.findings.items():
        assert finding.planet == planet
        assert finding.verdict in ("dosha", "mixed", "clear")
        assert set(finding.kendra_houses) <= set(finding.owned_houses)
        assert set(finding.trine_houses) <= set(finding.owned_houses)


def test_verdict_logic_is_consistent():
    result = assess_kendrapati(_chart())
    for finding in result.findings.values():
        if not finding.kendra_houses:
            assert finding.verdict == "clear"
        elif finding.trine_houses:
            assert finding.verdict == "mixed"
        else:
            assert finding.verdict == "dosha"
            assert finding.planet in result.dosha_planets


def test_dict_round_trip():
    result = assess_kendrapati(_chart())
    data = result.to_dict()
    assert data["dosha_planets"] == result.dosha_planets
    assert set(data["findings"]) == set(result.findings)


def test_summary_mentions_either_dosha_or_none():
    text = kendrapati_summary(_chart())
    assert "Kendrapati dosha:" in text
