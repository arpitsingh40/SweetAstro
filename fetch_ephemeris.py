"""
Fetch the official Swiss Ephemeris data files (.se1) for full JPL-grade
precision. Files are downloaded from the official Swiss Ephemeris repository
(github.com/aloistr/swisseph) into data/ephe/ and used automatically by the
engine at next start.

Usage:
    python fetch_ephemeris.py
"""

import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe"
FILES = [
    "sepl_18.se1",   # planets, 1800-2399 AD
    "semo_18.se1",   # Moon, 1800-2399 AD
]
EPHE_DIR = Path(__file__).parent / "data" / "ephe"
MIN_SIZE = 100_000  # sanity check against error pages


def main() -> int:
    print("SweetAstro ephemeris fetcher")
    print(f"Target: {EPHE_DIR}")
    EPHE_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name in FILES:
        target = EPHE_DIR / name
        if target.exists() and target.stat().st_size > MIN_SIZE:
            print(f"  {name}: already present ({target.stat().st_size:,} bytes)")
            continue
        url = f"{BASE_URL}/{name}"
        print(f"  {name}: downloading from {url} ...")
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                data = resp.read()
            if len(data) < MIN_SIZE:
                raise ValueError(f"file too small ({len(data)} bytes) — download may have failed")
            target.write_bytes(data)
            print(f"  {name}: saved ({len(data):,} bytes)")
        except Exception as exc:
            failures += 1
            print(f"  {name}: FAILED — {exc}")
    if failures:
        print("\nSome files could not be fetched. The engine will still run with the")
        print("built-in Moshier model (sub-arcsecond), or install pyswisseph if missing.")
        return 1
    print("\nDone. Restart the server to use the new data files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
