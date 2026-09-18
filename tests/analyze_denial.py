"""
Denial Analysis: Why strong dasha periods FAIL to produce marriage.
Marriage = responsibility + legal contract + public event.
We need to check NOT just favorability, but DENIAL factors.
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


def check_denial_factors(engine):
    """Check all known marriage denial yogas in the birth chart."""
    d1 = engine.d1
    d9 = engine.d9
    sev_lord = engine.seventh_lord
    sev_house = 7

    denials = []

    # 1. 7th lord combust - legal bond denied
    if sev_lord in d1.planets and d1.planets[sev_lord].is_combust:
        denials.append(("7th lord combust", "Legal bond weakened"))

    # 2. Venus combust - natural karaka of marriage denied
    if "Venus" in d1.planets and d1.planets["Venus"].is_combust:
        denials.append(("Venus combust", "Marriage significator weakened"))

    # 3. 7th lord retrograde - delays/denies the contract
    if sev_lord in d1.planets and d1.planets[sev_lord].is_retrograde:
        denials.append(("7th lord retrograde", "Contract delays"))

    # 4. Venus retrograde - delays relationship
    if "Venus" in d1.planets and d1.planets["Venus"].is_retrograde:
        denials.append(("Venus retrograde", "Relationship delays"))

    # 5. 7th lord in 6/8/12 - dusthana affliction
    if sev_lord in d1.planets:
        sev_house = d1.planets[sev_lord].house
        if sev_house in [6, 12]:
            denials.append((f"7th lord in {sev_house}th", "Marriage denied/delayed"))
        elif sev_house == 8:
            denials.append(("7th lord in 8th", "Marriage transforms/delays"))

    # 6. Multiple malefics in 7th - marriage suffers
    malefics_7th = [p for p in ["Saturn", "Mars", "Rahu", "Ketu", "Sun"]
                    if p in d1.planets and d1.planets[p].house == 7]
    if len(malefics_7th) >= 2:
        denials.append((f"{len(malefics_7th)} malefics in 7th", "Marriage under severe stress"))

    # 7. Saturn in 7th - delays AND restricts
    if "Saturn" in d1.planets and d1.planets["Saturn"].house == 7:
        denials.append(("Saturn in 7th", "Marriage severely delayed"))

    # 8. Rahu/Ketu axis on 7th - karmic disruption
    if ("Rahu" in d1.planets and d1.planets["Rahu"].house == 7) or \
       ("Ketu" in d1.planets and d1.planets["Ketu"].house == 7):
        denials.append(("Rahu/Ketu on 7th", "Karmic marriage disruption"))

    # 9. 7th lord debilitated - weak contract handler
    if sev_lord in d1.planets and d1.planets[sev_lord].dignity == "Debilitated":
        denials.append(("7th lord debilitated", "Weak marriage promise"))

    # 10. Venus debilitated - weak relationship significator
    if "Venus" in d1.planets and d1.planets["Venus"].dignity == "Debilitated":
        denials.append(("Venus debilitated", "Weak relationship promise"))

    # 11. 7th lord in enemy sign - hostile to marriage
    if sev_lord in d1.planets and d1.planets[sev_lord].dignity == "Enemy":
        denials.append(("7th lord in enemy sign", "Marriage challenged"))

    # 12. Venus in enemy sign - hostile to relationships
    if "Venus" in d1.planets and d1.planets["Venus"].dignity == "Enemy":
        denials.append(("Venus in enemy sign", "Relationship challenged"))

    # 13. Badhaka - 11th lord from UL aspects UL or UL lord
    if engine.upapada.ul_lord in d1.planets:
        ul_lord_house = d1.planets[engine.upapada.ul_lord].house
        # 11th from UL
        badhaka_house = (engine.upapada.ul_house_from_lagna + 10 - 1) % 12 + 1
        badhaka_lord = d1.houses[badhaka_house].lord
        if badhaka_lord in d1.planets:
            aspects = d1.planets[badhaka_lord].aspecting_houses
            if engine.upapada.ul_house_from_lagna in aspects:
                denials.append(("Badhaka aspects UL", "Obstruction to marriage"))

    # 14. UL lord combust - marriage institution weakened
    if engine.upapada.ul_lord in d1.planets and d1.planets[engine.upapada.ul_lord].is_combust:
        denials.append(("UL lord combust", "Marriage institution weakened"))

    # 15. Venus between Sun and Moon (combust range) - classical denial
    if "Venus" in d1.planets and "Sun" in d1.planets and "Moon" in d1.planets:
        ven_lon = d1.planets["Venus"].longitude
        sun_lon = d1.planets["Sun"].longitude
        moon_lon = d1.planets["Moon"].longitude
        # Check if Venus is between Sun and Moon (within 15 degrees)
        if abs(ven_lon - sun_lon) < 15 and abs(ven_lon - moon_lon) < 15:
            denials.append(("Venus between Sun-Moon", "Classical marriage denial"))

    # 16. 7th house has no planets AND no benefic aspects - empty marriage house
    planets_7th = [p for p, state in d1.planets.items() if state.house == 7]
    benefic_aspects_7th = [p for p, state in d1.planets.items()
                          if 7 in state.aspecting_houses and p in ["Jupiter", "Venus", "Mercury", "Moon"]]
    if not planets_7th and not benefic_aspects_7th:
        denials.append(("Empty 7th house, no benefic aspects", "No marriage support"))

    # 17. Jupiter retrograde - delays dharma/responsibility
    if "Jupiter" in d1.planets and d1.planets["Jupiter"].is_retrograde:
        denials.append(("Jupiter retrograde", "Dharma/responsibility delays"))

    # 18. All natural benefics retrograde - overall weakness
    retro_benefics = [p for p in ["Jupiter", "Venus", "Mercury", "Moon"]
                     if p in d1.planets and d1.planets[p].is_retrograde]
    if len(retro_benefics) >= 2:
        denials.append((f"{len(retro_benefics)} benefics retrograde", "Overall weakness"))

    return denials


def analyze_window_denials(engine, window, denial_factors):
    """Check if a specific dasha window is blocked by denial factors."""
    md = window.mahadasha_lord
    ad = window.antardasha_lord
    d1 = engine.d1

    blocked = False
    block_reasons = []

    # If 7th lord is combust, dasha of combust lord can't give marriage
    if md == engine.seventh_lord:
        if md in d1.planets and d1.planets[md].is_combust:
            blocked = True
            block_reasons.append(f"MD {md} is combust")

    # If Venus is combusted, Venus dasha can't give marriage
    if md == "Venus":
        if "Venus" in d1.planets and d1.planets["Venus"].is_combust:
            blocked = True
            block_reasons.append("MD Venus is combust")

    # If 7th lord is debilitated, its dasha gives weak results
    if md == engine.seventh_lord:
        if md in d1.planets and d1.planets[md].dignity == "Debilitated":
            blocked = True
            block_reasons.append(f"MD {md} is debilitated")

    # If dasha lord is in 6/12 from 7th lord - obstruction
    if md in d1.planets and engine.seventh_lord in d1.planets:
        md_house = d1.planets[md].house
        sev_house = d1.planets[engine.seventh_lord].house
        diff = abs(md_house - sev_house)
        if diff in [5, 7]:  # 6th or 8th from each other
            blocked = True
            block_reasons.append(f"MD {md} is 6th/8th from 7th lord")

    return blocked, block_reasons


def main():
    print("=" * 110)
    print("DENIAL ANALYSIS: Why strong dasha periods FAIL to produce marriage")
    print("=" * 110)

    for celeb in ALL_CELEBRITIES[:6]:  # Check first 6
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

        denials = check_denial_factors(engine)
        all_windows = engine.find_marriage_dashas(birth_dt, datetime(2030, 12, 31), search_from_birth=True)

        print(f"\n{'=' * 110}")
        print(f"{celeb['name']} | 7th Lord: {engine.seventh_lord} | UL Lord: {engine.upapada.ul_lord}")
        print(f"  Marriage: {celeb['marriage_date'].strftime('%Y-%m-%d')} | Windows: {len(all_windows)}")
        print(f"{'=' * 110}")

        if denials:
            print(f"  DENIAL FACTORS ({len(denials)}):")
            for factor, effect in denials:
                print(f"    - {factor}: {effect}")
        else:
            print(f"  No denial factors found")

        # Check if matching window is blocked
        matching = None
        for w in all_windows:
            if w.start_date <= celeb["marriage_date"] <= w.end_date:
                matching = w
                break

        if matching:
            blocked, reasons = analyze_window_denials(engine, matching, denials)
            print(f"\n  MATCHING WINDOW: {matching.mahadasha_lord}/{matching.antardasha_lord}")
            print(f"  Blocked by denials: {blocked}")
            if reasons:
                for r in reasons:
                    print(f"    - {r}")

        # Show which denials would block non-matching windows
        print(f"\n  WINDOW DENIAL CHECK:")
        for w in all_windows[:5]:
            blocked, reasons = analyze_window_denials(engine, w, denials)
            marker = " <-- MATCH" if w == matching else ""
            block_str = f" BLOCKED: {reasons}" if blocked else ""
            print(f"    {w.mahadasha_lord}/{w.antardasha_lord} ({w.start_date.strftime('%Y-%m')} to {w.end_date.strftime('%Y-%m')}){marker}{block_str}")


if __name__ == "__main__":
    main()
