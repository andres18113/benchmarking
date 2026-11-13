"""Excel (.xlsx) report generation with openpyxl.

Sheets
------
1. Main Table        - slide 8 layout: Algorithm | n | Operations | Time (ms), per scenario
2. A vs B            - side-by-side comparison and speed-up per scenario and n
3. Averages          - every averaged result with min/max/std-dev and validation flags
4. Repetitions       - every individual timed execution (raw data)
5. Edge Cases        - empty list, one element, all equal, all unique, ...
6. Skipped Tests     - tests that were not executed and why (no invented values)
7. Datasets          - seeds, SHA-256 fingerprints and properties of every dataset
8. Validation        - automatic coherence checks
9. Charts            - log-log charts of time and operations vs n
10. Environment      - hardware, software and experiment conditions
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from algorithms import ALGORITHMS
from benchmark import STATUS_EXECUTED, BenchmarkReport
from dataset_generator import SCENARIOS

# --------------------------------------------------------------------------- styles
NAVY = "1F3864"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
SECTION_FILL = PatternFill("solid", fgColor="D9E1F2")
A_FILL = PatternFill("solid", fgColor="FCE4D6")
B_FILL = PatternFill("solid", fgColor="E2EFDA")
SKIP_FILL = PatternFill("solid", fgColor="EDEDED")
OK_FILL = PatternFill("solid", fgColor="C6EFCE")
BAD_FILL = PatternFill("solid", fgColor="FFC7CE")

TITLE_FONT = Font(name="Calibri", size=16, bold=True, color=NAVY)
SUBTITLE_FONT = Font(name="Calibri", size=10, italic=True, color="595959")
SECTION_FONT = Font(name="Calibri", size=12, bold=True, color=NAVY)
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
SKIP_FONT = Font(name="Calibri", size=11, italic=True, color="7F7F7F")
BOLD = Font(name="Calibri", size=11, bold=True)

THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")

FMT_INT = "#,##0"
FMT_MS = "#,##0.0000"
FMT_FACTOR = '0.00"x"'
FMT_BYTES = "#,##0"

SKIPPED_TEXT = "SKIPPED"
NOT_MEASURED = "not measured"


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "-"
    return "YES" if value else "NO"


def _title(ws: Worksheet, title: str, subtitle: str, width: int) -> int:
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    ws["A2"] = subtitle
    ws["A2"].font = SUBTITLE_FONT
    ws["A2"].alignment = LEFT
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    ws.row_dimensions[2].height = 30
    return 4


def _header(ws: Worksheet, row: int, headers: list[str]) -> None:
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER
    ws.row_dimensions[row].height = 32


def _write_row(ws: Worksheet, row: int, values: list, formats: list[str | None],
               fill: PatternFill | None = None, font: Font | None = None) -> None:
    for col, (value, fmt) in enumerate(zip(values, formats), start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.border = BORDER
        if fmt:
            cell.number_format = fmt
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cell.alignment = RIGHT
        else:
            cell.alignment = LEFT if isinstance(value, str) and len(value) > 14 else CENTER
        if fill:
            cell.fill = fill
        if font:
            cell.font = font


def _widths(ws: Worksheet, widths: list[float]) -> None:
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width


def _algo_fill(algorithm: str) -> PatternFill:
    return A_FILL if algorithm == "A" else B_FILL


def _flag_cell(ws: Worksheet, row: int, col: int, value: bool | None) -> None:
    cell = ws.cell(row=row, column=col)
    if value is True:
        cell.fill = OK_FILL
    elif value is False:
        cell.fill = BAD_FILL


def _conditions_line(report: BenchmarkReport) -> str:
    env = report.environment
    return (f"Real measurements - mean of {report.config.repetitions} repetitions per cell - "
            f"time.perf_counter() - {env['Python']} - {env['CPU']} - seed {report.config.seed} - "
            f"run {report.started_at}. Operations = comparisons as defined on slide 6.")


def _scenario_order(report: BenchmarkReport) -> list[str]:
    return [s for s in report.config.scenarios]


# --------------------------------------------------------------------------- sheets
def _sheet_main_table(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.active
    ws.title = "Main Table"
    headers = ["Algorithm", "n", "Operations (comparisons)", "Time (ms)", "Answer",
               "Notes"]
    row = _title(ws, "Lab 02 - Algorithm Benchmarking: Duplicate Detection",
                 _conditions_line(report), len(headers))
    for scenario in _scenario_order(report):
        ws.cell(row=row, column=1, value=SCENARIOS[scenario]["label"]).font = SECTION_FONT
        for col in range(1, len(headers) + 1):
            ws.cell(row=row, column=col).fill = SECTION_FILL
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
        row += 1
        _header(ws, row, headers)
        row += 1
        for algorithm in ALGORITHMS:
            for n in report.config.sizes:
                s = report.summary_for(scenario, algorithm, n)
                if s is None:
                    continue
                if s.status == STATUS_EXECUTED:
                    note = ""
                    if s.time_factor_vs_previous_n:
                        note = f"x{s.time_factor_vs_previous_n:,.1f} time vs previous n"
                    _write_row(ws, row, [algorithm, n, s.mean_comparisons, s.mean_time_ms,
                                         "duplicates" if s.result else "no duplicates", note],
                               [None, FMT_INT, FMT_INT, FMT_MS, None, None],
                               fill=_algo_fill(algorithm))
                else:
                    _write_row(ws, row, [algorithm, n, SKIPPED_TEXT, SKIPPED_TEXT, "-",
                                         f"Not executed: would need {s.predicted_comparisons:,} "
                                         f"comparisons (> limit). See 'Skipped Tests'."],
                               [None, FMT_INT, None, None, None, None],
                               fill=SKIP_FILL, font=SKIP_FONT)
                row += 1
        row += 1
    ws.cell(row=row, column=1,
            value="Every number in this table was measured by the program in this run. "
                  "SKIPPED cells were intentionally not executed (see 'Skipped Tests').").font = SUBTITLE_FONT
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
    _widths(ws, [12, 13, 24, 16, 16, 62])
    ws.freeze_panes = "A4"


def _sheet_a_vs_b(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("A vs B")
    headers = ["Scenario", "n", "Operations A", "Operations B", "Operations ratio A/B",
               "Time A (ms)", "Time B (ms)", "Speed-up (time A / time B)", "Answer A",
               "Answer B", "Same answer?"]
    row = _title(ws, "Algorithm A vs Algorithm B on identical datasets",
                 "Speed-up > 1 means B was faster. Ratios are computed only when both "
                 "algorithms were actually executed.", len(headers))
    _header(ws, row, headers)
    first = row + 1
    row += 1
    for scenario in _scenario_order(report):
        for n in report.config.sizes:
            a = report.summary_for(scenario, "A", n)
            b = report.summary_for(scenario, "B", n)
            if not a or not b:
                continue
            a_run = a.status == STATUS_EXECUTED
            b_run = b.status == STATUS_EXECUTED
            both = a_run and b_run
            values = [
                scenario, n,
                a.mean_comparisons if a_run else SKIPPED_TEXT,
                b.mean_comparisons if b_run else SKIPPED_TEXT,
                (a.mean_comparisons / b.mean_comparisons) if both and b.mean_comparisons else "-",
                a.mean_time_ms if a_run else SKIPPED_TEXT,
                b.mean_time_ms if b_run else SKIPPED_TEXT,
                (a.mean_time_ms / b.mean_time_ms) if both and b.mean_time_ms else "-",
                _yes_no(a.result) if a_run else "-",
                _yes_no(b.result) if b_run else "-",
                _yes_no(a.result == b.result) if both else "-",
            ]
            _write_row(ws, row, values, [None, FMT_INT, FMT_INT, FMT_INT, FMT_FACTOR, FMT_MS,
                                         FMT_MS, FMT_FACTOR, None, None, None])
            if not a_run:
                for col in (3, 6):
                    ws.cell(row=row, column=col).font = SKIP_FONT
                    ws.cell(row=row, column=col).fill = SKIP_FILL
            if both:
                _flag_cell(ws, row, 11, a.result == b.result)
            row += 1
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(headers))}{row - 1}"
    ws.freeze_panes = ws.cell(row=first, column=3)
    _widths(ws, [26, 12, 18, 14, 14, 15, 14, 16, 11, 11, 12])


def _sheet_averages(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Averages")
    headers = ["Category", "Scenario", "Algorithm", "n", "Status", "Repetitions",
               "Mean operations", "Predicted operations (analytical)", "Counter = prediction?",
               "Mean time (ms)", "Min time (ms)", "Max time (ms)", "Std dev (ms)",
               "Time factor vs previous n", "Operations factor vs previous n",
               "Aux. elements stored", "Aux. structure size (bytes)", "Answer", "Expected",
               "Correct?", "Notes"]
    row = _title(ws, "Averages over repetitions (all scenarios and edge cases)",
                 "Predicted operations come from an exact formula and are only used to validate "
                 "the instrumented counters and to apply the A limit; they are not measurements.",
                 12)
    _header(ws, row, headers)
    first = row + 1
    row += 1
    for s in report.summaries:
        run = s.status == STATUS_EXECUTED
        values = [
            s.category, s.scenario, s.algorithm, s.n, s.status, s.repetitions,
            s.mean_comparisons if run else SKIPPED_TEXT,
            s.predicted_comparisons,
            _yes_no(s.comparisons_match_prediction),
            s.mean_time_ms if run else SKIPPED_TEXT,
            s.min_time_ms if run else "-",
            s.max_time_ms if run else "-",
            s.stdev_time_ms if run else "-",
            s.time_factor_vs_previous_n if s.time_factor_vs_previous_n else "-",
            s.comparisons_factor_vs_previous_n if s.comparisons_factor_vs_previous_n else "-",
            s.aux_elements if run else "-",
            s.aux_bytes if run else "-",
            _yes_no(s.result), _yes_no(s.expected), _yes_no(s.correct), s.note,
        ]
        fmts = [None, None, None, FMT_INT, None, FMT_INT, FMT_INT, FMT_INT, None, FMT_MS,
                FMT_MS, FMT_MS, FMT_MS, FMT_FACTOR, FMT_FACTOR, FMT_INT, FMT_BYTES, None, None,
                None, None]
        _write_row(ws, row, values, fmts,
                   fill=_algo_fill(s.algorithm) if run else SKIP_FILL,
                   font=None if run else SKIP_FONT)
        _flag_cell(ws, row, 9, s.comparisons_match_prediction)
        _flag_cell(ws, row, 20, s.correct)
        row += 1
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(headers))}{row - 1}"
    ws.freeze_panes = ws.cell(row=first, column=5)
    _widths(ws, [13, 26, 10, 12, 11, 11, 17, 19, 12, 15, 13, 13, 12, 13, 14, 13, 15, 9,
                 9, 9, 50])


def _sheet_repetitions(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Repetitions")
    headers = ["Category", "Scenario", "Algorithm", "n", "Repetition", "Position in repetition",
               "Answer", "Operations", "Time (ms)", "Aux. elements", "Aux. bytes"]
    row = _title(ws, "Raw data: every individual timed execution",
                 "The means in 'Main Table' and 'Averages' are computed from these rows.",
                 len(headers))
    _header(ws, row, headers)
    first = row + 1
    row += 1
    for m in report.measurements:
        _write_row(ws, row, [m.category, m.scenario, m.algorithm, m.n, m.repetition,
                             m.position_in_repetition, _yes_no(m.has_duplicates), m.comparisons,
                             m.time_ms, m.aux_elements, m.aux_bytes],
                   [None, None, None, FMT_INT, None, None, None, FMT_INT, FMT_MS, FMT_INT,
                    FMT_BYTES], fill=_algo_fill(m.algorithm))
        row += 1
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(headers))}{row - 1}"
    ws.freeze_panes = ws.cell(row=first, column=1)
    _widths(ws, [13, 26, 10, 12, 11, 12, 9, 17, 14, 13, 12])


def _sheet_edge_cases(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Edge Cases")
    headers = ["Case", "Description", "Data", "n", "Expected", "Answer A", "Operations A",
               "Time A (ms)", "Answer B", "Operations B", "Time B (ms)", "A = B?", "Correct?"]
    row = _title(ws, "Edge cases (slide 9): empty list, one element, all equal, all unique",
                 "Each case was timed with the same number of repetitions as the main scenarios.",
                 len(headers))
    _header(ws, row, headers)
    row += 1
    datasets = {d.scenario: d for d in report.datasets if d.category == "edge case"}
    if not datasets:
        ws.cell(row=row, column=1, value="Edge cases were disabled for this run.")
    for name, d in datasets.items():
        a = report.summary_for(name, "A", d.n)
        b = report.summary_for(name, "B", d.n)
        a_run = bool(a and a.status == STATUS_EXECUTED)
        b_run = bool(b and b.status == STATUS_EXECUTED)
        agree = (a.result == b.result) if a_run and b_run else None
        correct = all(x.correct for x in (a, b) if x and x.status == STATUS_EXECUTED)
        values = [name, d.label, d.preview, d.n, _yes_no(d.expected),
                  _yes_no(a.result) if a_run else SKIPPED_TEXT,
                  a.mean_comparisons if a_run else SKIPPED_TEXT,
                  a.mean_time_ms if a_run else SKIPPED_TEXT,
                  _yes_no(b.result) if b_run else SKIPPED_TEXT,
                  b.mean_comparisons if b_run else SKIPPED_TEXT,
                  b.mean_time_ms if b_run else SKIPPED_TEXT,
                  _yes_no(agree), _yes_no(correct)]
        _write_row(ws, row, values, [None, None, None, FMT_INT, None, None, FMT_INT, FMT_MS,
                                     None, FMT_INT, FMT_MS, None, None])
        _flag_cell(ws, row, 12, agree)
        _flag_cell(ws, row, 13, correct)
        row += 1
    _widths(ws, [26, 36, 44, 8, 10, 10, 13, 12, 10, 13, 12, 9, 10])
    ws.freeze_panes = "B5"


def _sheet_skipped(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Skipped Tests")
    headers = ["Scenario", "Algorithm", "n", "Required comparisons (analytical prediction, "
               "not measured)", "Configured limit", "Reason", "How to run it voluntarily"]
    limit = report.config.max_comparisons_a
    limit_text = "no limit (--no-limit)" if limit is None else f"{limit:,} comparisons"
    row = _title(ws, "Tests intentionally not executed",
                 f"Algorithm A limit for this run: {limit_text}. Skipped tests have NO time or "
                 f"operation values anywhere in this workbook.", len(headers))
    _header(ws, row, headers)
    row += 1
    if not report.skipped:
        ws.cell(row=row, column=1, value="No test was skipped in this run: every combination "
                                         "was executed and measured.").font = BOLD
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))
    for sk in report.skipped:
        _write_row(ws, row, [sk.scenario, sk.algorithm, sk.n, sk.predicted_comparisons,
                             sk.limit, sk.reason, sk.how_to_run],
                   [None, None, FMT_INT, FMT_INT, FMT_INT, None, None], fill=SKIP_FILL)
        ws.row_dimensions[row].height = 62
        row += 1
    _widths(ws, [26, 10, 13, 24, 17, 70, 60])


def _sheet_datasets(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Datasets")
    headers = ["Category", "Scenario", "n", "Derived seed", "SHA-256 before", "SHA-256 after",
               "Unchanged?", "Contains duplicates (ground truth)", "Pair where A stops (i, j)",
               "Index where B stops", "Distinct values", "Min", "Max", "Preview"]
    row = _title(ws, "Datasets used (identical list object passed to A and B)",
                 "Reproducible: each list is generated with random.Random(\"<seed>:<scenario>:<n>\"). "
                 "The fingerprint before and after the runs proves the data was not modified.",
                 10)
    _header(ws, row, headers)
    first = row + 1
    row += 1
    for d in report.datasets:
        _write_row(ws, row, [d.category, d.scenario, d.n, d.seed or "fixed list",
                             d.fingerprint_before, d.fingerprint_after, _yes_no(d.unchanged),
                             _yes_no(d.expected),
                             str(d.first_pair_a) if d.first_pair_a else "none (full scan)",
                             d.first_repeat_index_b if d.first_repeat_index_b is not None
                             else "none (full scan)",
                             d.distinct_values, d.min_value if d.min_value is not None else "-",
                             d.max_value if d.max_value is not None else "-", d.preview],
                   [None, None, FMT_INT, None, None, None, None, None, None, FMT_INT, FMT_INT,
                    FMT_INT, FMT_INT, None])
        _flag_cell(ws, row, 7, d.unchanged)
        row += 1
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(len(headers))}{row - 1}"
    ws.freeze_panes = ws.cell(row=first, column=4)
    _widths(ws, [13, 26, 12, 34, 30, 30, 11, 14, 18, 14, 13, 11, 12, 50])


def _sheet_validation(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Validation")
    row = _title(ws, "Automatic coherence checks",
                 "Computed by the program after the benchmark. Any 'NO' means the run is not valid.",
                 3)
    _header(ws, row, ["Check", "Result", "Meaning"])
    row += 1
    labels = {
        "timed_executions": ("Timed executions",
                             "Total timed executions recorded in 'Repetitions'."),
        "executed_summaries": ("Executed combinations",
                               "Algorithm/dataset combinations that were executed."),
        "skipped_tests": ("Skipped tests",
                          "Combinations intentionally not executed ('Skipped Tests')."),
        "all_answers_correct": ("All answers correct",
                                "Every answer equals the known ground truth of its dataset."),
        "a_and_b_pairs_compared": ("Datasets run by both A and B",
                                   "Datasets on which both A and B were executed."),
        "a_and_b_always_agree": ("A and B always agree",
                                 "A and B returned the same answer on every common dataset."),
        "counters_match_prediction": ("Counters match prediction",
                                      "Instrumented counters equal the exact analytical count."),
        "results_consistent_across_repetitions": ("Consistent across repetitions",
                                                  "Same answer and count in every repetition."),
        "datasets_unchanged_by_algorithms": ("Datasets unchanged",
                                             "SHA-256 of every dataset identical before/after."),
        "all_checks_passed": ("ALL CHECKS PASSED", "Overall verdict."),
    }
    for key, value in report.validation().items():
        shown = _yes_no(value) if isinstance(value, bool) else value
        label, meaning = labels.get(key, (key, ""))
        _write_row(ws, row, [label, shown, meaning],
                   [None, FMT_INT, None], font=BOLD if key == "all_checks_passed" else None)
        if isinstance(value, bool):
            _flag_cell(ws, row, 2, value)
        row += 1
    _widths(ws, [40, 12, 70])


def _sheet_charts(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Charts")
    row = _title(ws, "Growth with n (log-log scale)",
                 "Only executed measurements are plotted; skipped points are left blank. On a "
                 "log-log plot a slope of 1 means linear growth and a slope of 2 quadratic.", 8)
    chart_row = row
    data_col = 12  # helper tables start at column L
    table_row = row
    for idx, scenario in enumerate(_scenario_order(report)):
        headers = ["n", "Time A (ms)", "Time B (ms)", "Operations A", "Operations B"]
        ws.cell(row=table_row, column=data_col, value=scenario).font = SECTION_FONT
        for c, text in enumerate(headers):
            cell = ws.cell(row=table_row + 1, column=data_col + c, value=text)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
        r = table_row + 2
        for n in report.config.sizes:
            a = report.summary_for(scenario, "A", n)
            b = report.summary_for(scenario, "B", n)
            vals = [n,
                    a.mean_time_ms if a and a.status == STATUS_EXECUTED else None,
                    b.mean_time_ms if b and b.status == STATUS_EXECUTED else None,
                    a.mean_comparisons if a and a.status == STATUS_EXECUTED else None,
                    b.mean_comparisons if b and b.status == STATUS_EXECUTED else None]
            for c, v in enumerate(vals):
                cell = ws.cell(row=r, column=data_col + c, value=v)
                cell.number_format = FMT_MS if c in (1, 2) else FMT_INT
            r += 1
        last = r - 1
        xref = Reference(ws, min_col=data_col, min_row=table_row + 2, max_row=last)
        for kind, cols, ylabel in (("Time", (1, 2), "Time (ms)"),
                                   ("Operations", (3, 4), "Comparisons")):
            chart = ScatterChart()
            chart.title = f"{kind} vs n - {scenario}"
            chart.style = 13
            chart.x_axis.title = "n (log scale)"
            chart.y_axis.title = f"{ylabel} (log scale)"
            chart.x_axis.scaling.logBase = 10
            chart.y_axis.scaling.logBase = 10
            chart.x_axis.delete = False
            chart.y_axis.delete = False
            chart.height = 7.5
            chart.width = 13
            for offset, name in zip(cols, ("A", "B")):
                yref = Reference(ws, min_col=data_col + offset, min_row=table_row + 2, max_row=last)
                series = Series(yref, xref, title=f"Algorithm {name}")
                series.marker.symbol = "circle"
                series.marker.size = 7
                chart.series.append(series)
            col_anchor = "A" if kind == "Time" else "F"
            ws.add_chart(chart, f"{col_anchor}{chart_row + idx * 16}")
        table_row = last + 3
    for c, w in enumerate([12, 14, 14, 18, 18], start=data_col):
        ws.column_dimensions[get_column_letter(c)].width = w


def _sheet_environment(wb: Workbook, report: BenchmarkReport) -> None:
    ws = wb.create_sheet("Environment")
    row = _title(ws, "Experiment conditions", "Recorded automatically at run time (slide 9).", 2)
    _header(ws, row, ["Item", "Value"])
    row += 1
    items = dict(report.environment)
    items["Started"] = report.started_at
    items["Finished"] = report.finished_at
    items["Total benchmark time"] = f"{report.total_seconds:,.1f} s"
    for spec in ALGORITHMS.values():
        items[f"Algorithm {spec['short']}"] = (f"{spec['name']} - time {spec['time_complexity']}, "
                                               f"extra space {spec['space_complexity']}")
    for key, value in items.items():
        _write_row(ws, row, [key, value], [None, None])
        ws.cell(row=row, column=1).font = BOLD
        row += 1
    _widths(ws, [30, 110])


# --------------------------------------------------------------------------- API
def write_excel(report: BenchmarkReport, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    _sheet_main_table(wb, report)
    _sheet_a_vs_b(wb, report)
    _sheet_averages(wb, report)
    _sheet_repetitions(wb, report)
    _sheet_edge_cases(wb, report)
    _sheet_skipped(wb, report)
    _sheet_datasets(wb, report)
    _sheet_validation(wb, report)
    _sheet_charts(wb, report)
    _sheet_environment(wb, report)
    wb.properties.title = "Lab 02 - Algorithm Benchmarking: Duplicate Detection"
    wb.properties.subject = "Comparison of O(n^2) vs O(n) duplicate detection"
    wb.properties.creator = "Lab 02 benchmark program"
    wb.save(path)
    return path


def verify_excel(path: Path, report: BenchmarkReport) -> list[str]:
    """Reopen the saved workbook and cross-check it against the in-memory report.

    Returns a list of problems (empty list = the file opens and is coherent).
    """
    problems: list[str] = []
    wb = load_workbook(path)  # raises if the file is not a valid .xlsx
    expected_sheets = ["Main Table", "A vs B", "Averages", "Repetitions", "Edge Cases",
                       "Skipped Tests", "Datasets", "Validation", "Charts", "Environment"]
    if wb.sheetnames != expected_sheets:
        problems.append(f"unexpected sheets: {wb.sheetnames}")
    reps = wb["Repetitions"]
    data_rows = reps.max_row - 4  # title (2 rows) + blank + header
    if data_rows != len(report.measurements):
        problems.append(f"'Repetitions' has {data_rows} rows, expected {len(report.measurements)}")
    main = wb["Main Table"]
    found: dict[tuple[str, int], object] = {}
    for r in main.iter_rows(min_row=4, values_only=True):
        if r and r[0] in ALGORITHMS and isinstance(r[1], int):
            found.setdefault((r[0], r[1]), r[3])
    for algorithm in ALGORITHMS:
        for n in report.config.sizes:
            if (algorithm, n) not in found:
                problems.append(f"'Main Table' lacks algorithm {algorithm}, n={n}")
    for s in report.summaries:
        if s.status != STATUS_EXECUTED and s.mean_time_ms is not None:
            problems.append(f"skipped test with a time value: {s.scenario} {s.algorithm} {s.n}")
    if len(wb["Charts"]._charts) != 2 * len(report.config.scenarios):
        problems.append("charts missing")
    return problems
