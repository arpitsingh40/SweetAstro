"""
Kundli Milan (marriage compatibility) — Ashtakoota core.

Classical 8-kuta / 36-point scheme on the two Moons:

  Varna (1), Vashya (2), Tara (3), Yoni (4), Graha Maitri (5),
  Gana (6), Bhakoot (7), Nadi (8)

Plus Mangal Dosha (Manglik) with the common cancellation checks.

Conventions are documented per-kuta. Where traditions differ, the most
commonly implemented convention is used and marked in the detail text.
This is an interpretive traditional assessment, not a guarantee — see
docs/accuracy_protocol.md.

Sources: classical Ashtakoota tables (Muhurta Chintamani / Jyotisha
traditions) as catalogued in docs/knowledge/02_modern_specialized.md (77).
"""

from dataclasses import dataclass, field
from typing import Dict, List

from .chart import D1Chart
from .constants import INDEX_TO_SIGN, NAKSHATRAS, PERMANENT_FRIENDSHIPS, SIGN_LORDS
from .nakshatra import NAKSHATRA_DETAILS

MAX_TOTAL = 36.0

# ---------------------------------------------------------------------------
# Varna (sign -> varna)
# ---------------------------------------------------------------------------
VARNA_BY_SIGN = [
    "Kshatriya", "Vaishya", "Shudra", "Brahmin",
    "Kshatriya", "Vaishya", "Shudra", "Brahmin",
    "Kshatriya", "Vaishya", "Shudra", "Brahmin",
]
_VARNA_RANK = {"Shudra": 1, "Vaishya": 2, "Kshatriya": 3, "Brahmin": 4}

# ---------------------------------------------------------------------------
# Vashya (sign -> group). Whole-sign simplification for Sagittarius/Capricorn
# (texts split their halves between groups).
# ---------------------------------------------------------------------------
VASHYA_BY_SIGN = [
    "Chatushpada", "Chatushpada", "Manava", "Jalachara",
    "Vanachara", "Manava", "Manava", "Keeta",
    "Chatushpada", "Jalachara", "Manava", "Jalachara",
]
# Symmetric compatibility values (commonly implemented convention).
_VASHYA_SCORES = {
    ("Chatushpada", "Chatushpada"): 2.0,
    ("Chatushpada", "Manava"): 2.0,
    ("Chatushpada", "Jalachara"): 1.0,
    ("Chatushpada", "Vanachara"): 0.0,
    ("Chatushpada", "Keeta"): 1.0,
    ("Manava", "Manava"): 2.0,
    ("Manava", "Jalachara"): 1.0,
    ("Manava", "Vanachara"): 0.0,
    ("Manava", "Keeta"): 1.0,
    ("Jalachara", "Jalachara"): 2.0,
    ("Jalachara", "Vanachara"): 0.0,
    ("Jalachara", "Keeta"): 1.0,
    ("Vanachara", "Vanachara"): 2.0,
    ("Vanachara", "Keeta"): 0.0,
    ("Keeta", "Keeta"): 2.0,
}

_GOOD_TARAS = {2, 4, 6, 8, 9}  # Sampat, Kshema, Sadhana, Mitra, Parama Mitra
_TARA_NAMES = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyari",
               "Sadhana", "Vadha", "Mitra", "Parama Mitra"]

# Yoni "enemy" pairs (classical): 0 points.
_YONI_ENEMIES = {
    frozenset(("Horse", "Buffalo")),
    frozenset(("Elephant", "Lion")),
    frozenset(("Sheep", "Monkey")),
    frozenset(("Serpent", "Mongoose")),
    frozenset(("Dog", "Deer")),
    frozenset(("Cat", "Rat")),
    frozenset(("Cow", "Tiger")),
}

# Nadi by nakshatra index (0-based) — Adi / Madhya / Antya, 9 each.
NADI_NAMES = ["Adi", "Madhya", "Antya"]
_NADI_BY_NAKSHATRA = [
    "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi", "Adi", "Madhya", "Antya",
    "Antya", "Madhya", "Adi", "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi",
    "Adi", "Madhya", "Antya", "Antya", "Madhya", "Adi", "Adi", "Madhya", "Antya",
]

