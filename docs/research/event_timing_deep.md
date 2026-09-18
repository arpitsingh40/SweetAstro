# Event Timing — Deep Method Research

**Date**: 2026-09-13 · **Scope**: method-by-method research, engine audit, evidence
status, and a testable plan for the Event Timing Engine (`src/prediction/event_timing.py`
+ layers) · **Companion**: `docs/research/timely_event_prediction.md` (brief)

**Method of research**: audit of every engine module used in timing; audit of the
52-rule corpus (`data/rules/*.json`) and the 537-entry bibliography
(`docs/reference_library.md`, `docs/knowledge/*`); evidence review of controlled
studies via secondary summaries (flagged); no verse is quoted unless the project
corpus already carries it. Provenance tags follow the corpus style:
`[canon]` classical text · `[known]` published work · `[tech]` modern practice ·
`[verify]` edition/content must be checked before encoding.

---

## 1. Executive summary

Event timing in this engine is a promise-gated stack of five gates (promise →
period → transit → annual → elective). The stack is implemented for Vimshottari,
Ashtakavarga-filtered slow transits, Varshaphala Muntha, Gochara/vedha, and a
Chara-dasha cross-check. Ten concrete findings emerged; four are machinery fixes
that need no new source, and the remainder are source-gated.

**Headline findings**

| # | Finding | Evidence | Class |
|---|---|---|---|
| F1 | Transits are sampled only on the 15th of each month; sub-month activations are missed | `event_timing.py:166-180` | **fixed 2026-09-13** |
| F2 | Scoring weights, thresholds and tier cuts are uncalibrated declared heuristics | `event_timing.py:80,354-357`; config `min_bav/min_sav` | protocol |
| F3 | Dasha-lord quality is ignored (no BAV, strength, combustion, retrograde, sandhi, tarabala) | `event_timing.py:141-163` | source-gated |
| F4 | Yoga/Chara cross-checks are non-stacking by design, but Yogini is implemented and unwired | `chara_dasha.py`, `yogini.py` | machinery |
| F5 | Adjacent qualifying PD windows are emitted separately, fragmenting one window | `event_timing.py:367-369` | machinery |
| F6 | Event registry (houses/karakas/transit planets) carries no source citations | `event_timing.py:47-78` | governance |
| F7 | `travel` promise uses topic `general` — the gate is not travel-specific | `event_timing.py:68-72` | machinery |
| F8 | Double transit is sign-level only (no orb/degree, no retro passes, no ingress dates) | `transits.py:47-67,108-197` | machinery |
| F9 | Event timing has no pre-registered evaluation; only marriage-year is scored | `accuracy_protocol.md §1` | protocol |
| F10 | Outcome log is not joined to emitted windows (no per-event calibration) | `src/chat/outcomes.py` | protocol |

