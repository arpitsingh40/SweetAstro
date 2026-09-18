"""
Deep analysis: What makes Jupiter/Rahu periods trigger marriage?
Examines Jupiter/Rahu's role in the chart for the 8 people where MD/AD isn't directly connected.
"""

from datetime import datetime
from collections import Counter
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine

JUPITER_RAHU_MATCHES = [
    {"name": "Shah Rukh Khan", "birth": {"year": 1965, "month": 11, "day": 2, "hour": 2, "minute": 30, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1991, 10, 25)},
    {"name": "Priyanka Chopra", "birth": {"year": 1982, "month": 7, "day": 18, "hour": 0, "minute": 0, "tz": 5.5}, "coords": {"lat": 25.6117, "lon": 85.1403}, "marriage_date": datetime(2018, 12, 1)},
    {"name": "Donald Trump", "birth": {"year": 1946, "month": 6, "day": 14, "hour": 10, "minute": 54, "tz": -4}, "coords": {"lat": 40.7128, "lon": -74.0060}, "marriage_date": datetime(2005, 1, 22)},
    {"name": "Kareena Kapoor", "birth": {"year": 1980, "month": 9, "day": 21, "hour": 8, "minute": 39, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2012, 10, 16)},
    {"name": "Katrina Kaif", "birth": {"year": 1983, "month": 7, "day": 16, "hour": 6, "minute": 40, "tz": 5.5}, "coords": {"lat": 22.31, "lon": 114.16}, "marriage_date": datetime(2021, 12, 9)},
    {"name": "Alia Bhatt", "birth": {"year": 1993, "month": 3, "day": 15, "hour": 11, "minute": 30, "tz": 5.5}, "coords": {"lat": 18.9667, "lon": 72.8333}, "marriage_date": datetime(2022, 4, 14)},
    {"name": "Akshay Kumar", "birth": {"year": 1967, "month": 9, "day": 9, "hour": 14, "minute": 0, "tz": 5.5}, "coords": {"lat": 30.9010, "lon": 75.8573}, "marriage_date": datetime(2001, 1, 17)},
    {"name": "Ajay Devgn", "birth": {"year": 1969, "month": 4, "day": 2, "hour": 13, "minute": 32, "tz": 5.5}, "coords": {"lat": 28.6139, "lon": 77.2090}, "marriage_date": datetime(1999, 2, 24)},
    {"name": "Shilpa Shetty", "birth": {"year": 1975, "month": 6, "day": 8, "hour": 16, "minute": 30, "tz": 5.5}, "coords": {"lat": 12.9716, "lon": 77.5946}, "marriage_date": datetime(2009, 11, 22)},
    {"name": "Deepika Padukone", "birth": {"year": 1986, "month": 1, "day": 5, "hour": 0, "minute": 5, "tz": 5.5}, "coords": {"lat": 12.9716, "lon": 77.5946}, "marriage_date": datetime(2018, 11, 14)},
]


def analyze_jupiter_rahu(celeb):
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

    promise = engine.analyze_natal_promise()
    sev_lord = promise.seventh_lord
    sev_lord_house = promise.seventh_lord_house
    sev_sign_idx = d1.houses[7].sign_index

    # Jupiter's role
    jup_house = d1.planets["Jupiter"].house if "Jupiter" in d1.planets else 0
    jup_sign_idx = d1.planets["Jupiter"].sign_index if "Jupiter" in d1.planets else 0
    jup_dignity = engine._get_d1_dignity("Jupiter")
    jup_aspects_houses = d1.planets["Jupiter"].aspecting_houses if "Jupiter" in d1.planets else []
    jup_aspects_7th = 7 in jup_aspects_houses
    jup_aspects_sev_lord = sev_lord_house in jup_aspects_houses if sev_lord_house > 0 else False
    jup_in_kendra_tri = jup_house in [1, 4, 5, 7, 9, 10]

    # Rahu's role
    rahu_house = d1.planets["Rahu"].house if "Rahu" in d1.planets else 0
    rahu_dignity = engine._get_d1_dignity("Rahu")
    rahu_aspects_houses = d1.planets["Rahu"].aspecting_houses if "Rahu" in d1.planets else []
    rahu_aspects_7th = 7 in rahu_aspects_houses
    rahu_aspects_sev_lord = sev_lord_house in rahu_aspects_houses if sev_lord_house > 0 else False

    # Marriage-related houses for Jupiter/Rahu
    jup_in_2_7_11 = jup_house in [2, 7, 11]
    jup_in_1_5_9 = jup_house in [1, 5, 9]
    rahu_in_2_7_11 = rahu_house in [2, 7, 11]

    # Navamsa
    d9_jup_dignity = engine._get_d9_dignity("Jupiter")

    # Which dasha was the actual marriage in?
    all_windows = engine.find_marriage_dashas(engine.birth_date, datetime(2030, 12, 31), search_from_birth=True)
    matching = None
    for w in all_windows:
        if w.start_date <= celeb["marriage_date"] <= w.end_date:
            matching = w
            break

    return {
        "name": celeb["name"],
        "marriage_date": celeb["marriage_date"].strftime("%Y-%m"),
        "7th_lord": sev_lord,
        "7th_lord_house": sev_lord_house,
        "jup_house": jup_house,
        "jup_dignity": jup_dignity,
        "jup_aspects_7th": jup_aspects_7th,
        "jup_aspects_sev_lord": jup_aspects_sev_lord,
        "jup_in_kendra_tri": jup_in_kendra_tri,
        "jup_in_2_7_11": jup_in_2_7_11,
        "jup_in_1_5_9": jup_in_1_5_9,
        "rahu_house": rahu_house,
        "rahu_dignity": rahu_dignity,
        "rahu_aspects_7th": rahu_aspects_7th,
        "rahu_aspects_sev_lord": rahu_aspects_sev_lord,
        "rahu_in_2_7_11": rahu_in_2_7_11,
        "d9_jup_dignity": d9_jup_dignity,
        "matching_md": matching.mahadasha_lord if matching else "N/A",
        "matching_ad": matching.antardasha_lord if matching else "N/A",
        "matching_confidence": matching.confidence.value if matching else "N/A",
    }


