"""
Step 1 (SweetAstro Core v2): multi-ayanamsha provider.

Frozen J2000.0 references were captured from Swiss Ephemeris 2.10. The
built-in fallback embeds the same bases, so both backends are exercised here.
"""

import pytest

from SweetAstro.src.core import ephemeris
from SweetAstro.src.core.ayanamsha import (
    AYANAMSHAS, available_ayanamshas, normalize_ayanamsha, ayanamsha_label,
    calculate_ayanamsha, swe_sid_mode,
)
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.ephemeris import calculate_lahiri_ayanamsha

J2000 = 2451545.0

FROZEN_J2000 = {
    "lahiri": 23.857092,
    "krishnamurti": 23.760240040326494,
    "raman": 22.410791040326500,
    "fagan_bradley": 24.740299994434963,
    "true_citra": 23.840018014902910,
    "yukteshwar": 22.478803027808170,
    "ushashashi": 20.057541027808156,
}

BIRTH = dict(year=1995, month=5, day=15, hour=14, minute=30,
             tz_offset_hours=5.5, lat=28.6139, lon=77.2090)


def test_registry_has_plan_systems():
    assert {"lahiri", "krishnamurti", "raman", "fagan_bradley"} <= set(available_ayanamshas())


def test_registry_specs_are_complete():
    for key, spec in AYANAMSHAS.items():
        assert spec.key == key
        assert spec.label
        assert isinstance(spec.swe_mode, int)


def test_normalize_handles_names_and_aliases():
    assert normalize_ayanamsha("Lahiri (Chitra Paksha)") == "lahiri"
    assert normalize_ayanamsha("KP") == "krishnamurti"
    assert normalize_ayanamsha("fagan-bradley") == "fagan_bradley"
    assert normalize_ayanamsha(None) == "lahiri"


def test_normalize_rejects_unknown_system():
    with pytest.raises(ValueError):
        normalize_ayanamsha("mayan")


def test_labels_and_sid_modes():
    assert ayanamsha_label("kp") == "Krishnamurti (KP)"
    assert swe_sid_mode("lahiri") == 1
    assert swe_sid_mode("fagan_bradley") == 0


@pytest.mark.parametrize("system,expected", sorted(FROZEN_J2000.items()))
def test_j2000_reference_values(system, expected):
    # True Citra evaluates Spica's actual position and moves ~3e-6 deg with the
    # Swiss Ephemeris data model; every other origin is stable to <1e-6.
    tol = 1e-5 if system == "true_citra" else 1e-6
    assert calculate_ayanamsha(J2000, system) == pytest.approx(expected, abs=tol)


@pytest.mark.parametrize("jd", [2439844.5, J2000, 2460000.5])
def test_lahiri_matches_legacy_function(jd):
    assert calculate_ayanamsha(jd, "lahiri") == pytest.approx(
        calculate_lahiri_ayanamsha(jd), abs=1e-9)


def test_fallback_backend_without_swisseph(monkeypatch):
    monkeypatch.setattr(ephemeris, "HAS_SWISSEPH", False)
    for system, expected in FROZEN_J2000.items():
        assert calculate_ayanamsha(J2000, system) == pytest.approx(expected, abs=1e-6)
    # The fallback must still advance with time (general precession).
    later = calculate_ayanamsha(J2000 + 36525.0, "krishnamurti")
    assert later > FROZEN_J2000["krishnamurti"]


def test_chart_default_is_lahiri_and_records_system():
    chart = calculate_d1_chart(**BIRTH)
    assert chart.ayanamsha_system == "lahiri"
    assert chart.ayanamsha == pytest.approx(calculate_lahiri_ayanamsha(chart.jd), abs=1e-9)


def test_chart_honors_krishnamurti_ayanamsha():
    lahiri = calculate_d1_chart(**BIRTH)
    kp = calculate_d1_chart(**BIRTH, ayanamsha="krishnamurti")
    assert kp.ayanamsha_system == "krishnamurti"
    shift = lahiri.ayanamsha - kp.ayanamsha
    assert 0.05 < shift < 0.15
    # Sidereal longitude = tropical - ayanamsha, so the smaller KP offset puts
    # KP longitudes ahead of Lahiri by exactly `shift` (modulo 360).
    delta = (kp.planets["Sun"].longitude - lahiri.planets["Sun"].longitude) % 360.0
    err = min((delta - shift) % 360.0, (shift - delta) % 360.0)
    assert err == pytest.approx(0.0, abs=1e-6)


def test_chart_rejects_unknown_ayanamsha():
    with pytest.raises(ValueError):
        calculate_d1_chart(**BIRTH, ayanamsha="mayan")
