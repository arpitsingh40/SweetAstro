"""
SweetAstro Calculation Verification Report.

Backtests every astronomical/astrological calculation against authenticated
and trusted sources:
  [SE]    Swiss Ephemeris 2.10.03 (pyswisseph), Lahiri sidereal mode —
          the reference implementation used by professional Vedic software.
  [BPHS]  Brihat Parashara Hora Shastra rules with hand-computed expectations
          (nakshatra/pada, navamsa, divisional charts, Vimshottari balance).

Usage:
    python tests/verify_calculations.py
Exit code 0 = all checks passed.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from SweetAstro.src.core import ephemeris
from SweetAstro.src.core.chart import calculate_d1_chart, _get_nakshatra_and_pada
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
from SweetAstro.src.core.navamsa import calculate_navamsa_sign_index
from SweetAstro.src.core.vargas import varga_sign_index
from SweetAstro.src.core.constants import INDEX_TO_SIGN

from test_calculation_backtest import (
    REFERENCE_CHARTS, AYANAMSHA_FROZEN, DEMO_FROZEN,
    NAKSHATRA_CASES, NAVAMSA_CASES, VARGA_CASES,
)

CHECKS = []


def check(name: str, ok: bool, detail: str):
    CHECKS.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {detail}")


def signed_diff(a: float, b: float) -> float:
    return (a - b + 540.0) % 360.0 - 180.0


def main() -> int:
    print("=" * 78)
    print("SWEETASTRO CALCULATION VERIFICATION REPORT")
    print("=" * 78)
    print(f"  Engine:    {ephemeris.ephemeris_engine_name()} | {ephemeris.ephemeris_data_source()}")
    try:
        import swisseph as swe
        print(f"  Reference: pyswisseph {swe.version} (SIDM_LAHIRI)")
    except ImportError:
        print("  Reference: UNAVAILABLE (pyswisseph not installed)")
    print()

    # 1. Ayanamsha ----------------------------------------------------------
    print("1. Lahiri ayanamsha vs Swiss Ephemeris")
    max_diff = 0.0
    for jd, expected in AYANAMSHA_FROZEN:
        diff = abs(ephemeris.calculate_lahiri_ayanamsha(jd) - expected)
        max_diff = max(max_diff, diff)
    check("ayanamsha (5 reference JDs)", max_diff < 1e-4, f"max diff {max_diff:.6f} deg")

    # 2. Planets + ascendant vs direct SE ------------------------------------
    has_swe = ephemeris.HAS_SWISSEPH
    if has_swe:
        import swisseph as swe
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        mapping = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
                   "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
                   "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
        max_planet = 0.0
        max_asc = 0.0
        for (label, y, mo, d, h, mi, tz, lat, lon) in REFERENCE_CHARTS:
            jd = ephemeris.datetime_to_julian_day(y, mo, d, h, mi, 0.0, tz)
            chart = calculate_d1_chart(y, mo, d, h, mi, 0.0, tz, lat, lon)
            for planet, pid in mapping.items():
                direct, _ = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SPEED)
                max_planet = max(max_planet, abs(signed_diff(chart.planets[planet].longitude, direct[0])))
            _, ascmc = swe.houses_ex(jd, lat, lon, b'W', swe.FLG_SIDEREAL)
            max_asc = max(max_asc, abs(signed_diff(chart.ascendant_deg, ascmc[0])))

        print("2. Planetary longitudes vs Swiss Ephemeris (6 charts x 8 grahas)")
        check("planet longitudes", max_planet < 1e-6, f"max diff {max_planet:.8f} deg")
        print("3. Ascendant vs Swiss Ephemeris (6 charts, both hemispheres)")
        check("ascendant", max_asc < 1e-6, f"max diff {max_asc:.8f} deg")

        # Fallback envelope
        trusted = ephemeris.calculate_planet_positions(
            ephemeris.datetime_to_julian_day(1995, 5, 15, 14, 30, 0.0, 5.5),
            ephemeris.calculate_lahiri_ayanamsha(2449852.875))
        saved = ephemeris.HAS_SWISSEPH
        ephemeris.HAS_SWISSEPH = False
        fb_asc = ephemeris.calculate_ascendant(2449852.875, 28.6139, 77.2090, 23.792378)
        fb_planets = ephemeris.calculate_planet_positions(2449852.875, 23.792378)
        ephemeris.HAS_SWISSEPH = saved
        fb_asc_diff = abs(signed_diff(fb_asc, DEMO_FROZEN["ascendant"]))
        fb_max = max(abs(signed_diff(fb_planets[p]["longitude"], trusted[p]["longitude"]))
                     for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"])
        print("4. Builtin fallback envelope (used only if pyswisseph missing)")
        check("fallback ascendant", fb_asc_diff < 0.05, f"off by {fb_asc_diff:.4f} deg (was 180 deg before fix)")
        check("fallback planets < 1 deg", fb_max < 1.0, f"max diff {fb_max:.4f} deg")
    else:
        print("2-4. SKIPPED — pip install pyswisseph for authoritative verification")

    # 5. Nakshatra -----------------------------------------------------------
    print("5. Nakshatra & Pada (13 deg 20' divisions, hand-computed)")
    ok = 0
    for lon, nak, pada, lord in NAKSHATRA_CASES:
        got = _get_nakshatra_and_pada(lon)
        ok += int(got == (nak, pada, lord))
    check("nakshatra/pada cases", ok == len(NAKSHATRA_CASES), f"{ok}/{len(NAKSHATRA_CASES)} passed")

    # 6. Navamsa -------------------------------------------------------------
    print("6. Navamsa D9 sign mapping (continuous Parashara rule)")
    ok = 0
    for lon, sign in NAVAMSA_CASES:
        idx, _ = calculate_navamsa_sign_index(lon)
        ok += int(INDEX_TO_SIGN[idx] == sign)
    check("navamsa cases", ok == len(NAVAMSA_CASES), f"{ok}/{len(NAVAMSA_CASES)} passed")

    # 7. Vargas --------------------------------------------------------------
    print("7. Divisional charts D2-D144 (Parashari + declared non-Parashari rules)")
    ok = 0
    for (varga, sign_idx, deg, expected) in VARGA_CASES:
        got = INDEX_TO_SIGN[varga_sign_index(varga, (sign_idx - 1) * 30.0 + deg, sign_idx, deg)]
        ok += int(got == expected)
    check("varga cases", ok == len(VARGA_CASES), f"{ok}/{len(VARGA_CASES)} passed")

    # 8. Dasha ---------------------------------------------------------------
    print("8. Vimshottari dasha balance (hand-computed classical arithmetic)")
    birth = datetime(1990, 1, 1, 12, 0)

    def state(moon):
        tl = calculate_vimshottari_timeline(birth, moon, max_years=120.0)
        return get_dasha_at_date(tl, birth)

    s1 = state(0.0)
    check("Moon 0d (full Ketu balance)", (s1.mahadasha, s1.antardasha) == ("Ketu", "Ketu"),
          f"{s1.mahadasha}/{s1.antardasha}")
    s2 = state(20.0)
    check("Moon 20d (50% elapsed, Rahu AD at birth)", (s2.mahadasha, s2.antardasha) == ("Venus", "Rahu"),
          f"{s2.mahadasha}/{s2.antardasha}, PD {s2.pratyantardasha}")
    s3 = state(16.0)
    check("Moon 16d (elapsed lands in Sun AD)", (s3.mahadasha, s3.antardasha) == ("Venus", "Sun"),
          f"{s3.mahadasha}/{s3.antardasha}")
    s4 = state(350.0)
    check("Moon 350d (wraparound Mercury->Venus)", (s4.mahadasha, s4.antardasha) == ("Mercury", "Venus"),
          f"{s4.mahadasha}/{s4.antardasha}")

    # 9. Historical dataset --------------------------------------------------
    print("9. Historical dataset recomputation")
    import json
    data_file = Path(__file__).parent.parent / "data" / "test_charts" / "historical_verified.json"
    dataset = json.loads(data_file.read_text(encoding="utf-8"))
    ok = 0
    for row in dataset:
        y, mo, d = (int(p) for p in row["dob"].split("-"))
        h, mi, sec = (int(float(p)) for p in row["tob"].split(":"))
        chart = calculate_d1_chart(y, mo, d, h, mi, sec, float(row["tz_offset"]),
                                   float(row["lat"]), float(row["lon"]))
        tl = calculate_vimshottari_timeline(datetime(y, mo, d, h, mi, sec), chart.planets["Moon"].longitude)
        ok += int(get_dasha_at_date(tl, datetime(y, mo, d, h, mi, sec)) is not None)
    check("dataset charts", ok == len(dataset), f"{ok}/{len(dataset)} recomputed cleanly")

    # Summary ----------------------------------------------------------------
    passed = sum(1 for _, ok_, _ in CHECKS if ok_)
    print()
    print("=" * 78)
    print(f"VERDICT: {'PASS' if passed == len(CHECKS) else 'FAIL'} — {passed}/{len(CHECKS)} checks")
    print("=" * 78)
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
