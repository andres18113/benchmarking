"""Tests for dataset reproducibility, the benchmark engine, the A limit and the Excel report."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openpyxl import load_workbook  # noqa: E402

from benchmark import STATUS_EXECUTED, STATUS_SKIPPED, BenchmarkConfig, run_benchmark  # noqa: E402
from dataset_generator import (  # noqa: E402
    SCENARIOS,
    build_edge_cases,
    build_size_case,
    fingerprint,
)
from excel_report import verify_excel, write_excel  # noqa: E402
from main import main  # noqa: E402


class DatasetTests(unittest.TestCase):
    def test_reproducible_with_same_seed(self):
        for scenario in SCENARIOS:
            a = build_size_case(scenario, 1000, base_seed=99)
            b = build_size_case(scenario, 1000, base_seed=99)
            self.assertEqual(a.data, b.data)
            self.assertEqual(fingerprint(a.data), fingerprint(b.data))

    def test_different_seed_changes_data(self):
        a = build_size_case("random_unique", 1000, base_seed=1)
        b = build_size_case("random_unique", 1000, base_seed=2)
        self.assertNotEqual(a.data, b.data)

    def test_sizes_and_ground_truth(self):
        for scenario, spec in SCENARIOS.items():
            for n in (100, 1000, 10_000):
                case = build_size_case(scenario, n)
                self.assertEqual(case.n, n)
                self.assertEqual(len(set(case.data)) != n, spec["expected"], scenario)

    def test_scenario_shapes(self):
        early = build_size_case("early_duplicate", 1000).data
        self.assertEqual(early[0], early[1])
        self.assertEqual(len(set(early)), 999)
        late = build_size_case("late_duplicate", 1000).data
        self.assertEqual(late[-1], late[-2])
        self.assertEqual(len(set(late)), 999)

    def test_edge_cases_ground_truth(self):
        for case in build_edge_cases():
            self.assertEqual(len(set(case.data)) != case.n, case.expected, case.scenario)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            build_size_case("nope", 100)
        with self.assertRaises(ValueError):
            build_size_case("random_unique", 1)


class BenchmarkEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = BenchmarkConfig(sizes=(100, 1000, 2000), repetitions=3, seed=5,
                                     max_comparisons_a=600_000)
        cls.report = run_benchmark(cls.config)

    def test_all_validation_checks_pass(self):
        v = self.report.validation()
        self.assertTrue(v["all_checks_passed"], v)

    def test_repetitions_recorded(self):
        for s in self.report.summaries:
            if s.status == STATUS_EXECUTED:
                self.assertEqual(s.repetitions, 3)
                self.assertGreaterEqual(s.mean_time_ms, 0)

    def test_limit_skips_quadratic_runs_without_inventing_values(self):
        # n = 2000 without an early duplicate needs ~2 million comparisons > 600,000.
        skipped = {(s.scenario, s.n) for s in self.report.skipped}
        self.assertEqual(skipped, {("random_unique", 2000), ("late_duplicate", 2000)})
        for s in self.report.summaries:
            if s.status == STATUS_SKIPPED:
                self.assertEqual(s.algorithm, "A")
                self.assertIsNone(s.mean_time_ms)
                self.assertIsNone(s.mean_comparisons)
                self.assertIsNone(s.result)
        measured = {(m.scenario, m.algorithm, m.n) for m in self.report.measurements}
        self.assertNotIn(("random_unique", "A", 2000), measured)
        # B is never skipped.
        self.assertIn(("random_unique", "B", 2000), measured)

    def test_no_limit_runs_everything(self):
        cfg = BenchmarkConfig(sizes=(100, 300), repetitions=3, max_comparisons_a=None,
                              include_edge_cases=False)
        report = run_benchmark(cfg)
        self.assertEqual(report.skipped, [])
        self.assertTrue(report.validation()["all_checks_passed"])

    def test_minimum_three_repetitions(self):
        with self.assertRaises(ValueError):
            run_benchmark(BenchmarkConfig(sizes=(100,), repetitions=2))

    def test_alternating_order(self):
        first = [m.algorithm for m in self.report.measurements
                 if m.scenario == "random_unique" and m.n == 100 and m.position_in_repetition == 1]
        self.assertEqual(first, ["A", "B", "A"])


class ExcelTests(unittest.TestCase):
    def test_excel_is_written_and_reopens(self):
        report = run_benchmark(BenchmarkConfig(sizes=(100, 1000, 2000), repetitions=3,
                                               max_comparisons_a=600_000))
        with tempfile.TemporaryDirectory() as tmp:
            path = write_excel(report, Path(tmp) / "out.xlsx")
            self.assertEqual(verify_excel(path, report), [])
            wb = load_workbook(path)
            ws = wb["Main Table"]
            header = None
            for row in ws.iter_rows(min_row=1, max_row=8, values_only=True):
                if row[0] == "Algorithm":
                    header = row[:4]
                    break
            self.assertEqual(header, ("Algorithm", "n", "Operations (comparisons)", "Time (ms)"))
            skipped_rows = [r for r in wb["Skipped Tests"].iter_rows(min_row=5, values_only=True)
                            if r[0]]
            self.assertEqual(len(skipped_rows), 2)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--sizes", "100", "500", "--output-dir", tmp,
                         "--max-comparisons-a", "50000"])
            self.assertEqual(code, 0)
            for name in ("benchmark_results.xlsx", "results.json", "measurements.csv",
                         "averages.csv", "results_summary.md", "execution_log.txt"):
                self.assertTrue((Path(tmp) / name).is_file(), name)
            import logging
            for h in logging.getLogger("benchmark").handlers:
                h.close()
            logging.getLogger("benchmark").handlers.clear()


if __name__ == "__main__":
    unittest.main()
