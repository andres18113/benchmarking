"""Benchmark engine: runs both algorithms on identical data and records results.

Measurement protocol
--------------------
* Each dataset is generated once and the *same list object* is passed to both
  algorithms in every repetition (the algorithms never modify it; a SHA-256
  fingerprint taken before and after the runs proves it).
* Wall-clock time is measured with ``time.perf_counter()`` immediately around
  the algorithm call only (data generation and bookkeeping are excluded) and
  converted to milliseconds.
* The garbage collector is paused during each timed call (as ``timeit`` does)
  so a random GC cycle does not land inside one measurement; it is re-enabled
  right after.
* Cheap runs (<= 1,000,000 predicted comparisons) get one untimed warm-up call
  per algorithm before the timed repetitions; it is not part of any average.
* The execution order alternates per repetition (A,B / B,A / A,B ...) to avoid
  favouring one algorithm with warm caches or CPU frequency drift.
* Every repetition's answer is checked against the ground truth and against the
  other algorithm; every comparison count is checked against the analytical
  prediction.

Safety limit for Algorithm A
----------------------------
Before running A, its exact comparison count is predicted analytically. If it
exceeds ``max_comparisons_a`` the run is *not executed* and is recorded as a
skipped test with its reason. No time or operation count is ever invented for a
skipped run.
"""

from __future__ import annotations

import gc
import logging
import os
import platform
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from algorithms import ALGORITHMS, first_duplicate_pair_a, first_repeat_index_b
from dataset_generator import (
    DEFAULT_SEED,
    DEFAULT_SIZES,
    SCENARIOS,
    BenchmarkCase,
    build_edge_cases,
    build_size_case,
    fingerprint,
)

DEFAULT_REPETITIONS = 3
MIN_REPETITIONS = 3
# 100 million comparisons ~ a few seconds per run of A in CPython. It allows
# n = 10,000 without duplicates (49,995,000 comparisons) and blocks n = 100,000
# (4,999,950,000) and n = 1,000,000 (499,999,500,000) unless raised/disabled.
DEFAULT_MAX_COMPARISONS_A = 100_000_000
# Datasets needing at most this many comparisons get one untimed warm-up call.
WARMUP_MAX_COMPARISONS = 1_000_000

STATUS_EXECUTED = "EXECUTED"
STATUS_SKIPPED = "SKIPPED"


@dataclass
class BenchmarkConfig:
    sizes: tuple[int, ...] = DEFAULT_SIZES
    scenarios: tuple[str, ...] = tuple(SCENARIOS)
    repetitions: int = DEFAULT_REPETITIONS
    seed: int = DEFAULT_SEED
    max_comparisons_a: int | None = DEFAULT_MAX_COMPARISONS_A  # None = no limit
    include_edge_cases: bool = True
    command_line: str = ""

    def validate(self) -> None:
        if self.repetitions < MIN_REPETITIONS:
            raise ValueError(f"repetitions must be >= {MIN_REPETITIONS} (got {self.repetitions})")
        if not self.sizes or any(n < 2 for n in self.sizes):
            raise ValueError("sizes must be a non-empty list of integers >= 2")
        unknown = [s for s in self.scenarios if s not in SCENARIOS]
        if unknown:
            raise ValueError(f"unknown scenarios: {unknown}. Valid: {list(SCENARIOS)}")
        if self.max_comparisons_a is not None and self.max_comparisons_a < 0:
            raise ValueError("max_comparisons_a must be >= 0 (or None for no limit)")


@dataclass
class Measurement:
    """One timed execution (one repetition of one algorithm on one dataset)."""

    scenario: str
    category: str
    algorithm: str
    n: int
    repetition: int
    position_in_repetition: int  # 1 = ran first in that repetition
    has_duplicates: bool
    comparisons: int
    time_ms: float
    aux_elements: int
    aux_bytes: int


@dataclass
class SkippedTest:
    scenario: str
    label: str
    category: str
    algorithm: str
    n: int
    predicted_comparisons: int  # analytical prediction, NOT a measurement
    limit: int
    reason: str
    how_to_run: str


@dataclass
class Summary:
    """Averages over the repetitions of one algorithm on one dataset."""

    scenario: str
    label: str
    category: str
    algorithm: str
    n: int
    status: str
    repetitions: int
    predicted_comparisons: int
    mean_comparisons: float | None = None
    comparisons_match_prediction: bool | None = None
    mean_time_ms: float | None = None
    min_time_ms: float | None = None
    max_time_ms: float | None = None
    stdev_time_ms: float | None = None
    aux_elements: int | None = None
    aux_bytes: int | None = None
    result: bool | None = None
    expected: bool = False
    correct: bool | None = None
    consistent_across_repetitions: bool | None = None
    time_factor_vs_previous_n: float | None = None
    comparisons_factor_vs_previous_n: float | None = None
    note: str = ""


@dataclass
class DatasetInfo:
    scenario: str
    label: str
    category: str
    n: int
    seed: str | None
    fingerprint_before: str
    fingerprint_after: str
    expected: bool
    first_pair_a: tuple[int, int] | None
    first_repeat_index_b: int | None
    min_value: int | None
    max_value: int | None
    distinct_values: int
    preview: str

    @property
    def unchanged(self) -> bool:
        return self.fingerprint_before == self.fingerprint_after


