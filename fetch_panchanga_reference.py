"""Build the authentic panchanga reference fixture from DrikPanchang (drik ganita).

Values are factual reference outputs (times/names), used solely to verify the
SweetAstro deterministic panchanga engine. Source attribution is embedded.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from html import unescape

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TITHIS = "Pratipada|Prathama|Dwitiya|Tritiya|Chaturthi|Panchami|Shashthi|Saptami|Ashtami|Navami|Dashami|Ekadashi|Dwadashi|Trayodashi|Chaturdashi|Purnima|Amavasya"
NAKS = ("Uttara Phalguni|Purva Phalguni|Uttara Ashadha|Purva Ashadha|Uttara Bhadrapada|Purva Bhadrapada|Mrigashira|"
        "Ashwini|Bharani|Krittika|Rohini|Ardra|Punarvasu|Pushya|Ashlesha|Magha|Hasta|Chitra|Swati|Vishakha|"
        "Anuradha|Jyeshtha|Mula|Shravana|Dhanishtha|Shatabhisha|Revati")
YOGAS = "Vishkambha|Priti|Ayushman|Saubhagya|Shobhana|Atiganda|Sukarman|Dhriti|Shula|Ganda|Vriddhi|Dhruva|Vyaghata|Harshana|Vajra|Siddhi|Vyatipata|Variyana|Parigha|Shiva|Siddha|Sadhya|Shubha|Shukla|Brahma|Indra|Vaidhriti"
KARANAS = "Kimstughna|Bava|Balava|Kaulava|Taitila|Gara(?:ja)?|Vanija|Vishti|Shakuni|Chatushpada|Naga"
SIGNS = "Mesha|Vrishabha|Mithuna|Karka|Simha|Kanya|Tula|Vrishchika|Dhanu|Makara|Kumbha|Meena"

BASE = "https://www.drikpanchang.com/panchang/day-panchang.html"

LOCATIONS = {
    "new_delhi": {"geoname_id": "1261481", "label": "New Delhi, India"},
    "diu": {"geoname_id": "1272502", "label": "Diu, India"},
}

DATES = [
    "12/09/2026",  # Saturday, Shukla Pratipada -> Dwitiya
    "13/09/2026",  # Sunday (Rahu mapping)
    "14/09/2026",  # Monday, Shukla Chaturthi (Ganesha Chaturthi)
    "15/09/2026",  # Tuesday (Rahu mapping)
    "16/09/2026",  # Wednesday (Rahu mapping)
    "11/09/2026",  # Friday, Amavasya -> Shukla Pratipada
    "26/09/2026",  # Saturday, Purnima area
    "05/09/2026",  # Saturday, Krishna paksha
    "01/01/2026",  # Thursday, winter day length
]


def text_of(html: str) -> str:
    html = unescape(html)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def dms_to_decimal(raw: str):
    m = re.match(r"(\d+)\D+(\d+)\D+(\d+)?\D*([NSEW])?", raw.strip())
    if not m:
        return None
    deg, minutes, seconds, hemi = m.group(1), m.group(2), m.group(3) or 0, m.group(4)
    value = float(deg) + float(minutes) / 60.0 + float(seconds) / 3600.0
    if hemi in ("S", "W"):
        value = -value
    return round(value, 6)


def extract(html: str) -> dict:
    t = text_of(html)
    out = {}

    lat_raw = re.search(r"Latitude: ([^A-Za-z]{3,24})", t)
    lon_raw = re.search(r"Longitude: ([^A-Za-z]{3,24})", t)
    elev = re.search(r"Elevation: (\d+) m", t)
    out["latitude"] = dms_to_decimal(lat_raw.group(1)) if lat_raw else None
    out["longitude"] = dms_to_decimal(lon_raw.group(1)) if lon_raw else None
    out["elevation_m"] = int(elev.group(1)) if elev else 0

    m = re.search(r"Sunrise and Moonrise Sunrise (\d{1,2}:\d{2} [AP]M) Sunset (\d{1,2}:\d{2} [AP]M)", t)
    out["sunrise"] = m.group(1) if m else None
    out["sunset"] = m.group(2) if m else None

    out["tithi"] = [list(x) for x in re.findall(rf"({TITHIS}) upto (\d{{1,2}}:\d{{2}} [AP]M)", t)[:3]]
    out["nakshatra"] = [list(x) for x in re.findall(rf"({NAKS}) upto (\d{{1,2}}:\d{{2}} [AP]M)", t)[:4]]
    out["yoga"] = [list(x) for x in re.findall(rf"({YOGAS}) upto (\d{{1,2}}:\d{{2}} [AP]M)", t)[:3]]
    out["karana"] = [list(x) for x in re.findall(rf"({KARANAS}) upto (\d{{1,2}}:\d{{2}} [AP]M)", t)[:5]]

    for label, key in [("Rahu Kalam", "rahu_kalam"), ("Yamaganda", "yamaganda"),
                       ("Gulikai Kalam", "gulika_kalam"), ("Abhijit", "abhijit")]:
        m = re.search(rf"{label} (\d{{1,2}}:\d{{2}} [AP]M) to (\d{{1,2}}:\d{{2}} [AP]M)", t)
        out[key] = [m.group(1), m.group(2)] if m else None

    out["dinamana"] = (re.findall(r"Dinamana (\d{1,2} Hours \d{1,2} Mins \d{1,2} Secs)", t) or [None])[0]
    out["ayanamsha"] = float((re.findall(r"Lahiri Ayanamsha ([\d.]+)", t) or ["0"])[0])
    out["moon_sign"] = (re.findall(rf"Moonsign ({SIGNS})", t) or [None])[0]
    out["sun_sign"] = (re.findall(rf"Sunsign ({SIGNS})", t) or [None])[0]
    out["weekday"] = (re.findall(r"Weekday ([A-Za-z]+)", t) or [None])[0]
    return out


cases = []
for loc_key, loc in LOCATIONS.items():
    for date_str in (DATES if loc_key == "new_delhi" else ["12/09/2026"]):
        url = f"{BASE}?geoname-id={loc['geoname_id']}&date={date_str}"
        try:
            html = httpx.get(url, timeout=40,
                             headers={"User-Agent": "Mozilla/5.0 (SweetAstro reference extraction)"}).text
            data = extract(html)
            d, m, y = date_str.split("/")
            data.update({"location": loc["label"], "location_key": loc_key,
                         "date": f"{y}-{m}-{d}", "source_url": url})
            cases.append(data)
            print(f"OK  {loc['label']:18s} {data['date']}  sunrise={data['sunrise']} "
                  f"tithi={data['tithi'][:1]} rahu={data['rahu_kalam']}")
        except Exception as exc:
            print(f"FAIL {loc['label']} {date_str}: {exc}")
        time.sleep(1.0)

fixture = {
    "source": "DrikPanchang.com — Drik Panchang (drik ganita), Lahiri ayanamsha",
    "source_url": BASE,
    "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "notes": [
        "Times are local civil time at the stated location.",
        "Panchang day starts/ends at sunrise (vara is sunrise-to-sunrise).",
        "Values used only to verify the SweetAstro deterministic panchanga engine.",
    ],
    "cases": cases,
}

out_path = Path(r"C:\Users\Dell -\Documents\Code\SweetAstro\data\reference\panchanga_drikpanchang.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nSaved {len(cases)} cases -> {out_path}")
