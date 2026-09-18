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

print("7th lord:", engine.seventh_lord)
print("7th lord house:", engine.seventh_lord_house)

jup = d1.planets.get("Jupiter")
if jup:
    print("\nJupiter house:", jup.house)
    print("Jupiter aspects houses:", jup.aspecting_houses)
    print("Jupiter aspects 7th?", 7 in jup.aspecting_houses)
    sev_house = engine.seventh_lord_house
    print("Jupiter aspects %s (house %d)? %s" % (engine.seventh_lord, sev_house, sev_house in jup.aspecting_houses))

print("\nJupiter score:", engine._score_dasha_lord("Jupiter"))

all_windows = engine.find_marriage_dashas(birth_dt, datetime(2030,12,31), search_from_birth=True)
marriage_date = datetime(2022,4,14)
found = False
for w in all_windows:
    if w.start_date <= marriage_date <= w.end_date:
        print("\nMatching window: %s/%s (%s to %s)" % (w.mahadasha_lord, w.antardasha_lord, w.start_date.strftime("%Y-%m"), w.end_date.strftime("%Y-%m")))
        print("  Confidence:", w.confidence.value)
        print("  Indicators:", [i.value for i in w.indicators])
        print("  MD score:", engine._score_dasha_lord(w.mahadasha_lord), "AD score:", engine._score_dasha_lord(w.antardasha_lord))
        found = True
        break

if not found:
    print("\nNO MATCHING WINDOW FOUND")
    for w in all_windows:
        dist_start = abs((w.start_date - marriage_date).days)
        dist_end = abs((w.end_date - marriage_date).days)
        if dist_start < 60 or dist_end < 60:
            print("  Close: %s/%s (%s to %s) gap=%d days" % (w.mahadasha_lord, w.antardasha_lord, w.start_date.strftime("%Y-%m"), w.end_date.strftime("%Y-%m"), min(dist_start, dist_end)))