def main():
    print("=" * 110)
    print("JUPITER/RAHU ANALYSIS: Why do their periods trigger marriage?")
    print("=" * 110)

    results = []
    for celeb in JUPITER_RAHU_MATCHES:
        r = analyze_jupiter_rahu(celeb)
        results.append(r)

    print(f"\n{'Name':20s} | {'7L':6s} {'7L-H':4s} | {'Jup-H':5s} {'Jup-D':10s} {'J-7th':5s} {'J-7L':5s} {'J-KT':5s} {'J-2711':6s} {'J-159':5s} | "
          f"{'Rah-H':5s} {'Rah-D':10s} {'R-7th':5s} {'R-7L':5s} {'R-2711':6s} | {'D9-J':10s} | {'MD':8s} {'AD':8s}")
    print("-" * 110)

    for r in results:
        print(f"{r['name']:20s} | {r['7th_lord']:6s} {r['7th_lord_house']:4d} | "
              f"{r['jup_house']:5d} {r['jup_dignity']:10s} "
              f"{'YES' if r['jup_aspects_7th'] else 'NO':5s} "
              f"{'YES' if r['jup_aspects_sev_lord'] else 'NO':5s} "
              f"{'YES' if r['jup_in_kendra_tri'] else 'NO':5s} "
              f"{'YES' if r['jup_in_2_7_11'] else 'NO':6s} "
              f"{'YES' if r['jup_in_1_5_9'] else 'NO':5s} | "
              f"{r['rahu_house']:5d} {r['rahu_dignity']:10s} "
              f"{'YES' if r['rahu_aspects_7th'] else 'NO':5s} "
              f"{'YES' if r['rahu_aspects_sev_lord'] else 'NO':5s} "
              f"{'YES' if r['rahu_in_2_7_11'] else 'NO':6s} | "
              f"{r['d9_jup_dignity']:10s} | {r['matching_md']:8s} {r['matching_ad']:8s}")

    # Pattern summary
    print("\n" + "=" * 110)
    print("PATTERN SUMMARY")
    print("=" * 110)

    jup_aspect_7th = sum(1 for r in results if r["jup_aspects_7th"])
    jup_aspect_7L = sum(1 for r in results if r["jup_aspects_sev_lord"])
    jup_kendra_tri = sum(1 for r in results if r["jup_in_kendra_tri"])
    jup_2711 = sum(1 for r in results if r["jup_in_2_7_11"])
    jup_159 = sum(1 for r in results if r["jup_in_1_5_9"])
    rahu_aspect_7th = sum(1 for r in results if r["rahu_aspects_7th"])
    rahu_aspect_7L = sum(1 for r in results if r["rahu_aspects_sev_lord"])
    rahu_2711 = sum(1 for r in results if r["rahu_in_2_7_11"])

    print(f"""
  Jupiter aspects 7th house:         {jup_aspect_7th}/{len(results)} ({jup_aspect_7th/len(results)*100:.0f}%)
  Jupiter aspects 7th lord sign:     {jup_aspect_7L}/{len(results)} ({jup_aspect_7L/len(results)*100:.0f}%)
  Jupiter in Kendra/Trikona:         {jup_kendra_tri}/{len(results)} ({jup_kendra_tri/len(results)*100:.0f}%)
  Jupiter in 2/7/11:                 {jup_2711}/{len(results)} ({jup_2711/len(results)*100:.0f}%)
  Jupiter in 1/5/9:                  {jup_159}/{len(results)} ({jup_159/len(results)*100:.0f}%)
  Jupiter connected to marriage:     {sum(1 for r in results if r['jup_aspects_7th'] or r['jup_aspects_sev_lord'] or r['jup_in_2_7_11'])}/{len(results)}

  Rahu aspects 7th house:            {rahu_aspect_7th}/{len(results)} ({rahu_aspect_7th/len(results)*100:.0f}%)
  Rahu aspects 7th lord sign:        {rahu_aspect_7L}/{len(results)} ({rahu_aspect_7L/len(results)*100:.0f}%)
  Rahu in 2/7/11:                    {rahu_2711}/{len(results)} ({rahu_2711/len(results)*100:.0f}%)
  Rahu connected to marriage:        {sum(1 for r in results if r['rahu_aspects_7th'] or r['rahu_aspects_sev_lord'] or r['rahu_in_2_7_11'])}/{len(results)}
""")

    # Dasha pattern
    print("  Dasha patterns for Jupiter/Rahu matches:")
    for r in results:
        print(f"    {r['name']:20s}: MD={r['matching_md']:8s} AD={r['matching_ad']:8s} | "
              f"Jup conn: {'YES' if r['jup_aspects_7th'] or r['jup_aspects_sev_lord'] or r['jup_in_2_7_11'] else 'NO'} | "
              f"Rahu conn: {'YES' if r['rahu_aspects_7th'] or r['rahu_aspects_sev_lord'] or r['rahu_in_2_7_11'] else 'NO'}")


if __name__ == "__main__":
    main()
