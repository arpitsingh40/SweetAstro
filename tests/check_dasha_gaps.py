from datetime import datetime
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d1 = calculate_d1_chart(1975, 6, 8, 20, 0, 0, 5.5, 12.8714, 74.8830)
birth_dt = datetime(1975, 6, 8, 20, 0, 0)
moon_lon = d1.planets['Moon'].longitude
timeline = calculate_vimshottari_timeline(birth_dt, moon_lon, max_years=120.0)

rahu_periods = [p for p in timeline if p.lord == 'Rahu' and p.level == 'AD' and p.parent_md == 'Rahu']
print('Rahu/Rahu AD periods:')
for p in rahu_periods:
    print(f'  {p.start_date.strftime("%Y-%m-%d")} to {p.end_date.strftime("%Y-%m-%d")} ({p.duration_days:.0f} days)')

print()
print('Dasha at key dates in 2009:')
for m in [1, 4, 7, 10, 11, 12]:
    dt = datetime(2009, m, 15)
    state = get_dasha_at_date(timeline, dt)
    if state:
        print(f'  {dt.strftime("%Y-%m")}: MD={state.mahadasha}, AD={state.antardasha}, PD={state.pratyantardasha}')
    else:
        print(f'  {dt.strftime("%Y-%m")}: NO STATE')
