"""Plain-text exports of a benchmark run: JSON, CSV and a Markdown summary."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from algorithms import ALGORITHMS
from benchmark import STATUS_EXECUTED, BenchmarkReport
from dataset_generator import SCENARIOS


def write_json(report: BenchmarkReport, path: Path) -> Path:
    payload = {
        "config": asdict(report.config),
        "environment": report.environment,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "total_seconds": report.total_seconds,
        "validation": report.validation(),
        "summaries": [asdict(s) for s in report.summaries],
        "skipped": [asdict(s) for s in report.skipped],
        "datasets": [asdict(d) | {"unchanged": d.unchanged} for d in report.datasets],
        "measurements": [asdict(m) for m in report.measurements],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_csv(report: BenchmarkReport, directory: Path) -> list[Path]:
    paths = []
    for name, rows in (("measurements.csv", [asdict(m) for m in report.measurements]),
                       ("averages.csv", [asdict(s) for s in report.summaries])):
        path = directory / name
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
            writer.writeheader()
            writer.writerows(rows)
        paths.append(path)
    return paths


def _fmt_ms(value: float | None) -> str:
    return "SKIPPED" if value is None else f"{value:,.4f}"


def _fmt_int(value: float | None) -> str:
    return "SKIPPED" if value is None else f"{int(value):,}"


def markdown_summary(report: BenchmarkReport) -> str:
    lines = [
        "# Benchmark results (generated automatically)",
        "",
        f"- Run: {report.started_at} -> {report.finished_at} ({report.total_seconds:,.1f} s)",
        f"- Python: {report.environment['Python']} | CPU: {report.environment['CPU']}",
        f"- Repetitions per measurement: {report.config.repetitions} | Seed: {report.config.seed}",
        f"- Algorithm A limit: {report.environment['Algorithm A comparison limit']}",
        f"- Command: `{report.config.command_line}`",
        "",
        "Operations = comparisons (A: `data[i] == data[j]`, B: `value in seen`). "
        "Time = mean wall-clock milliseconds measured with `time.perf_counter()`.",
        "",
    ]
    for scenario in report.config.scenarios:
        lines += [f"## {SCENARIOS[scenario]['label']} (`{scenario}`)", "",
                  "| Algorithm | n | Operations | Time (ms) | Answer |",
                  "|---|---:|---:|---:|---|"]
        for algorithm in ALGORITHMS:
            for n in report.config.sizes:
                s = report.summary_for(scenario, algorithm, n)
                if s is None:
                    continue
                if s.status == STATUS_EXECUTED:
                    answer = "duplicates" if s.result else "no duplicates"
                    lines.append(f"| {algorithm} | {n:,} | {_fmt_int(s.mean_comparisons)} | "
                                 f"{_fmt_ms(s.mean_time_ms)} | {answer} |")
                else:
                    lines.append(f"| {algorithm} | {n:,} | SKIPPED | SKIPPED | - |")
        lines.append("")
    lines += ["## Skipped tests", ""]
    if report.skipped:
        lines += ["| Scenario | Algorithm | n | Required comparisons (prediction) | Limit |",
                  "|---|---|---:|---:|---:|"]
        lines += [f"| {s.scenario} | {s.algorithm} | {s.n:,} | {s.predicted_comparisons:,} | "
                  f"{s.limit:,} |" for s in report.skipped]
    else:
        lines.append("None - every combination was executed.")
    lines += ["", "## Validation", ""]
    lines += [f"- {k.replace('_', ' ')}: **{v}**" for k, v in report.validation().items()]
    return "\n".join(lines) + "\n"


def write_markdown(report: BenchmarkReport, path: Path) -> Path:
    path.write_text(markdown_summary(report), encoding="utf-8")
    return path
