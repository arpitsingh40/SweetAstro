"""Markdown report renderer for accuracy evaluation results."""

from __future__ import annotations

from typing import Dict

from .harness import EvaluationResult


def _verdict(result: EvaluationResult) -> str:
    engine_top1 = result.engine_test.get("top1_year", 0.0)
    uniform_hi = result.uniform_baseline.get("top1_hi", 100.0)
    p_value = result.permutation.get("p_value", 1.0)
    if result.n_test < 30:
        return (
            f"**No accuracy claim is possible from this run** — the held-out test split has only "
            f"{result.n_test} chart(s). Results are shown for methodology validation only. "
            "A dataset of ≥500 verified charts (Rodden AA/A) is required before any public claim."
        )
    if engine_top1 > uniform_hi and p_value < 0.05:
        return (
            "**Primary endpoint passed on this test split** (engine beats the uniform-random 95% "
            "bound and permutation p < 0.05). This is a single pre-registered run; independent "
            "replication on a fresh dataset is required before any accuracy claim."
        )
    return (
        "**No demonstrated predictive skill.** The engine's primary endpoint is within the "
        "chance-baseline range on the held-out split. Per protocol, no accuracy claim may be made."
    )


def render_markdown(result: EvaluationResult) -> str:
    m = result.manifest
    v = result.validation
    lines = []
    lines.append("# SweetAstro Accuracy Backtest Report")
    lines.append("")
    lines.append(f"- Generated (UTC): `{result.generated_utc}`")
    lines.append(f"- Protocol: **v{result.protocol_version}** ({result.dataset_path})")
    lines.append(f"- Runtime: {result.runtime_seconds}s")
    lines.append("")
    lines.append("## Frozen pre-registration")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append(f"| Protocol version | {m['protocol_version']} |")
    lines.append(f"| Dataset SHA-256 | `{m['dataset_sha256'][:16]}…` |")
    lines.append(f"| Rules SHA-256 | `{m['rules_sha256'][:16]}…` |")
    lines.append(f"| Search window | ages {m['search_window']['min_age']}–{m['search_window']['max_age']} |")
    lines.append(f"| Split | {m['split']['train_pct']}% train / {100 - m['split']['train_pct']}% test, seed {m['split']['seed']} |")
    lines.append(f"| Primary endpoint | {m['primary_endpoint']} |")
    lines.append("")
    lines.append("## Dataset")
    lines.append("")
    lines.append(f"- Records: **{v['n_records']}** ({v['n_primary']} Rodden AA/A included in primary analysis)")
    lines.append(f"- Rodden distribution: {v['rodden_counts']}")
    lines.append(f"- Outside search window: {len(v['outside_window'])} {v['outside_window'] or ''}")
    lines.append(f"- Duplicate-birth warnings: {len(v['duplicates'])}")
    lines.append(f"- Held-out split: **{result.n_train} train / {result.n_test} test** (AA/A only)")
    lines.append(f"- Test coverage (actual marriage inside window): {result.coverage_pct}%")
    for warning in v["warnings"]:
        lines.append(f"- ⚠️ {warning}")
    lines.append("")
    lines.append("## Headline results (held-out test split)")
    lines.append("")
    lines.append("| Metric | Engine | Engine 95% CI | Uniform baseline | Uniform 95% range | Modal baseline |")
    lines.append("|---|---|---|---|---|---|")
    et, ci, ub, mb = result.engine_test, result.engine_test_ci, result.uniform_baseline, result.modal_baseline
    lines.append(
        f"| Top-1 year | {et['top1_year']}% | [{ci['top1_year']['lo']}, {ci['top1_year']['hi']}] | "
        f"{ub['top1_year']}% | [{ub['top1_lo']}, {ub['top1_hi']}] | {mb['top1_year']}% |"
    )
    lines.append(
        f"| Hit within ±12 months | {et['hit_within_12_months']}% | [{ci['hit_12m']['lo']}, {ci['hit_12m']['hi']}] | "
        f"{ub['hit_12m']}% | [{ub['hit_lo']}, {ub['hit_hi']}] | {mb['hit_12m']}% |"
    )
    lines.append(
        f"| MAE (months) | {et['mae_months']} | [{ci['mae_months']['lo']}, {ci['mae_months']['hi']}] | — | — | — |"
    )
    lines.append("")
    lines.append(f"- Top-3 year: engine {et['top3_year']}%")
    lines.append(f"- Permutation test (Top-1 year): **p = {result.permutation['p_value']}** "
                 f"(observed {result.permutation['observed_top1_pct']}%)")
    if et.get("n_withheld"):
        lines.append(f"- Promise gate withheld timing on **{et['n_withheld']}** record(s) "
                     "(counted as misses; excluded from MAE).")
    lines.append("")
    lines.append("## Secondary / sensitivity")
    lines.append("")
    lines.append(f"- Train split (in-sample, **not** evidence): Top-1 {result.engine_train['top1_year']}%, "
                 f"MAE {result.engine_train['mae_months']} months")
    lines.append(f"- All ratings on test (AA/A included): Top-1 {result.engine_test_all_ratings['top1_year']}%, "
                 f"MAE {result.engine_test_all_ratings['mae_months']} months")
    lines.append(f"- Modal baseline fitted on train: age {mb['modal_age']}, month {mb['modal_month']}")
    lines.append("")
    lines.append("## Calibration (indicative)")
    lines.append("")
    lines.append("| Engine score bin | n | Top-1 year | Hit ±12m |")
    lines.append("|---|---|---|---|")
    for row in result.calibration:
        lines.append(f"| {row['bin']} | {row['n']} | {row['top1_year'] if row['top1_year'] is not None else '—'} | "
                     f"{row['hit_12m'] if row['hit_12m'] is not None else '—'} |")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(_verdict(result))
    lines.append("")
    lines.append("## Per-chart test appendix")
    lines.append("")
    lines.append("| Chart | Rodden | Predicted | Actual | Error (months) | Top-1 |")
    lines.append("|---|---|---|---|---|---|")
    for row in result.per_chart_test:
        error = row['error_months'] if row['error_months'] is not None else 'withheld'
        lines.append(
            f"| {row['chart_id']} | {row['rodden']} | {row['predicted']} | {row['actual']} | "
            f"{error} | {'✅' if row['top1'] else '❌'} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("_Astrology is a traditional interpretive system, not established predictive "
                 "causation. This report measures engineering performance only. A negative result "
                 "here does not invalidate the chart calculations, which are independently "
                 "verified against Swiss Ephemeris (`tests/test_calculation_backtest.py`)._")
    return "\n".join(lines)
