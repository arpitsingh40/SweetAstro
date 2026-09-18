"""
Remedy Catalog — Consumer Engine Sec 9.

Categories: alignment | mantra | ritual | donation | lal_kitab | reference.
Every remedy: chart-specific reason, optional, proportionate, safe.
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional

RemedyKind = Literal["alignment", "mantra", "ritual", "donation", "lal_kitab", "conduct", "reference"]
Tradition = Literal["Parashari", "Lal Kitab", "traditional remedy literature", "modern conduct"]


@dataclass
class Remedy:
    kind: RemedyKind
    tradition: Tradition
    title: str
    practice: str
    planetary_purpose: str
    chart_reason: str  # why for THIS chart (never generic)
    frequency: str
    duration: str
    safety_note: str
    suitability: Literal["Low", "Moderate", "High"]
    is_primary: bool = False


PLANET_WEEKDAY = {
    "Sun": "Sunday", "Moon": "Monday", "Mars": "Tuesday", "Mercury": "Wednesday",
    "Jupiter": "Thursday", "Venus": "Friday", "Saturn": "Saturday",
    "Rahu": "Saturday", "Ketu": "Tuesday",
}

PLANET_DONATIONS = {
    "Sun": "food donation on Sunday; support for eye-health / community kitchens",
    "Moon": "milk/food or educational support on Monday; care for mother/elderly",
    "Mars": "support for children / sports / blood-donation camps (voluntary) on Tuesday",
    "Mercury": "educational support, books for students on Wednesday",
    "Jupiter": "educational support, teacher respect, food for scholars on Thursday",
    "Venus": "clothing/essentials for girls/women's welfare, cleanliness drives on Friday",
    "Saturn": "food/service for elderly, labourers, disabled; medical/humanitarian aid on Saturday",
    "Rahu": "service without display; support for marginalised; de-addiction awareness (no intoxicants)",
    "Ketu": "animal welfare (esp. dogs per tradition — only kindness, never harm), meditation service",
}

PLANET_ALIGNMENT = {
    "Sun": "punctuality, integrity in commitments, respect for father/mentors, morning discipline",
    "Moon": "sleep hygiene, emotional steadiness, care for mother, hydration/routine",
    "Mars": "exercise discipline, courage without aggression, completing pending tasks",
    "Mercury": "study habit, clear speech, keeping accounts/notes, honesty in communication",
    "Jupiter": "learning, ethical conduct, gratitude to teachers, moderation in food/advice",
    "Venus": "cleanliness, respectful partnership conduct, arts/appreciation in balance",
    "Saturn": "perseverance, service to elderly/workers, punctuality, owning responsibilities",
    "Rahu": "transparent rules, digital discipline, no shortcuts/speculation; structured experimentation",
    "Ketu": "focused deep work, meditation, minimalism, finishing what you start",
}


def alignment_remedy(planet: str, chart_reason: str, suitability: str = "High") -> Remedy:
    wd = PLANET_WEEKDAY.get(planet, "relevant weekday")
    return Remedy(
        kind="alignment", tradition="Parashari",
        title=f"{planet} alignment conduct",
        practice=f"{PLANET_ALIGNMENT.get(planet, 'balanced conduct')} (especially {wd}).",
        planetary_purpose=f"Encourage constructive expression of {planet}.",
        chart_reason=chart_reason, frequency="Daily, continuous",
        duration="Ongoing; review after one Antardasha change",
        safety_note="Safe behavioural practice; no cost or risk.",
        suitability=suitability, is_primary=True,
    )


def mantra_remedy(planet: str, chart_reason: str, suitability: str = "Moderate") -> Remedy:
    mantras = {
        "Sun": "Om Suryaya Namah (devotional/meditative, 11x)",
        "Moon": "Om Chandraya Namah (11x, calm sitting)",
        "Mars": "Om Mangalaya Namah (11x)",
        "Mercury": "Om Budhaya Namah (11x)",
        "Jupiter": "Om Gurave Namah (11x)",
        "Venus": "Om Shukraya Namah (11x)",
        "Saturn": "Om Sham Shanicharaya Namah (11x, steady pace)",
        "Rahu": "Om Rahave Namah (11x, pacifying intent)",
        "Ketu": "Om Ketave Namah (11x, pacifying intent)",
    }
    return Remedy(
        kind="mantra", tradition="Parashari",
        title=f"Optional {planet} mantra",
        practice=f"{mantras.get(planet, 'Simple planetary prayer')} — personal faith varies; pronunciation need not be perfect.",
        planetary_purpose=f"Devotional/meditative support for {planet} themes; not a guaranteed cure.",
        chart_reason=chart_reason, frequency=f"Weekly on {PLANET_WEEKDAY.get(planet, 'weekday')} or daily briefly",
        duration="4–8 weeks, then review",
        safety_note="Stop if it causes anxiety/obsession; faith-based, optional.",
        suitability=suitability,
    )


def donation_remedy(planet: str, chart_reason: str, suitability: str = "Moderate") -> Remedy:
    return Remedy(
        kind="donation", tradition="Parashari",
        title=f"{planet}-linked donation/service",
        practice=f"{PLANET_DONATIONS.get(planet, 'Food/educational support')} — genuine service, small affordable amount, never causing hardship.",
        planetary_purpose=f"Balance {planet} through service rather than transactional superstition.",
        chart_reason=chart_reason, frequency=f"Monthly or on {PLANET_WEEKDAY.get(planet, 'weekday')}",
        duration="2–3 months, then review",
        safety_note="Never donate beyond means; donating does not guarantee wealth/marriage/health/legal success.",
        suitability=suitability,
    )


def lal_kitab_remedy(title: str, practice: str, purpose: str, chart_reason: str,
                     frequency: str = "Once weekly", duration: str = "4 weeks",
                     suitability: str = "Moderate") -> Remedy:
    """Only for practices with a verifiable Lal Kitab edition/passage.

    Audit round 2, item 5: never label a modern conduct suggestion "Lal Kitab".
    Use ``modern_conduct_remedy`` when no Lal Kitab source can be cited.
    """
    return Remedy(
        kind="lal_kitab", tradition="Lal Kitab",
        title=f"Traditional Lal Kitab practice: {title}",
        practice=f"[Traditional Lal Kitab practice — distinct system from Parashari.] {practice}",
        planetary_purpose=purpose, chart_reason=chart_reason,
        frequency=frequency, duration=duration,
        safety_note="Only if safe, practical, non-polluting, and not interfering with others; skip if circumstances conflict.",
        suitability=suitability,
    )


def modern_conduct_remedy(title: str, practice: str, purpose: str, chart_reason: str,
                          frequency: str = "Once weekly", duration: str = "4 weeks",
                          suitability: str = "Moderate") -> Remedy:
    """Declared modern conduct — explicitly not a classical text prescription."""
    return Remedy(
        kind="conduct", tradition="modern conduct",
        title=f"Practical conduct: {title}",
        practice=("[Modern practical conduct — declared modern, not a classical "
                  "text prescription.] " + practice),
        planetary_purpose=purpose, chart_reason=chart_reason,
        frequency=frequency, duration=duration,
        safety_note="Only if safe, practical, non-polluting, and not interfering with others; skip if circumstances conflict.",
        suitability=suitability,
    )


def reference_remedy(title: str, practice: str, purpose: str, chart_reason: str) -> Remedy:
    return Remedy(
        kind="reference", tradition="traditional remedy literature",
        title=title,
        practice=(practice + " This is a traditional remedy commonly associated with classical remedy literature "
                  "(e.g. Encyclopaedia of Remedies family); verify the exact procedure with a qualified practitioner — "
                  "no fabricated page/verse is cited."),
        planetary_purpose=purpose, chart_reason=chart_reason,
        frequency="As per practitioner guidance; occasional",
        duration="Short trial, then review",
        safety_note="Must be safe, low-cost, and culturally respectful.",
        suitability="Moderate",
    )
