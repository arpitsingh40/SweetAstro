# SweetAstro — Final System Report

**Date**: 2026-09-13 · **Scope**: full codebase, audit round-2 backlog executed
· **Verification**: `tests/verify_calculations.py` 13/13 PASS; pytest 740 passed.

---

## 1. Purpose and design philosophy

A chat-based Vedic astrology answer engine whose central architectural rule is:
**the LLM never calculates or predicts astrology.** Every chart fact comes from
the deterministic engine; classical rules and statistical convergence produce
the analysis; the LLM only articulates it under a calibrated-language contract.
No accuracy claim is permitted without a passed pre-registered run
(`docs/accuracy_protocol.md`, v1.2.0).

Five-layer design:

```
User message
  → chat/orchestrator (extract → slots → route)
     → core/            deterministic astronomy & Jyotish math
     → interpretation/  promise, timing separation, money split
     → prediction/      convergence, ensemble, event timing, sensitivity
     → remedies/        catalog + safety gate + KAT + gemstone gate
     → chat/payload     "VERIFIED CHART DATA" (single source of chart truth)
  → DeepSeek (articulation only) → sanitizer → verify_answer → persistence
```

Support systems: `evaluation/` (pre-registered harness, rubrics, outcome
calibration), `knowledge/` (source-citation retrieval), `chat/memory.py`
(birth-fingerprint profiles + recall), SQL-free JSON persistence under
`data/chat_sessions/`.

## 2. Provenance ledger (what is sourced where)

| Subsystem | Method | Source / tradition |
|---|---|---|
| Ephemeris | Lahiri (Chitrapaksha) ayanamsha, sidereal longitudes | Swiss Ephemeris 2.10.03 (+Meeus/JPL fallback, precessed to equinox of date — §6.4) |
| Chart | whole-sign houses, dignities, combustion, Parashara drishti | BPHS; frozen `docs/astrology_spec_v1.0.md` |
| Vargas | shodashavarga + D5/D6/D8/D11 + cyclic D81/D108/D144 | BPHS Ch. 6–7; non-Parashari conventions declared per chart |
| Navamsa | continuous Parashari mapping, vargottama | BPHS; parity-tested |
| Dasha | Vimshottari MD→Prana, 365.2425-day solar year | BPHS; balance arithmetic hand-verified |
| Dasha (2nd/3rd) | Yogini (36-yr cycle), Chara (K.N. Rao count-minus-one) | tradition + declared convention docs |
| Strength | classical Shadbala six components, Ishta/Kashta, Rashmi minimums | BPHS as standardised by B.V. Raman, *Graha and Bhava Balas* |
| Strength (compat) | 360-point analytical index | **explicitly non-classical**, labelled everywhere |
| Planet factors | panchadha maitri, Baladi/Jagradadi/Deeptadi avasthas, sandhi/gandanta, graha yuddha, parivartana | BPHS (conventions declared) |
| Sensitive degrees | Pushkara Navamsa (degree ranges), Pushkara Bhaga (two traditions) | C. S. Patel, *Navamsa in Astrology*; Jataka Parijata Ch.1 v.58 |
| Vimshopaka | 20-point schemes, Vaiseshikamsa names | standard 4 schemes; D2 exception flagged "verify edition" |
| Jaimini | chara karakas (7, declared simplified), arudha/UL, argala | Jaimini Sutras; exception rules spec-frozen |
| Ashtakavarga | BAV/SAV tables, SAV=337 invariant | BPHS Ch. 66; invariants tested |
| Gochara | good-house sets, vedha pairs, Sade Sati | B.V. Raman standard |
| Matching | Ashtakoota 36-point, Mangal dosha + cancellations | standard Ashtakoota tables |
| Panchanga | drik ganita limbs + windows | verified against frozen DrikPanchang dataset (10 cases) |
| Muhurta | sourced filters (Rikta/Amavasya/Vishti/Rahu Kala/Abhijit) | Muhurta Chintamani, Nirnaya Sindhu, Kalaprakasika (`data/rules/muhurta_rules.json`) |
| Varshaphala | solar return, Muntha, Varsha lagna; year-lord strength omitted | Tajika (declared partial) |
| Rules engine | 52 marriage rules, condition DSL | BPHS, Phaladeepika, Jataka Parijata, Sarvartha Chintamani, Jaimini Sutras, Deva Keralam — verse-level provenance in each JSON |
| Remedies | catalog, safety gate, KAT (modern, labelled), gemstone gate | T7 sources; KAT research note; gemstone gate by design conservative |
| Knowledge | retrieval index of 537-entry bibliography | `docs/reference_library.md` + `docs/knowledge/` |

