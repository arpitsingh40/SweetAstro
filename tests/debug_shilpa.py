from datetime import datetime
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.navamsa import calculate_navamsa_chart
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
from SweetAstro.src.prediction.marriage_timing import MarriageTimingEngine
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d1 = calculate_d1_chart(1975, 6, 8, 20, 0, 0, 5.5, 12.8714, 74.8830)
d9 = calculate_navamsa_chart(d1)
birth_dt = datetime(1975, 6, 8, 20, 0, 0)
engine = MarriageTimingEngine(d1, d9, birth_dt)

print("7th Lord:", engine.seventh_lord)
print("7th Lord House:", engine.seventh_lord_house)
print("Darakaraka:", engine._get_darakaraka())

moon_lon = d1.planets['Moon'].longitude
timeline = calculate_vimshottari_timeline(birth_dt, moon_lon, max_years=120.0)

print("\nDasha states around Nov 2009:")
for m in range(1, 13):
    dt = datetime(2009, m, 15)
    state = get_dasha_at_date(timeline, dt)
    if state:
        md_score = engine._score_dasha_lord(state.mahadasha)
        ad_score = engine._score_dasha_lord(state.antardasha)
        pd_score = engine._score_dasha_lord(state.pratyantardasha)
        print(f"  {dt.strftime('%Y-%m')}: MD={state.mahadasha}({md_score}) AD={state.antardasha}({ad_score}) PD={state.pratyantardasha}({pd_score}) Total={md_score+ad_score+pd_score}")

print("\nScore details for key lords:")
for lord in ['Rahu', 'Mars', 'Moon', 'Jupiter', 'Venus', 'Saturn']:
    score = engine._score_dasha_lord(lord)
    print(f"  {lord}: {score}")
    if lord in engine.d1.planets:
        print(f"    House: {engine.d1.planets[lord].house}")
