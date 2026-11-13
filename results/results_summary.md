# Benchmark results (generated automatically)

- Run: 2026-11-12 23:39:31 -> 2026-11-12 23:39:49 (17.3 s)
- Python: CPython 3.13.15 | CPU: Intel(R) Core(TM) i9-14900HX
- Repetitions per measurement: 3 | Seed: 2026
- Algorithm A limit: 100,000,000 comparisons
- Command: `python src/main.py `

Operations = comparisons (A: `data[i] == data[j]`, B: `value in seen`). Time = mean wall-clock milliseconds measured with `time.perf_counter()`.

## Random data, no duplicates (all unique) - worst case (`random_unique`)

| Algorithm | n | Operations | Time (ms) | Answer |
|---|---:|---:|---:|---|
| A | 100 | 4,950 | 0.1678 | no duplicates |
| A | 1,000 | 499,500 | 19.6791 | no duplicates |
| A | 10,000 | 49,995,000 | 1,821.3574 | no duplicates |
| A | 100,000 | SKIPPED | SKIPPED | - |
| A | 1,000,000 | SKIPPED | SKIPPED | - |
| B | 100 | 100 | 0.0064 | no duplicates |
| B | 1,000 | 1,000 | 0.0648 | no duplicates |
| B | 10,000 | 10,000 | 0.6377 | no duplicates |
| B | 100,000 | 100,000 | 9.1023 | no duplicates |
| B | 1,000,000 | 1,000,000 | 174.1207 | no duplicates |

## Random data with duplicates (values drawn from [0, n)) (`random_with_duplicates`)

| Algorithm | n | Operations | Time (ms) | Answer |
|---|---:|---:|---:|---|
| A | 100 | 67 | 0.0024 | duplicates |
| A | 1,000 | 26 | 0.0014 | duplicates |
| A | 10,000 | 158 | 0.0045 | duplicates |
| A | 100,000 | 22,804 | 0.8059 | duplicates |
| A | 1,000,000 | 1,221,377 | 48.8944 | duplicates |
| B | 100 | 8 | 0.0014 | duplicates |
| B | 1,000 | 18 | 0.0014 | duplicates |
| B | 10,000 | 159 | 0.0071 | duplicates |
| B | 100,000 | 325 | 0.0222 | duplicates |
| B | 1,000,000 | 1,583 | 0.1229 | duplicates |

## Early duplicate (positions 0 and 1) - best case (`early_duplicate`)

| Algorithm | n | Operations | Time (ms) | Answer |
|---|---:|---:|---:|---|
| A | 100 | 1 | 0.0007 | duplicates |
| A | 1,000 | 1 | 0.0008 | duplicates |
| A | 10,000 | 1 | 0.0008 | duplicates |
| A | 100,000 | 1 | 0.0008 | duplicates |
| A | 1,000,000 | 1 | 0.0009 | duplicates |
| B | 100 | 2 | 0.0007 | duplicates |
| B | 1,000 | 2 | 0.0009 | duplicates |
| B | 10,000 | 2 | 0.0009 | duplicates |
| B | 100,000 | 2 | 0.0007 | duplicates |
| B | 1,000,000 | 2 | 0.0007 | duplicates |

## Late duplicate (last two positions only) (`late_duplicate`)

| Algorithm | n | Operations | Time (ms) | Answer |
|---|---:|---:|---:|---|
| A | 100 | 4,950 | 0.1352 | duplicates |
| A | 1,000 | 499,500 | 17.0112 | duplicates |
| A | 10,000 | 49,995,000 | 1,683.3825 | duplicates |
| A | 100,000 | SKIPPED | SKIPPED | - |
| A | 1,000,000 | SKIPPED | SKIPPED | - |
| B | 100 | 100 | 0.0045 | duplicates |
| B | 1,000 | 1,000 | 0.0567 | duplicates |
| B | 10,000 | 10,000 | 0.5953 | duplicates |
| B | 100,000 | 100,000 | 7.4048 | duplicates |
| B | 1,000,000 | 1,000,000 | 130.5248 | duplicates |

## Skipped tests

| Scenario | Algorithm | n | Required comparisons (prediction) | Limit |
|---|---|---:|---:|---:|
| random_unique | A | 100,000 | 4,999,950,000 | 100,000,000 |
| random_unique | A | 1,000,000 | 499,999,500,000 | 100,000,000 |
| late_duplicate | A | 100,000 | 4,999,950,000 | 100,000,000 |
| late_duplicate | A | 1,000,000 | 499,999,500,000 | 100,000,000 |

## Validation

- timed executions: **174**
- executed summaries: **58**
- skipped tests: **4**
- all answers correct: **True**
- a and b pairs compared: **27**
- a and b always agree: **True**
- counters match prediction: **True**
- results consistent across repetitions: **True**
- datasets unchanged by algorithms: **True**
- all checks passed: **True**
