"""Non-Parashari varga tests: D5, D6, D8, D11 boundaries and topic routing."""

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.constants import INDEX_TO_SIGN
from SweetAstro.src.core.vargas import (
    QUESTION_TO_VARGAS, VARGA_TOPICS, calculate_varga_chart,
    varga_sign_index, vargas_for_question,
)

BIRTH_ARGS = (1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)


def _sign(varga, sign, deg):
    return INDEX_TO_SIGN[varga_sign_index(varga, deg, sign, deg)]


def test_d5_panchamsha_boundaries():
    # Odd signs: Aries -> Aquarius -> Sagittarius -> Gemini -> Libra
    assert _sign("D5", 1, 0.0) == "Aries"
    assert _sign("D5", 1, 5.999) == "Aries"
    assert _sign("D5", 1, 6.0) == "Aquarius"
    assert _sign("D5", 1, 12.0) == "Sagittarius"
    assert _sign("D5", 1, 18.0) == "Gemini"
    assert _sign("D5", 1, 24.0) == "Libra"
    # Even signs: Taurus -> Virgo -> Pisces -> Capricorn -> Scorpio
    assert _sign("D5", 2, 0.0) == "Taurus"
    assert _sign("D5", 2, 6.0) == "Virgo"
    assert _sign("D5", 2, 24.0) == "Scorpio"


def test_d6_shashtamsha_boundaries():
    # Odd signs count from Aries; even from Libra (5 deg parts)
    assert _sign("D6", 1, 0.0) == "Aries"
    assert _sign("D6", 1, 29.9) == "Virgo"
    assert _sign("D6", 2, 4.99) == "Libra"
    assert _sign("D6", 2, 5.0) == "Scorpio"
    assert _sign("D6", 5, 5.0) == "Taurus"


def test_d8_ashtamsha_boundaries():
    # Movable from Aries, fixed from Sagittarius, dual from Leo (3.75 deg parts)
    assert _sign("D8", 1, 0.0) == "Aries"        # Aries movable
    assert _sign("D8", 1, 3.75) == "Taurus"
    assert _sign("D8", 2, 0.0) == "Sagittarius"  # Taurus fixed
    assert _sign("D8", 3, 0.0) == "Leo"          # Gemini dual
    assert _sign("D8", 10, 0.0) == "Aries"       # Capricorn movable
    assert _sign("D8", 12, 0.0) == "Leo"         # Pisces dual


def test_d11_ekadashamsha_boundaries():
    # Movable from the sign itself, fixed from the 9th, dual from the 5th
    assert _sign("D11", 1, 0.0) == "Aries"
    assert _sign("D11", 1, 15.0) == "Virgo"       # part 6 from Aries
    assert _sign("D11", 2, 0.0) == "Capricorn"    # 9th from Taurus
    assert _sign("D11", 3, 0.0) == "Libra"        # 5th from Gemini
    assert _sign("D11", 4, 0.0) == "Cancer"       # movable


def test_d81_d108_d144_cyclic_method():
    # Parivritti (continuous from Aries): part index = (sign-1)*n + part, mod 12
    assert _sign("D81", 1, 0.0) == "Aries"
    assert _sign("D81", 1, 30.0 / 81.0) == "Taurus"
    assert _sign("D81", 1, 29.99) == "Sagittarius"   # part 80 -> 80 % 12 = 8
    assert _sign("D81", 2, 0.0) == "Capricorn"       # 81 % 12 = 9

    assert _sign("D108", 1, 0.0) == "Aries"
    assert _sign("D108", 1, 30.0 / 108.0) == "Taurus"
    assert _sign("D108", 2, 0.0) == "Aries"          # 108 % 12 = 0

    assert _sign("D144", 1, 0.0) == "Aries"
    assert _sign("D144", 1, 30.0 / 144.0) == "Taurus"
    assert _sign("D144", 2, 0.0) == "Aries"          # 144 % 12 = 0
    assert _sign("D144", 11, 0.0) == "Aries"         # 10*144 % 12 = 0


