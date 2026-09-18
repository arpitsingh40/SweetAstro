"""
Verified chart payload builder.

Turns the deterministic ConsumerAnswer result into a compact, auditable text
block handed to the LLM. The LLM must treat this as the single source of
chart truth and never recalculate.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from ..consumer import ConsumerResult, TOPIC_HOUSES
from ..knowledge.provenance import provenance_block
from ..remedies.kat import kat_alignment_for_topic
from ..remedies.period import period_alignment_lines
from ..methods.registry import format_method_lines, method_for_topic, quotes_enabled


def _planet_line(p: Any) -> str:
    flags = []
    if p.is_retrograde:
        flags.append("retrograde")
    if p.is_combust:
        flags.append("combust")
    flag_txt = f" [{', '.join(flags)}]" if flags else ""
    return (
        f"{p.name}: {p.sign} {p.degree_in_sign:.2f}° (H{p.house}) — {p.dignity}, "
        f"Nak {p.nakshatra} Pada {p.nakshatra_pada} (lord {p.nakshatra_lord}){flag_txt}"
    )


def _house_line(h: Any) -> str:
    parts = [f"H{h.house_num}: {h.sign} (lord {h.lord})"]
    if h.occupants:
        parts.append(f"occupants: {', '.join(h.occupants)}")
    if h.aspecting_planets:
        parts.append(f"aspected by: {', '.join(sorted(set(h.aspecting_planets)))}")
    return " — ".join(parts)


def _factor_notes(data: Dict[str, Any]) -> str:
    """One compact line of classical per-planet factors (P0 dossier)."""
    parts: List[str] = []
    avasthas = data.get("avasthas") or {}
    if avasthas:
        parts.append("avasthas " + "/".join(f"{k[:3]}:{v}" for k, v in avasthas.items()))
    compound = data.get("compound_friendship") or {}
    notable = [f"{p}:{v}" for p, v in compound.items()
               if v in ("Adhimitra", "Mitra", "Shatru", "Adhishatru")]
    if notable:
        parts.append("maitri " + ", ".join(notable[:4]))
    if data.get("bav_bindus") is not None:
        parts.append(f"BAV {data['bav_bindus']}/8")
    if data.get("sandhi"):
        parts.append("sandhi")
    if data.get("gandanta"):
        parts.append("gandanta")
    if data.get("graha_yuddha"):
        parts.append(str(data["graha_yuddha"]))
    if data.get("parivartana"):
        parts.append("parivartana " + ", ".join(data["parivartana"][:2]))
    classical = data.get("classical_shadbala")
    if classical:
        parts.append(
            f"shadbala {classical['rupas']}r ({classical['ratio']}x min, "
            f"{classical['category']}), ishta/kashta {classical['ishta']}/{classical['kashta']}"
        )
    if data.get("sensitive"):
        parts.append(str(data["sensitive"]))
    return "; ".join(parts)


def _strength_block(strengths: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for name, sa in strengths.items():
        data = asdict(sa)
        sb = data.get("shadbala") or {}
        sb_txt = (f", strength-index {sb.get('category')} ({sb.get('total')}/360; "
                  f"SweetAstro analytical model, not classical Shadbala)" if sb else "")
        vargas = data.get("varga_dignities") or {}
        varga_txt = ", ".join(f"{k}:{v}" for k, v in vargas.items()) or "none"
        afflicted = "; ".join(data.get("affliction_reasons") or []) or "none"
        lines.append(
            f"- {name}: owns {data.get('functional_lordship')}, sits in H{data.get('house')}/{data.get('sign')} "
            f"as {data.get('sign_dignity')}; Nakshatra {data.get('nakshatra')} pada {data.get('nakshatra_pada')} "
            f"(lord {data.get('nakshatra_lord')}); dispositor {data.get('dispositor')} "
            f"({data.get('dispositor_dignity')}); relation with lagna lord: {data.get('relation_with_lagna_lord')}; "
            f"vargottama: {'yes' if data.get('vargottama') else 'no'}; varga dignities: {varga_txt}; "
            f"afflictions: {afflicted}; recommendation: {data.get('recommendation')} "
            f"({data.get('recommendation_reason')}){sb_txt}"
        )
        factors_txt = _factor_notes(data)
        if factors_txt:
            lines.append(f"  \u00b7 factors: {factors_txt}")
    return lines


def _varga_block(result: ConsumerResult) -> List[str]:
    lines: List[str] = []
    for varga_name in sorted(result.vargas.keys()):
        vc = result.vargas[varga_name]
        rows = []
        for name, vp in vc.planets.items():
            vargottama = " vargottama" if vp.is_vargottama else ""
            rows.append(f"{name}→{vp.varga_sign} (H{vp.varga_house}, {vp.varga_dignity}{vargottama})")
        lines.append(f"- {varga_name} [{vc.topic}] lagna {vc.ascendant_sign}: " + "; ".join(rows))
    return lines


def _remedy_block(remedy: Optional[Any], label: str) -> List[str]:
    if remedy is None:
        return []
    return [
        f"- {label}: {remedy.title} | tradition: {remedy.tradition} | practice: {remedy.practice} | "
        f"purpose: {remedy.planetary_purpose} | chart reason: {remedy.chart_reason} | "
        f"frequency: {remedy.frequency} | duration: {remedy.duration} | safety: {remedy.safety_note} | "
        f"suitability: {remedy.suitability}"
    ]


def _evidence_index(result: ConsumerResult) -> List[str]:
    """Numbered, exact citable facts so answers reason instead of generalising."""
    d1 = result.d1
    lines: List[str] = []

    def lord_state(name: str) -> str:
        state = d1.planets.get(name)
        if state is None:
            return name
        return f"{name} in H{state.house}/{state.sign} ({state.dignity})"

    moon = d1.planets["Moon"]
    sun = d1.planets["Sun"]
    lines.append(
        f"1. Lagna {d1.ascendant_sign} {d1.ascendant_degree_in_sign:.2f}°; "
        f"Sun in {sun.sign} (H{sun.house}), Moon in {moon.sign} (H{moon.house}), "
        f"Moon nakshatra {moon.nakshatra} P{moon.nakshatra_pada} (lord {moon.nakshatra_lord})."
    )

    md_ad_pd = [part.strip() for part in (result.timing.current_md_ad_pd or "").split("/")]
    while len(md_ad_pd) < 3:
        md_ad_pd.append("—")
    dasha_bits = [lord_state(part) for part in md_ad_pd if part and part != "—"]
    if dasha_bits:
        lines.append(
            f"2. Current dasha: {md_ad_pd[0]} MD / {md_ad_pd[1]} AD / {md_ad_pd[2]} PD — "
            + "; ".join(dasha_bits) + "."
        )

    if result.gochara is not None:
        transit_bits = []
        jupiter = result.gochara.entries.get("Jupiter")
        saturn = result.gochara.entries.get("Saturn")
        if jupiter is not None:
            transit_bits.append(f"Jupiter in {jupiter.sign} (H{jupiter.house_from_moon} from Moon)")
        if saturn is not None:
            transit_bits.append(f"Saturn in {saturn.sign} (H{saturn.house_from_moon} from Moon)")
        if transit_bits:
            lines.append(f"3. Transits now: " + "; ".join(transit_bits) + ".")

    for name, strength in list((result.strengths or {}).items())[:3]:
        affliction = ("; ".join(strength.affliction_reasons[:2])
                      if strength.afflicted else "")
        lines.append(
            f"{len(lines) + 1}. {name}: H{strength.house}/{strength.sign} {strength.sign_dignity}, "
            f"Nak {strength.nakshatra} P{strength.nakshatra_pada} (lord {strength.nakshatra_lord}), "
            f"dispositor {strength.dispositor}, vargottama "
            f"{'yes' if strength.vargottama else 'no'}"
            + (f", afflicted ({affliction})" if affliction else "")
            + "."
        )

    topic = getattr(result, "topic", "general")
    houses = TOPIC_HOUSES.get(topic, TOPIC_HOUSES["general"])[:4]
    house_bits = []
    for house_num in houses:
        house = d1.houses[house_num]
        lord = d1.planets.get(house.lord)
        detail = (f"H{house_num} {house.sign} (lord {house.lord} in H{lord.house})"
                  if lord is not None else f"H{house_num} {house.sign}")
        if house.occupants:
            detail += f", occupants {', '.join(house.occupants)}"
        house_bits.append(detail)
    if house_bits:
        lines.append(f"{len(lines) + 1}. Topic houses: " + "; ".join(house_bits) + ".")

    if result.ashtakavarga is not None:
        sav = ", ".join(
            f"H{h} {result.ashtakavarga.sav_by_house.get(h, 0)}/56" for h in houses)
        lines.append(f"{len(lines) + 1}. Sarvashtakavarga support: {sav}.")

    yoga_names: List[str] = []
    if result.yogas is not None:
        for yoga in sorted(result.yogas.yogas, key=lambda y: abs(y.strength_impact), reverse=True):
            if yoga.yoga_name not in yoga_names:
                yoga_names.append(yoga.yoga_name)
            if len(yoga_names) >= 4:
                break
    if yoga_names:
        lines.append(f"{len(lines) + 1}. Detected yogas: {', '.join(yoga_names)}.")

    varshaphala = getattr(result, "varshaphala", None)
    if varshaphala is not None and getattr(varshaphala, "muntha_house_from_lagna", None):
        lines.append(
            f"{len(lines) + 1}. Annual frame {varshaphala.target_year}: "
            f"Muntha in H{varshaphala.muntha_house_from_lagna} ({varshaphala.muntha_sign})."
        )

    return lines


def build_chart_payload(
    result: ConsumerResult,
    *,
    name: str,
    dob: str,
    tob: str,
    tz_offset: float,
    place: str,
    geo_note: str,
    time_reliable: bool,
    question: str,
    topic: str,
    tob_unknown: bool = False,
    tz_estimated: bool = False,
    dasha_detail: str = "",
    include_full_matrix: bool = False,
    include_deep_planets: bool = False,
    returning_note: str = "",
    source_references: Optional[List[str]] = None,
    expectation_block: str = "",
    subject_label: str = "",
    capability_gap: bool = False,
    unfavorable: bool = False,
    reason_tags: Optional[List[str]] = None,
) -> str:
    d1 = result.d1
    ans = result.answer

    sections: List[str] = []
    sections.append("=== VERIFIED CHART DATA (computed deterministically by SweetAstro — the ONLY source of chart facts) ===")
    sections.append(
        f"Birth data: name={name or 'Native'}; DOB={dob}; TOB={tob or 'unknown (neutral noon chart used)'}; "
        f"TZ offset={tz_offset:+.2f}h{' (estimated from place)' if tz_estimated else ''}; place={place}; {geo_note}"
    )
    sections.append(
        f"Birth-time reliability: {'RELIABLE' if time_reliable else 'UNCERTAIN — houses, divisional charts and house-based remedies carry reduced confidence'}"
        + (" (user does not know the birth time)" if tob_unknown else "")
    )
    if returning_note:
        sections.append(returning_note)
    sections.append(f"User question: {question or '(general reading)'}")
    sections.append(f"Detected topic: {topic}")
    if subject_label:
        role, _, subject_name = subject_label.partition(":")
        who = f"their {role}" + (f" ({subject_name})" if subject_name else "")
        sections.append(
            f"Subject: this chart belongs to {who}, NOT the user — the details were "
            "provided by the user. Address the answer to the user about this person, "
            "and note the chart is as accurate as the details provided."
        )
    if expectation_block:
        sections.append("")
        sections.append(expectation_block)
    sections.append(f"Ayanamsha: Lahiri/Chitrapaksha {d1.ayanamsha:.4f}°")
    sections.append(f"Ascendant: {d1.ascendant_sign} {d1.ascendant_degree_in_sign:.2f}°")
    moon = d1.planets["Moon"]
    sections.append(
        f"Moon: {moon.sign} {moon.degree_in_sign:.2f}°, Nakshatra {moon.nakshatra} pada {moon.nakshatra_pada} (lord {moon.nakshatra_lord})"
    )

    sections.append("")
    sections.append("Planetary positions (sidereal):")
    for p in d1.planets.values():
        sections.append(_planet_line(p))

    sections.append("")
    sections.append("Houses (whole-sign from lagna):")
    for h in d1.houses.values():
        sections.append(_house_line(h))

    sections.append("")
    sections.append(f"Current Vimshottari dasha: {result.timing.current_md_ad_pd}")
    # Promise gate: timing blocks are withheld from the payload itself (not
    # just prompt-enforced) when the natal promise is weak — audit round 2, MEDIUM.
    promise_timing_ok = not (result.promise is not None and not result.promise.timing_reliable)
    if dasha_detail and promise_timing_ok:
        sections.append(f"Dasha period boundaries: {dasha_detail}")
    sections.append(f"Dasha activation: {result.timing.dasha_activation}")
    sections.append(f"Transit activation: {result.timing.transit_activation}")
    if not promise_timing_ok:
        sections.append(
            "TIMING WITHHELD: the natal promise is weak — do NOT present event timing "
            "windows; present the promise finding, limiting factors, and guidance only."
        )

    sections.append("")
    sections.append(f"Relevant divisional charts: {', '.join(result.vargas.keys()) or 'D1 only'}")
    sections.extend(_varga_block(result))

    if include_full_matrix and result.full_varga_matrix is not None:
        sections.append("")
        sections.append(
            "Full varga matrix — every graha in every divisional chart "
            "(16 Parashari + non-Parashari D5/D6/D8/D11). Read-only reference: "
            "cite rows from here, never recalculate:"
        )
        sections.extend(result.full_varga_matrix.to_lines())

    if result.strengths:
        sections.append("")
        if include_deep_planets:
            sections.append("Planet strength — full chain (deep mode: all seven physical grahas):")
        else:
            sections.append("Planet strength — full chain:")
        sections.extend(_strength_block(result.strengths))

    if include_deep_planets and result.nodes:
        sections.append("")
        sections.append("Deep node dossier (full chain for Rahu and Ketu):")
        for node in ("Rahu", "Ketu"):
            na = result.nodes.get(node)
            if na is None:
                continue
            vargas_txt = ", ".join(f"{k}:{v}" for k, v in na.varga_positions.items()) or "none"
            sections.append(
                f"- {node}: H{na.house}/{na.sign}; sign lord {na.sign_lord} "
                f"({na.dispositor_dignity}, H{na.dispositor_house}); "
                f"nakshatra {na.nakshatra} pada {na.nakshatra_pada} "
                f"(lord {na.nakshatra_lord}, H{na.nakshatra_lord_house}); "
                f"conjunctions: {', '.join(na.conjunctions) or 'none'}; "
                f"aspects received: {', '.join(na.aspects_received_from) or 'none'}; "
                f"vargas: {vargas_txt}; wants: {na.wants}; gains: {na.where_gains}; "
                f"instability: {na.where_instability}; channel: {na.constructive_channel}; "
                f"reduce: {na.reducing_behaviour}; recommendation: {na.recommendation} "
                f"({na.recommendation_reason})"
            )
        sections.append(
            "- Read both nodes through this full chain; nodes are pacified/balanced, "
            "never blindly strengthened."
        )

    evidence = _evidence_index(result)
    if evidence:
        sections.append("")
        sections.append(
            "Evidence index (exact citable facts — quote these values in reasoning; "
            "never generalise beyond them):"
        )
        sections.extend(evidence)

    sections.append("")
    if ans.predictions:
        sections.append("Engine structured predictions (per-topic evidence; overall confidence is stated once below):")
        for idx, pred in enumerate(ans.predictions, 1):
            pd = pred.to_dict()
            sections.append(
                f"[{idx}] topic: {pd['topic']} | strength: {pd['strength']} | topic confidence: {pd['confidence']}\n"
                f"    signal: {pd['signal']}\n"
                f"    mechanism: {pd['mechanism']}\n"
                f"    timing: {pd['timing']}\n"
                f"    risk: {pd['risk']}\n"
                f"    statement: {pd['statement']}\n"
                f"    topic evidence: {pd['confidence_reason']}"
            )
    else:
        sections.append("Engine structured predictions: none (timing withheld or no strong thread).")

    sections.append("")
    sections.append("Engine key factors:")
    for factor in ans.key_factors:
        sections.append(f"- {factor}")

    sections.append("")
    sections.append(f"Engine timing reading:\n- Natal promise: {result.timing.natal_promise}\n"
                    f"- Remedy timing: {result.timing.remedy_timing}")

    sections.append("")
    sections.append("Engine opportunity / risk:")
    sections.append(f"- Opportunity: {ans.opportunity}")
    sections.append(f"- Risk: {ans.risk}")

    sections.append("")
    sections.append("Remedy candidates (chart-specific, optional — select at most 1 primary + 2 supporting):")
    remedy_lines = _remedy_block(ans.primary_remedy, "PRIMARY")
    for r in ans.supporting_remedies:
        remedy_lines += _remedy_block(r, "SUPPORTING")
    sections.extend(remedy_lines or ["- none computed"])

    sections.append("")
    kat = kat_alignment_for_topic(topic)
    if kat:
        sections.append(f"KAT domain alignment (modern method — {kat.source_label}; optional, no guarantees):")
        sections.append(f"- Domain: {kat.label} (houses {kat.houses}); focus planets: {', '.join(kat.planets)}")
        sections.append(f"- Guidance: {kat.focus_note}")
        if kat.adapted and kat.adapted_note:
            sections.append(f"- Mapping note: {kat.adapted_note}")
        for action in kat.actions:
            sections.append(f"  * {action}")
        sections.append("- Present as an optional modern alignment; never as a guarantee or prescription.")
    if capability_gap or unfavorable:
        method_match = method_for_topic(
            topic, reason_tags=reason_tags if unfavorable else None)
        if method_match is not None:
            sections.append("")
            sections.extend(format_method_lines(method_match, allow_quotes=quotes_enabled()))
    sections.append("")
    if ans.promise_note:
        sections.append("Promise assessment (promise gate — do not present event timing beyond this):")
        sections.append(f"- {ans.promise_note}")
    if ans.timeline and promise_timing_ok:
        sections.append("")
        sections.append("Personal timeline (verified period boundaries):")
        for item in ans.timeline:
            sections.append(f"- {item}")

    period_lines = period_alignment_lines(
        result.timing.current_md_ad_pd,
        promise=result.promise,
        upcoming=result.upcoming,
        time_reliable=time_reliable,
    )
    if period_lines:
        sections.append("")
        sections.extend(period_lines)

    if result.gochara is not None:
        sections.append("")
        sections.append("Gochara (transits from natal Moon) and Sade Sati:")
        sections.append(f"- {result.gochara.summary}")
        sections.append(f"- {result.gochara.sade_sati.note}")
        for planet in ("Saturn", "Jupiter"):
            entry = result.gochara.entries.get(planet)
            if entry:
                sections.append(f"- {entry.note}")
    if result.ashtakavarga is not None:
        sections.append("")
        sections.append("Ashtakavarga (verified bindu counts):")
        sections.append(f"- {ans.ashtakavarga_note}")
    if ans.yoga_notes:
        sections.append("")
        sections.append("Yogas and special combinations (classical detections):")
        for item in ans.yoga_notes:
            sections.append(f"- {item}")
    if ans.node_guidance:
        sections.append("")
        sections.append("Rahu/Ketu deep guidance:")
        for item in ans.node_guidance:
            sections.append(f"- {item}")
    if ans.panchanga_note:
        sections.append("")
        sections.append("Natal panchanga and nakshatra layer:")
        sections.append(f"- {ans.panchanga_note}")
    if ans.varshaphala_note:
        sections.append("")
        sections.append("Annual chart (Varshaphala — verified solar return/Muntha, year-lord strength not computed):")
        sections.append(f"- {ans.varshaphala_note}")
    if ans.jaimini_note:
        sections.append("")
        sections.append("Jaimini marriage layer (kendras/trikonas, UL):")
        sections.append(f"- {ans.jaimini_note}")
    if ans.stability_note:
        sections.append("")
        sections.append("Birth-time stability (sensitivity check):")
        sections.append(f"- {ans.stability_note}")
    sections.append("")
    sections.append(
        f"Gemstone gate: {ans.remedy_suitability_reason}"
    )
    sections.append(
        "ASSESSMENT CONFIDENCE (canonical — state this level exactly once, using only "
        "Low / Medium / High; never a hybrid range, never repeated in other sections):\n"
        f"- Level: {ans.confidence}\n"
        f"- Basis: {ans.confidence_reason}"
    )
    sections.append(f"Remedy suitability: {ans.remedy_suitability} — {ans.remedy_suitability_reason}")
    if ans.referrals:
        sections.append("Professional referrals required: " + " | ".join(ans.referrals))
    if ans.backtest_note:
        sections.append("Backtesting mode: " + ans.backtest_note)
    sections.append(
        "Calculation note: " + (ans.calculation_note or "Sidereal Lahiri; Vimshottari 365.2425 days/year.")
    )
    if source_references:
        sections.append("")
        sections.append(
            "Source references (the ONLY citable sources from the project corpus — "
            "never invent verses, pages, authors, or quotations):"
        )
        sections.extend(source_references)
    provenance = provenance_block(result, include_full_matrix=include_full_matrix)
    if provenance:
        sections.append("")
        sections.extend(provenance)
    sections.append("=== END VERIFIED CHART DATA ===")
    return "\n".join(sections)


def build_muhurta_payload(
    *,
    event_key: str,
    event_label: str,
    rules_source: str,
    place: str,
    geo_note: str,
    lat: float,
    lon: float,
    tz_offset: float,
    range_start: str,
    range_end: str,
    total_days: int,
    days: List[Any],
    birth_note: str,
    recommended_lagnas: List[str],
    avoid_tithis: List[str],
    max_days: int = 8,
) -> str:
    """Verified panchanga/muhurta payload for the LLM (dates computed, never invented)."""
    lines: List[str] = []
    lines.append("=== VERIFIED PANCHANGA & MUHURTA DATA (computed deterministically by SweetAstro — the ONLY source of dates and times) ===")
    lines.append(f"Location: {place} (lat {lat:.4f}, lon {lon:.4f}, tz {tz_offset:+.2f}h); {geo_note}")
    lines.append(f"Event: {event_label} [{event_key}] — sourced filters: {rules_source}")
    lines.append(f"Range searched: {range_start} to {range_end} ({total_days} days); suitable days found: {len(days)}")
    lines.append(f"Personal factors: {birth_note}")
    lines.append(f"Recommended lagnas: {', '.join(recommended_lagnas) if recommended_lagnas else 'none (no lagna filter for this event)'}")
    lines.append("Rules applied: avoid Rikta tithis (4/9/14) and Amavasya, avoid Vishti (Bhadra) karana and intraday Bhadra windows, avoid Rahu Kala; candidate windows are recommended-lagna windows plus Abhijit muhurta.")
    lines.append("")
    if not days:
        lines.append("No suitable days were found in this range. Suggest the customer widen the date range.")
        lines.append("=== END VERIFIED PANCHANGA DATA ===")
        return "\n".join(lines)

    lines.append(f"Suitable days (top {min(max_days, len(days))}, in chronological order):")
    for index, assessment in enumerate(days[:max_days], 1):
        day = assessment.day
        lines.append(f"{index}. {day.vara}, {day.date.isoformat()} — {day.paksha} {day.tithi_name}, {day.nakshatra} (pada {day.nakshatra_pada}), {day.karana} karana, Moon in {day.moon_sign}")
        lines.append(f"   Sunrise {day.sunrise.strftime('%H:%M')}, sunset {day.sunset.strftime('%H:%M')}; Rahu Kala {day.rahu_kalam[0].strftime('%H:%M')}–{day.rahu_kalam[1].strftime('%H:%M')}; Abhijit {day.abhijit[0].strftime('%H:%M')}–{day.abhijit[1].strftime('%H:%M')}")
        if assessment.windows:
            window_text = "; ".join(
                f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} ({label})"
                for start, end, label in assessment.windows[:4]
            )
            lines.append(f"   Candidate windows: {window_text}")
        else:
            lines.append("   Candidate windows: none free of Rahu Kala/Bhadra within the filtered lagnas")
        if assessment.tara or assessment.chandrabala:
            details = []
            if assessment.tara:
                details.append(f"Tarabala {assessment.tara} ({'favourable' if assessment.tara in ('Sampat', 'Kshema', 'Sadhaka', 'Mitra', 'Parama Mitra') else 'inauspicious'})")
            if assessment.chandrabala:
                details.append(f"Chandrabala {assessment.chandrabala}")
            lines.append("   Personal: " + "; ".join(details))
    lines.append("=== END VERIFIED PANCHANGA DATA ===")
    return "\n".join(lines)


def build_compatibility_payload(
    result: Any,
    *,
    label_a: str,
    label_b: str,
    birth_note_a: str = "",
    birth_note_b: str = "",
) -> str:
    """Verified Kundli Milan payload (8-kuta/36-point + Mangal dosha) for the LLM."""
    data = result.to_dict()
    lines: List[str] = []
    lines.append("=== VERIFIED KUNDLI MILAN (Ashtakoota 36-point + Mangal dosha — "
                 "computed deterministically by SweetAstro; the ONLY source of kuta facts) ===")
    lines.append(f"Person A: {label_a}" + (f" — {birth_note_a}" if birth_note_a else ""))
    lines.append(f"Person B: {label_b}" + (f" — {birth_note_b}" if birth_note_b else ""))
    lines.append(f"Total: {data['total']:g}/{data['max_total']:g}")
    lines.append(f"Verdict: {data['verdict']}")
    lines.append("")
    lines.append("Kuta scores (traditional 8-kuta scheme, Moon-based):")
    for kuta in data["kutas"]:
        lines.append(f"- {kuta['kuta']}: {kuta['points']:g}/{kuta['max_points']:g} — {kuta['detail']}")
    lines.append("")
    for side, label in (("mangal_a", label_a), ("mangal_b", label_b)):
        mangal = data[side]
        state = "active" if mangal["active"] else "not flagged"
        cancellations = ", ".join(mangal.get("cancellations") or []) or "none"
        lines.append(f"{label} Mangal dosha: {state} — houses {mangal.get('houses')}; "
                     f"cancellations: {cancellations}; {mangal.get('note', '')}")
    for note in data.get("notes") or []:
        lines.append(f"Note: {note}")
    lines.append("This is an interpretive traditional assessment, not a guarantee, probability, "
                 "or a substitute for the two people's own judgment.")
    lines.append("=== END VERIFIED KUNDLI MILAN ===")
    return "\n".join(lines)


def build_rectification_payload(
    *,
    name: str,
    dob: str,
    place: str,
    topic: str,
    result: Any,
) -> str:
    """Deterministic candidate-time ranking payload (never a verified birth time)."""
    lines: List[str] = []
    lines.append("=== VERIFIED RECTIFICATION ASSIST (deterministic candidate-time scoring — "
                 "the ONLY source of times and scores) ===")
    lines.append(f"Person: {name or 'Native'}; DOB {dob}; place {place}")
    lines.append(f"Topic used for scoring: {topic}")
    lines.append(f"Dated events used: {result.event_count}")
    lines.append("Best-fit windows (10-minute grid; contiguous top candidates):")
    for start, end in result.best_windows[:6]:
        lines.append(f"- {start} to {end}")
    lines.append("Ranked candidate times (time: score, events matched):")
    for candidate in result.candidates[:8]:
        lines.append(f"- {candidate.time}: score {candidate.score:g}, "
                     f"matched {candidate.events_matched}/{result.event_count}")
    lines.append(f"Method: {result.method_note}")
    lines.append("This is a ranking assist from the events the user supplied — NOT a verified birth "
                 "time. Present the windows as candidates to confirm against family memory, never as "
                 "a corrected time.")
    lines.append("=== END RECTIFICATION ASSIST ===")
    return "\n".join(lines)


def build_vastu_payload(assessment: Any, layout: Dict[str, Any]) -> str:
    """Verified Vastu assessment payload for the LLM (rules-computed, never invented)."""
    data = assessment.to_dict()
    lines: List[str] = []
    lines.append("=== VASTU ASSESSMENT (deterministic evaluation of the sourced rule base) ===")
    lines.append(f"Completeness score: {data['score'] if data['score'] is not None else 'n/a'}/100 "
                 f"(assessed items: {sum(v for k, v in data['counts'].items() if k in ('compliant', 'acceptable', 'neutral', 'defect'))})")
    lines.append(f"Counts: {data['counts']}")

    rooms = layout.get("rooms") or {}
    if rooms:
        lines.append("Rooms provided: " + ", ".join(f"{k}={v}" for k, v in rooms.items()))
    water = layout.get("water") or {}
    if water:
        lines.append("Water provided: " + ", ".join(f"{k}={v}" for k, v in water.items()))
    extras = []
    if layout.get("facing"):
        extras.append(f"facing={layout['facing']}")
    if layout.get("slope"):
        extras.append(f"slope={layout['slope']}")
    if layout.get("plot_shape"):
        extras.append(f"plot_shape={layout['plot_shape']}")
    if extras:
        lines.append("Other: " + ", ".join(extras))
    lines.append("")

    def _finding_line(f: Dict[str, Any]) -> str:
        base = f"- {f['label']} is in the {f['direction']} (preferred: {', '.join(f['expected_best']) or '—'})"
        if f.get("defect_id"):
            base += f" [defect {f['defect_id']}, severity {f.get('severity')}]"
        if f.get("note"):
            base += f" — {f['note']}"
        base += f" [{f.get('confidence', 'traditional')}]"
        return base

    if data["defects"]:
        lines.append("Defects (most severe first):")
        lines.extend(_finding_line(f) for f in data["defects"])
        lines.append("")
    if data["acceptable"]:
        lines.append("Acceptable:")
        lines.extend(_finding_line(f) for f in data["acceptable"])
        lines.append("")
    if data["compliant"]:
        lines.append("Compliant:")
        lines.extend(_finding_line(f) for f in data["compliant"])
        lines.append("")
    if data["neutral"]:
        lines.append("Neutral (not classified as beneficial or defective):")
        lines.extend(_finding_line(f) for f in data["neutral"])
        lines.append("")
    if data["remedies"]:
        lines.append("Remedies for the defects (optional, safe; zero-cost/usage changes first):")
        for remedy in data["remedies"]:
            lines.append(f"- {remedy['defect_id']} ({remedy['severity']}): {remedy['pattern']}")
            for action in remedy["actions"]:
                lines.append(f"    * {action}")
        lines.append("")
    if data["not_assessed"]:
        lines.append("Not assessed (invite the customer to share these; do not guess):")
        lines.append("- " + "; ".join(data["not_assessed"][:10]))
        lines.append("")
    lines.append("Safety: no demolition or structural advice — refer to a qualified professional for structural matters.")
    lines.append("Sources: " + " | ".join(data.get("sources", [])[:5]))
    lines.append("=== END VASTU ASSESSMENT ===")
    return "\n".join(lines)


def build_panchanga_payload(day: Any, place: str, geo_note: str) -> str:
    """Compact verified panchanga payload for single-date lookup questions."""
    d = day.to_dict()

    def window(pair: List[str]) -> str:
        return f"{pair[0][11:16]} to {pair[1][11:16]}"

    lines = [
        "=== VERIFIED PANCHANGA (deterministic drik ganita) ===",
        f"Date: {d['date']} ({d['vara']}) | Location: {place} | {geo_note}",
        f"Sunrise: {d['sunrise'][11:16]} | Sunset: {d['sunset'][11:16]}",
        f"Tithi: {d['tithi']} (ends {d['tithi_ends'][11:16]})",
        f"Nakshatra: {d['nakshatra']} pada {d['nakshatra_pada']} (ends {d['nakshatra_ends'][11:16]})",
        f"Yoga: {d['yoga']} (ends {d['yoga_ends'][11:16]}) | Karana: {d['karana']} (ends {d['karana_ends'][11:16]})",
        f"Rahu Kalam: {window(d['rahu_kalam'])}",
        f"Yamaganda: {window(d['yamaganda'])} | Gulika Kalam: {window(d['gulika_kalam'])}",
        f"Abhijit muhurta: {window(d['abhijit'])}",
        f"Moon sign: {d['moon_sign']} | Sun sign: {d['sun_sign']}",
        "=== END VERIFIED PANCHANGA ===",
    ]
    return "\n".join(lines)
