"""Gochara tests: nine-planet transits, vedha cancellation, Sade Sati phases."""

from datetime import datetime
from types import SimpleNamespace

import SweetAstro.src.core.transits as tr
from SweetAstro.src.core.transits import (
    TransitPosition, evaluate_gochara, get_transit_positions,
)


def _chart():
    return SimpleNamespace(
        planets={"Moon": SimpleNamespace(sign_index=1)},
        ascendant_sign_index=1,
    )


def _pos(planet, sign_index):
    return TransitPosition(planet=planet, sign="X", sign_index=sign_index,
                           degree_in_sign=0.0, is_retrograde=False,
                           aspected_sign_indices=[sign_index])


def test_transit_positions_cover_nine_grahas():
    positions = get_transit_positions(datetime(2028, 3, 15, 12, 0, 0))
    assert set(positions) == {"Sun", "Moon", "Mars", "Mercury", "Jupiter",
                              "Venus", "Saturn", "Rahu", "Ketu"}


def test_vedha_cancels_favourable_transit_and_sade_sati_detected(monkeypatch):
    positions = {p: _pos(p, 1) for p in ("Sun", "Moon", "Mars", "Mercury",
                                         "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")}
    positions["Saturn"] = _pos("Saturn", 12)   # 12th from Aries Moon -> Sade Sati rising
    positions["Jupiter"] = _pos("Jupiter", 2)  # 2nd from Moon: favourable, vedha at 12
    monkeypatch.setattr(tr, "get_transit_positions", lambda d, **kwargs: positions)

    reading = evaluate_gochara(_chart(), datetime(2028, 3, 15))

    assert reading.sade_sati.active is True
    assert "Rising" in reading.sade_sati.phase
    assert reading.sade_sati.saturn_house_from_moon == 12

    jupiter = reading.entries["Jupiter"]
    assert jupiter.house_from_moon == 2
    assert jupiter.favourable is False
    assert "Saturn" in jupiter.vedha_by
    assert "vedha" in jupiter.note.lower()


def test_clean_favourable_transit_without_vedha(monkeypatch):
    positions = {p: _pos(p, 3) for p in ("Sun", "Moon", "Mars", "Mercury",
                                         "Jupiter", "Venus", "Saturn", "Rahu", "Ketu")}
    positions["Saturn"] = _pos("Saturn", 3)   # 3rd from Moon -> favourable
    positions["Jupiter"] = _pos("Jupiter", 5)  # 5th from Moon -> favourable, vedha 4 (free)
    monkeypatch.setattr(tr, "get_transit_positions", lambda d, **kwargs: positions)

    reading = evaluate_gochara(_chart(), datetime(2028, 3, 15))
    assert reading.entries["Jupiter"].favourable is True
    assert reading.entries["Saturn"].favourable is True
    assert reading.sade_sati.active is False
    assert "Supportive gochara" in reading.summary