UNIFORM_DIVISIONS = {
    "D2": 2, "D3": 3, "D4": 4, "D5": 5, "D6": 6, "D7": 7, "D8": 8,
    "D10": 10, "D11": 11, "D12": 12, "D16": 16, "D20": 20, "D24": 24,
    "D27": 27, "D40": 40, "D45": 45, "D60": 60, "D81": 81, "D108": 108,
    "D144": 144,
}


def test_every_uniform_varga_partitions_all_twelve_signs():
    """Structural verification: n equal parts per sign, a sign change at each
    internal boundary, and a valid sign index everywhere."""
    for varga, n in UNIFORM_DIVISIONS.items():
        span = 30.0 / n
        for sign_index in range(1, 13):
            for part in range(n):
                deg = (part + 0.5) * span
                idx = varga_sign_index(varga, (sign_index - 1) * 30.0 + deg, sign_index, deg)
                assert 1 <= idx <= 12, (varga, sign_index, part)
            for boundary in range(1, n):
                before = varga_sign_index(varga, 0.0, sign_index, boundary * span - 1e-6)
                after = varga_sign_index(varga, 0.0, sign_index, boundary * span + 1e-6)
                assert before != after, (varga, sign_index, boundary)


def test_d30_has_documented_unequal_ranges():
    # Odd: Mars 0-5, Saturn 5-10, Jupiter 10-18, Mercury 18-25, Venus 25-30
    assert [_sign("D30", 1, d) for d in (0.0, 5.0, 10.0, 18.0, 25.0)] == \
        ["Aries", "Aquarius", "Sagittarius", "Gemini", "Libra"]
    # Even: Venus 0-5, Mercury 5-12, Jupiter 12-20, Saturn 20-25, Mars 25-30
    assert [_sign("D30", 2, d) for d in (0.0, 5.0, 12.0, 20.0, 25.0)] == \
        ["Taurus", "Virgo", "Pisces", "Capricorn", "Scorpio"]


def test_new_vargas_are_labeled_and_routable():
    for varga in ("D5", "D6", "D8", "D11"):
        assert varga in VARGA_TOPICS
    assert "D6" in QUESTION_TO_VARGAS["health"]
    assert "D8" in QUESTION_TO_VARGAS["difficulties"]
    assert "D11" in QUESTION_TO_VARGAS["wealth"]
    assert "D11" in QUESTION_TO_VARGAS["business"]
    assert "D5" in QUESTION_TO_VARGAS["spirituality"]


def test_new_vargas_compute_charts_for_all_grahas():
    d1 = calculate_d1_chart(*BIRTH_ARGS)
    for varga in ("D5", "D6", "D8", "D11"):
        chart = calculate_varga_chart(d1, varga)
        assert chart.varga == varga
        assert chart.ascendant_sign
        assert set(chart.planets) == set(d1.planets)
        for state in chart.planets.values():
            assert 1 <= state.varga_house <= 12
            assert state.varga_dignity


def test_vargas_for_question_routes_new_charts():
    assert "D6" in vargas_for_question("I have a health problem")
    assert "D11" in vargas_for_question("wealth and income")
    assert "D5" in vargas_for_question("spiritual progress")


def test_varga_dignities_never_use_d1_moolatrikona():
    from SweetAstro.src.core.chart import _calculate_dignity
    assert _calculate_dignity("Sun", "Leo", 5.0) == "Moolatrikona"
    assert _calculate_dignity("Sun", "Leo", 5.0, allow_moolatrikona=False) == "Own"

    d1 = calculate_d1_chart(*BIRTH_ARGS)
    for varga in ("D2", "D3", "D4", "D5", "D6", "D7", "D8", "D10", "D11",
                  "D12", "D16", "D20", "D24", "D27", "D30", "D40", "D45",
                  "D60", "D81", "D108", "D144"):
        chart = calculate_varga_chart(d1, varga)
        assert all(vs.varga_dignity != "Moolatrikona" for vs in chart.planets.values()), varga
