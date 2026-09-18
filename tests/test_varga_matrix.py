"""Full varga matrix tests: coverage, consistency, consumer + payload wiring."""

from SweetAstro.src.consumer import answer_question
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.core.varga_matrix import (
    ALL_VARGAS, NON_PARASHARI_VARGAS, PARASHARI_VARGAS,
    calculate_full_varga_matrix,
)

BIRTH_ARGS = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _chart():
    return calculate_d1_chart(*BIRTH_ARGS)


def test_varga_sets_are_consistent():
    assert len(ALL_VARGAS) == 23
    assert len(set(ALL_VARGAS)) == 23
    assert set(PARASHARI_VARGAS).isdisjoint(NON_PARASHARI_VARGAS)
    assert set(NON_PARASHARI_VARGAS) == {"D5", "D6", "D8", "D11", "D81", "D108", "D144"}


def test_matrix_covers_every_planet_in_every_chart():
    matrix = calculate_full_varga_matrix(_chart())
    assert list(matrix.charts) == list(ALL_VARGAS)
    for varga, chart in matrix.charts.items():
        assert chart.varga == varga
        assert chart.ascendant
        assert chart.topic
        assert chart.family in ("parashari", "non-parashari")
        assert len(chart.planets) == 9
        for planet, p in chart.planets.items():
            assert p.planet == planet
            assert p.sign
            assert 1 <= p.house <= 12
            assert p.dignity


def test_matrix_d1_and_d9_consistency():
    d1 = _chart()
    matrix = calculate_full_varga_matrix(d1)
    navamsa = calculate_navamsa_chart(d1)

    for planet, p in matrix.charts["D1"].planets.items():
        assert p.sign == d1.planets[planet].sign
        assert p.house == d1.planets[planet].house
        assert p.same_sign_as_d1 is False  # D1 is the reference, not an echo

    for planet, p in matrix.charts["D9"].planets.items():
        assert p.sign == navamsa.planets[planet].d9_sign
        assert p.same_sign_as_d1 == navamsa.planets[planet].is_vargottama


def test_matrix_is_deterministic_and_serializable():
    first = calculate_full_varga_matrix(_chart()).to_dict()
    second = calculate_full_varga_matrix(_chart()).to_dict()
    assert first == second
    assert len(first) == 23
    for chart in first.values():
        assert set(chart["planets"]) == set(_chart().planets)


def test_matrix_lines_include_all_vargas():
    matrix = calculate_full_varga_matrix(_chart())
    lines = matrix.to_lines()
    assert len(lines) == 23
    for varga in ALL_VARGAS:
        assert any(line.startswith(f"- {varga} [") for line in lines)


def test_consumer_full_matrix_flag():
    base = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=26.9124, lon=75.7873,
        question="general", time_reliable=True,
    )
    assert base.full_varga_matrix is None

    full = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=26.9124, lon=75.7873,
        question="general", time_reliable=True, full_matrix=True,
    )
    assert full.full_varga_matrix is not None
    assert set(full.full_varga_matrix.charts) == set(ALL_VARGAS)


def test_consumer_deep_planets_flag():
    from SweetAstro.src.core.constants import PHYSICAL_PLANETS

    base = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=26.9124, lon=75.7873,
        question="wealth and income", time_reliable=True,
    )
    assert len(base.strengths) <= 5
    assert not set(PHYSICAL_PLANETS) <= set(base.strengths)

    deep = answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=26.9124, lon=75.7873,
        question="wealth and income", time_reliable=True, deep_planets=True,
    )
    assert set(PHYSICAL_PLANETS) <= set(deep.strengths)
    # Topic-relevant planets stay first so the remedy primary remains topical.
    assert list(deep.strengths)[0] in base.strengths