**Status update 2026-09-13 (fix round 1)**: F1 fixed — transit evidence is now
built from 5-day samples with bisected sign-change instants, and each window is
evaluated over the signs it actually holds; transit evidence is interleaved into
the supporting factors so it is no longer truncated away (found during the fix:
dasha lines could fill the old 6-item cap and hide the transit reason entirely).
Window width and a *measured* birth-time sensitivity ("±5 min moves dasha
boundaries by N days for this chart") are disclosed in the method notes. Tests:
`tests/test_event_timing.py` (9).

**Bottom line**: the engine is a faithful implementation of the classical stack's
*structure*; its *parameters* are conventions, and its *evidence* is absent. The
honest next step is not a new technique — it is (a) fixing the machinery gaps
(F1, F5, F7, F8) and (b) pre-registering an event-timing protocol before touching
any weight (F2, F9).

---

## 2. The classical architecture: five gates that must agree

1. **Promise** — the natal chart permits the event (bhava/lord/karaka condition,
   dignity, vargottama, yogas, Ashtakavarga support). No promise → no timing.
   Engine: `src/interpretation/promise.py:93` (transparent factor counting)
   + rule corpus (`data/rules/mar_*.json`, 52 rules: 35 timing-capable, 17
   diagnostic; sources: BPHS ×19, Phaladeepika ×14, Jataka Parijata ×7,
   Jaimini Sutras ×5, Sarvartha Chintamani ×4, Deva Keralam ×3).
2. **Period** — a Vimshottari time-lord connected to the event's significators.
   Engine: `src/core/dasha.py` MD/AD/PD ± Sukshma/Prana (`get_deep_dasha_at_date:224`).
3. **Transit** — slow planets activating natal points, filtered by Ashtakavarga
   bindus. Engine: `src/core/transits.py` + `src/core/ashtakavarga.py`.
4. **Annual** — Varshaphala (solar return, Muntha) or Tajika year-lord.
   Engine: `src/core/varshaphala.py:71` (Muntha + Varsha lagna; year-lord omitted).
5. **Elective** — Muhurta for choosing a date (not predicting one). Engine:
   `data/rules/muhurta_rules.json` + `src/core/muhurta.py`; deliberately separated.

Doctrine (kept in the engine): a single factor is never sufficient; disagreement
widens the window rather than being averaged away.

---

## 3. Method-by-method deep dive

### 3.1 Vimshottari (MD/AD/PD/SD/Prana)
- **Mechanics**: 120-year cycle from the Moon's nakshatra; 365.2425-day year;
  sub-periods proportional (`dasha.py:204`); timeline integrity and balance are
  hand-verified in `tests/test_calculation_backtest.py:409-486`.
- **Source**: BPHS (corpus #47 `[canon]`), Phaladeepika (#23 `[canon]`, a
  primary timing text); arithmetic standard.
- **Engine use in timing**: `event_timing.find_timing_windows` scans PD periods
  in the requested range and scores the MD/AD/PD lords by event connection
  (`_period_significance`: ownership, occupation, karaka, aspect).
- **Failure modes**: lord-event mapping is interpretive; no lord-quality
  modifiers; PD windows can be shorter than the monthly transit sampling
  resolution (see F1); no *dasha chidra*/sandhi logic; retrograde/combustion of
  the dasha lord is not considered although classical practice flags them.
- **Action**: add optional lord modifiers (source-gated, F3) and make window
  resolution consistent with transit resolution (F1).

### 3.2 Alternate dashas (cross-checks)
- **Implemented**: Yogini (36-year, 8 yoginis — `src/core/yogini.py`;
  corpus #315 `[tech]`) and Jaimini Chara (`src/core/chara_dasha.py`; declared
  count-minus-one convention, K.N. Rao reading; Jaimini Sutras #48 `[canon]`,
  #148 `[known]`, #206 `[known]`).
- **Engine use**: Chara is a bonus-only cross-check in `event_timing`
  (`_chara_cross_check:229`); **Yogini is implemented but not wired** into the
  scoring stack. Cross-system agreement also appears in `strength_extras.py`
  (Vimshottari/Yogini/Chara count, verdict cross-confirmed/single-system).
- **Failure modes**: applicability conditions for Ashtottari/Kalachakra are
  disputed (#234 `[tech]`); Chara variants differ (#296 `[tech]`); stacking
  systems silently inflates confidence — forbidden by design.
- **Action (F4)**: wire Yogini as a second non-stacking cross-check; report
  agreement/disagreement, never add points from both cross-checks.

### 3.3 Double transit (Jupiter + Saturn)
- **Mechanics (engine)**: whole-sign aspects including the occupied sign;
  Jupiter activates via 7th house/lord, lagna/lord, or Venus; Saturn via 7th
  house/lord or lagna/lord (`transits.py:108-197`). Weighted sub-scores
  (40/25/15/10/10 and 45/30/15/10) combine only when both are active.
- **Source**: modern technique attributed to the K.N. Rao school (#204 `[known]`,
  #256 marriage keys `[tech]`); compatible with Raman-school transit practice
  (#168 `[known]`, #242 `[tech]`).
- **Failure modes**: sign-level only — no orb/degree, no distinguishing direct,
  retrograde or stationary passes (a Saturn sign is ~2.5 years); without a BAV
  filter almost every Jupiter–Saturn overlap looks "active" (the separate
  `_transit_layer` does apply BAV thresholds; the marriage double-transit
  convenience function does not); the "Venus aspect" extension is modern and
  un-sourced in the corpus.
- **Action (F8)**: add BAV filtering and ingress dates to the double-transit
  layer, or document it as a coarse confirmation only. Do not present it as
  precise timing.

### 3.4 Gochara from the Moon + vedha + Sade Sati
- **Mechanics**: good-house sets per planet counted from the natal Moon;
  vedha cancellation map; Sade Sati phase detection (`transits.py:205-332`).
- **Source**: gochara tables and vedha pairs catalogued as B.V. Raman standard
  (#233 `[tech]`, #242 `[tech]`, #270 `[tech]`).
- **Failure modes**: vedha has school-specific pairs and ordering subtleties;
  the implementation compares one planet per pair but does not model the
  "reverse vedha" exception; Sade Sati is a background restructuring signal, not
  an event trigger, yet it can dominate the prose.
- **Action**: cite the exact edition in the method notes; use Gochara as a
  filter/context, never as a standalone trigger.

### 3.5 Ashtakavarga (BAV/SAV)
- **Mechanics**: BAV per planet, SAV = sum with the 337 invariant
  (`ashtakavarga.py`; `tests/test_ashtakavarga.py`); event windows require the
  transiting slow planet to carry ≥ `min_bav` bindus (default 4) and event
  houses to carry ≥ `min_sav` (default 25) (`event_timing.py:43-44,201-219`).
- **Source**: BPHS Ch. 66 (provenance ledger); practice corpus #201 `[known]`,
  #203 `[known]`, #311-314 `[verify]/[tech]`.
- **Failure modes**: bindu tables vary by edition; school-dependent reductions
  (trikona/ekadhipatya shodhana) are not applied; thresholds are declared
  conventions, not text-derived.
- **Action**: keep BAV/SAV as a *filter*; pre-register the thresholds before any
  scoring (F2); expose an optional shodhana variant only with a verified edition.

### 3.6 Jaimini layer (AK/DK/AL/UL, argala, Chara)
- **Engine**: `src/core/jaimini.py`, `arudha.py`, `argala.py`,
  `chara_dasha.py`; marriage layer in the chat payload.
- **Source**: Jaimini Sutras (#48 `[canon]`, #148 `[known]`), K.N. Rao practice
  (#206 `[known]`, #296 `[tech]`, #302 `[tech]`).
- **Failure modes**: 7-karaka scheme declared simplified; Chara conventions
  declared; Narayana dasha (#318 `[tech]`) not implemented.
- **Action**: keep as an independent confirmation layer; Narayana dasha is a
  candidate but needs a verified convention before encoding.

### 3.7 Varshaphala / Tajika
- **Engine**: solar-return moment, Muntha, Muntha lord, Varsha lagna
  (`varshaphala.py:36-110`); year correction regression-tested.
- **Source**: Tajika Neelakanthi and companions (#61-63 `[canon]`), translations
  #150 `[verify]`, practice #240/#308/#309 `[tech]`.
- **Failure modes**: year-lord (varshesha, Panchavargiya Bala), sahams and
  ithasala/muthasala aspects are missing, so "day-level Tajika resolution" is not
  available; Muntha theme-house lists vary by author (engine lists are declared).
- **Action**: implement year-lord *only* from a verified edition; until then keep
  the annual layer as a planning frame.

### 3.8 KP sub-lords, Prashna, Nadi/BNN
- **Status**: not implemented. Corpus: KP #286/#294/#338 `[tech]` (note: KP uses
  the Krishnamurti ayanamsha — mixing it silently with Lahiri outputs would be a
  correctness error); Prashna #239/#353-357 `[tech]`; Nadi/BNN #67/#68 `[canon]`,
  #208/#209/#305 `[known]/[tech]`, #303/#306 `[verify]`.
- **Failure modes**: tradition-specific, unvalidated; palm-leaf Nadi claims are
  not reproducible; BNN "Saturn/Jupiter on significators" overlaps the double
  transit but uses different significator selection.
- **Action**: only via `research_intake.py` with a declared `source_class`
  (`tech`/`web` are modern-only), never blended into the Lahiri stack.

### 3.9 Muhurta (election) vs event prediction
- Muhurta chooses a date under sourced filters (`data/rules/muhurta_rules.json`;
  corpus #56-60 `[canon]`, #341 `[canon]`). It must never be presented as a
  prediction of when an event will occur. The engine keeps them in separate
  routes; keep that boundary.

### 3.10 Not recommended (yet)
Sudarshana chakra (#250/#319 `[tech]`), Sarvatobhadra chakra (#249 `[tech]`),
Kalachakra dasha (#317 `[tech]`), Shoola (#324 `[tech]`), Ashtottari (#316
`[tech]`), Prashna systems — large unverified tables or applicability disputes;
encode only after edition checks via the intake gate.

---

## 4. Code audit of the timing engine (findings with exact references)

- **F1 — monthly transit sampling** (`_monthly_transit_cache`,
  `event_timing.py:166-180`): **fixed 2026-09-13**. Replaced by
  `_transit_segments` (5-day samples + `_bisect_sign_change` to ~0.02 d) and
  per-window `_signs_in_window`, so a PD is matched against the signs it holds
  across its whole span; a planet changing sign inside a window is named in the
  transit note. Regression: `test_transit_segments_detect_and_bisect_sign_change`.
  A second truncation bug found while fixing it: dasha lines could fill the old
  6-item support cap and hide the BAV-filtered transit reason — evidence is now
  interleaved across layers (`test_windows_cite_bav_filtered_transit_evidence`).
- **F2 — uncalibrated parameters**: `connection * 1.6`, transit ±3/1, Muntha
  +1.5, Chara +1.0/1.5, `MIN_SCORE = 4.0`, tiers 10.5/7.0
  (`event_timing.py:80,354-357`); `min_bav=4`, `min_sav=25` (`:43-44`). These are
  the model's degrees of freedom. They must be frozen in a pre-registration
  manifest before any scoring; changing them requires a protocol version bump.
- **F3 — dasha-lord quality ignored**: a dasha lord can be debilitated,
  combust, retrograde, in sandhi or weak in BAV and score identically. Classical
  practice (as summarised in the brief) applies lord-level modifiers. *Needs a
  verified edition before encoding* (intake candidate IC-1).
- **F4 — Yogini unwired**: `yogini.py` exists with a full 36-year timeline;
  `dasha_agreement` exists in `strength_extras.py`. Wiring it into
  `event_timing` as a non-stacking cross-check is machinery-only.
- **F5 — window fragmentation**: qualifying PDs are emitted individually
  (`:367-369`); contiguous qualifying periods should merge into one window with
  combined factors (merge must not inflate score — take max, list combined
  supports).
- **F6 — registry provenance**: `EVENT_CONFIGS` houses/karakas/thresholds have
  no citation fields. Add `source_refs` per event mirroring the rules JSON
  pattern, so the payload's method provenance can be per-event specific.
- **F7 — travel promise**: `travel` maps to `promise_topic="general"`
  (`:68-72`), so a weak general promise may gate travel timing while travel
  significators (3/9/12, Moon/Mercury) are never checked. Add a travel promise
  topic or document the mapping.
- **F8 — double transit coarse** (see §3.3): sign-level, no ingress dates, no
  retro passes, no BAV; the `/api/timing` path uses it via `EVENT_CONFIGS`, while
  the dedicated marriage axis function remains separate.
- **F9 — no event-timing evaluation**: `accuracy_protocol.md §1` scores
  `PredictionHierarchy.predict` (marriage year/month). Event timing
  (`find_timing_windows`) has no pre-registered run.
- **F10 — outcomes not joined**: `data/outcomes/outcomes.jsonl` records verdicts
  per session; there is no link from a reported event to the emitted window set
  (needed for coverage/hit-rate review).

---

## 5. Evidence review (what is actually known)

- **Controlled studies** (secondary summaries; verify primaries before any public
  use): Carlson 1985 double-blind profile matching — no effect; Dean & Kelly
  meta-analysis (~700 astrologers) — no effect, experienced astrologers worse
  than controls; time-twin (~2 000 pairs) and Voas census (>20M records) — no
  detectable effect; inter-astrologer agreement ≈ 0.1.
- **Our own seed run** (protocol 1.1.0, re-run 1.2.0): Top-1 year 0%, MAE 93
  months, p = 1.0 on one held-out chart → no demonstrated skill, correctly stated.
- **Implication**: no event-timing claim may be made. The product value is the
  transparent multi-layer reasoning, the promise gate, the declared sources, and
  the calibration loop — not the dates.

---

## 6. Evaluation design for event timing (proposal)

**Dataset schema** (extends `data/test_charts/dataset_template.csv`):
`chart_id, rodden, dob, tob, tz_offset, lat, lon, event_type, event_date,
source, first_or_later`. Event date precision must be recorded (day/month/year).

**Endpoints** (pre-registered; window-relative to prevent fishing):
- **E1 window hit**: actual event inside *any* emitted window.
- **E2 best-window hit**: actual event inside the top-ranked window.
- **E3 coverage**: share of charts with ≥1 window in the search range.
- **E4 window width**: median emitted window width (parsimony guard).
- **E5 lead time**: distance from window start to event (from window end too).
- **E6 windows/year**: parsimony (a method emitting everything is useless).

**Baselines**: (a) uniform-random window of the same width and range (Monte
Carlo); (b) dasha-lord-only windows (no transit/annual confirmation); (c) modal
period baseline. Success requires beating the uniform upper bound on E1 **and**
a permutation p < 0.05 **and** E4/E6 no worse than a declared budget.

**Protocol mechanics**: freeze `EVENT_CONFIGS`, weights, thresholds, sampling
resolution, search range and merge rules as protocol **1.3.0**; run once on a
held-out split (Rodden AA/A); ≥500 records for any claim; no post-hoc tuning.
Event timing is currently out of scope of the accuracy protocol — adding it
requires a new protocol version per `docs/accuracy_protocol.md`.

**Machinery tests addable now** (no dataset needed): window containment,
promise gating, determinism, merge invariants, ingress membership (F1), and a
"no windows for empty range" guard. Existing coverage:
`tests/test_event_timing.py` (6 tests).

---

## 7. Prioritized roadmap

**P0 — machinery (no new source; do first)**
1. ~~F1: transit membership at PD boundaries/ingresses + regression test.~~
   **Done 2026-09-13** (plus evidence-interleaving and the measured
   birth-time sensitivity note).
2. F5: merge contiguous qualifying windows (max score, combined factors).
3. F7: travel promise topic (or explicit documented mapping).
4. F4: wire Yogini as a non-stacking cross-check (declared, reported).
5. F9: draft protocol 1.3.0 for event timing (freeze before scoring).

**P1 — source-gated (intake candidates; no encoding without a verified edition)**
6. F3: dasha-lord modifiers (BAV, combustion, retrograde, sandhi, tarabala).
7. F8: degree/orb and retro-grade pass handling for double transit.
8. Varshaphala year-lord (Panchavargiya Bala) from a verified Tajika edition.
9. BNN/Nadi trigger rules (corpus #67/#209) — modern-labelled if web-based.

**P2 — research only**
10. Narayana dasha, Sudarshana/Sarvatobhadra, Kalachakra/Ashtottari, KP
    sub-lords (separate ayanamsha), Prashna systems.

---

## 8. Intake candidates (for `research_intake.py`)

| ID | Claim to verify | Target | Candidate source | Class |
|---|---|---|---|---|
| IC-1 | Dasha-lord results are modified by the lord's Ashtakavarga bindus, tarabala, combustion and sandhi | `dasha_lord_modifiers` | Jataka Parijata (editions #124/#125) — passage to be located | verify |
| IC-2 | Jupiter/Saturn transit over significators triggers events (BNN) | `bhrigu_nandi_transit` | Bhrigu Nandi Nadi (#67 `[canon]`, #209 `[known]`) — edition check | verify |
| IC-3 | Tajika year-lord (varshesha) is elected via Panchavargiya Bala | `tajika_year_lord` | Tajika Neelakanthi translations (#150 `[verify]`) | verify |
| IC-4 | Chara dasha periods map to specific life events (count-minus-one) | `chara_event_mapping` | K.N. Rao (#206 `[known]`) | known |
| IC-5 | KP sub-lord of the significator times the event (Krishnamurti ayanamsha) | `kp_sub_lord` | KP Readers I–VI (#286 `[tech]`) | tech |

Promotion path: `python research_intake.py add ...` → curator checks the physical
edition → `verify --source-class canon|known` → only then encode with tests.
Web/YouTube sources verify as **modern-only** and can never ground a classical rule.

---

## 9. Bottom line

The engine already does the structurally honest thing: promise-gated,
multi-layer, source-declared windows that never collapse into a single date. The
research shows the next gains are not new techniques but (1) resolution and
merging fixes so the emitted windows match the reasoning, (2) a frozen
event-timing protocol so any future number is earned, and (3) two or three
source-gated modifiers (lord quality, year-lord, BNN triggers) once editions are
verified. Until then: windows are interpretive, no accuracy claim is made, and
the measurement gap is the roadmap — not the astrology.

_This document makes no efficacy claim. External studies are secondary summaries;
verify primaries before public use._
