"""
Environment check for SweetAstro — reports which optional dependencies are
available and which ephemeris backend will be used for chart calculation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def check():
    modules = ["fastapi", "uvicorn", "pydantic", "swisseph", "flask", "httpx", "dotenv"]
    for m in modules:
        try:
            mod = __import__(m)
            version = getattr(mod, "__version__", getattr(mod, "version", ""))
            print(f"{m}: AVAILABLE {version}")
        except ImportError:
            print(f"{m}: NOT AVAILABLE")

    try:
        from SweetAstro.src.core.ephemeris import (
            ephemeris_engine_name, ephemeris_data_source,
        )
        print(f"\nchart engine: {ephemeris_engine_name()}")
        print(f"data source:  {ephemeris_data_source()}")
        if ephemeris_engine_name() != "swisseph":
            print("WARNING: pyswisseph is missing — charts will be approximate.")
            print("         Install with: pip install pyswisseph")
        elif "se1" not in ephemeris_data_source():
            print("TIP: run `python fetch_ephemeris.py` for official .se1 data files.")
    except Exception as exc:
        print(f"\nchart engine check failed: {exc}")


if __name__ == "__main__":
    check()
