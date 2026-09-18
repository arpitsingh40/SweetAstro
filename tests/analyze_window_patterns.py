"""
Deep Analysis: Why Marriage Windows Work
Examines all 18 celebrities to find patterns in successful vs non-successful windows.
"""

from datetime import datetime
from collections import Counter, defaultdict
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine, MarriageStrength

ALL_CELEBRITIES = [
    {"name": "Shah Rukh Khan", "birth": {"year": 1965, "month": 11, "day": 2, "hour": 2, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1991, 10, 25), "spouse": "Gauri Chibber"},
    {"name": "Priyanka Chopra", "birth": {"year": 1982, "month": 7, "day": 18, "hour": 0, "minute": 0, "tz": 5.5}, "coords": {"lat": 25.6117, "lon": 85.1403}, "marriage_date": datetime(2018, 12, 1), "spouse": "Nick Jonas"},
    {"name": "Anushka Sharma", "birth": {"year": 1988, "month": 5, "day": 1, "hour": 8, "minute": 0, "tz": 5.5}, "coords": {"lat": 30.9010, "lon": 75.8573}, "marriage_date": datetime(2017, 12, 11), "spouse": "Virat Kohli"},
    {"name": "Amitabh Bachchan", "birth": {"year": 1942, "month": 10, "day": 11, "hour": 16, "minute": 0, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1973, 6, 3), "spouse": "Jaya Bhaduri"},
    {"name": "Shilpa Shetty", "birth": {"year": 1975, "month": 6, "day": 8, "hour": 16, "minute": 30, "tz": 5.5}, "coords": {"lat": 12.9716, "lon": 77.5946}, "marriage_date": datetime(2009, 11, 22), "spouse": "Raj Kundra"},
    {"name": "Donald Trump", "birth": {"year": 1946, "month": 6, "day": 14, "hour": 10, "minute": 54, "tz": -4}, "coords": {"lat": 40.7128, "lon": -74.0060}, "marriage_date": datetime(2005, 1, 22), "spouse": "Melania Knauss"},
    {"name": "Angelina Jolie", "birth": {"year": 1975, "month": 6, "day": 4, "hour": 9, "minute": 21, "tz": -7}, "coords": {"lat": 34.0522, "lon": -118.2437}, "marriage_date": datetime(1996, 3, 24), "spouse": "Jonny Lee Miller"},
    {"name": "Barack Obama", "birth": {"year": 1961, "month": 8, "day": 4, "hour": 19, "minute": 24, "tz": -10}, "coords": {"lat": 21.3069, "lon": -157.8583}, "marriage_date": datetime(1992, 10, 3), "spouse": "Michelle Robinson"},
    {"name": "Kareena Kapoor", "birth": {"year": 1980, "month": 9, "day": 21, "hour": 8, "minute": 39, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2012, 10, 16), "spouse": "Saif Ali Khan"},
    {"name": "Katrina Kaif", "birth": {"year": 1983, "month": 7, "day": 16, "hour": 6, "minute": 40, "tz": 5.5}, "coords": {"lat": 22.31, "lon": 114.16}, "marriage_date": datetime(2021, 12, 9), "spouse": "Vicky Kaushal"},
    {"name": "Deepika Padukone", "birth": {"year": 1986, "month": 1, "day": 5, "hour": 0, "minute": 5, "tz": 5.5}, "coords": {"lat": 12.9716, "lon": 77.5946}, "marriage_date": datetime(2018, 11, 14), "spouse": "Ranveer Singh"},
    {"name": "Ranbir Kapoor", "birth": {"year": 1982, "month": 9, "day": 28, "hour": 12, "minute": 0, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2022, 4, 14), "spouse": "Alia Bhatt"},
    {"name": "Alia Bhatt", "birth": {"year": 1993, "month": 3, "day": 15, "hour": 11, "minute": 30, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2022, 4, 14), "spouse": "Ranbir Kapoor"},
    {"name": "Vicky Kaushal", "birth": {"year": 1988, "month": 5, "day": 16, "hour": 12, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(2021, 12, 9), "spouse": "Katrina Kaif"},
    {"name": "Ranveer Singh", "birth": {"year": 1985, "month": 7, "day": 6, "hour": 2, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(2018, 11, 14), "spouse": "Deepika Padukone"},
    {"name": "Akshay Kumar", "birth": {"year": 1967, "month": 9, "day": 9, "hour": 14, "minute": 0, "tz": 5.5}, "coords": {"lat": 30.9010, "lon": 75.8573}, "marriage_date": datetime(2001, 1, 17), "spouse": "Twinkle Khanna"},
    {"name": "Ajay Devgn", "birth": {"year": 1969, "month": 4, "day": 2, "hour": 13, "minute": 32, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1999, 2, 24), "spouse": "Kajol"},
    {"name": "Hrithik Roshan", "birth": {"year": 1974, "month": 1, "day": 10, "hour": 12, "minute": 0, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2000, 12, 20), "spouse": "Sussanne Khan"},
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

    search_end = datetime(2030, 12, 31)
    all_windows = engine.find_marriage_dashas(engine.birth_date, search_end, search_from_birth=True)
    promise = engine.analyze_natal_promise()
    navamsa = engine.confirm_with_navamsa()

    matching = None
    for w in all_windows:
        if w.start_date <= celeb["marriage_date"] <= w.end_date:
            matching = w
            break

    if matching is None:
        return None

    md = matching.mahadasha_lord
    ad = matching.antardasha_lord

    def is_connected(planet, lord):
        if planet == lord:
            return True
        if lord in engine.d1.planets:
            if engine.d1.planets[lord].house == 7:
                return True
        return False

    md_is_7th_lord = is_connected(md, promise.seventh_lord)
    md_is_venus = md == "Venus"
    md_in_7th = engine._is_planet_in_house(md, 7)
    md_is_darakaraka = md == engine._get_darakaraka()

    ad_is_7th_lord = is_connected(ad, promise.seventh_lord)
    ad_is_venus = ad == "Venus"
    ad_in_7th = engine._is_planet_in_house(ad, 7)
    ad_is_darakaraka = ad == engine._get_darakaraka()

    md_house = engine.d1.planets[md].house if md in engine.d1.planets else 0
    ad_house = engine.d1.planets[ad].house if ad in engine.d1.planets else 0

    md_dignity = engine._get_d1_dignity(md)
    ad_dignity = engine._get_d1_dignity(ad)

    md_score = engine._score_dasha_lord(md)
    ad_score = engine._score_dasha_lord(ad)

    return {
        "name": celeb["name"],
        "7th_lord": promise.seventh_lord,
        "7th_lord_house": promise.seventh_lord_house,
        "venus_dignity": promise.venus_dignity,
        "promise_strength": promise.strength.value,
        "navamsa_confirmed": navamsa.confirmed,
        "matching_md": md,
        "matching_ad": ad,
        "md_is_7th_lord": md_is_7th_lord,
        "md_is_venus": md_is_venus,
        "md_in_7th": md_in_7th,
        "md_is_darakaraka": md_is_darakaraka,
        "md_house": md_house,
        "md_dignity": md_dignity,
        "md_score": md_score,
        "ad_is_7th_lord": ad_is_7th_lord,
        "ad_is_venus": ad_is_venus,
        "ad_in_7th": ad_in_7th,
        "ad_is_darakaraka": ad_is_darakaraka,
        "ad_house": ad_house,
        "ad_dignity": ad_dignity,
        "ad_score": ad_score,
        "confidence": matching.confidence.value,
        "indicators": [i.value for i in matching.indicators],
        "num_windows": len(all_windows),
    }


def main():
    print("=" * 100)
    print("DEEP ANALYSIS: WHY MARRIAGE WINDOWS WORK")
    print("=" * 100)

    results = []
    for celeb in ALL_CELEBRITIES:
        r = analyze(celeb)
        if r:
            results.append(r)

    # === TABLE 1: Matching Window Details ===
    print("\n" + "=" * 100)
    print("1. MATCHING WINDOW DETAILS")
    print("=" * 100)
    print(f"{'Name':22s} | {'7th Lord':8s} | {'Match MD':8s} | {'Match AD':8s} | "
          f"{'MD=7L?':6s} {'MD=V?':5s} {'MD=7H?':6s} {'MD=DK?':6s} | "
          f"{'AD=7L?':6s} {'AD=V?':5s} {'AD=7H?':6s} {'AD=DK?':6s} | "
          f"{'MD Sc':5s} {'AD Sc':5s} | {'Confidence':10s}")
    print("-" * 100)
    for r in results:
        print(f"{r['name']:22s} | {r['7th_lord']:8s} | {r['matching_md']:8s} | {r['matching_ad']:8s} | "
              f"{'YES' if r['md_is_7th_lord'] else 'NO':6s} "
              f"{'YES' if r['md_is_venus'] else 'NO':5s} "
              f"{'YES' if r['md_in_7th'] else 'NO':6s} "
              f"{'YES' if r['md_is_darakaraka'] else 'NO':6s} | "
              f"{'YES' if r['ad_is_7th_lord'] else 'NO':6s} "
              f"{'YES' if r['ad_is_venus'] else 'NO':5s} "
              f"{'YES' if r['ad_in_7th'] else 'NO':6s} "
              f"{'YES' if r['ad_is_darakaraka'] else 'NO':6s} | "
              f"{r['md_score']:5d} {r['ad_score']:5d} | {r['confidence']:10s}")

    # === PATTERN ANALYSIS ===
    print("\n" + "=" * 100)
    print("2. PATTERN ANALYSIS")
    print("=" * 100)

    md_lords = [r["matching_md"] for r in results]
    ad_lords = [r["matching_ad"] for r in results]
    md_connected_7th = sum(1 for r in results if r["md_is_7th_lord"] or r["md_is_venus"] or r["md_in_7th"])
    ad_connected_7th = sum(1 for r in results if r["ad_is_7th_lord"] or r["ad_is_venus"] or r["ad_in_7th"])
    md_connected_any = sum(1 for r in results if r["md_is_7th_lord"] or r["md_is_venus"] or r["md_in_7th"] or r["md_is_darakaraka"])
    ad_connected_any = sum(1 for r in results if r["ad_is_7th_lord"] or r["ad_is_venus"] or r["ad_in_7th"] or r["ad_is_darakaraka"])

    print(f"\n  Mahadasha Lord Distribution:")
    for lord, count in Counter(md_lords).most_common():
        pct = count / len(results) * 100
        print(f"    {lord:10s}: {count:2d} ({pct:.0f}%)")

    print(f"\n  Antardasha Lord Distribution:")
    for lord, count in Counter(ad_lords).most_common():
        pct = count / len(results) * 100
        print(f"    {lord:10s}: {count:2d} ({pct:.0f}%)")

    print(f"\n  Mahadasha Connection to 7th House:")
    print(f"    MD = 7th Lord or Venus or in 7th: {md_connected_7th}/{len(results)} ({md_connected_7th/len(results)*100:.0f}%)")
    print(f"    MD = any marriage indicator (7L/Venus/7H/DK): {md_connected_any}/{len(results)} ({md_connected_any/len(results)*100:.0f}%)")

    print(f"\n  Antardasha Connection to 7th House:")
    print(f"    AD = 7th Lord or Venus or in 7th: {ad_connected_7th}/{len(results)} ({ad_connected_7th/len(results)*100:.0f}%)")
    print(f"    AD = any marriage indicator (7L/Venus/7H/DK): {ad_connected_any}/{len(results)} ({ad_connected_any/len(results)*100:.0f}%)")

    # === COMBINATION PATTERNS ===
    print(f"\n  Key Pattern: Which combination is most common?")
    patterns = []
    for r in results:
        md_key = "7L" if r["md_is_7th_lord"] else ("V" if r["md_is_venus"] else ("7H" if r["md_in_7th"] else ("DK" if r["md_is_darakaraka"] else "-")))
        ad_key = "7L" if r["ad_is_7th_lord"] else ("V" if r["ad_is_venus"] else ("7H" if r["ad_in_7th"] else ("DK" if r["ad_is_darakaraka"] else "-")))
        patterns.append(f"{md_key}/{ad_key}")

    for pat, count in Counter(patterns).most_common():
        names = [r["name"] for r, p in zip(results, patterns) if p == pat]
        print(f"    MD:{pat.split('/')[0]:3s} AD:{pat.split('/')[1]:3s}: {count:2d} — {', '.join(names)}")

    # === DIGNITY ANALYSIS ===
    print(f"\n  MD Dignity Distribution:")
    for dignity, count in Counter(r["md_dignity"] for r in results).most_common():
        print(f"    {dignity:15s}: {count:2d}")

    print(f"\n  AD Dignity Distribution:")
    for dignity, count in Counter(r["ad_dignity"] for r in results).most_common():
        print(f"    {dignity:15s}: {count:2d}")

    # === HOUSE ANALYSIS ===
    print(f"\n  MD House Distribution:")
    for house, count in Counter(r["md_house"] for r in results).most_common():
        print(f"    House {house:2d}: {count:2d}")

    print(f"\n  AD House Distribution:")
    for house, count in Counter(r["ad_house"] for r in results).most_common():
        print(f"    House {house:2d}: {count:2d}")

    # === SCORE ANALYSIS ===
    print(f"\n  Score Statistics:")
    md_scores = [r["md_score"] for r in results]
    ad_scores = [r["ad_score"] for r in results]
    print(f"    MD scores: min={min(md_scores)}, max={max(md_scores)}, avg={sum(md_scores)/len(md_scores):.1f}")
    print(f"    AD scores: min={min(ad_scores)}, max={max(ad_scores)}, avg={sum(ad_scores)/len(ad_scores):.1f}")

    # === PROMISE vs MATCHING ===
    print(f"\n  Promise Strength vs Matching Window:")
    for strength in ["Very High", "High", "Moderate", "Low", "Delayed"]:
        subset = [r for r in results if r["promise_strength"] == strength]
        if subset:
            md7l = sum(1 for r in subset if r["md_is_7th_lord"] or r["md_is_venus"])
            print(f"    Promise {strength:10s}: {len(subset):2d} people, MD=7L/V: {md7l}")

    # === KEY FINDINGS ===
    print("\n" + "=" * 100)
    print("3. KEY FINDINGS")
    print("=" * 100)

    md_venus_count = sum(1 for r in results if r["md_is_venus"])
    md_7lord_count = sum(1 for r in results if r["md_is_7th_lord"])
    ad_venus_count = sum(1 for r in results if r["ad_is_venus"])
    ad_7lord_count = sum(1 for r in results if r["ad_is_7th_lord"])

    at_least_one = sum(1 for r in results if r["md_is_7th_lord"] or r["md_is_venus"] or r["md_in_7th"] or r["md_is_darakaraka"] or r["ad_is_7th_lord"] or r["ad_is_venus"] or r["ad_in_7th"] or r["ad_is_darakaraka"])
    print(f"""
  FINDING 1: Mahadasha lord is Venus in {md_venus_count}/{len(results)} ({md_venus_count/len(results)*100:.0f}%)
  FINDING 2: Mahadasha lord is 7th Lord in {md_7lord_count}/{len(results)} ({md_7lord_count/len(results)*100:.0f}%)
  FINDING 3: Antardasha lord is Venus in {ad_venus_count}/{len(results)} ({ad_venus_count/len(results)*100:.0f}%)
  FINDING 4: Antardasha lord is 7th Lord in {ad_7lord_count}/{len(results)} ({ad_7lord_count/len(results)*100:.0f}%)
  FINDING 5: MD or AD is Venus or 7th Lord: {sum(1 for r in results if r["md_is_venus"] or r["md_is_7th_lord"] or r["ad_is_venus"] or r["ad_is_7th_lord"])}/{len(results)}
  FINDING 6: AD connected to any marriage indicator: {ad_connected_any}/{len(results)} ({ad_connected_any/len(results)*100:.0f}%)
  FINDING 7: At least one of MD/AD connected: {at_least_one}/{len(results)}
""")

    # === NON-MATCHING WINDOWS ANALYSIS ===
    print("=" * 100)
    print("4. NON-MATCHING WINDOWS: Why they don't trigger marriage")
    print("=" * 100)

    for celeb in ALL_CELEBRITIES[:3]:
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
        all_windows = engine.find_marriage_dashas(engine.birth_date, datetime(2030, 12, 31), search_from_birth=True)

        non_match = [w for w in all_windows if not (w.start_date <= celeb["marriage_date"] <= w.end_date)][:3]

        print(f"\n  {celeb['name']} — 7th Lord: {engine.seventh_lord}")
        print(f"  Non-matching windows (first 3 of {len(all_windows)}):")
        for w in non_match:
            md, ad = w.mahadasha_lord, w.antardasha_lord
            md_conn = "7L" if md == engine.seventh_lord else ("V" if md == "Venus" else ("7H" if engine._is_planet_in_house(md, 7) else "-"))
            ad_conn = "7L" if ad == engine.seventh_lord else ("V" if ad == "Venus" else ("7H" if engine._is_planet_in_house(ad, 7) else "-"))
            print(f"    {w.start_date.strftime('%Y-%m')} to {w.end_date.strftime('%Y-%m')} | "
                  f"MD:{md:8s}({md_conn}) AD:{ad:8s}({ad_conn}) | "
                  f"Conf: {w.confidence.value}")


if __name__ == "__main__":
    main()
