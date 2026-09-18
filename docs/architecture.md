# SweetAstro Architecture & Data Pipeline

## 1. System Philosophy: Separation of Calculation, Rules, Scoring, and LLM

SweetAstro adheres strictly to the rule: **Never let an LLM calculate or predict astrology.**
The prediction is derived deterministically from classical rules and statistical convergence over astronomical ephemerides. The LLM is strictly an articulation and conversational interface.

```
+-------------------------------------------------------------------------------+
|                             SWEETASTRO PLATFORM                               |
+-------------------------------------------------------------------------------+
  |
  +--> System #1: ASTRONOMICAL & CHART ENGINE (Pure Deterministic)
  |     - Sidereal Lahiri Ayanamsha
  |     - D1 (Rashi, Houses, Lords, Dignities, Aspects, Retro, Combustion)
  |     - D9 (Navamsa placements & Navamsa Lagna)
  |     - Nakshatras & Padas
  |     - Vimshottari Dasha Engine (MD, AD, PD - Solar year standard)
  |     - Gochara (Jupiter, Saturn, Rahu, Ketu double-transit activations)
  |     - Jaimini Chara Karakas (DK, AK) & Upapada Lagna (UL)
  |
  +--> System #2: CLASSICAL RULE ENGINE & KNOWLEDGE GRAPH
  |     - Catalog of structured rules with classical provenance (BPHS, Phaladeepika, etc.)
  |     - 7 Standard Categories: Promise, Delay, Timing, Relationships, Type, Stability, Remarriage
  |     - Knowledge Graph: Relational connections between 7th house, lord, Venus/Jupiter, D9, Dasha, Transits
  |
  +--> System #3: HISTORICAL EVENT DATABASE & VALIDATION SETS
  |     - High-confidence birth data (Rodden Rating AA/A) with exact official marriage dates
  |     - Temporal train/validation/test splitting to prevent future-data leakage
  |
  +--> System #4: PREDICTION & ENSEMBLE ENGINE
  |     - Progressive Time Hierarchy: Promise -> Age Window -> Year -> Quarter -> Month
  |     - Birth-Time Uncertainty Engine: Perturbation across +/- 10 min window to measure stability
  |     - Positive and Negative Evidence Convergence Tally
  |     - Multi-System Ensemble: Parashari + D9 + Vimshottari + Transit + Jaimini
  |
  +--> System #5: BACKTESTING LAB & EMPIRICAL BENCHMARKS
  |     - Blind Backtest Harness (Engine receives birth info only, predicts date, then reveals outcome)
  |     - Metrics: Top-1 Accuracy, Top-3 Accuracy, MAE in months, Calibration Curves
  |     - Method Tournaments and Individual Rule Leaderboards
  |
  +--> System #6: LLM INTERFACE & CALIBRATED ANSWER LAYER
        - Calibrated window mode ("The clearest marriage window this model indicates is around March 2028 —
          interpretive estimate, not a prediction."; absolute date claims are retired per docs/accuracy_protocol.md)
        - Structured Explainability ("Why March 2028?", "Why not other months?")
        - Longitudinal Outcome Tracking with immutable Prediction IDs (e.g. SA-MAR-000001)
```

## 2. Progressive Time-Resolution Hierarchy

```
LEVEL 1: Marriage Promise
   ├── Evaluation of 7th house, 7th lord, Venus, D9 Lagna
   └── Verdict: Strong Promise / Delayed / Obstructed
           │
           ▼
LEVEL 2: Age Range
   ├── Malefic delays (Saturn aspect, 6/8/12 occupation, combustion)
   └── Candidate Age Bracket (e.g. 27–32 years)
           │
           ▼
LEVEL 3: Candidate Years
   ├── Vimshottari Mahadasha / Antardasha filtering
   ├── Jupiter & Saturn Double Transit activation of 7th/Lagna
   └── Ranked Year Probabilities (e.g. 2027: 18%, 2028: 59%, 2029: 15%)
           │
           ▼
LEVEL 4: Candidate Quarters
   ├── Antardasha / Pratyantardasha shift points
   └── Ranked Quarter Scores (e.g. Q1 2028: 72%, Q2 2028: 18%)
           │
           ▼
LEVEL 5: Candidate Months
   ├── Pratyantardasha exact window
   ├── Jupiter transit aspect window
   └── Ranked Monthly Scores (Jan: 61, Feb: 74, Mar: 93, Apr: 78)
           │
           ▼
LEVEL 6: Calibrated Output with Explainability
   └── Final Output: "The clearest window this model indicates is around March 2028
       (interpretive estimate; no accuracy claim without pre-registered evaluation)."
```
