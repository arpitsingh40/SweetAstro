"""
Regression tests for audit round 2 (2026-09-12):

10. Shadbala ksepa factor was discontinuous (half the zodiac scored 0)
11. dig-bala was dignity-based instead of the classical directional strength
12. The strength index denominator said /420 while six factors cap at 360
13. Pancha Mahapurusha yogas were mislabelled (Sun "Vajra", Saturn "Kesari")
    and used an OR instead of the classical own/exaltation AND kendra
14. Venus-Mars conjunction was mislabelled "Malavya" (colliding with the
    Mahapurusha yoga of the same name)
15. Gajakesari used a non-classical condition (Jupiter in 1/5/9 with Moon in 7)
16. Sensitivity engine edge cases were untested
"""

from datetime import datetime

import pytest

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.yogas import detect_yogas
from SweetAstro.src.core.shadbala import MAX_SHADBALA, _ksepa_bala, calculate_shadbala, digbala
from SweetAstro.src.prediction.sensitivity import evaluate_birth_time_sensitivity


@pytest.fixture(scope="module")
def d1():
    return calculate_d1_chart(1995, 5, 15, 14, 30, 0, 5.5, 28.6139, 77.2090)


# ---------------------------------------------------------------------------
# Bug 10 — ksepa continuity
# ---------------------------------------------------------------------------

def test_ksepa_bala_is_continuous():
    before = _ksepa_bala(1, 1, 19.4, False, 1.0)
    after = _ksepa_bala(1, 1, 19.6, False, 1.0)
    assert before > 50.0 and after > 50.0
    assert abs(before - after) < 3.0, "ksepa must not jump across 19.5 degrees"
    assert _ksepa_bala(1, 1, 19.5, False, 1.0) == 60.0
    assert _ksepa_bala(1, 1, 4.5, False, 1.0) == 0.0     # 15 degrees away
    assert _ksepa_bala(1, 1, 5.0, False, 1.0) > 0.0      # no dead half of the sign


def test_ksepa_retrograde_and_speed_scale():
    fast = _ksepa_bala(1, 1, 19.5, False, 1.0)
    slow = _ksepa_bala(1, 1, 19.5, False, 0.0)
    retro = _ksepa_bala(1, 1, 19.5, True, 1.0)
    assert fast == 60.0
    assert slow == pytest.approx(30.0)
    assert retro == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Bug 11 — directional dig-bala
# ---------------------------------------------------------------------------

def test_digbala_is_directional():
    assert digbala("Jupiter", 1) == 60.0     # East (lagna)
    assert digbala("Mercury", 1) == 60.0
    assert digbala("Sun", 10) == 60.0        # South
    assert digbala("Mars", 10) == 60.0
    assert digbala("Saturn", 7) == 60.0      # West
    assert digbala("Moon", 4) == 60.0        # North
    assert digbala("Venus", 4) == 60.0
    assert digbala("Jupiter", 7) == 0.0      # opposite point
    assert digbala("Moon", 10) == 0.0
    assert digbala("Rahu", 1) == 0.0         # nodes excluded


def test_digbala_linear_falloff():
    assert digbala("Sun", 9) == pytest.approx(50.0)   # one sign from the 10th
    assert digbala("Sun", 8) == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Bug 12 — denominator and category scale
# ---------------------------------------------------------------------------

def test_strength_index_capped_at_360(d1):
    totals = [calculate_shadbala(d1.planets[p], d1).total_bala
              for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]]
    assert MAX_SHADBALA == 360.0
    assert max(totals) <= MAX_SHADBALA
    for score in [calculate_shadbala(d1.planets[p], d1) for p in d1.planets]:
        expected = ("Strong" if score.total_bala >= 0.70 * MAX_SHADBALA
                    else "Moderate" if score.total_bala >= 0.50 * MAX_SHADBALA
                    else "Weak" if score.total_bala >= 0.30 * MAX_SHADBALA
                    else "Very Weak")
        assert score.strength_category == expected


