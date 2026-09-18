"""
Ayanamsha provider (SweetAstro Core v2 — Step 1).

The sidereal zodiac origin is a *choice*, not a constant: Parashari work uses
Lahiri (Chitra Paksha), KP uses Krishnamurti, Western sidereal work uses
Fagan/Bradley, and so on. Every calculation that consumes a sidereal longitude
must declare which origin it used so results stay traceable.

Accuracy:
- When pyswisseph is available, values come directly from Swiss Ephemeris
  (``swe.get_ayanamsa_ut``) for the requested mode.
- Without it, the built-in fallback is exact for Lahiri and a documented
  constant-offset approximation for the other systems: each system's J2000.0
  base (frozen below from Swiss Ephemeris 2.10) is carried forward with the
  same general-precession polynomial used for Lahiri. This is consistent with
  the fallback's existing "approximate" provenance.

The registry is extensible: append an ``AyanamshaSpec`` to ``AYANAMSHAS`` and
it becomes available by key and aliases everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from . import ephemeris as _ephemeris

# Lahiri value at J2000.0 used by the built-in fallback polynomial
# (23° 51' 25.53"). Keeping it separate makes the Lahiri fallback bit-for-bit
# identical to the legacy ``calculate_lahiri_ayanamsha``.
_LAHIRI_J2000 = 23.857092


@dataclass(frozen=True)
class AyanamshaSpec:
    key: str
    label: str
    # Swiss Ephemeris SIDM_* constant (stable API values, see swephexp.h).
    swe_mode: int
    # Sidereal offset in degrees at J2000.0 (frozen from Swiss Ephemeris 2.10).
    j2000: float
    aliases: Tuple[str, ...] = ()


AYANAMSHAS: Dict[str, AyanamshaSpec] = {
    "lahiri": AyanamshaSpec(
        "lahiri", "Lahiri (Chitra Paksha)", swe_mode=1, j2000=_LAHIRI_J2000,
        aliases=("chitra", "chitrapaksha", "chitra_paksha",
                 "lahiri_chitra_paksha", "drik"),
    ),
    "krishnamurti": AyanamshaSpec(
        "krishnamurti", "Krishnamurti (KP)", swe_mode=5, j2000=23.760240040326494,
        aliases=("kp", "kp_ayanamsha", "krishnamurti_kp", "krishnamurthy"),
    ),
    "raman": AyanamshaSpec(
        "raman", "Raman", swe_mode=3, j2000=22.410791040326500,
    ),
    "fagan_bradley": AyanamshaSpec(
        "fagan_bradley", "Fagan/Bradley", swe_mode=0, j2000=24.740299994434963,
        aliases=("fagan", "bradley", "western_sidereal"),
    ),
    "true_citra": AyanamshaSpec(
        "true_citra", "True Citra", swe_mode=27, j2000=23.840018014902910,
        aliases=("truecitra", "true_chitra"),
    ),
    "yukteshwar": AyanamshaSpec(
        "yukteshwar", "Yukteshwar", swe_mode=7, j2000=22.478803027808170,
        aliases=("yukteshwar_sri",),
    ),
    "ushashashi": AyanamshaSpec(
        "ushashashi", "Usha/Shashi", swe_mode=4, j2000=20.057541027808156,
        aliases=("usha_shashi",),
    ),
}

_ALIASES: Dict[str, str] = {
    alias: key
    for key, spec in AYANAMSHAS.items()
    for alias in spec.aliases
}


def available_ayanamshas() -> Tuple[str, ...]:
    """Registered ayanamsha keys, in registry order."""
    return tuple(AYANAMSHAS)


def normalize_ayanamsha(name: str) -> str:
    """Resolve a user-facing name or alias to a registry key.

    Raises ``ValueError`` for unknown systems (the provider must never guess
    which zodiac origin the caller meant).
    """
    if name is None or not str(name).strip():
        return "lahiri"
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    key = key.replace("(", "").replace(")", "").replace("/", "_")
    key = key.replace("__", "_").strip("_")
    if key in AYANAMSHAS:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    raise ValueError(
        f"Unknown ayanamsha {name!r}; available: {', '.join(available_ayanamshas())}"
    )


def ayanamsha_label(name: str) -> str:
    """Human-readable label for provenance display."""
    return AYANAMSHAS[normalize_ayanamsha(name)].label


def swe_sid_mode(name: str = "lahiri") -> int:
    """Swiss Ephemeris SIDM_* constant for the requested origin.

    Callers that pass this to :mod:`src.core.ephemeris` functions are expected
    to use it only when pyswisseph is available.
    """
    return AYANAMSHAS[normalize_ayanamsha(name)].swe_mode


def calculate_ayanamsha(jd: float, system: str = "lahiri") -> float:
    """Sidereal offset in degrees for `system` at Julian Day `jd`."""
    spec = AYANAMSHAS[normalize_ayanamsha(system)]

    swe = getattr(_ephemeris, "swe", None)
    if _ephemeris.HAS_SWISSEPH and swe is not None:
        swe.set_sid_mode(spec.swe_mode)
        return swe.get_ayanamsa_ut(jd) % 360.0

    # Fallback: constant offset from the Lahiri polynomial. For Lahiri this is
    # exact (spec.j2000 == _LAHIRI_J2000) and bit-identical to legacy behavior.
    delta = _ephemeris.calculate_lahiri_ayanamsha(jd) - _LAHIRI_J2000
    return (spec.j2000 + delta) % 360.0
