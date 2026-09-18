"""Argala and progeny sphuta tests: structure, arithmetic, formatting."""

from SweetAstro.src.core.argala import (
    ARGALA_PAIRS, argala_summary, compute_argala,
)
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.sphuta import calculate_progeny_sphutas, format_sphutas

BIRTH_ARGS = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart():
    return calculate_d1_chart(*BIRTH_ARGS)


def test_argala_pairs_are_classical():
    assert (2, 12) in ARGALA_PAIRS
    assert (4, 10) in ARGALA_PAIRS
    assert (11, 3) in ARGALA_PAIRS


def test_argala_structure_and_net_score():
    result = compute_argala(_chart(), reference_house=7)
    assert result.reference_house == 7
    assert len(result.pairs) == len(ARGALA_PAIRS)
    expected_net = 0
    for pair in result.pairs:
        assert pair.outcome in ("argala", "virodha", "contested", "none")
        if pair.outcome == "argala":
            expected_net += 1
        elif pair.outcome == "virodha":
            expected_net -= 1
        elif pair.outcome == "contested":
            assert len(pair.argala_planets) == len(pair.virodha_planets) > 0
        else:
            assert not pair.argala_planets and not pair.virodha_planets
    assert result.net_score == expected_net
    assert result.verdict


def test_argala_houses_are_counted_from_reference():
    d1 = _chart()
    result = compute_argala(d1, reference_house=1)
    for pair in result.pairs:
        expected_argala = ((1 - 1 + pair.argala_house - 1) % 12) + 1
        assert expected_argala == pair.argala_house
        assert pair.argala_planets == d1.houses[pair.argala_house].occupants


def test_argala_to_dict_round_trips():
    result = compute_argala(_chart(), reference_house=1)
    data = result.to_dict()
    assert data["reference_house"] == 1
    assert len(data["pairs"]) == len(result.pairs)
    assert data["verdict"] == result.verdict


def test_argala_summary_is_a_line():
    text = argala_summary(_chart(), reference_house=1)
    assert "Argala on H1" in text


def test_progeny_sphuta_arithmetic():
    d1 = _chart()
    result = calculate_progeny_sphutas(d1)
    expected_beeja = (
        d1.planets["Sun"].longitude
        + d1.planets["Venus"].longitude
        + d1.planets["Jupiter"].longitude
    ) % 360.0
    expected_kshetra = (
        d1.planets["Moon"].longitude
        + d1.planets["Mars"].longitude
        + d1.planets["Jupiter"].longitude
    ) % 360.0
    assert abs(result.beeja.longitude - expected_beeja) < 1e-9
    assert abs(result.kshetra.longitude - expected_kshetra) < 1e-9
    assert 0 <= result.beeja.pada <= 4
    assert "no fertility judgement" in result.note.lower()


def test_sphuta_format_lists_both():
    text = format_sphutas(calculate_progeny_sphutas(_chart()))
    assert "Beeja Sphuta" in text
    assert "Kshetra Sphuta" in text