_FRIEND = "Friend"
_NEUTRAL = "Neutral"
_ENEMY = "Enemy"

_GRAHA_MAITRI_SCORES = {
    (_FRIEND, _FRIEND): 5.0,
    (_FRIEND, _NEUTRAL): 4.0,
    (_NEUTRAL, _NEUTRAL): 3.0,
    (_FRIEND, _ENEMY): 1.0,
    (_NEUTRAL, _ENEMY): 0.5,
    (_ENEMY, _ENEMY): 0.0,
}


@dataclass
class KutaScore:
    kuta: str
    points: float
    max_points: float
    detail: str


@dataclass
class MangalReading:
    active: bool
    houses: Dict[str, int]
    cancellations: List[str]
    note: str


@dataclass
class MatchResult:
    total: float
    max_total: float
    kutas: List[KutaScore]
    verdict: str
    mangal_a: MangalReading
    mangal_b: MangalReading
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "max_total": self.max_total,
            "verdict": self.verdict,
            "kutas": [k.__dict__ for k in self.kutas],
            "mangal_a": self.mangal_a.__dict__,
            "mangal_b": self.mangal_b.__dict__,
            "notes": self.notes,
        }


def _relation(lord_a: str, lord_b: str) -> str:
    if lord_a == lord_b:
        return _FRIEND
    data = PERMANENT_FRIENDSHIPS.get(lord_a, {})
    if lord_b in data.get("friends", []):
        return _FRIEND
    if lord_b in data.get("enemies", []):
        return _ENEMY
    return _NEUTRAL


def _pair_score(table: Dict, a: str, b: str) -> float:
    return table.get((a, b), table.get((b, a), 0.0))


def _varna(moon_a: int, moon_b: int) -> KutaScore:
    varna_a = VARNA_BY_SIGN[moon_a - 1]
    varna_b = VARNA_BY_SIGN[moon_b - 1]
    points = 1.0 if _VARNA_RANK[varna_b] >= _VARNA_RANK[varna_a] else 0.0
    return KutaScore("Varna", points, 1.0,
                     f"bride {varna_a}, groom {varna_b} "
                     f"(groom's varna should be equal or higher; directional convention)")


def _vashya(moon_a: int, moon_b: int) -> KutaScore:
    group_a = VASHYA_BY_SIGN[moon_a - 1]
    group_b = VASHYA_BY_SIGN[moon_b - 1]
    points = _pair_score(_VASHYA_SCORES, group_a, group_b)
    return KutaScore("Vashya", points, 2.0,
                     f"bride {group_a}, groom {group_b} (whole-sign grouping; split-sign traditions differ)")


def _tara(nak_a: int, nak_b: int) -> KutaScore:
    count_ab = ((nak_b - nak_a) % 27) + 1
    count_ba = ((nak_a - nak_b) % 27) + 1
    tara_ab = ((count_ab - 1) % 9) + 1
    tara_ba = ((count_ba - 1) % 9) + 1
    good_ab = tara_ab in _GOOD_TARAS
    good_ba = tara_ba in _GOOD_TARAS
    if good_ab and good_ba:
        points = 3.0
    elif good_ab or good_ba:
        points = 1.5
    else:
        points = 0.0
    return KutaScore("Tara", points, 3.0,
                     f"from bride: {_TARA_NAMES[tara_ab - 1]} ({'good' if good_ab else 'avoid'}); "
                     f"from groom: {_TARA_NAMES[tara_ba - 1]} ({'good' if good_ba else 'avoid'})")


