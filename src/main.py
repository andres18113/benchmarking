"""Lab 02 - Algorithm benchmarking: duplicate detection.

Runs Algorithm A (nested loops, O(n^2)) and Algorithm B (hash set, O(n)) on the
same reproducible datasets, measures time and operations, and writes the
results to an Excel workbook plus JSON/CSV/Markdown files.

Examples
--------
    python src/main.py                              # full default experiment
    python src/main.py --sizes 100 1000 --repetitions 5
    python src/main.py --max-comparisons-a 5000000000   # also run A for n = 100,000
    python src/main.py --no-limit                   # run everything (A at n = 10^6 takes hours)
"""

from __future__ import annotations

import argparse
import logging
import shlex
import sys
from pathlib import Path

from benchmark import (
    DEFAULT_MAX_COMPARISONS_A,
    DEFAULT_REPETITIONS,
    MIN_REPETITIONS,
    BenchmarkConfig,
    run_benchmark,
)
from dataset_generator import DEFAULT_SEED, DEFAULT_SIZES, SCENARIOS
from excel_report import verify_excel, write_excel
from text_reports import write_csv, write_json, write_markdown

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results"
DEFAULT_EXCEL_NAME = "benchmark_results.xlsx"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark two duplicate-detection algorithms and export the results to Excel.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES),
                        help="input sizes n to test")
    parser.add_argument("--scenarios", nargs="+", choices=list(SCENARIOS), default=list(SCENARIOS),
                        help="dataset scenarios to test")
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS,
                        help=f"timed repetitions per measurement (minimum {MIN_REPETITIONS})")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="base seed for reproducible datasets")
    limit = parser.add_mutually_exclusive_group()
    limit.add_argument("--max-comparisons-a", type=int, default=DEFAULT_MAX_COMPARISONS_A,
                       help="skip Algorithm A on datasets that need more comparisons than this")
    limit.add_argument("--no-limit", action="store_true",
                       help="run Algorithm A on every dataset, however long it takes")
    parser.add_argument("--no-edge-cases", action="store_true", help="do not run the edge cases")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="directory for the Excel workbook and the other result files")
    parser.add_argument("--excel-name", default=DEFAULT_EXCEL_NAME, help="Excel file name")
    return parser.parse_args(argv)


def setup_logging(output_dir: Path) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("benchmark")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout),
                    logging.FileHandler(output_dir / "execution_log.txt", mode="w",
                                        encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    return log


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir: Path = args.output_dir.resolve()
    log = setup_logging(output_dir)
    raw_args = sys.argv[1:] if argv is None else argv
    config = BenchmarkConfig(
        sizes=tuple(args.sizes),
        scenarios=tuple(args.scenarios),
        repetitions=args.repetitions,
        seed=args.seed,
        max_comparisons_a=None if args.no_limit else args.max_comparisons_a,
        include_edge_cases=not args.no_edge_cases,
        command_line="python src/main.py " + " ".join(shlex.quote(a) for a in raw_args),
    )
    try:
        config.validate()
    except ValueError as exc:
        log.error("Invalid configuration: %s", exc)
        return 2

    limit_text = "none" if config.max_comparisons_a is None else f"{config.max_comparisons_a:,}"
    log.info("Lab 02 - duplicate detection benchmark")
    log.info("sizes=%s repetitions=%d seed=%d A-limit=%s", list(config.sizes),
             config.repetitions, config.seed, limit_text)
    if config.max_comparisons_a is None and max(config.sizes) >= 100_000:
        log.warning("No limit for Algorithm A: datasets without an early duplicate at "
                    "n >= 100,000 need billions of comparisons and may take hours.")

    report = run_benchmark(config, log)

    excel_path = write_excel(report, output_dir / args.excel_name)
    write_json(report, output_dir / "results.json")
    write_csv(report, output_dir)
    write_markdown(report, output_dir / "results_summary.md")

    problems = verify_excel(excel_path, report)
    validation = report.validation()
    log.info("-" * 78)
    for key, value in validation.items():
        log.info("%-40s %s", key.replace("_", " "), value)
    if report.skipped:
        log.info("Skipped tests (not executed, no values invented):")
        for sk in report.skipped:
            log.info("  %s / %s / n=%s -> needs %s comparisons > limit %s", sk.scenario,
                     sk.algorithm, f"{sk.n:,}", f"{sk.predicted_comparisons:,}", f"{sk.limit:,}")
    if problems:
        for p in problems:
            log.error("Excel verification problem: %s", p)
    else:
        log.info("Excel reopened with openpyxl and verified: OK")
    log.info("Excel workbook: %s", excel_path)
    log.info("Other results : %s", output_dir)
    log.info("Total benchmark time: %.1f s", report.total_seconds)
    return 0 if validation["all_checks_passed"] and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
