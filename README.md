# SweetAstro Marriage Timing Engine 💍

> **North-star objective**: Build an engine that answers one narrow question exceptionally well:  
> *"When is this person's marriage most likely to occur?"*

**V2 — Chat Mode**: SweetAstro now ships as a fully chat-based **Consumer Astrology Answer Engine**. You talk naturally (any astrology question, not just marriage); it extracts your birth details, computes the chart deterministically, and answers with DeepSeek in a calibrated 16-section format with optional, chart-specific traditional remedies. See [Chat Mode](#chat-mode-consumer-astrology-answer-engine).

SweetAstro is a world-class, backtested Vedic astrology prediction system engineered according to a 51-point architectural blueprint. It separates pure astronomical calculation, machine-readable classical rule evaluation, and statistical ensemble modeling from conversational natural-language presentation.

---

## The 5 Core Systems

```
                    SWEETASTRO
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
   CHART ENGINE     RULE ENGINE      EVENT DATABASE
        │               │                │
        └───────────────┼────────────────┘
                        ▼
                 PREDICTION ENGINE
                        │
                        ▼
                  BACKTESTING LAB
                        │
                        ▼
                  LLM INTERFACE
```

1. **Astronomical / Chart Engine (Deterministic)**:
   - Sidereal calculation using **Lahiri (Chitra Paksha) Ayanamsha** (SA-SPEC-V1.0).
   - Complete **D1 (Rashi)** chart: Ascendant (Lagna), planetary signs, houses, lords, dignities, retrogression, combustion, and Parashara standard aspects.
   - Complete **D9 (Navamsa)** chart: Navamsa signs, Pada mapping, Navamsa Lagna, and 7th house lord.
   - **Vimshottari Dasha Engine**: Exact balance of birth dasha from Moon nakshatra, calculating Mahadasha (MD), Antardasha (AD), and Pratyantardasha (PD) using 365.2425 days/year solar standard.
   - **Transit (Gochara) Engine**: Historical and future search for Jupiter, Saturn, Rahu, and Ketu. Evaluates the classical **Double Transit Principle** (simultaneous activation of 7th house/lord/Lagna).
   - **Jaimini Engine**: 7 Chara Karakas (Atmakaraka AK down to Darakaraka DK for spouse), Upapada Lagna (UL), and Arudha Lagna (AL).

2. **Classical Rule Engine & Knowledge Graph**:
   - Machine-readable JSON rule library with strict textual provenance (Brihat Parashara Hora Shastra, Phaladeepika, Jataka Parijata, Deva Keralam, Jaimini Sutras).
   - 7 canonical categories: Marriage Promise, Delay, Dasha Timing, Transit Timing, Jaimini, Stability, and Remarriage.
   - Relational Knowledge Graph connecting 7th house, 7th lord, Venus, Jupiter, D9, Dasha, and Transits.

3. **Historical Event Database**:
   - High-confidence benchmark charts (Rodden Rating AA/A from official registries) with verified marriage dates.

4. **Prediction & Ensemble Engine**:
   - **Progressive Time Hierarchy**: Level 1 (Promise) $\to$ Level 2 (Age Bracket) $\to$ Level 3 (Year) $\to$ Level 4 (Quarter) $\to$ Level 5 (Month).
   - **Convergence Score**: Tally of positive evidence minus negative obstruction (Point 19 & 20).
   - **Birth-Time Uncertainty Engine**: Perturbations across $\pm 10$ minutes in 2-minute steps to measure temporal stability (Point 21 & 22).
   - **Multi-System Ensemble**: Combines Parashari, D9, Vimshottari, Transits, and Jaimini.

5. **Backtesting Lab**:
   - Strict **Blind Evaluation**: Engine generates prediction and stamps immutable `Prediction ID` (e.g. `SA-MAR-000001`) *before* ground truth marriage date is revealed.
   - Metrics: top-1/top-3 year hit rates, mean absolute error (MAE) in months, 95% confidence intervals, and a high-confidence top-3 share. On the seed set these are **machinery validation only — not an accuracy claim**; the dashboard and API surface that guard explicitly.
   - **Method Tournaments & Rule Leaderboards**: Empirically compares Model 1 (Parashari only) through Model 5 (Full Ensemble).

6. **LLM Calibrated-Answer Layer** (absolute date claims retired per `docs/accuracy_protocol.md`):
   - **Calibrated window mode**: presents the clearest window the model indicates as an interpretive estimate, never a promise (*"The clearest window this model indicates is around March 2028."*).
   - **"Why this window?"**: Multi-system convergence breakdown.
   - **"Why not other months?"**: Internal comparative scores across all 12 candidate months.
   - Internal score distribution (score shares, not probabilities), stability scores, and evidence metadata strictly preserved.
   - Answer shapes adapt to the ask (verdict / timing / analysis / remedy / full report); full 16-section reports only on request.

---

## Directory Layout

```
SweetAstro/
├── docs/
│   ├── astrology_spec_v1.0.md      # Frozen mathematical specification
│   ├── rule_schema.json            # JSON Schema for classical rules
│   ├── reference_library.md        # 520 curated source volumes (astrology/Vastu/remedies)
│   ├── knowledge/                  # Per-source knowledge + full Vastu corpus (04)
│   └── architecture.md             # System architecture & data flow
├── data/
│   ├── rules/                      # Structured classical rules with provenance
│   │   ├── mar_*.json              # 52 marriage rules (v1 + v2 generations)
│   │   ├── muhurta_rules.json      # Sourced electional filters
│   │   ├── vastu_rules.json        # Vastu directions/defects/practices
│   │   └── remedies_kat.json       # KAT alignment triangles (modern, labelled)
│   ├── reference/
│   │   └── panchanga_drikpanchang.json  # Frozen DrikPanchang verification cases
│   └── test_charts/
│       └── historical_verified.json # Verified historical validation set
├── src/
│   ├── core/                       # Astronomical & chart calculation engine
│   ├── rules/                      # Classical rule catalog, evaluator, knowledge graph
│   ├── prediction/                 # Hierarchy, convergence scoring, sensitivity, ensemble, event timing
│   ├── backtest/                   # Blind runner, metrics, method tournaments
│   ├── evaluation/                 # Pre-registered harness, rubrics, outcome calibration
│   ├── interpretation/             # Promise gate, timing separation, money split
│   ├── llm/                        # Calibrated answer synthesis, explainability, prompts
│   ├── remedies/                   # Catalog, safety gate, KAT, gemstone gate
│   ├── chat/                       # Chat orchestrator, DeepSeek client, extractor, payload, memory
│   ├── knowledge/                  # Source-citation retrieval over docs/knowledge
│   ├── api/                        # FastAPI app + chat UI (static/chat.html)
│   └── service.py                  # Unified SweetAstro engine API
├── tests/                          # Comprehensive pytest test suite
├── .env                            # DEEPSEEK_API_KEY (git-ignored)
├── serve.py                        # Chat server entry point
└── run_sweetastro.py               # Interactive CLI demonstration
```

---

## Quick Start & Execution

### 0. Install dependencies & configure the DeepSeek API key

```bash
pip install -r SweetAstro/requirements.txt
python SweetAstro/fetch_ephemeris.py     # official Swiss Ephemeris .se1 data files
```

Create `SweetAstro/.env` (already git-ignored):

```bash
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

### 1. Launch the chat app
```bash
python SweetAstro/serve.py
```
Open **http://127.0.0.1:8088** — the chat UI. The legacy testing dashboard lives at `/dashboard`.

### 2. Run Interactive CLI Demo
```bash
python SweetAstro/run_sweetastro.py
```

### 3. Run the test suite (fast & scoped)
```bash
python -m pytest                  # full suite (~5-6 s) — pytest.ini locks scope to tests/
python -m pytest -m "not slow"    # fast dev loop (~4 s)
.\dev.ps1 test-fast               # same, works from any directory
.\dev.ps1 test-quick              # last-failed only, stop at first failure (fastest loop)
```

> **Reading this from the parent folder (`Documents\Code`)?** Never run a bare
> `pytest` there — it scans and runs **every sibling project's tests**
> (Smartdecision, SolarDeals, ...), which is what makes a test run look endless.
> Use either of these instead:
> ```bash
> python -m pytest SweetAstro/tests -q     # explicit path scopes collection
> SweetAstro\dev.ps1 test-fast             # wrapper that fixes the working dir
> ```

> **Can a test run ever hang now? No.** Two enforced layers:
> 1. `pytest-timeout` kills any single test at **60 s** with a stack dump naming it (pytest.ini).
> 2. `dev.ps1` watchdog-kills the whole run at **`-RunTimeoutSeconds`** (default 300 s),
>    terminates the process tree, and returns exit code **124** — so deploys abort instead
>    of hanging. Verified: a 30-second hanging test was killed in 3.9 s, and a full run
>    with a 1 s limit was killed at 1 s with exit 124.

### 4. One-command verify & deploy
```bash
.\dev.ps1 verify               # preflight: deps, ephemeris, chart self-test, LLM, port, geocoder
.\dev.ps1 deploy               # preflight -> fast tests -> restart server -> health check
.\dev.ps1 deploy -SkipTests    # preflight -> restart -> health (no test run)
.\dev.ps1 accuracy             # pre-registered accuracy backtest -> reports/
```

### 3. Programmatic Usage in Python
```python
from SweetAstro.src.service import SweetAstroEngine

engine = SweetAstroEngine()

# Ask any astrology question (calibrated windows — no absolute date claims)
result = engine.answer_question(
    year=1995, month=5, day=15,
    hour=14, minute=30, second=0.0,
    tz_offset=5.5,
    lat=28.6139, lon=77.2090,
    place="New Delhi, India",
    question="When will I get married?",
)

# Calibrated output (the chart's actual window language lives in the answer)
print(result.answer.confidence)            # Low / Medium / High
print(result.timing.current_md_ad_pd)      # e.g. Mercury MD / Jupiter AD / Venus PD
print(result.answer.to_markdown()[:400])   # evidence-structured, gated answer
```

---

## Chat Mode (Consumer Astrology Answer Engine)

The chat app implements the 16-section Consumer Astrology Answer Engine contract:
deterministic calculation → multiple independent confirmations → correct timing →
transparent reasoning → appropriate alignment → safe traditional remedies →
practical advice → calibrated confidence. **The LLM never calculates astrology.**

### How a turn works

```
User message
   │
   ▼
1. DeepSeek JSON extraction ──► birth slots (dob, tob, place, tz, question, topic)
   │                                │ missing? ──► guide reply asks for it
   ▼
2. Deterministic engine (SweetAstro core + consumer.py)
   │   Lahiri sidereal D1/D9/vargas, Nakshatra-Pada, Vimshottari MD/AD/PD with
   │   exact boundaries, full-chain strength (dispositor, nakshatra lord, Shadbala,
   │   yogas), topic-selected vargas, remedies + gemstone gate, safety referrals
   ▼
3. "VERIFIED CHART DATA" payload ──► DeepSeek Flash streams the answer
   │   (reasoning deltas kept separate; certainty language sanitized server-side)
   ▼
4. Answer persisted to the session; follow-ups reuse the same chart
```

### Behaviour guarantees

- **Never guesses positions** — all chart facts come from the deterministic engine; if a
  fact is absent (e.g. birth time unknown) the engine lowers confidence and says so.
- **Never judges from one placement** — every statement cites the full chain.
- **No certainty language** — "Jyotish indicates…", "The chart suggests…"; a server-side
  sanitizer rewrites absolute phrasing as a final safety net.
- **Remedies are optional and chart-specific** — max 1 primary + 2 supporting, each with
  purpose, timing, duration, safety note and suitability; Lal Kitab is labelled distinctly;
  gemstones are gated and scored, never automatic; health/legal/finance questions add referrals.
- **KAT domain alignment (modern, labelled)** — the Karma Alignment Technique triangle
  framework (Rahul Kaushik, based on Bhrigu Nandi Nadi) is offered as an optional
  zero-cost alignment option (`data/rules/remedies_kat.json`, research:
  `docs/research/rahul_kaushik_kat.md`); it is never presented as a guarantee.
- **Backtesting mode** — past events shared by the user are passed through with the
  rule-first / in-sample-is-not-proof caveats.

### API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/chat/stream` | SSE stream: `session`, `status`, `meta`, `delta` (content/reasoning), `done`, `error` |
| `POST` | `/api/chat` | Non-streaming JSON reply (same pipeline) |
| `GET` | `/api/chat/session/{id}` | Session snapshot (messages, slots, chart basis) |
| `DELETE` | `/api/chat/session/{id}` | Reset a session |
| `GET` | `/api/chat/config` | Active model + key availability |

### Tests

```bash
pytest SweetAstro/tests/test_chat.py -v
```

The chat tests use a fake LLM client; all chart computation is the real deterministic engine.

---

## Chart Accuracy & Verification

Charts are computed with **Swiss Ephemeris** (`pyswisseph`) in Lahiri/Chitrapaksha
sidereal mode — the reference implementation used by professional Vedic astrology
software and derived from JPL DE ephemerides. Official `.se1` data files live in
`data/ephe/` (fetch with `python fetch_ephemeris.py`).

If `pyswisseph` is unavailable, the engine falls back to a built-in Meeus model
(planets within ~0.15°, ascendant regression-tested); the active backend is
reported by `/api/health` and in every reading's calculation note.

### Verification suite (backtest against trusted sources)

```bash
python tests/verify_calculations.py          # human-readable report, exit 0 = all pass
pytest tests/test_calculation_backtest.py -v # 134 automated checks
```

Every calculation method is backtested against:

- **Swiss Ephemeris 2.10.03** direct calls — ayanamsha, 9 graha longitudes,
  ascendant across both hemispheres and high latitudes, plus frozen reference
  values (J2000, 1900/1950/2050) so regressions are caught without the library.
- **Hand-computed classical rules (BPHS)** — nakshatra/pada boundaries, Navamsa
  D9 mapping, divisional charts D2–D60, Vimshottari balance-of-dasha arithmetic
  (including partially elapsed Mahadasha/Antardasha cases), dasha sequence
  integrity and proportionality.
- **Historical dataset** — all verified charts recompute cleanly end to end.

A fallback-accuracy test pins the built-in engine's envelope, including a
regression guard for the ascendant formula (an earlier version returned the
descendant, exactly 180° off).

---

## Accuracy Backtest (Pre-Registered, Baseline-Controlled)

Calculations are verified; **prediction accuracy is measured, not assumed**.
The protocol (`docs/accuracy_protocol.md`, v1.2.0) freezes endpoints, windows,
split, and rules before scoring and compares the engine against explicit chance
baselines. The scored model applies the natal promise gate: when the net promise
is obstructed, timing is withheld and the record counts as a miss (excluded from
MAE, reported as `n_withheld`):

```bash
python accuracy_backtest.py --freeze   # freeze protocol + dataset + rules hashes
python accuracy_backtest.py            # score the frozen run (aborts if anything changed)
```

Every run outputs `reports/accuracy_<timestamp>.md` + `.json` containing:

- engine metrics (Top-1/Top-3 year, hit ±6/±12/±24 months, MAE) on the held-out split
- uniform-random baseline (2 000 simulations, 95% interval) and modal baseline (train-fitted)
- permutation test p-value, bootstrap CIs, and confidence calibration table
- an explicit verdict: no demonstrated predictive skill, or primary endpoint passed
  (which still requires replication on a fresh ≥500-chart Rodden AA/A dataset)

The seed dataset (5 charts) exists to validate the *machinery*; no accuracy claim may
be made from it. To run a real claim, supply a dataset using
`data/test_charts/dataset_template.csv` (any CSV/JSON with the documented schema),
then freeze and score once.

---

## Panchanga & Muhurta (Verified Deterministic Timing)

The one astrology domain that is fully computable and verifiable — implemented and
tested against authentic published data:

- **Panchanga (drik ganita)**: sunrise/sunset, tithi, vara, nakshatra, yoga, karana
  with exact end times, Rahu Kalam, Yamaganda, Gulika Kalam, Abhijit muhurta,
  moon/sun signs, Lahiri ayanamsha.
- **Muhurta**: sourced rule sets (`data/rules/muhurta_rules.json` — Muhurta Chintamani,
  Nirnaya Sindhu, Kalaprakasika) filter Rikta tithis (4/9/14) and Amavasya, Vishti
  (Bhadra) karana and Rahu Kala, and return clean Abhijit windows.

```python
from SweetAstro.src.core.panchanga import compute_panchanga
from SweetAstro.src.core.muhurta import find_muhurta_days

day = compute_panchanga(2026, 9, 12, tz_offset=5.5, lat=28.6356, lon=77.2244, elevation_m=212)
print(day.tithi_name, day.nakshatra, day.rahu_kalam)

windows = find_muhurta_days(date(2026, 9, 12), date(2026, 9, 30), 5.5, 28.6356, 77.2244, "vivaha")
```

REST: `GET /api/panchanga?date=2026-09-12&lat=28.6356&lon=77.2244&tz_offset=5.5&elevation=212`

**Authentic-source verification**: `tests/test_panchanga.py` (54 checks) validates
every limb and window against reference values extracted from **DrikPanchang.com**
(drik ganita, Lahiri) — 10 cases across all 7 weekdays, both pakshas, summer and
winter, two locations — frozen in `data/reference/panchanga_drikpanchang.json`.
Refresh with `python fetch_panchanga_reference.py`.