def _yoni(nak_a: int, nak_b: int) -> KutaScore:
    yoni_a = NAKSHATRA_DETAILS[_nak_name(nak_a)].yoni
    yoni_b = NAKSHATRA_DETAILS[_nak_name(nak_b)].yoni
    pair = frozenset((yoni_a, yoni_b))
    if yoni_a == yoni_b:
        points = 4.0
    elif pair in _YONI_ENEMIES:
        points = 0.0
    else:
        points = 2.0
    return KutaScore("Yoni", points, 4.0,
                     f"bride {yoni_a}, groom {yoni_b} "
                     f"(same 4, classical enemy pair 0, other pairs 2 in this implementation)")


def _graha_maitri(moon_a: int, moon_b: int) -> KutaScore:
    lord_a = SIGN_LORDS[INDEX_TO_SIGN[moon_a]]
    lord_b = SIGN_LORDS[INDEX_TO_SIGN[moon_b]]
    rel_a = _relation(lord_a, lord_b)
    rel_b = _relation(lord_b, lord_a)
    points = _pair_score(_GRAHA_MAITRI_SCORES, rel_a, rel_b)
    return KutaScore("Graha Maitri", points, 5.0,
                     f"Moon lords {lord_a} and {lord_b} are {rel_a.lower()}/{rel_b.lower()}")


def _gana(nak_a: int, nak_b: int) -> KutaScore:
    gana_a = NAKSHATRA_DETAILS[_nak_name(nak_a)].gana
    gana_b = NAKSHATRA_DETAILS[_nak_name(nak_b)].gana
    if gana_a == gana_b:
        points = 6.0
    elif {gana_a, gana_b} == {"Deva", "Manushya"}:
        points = 5.0
    else:
        points = 0.0
    return KutaScore("Gana", points, 6.0,
                     f"bride {gana_a}, groom {gana_b} "
                     f"(same 6, Deva-Manushya 5, any Rakshasa pairing 0 in this implementation)")


def _bhakoot(moon_a: int, moon_b: int) -> KutaScore:
    distance = ((moon_b - moon_a) % 12) + 1
    if distance in (2, 5, 6, 8, 9, 12):
        points = 0.0
        reason = "Bhakoot dosha (2/12, 6/8 or 5/9 Moon-sign axis)"
    else:
        points = 7.0
        reason = "favourable Moon-sign axis"
    return KutaScore("Bhakoot", points, 7.0,
                     f"Moon signs at distance {distance} — {reason}")


def _nadi(nak_a: int, nak_b: int) -> KutaScore:
    nadi_a = _NADI_BY_NAKSHATRA[nak_a]
    nadi_b = _NADI_BY_NAKSHATRA[nak_b]
    points = 8.0 if nadi_a != nadi_b else 0.0
    return KutaScore("Nadi", points, 8.0,
                     f"bride {nadi_a} nadi, groom {nadi_b} nadi "
                     f"({'different' if nadi_a != nadi_b else 'same — Nadi dosha'})")


def _nak_name(index: int) -> str:
    return NAKSHATRAS[index]["name"]


def mangal_dosha(d1: D1Chart) -> MangalReading:
    """Manglik check: Mars in 1/2/4/7/8/12 from Lagna or Moon, with basic cancellations."""
    mars = d1.planets["Mars"]
    houses = {
        "from_lagna": ((mars.sign_index - d1.ascendant_sign_index) % 12) + 1,
        "from_moon": ((mars.sign_index - d1.planets["Moon"].sign_index) % 12) + 1,
    }
    active = any(h in (1, 2, 4, 7, 8, 12) for h in houses.values())
    cancellations: List[str] = []
    if mars.dignity in ("Exalted", "Moolatrikona", "Own"):
        cancellations.append(f"Mars is {mars.dignity} (dignity reduces the dosha)")
    if "Jupiter" in d1.houses[mars.house].occupants:
        cancellations.append("Jupiter is conjunct Mars (common cancellation)")
    if "Moon" in d1.houses[mars.house].occupants:
        cancellations.append("Moon is conjunct Mars (common cancellation)")
    note = ("Mars in 1/2/4/7/8/12 from lagna or Moon — traditionally flagged for matching "
            "(many schools apply the listed cancellations; verdicts differ).")
    if not active:
        note = "No Mangal dosha placement in this chart."
    return MangalReading(active=active, houses=houses, cancellations=cancellations, note=note)


