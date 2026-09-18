"""
Deep Case Analysis: What specific factors made marriage POSSIBLE in each window.
For each celebrity: what was strong, what was denied, why did it still happen.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from datetime import datetime
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine, MarriageStrength
from SweetAstro.src.core.arudha import calculate_upapada

ALL = [
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


def full_analysis(celeb):
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
    ul = engine.upapada

    sev_lord = engine.seventh_lord
    sev_house = d1.houses[7]
    venus = d1.planets.get("Venus")
    dk = engine._get_darakaraka()

    # All windows
    all_windows = engine.find_marriage_dashas(birth_dt, datetime(2030, 12, 31), search_from_birth=True)

    # Matching window
    matching = None
    for w in all_windows:
        if w.start_date <= celeb["marriage_date"] <= w.end_date:
            matching = w
            break

    # Natal factors
    natal = []
    if venus and venus.dignity in ["Exalted", "Own", "Moolatrikona"]:
        natal.append(f"Venus {venus.dignity} in house {venus.house}")
    elif venus and venus.dignity == "Friend":
        natal.append(f"Venus Friend in house {venus.house}")
    elif venus and venus.dignity == "Debilitated":
        natal.append(f"Venus Debilitated in house {venus.house}")
    elif venus and venus.dignity == "Enemy":
        natal.append(f"Venus Enemy in house {venus.house}")

    if venus and venus.is_combust:
        natal.append("Venus COMBUST")

    if sev_lord in d1.planets:
        sl = d1.planets[sev_lord]
        if sl.dignity in ["Exalted", "Own", "Moolatrikona"]:
            natal.append(f"7th lord {sev_lord} {sl.dignity} in house {sl.house}")
        elif sl.dignity == "Debilitated":
            natal.append(f"7th lord {sev_lord} Debilitated in house {sl.house}")
        elif sl.dignity == "Enemy":
            natal.append(f"7th lord {sev_lord} Enemy in house {sl.house}")
        if sl.is_combust:
            natal.append(f"7th lord {sev_lord} COMBUST")
        if sl.is_retrograde:
            natal.append(f"7th lord {sev_lord} RETROGRADE")

    # Planets in 7th
    planets_7 = [p for p, s in d1.planets.items() if s.house == 7]
    if planets_7:
        natal.append(f"Planets in 7th: {', '.join(planets_7)}")

    # UL factors
    natal.append(f"UL: {ul.ul_sign} (lord {ul.ul_lord} {ul.ul_lord_dignity})")
    natal.append(f"UL2: {ul.ul2_sign} (lord {ul.ul2_lord} {ul.ul2_lord_dignity})")
    if ul.malefics_in_ul2:
        natal.append(f"Malefics in UL2: {', '.join(ul.malefics_in_ul2)}")
    if ul.benefics_in_ul2:
        natal.append(f"Benefics in UL2: {', '.join(ul.benefics_in_ul2)}")

    # Manglik
    if engine._check_manglik_dosha():
        natal.append("Manglik Dosha")

    # Matching window analysis
    window_info = []
    if matching:
        md = matching.mahadasha_lord
        ad = matching.antardasha_lord

        md_state = d1.planets.get(md)
        ad_state = d1.planets.get(ad)

        # MD factors
        md_factors = []
        if md == sev_lord:
            md_factors.append("IS 7th lord")
        if md == "Venus":
            md_factors.append("IS Venus")
        if md == dk:
            md_factors.append("IS Darakaraka")
        if md == ul.ul_lord:
            md_factors.append("IS UL lord")
        if md == ul.ul2_lord:
            md_factors.append("IS UL2 lord")
        if md_state:
            if md_state.house == 7:
                md_factors.append("IN 7th house")
            if 7 in md_state.aspecting_houses:
                md_factors.append("ASPECTS 7th house")
            if sev_lord in d1.planets:
                if d1.planets[sev_lord].house in md_state.aspecting_houses:
                    md_factors.append(f"ASPECTS 7th lord {sev_lord}")
            if md_state.dignity in ["Exalted", "Own", "Moolatrikona"]:
                md_factors.append(f"{md_state.dignity}")
            if md_state.is_combust:
                md_factors.append("COMBUST")
            if md_state.is_retrograde:
                md_factors.append("RETROGRADE")
            if md_state.house in [2, 7, 11]:
                md_factors.append(f"in house {md_state.house} (marriage house)")

        # AD factors
        ad_factors = []
        if ad == sev_lord:
            ad_factors.append("IS 7th lord")
        if ad == "Venus":
            ad_factors.append("IS Venus")
        if ad == dk:
            ad_factors.append("IS Darakaraka")
        if ad == ul.ul_lord:
            ad_factors.append("IS UL lord")
        if ad == ul.ul2_lord:
            ad_factors.append("IS UL2 lord")
        if ad_state:
            if ad_state.house == 7:
                ad_factors.append("IN 7th house")
            if 7 in ad_state.aspecting_houses:
                ad_factors.append("ASPECTS 7th house")
            if sev_lord in d1.planets:
                if d1.planets[sev_lord].house in ad_state.aspecting_houses:
                    ad_factors.append(f"ASPECTS 7th lord {sev_lord}")
            if ad_state.dignity in ["Exalted", "Own", "Moolatrikona"]:
                ad_factors.append(f"{ad_state.dignity}")
            if ad_state.house in [2, 7, 11]:
                ad_factors.append(f"in house {ad_state.house} (marriage house)")

        window_info.append(f"MD: {md} ({', '.join(md_factors) if md_factors else 'no direct connection'})")
        window_info.append(f"AD: {ad} ({', '.join(ad_factors) if ad_factors else 'no direct connection'})")
        window_info.append(f"Confidence: {matching.confidence.value}")
        window_info.append(f"Indicators: {[i.value for i in matching.indicators]}")

    # WHY it happened - key reason
    why = []
    if matching:
        md = matching.mahadasha_lord
        ad = matching.antardasha_lord
        md_state = d1.planets.get(md)
        ad_state = d1.planets.get(ad)

        # Find the strongest connection
        if md == sev_lord:
            why.append(f"MD {md} is 7th lord — direct marriage trigger")
        elif md == "Venus":
            why.append(f"MD {md} is natural karaka — relationship trigger")
        elif md == ul.ul_lord:
            why.append(f"MD {md} is UL lord — marriage institution activated")
        elif md == dk:
            why.append(f"MD {md} is Darakaraka — spouse significator activated")
        elif md_state and 7 in md_state.aspecting_houses:
            why.append(f"MD {md} aspects 7th house — marriage area activated")
        elif md_state and md_state.house in [2, 7, 11]:
            why.append(f"MD {md} in house {md_state.house} — marriage house occupied")

        if ad == sev_lord:
            why.append(f"AD {ad} is 7th lord — contract handler activated")
        elif ad == "Venus":
            why.append(f"AD {ad} is Venus — relationship energy activated")
        elif ad == ul.ul_lord:
            why.append(f"AD {ad} is UL lord — institution handler activated")
        elif ad == dk:
            why.append(f"AD {ad} is Darakaraka — spouse energy activated")
        elif ad_state and 7 in ad_state.aspecting_houses:
            why.append(f"AD {ad} aspects 7th house")
        elif ad_state and ad_state.house in [2, 7, 11]:
            why.append(f"AD {ad} in house {ad_state.house}")

        if not why:
            why.append(f"Combined scoring (MD={engine._score_dasha_lord(md)}, AD={engine._score_dasha_lord(ad)})")

    return {
        "name": celeb["name"],
        "marriage": celeb["marriage_date"].strftime("%Y-%m-%d"),
        "natal": natal,
        "window": f"{matching.mahadasha_lord}/{matching.antardasha_lord}" if matching else "N/A",
        "window_period": f"{matching.start_date.strftime('%Y-%m')} to {matching.end_date.strftime('%Y-%m')}" if matching else "N/A",
        "window_info": window_info,
        "why": why,
        "total_windows": len(all_windows),
    }


def main():
    print("=" * 100)
    print("DEEP CASE ANALYSIS: WHAT MADE MARRIAGE POSSIBLE IN EACH WINDOW")
    print("=" * 100)

    for celeb in ALL:
        r = full_analysis(celeb)

        print(f"\n{'=' * 100}")
        print(f"  {r['name']} | Marriage: {r['marriage']}")
        print(f"  Matching Window: {r['window']} ({r['window_period']}) | Total Windows: {r['total_windows']}")
        print(f"{'=' * 100}")

        print(f"\n  NATAL CHART FACTORS:")
        for f in r["natal"]:
            print(f"    - {f}")

        print(f"\n  MATCHING WINDOW DETAILS:")
        for f in r["window_info"]:
            print(f"    - {f}")

        print(f"\n  WHY MARRIAGE HAPPENED IN THIS WINDOW:")
        for f in r["why"]:
            print(f"    >>> {f}")

    # Summary: most common "why" factors
    print(f"\n\n{'=' * 100}")
    print("SUMMARY: MOST COMMON MARRIAGE TRIGGERS")
    print(f"{'=' * 100}")

    all_whys = []
    for celeb in ALL:
        r = full_analysis(celeb)
        all_whys.extend(r["why"])

    from collections import Counter
    for factor, count in Counter(all_whys).most_common(15):
        print(f"  {count:2d}x  {factor}")


if __name__ == "__main__":
    main()
