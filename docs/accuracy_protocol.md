# SweetAstro Accuracy Evaluation Protocol (Pre-Registered)

**Protocol version**: 1.2.0
**Effective date**: 2026-09-13
**Status**: Frozen — any change to endpoints, windows, splits, or rules requires a new
protocol version and a fresh dataset; results from different protocol versions must
never be merged into one claim.

**Changelog**
- 1.2.0 (2026-09-13): model revision only (endpoints/windows/split/seed/weights
  unchanged). The natal promise gate is now active in the scored model
  (`PredictionHierarchy.predict`): when the net promise is obstructed (< −10), timing
  candidates are withheld instead of a best year/month. Withheld records count as
  automatic misses for hit-rate endpoints and are excluded from MAE (reported as
  `n_withheld`). Hierarchy levels 4–5 now score on the same ensemble scale as level 3.
  Requires a fresh freeze before scoring.
- 1.1.0 (2026-09-12): rules revision only (endpoints/windows/split/seed/weights unchanged).
  Rule exceptions now evaluated; unsupported condition types implemented (`in_sign`,
  `conjunct_with`, `dignity_at_least`, `transit_in_house`, `aspects_planet` with dasha lords
  and planet aliases); duplicate/dead rule conditions corrected (MAR-0026, MAR-0035,
  MAR-0042, MAR-0043); legacy absolute wording replaced with calibrated language.
  Requires a fresh freeze before scoring.
- 1.0.0 (2026-09-12): initial frozen baseline.

This protocol exists so that any accuracy claim by SweetAstro is *earned*: rules and
metrics are fixed **before** seeing outcomes, tested on a held-out split, and compared
against explicit chance baselines. Until that succeeds, the engine makes **no
predictive accuracy claim**.

---

## 1. Scope

Evaluated model: the legacy marriage-timing engine (`PredictionHierarchy.predict`),
which produces a best year, best month, and top-3 years per chart.

Out of scope for this protocol: the consumer Q&A engine (interpretive, not date-
predictive), remedies, vastu, and any non-marriage event.

## 2. Dataset requirements

- Verified birth data: date, time, timezone, coordinates.
- Verified marriage date with a documented source.
- Rodden rating per record; the **primary analysis includes only AA and A**.
- Records outside the search window (marriage before min age or after max age) are
  reported for *coverage* but are automatic misses.
- No post-hoc removal of charts that the engine gets wrong.
- The dataset file hash is frozen in the pre-registration manifest.

Required schema (JSON array or CSV) — see `data/test_charts/dataset_template.csv`:

| field | required | notes |
|---|---|---|
| chart_id | yes | unique |
| name | no | not used in evaluation |
| rodden | yes | AA / A / B / C / DD / X / XX |
| dob | yes | YYYY-MM-DD |
| tob | yes | HH:MM:SS (24h), local civil time |
| tz_offset | yes | decimal hours east of UTC |
| lat, lon | yes | decimal degrees |
| marriage_date | yes | YYYY-MM-DD |
| marriage_type | no | first / later |
| source | no | provenance string |

## 3. Frozen parameters

| Parameter | Value |
|---|---|
| Search window (ages) | **18 – 45 inclusive** |
| Primary endpoint | **Top-1 year exact hit** |
| Secondary endpoints | Top-3 year hit · hit within ±6 / ±12 / ±24 months · MAE (months) |
| Hit definition | predicted (year, month) vs actual within the window in whole months |
| Split | sha256(chart_id + seed) ranked → exact 70% train / 30% test (≥1 each side); **test is never used for tuning** |
| Split seed | 20260912 |
| Model weights | frozen defaults (`EnsembleWeights()`: 0.25/0.20/0.25/0.20/0.10); no fitting on test |
| Bootstrap | 2 000 resamples, seed 20260912, 95% percentile CI |
| Baselines | uniform-random age/month; modal age+month fitted on **train only**; permutation test (1 000 shuffles) |
| Included Rodden | AA, A (primary); all ratings reported as sensitivity |

## 4. Endpoints and decision rules

For each endpoint we report the engine value, the uniform-random baseline value with
95% CI, and the modal baseline value.

- **Success criterion (exploratory)**: engine beats the upper 95% bound of the
  uniform baseline on the primary endpoint **and** the permutation p-value < 0.05.
- **Failure criterion**: engine within the baseline CI → no demonstrated skill;
  the report must say so in plain language.
- Multiple-endpoint results are reported as secondary and are not "successes" unless
  the primary endpoint passes.
- A positive result from the seed (5-chart) dataset is uninterpretable; a fresh,
  pre-registered dataset of ≥ 500 verified charts (Rodden AA/A) is required before
  any public accuracy statement.

## 5. Anti-fabrication rules

1. No chart may be edited, added, or removed after the manifest is frozen.
2. Rules/weights are not changed between freeze and scoring.
3. Wide, overlapping "windows" that inflate hits must be pre-declared; the fixed
   ±6/±12/±24-month endpoints exist to prevent window fishing.
4. In-sample (train) numbers are always labelled and never presented as accuracy.
5. Failure is reportable; the default expectation from controlled studies is that the
   engine will not beat the baseline out-of-sample.

## 6. Procedure

```bash
# 1. Prepare dataset (≥500 verified charts for any real claim)
# 2. Freeze the pre-registration manifest (hashes protocol + dataset + rules)
python accuracy_backtest.py --freeze

# 3. Score the frozen run (refuses if dataset/rules changed since freeze)
python accuracy_backtest.py

# Output: reports/accuracy_<timestamp>.md and .json
```

## 7. Reporting template

Every report must contain: protocol version and hashes; dataset summary and coverage;
engine vs baselines with CIs for all endpoints; permutation p-value; calibration table;
per-chart appendix; and an explicit conclusion sentence that is either
"no demonstrated predictive skill" or "primary endpoint passed; requires independent
replication on a fresh dataset before any claim".

---

## 8. Errata

**Erratum 1 (2026-09-13) — split-hash description (protocol §3).**
The frozen parameter table describes the split as `sha256(chart_id + seed)` ranked with an
"exact 70% train / 30% test". The implemented and controlling split
(`src/evaluation/dataset.py: split_records`) is:

- rank by `sha256(f"{seed}:{chart_id}")` — seed **prefixed** with a colon separator, not
  appended;
- train count = `round(n * train_pct / 100)` clamped to at least one record per side
  (never an empty evaluation split).

This is a documentation correction only: the seed (20260912), the 70% fraction, the
deterministic ordering and the disjoint train/test split are unchanged, so no re-freeze
or re-scoring is required for this erratum alone. The implementation is controlling; the
frozen table is not silently edited.