def match_charts(d1_a: D1Chart, d1_b: D1Chart, label_a: str = "bride",
                 label_b: str = "groom") -> MatchResult:
    """Ashtakoota between two charts. Labels are positional; swaps are the caller's choice."""
    nak_a = _nakshatra_index(d1_a)
    nak_b = _nakshatra_index(d1_b)
    moon_a = d1_a.planets["Moon"].sign_index
    moon_b = d1_b.planets["Moon"].sign_index

    kutas = [
        _varna(moon_a, moon_b),
        _vashya(moon_a, moon_b),
        _tara(nak_a, nak_b),
        _yoni(nak_a, nak_b),
        _graha_maitri(moon_a, moon_b),
        _gana(nak_a, nak_b),
        _bhakoot(moon_a, moon_b),
        _nadi(nak_a, nak_b),
    ]
    total = round(sum(k.points for k in kutas), 2)

    if total >= 28:
        verdict = ("Excellent match by the traditional 36-point scale — multiple independent "
                   "kutas agree. This is an interpretive traditional assessment, not a guarantee.")
    elif total >= 24:
        verdict = ("Good match by the traditional 36-point scale — most kutas agree, with some "
                   "points to understand. Interpretive guidance, not a guarantee.")
    elif total >= 18:
        verdict = ("Average match by the traditional 36-point scale — the strong and weak kutas "
                   "should be weighed together with the birth charts themselves.")
    else:
        verdict = ("Below the traditional comfort zone on the 36-point scale — this does not "
                   "forbid a marriage; classical practice looks for compensating factors in the "
                   "full charts, which this score alone cannot do.")

    notes = [
        f"Scored {label_a} vs {label_b} using the 8 classical kutas (max 36).",
        "Conventions differ between traditions (Vashya splitting, Gana/Rakshasa handling, "
        "Yoni intermediate values); details are shown per kuta for transparency.",
        "Mangal dosha uses lagna and Moon references with common cancellations only.",
        "A compatibility score never overrides the two individuals' judgement or professional advice.",
    ]

    return MatchResult(
        total=total, max_total=MAX_TOTAL, kutas=kutas, verdict=verdict,
        mangal_a=mangal_dosha(d1_a), mangal_b=mangal_dosha(d1_b), notes=notes,
    )


def _nakshatra_index(d1: D1Chart) -> int:
    """0-based nakshatra index of the natal Moon."""
    name = d1.planets["Moon"].nakshatra
    for idx, entry in enumerate(NAKSHATRAS):
        if entry["name"] == name:
            return idx
    raise ValueError(f"Unknown nakshatra: {name!r}")


def render_match_markdown(result: MatchResult, label_a: str = "Person A",
                          label_b: str = "Person B") -> str:
    lines = [
        f"# Kundli Milan — {label_a} × {label_b}",
        "",
        f"**Ashtakoota total: {result.total} / {int(result.max_total)}**",
        "",
        result.verdict,
        "",
        "## Kuta breakdown",
    ]
    for k in result.kutas:
        lines.append(f"- **{k.kuta}: {k.points:g}/{k.max_points:g}** — {k.detail}")
    lines.append("")
    lines.append("## Mangal dosha")
    for label, reading in ((label_a, result.mangal_a), (label_b, result.mangal_b)):
        status = "flagged" if reading.active else "not indicated"
        lines.append(f"- **{label}: {status}** — {reading.note}")
        for c in reading.cancellations:
            lines.append(f"  - cancellation: {c}")
    lines.append("")
    for note in result.notes:
        lines.append(f"> {note}")
    lines.append("")
    lines.append("_Traditional interpretive assessment; not established causation and not a "
                 "guarantee. It does not replace the individuals' own judgement or professional advice._")
    return "\n".join(lines)
