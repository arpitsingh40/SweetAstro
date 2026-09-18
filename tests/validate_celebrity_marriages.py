"""
Celebrity Marriage Timing Validation
Tests our marriage prediction engine against known celebrity marriages.
"""

from datetime import datetime
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import (
    MarriageTimingEngine, get_marriage_summary
)

CELEBRITIES = [
    {
        "name": "Shah Rukh Khan",
        "birth": {"year": 1965, "month": 11, "day": 2, "hour": 6, "minute": 25, "tz": 5.5},
        "coords": {"lat": 28.6139, "lon": 77.2090},
        "marriage_date": datetime(1991, 10, 25),
        "marriage_age": 25.9,
        "spouse": "Gauri Chibber",
    },
    {
        "name": "Priyanka Chopra",
        "birth": {"year": 1982, "month": 7, "day": 18, "hour": 1, "minute": 30, "tz": 5.5},
        "coords": {"lat": 22.47, "lon": 86.12},
        "marriage_date": datetime(2018, 12, 1),
        "marriage_age": 36.4,
        "spouse": "Nick Jonas",
    },
    {
        "name": "Anushka Sharma",
        "birth": {"year": 1988, "month": 5, "day": 1, "hour": 14, "minute": 0, "tz": 5.5},
        "coords": {"lat": 26.7922, "lon": 82.1998},
        "marriage_date": datetime(2017, 12, 11),
        "marriage_age": 29.6,
        "spouse": "Virat Kohli",
    },
    {
        "name": "Amitabh Bachchan",
        "birth": {"year": 1942, "month": 10, "day": 11, "hour": 15, "minute": 0, "tz": 5.5},
        "coords": {"lat": 25.4358, "lon": 81.8463},
        "marriage_date": datetime(1973, 6, 3),
        "marriage_age": 30.6,
        "spouse": "Jaya Bhaduri",
    },
    {
        "name": "Shilpa Shetty",
        "birth": {"year": 1975, "month": 6, "day": 8, "hour": 20, "minute": 0, "tz": 5.5},
        "coords": {"lat": 12.8714, "lon": 74.8830},
        "marriage_date": datetime(2009, 11, 22),
        "marriage_age": 34.4,
        "spouse": "Raj Kundra",
    },
    {
        "name": "Donald Trump",
        "birth": {"year": 1946, "month": 6, "day": 14, "hour": 10, "minute": 54, "tz": -5.0},
        "coords": {"lat": 40.7061, "lon": -73.8100},
        "marriage_date": datetime(2005, 1, 22),
        "marriage_age": 58.5,
        "spouse": "Melania Knauss",
    },
    {
        "name": "Angelina Jolie",
        "birth": {"year": 1975, "month": 6, "day": 4, "hour": 9, "minute": 9, "tz": -7.0},
        "coords": {"lat": 34.0901, "lon": -118.2900},
        "marriage_date": datetime(1996, 3, 28),
        "marriage_age": 20.8,
        "spouse": "Jonny Lee Miller",
    },
    {
        "name": "Barack Obama",
        "birth": {"year": 1961, "month": 8, "day": 4, "hour": 19, "minute": 24, "tz": -10.0},
        "coords": {"lat": 21.3069, "lon": -157.8583},
        "marriage_date": datetime(1992, 10, 18),
        "marriage_age": 31.2,
        "spouse": "Michelle Robinson",
    },
]


