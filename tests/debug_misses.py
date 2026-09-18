"""
Debug the 2 misses - Anushka Sharma and Shilpa Shetty
"""

from datetime import datetime
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine

def debug_celebrity(name, birth, coords, marriage_date):
    print(f"\n{'=' * 60}")
    print(f"DEBUGGING: {name}")
    print(f"Actual Marriage: {marriage_date.strftime('%Y-%m')}")
    print(f"{'=' * 60}")
    
    b = birth
    c = coords
    
    d1 = calculate_d1_chart(
        year=b["year"], month=b["month"], day=b["day"],
        hour=b["hour"], minute=b["minute"], second=0,
        tz_offset_hours=b["tz"],
        lat=c["lat"], lon=c["lon"]
    )
    d9 = calculate_navamsa_chart(d1)
    birth_dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"], 0)
    
    engine = MarriageTimingEngine(d1, d9, birth_dt)
    
    print(f"\n7th Lord: {engine.seventh_lord}")
    print(f"7th House: {engine.seventh_house_sign}")
    print(f"7th Lord House: {engine.seventh_lord_house}")
    
    from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
    
    moon_lon = d1.planets["Moon"].longitude
    timeline = calculate_vimshottari_timeline(birth_dt, moon_lon, max_years=120.0)
    
    marriage_year = marriage_date.year
    marriage_month = marriage_date.month
    
    print(f"\nDasha periods around {marriage_year}:")
    check_date = datetime(marriage_year, 1, 1)
    state = get_dasha_at_date(timeline, check_date)
    if state:
        print(f"  MD: {state.mahadasha}, AD: {state.antardasha}, PD: {state.pratyantardasha}")
        print(f"  AD Period: {state.ad_period.start_date.strftime('%Y-%m')} to {state.ad_period.end_date.strftime('%Y-%m')}")
    
    check_date2 = datetime(marriage_year, marriage_month, 1)
    state2 = get_dasha_at_date(timeline, check_date2)
    if state2:
        print(f"\n  At marriage month:")
        print(f"  MD: {state2.mahadasha}, AD: {state2.antardasha}, PD: {state2.pratyantardasha}")
    
    all_windows = engine.find_marriage_dashas(birth_dt, datetime(2030, 12, 31), search_from_birth=True)
    
    print(f"\nAll marriage windows ({len(all_windows)}):")
    marriage_windows_around = []
    for w in all_windows:
        if abs((w.start_date - marriage_date).days) < 365 * 3:
            marriage_windows_around.append(w)
            print(f"  {w.start_date.strftime('%Y-%m')} to {w.end_date.strftime('%Y-%m')}: "
                  f"{w.mahadasha_lord}/{w.antardasha_lord} ({w.confidence.value})")
    
    if not marriage_windows_around:
        print("  No windows within 3 years of marriage!")
        print("\n  All windows:")
        for w in all_windows[:10]:
            print(f"    {w.start_date.strftime('%Y-%m')} to {w.end_date.strftime('%Y-%m')}: "
                  f"{w.mahadasha_lord}/{w.antardasha_lord} ({w.confidence.value})")
    
    return all_windows


if __name__ == "__main__":
    debug_celebrity(
        "Anushka Sharma",
        {"year": 1988, "month": 5, "day": 1, "hour": 14, "minute": 0, "tz": 5.5},
        {"lat": 26.7922, "lon": 82.1998},
        datetime(2017, 12, 11)
    )
    
    debug_celebrity(
        "Shilpa Shetty",
        {"year": 1975, "month": 6, "day": 8, "hour": 20, "minute": 0, "tz": 5.5},
        {"lat": 12.8714, "lon": 74.8830},
        datetime(2009, 11, 22)
    )
