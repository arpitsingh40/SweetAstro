"""
SweetAstro Interactive CLI Demonstration.
Runs sample predictions, blind backtesting benchmark, and method tournaments.
"""

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from SweetAstro.src.service import SweetAstroEngine


def main():
    print("======================================================================")
    print("     SWEETASTRO LEGACY MARRIAGE-TIMING DEMO (calibrated language)     ")
    print("  No date or accuracy claim: docs/accuracy_protocol.md               ")
    print("======================================================================")

    engine = SweetAstroEngine()

    print("\n[1] Running Demonstration Prediction on Sample Chart...")
    print("    Input: DOB 1995-05-15, 14:30:00 (New Delhi, India)")

    answer = engine.predict_marriage(
        year=1995, month=5, day=15,
        hour=14, minute=30, second=0.0,
        tz_offset=5.5,
        lat=28.6139, lon=77.2090,
        name="Ananya Sharma",
        search_start_age=25,
        search_end_age=36
    )

    print("\n---------------- USER-FACING DECISIVE PREDICTION ----------------")
    print(answer.bold_headline)
    print("\nWhy I'm saying this:")
    print(answer.why_saying_this)
    print("\nWhat happens before then:")
    print(answer.what_happens_before_then)
    print("\nWhat kind of partner / marriage is indicated:")
    print(answer.partner_and_marriage_profile)
    print("\nWhy the delay:")
    print(answer.why_the_delay)
    print("\nWhat you should do now:")
    print(answer.what_to_do_now)
    print("\nOne question for you:")
    print(answer.closing_question)

    print("\n---------------- INTERNAL STATISTICAL BOOKKEEPING ----------------")
    p = answer.internal_payload
    print(f"Event:                     {p.event}")
    print(f"Best Period Candidate:     {p.best_period}")
    print(f"Year Score:                {p.year_score}/100")
    print(f"Month Score:               {p.month_score}/100")
    print(f"Temporal Stability:        {p.birth_time_stability_pct}% ({p.stability_classification})")
    print(f"Negative Obstruction:      -{p.negative_evidence_score}")
    print("\nMonthly Comparison ('Why not other months?'):")
    for m_item in p.why_not_other_months["monthly_breakdown"]:
        mark = "★ HIGHEST" if m_item["is_strongest"] else f"-{m_item['margin_from_peak']} pts"
        print(f"  {m_item['month']:<12}: {m_item['score']:>5.1f}/100  [{mark}]")

    print("\n======================================================================")
    print("[2] Running Blind Backtesting Lab on Verified Historical Dataset...")
    print("    ** MACHINERY VALIDATION ONLY - NO ACCURACY CLAIM **")
    print("    ** The seed set is far below the pre-registered 500-chart minimum. **")
    print("    ** See docs/accuracy_protocol.md for the only valid accuracy path. **")
    dataset_file = Path(__file__).parent / "data" / "test_charts" / "historical_verified.json"
    metrics, records = engine.run_backtest(dataset_file)

    print(f"\nTotal Verified Charts Evaluated: {metrics.total_charts_tested}")
    print(f"Top-1 Year Hit Rate (seed):      {metrics.top_1_year_accuracy}%")
    print(f"Top-3 Year Hit Rate (seed):      {metrics.top_3_year_accuracy}%")
    print(f"Mean Absolute Error (MAE):       {metrics.mean_absolute_error_months} months")
    print(f"Median Absolute Error:           {metrics.median_absolute_error_months} months")
    print(f"95% Confidence Interval:         {metrics.confidence_interval_95} months")
    print(f"High-Confidence Top-3 Share:     {metrics.high_confidence_top3_year_share}%  (not calibration)")

    print("\nIndividual Blind Prediction Records:")
    for r in records:
        status = "HIT (Top 1)" if r.is_top_1_year else ("HIT (Top 3)" if r.is_top_3_year else "MISS")
        print(f"  [{r.prediction_id}] Chart: {r.chart_id:<10} Actual: {r.actual_date_str} | Pred: {r.predicted_period_label:<15} Error: {r.month_error:>4.1f}m [{status}]")

    print("\n======================================================================")
    print("[3] Running Method Tournament (Points 26 & 39)...")
    tourney = engine.run_tournament(dataset_file)
    print(f"{'Model Name':<35} {'Top-1 Yr':<10} {'Top-3 Yr':<10} {'MAE (Months)':<12}")
    print("-" * 70)
    for t in tourney:
        print(f"{t.model_name:<35} {t.metrics.top_1_year_accuracy:>6.1f}%   {t.metrics.top_3_year_accuracy:>6.1f}%   {t.metrics.mean_absolute_error_months:>8.2f}m")
    print("\n======================================================================")
    print("[4] Consumer Answer Engine demo (calibrated, Sec 12/16)...")
    consumer = engine.answer_question(
        year=1995, month=5, day=15, hour=14, minute=30,
        tz_offset=5.5, lat=28.6139, lon=77.2090,
        question="career growth and wealth", time_reliable=True,
    )
    print(consumer.answer.to_markdown()[:3500])
    print("======================================================================\n")


if __name__ == "__main__":
    main()
