"""Promise gate tests: factor counting, levels, real-chart integration."""

from types import SimpleNamespace

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.interpretation.promise import assess_promise


def _planet(dignity, house=1):
    return SimpleNamespace(dignity=dignity, house=house)


def _house(lord, occupants=None, aspecting=None):
    return SimpleNamespace(lord=lord, occupants=list(occupants or []),
                           aspecting_planets=list(aspecting or []))


def _chart(houses):
    planets = {
        "Sun": _planet(houses[1].lord == "Sun" and "Exalted" or "Neutral"),
        "Mars": _planet("Own"),
        "Jupiter": _planet("Neutral"),
        "Venus": _planet("Neutral"),
        "Mercury": _planet("Neutral"),
        "Moon": _planet("Neutral"),
        "Saturn": _planet("Neutral"),
        "Rahu": _planet("Neutral"),
        "Ketu": _planet("Neutral"),
    }
    all_houses = {h: _house("Sun") for h in range(1, 13)}
    all_houses.update(houses)
    return SimpleNamespace(houses=all_houses, planets=planets, ascendant_sign_index=1)


def test_supported_chart_scores_high_and_allows_timing():
    houses = {
        1: _house("Sun", occupants=["Jupiter"], aspecting=["Venus"]),
        9: _house("Mars", occupants=["Mercury"]),
        10: _house("Sun"),
    }
    result = assess_promise(_chart(houses), "general")
    assert result.level == "Supported"
    assert result.timing_reliable is True
    assert len(result.supportive_factors) >= 3
    assert "supported" in result.statement.lower()


def test_weak_chart_blocks_timing():
    houses = {
        1: _house("Saturn", occupants=["Saturn", "Rahu"]),
        9: _house("Mars", occupants=["Mars"]),
        10: _house("Saturn"),
    }
    chart = _chart(houses)
    chart.planets["Saturn"] = _planet("Debilitated")
    result = assess_promise(chart, "general")
    assert result.level == "Weak"
    assert result.timing_reliable is False
    assert result.limiting_factors
    assert "weak promise" in result.statement.lower()


def test_partial_chart_is_indicative_only():
    houses = {
        1: _house("Jupiter", occupants=["Saturn"]),
        9: _house("Mars"),
        10: _house("Sun"),
    }
    chart = _chart(houses)
    chart.planets["Jupiter"] = _planet("Friend")
    chart.planets["Mars"] = _planet("Own")
    result = assess_promise(chart, "general")
    assert result.level == "Partial"
    assert result.timing_reliable is True
    assert "partial promise" in result.statement.lower()


def test_real_chart_promise_is_structured():
    d1 = calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 26.9124, 75.7873)
    result = assess_promise(d1, "marriage")
    assert result.level in ("Supported", "Partial", "Weak")
    assert result.statement
    assert isinstance(result.score, float)
