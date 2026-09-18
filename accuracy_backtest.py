"""
SweetAstro Accuracy Backtest — pre-registered, baseline-controlled evaluation.

Usage:
    python accuracy_backtest.py --freeze     # freeze the manifest (do this first)
    python accuracy_backtest.py              # score the frozen run
    python accuracy_backtest.py --dataset data/test_charts/<file>.csv

See docs/accuracy_protocol.md. The runner refuses to score if the dataset or
rules changed since the freeze, and makes no accuracy claim when the test split
is smaller than 30 charts.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from SweetAstro.src.evaluation.harness import run_evaluation
from SweetAstro.src.evaluation.preregistration import MANIFEST_PATH
from SweetAstro.src.evaluation.report import render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="SweetAstro accuracy backtest (pre-registered)")
    parser.add_argument("--dataset", default=str(PROJECT_ROOT / "data" / "test_charts" / "historical_verified.json"),
                        help="dataset JSON or CSV")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH),
                        help="path to the pre-registration manifest")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "reports"),
                        help="output directory for md/json reports")
    parser.add_argument("--freeze", action="store_true",
                        help="freeze (overwrite) the pre-registration manifest before scoring")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    manifest_path = Path(args.manifest)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = run_evaluation(
            dataset_path,
            manifest_path=manifest_path,
            allow_freeze=args.freeze,
        )
    except RuntimeError as exc:
        print(f"ABORTED: {exc}")
        return 2
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}")
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_md = out_dir / f"accuracy_{stamp}.md"
    report_json = out_dir / f"accuracy_{stamp}.json"
    report_md.write_text(render_markdown(result), encoding="utf-8")
    report_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

    et = result.engine_test
    ub = result.uniform_baseline
    mb = result.modal_baseline
    print("=" * 78)
    print(f"SWEETASTRO ACCURACY BACKTEST — protocol v{result.protocol_version}")
    print("=" * 78)
    print(f"  Dataset        : {result.dataset_path}")
    print(f"  Records        : {result.validation['n_records']} (primary AA/A: {result.validation['n_primary']})")
    print(f"  Split          : {result.n_train} train / {result.n_test} test (AA/A)")
    print(f"  Test coverage  : {result.coverage_pct}%")
    print(f"  Engine Top-1   : {et['top1_year']}%   (uniform baseline {ub['top1_year']}% "
          f"[{ub['top1_lo']}–{ub['top1_hi']}], modal {mb['top1_year']}%)")
    print(f"  Engine hit ±12m: {et['hit_within_12_months']}%   (uniform {ub['hit_12m']}%)")
    print(f"  Engine MAE     : {et['mae_months']} months")
    print(f"  Permutation p  : {result.permutation['p_value']} (observed {result.permutation['observed_top1_pct']}%)")
    verdict = "no accuracy claim possible (test split < 30)" if result.n_test < 30 else (
        "primary endpoint passed — replication required"
        if et['top1_year'] > ub['top1_hi'] and result.permutation['p_value'] < 0.05
        else "no demonstrated predictive skill"
    )
    print(f"  Verdict        : {verdict}")
    print("-" * 78)
    print(f"  Report         : {report_md}")
    print(f"  Raw JSON       : {report_json}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
