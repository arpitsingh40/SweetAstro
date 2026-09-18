"""
Consumer Answer Engine — Sec 12/13/16.

Output order (exact):
🔮 Bottom Line / 🧩 Key Chart Factors / ⏳ Timing / 📈 Opportunity /
⚠️ Risk / 🪐 Recommended Alignment / 🕉️ Traditional Remedies /
🎯 What You Should Do / Confidence / Remedy Suitability.

Rules enforced here:
- Plain language first (no Sanskrit overload).
- Calibrated phrasing: 'Jyotish indicates / chart suggests / traditionally supports'.
- No guarantees, no 'definitely', no 100%.
- Max 1 primary + 2 supporting remedies, each with purpose/timing/duration/safety/suitability.
- Practical action is non-superstitious.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ..interpretation.prediction_logic import Prediction
from ..interpretation.dasha_timing import TimingReading
from ..remedies.catalog import Remedy
from ..remedies.safety import safety_check
from .calibrated_language import sanitize_absolute_language


@dataclass
class ConsumerAnswer:
    bottom_line: str
    key_factors: List[str]
    timing: str
    opportunity: str
    risk: str
    alignment_title: str
    alignment_actions: List[str]
    primary_remedy: Optional[Remedy]
    supporting_remedies: List[Remedy]
    practical_actions: List[str]
    confidence: str
    confidence_reason: str
    remedy_suitability: str
    remedy_suitability_reason: str
    referrals: List[str] = field(default_factory=list)
    predictions: List[Prediction] = field(default_factory=list)
    backtest_note: str = ""
    calculation_note: str = ""
    promise_note: str = ""
    timeline: List[str] = field(default_factory=list)
    gochara_note: str = ""
    ashtakavarga_note: str = ""
    yoga_notes: List[str] = field(default_factory=list)
    node_guidance: List[str] = field(default_factory=list)
    panchanga_note: str = ""
    varshaphala_note: str = ""
    jaimini_note: str = ""
    stability_note: str = ""

    def to_markdown(self) -> str:
        lines = []
        lines.append("🔮 Bottom Line\n")
        lines.append(self.bottom_line.strip() + "\n")
        lines.append("🧩 Key Chart Factors\n")
        for i, f in enumerate(self.key_factors[:5], 1):
            lines.append(f"{i}. {f}")
        lines.append("")
        lines.append("⏳ Timing\n")
        lines.append(self.timing.strip() + "\n")
        lines.append("📈 Opportunity\n")
        lines.append(self.opportunity.strip() + "\n")
        lines.append("⚠️ Risk\n")
        lines.append(self.risk.strip() + "\n")
        lines.append("🪐 Recommended Alignment\n")
        lines.append(self.alignment_title.strip())
        for a in self.alignment_actions:
            lines.append(f"- {a}")
        lines.append("")
        lines.append("🕉️ Traditional Remedies\n")
        if self.primary_remedy:
            r = self.primary_remedy
            lines.append("Primary Remedy\n")
            lines.append(f"* Remedy: {r.title} — {r.practice}")
            lines.append(f"* Planetary purpose: {r.planetary_purpose}")
            lines.append(f"* Chart reason: {r.chart_reason}")
            lines.append(f"* Timing/frequency: {r.frequency}")
            lines.append(f"* Duration: {r.duration}")
            lines.append(f"* Safety note: {r.safety_note}")
            lines.append(f"* Source tradition: {r.tradition} | Suitability: {r.suitability}\n")
        for r in self.supporting_remedies[:2]:
            lines.append("Optional Supporting Remedy\n")
            lines.append(f"* Remedy: {r.title} — {r.practice}")
            lines.append(f"* Source tradition: {r.tradition}")
            lines.append(f"* Purpose: {r.planetary_purpose}")
            lines.append(f"* Chart reason: {r.chart_reason}")
            lines.append(f"* Timing/frequency: {r.frequency}")
            lines.append(f"* Safety note: {r.safety_note}\n")
        if not self.primary_remedy and not self.supporting_remedies:
            lines.append("No traditional remedy is necessary for this chart at this time.\n")
        lines.append("🎯 What You Should Do\n")
        for i, a in enumerate(self.practical_actions[:7], 1):
            lines.append(f"{i}. {a}")
        lines.append("")
        if self.promise_note:
            lines.append("🧭 Promise Assessment\n")
            lines.append(self.promise_note.strip() + "\n")
        if self.timeline:
            lines.append("🗓️ Personal Timeline (coming windows)\n")
            for item in self.timeline:
                lines.append(f"- {item}")
            lines.append("")
        if self.gochara_note or self.ashtakavarga_note:
            lines.append("🌐 Transit Strength (Gochara & Ashtakavarga)\n")
            if self.gochara_note:
                lines.append(self.gochara_note.strip())
            if self.ashtakavarga_note:
                lines.append(self.ashtakavarga_note.strip())
            lines.append("")
        if self.yoga_notes:
            lines.append("✨ Yogas & Special Combinations\n")
            for item in self.yoga_notes:
                lines.append(f"- {item}")
            lines.append("")
        if self.node_guidance:
            lines.append("☊ Rahu–Ketu Guidance\n")
            for item in self.node_guidance:
                lines.append(f"- {item}")
            lines.append("")
        if self.panchanga_note:
            lines.append("🌙 Birth Panchanga & Nakshatra\n")
            lines.append(self.panchanga_note.strip() + "\n")
        if self.varshaphala_note:
            lines.append("📅 Annual Chart (Varshaphala)\n")
            lines.append(self.varshaphala_note.strip() + "\n")
        if self.jaimini_note:
            lines.append("💍 Marriage Layer (Jaimini)\n")
            lines.append(self.jaimini_note.strip() + "\n")
        if self.stability_note:
            lines.append("🎚️ Birth-Time Stability\n")
            lines.append(self.stability_note.strip() + "\n")
        lines.append(f"Confidence\n\n{self.confidence}\n")
        lines.append(f"Reason:\n\n{self.confidence_reason}\n")
        lines.append(f"Remedy Suitability\n\n{self.remedy_suitability}\n")
        lines.append(f"Reason:\n\n{self.remedy_suitability_reason}\n")
        if self.referrals:
            lines.append("Professional guidance (alongside, not replaced by, astrology):")
            for ref in self.referrals:
                lines.append(f"- {ref}")
            lines.append("")
        lines.append("_Astrology is a traditional interpretive system, not scientifically established causation. "
                     "This reading is optional guidance and does not replace professional advice._")
        if self.calculation_note:
            lines.append(f"\n_Calculations: {self.calculation_note}_")
        if self.backtest_note:
            lines.append(f"\n_Backtest: {self.backtest_note}_")
        return "\n".join(lines)

    def to_dict(self):
        def r_dict(r: Remedy):
            return {"kind": r.kind, "tradition": r.tradition, "title": r.title,
                    "practice": r.practice, "planetary_purpose": r.planetary_purpose,
                    "chart_reason": r.chart_reason, "frequency": r.frequency,
                    "duration": r.duration, "safety_note": r.safety_note,
                    "suitability": r.suitability, "is_primary": r.is_primary}
        return {
            "bottom_line": self.bottom_line,
            "key_factors": self.key_factors,
            "timing": self.timing,
            "opportunity": self.opportunity,
            "risk": self.risk,
            "alignment_title": self.alignment_title,
            "alignment_actions": self.alignment_actions,
            "primary_remedy": r_dict(self.primary_remedy) if self.primary_remedy else None,
            "supporting_remedies": [r_dict(r) for r in self.supporting_remedies],
            "practical_actions": self.practical_actions,
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "remedy_suitability": self.remedy_suitability,
            "remedy_suitability_reason": self.remedy_suitability_reason,
            "referrals": self.referrals,
            "predictions": [p.to_dict() for p in self.predictions],
            "promise_note": self.promise_note,
            "timeline": self.timeline,
            "gochara_note": self.gochara_note,
            "ashtakavarga_note": self.ashtakavarga_note,
            "yoga_notes": self.yoga_notes,
            "node_guidance": self.node_guidance,
            "panchanga_note": self.panchanga_note,
            "varshaphala_note": self.varshaphala_note,
            "jaimini_note": self.jaimini_note,
            "stability_note": self.stability_note,
            "markdown": self.to_markdown(),
        }


class ConsumerAnswerBuilder:
    """Assembles a ConsumerAnswer from analysed pieces with calibrated language."""

    CALIBRATED_PREFIX = ("Jyotish indicates", "The chart suggests",
                         "This combination traditionally supports")

    def build(self, *, question: str, bottom_line: str, key_factors: List[str],
              timing_reading: TimingReading, opportunity: str, risk: str,
              alignment_title: str, alignment_actions: List[str],
              remedies: List[Remedy], practical_actions: List[str],
              predictions: List[Prediction], confidence: str, confidence_reason: str,
              remedy_suitability: str, remedy_suitability_reason: str,
              calculation_note: str = "", backtest_note: str = "",
              promise_note: str = "", timeline: Optional[List[str]] = None,
              gochara_note: str = "", ashtakavarga_note: str = "",
              yoga_notes: Optional[List[str]] = None,
              node_guidance: Optional[List[str]] = None,
              panchanga_note: str = "", varshaphala_note: str = "",
              jaimini_note: str = "", stability_note: str = "") -> ConsumerAnswer:
        # Enforce remedy cap: 1 primary + <=2 supporting (Sec 16)
        primary = next((r for r in remedies if r.is_primary), (remedies[0] if remedies else None))
        supporting = [r for r in remedies if r is not primary][:2]

        # Safety gate
        texts = [bottom_line, opportunity, risk] + key_factors + practical_actions
        texts += [f"{r.title} {r.practice}" for r in ([primary] if primary else []) + supporting]
        texts += [promise_note, gochara_note, ashtakavarga_note, panchanga_note,
                  varshaphala_note, jaimini_note, stability_note]
        texts += list(yoga_notes or []) + list(node_guidance or [])
        verdict = safety_check(question, texts)
        if not verdict.allowed:
            # Strip to safe fallback: keep alignment only, drop mantra/ritual specifics
            supporting = []
            if primary and primary.kind in ("mantra", "ritual"):
                primary = None

        # Enforce non-absolute bottom line using the shared calibrated-language
        # contract (same list the sanitizer and rubric use).
        bl = sanitize_absolute_language(bottom_line).strip()
        if "Jyotish" not in bl and "chart" not in bl.lower() and "tradition" not in bl.lower():
            bl = f"The chart suggests: {bl}"

        return ConsumerAnswer(
            bottom_line=bl, key_factors=key_factors[:5],
            timing=(f"{timing_reading.dasha_activation}\n{timing_reading.natal_promise}\n"
                    f"{timing_reading.transit_activation}\n{timing_reading.remedy_timing}\n"
                    f"Current MD/AD/PD: {timing_reading.current_md_ad_pd}."),
            opportunity=opportunity, risk=risk,
            alignment_title=alignment_title, alignment_actions=alignment_actions,
            primary_remedy=primary, supporting_remedies=supporting,
            practical_actions=practical_actions[:7],
            confidence=confidence, confidence_reason=confidence_reason,
            remedy_suitability=remedy_suitability,
            remedy_suitability_reason=remedy_suitability_reason,
            referrals=list(verdict.referrals),
            predictions=predictions, backtest_note=backtest_note,
            calculation_note=calculation_note,
            promise_note=promise_note,
            timeline=list(timeline or []),
            gochara_note=gochara_note,
            ashtakavarga_note=ashtakavarga_note,
            yoga_notes=list(yoga_notes or []),
            node_guidance=list(node_guidance or []),
            panchanga_note=panchanga_note,
            varshaphala_note=varshaphala_note,
            jaimini_note=jaimini_note,
            stability_note=stability_note,
        )
