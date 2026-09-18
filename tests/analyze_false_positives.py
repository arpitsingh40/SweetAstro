"""
Why do most windows fail? Analyze false positive vs true positive windows.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from datetime import datetime
from collections import Counter
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine, MarriageStrength

ALL_CELEBRITIES = [
    {"name": "Shah Rukh Khan", "birth": {"year": 1965, "month": 11, "day": 2, "hour": 2, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1991, 10, 25)},
    {"name": "Priyanka Chopra", "birth": {"year": 1982, "month": 7, "day": 18, "hour": 0, "minute": 0, "tz": 5.5}, "coords": {"lat": 25.6117, "lon": 85.1403}, "marriage_date": datetime(2018, 12, 1)},
    {"name": "Anushka Sharma", "birth": {"year": 1988, "month": 5, "day": 1, "hour": 8, "minute": 0, "tz": 5.5}, "coords": {"lat": 30.9010, "lon": 75.8573}, "marriage_date": datetime(2017, 12, 11)},
    {"name": "Amitabh Bachchan", "birth": {"year": 1942, "month": 10, "day": 11, "hour": 16, "minute": 0, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1973, 6, 3)},
    {"name": "Shilpa Shetty", "birth": {"year": 1975, "month": 6, "day": 8, "hour": 16, "minute": 30, "tz": 5.5}, "coords": {"lat": 12.9716, "lon": 77.5946}, "marriage_date": datetime(2009, 11, 22)},
    {"name": "Donald Trump", "birth": {"year": 1946, "month": 6, "day": 14, "hour": 10, "minute": 54, "tz": -4}, "coords": {"lat": 40.7128, "lon": -74.0060}, "marriage_date": datetime(2005, 1, 22)},
    {"name": "Angelina Jolie", "birth": {"year": 1975, "month": 6, "day": 4, "hour": 9, "minute": 21, "tz": -7}, "coords": {"lat": 34.0522, "lon": -118.2437}, "marriage_date": datetime(1996, 3, 24)},
    {"name": "Barack Obama", "birth": {"year": 1961, "month": 8, "day": 4, "hour": 19, "minute": 24, "tz": -10}, "coords": {"lat": 21.3069, "lon": -157.8583}, "marriage_date": datetime(1992, 10, 3)},
    {"name": "Kareena Kapoor", "birth": {"year": 1980, "month": 9, "day": 21, "hour": 8, "minute": 39, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2012, 10, 16)},
    {"name": "Katrina Kaif", "birth": {"year": 1983, "month": 7, "day": 16, "hour": 6, "minute": 40, "tz": 5.5}, "coords": {"lat": 22.31, "lon": 114.16}, "marriage_date": datetime(2021, 12, 9)},
    {"name": "Deepika Padukone", "birth": {"year": 1986, "month": 1, "day": 5, "hour": 0, "minute": 5, "tz": 5.5}, "coords": {"lat": 12.9716, "lon": 77.5946}, "marriage_date": datetime(2018, 11, 14)},
    {"name": "Ranbir Kapoor", "birth": {"year": 1982, "month": 9, "day": 28, "hour": 12, "minute": 0, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2022, 4, 14)},
    {"name": "Alia Bhatt", "birth": {"year": 1993, "month": 3, "day": 15, "hour": 11, "minute": 30, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2022, 4, 14)},
    {"name": "Vicky Kaushal", "birth": {"year": 1988, "month": 5, "day": 16, "hour": 12, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(2021, 12, 9)},
    {"name": "Ranveer Singh", "birth": {"year": 1985, "month": 7, "day": 6, "hour": 2, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(2018, 11, 14)},
    {"name": "Akshay Kumar", "birth": {"year": 1967, "month": 9, "day": 9, "hour": 14, "minute": 0, "tz": 5.5}, "coords": {"lat": 30.9010, "lon": 75.8573}, "marriage_date": datetime(2001, 1, 17)},
    {"name": "Ajay Devgn", "birth": {"year": 1969, "month": 4, "day": 2, "hour": 13, "minute": 32, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1999, 2, 24)},
    {"name": "Hrithik Roshan", "birth": {"year": 1974, "month": 1, "day": 10, "hour": 12, "minute": 0, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2000, 12, 20)},
]


def analyze(celeb):
    b = celeb["birth"]
    c = celeb["coords"]
    d1 = calculate_d1_chart(
        year=b["year"], month=b["month"], day=b["day"],
        hour=b["hour"], minute=b["minute"], second=0,
        tz_offset_hours=b["tz"], lat=c["lat"], lon=c["lon"]
    )
    d9 = calculate_navamsa_chart(d1)
    birth_dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"], 0)
    engine = MarriageTimingEngine(d1, d9, birth_dt)

    all_windows = engine.find_marriage_dashas(birth_dt, datetime(2030, 12, 31), search_from_birth=True)

    true_positive = None
    false_positives = []
    for w in all_windows:
        if w.start_date <= celeb["marriage_date"] <= w.end_date:
            true_positive = w
        else:
            false_positives.append(w)

    # For each false positive, check if transits were active at midpoint
    fp_with_transits = []
    for w in false_positives:
        mid = w.start_date + (w.end_date - w.start_date) / 2
        transit = engine.analyze_transits(mid)
        fp_with_transits.append({
            "window": w,
            "transit_active": transit.double_transit_active,
            "jupiter_active": transit.jupiter_transit_active,
            "saturn_active": transit.saturn_transit_active,
        })

    # For true positive, check transits
    tp_transit = None
    if true_positive:
        mid = true_positive.start_date + (true_positive.end_date - true_positive.start_date) / 2
        transit = engine.analyze_transits(mid)
        tp_transit = {
            "transit_active": transit.double_transit_active,
            "jupiter_active": transit.jupiter_transit_active,
            "saturn_active": transit.saturn_transit_active,
        }

    return {
        "name": celeb["name"],
        "total_windows": len(all_windows),
        "true_positive": true_positive,
        "false_positives_count": len(false_positives),
        "tp_transit": tp_transit,
        "fp_transits": fp_with_transits,
        "fp_confidence_dist": Counter(w.confidence.value for w in false_positives),
    }


def main():
    print("=" * 100)
    print("WHY DO MOST WINDOWS FAIL?")
    print("=" * 100)

    results = []
    for celeb in ALL_CELEBRITIES:
        r = analyze(celeb)
        results.append(r)

    # Summary table
    print("\nWINDOW COUNTS:")
    print(f"{'Name':22s} | {'Total':5s} | {'TP':2s} | {'FP':3s} | {'FP%':5s} | {'TP Transit':10s} | FP Transit Active")
    print("-" * 100)
    for r in results:
        fp_pct = r["false_positives_count"] / r["total_windows"] * 100 if r["total_windows"] > 0 else 0
        tp_transit = "YES" if r["tp_transit"] and r["tp_transit"]["transit_active"] else ("Jup only" if r["tp_transit"] and r["tp_transit"]["jupiter_active"] else "NO")
        fp_transit_active = sum(1 for f in r["fp_transits"] if f["transit_active"])
        fp_jup_active = sum(1 for f in r["fp_transits"] if f["jupiter_active"])
        print(f"{r['name']:22s} | {r['total_windows']:5d} | {1:2d} | {r['false_positives_count']:3d} | {fp_pct:5.0f}% | {tp_transit:10s} | {fp_transit_active} double, {fp_jup_active} jupiter")

    # Overall stats
    total_all = sum(r["total_windows"] for r in results)
    total_tp = len(results)
    total_fp = sum(r["false_positives_count"] for r in results)
    tp_with_transit = sum(1 for r in results if r["tp_transit"] and r["tp_transit"]["transit_active"])
    tp_with_jupiter = sum(1 for r in results if r["tp_transit"] and r["tp_transit"]["jupiter_active"])

    print(f"\n{'=' * 100}")
    print(f"OVERALL STATS:")
    print(f"  Total windows across 18 people:  {total_all}")
    print(f"  True positives (marriage):        {total_tp}")
    print(f"  False positives:                  {total_fp}")
    print(f"  False positive rate:              {total_fp/total_all*100:.0f}%")
    print(f"  Avg windows per person:           {total_all/len(results):.1f}")
    print(f"  True positives with double transit: {tp_with_transit}/{total_tp} ({tp_with_transit/total_tp*100:.0f}%)")
    print(f"  True positives with Jupiter transit: {tp_with_jupiter}/{total_tp} ({tp_with_jupiter/total_tp*100:.0f}%)")

    # FP confidence distribution
    all_fp_conf = Counter()
    for r in results:
        all_fp_conf += r["fp_confidence_dist"]
    print(f"\n  False positive confidence distribution:")
    for conf, count in all_fp_conf.most_common():
        print(f"    {conf:12s}: {count:3d} ({count/total_fp*100:.0f}%)")

    # FP transit stats
    all_fp_double = sum(1 for r in results for f in r["fp_transits"] if f["transit_active"])
    all_fp_jupiter = sum(1 for r in results for f in r["fp_transits"] if f["jupiter_active"])
    all_fp_saturn = sum(1 for r in results for f in r["fp_transits"] if f["saturn_active"])
    print(f"\n  False positive transit activity:")
    print(f"    Double transit active: {all_fp_double}/{total_fp} ({all_fp_double/total_fp*100:.0f}%)")
    print(f"    Jupiter transit active: {all_fp_jupiter}/{total_fp} ({all_fp_jupiter/total_fp*100:.0f}%)")
    print(f"    Saturn transit active: {all_fp_saturn}/{total_fp} ({all_fp_saturn/total_fp*100:.0f}%)")

    # Key insight
    print(f"\n{'=' * 100}")
    print("KEY INSIGHT:")
    print(f"  If we REQUIRED double transit to be active:")
    print(f"    Would keep {tp_with_transit} true positives")
    print(f"    Would eliminate {all_fp_double} false positives")
    print(f"    Remaining FP: {total_fp - all_fp_double}")
    print(f"    Precision improvement: {total_tp/(total_tp + total_fp - all_fp_double)*100:.0f}% (from {total_tp/(total_tp + total_fp)*100:.0f}%)")


if __name__ == "__main__":
    main()