## 3. Working (end-to-end)

1. **Extraction** (LLM JSON, re-validated in Python) → birth slots + topic +
   answer mode/shape; unknown time handled with noon chart + reduced confidence.
2. **Routing**: outcome feedback · panchanga lookup · muhurta · vastu ·
   chart reading (verdict/timing/analysis/remedy/report shapes).
3. **Chart compute**: D1 → selected vargas → dashas → strengths (P0 factors
   always; classical Shadbala in deep mode) → transits → varshaphala → Jaimini
   → remedies + safety → structured answer.
4. **Payload**: verified facts block + full varga matrix (lookup) or deep
   planetary dossier + source references (the only citable sources).
5. **Articulation**: shape-specific prompt; streaming with reasoning separated.
6. **Safety net**: certainty sanitizer (newline-preserving), numeric
   `verify_answer`, report-voice + confidence contracts, promise-gate
   instructions, referrals, gemstone gate.
7. **Memory**: birth-fingerprint profile upsert, cross-session recall with
   disclosure; outcomes appended (with prediction snapshot) for calibration review.
8. **Web app (Phases 0-5 UI, 2026-09-13)**: React + Vite SPA at `/app`
   (`frontend/`, built into `src/api/static/app`). Onboarding birth form with
   geocode search; kundli SVG (North/South Indian) with PNG export; graha table
   with dignity/nakshatra; current dasha + ordered upcoming periods; birth
   panchanga; Today panchanga view; life Timeline page (120-year Mahadasha bar,
   age table, current-MD Antardashas); in-app Chat (SSE streaming, engine
   reasoning disclosure, markdown answers, one-click new chat); Muhurta page
   (sourced electional windows from `/api/timing`); PWA (manifest, icon,
   origin-scoped service worker at `/app/sw.js` with offline shell); and UI
   i18n in English / हिंदी / Hinglish. Backed by the stateless `POST /api/chart`;
   legacy pages remain unchanged at `/`, `/match`, `/dashboard`. Build via
   `.\dev.ps1 ui-build`, live-reload via `ui-watch`, full HMR via `dev-all`.

## 4. Verification evidence

- **Calculation report**: 13/13 PASS — ayanamsha, 8 grahas + ascendant vs
  Swiss Ephemeris (max diff 0.00000000°), fallback envelope (asc 0.0005°,
  planets 0.1528°), nakshatra/pada 13/13, navamsa 9/9, vargas 81/81,
  Vimshottari arithmetic 4/4, dataset recompute 5/5.
- **Tests**: 740 passed (2 slow; 26 round-6 + 3 report-voice + 11
  confidence-contract + 24 research-intake/source-class + 4 routing + 5
  provenance + 11 expectation-gap + 3 event-timing resolution + 9 web-app
  regressions), deterministic engine real, LLM mocked.
- **Accuracy protocol**: manifest re-frozen & valid (protocol 1.2.0; promise
  gate active, withheld records score as misses and are excluded from MAE);
  latest report: 0% top-1, MAE 93 months, p=1.0 on a 1-chart held-out split →
  correctly states *no accuracy claim possible*.
- **Chat quality**: golden payload cases 5/5; engine rubric 100/100.

## 5. Safety & honesty architecture (verified working)

