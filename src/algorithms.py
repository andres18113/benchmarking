"""Duplicate-detection algorithms with instrumented operation counters.

Both functions answer the same question -- "does the list contain at least one
repeated value?" -- and follow the pseudocode from slide 6 of the Week 2 deck:

* Algorithm A (nested loops): compare every element with every element after it.
* Algorithm B (single pass): remember the values already seen in a hash set.

The counted operation is the one the slides count: ``comparisons``.

* In A, one comparison is one evaluation of ``data[i] == data[j]``.
* In B, one comparison is one membership test ``value in seen``.

The functions never modify the input list, so both algorithms can be fed the
very same list object during a benchmark.

The module also contains two *analytical predictors* (``predicted_comparisons_a``
and ``predicted_comparisons_b``). They compute, without running the algorithms,
how many comparisons each algorithm will perform on a given list. They are used
to (1) cross-check the instrumented counters in the tests and in every benchmark
run, and (2) decide in advance whether a run of Algorithm A would exceed the
configured operation limit. Their output is always labelled as a prediction and
is never reported as a measurement.
"""

from __future__ import annotations

import sys
from typing import NamedTuple, Sequence


class DetectionResult(NamedTuple):
    """Outcome of one execution of a duplicate-detection algorithm."""

    has_duplicates: bool
    comparisons: int
    aux_elements: int  # elements stored in auxiliary structures (memory proxy)
    aux_bytes: int  # bytes used by those auxiliary structures (sys.getsizeof)


def has_duplicates_nested_loops(data: Sequence[int]) -> DetectionResult:
    """Algorithm A -- compare each element against all the following ones.

    Slide pseudocode::

        comparisons = 0
        for i = 0 to n - 1:
            for j = i + 1 to n - 1:
                comparisons++
                if data[i] == data[j]:
                    return true
        return false

    Time: O(n^2) worst case, O(1) best case.  Extra space: O(1).
    """
    comparisons = 0
    n = len(data)
    for i in range(n):
        for j in range(i + 1, n):
            comparisons += 1
            if data[i] == data[j]:
                return DetectionResult(True, comparisons, 0, 0)
    return DetectionResult(False, comparisons, 0, 0)


def has_duplicates_hash_set(data: Sequence[int]) -> DetectionResult:
    """Algorithm B -- single pass that stores already-seen values in a set.

    Slide pseudocode::

        comparisons = 0
        seen = {}
        for value in data:
            comparisons++
            if value is in seen:
                return true
            add value to seen
        return false

    Time: O(n) worst case (average O(1) per hash lookup), O(1) best case.
    Extra space: O(n) worst case (the set may hold n - 1 or n elements).
    """
    comparisons = 0
    seen: set[int] = set()
    for value in data:
        comparisons += 1
        if value in seen:
            return DetectionResult(True, comparisons, len(seen), sys.getsizeof(seen))
        seen.add(value)
    return DetectionResult(False, comparisons, len(seen), sys.getsizeof(seen))


# ---------------------------------------------------------------------------
# Analytical predictors (used for validation and for the A safety limit)
# ---------------------------------------------------------------------------

def worst_case_comparisons_a(n: int) -> int:
    """Comparisons performed by Algorithm A when no duplicate exists: n(n-1)/2."""
    return n * (n - 1) // 2


def first_duplicate_pair_a(data: Sequence[int]) -> tuple[int, int] | None:
    """Return the (i, j) pair at which Algorithm A stops, or None if no duplicate.

    A scans pairs in lexicographic order, so it stops at the smallest ``i`` that
    has an equal value later in the list, paired with the *next* occurrence ``j``
    of that value. That ``i`` is always the first occurrence of some repeated
    value and ``j`` is that value's second occurrence.
    """
    first_index: dict[int, int] = {}
    second_index: dict[int, int] = {}
    for idx, value in enumerate(data):
        if value not in first_index:
            first_index[value] = idx
        elif value not in second_index:
            second_index[value] = idx
    if not second_index:
        return None
    value = min(second_index, key=lambda v: first_index[v])
    return first_index[value], second_index[value]


def predicted_comparisons_a(data: Sequence[int]) -> int:
    """Exact number of comparisons Algorithm A will perform on ``data``.

    If A stops at pair (i, j), every row k < i was fully scanned
    (n - 1 - k comparisons each) and row i contributed j - i comparisons::

        sum_{k=0}^{i-1} (n - 1 - k) + (j - i)  =  i(n - 1) - i(i - 1)/2 + (j - i)
    """
    n = len(data)
    pair = first_duplicate_pair_a(data)
    if pair is None:
        return worst_case_comparisons_a(n)
    i, j = pair
    return i * (n - 1) - i * (i - 1) // 2 + (j - i)


def first_repeat_index_b(data: Sequence[int]) -> int | None:
    """Index of the first element whose value already appeared earlier, or None."""
    seen: set[int] = set()
    for idx, value in enumerate(data):
        if value in seen:
            return idx
        seen.add(value)
    return None


def predicted_comparisons_b(data: Sequence[int]) -> int:
    """Exact number of comparisons Algorithm B will perform on ``data``."""
    idx = first_repeat_index_b(data)
    return len(data) if idx is None else idx + 1


ALGORITHMS = {
    "A": {
        "name": "A - Nested loops (pairwise comparison)",
        "short": "A",
        "function": has_duplicates_nested_loops,
        "predictor": predicted_comparisons_a,
        "time_complexity": "O(n^2) worst case",
        "space_complexity": "O(1)",
    },
    "B": {
        "name": "B - Single pass (hash set)",
        "short": "B",
        "function": has_duplicates_hash_set,
        "predictor": predicted_comparisons_b,
        "time_complexity": "O(n) worst case (average O(1) per lookup)",
        "space_complexity": "O(n)",
    },
}
