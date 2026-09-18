import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from datetime import datetime
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine

d1 = calculate_d1_chart(1993,3,15,11,30,0,5.5,18.9667,72.8333)
d9 = calculate_navamsa_chart(d1)
birth_dt = datetime(1993,3,15,11,30,0)
engine = MarriageTimingEngine(d1, d9, birth_dt)

marriage_date = datetime(2022,4,14)

# Get raw merged windows (before extension)
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
moon_lon = engine.d1.planets["Moon"].longitude
timeline = calculate_vimshottari_timeline(birth_dt=birth_dt, moon_lon=moon_lon, max_years=120.0)

raw_windows = []
current = birth_dt
end_date = datetime(2030,12,31)
while current <= end_date:
    state = get_dasha_at_date(timeline, current)
    if state:
        w = engine._check_dasha_for_marriage(state, current)
        if w:
            raw_windows.append(w)
    try:
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    except ValueError:
        current = current.replace(day=28, month=current.month + 1 if current.month < 12 else 1,
                                  year=current.year if current.month < 12 else current.year + 1)

merged = engine._merge_overlapping_windows(raw_windows)
print("Raw windows:", len(raw_windows))
print("Merged windows:", len(merged))

# Check Sun/Jupiter window specifically
for w in merged:
    if w.mahadasha_lord == "Sun" and w.antardasha_lord == "Jupiter":
        print("\nSun/Jupiter window (raw):")
        print("  Start:", w.start_date.strftime("%Y-%m-%d"))
        print("  End:", w.end_date.strftime("%Y-%m-%d"))
        
        from datetime import timedelta
        ext_start = w.start_date - timedelta(days=45)
        ext_end = w.end_date + timedelta(days=45)
        print("  Extended start:", ext_start.strftime("%Y-%m-%d"))
        print("  Extended end:", ext_end.strftime("%Y-%m-%d"))
        print("  Marriage date:", marriage_date.strftime("%Y-%m-%d"))
        print("  In extended?", ext_start <= marriage_date <= ext_end)

# Now check final output
final_windows = engine.find_marriage_dashas(birth_dt, end_date, search_from_birth=True)
print("\nFinal windows:", len(final_windows))
for w in final_windows:
    if w.start_date.year >= 2022 and w.start_date.year <= 2023:
        in_win = w.start_date <= marriage_date <= w.end_date
        marker = " <-- MATCH" if in_win else ""
        print("  %s/%s  %s to %s  conf=%s%s" % (w.mahadasha_lord, w.antardasha_lord, w.start_date.strftime("%Y-%m-%d"), w.end_date.strftime("%Y-%m-%d"), w.confidence.value, marker))
