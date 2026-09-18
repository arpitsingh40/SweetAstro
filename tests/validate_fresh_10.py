"""
Fresh 10 Celebrity Marriage Timing Validation
"""

from datetime import datetime
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine

FRESH_CELEBRITIES = [
    {
        "name": "Kareena Kapoor",
        "birth": {"year": 1980, "month": 9, "day": 21, "hour": 8, "minute": 39, "tz": 5.5},
        "coords": {"lat": 18.9667, "lon": 72.8333},
        "marriage_date": datetime(2012, 10, 16),
        "marriage_age": 32.0,
        "spouse": "Saif Ali Khan",
    },
    {
        "name": "Katrina Kaif",
        "birth": {"year": 1983, "month": 7, "day": 16, "hour": 6, "minute": 40, "tz": 5.5},
        "coords": {"lat": 22.31, "lon": 114.16},
        "marriage_date": datetime(2021, 12, 9),
        "marriage_age": 38.4,
        "spouse": "Vicky Kaushal",
    },
    {
        "name": "Deepika Padukone",
        "birth": {"year": 1986, "month": 1, "day": 5, "hour": 0, "minute": 5, "tz": 5.5},
        "coords": {"lat": 12.9716, "lon": 77.5946},
        "marriage_date": datetime(2018, 11, 14),
        "marriage_age": 32.8,
        "spouse": "Ranveer Singh",
    },
    {
        "name": "Ranbir Kapoor",
        "birth": {"year": 1982, "month": 9, "day": 28, "hour": 12, "minute": 0, "tz": 5.5},
        "coords": {"lat": 18.9667, "lon": 72.8333},
        "marriage_date": datetime(2022, 4, 14),
        "marriage_age": 39.5,
        "spouse": "Alia Bhatt",
    },
    {
        "name": "Alia Bhatt",
        "birth": {"year": 1993, "month": 3, "day": 15, "hour": 11, "minute": 30, "tz": 5.5},
        "coords": {"lat": 18.9667, "lon": 72.8333},
        "marriage_date": datetime(2022, 4, 14),
        "marriage_age": 29.1,
        "spouse": "Ranbir Kapoor",
    },
    {
        "name": "Vicky Kaushal",
        "birth": {"year": 1988, "month": 5, "day": 16, "hour": 12, "minute": 30, "tz": 5.5},
        "coords": {"lat": 28.6139, "lon": 77.2090},
        "marriage_date": datetime(2021, 12, 9),
        "marriage_age": 33.5,
        "spouse": "Katrina Kaif",
    },
    {
        "name": "Ranveer Singh",
        "birth": {"year": 1985, "month": 7, "day": 6, "hour": 2, "minute": 30, "tz": 5.5},
        "coords": {"lat": 28.6139, "lon": 77.2090},
        "marriage_date": datetime(2018, 11, 14),
        "marriage_age": 33.3,
        "spouse": "Deepika Padukone",
    },
    {
        "name": "Akshay Kumar",
        "birth": {"year": 1967, "month": 9, "day": 9, "hour": 14, "minute": 0, "tz": 5.5},
        "coords": {"lat": 30.9010, "lon": 75.8573},
        "marriage_date": datetime(2001, 1, 17),
        "marriage_age": 33.3,
        "spouse": "Twinkle Khanna",
    },
    {
        "name": "Ajay Devgn",
        "birth": {"year": 1969, "month": 4, "day": 2, "hour": 13, "minute": 32, "tz": 5.5},
        "coords": {"lat": 28.6139, "lon": 77.2090},
        "marriage_date": datetime(1999, 2, 24),
        "marriage_age": 29.9,
        "spouse": "Kajol",
    },
    {
        "name": "Hrithik Roshan",
        "birth": {"year": 1974, "month": 1, "day": 10, "hour": 12, "minute": 0, "tz": 5.5},
        "coords": {"lat": 18.9667, "lon": 72.8333},
        "marriage_date": datetime(2000, 12, 20),
        "marriage_age": 26.9,
        "spouse": "Sussanne Khan",
    },
]


def validate_celebrity(celeb):
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
    all_windows = engine.find_marriage_dashas(engine.birth_date, search_end, search_from_birth=True)
    
    actual_married = False
    matching_window = None
    
    for window in all_windows:
        if window.start_date <= celeb["marriage_date"] <= window.end_date:
            actual_married = True
            matching_window = window
            break
    
    return {
        "name": celeb["name"],
        "actual_marriage": celeb["marriage_date"].strftime("%Y-%m"),
        "actual_age": celeb["marriage_age"],
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
        "manglik": prediction.promise.manglik_dosha,
    }


def main():
    print("=" * 80)
    print("FRESH 10 CELEBRITY MARRIAGE TIMING VALIDATION")
    print("=" * 80)
    
    results = []
    
    for celeb in FRESH_CELEBRITIES:
        print(f"\nProcessing: {celeb['name']}...")
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
        if result['manglik']:
            print(f"  Manglik Dosha:       YES")
    
    in_window_count = sum(1 for r in results if r["in_predicted_window"])
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total Celebrities:       {len(results)}")
    print(f"  In Predicted Window:     {in_window_count}/{len(results)} ({in_window_count/len(results)*100:.0f}%)")
    
    print(f"\n{'-' * 80}")
    print("DETAILED RESULTS:")
    for r in results:
        status = "HIT" if r["in_predicted_window"] else "MISS"
        print(f"  [{status}] {r['name']:25s} | Actual: {r['actual_marriage']} | "
              f"Windows: {r['predicted_windows']} | Promise: {r['promise_strength']} | "
              f"Dasha: {r['matching_window_dasha']}")


if __name__ == "__main__":
    main()
