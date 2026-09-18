"""Vimshopak Bala tests: scheme weights, scores, Vaiseshikamsa, formatting."""

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import PHYSICAL_PLANETS
from SweetAstro.src.core.vimshopaka import (
    VARGAVISVA, VAISESHIKAMSA, VIMSHOPAKA_WEIGHTS, calculate_vimsopaka,
    format_vimsopaka,
)

BIRTH_ARGS = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart():
    return calculate_d1_chart(*BIRTH_ARGS)


def test_weight_schemes_sum_to_twenty():
    for scheme, weights in VIMSHOPAKA_WEIGHTS.items():
        assert abs(sum(weights.values()) - 20.0) < 1e-9, scheme


def test_scores_are_bounded_and_complete():
    result = calculate_vimsopaka(_chart(), scheme="shodashavarga")
    assert result.scheme == "shodashavarga"
    assert set(result.scores) == set(PHYSICAL_PLANETS)
    for planet, score in result.scores.items():
        assert 0.0 <= score.total <= 20.0, planet
        assert score.grade
        assert score.good_varga_count >= 0
        if score.good_varga_count >= 2:
            assert score.vaiseshikamsa is not None


def test_per_varga_contributions_match_total():
    result = calculate_vimsopaka(_chart(), scheme="shadvarga")
    weights = VIMSHOPAKA_WEIGHTS["shadvarga"]
    for score in result.scores.values():
        assert abs(sum(score.per_varga.values()) - score.total) < 0.01
        for varga, contribution in score.per_varga.items():
            assert contribution <= weights[varga] + 1e-9


def test_all_schemes_compute():
    for scheme in VIMSHOPAKA_WEIGHTS:
        result = calculate_vimsopaka(_chart(), scheme=scheme)
        assert result.scores
        assert f"({scheme})" in result.note


def test_vargavisva_table_is_ordered():
    assert VARGAVISVA["Own"] == 20.0
    assert VARGAVISVA["Exalted"] == 20.0
    assert VARGAVISVA["Debilitated"] == 0.0
    assert VARGAVISVA["Friend"] > VARGAVISVA["Neutral"] > VARGAVISVA["Enemy"]


def test_vaiseshikamsa_tables_have_expected_ranges():
    assert max(VAISESHIKAMSA["shadvarga"]) == 6
    assert max(VAISESHIKAMSA["saptavarga"]) == 7
    assert max(VAISESHIKAMSA["dashavarga"]) == 10
    assert max(VAISESHIKAMSA["shodashavarga"]) == 16


def test_format_contains_every_planet():
    result = calculate_vimsopaka(_chart(), scheme="shodashavarga")
    text = format_vimsopaka(result)
    for planet in PHYSICAL_PLANETS:
        assert planet in text
    assert "/20" in text