@dataclass
class BenchmarkReport:
    config: BenchmarkConfig
    environment: dict[str, str]
    measurements: list[Measurement] = field(default_factory=list)
    summaries: list[Summary] = field(default_factory=list)
    skipped: list[SkippedTest] = field(default_factory=list)
    datasets: list[DatasetInfo] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    total_seconds: float = 0.0

    def summary_for(self, scenario: str, algorithm: str, n: int) -> Summary | None:
        for s in self.summaries:
            if s.scenario == scenario and s.algorithm == algorithm and s.n == n:
                return s
        return None

    def validation(self) -> dict[str, object]:
        """Aggregate coherence checks used by the console, Excel and tests."""
        executed = [s for s in self.summaries if s.status == STATUS_EXECUTED]
        pairs_compared = 0
        pairs_agree = 0
        keys = {(s.scenario, s.n) for s in self.summaries}
        for scenario, n in keys:
            a = self.summary_for(scenario, "A", n)
            b = self.summary_for(scenario, "B", n)
            if a and b and a.status == b.status == STATUS_EXECUTED:
                pairs_compared += 1
                pairs_agree += int(a.result == b.result)
        checks = {
            "timed_executions": len(self.measurements),
            "executed_summaries": len(executed),
            "skipped_tests": len(self.skipped),
            "all_answers_correct": all(s.correct for s in executed),
            "a_and_b_pairs_compared": pairs_compared,
            "a_and_b_always_agree": pairs_agree == pairs_compared,
            "counters_match_prediction": all(s.comparisons_match_prediction for s in executed),
            "results_consistent_across_repetitions": all(
                s.consistent_across_repetitions for s in executed),
            "datasets_unchanged_by_algorithms": all(d.unchanged for d in self.datasets),
        }
        checks["all_checks_passed"] = all(
            v for k, v in checks.items() if isinstance(v, bool))
        return checks


# ---------------------------------------------------------------------------
# Environment description (slide 9: "record the environment")
# ---------------------------------------------------------------------------

def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def _total_ram() -> str:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return f"{pages * page_size / 1024 ** 3:.1f} GiB"
    except (ValueError, OSError, AttributeError):
        return "unknown"


