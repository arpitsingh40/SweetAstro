from datetime import datetime
from SweetAstro.src.core.chart import calculate_d1_chart
from SweetAstro.src.core.dasha import calculate_vimshottari_timeline, get_dasha_at_date
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d1 = calculate_d1_chart(1975, 6, 8, 20, 0, 0, 5.5, 12.8714, 74.8830)
birth_dt = datetime(1975, 6, 8, 20, 0, 0)
moon_lon = d1.planets['Moon'].longitude
timeline = calculate_vimshottari_timeline(birth_dt, moon_lon, max_years=120.0)

print('All Rahu MD AD periods:')
rahu_periods = [p for p in timeline if p.level == 'AD' and p.parent_md == 'Rahu']
for p in rahu_periods:
    print(f'  Rahu/{p.lord}: {p.start_date.strftime("%Y-%m-%d")} to {p.end_date.strftime("%Y-%m-%d")} ({p.duration_days:.0f} days)')

print()
print('Checking Rahu/Mars specifically:')
mars_periods = [p for p in timeline if p.level == 'AD' and p.parent_md == 'Rahu' and p.lord == 'Mars']
for p in mars_periods:
    print(f'  Start: {p.start_date}, End: {p.end_date}')

print()
print('State at Nov 2009:')
dt = datetime(2009, 11, 1)
state = get_dasha_at_date(timeline, dt)
if state:
    print(f'  AD Period: {state.ad_period.start_date} to {state.ad_period.end_date}')
    print(f'  MD: {state.mahadasha}, AD: {state.antardasha}')