def test_payload_and_reason_use_360(d1):
    from SweetAstro.src.core.strength import assess_planet_strength
    assessment = assess_planet_strength(d1, "Saturn", None, ["Saturn"])
    assert "/360" in assessment.recommendation_reason
    assert "/420" not in assessment.recommendation_reason


# ---------------------------------------------------------------------------
# Bug 13/14/15 — yoga detection
# ---------------------------------------------------------------------------

def test_no_mislabelled_mahapurusha_yogas(d1):
    profile = detect_yogas(d1, None, None)
    names = {y.yoga_name for y in profile.yogas}
    for wrong in ("Vajra Yoga", "Kesari Yoga", "Pasa Yoga", "Malavya Yoga (Venus-Mars)"):
        assert wrong not in names, f"'{wrong}' is not a classical Mahapurusha yoga name"

    valid = {"Ruchaka Yoga", "Bhadra Yoga", "Hamsa Yoga", "Malavya Yoga", "Sasa Yoga"}
    valid_planets = {"Mars", "Mercury", "Jupiter", "Venus", "Saturn"}
    for yoga in profile.yogas:
        if yoga.yoga_type == "mahabala":
            assert yoga.yoga_name in valid
            assert yoga.planet in valid_planets


def test_mahapurusha_requires_kendra(d1):
    # Demo chart: Saturn is in its own sign (Capricorn) but in house 5
    # (trikona, not kendra) — it must NOT produce a Mahapurusha yoga.
    saturn = d1.planets["Saturn"]
    if saturn.sign == "Capricorn" and saturn.house not in (1, 4, 7, 10):
        profile = detect_yogas(d1, None, None)
        assert not any(y.yoga_type == "mahabala" and y.planet == "Saturn"
                       for y in profile.yogas)


def test_gajakesari_uses_kendra_from_moon(d1):
    profile = detect_yogas(d1, None, None)
    moon = d1.planets["Moon"]
    jup = d1.planets["Jupiter"]
    relative = ((jup.house - moon.house) % 12) + 1
    expected = (jup.sign == moon.sign) or relative in (1, 4, 7, 10)
    detected = any(y.yoga_name == "Gajakesari Yoga" for y in profile.yogas)
    assert detected is expected


def test_venus_mars_conjunction_naming(d1):
    profile = detect_yogas(d1, None, None)
    names = {y.yoga_name for y in profile.yogas}
    venus = d1.planets["Venus"]
    mars = d1.planets["Mars"]
    if venus.sign == mars.sign:
        assert "Venus-Mars Conjunction" in names
    assert "Malavya Yoga (Venus-Mars)" not in names


# ---------------------------------------------------------------------------
# Bug 16 — sensitivity edge cases (audited, no defect found)
# ---------------------------------------------------------------------------

def test_sensitivity_sample_count_and_bounds():
    report = evaluate_birth_time_sensitivity(
        1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090,
        window_minutes=10, step_minutes=2,
    )
    assert report.samples_tested == 11
    for ratio in (report.lagna_stable_ratio, report.navamsa_stable_ratio, report.dasha_stable_ratio):
        assert 0.0 <= ratio <= 1.0
    assert 0.0 <= report.overall_stability_score <= 100.0
    assert report.stability_classification in ("High", "Moderate", "Birth-Time Sensitive")


def test_sensitivity_zero_window_is_stable():
    report = evaluate_birth_time_sensitivity(
        1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090,
        window_minutes=0, step_minutes=2,
    )
    assert report.samples_tested == 1
    assert report.overall_stability_score == 100.0


def test_sensitivity_step_larger_than_window():
    report = evaluate_birth_time_sensitivity(
        1995, 5, 15, 14, 30, 0.0, 5.5, 28.6139, 77.2090,
        window_minutes=10, step_minutes=25,
    )
    assert report.samples_tested >= 1
    assert 0.0 <= report.overall_stability_score <= 100.0