def describe_environment(config: BenchmarkConfig) -> dict[str, str]:
    try:
        import openpyxl
        openpyxl_version = openpyxl.__version__
    except ImportError:  # pragma: no cover
        openpyxl_version = "not installed"
    clock = time.get_clock_info("perf_counter")
    limit = ("no limit" if config.max_comparisons_a is None
             else f"{config.max_comparisons_a:,} comparisons")
    return {
        "Date and time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Python": f"{platform.python_implementation()} {platform.python_version()}",
        "openpyxl": openpyxl_version,
        "Operating system": platform.platform(),
        "CPU": _cpu_model(),
        "Logical CPUs": str(os.cpu_count()),
        "Total RAM": _total_ram(),
        "Timer": f"time.perf_counter() ({clock.implementation}, resolution {clock.resolution:.0e} s)",
        "Garbage collector": "paused during each timed call, re-enabled afterwards",
        "Execution": "single process, single thread, algorithms run sequentially",
        "Repetitions per measurement": str(config.repetitions),
        "Execution order": "alternated per repetition (A,B then B,A ...)",
        "Warm-up": f"1 untimed call per algorithm when <= {WARMUP_MAX_COMPARISONS:,} comparisons",
        "Base seed": str(config.seed),
        "Sizes (n)": ", ".join(f"{n:,}" for n in config.sizes),
        "Scenarios": ", ".join(config.scenarios),
        "Edge cases included": "yes" if config.include_edge_cases else "no",
        "Algorithm A comparison limit": limit,
        "Counted operation": "A: evaluations of data[i] == data[j]; B: membership tests 'value in seen'",
        "Command": config.command_line or "(called as a library)",
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _timed_call(func: Callable, data: list[int]):
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter()
        result = func(data)
        end = time.perf_counter()
    finally:
        if gc_was_enabled:
            gc.enable()
    return result, (end - start) * 1000.0


def _preview(data: list[int], limit: int = 10) -> str:
    if len(data) <= limit:
        return str(data)
    return "[" + ", ".join(str(v) for v in data[:limit]) + f", ...] ({len(data):,} items)"


def _skip_command(case: BenchmarkCase, predicted: int) -> str:
    if case.category == "edge case":
        return "python src/main.py --no-limit"
    return (f"python src/main.py --sizes {case.n} --scenarios {case.scenario} "
            f"--max-comparisons-a {predicted}    (or: --no-limit)")


def run_case(case: BenchmarkCase, config: BenchmarkConfig, report: BenchmarkReport,
             log: logging.Logger) -> None:
    data = case.data
    fp_before = fingerprint(data)
    predicted = {key: spec["predictor"](data) for key, spec in ALGORITHMS.items()}

    active: list[str] = []
    for key in ALGORITHMS:
        limit = config.max_comparisons_a
        if key == "A" and limit is not None and predicted["A"] > limit:
            reason = (f"Algorithm A is O(n^2): this dataset requires {predicted['A']:,} "
                      f"comparisons (analytical prediction), which exceeds the configured "
                      f"limit of {limit:,}. The run was not executed, so no time or "
                      f"operation count is reported.")
            report.skipped.append(SkippedTest(
                case.scenario, case.label, case.category, key, case.n,
                predicted["A"], limit, reason, _skip_command(case, predicted["A"])))
            report.summaries.append(Summary(
                case.scenario, case.label, case.category, key, case.n, STATUS_SKIPPED,
                0, predicted[key], expected=case.expected,
                note=f"Skipped: needs {predicted['A']:,} comparisons > limit {limit:,}"))
            log.info("  %-26s n=%-9s A SKIPPED (needs %s comparisons > limit %s)",
                     case.scenario, f"{case.n:,}", f"{predicted['A']:,}", f"{limit:,}")
        else:
            active.append(key)

    # One untimed warm-up call per algorithm on cheap datasets, so the first timed
    # repetition does not pay one-off costs (cold caches, lazy initialisation).
    for key in active:
        if predicted[key] <= WARMUP_MAX_COMPARISONS:
            ALGORITHMS[key]["function"](data)

    per_algo: dict[str, list[Measurement]] = {key: [] for key in active}
    for rep in range(1, config.repetitions + 1):
        order = active if rep % 2 == 1 else list(reversed(active))
        for position, key in enumerate(order, start=1):
            result, elapsed_ms = _timed_call(ALGORITHMS[key]["function"], data)
            m = Measurement(case.scenario, case.category, key, case.n, rep, position,
                            result.has_duplicates, result.comparisons, elapsed_ms,
                            result.aux_elements, result.aux_bytes)
            per_algo[key].append(m)
            report.measurements.append(m)

    for key in active:
        runs = per_algo[key]
        times = [m.time_ms for m in runs]
        comps = [m.comparisons for m in runs]
        answers = {m.has_duplicates for m in runs}
        consistent = len(answers) == 1 and len(set(comps)) == 1
        answer = runs[0].has_duplicates
        mean_comps = statistics.fmean(comps)
        s = Summary(
            case.scenario, case.label, case.category, key, case.n, STATUS_EXECUTED,
            len(runs), predicted[key],
            mean_comparisons=mean_comps,
            comparisons_match_prediction=all(c == predicted[key] for c in comps),
            mean_time_ms=statistics.fmean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            stdev_time_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
            aux_elements=max(m.aux_elements for m in runs),
            aux_bytes=max(m.aux_bytes for m in runs),
            result=answer,
            expected=case.expected,
            correct=consistent and answer == case.expected,
            consistent_across_repetitions=consistent,
        )
        report.summaries.append(s)
        log.info("  %-26s n=%-9s %s  answer=%-5s comparisons=%-15s mean=%12.4f ms",
                 case.scenario, f"{case.n:,}", key, answer, f"{int(mean_comps):,}",
                 s.mean_time_ms)

    fp_after = fingerprint(data)
    report.datasets.append(DatasetInfo(
        case.scenario, case.label, case.category, case.n, case.seed, fp_before, fp_after,
        case.expected, first_duplicate_pair_a(data), first_repeat_index_b(data),
        min(data) if data else None, max(data) if data else None, len(set(data)),
        _preview(data)))
    if fp_before != fp_after:
        log.error("  Dataset %s n=%s was modified during the benchmark!", case.scenario, case.n)


def _fill_growth_factors(report: BenchmarkReport) -> None:
    """Ratio between consecutive sizes (e.g. T(10n) / T(n)) for each series."""
    series: dict[tuple[str, str], list[Summary]] = {}
    for s in report.summaries:
        if s.category == "size scenario":
            series.setdefault((s.scenario, s.algorithm), []).append(s)
    for items in series.values():
        items.sort(key=lambda s: s.n)
        for prev, cur in zip(items, items[1:]):
            if STATUS_EXECUTED == prev.status == cur.status:
                if prev.mean_time_ms and prev.mean_time_ms > 0:
                    cur.time_factor_vs_previous_n = cur.mean_time_ms / prev.mean_time_ms
                if prev.mean_comparisons:
                    cur.comparisons_factor_vs_previous_n = (
                        cur.mean_comparisons / prev.mean_comparisons)


def run_benchmark(config: BenchmarkConfig, log: logging.Logger | None = None) -> BenchmarkReport:
    config.validate()
    log = log or logging.getLogger("benchmark")
    report = BenchmarkReport(config=config, environment=describe_environment(config))
    report.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.perf_counter()

    for scenario in config.scenarios:
        log.info("Scenario: %s - %s", scenario, SCENARIOS[scenario]["label"])
        for n in config.sizes:
            case = build_size_case(scenario, n, config.seed)
            run_case(case, config, report, log)
            del case

    if config.include_edge_cases:
        log.info("Edge cases")
        for case in build_edge_cases():
            run_case(case, config, report, log)

    _fill_growth_factors(report)
    report.total_seconds = time.perf_counter() - t0
    report.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return report