No-certainty sanitizer · numeric verification (rounding-tolerant) · **single
canonical confidence per answer** (Low/Medium/High only; hybrid ranges like
"Low to Medium" are prompt-banned, rubric-flagged, and normalized to the
payload's level; the reason names evidence classes, never "N independent
factors agree"; the sensitivity window follows the stated precision — ±5 min
with a user-provided time, ±30 min when unknown — and caps are attributed to
chart sensitivity, not to doubt about the user's time) · promise gate (weak
promise → timing withheld from the payload *and* from the hierarchy model) ·
**report voice** (analytical report writer, never an emotionally supportive
companion: no empathy performatives, small talk, or reassurance; referrals are
formal advisories) · professional referrals
(health/legal/crisis/abuse; finance referral retired) · remedy cap (1 primary +
2 supporting) · gemstone never auto-recommended (verdict-composed note) · KAT
explicitly modern/optional · **sourced reasoning** (each answer's payload carries
a "Method provenance" block built only from the declared ledger — Vimshottari→BPHS,
D9→BPHS Ch. 6–7, Ashtakavarga→BPHS Ch. 66, Jaimini→Jaimini Sutras, etc.; the LLM
must cite these and never invent verses/authors, and no web/video source may
ground a classical value) · **expectation–capability assessment** (every payload
states what was asked, what is deliverable, what cannot be delivered and why —
weak promise, uncertain time, exact-date asks, past-event retrieval — and what
would unlock it; the reply must open with the gap) · **delivery check** (a reply
that still presents a timing window when the promise gate blocked it is corrected
deterministically before delivery) · source-citation guard ("never invent
verses") · birth-time reliability gating · memory-recall disclosure.

## 6. Audit round-2 findings — remediation closed (2026-09-13)

All HIGH items and the selected MEDIUM batch are fixed, each with regression
tests (`tests/test_audit_round6.py` plus earlier rounds for items closed before
this pass). The original findings are retained with their resolution.

HIGH:
1. `navamsa.py:72` D9 projected moolatrikona — **fixed earlier** (passes
   `allow_moolatrikona=False`).
2. `varshaphala.py:40` solar-return year — **fixed earlier** (search stays
   inside `target_year`).
3. `chart.py:210` + `strength.py:82` retrograde combustion orbs — **fixed
   earlier** (constants now applied).
4. `ephemeris.py` fallback frame — **fixed**: `frame_precession_deg()` precesses
   J2000 Keplerian longitudes to the equinox of date before the ayanamsha
   subtraction; regression asserts < 0.35° vs Swiss Ephemeris at 1900 (was
   ~1.4°).
5. Legacy accuracy labels — **fixed**: `backtest/metrics.py` renames
   `top_3_month_accuracy` → `within_2_months_share` and `calibration_score` →
   `high_confidence_top3_year_share`, and stamps `MACHINERY_VALIDATION_NOTE` on
   every summary; `/api/backtest/run` returns `accuracy_claim: false` +
   `claim_note`; CLI and dashboard carry the same guard.
6. `hierarchy.evaluate_promise` — **fixed**: an obstructed net promise (< −10)
   returns `indicated=False` and `predict()` withholds all timing candidates.
   This changes the protocol-scored model, so the protocol is bumped to
   **1.2.0** (changelog + fresh freeze); withheld records count as automatic
   misses for hit-rate endpoints and are excluded from MAE (`n_withheld`).
   The legacy blind runner/backtest dashboard now flags gated records the same
   way (`withheld: true`) instead of silently scoring the sentinel year 0.
7. Lal Kitab provenance — **fixed**: the consumer's third practice is now
   `modern_conduct_remedy` (declared "modern conduct"); `lal_kitab_remedy`
   remains only for practices with a verifiable edition/passage.
8. Final-text `safety_check` — **fixed earlier** (runs in `_finalize`).
9. Gemstone note — **fixed**: `format_gemstone_note()` composes the note from
   the verdict's safety class; "Unsuitable now" can no longer contradict
   consider-with-verification or suppressed mention.
10. Marriage-question misroute (late find, 2026-09-13) — **fixed**:
   `_topic_key` and `vargas_for_question` used substring matching, so "ill"
   inside "will" classified "When will I get married?" as *health* and selected
   the wrong vargas. Routing now uses whole-word matching
   (`src/core/keywords.py`: `matches_any`), with "married/marriage/shaadi"
   added to the marriage keywords.

MEDIUM (all closed):
- finance referral promise removed from chat prompts and prompt templates
  (retired — the safety gate never had a concrete referral to emit);
- sanitizer and rubric share one `BANNED_ABSOLUTE` list
  (`src/llm/calibrated_language.py`); every banned phrase has a rewrite;
- timing blocks (dasha boundaries, personal timeline, prediction block) are
  omitted from the LLM payload itself when the promise is weak, with an
  explicit `TIMING WITHHELD` marker;
- `probability_pct` renamed `score_share_pct` — it is a share of the summed
  model score, not a probability;
- protocol split-hash description corrected via published **Erratum 1**
  (implementation hashes `f"{seed}:{chart_id}"` and rounds the train count);
- legacy 933-line `marriage_timing.py` relabelled LEGACY (kept for analysis/
  back-compat; unused by production);
- `llm/explainability.py` rewritten: no "clear fruition"/"genuine marital
  union"/planetary grace claims; gated predictions handled; disclaimer added;
- backtest metric names corrected (see HIGH 5);
- `verify_answer` degree checks are rounding-tolerant (half of the last shown
  decimal place);
- hierarchy levels 3–5 all score on the `SystemEnsemble` scale (no
  `calibrated_score` mixing), including `best_month_score`.

LOW (remaining; not part of this pass): payload text says 16+4 vargas (actual
23); promise evaluates fewer houses than it documents; dead High-confidence
branch; hardcoded user path in `fetch_panchanga_reference.py`; muhurta default
range 45 vs max 120; README/doc counts drifted. (The stale health label
"Marriage Engine v1.0" was corrected with HIGH 5.)

**Fixes applied in round 1** (for context): Kala Sarpa arc, natal vara
timezone, sanitizer newlines, varga moolatrikona, fallback Moon speed, D9
convergence branch, `is_lord_of_house`, consumer KeyError guard, muhurta
confirmation state, event-timing truncation disclosure, window-merge
confidence ranking, arudha single-source, transit tz contract, panchanga
fallback.

## 7. Deliberate deferrals (never guessed)

- **Mrityu Bhaga** — structure + Moon row + spot values verified; a value
  conflict (Moon Capricorn 20 vs 25) and a fabricated-looking row block
  encoding. Needs Jataka Parijata (library 124/125) + Sarvartha Chintamani
  (126/211) book check. Plan ready in `docs/research/mrityu_bhaga.md`.
- **True Chesta Kendra** — mean planetary elements; speed-ratio convention
  currently declared in-module.
- **Goel-style varga-linking** — requires the licensed book.
- **Bhava Digbala** — needs a declared bhava-madhya source.
- **Accuracy** — no claim; protocol gates at ≥500 verified records
  (manifest re-frozen at protocol 1.2.0).

*Status 2026-09-13 (audit-round-2 pass): unchanged — none of the sources above
became available, and nothing was encoded from memory or inference. These stay
blocked until a verifiable edition/passage is checked.*

**Event-timing deep research (2026-09-13)**: `docs/research/event_timing_deep.md`
— method-by-method audit of the timing stack (F1–F10). F1 is fixed: transit
membership is now computed across each window from 5-day samples with bisected
sign-change instants, transit evidence is interleaved so it cannot be truncated
away, and the method notes disclose a measured birth-time sensitivity per chart
("±5 min moves dasha boundaries by N days"). Remaining P0: window merging,
travel promise mapping, Yogini cross-check wiring, and the event-timing
evaluation protocol (1.3.0) that must be frozen before any timing weight is
touched.

### Research intake gate (added 2026-09-13)

Sourced claims are never researched by the live model. They enter an
append-only quarantine and can only be promoted by an explicit human
verification with a complete citation (source title + edition + locator +
verifier name):

```bash
python research_intake.py add --claim "..." --target mrityu_bhaga \
    --source "Jataka Parijata" --edition "Subrahmanya Sastri translation" --locator "Ch. 1 v. 58"
python research_intake.py list
python research_intake.py verify RC-0001 --verifier "curator" --note "physical copy checked"
python research_intake.py reject RC-0002 --reason "Edition could not be located"
python research_intake.py report
```

- Store: `data/research_intake/{drafts,decisions}.jsonl` — append-only and auditable.
- Drafts are quarantined and locked out of the answer path by tests; only
  `servable_claim_lines()` (verified claims) is opt-in, and promotion into
  computed engine data stays a reviewed, tested code change.
- **Reliable-source test**: every claim carries a `source_class` —
  `canon` (classical text + edition + verse/page), `known` (published work),
  `tech` (modern technique, labelled), `verify` (real tradition, edition
  unchecked — cannot be promoted), `web` (video/lesson with URL; verified as
  modern-only and excluded from default serving, so it can never ground a
  classical value).
- The gate refuses: missing citation fields, an empty verifier, promoting a
  `verify`-class source, a `web` source without URL, rejecting a verified
  claim, and silent deletion (`src/knowledge/intake.py`).

## 8. Bottom line

The engineering architecture is sound, deeply tested, and honest: deterministic
math is verified to Swiss Ephemeris precision, classical methods carry declared
conventions and provenance, safety is layered, and unsourced material is
refused rather than invented. The audit round-2 backlog is now closed for every
HIGH item and the selected MEDIUM batch (protocol bumped to 1.2.0 with a fresh
freeze, so old and new results are never merged). The remaining LOW items and
the research-gated deferrals in §7 are the honest gap list; until a verifiable
source is checked, those outputs stay deliberately absent rather than guessed.
No accuracy claim is made or implied anywhere.
