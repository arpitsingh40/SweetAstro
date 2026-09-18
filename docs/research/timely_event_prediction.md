# Timely Event Prediction — Deep Research Brief

**Researched**: 2026-09-12 · **Status**: frozen reference for the Event Timing Engine
(`src/prediction/event_timing.py`) · **Purpose**: define the best-practice method stack,
its evidence status, and the honesty contract for event timing.

**Deep follow-up (2026-09-13)**: `docs/research/event_timing_deep.md` — method-by-method
research, code audit (findings F1–F10 with line references), an evaluation design for
event timing (endpoints/baselines/protocol 1.3.0), intake candidates, and a prioritized
roadmap.

Sources: classical canon catalogued in `docs/knowledge/01_classical_canon.md`,
`02_modern_specialized.md`, `03_applied_systems.md`; internal engine + `docs/accuracy_protocol.md`
+ seed backtest report; external secondary summaries of controlled studies (Carlson 1985;
Dean & Kelly; time-twin and census studies). External summaries are secondary and flagged as such.

---

## 1. The classical architecture: timing is a stack, never a single technique

Event timing in Jyotish is the intersection of four gates that must agree:

1. **Promise** — the natal chart must permit the event (bhava/lord/karaka strength,
   dignity, vargottama, yogas, Sarvashtakavarga support). No promise → no timing.
2. **Period** — a Vimshottari dasha lord connected to the event's significators must be
   operating (MD/AD/PD, classically down to Sukshma/Prana).
3. **Transit** — slow planets must activate the natal points. Phaladeepika 19.4
   (as summarised in the Dasha literature): events occur when the lagna lord transits a
   trine from the bhava lord, or the bhava lord transits a trine from the natal lagna,
   or they aspect/conjoin, or the bhava-karaka transits the natal lagna / Moon-lord point.
   Jataka Parijata adds that dasha results are modified by the lord's **Ashtakavarga
   bindus**, nakshatra-tara quality, combustion, sandhi and affliction.
4. **Annual / elective confirmation** — Varshaphala (solar return, Muntha, year-lord,
   sahams, ithasala aspects; the Tajika system claims day-level resolution), Sudarshana
   chakra, or Prashna/horary for exact "when" questions.

**Doctrine**: a single factor ("Jupiter transits the 7th") is never sufficient.
Disagreement between layers widens the window; it is not averaged away.

## 2. Method inventory and failure modes

| Method | What it contributes | Known weakness |
|---|---|---|
| Vimshottari MD/AD/PD/SD/PrD | the workhorse time-lord clock | event mapping is interpretive; lord quality dependent |
| Alternate dashas (Ashtottari, Yogini, Kalachakra, Chara/Narayana, Sthira, Shoola — Parashara names 42) | independent cross-check | disputed applicability conditions; cross-check, don't stack |
| Double transit (Jupiter+Saturn, K.N. Rao) | physical activation of the event axis | without BAV filtering every year looks activated |
| Gochara from Moon + vedha + Sade Sati | 9-planet transit quality | vedha cancellation ignored by most software |
| Ashtakavarga BAV/SAV | the classical transit filter | tables vary by edition; totals invariants used for QC |
| Jaimini AK/DK/AL/UL, Chara dasha | independent timing + marriage confirmation | Chara dasha variants differ |
| Varshaphala / Tajika (solar return, Muntha, year-lord, sahams) | annual frame, day-level claims | no published error rates for day-level claims |
| KP sub-lords / Prashna / Nadi | fine timing, horary | tradition-specific, unvalidated |

## 3. Evidence reality (the critical finding)

- **Carlson (Nature, 1985)**: 28 astrologers, double-blind CPI profile matching —
  no better than chance. (secondary summary)
- **Dean & Kelly**: meta-analysis of 40 studies (~700 astrologers, 1000+ charts) — no
  effect; 45 experienced astrologers performed *worse than controls who used no charts*.
  (secondary summary)
- **Time twins (2011, ~2000 pairs)** and **Voas' census study (>20M England/Wales
  records, marriage arrangements)**: no detectable effect. (secondary summaries)
- Inter-astrologer agreement on readings ≈ **0.1**. (secondary summary)
- **Our own pre-registered seed run** (`reports/accuracy_20260912_201459.md`):
  Top-1 year 0%, MAE 93 months, permutation p = 1.0 on the single held-out chart —
  no demonstrated skill (protocol v1.1.0).

**Conclusion**: no timing method has demonstrated out-of-sample validity. A product can
be excellent at analysis, transparency and calibration — but any claim of accurate event
dates would be fabrication. Our accuracy protocol forbids such claims.

## 4. Engine design (what we built)

`src/prediction/event_timing.py` implements the stack as a promise-gated pipeline:

1. **Promise gate** — reuses `src/interpretation/promise.py`; weak promise → windows withheld.
2. **Dasha layer** — scans Vimshottari AD/PD periods in the requested range; scores each
   lord by connection to event houses (ownership, occupation, karaka, aspect) and rewards
   AD+PD depth agreement.
3. **Transit layer** — monthly-cached slow-planet positions; a transit scores when it
   touches the event axis *and* carries enough Bhinnashtakavarga bindus (`min_bav`),
   with Sarvashtakavarga support for the event houses (`min_sav`).
4. **Annual layer** — Varshaphala Muntha falling in an event house adds confirmation.
5. **Output** — ranked windows with tier (High/Medium/Low), score, supporting and
   limiting factors, transit note, method notes and disclaimer. Never a single date.

Event registry: marriage, career_change, property, child, travel, business_launch
(`EVENT_CONFIGS`), each with houses, karakas, transit planets and thresholds.

### Deliberate omissions (documented, not hidden)
- Chara dasha **is now implemented** (`src/core/chara_dasha.py`, count-minus-one
  convention declared in the method notes) as an independent cross-check layer in
  `event_timing.py`; agreement adds a small confirmation bonus, disagreement is
  recorded but not subtracted. Narayana dasha is not computed. Yogini dasha is
  available (`src/core/yogini.py`) but not yet wired into the scoring stack.
- KP sub-lords, Sudarshana chakra, Varshaphala year-lord strength (Panchavargiya Bala)
  and sahams are not computed.
- No day-level claims; smallest emitted window is the Pratyantardasha span.

## 5. Calibration loop (the only honest path to claims)

1. Freeze each event config and score windows with the existing harness
   (`src/evaluation/`, endpoints hit ±6/12/24 months, MAE, baselines).
2. Collect real outcomes through the chat outcome log
   (`src/chat/outcomes.py` → `data/outcomes/outcomes.jsonl`).
3. Only after ≥500 verified records (Rodden AA/A) and a passed pre-registered run may
   any accuracy statement be considered; until then the engine says
   "interpretive windows, no demonstrated skill".

## 6. Bottom line

Timely event prediction is the highest-demand and least-evidenced claim in astrology.
World-class here does not mean the most confident dates — it means the most
cross-confirmed windows, the clearest confidence honesty, and a real calibration loop.
This engine implements the analysis stack; the decisive missing asset is outcome data
at scale.

_External studies are cited from secondary summaries; verify primary papers before any
public claim. This document makes no efficacy claim for astrology._