def validate_celebrity(celeb):
    """Run marriage prediction for a celebrity and compare with actual"""
    b = celeb["birth"]
    c = celeb["coords"]
    
    d1 = calculate_d1_chart(
        year=b["year"], month=b["month"], day=b["day"],
        hour=b["hour"], minute=b["minute"], second=0,
        tz_offset_hours=b["tz"],
        lat=c["lat"], lon=c["lon"]
    )
    d9 = calculate_navamsa_chart(d1)
    
    birth_dt = datetime(b["year"], b["month"], b["day"], b["hour"], b["minute"], 0)
    
    engine = MarriageTimingEngine(d1, d9, birth_dt)
    
    search_end = datetime(2030, 12, 31)
    prediction = engine.predict_marriage_timing(birth_dt, search_end)
    
    all_windows = engine.find_marriage_dashas(
        engine.birth_date, search_end, search_from_birth=True
    )
    
    actual_married = False
    matching_window = None
    
    for window in all_windows:
        if window.start_date <= celeb["marriage_date"] <= window.end_date:
            actual_married = True
            matching_window = window
            break
    
    actual_age = celeb["marriage_age"]
    
    return {
        "name": celeb["name"],
        "actual_marriage": celeb["marriage_date"].strftime("%Y-%m"),
        "actual_age": actual_age,
        "spouse": celeb["spouse"],
        "predicted_windows": len(all_windows),
        "in_predicted_window": actual_married,
        "matching_window_dasha": f"{matching_window.mahadasha_lord}/{matching_window.antardasha_lord}" if matching_window else "N/A",
        "matching_window_confidence": matching_window.confidence.value if matching_window else "N/A",
        "matching_window_period": f"{matching_window.start_date.strftime('%Y-%m')} to {matching_window.end_date.strftime('%Y-%m')}" if matching_window else "N/A",
        "promise_strength": prediction.promise.strength.value,
        "navamsa_confirmed": prediction.navamsa.confirmed,
        "overall_strength": prediction.overall_strength.value,
        "7th_lord": prediction.promise.seventh_lord,
        "7th_lord_house": prediction.promise.seventh_lord_house,
        "7th_lord_dignity": prediction.promise.seventh_lord_dignity,
        "venus_dignity": prediction.promise.venus_dignity,
        "delay_factors": prediction.promise.delay_factors[:2] if prediction.promise.delay_factors else [],
        "manglik": prediction.promise.manglik_dosha,
    }


def main():
    print("=" * 80)
    print("CELEBRITY MARRIAGE TIMING VALIDATION")
    print("=" * 80)
    
    results = []
    
    for celeb in CELEBRITIES:
        print(f"\n{'-' * 80}")
        print(f"Processing: {celeb['name']}...")
        result = validate_celebrity(celeb)
        results.append(result)
        
        print(f"\n  {result['name']}")
        print(f"  {'-' * 40}")
        print(f"  Actual Marriage:     {result['actual_marriage']} (age {result['actual_age']}) to {result['spouse']}")
        print(f"  Predicted Windows:   {result['predicted_windows']}")
        print(f"  In Window:           {'YES' if result['in_predicted_window'] else 'NO'}")
        if result['in_predicted_window']:
            print(f"  Window Dasha:        {result['matching_window_dasha']}")
            print(f"  Window Period:       {result['matching_window_period']}")
            print(f"  Window Confidence:   {result['matching_window_confidence']}")
        print(f"  Promise Strength:    {result['promise_strength']}")
        print(f"  Navamsa Confirmed:   {result['navamsa_confirmed']}")
        print(f"  Overall Strength:    {result['overall_strength']}")
        print(f"  7th Lord:            {result['7th_lord']} in house {result['7th_lord_house']} ({result['7th_lord_dignity']})")
        print(f"  Venus:               {result['venus_dignity']}")
        if result['delay_factors']:
            print(f"  Delay Factors:       {', '.join(result['delay_factors'])}")
        if result['manglik']:
            print(f"  Manglik Dosha:       YES")
    
    in_window_count = sum(1 for r in results if r["in_predicted_window"])
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total Celebrities:       {len(results)}")
    print(f"  In Predicted Window:     {in_window_count}/{len(results)} ({in_window_count/len(results)*100:.0f}%)")
    
    print(f"\n{'-' * 80}")
    print("DETAILED WINDOW CHECKS:")
    for r in results:
        status = "HIT" if r["in_predicted_window"] else "MISS"
        print(f"  [{status}] {r['name']:25s} | Actual: {r['actual_marriage']} | "
              f"Windows: {r['predicted_windows']} | Promise: {r['promise_strength']} | "
              f"Dasha: {r['matching_window_dasha']}")


if __name__ == "__main__":
    main()
