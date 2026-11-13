"""Reproducible dataset generation for the duplicate-detection benchmark.

Every dataset is produced by its own ``random.Random`` instance seeded with the
string ``"<base_seed>:<scenario>:<n>"``. String seeds are hashed with SHA-512 by
the ``random`` module, so the same base seed always yields exactly the same
lists on any machine and Python 3 version, independent of the generation order
and of ``PYTHONHASHSEED``.

A SHA-256 fingerprint of each list is stored with the results. It is computed
before and after the benchmark of that list to prove that both algorithms
received identical, unmodified data.
"""

from __future__ import annotations

import hashlib
import random
from array import array
from dataclasses import dataclass, field
from typing import Callable

DEFAULT_SIZES = (100, 1_000, 10_000, 100_000, 1_000_000)
DEFAULT_SEED = 2026


@dataclass
class BenchmarkCase:
    """A list to benchmark plus the metadata needed to validate the answers."""

    scenario: str  # identifier, e.g. "random_unique"
    label: str  # human-readable description
    category: str  # "size scenario" or "edge case"
    data: list[int] = field(repr=False)
    expected: bool  # ground truth: does the list contain duplicates?
    seed: str | None = None  # derived seed string (None for fixed edge cases)

    @property
    def n(self) -> int:
        return len(self.data)


def fingerprint(data: list[int]) -> str:
    """SHA-256 of the list contents (as signed 64-bit integers)."""
    return hashlib.sha256(array("q", data).tobytes()).hexdigest()


def derived_seed(base_seed: int, scenario: str, n: int) -> str:
    return f"{base_seed}:{scenario}:{n}"


# ---------------------------------------------------------------------------
# Size scenarios (run for every n in the configured sizes)
# ---------------------------------------------------------------------------

def _unique_values(n: int, rng: random.Random) -> list[int]:
    """n distinct integers drawn without replacement from [0, 10n), shuffled."""
    return rng.sample(range(10 * n), n)


def gen_random_unique(n: int, rng: random.Random) -> list[int]:
    """All values distinct: worst case for both algorithms (full scan)."""
    return _unique_values(n, rng)


def gen_random_with_duplicates(n: int, rng: random.Random) -> list[int]:
    """n values drawn *with* replacement from [0, n): realistic random data.

    By the birthday paradox, duplicates are practically certain for n >= 100;
    the generator still enforces it so that the expected answer is always True.
    """
    data = rng.choices(range(n), k=n)
    if len(set(data)) == n:  # astronomically unlikely, but keep ground truth exact
        data[-1] = data[0]
    return data


def gen_early_duplicate(n: int, rng: random.Random) -> list[int]:
    """Distinct values except data[1] == data[0]: best case for both algorithms."""
    data = _unique_values(n, rng)
    data[1] = data[0]
    return data


def gen_late_duplicate(n: int, rng: random.Random) -> list[int]:
    """Distinct values except data[n-1] == data[n-2]: the only repeated pair is
    at the very end, so both algorithms must scan (almost) everything."""
    data = _unique_values(n, rng)
    data[-1] = data[-2]
    return data


SCENARIOS: dict[str, dict] = {
    "random_unique": {
        "label": "Random data, no duplicates (all unique) - worst case",
        "generator": gen_random_unique,
        "expected": False,
    },
    "random_with_duplicates": {
        "label": "Random data with duplicates (values drawn from [0, n))",
        "generator": gen_random_with_duplicates,
        "expected": True,
    },
    "early_duplicate": {
        "label": "Early duplicate (positions 0 and 1) - best case",
        "generator": gen_early_duplicate,
        "expected": True,
    },
    "late_duplicate": {
        "label": "Late duplicate (last two positions only)",
        "generator": gen_late_duplicate,
        "expected": True,
    },
}


def build_size_case(scenario: str, n: int, base_seed: int = DEFAULT_SEED) -> BenchmarkCase:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario}'. Valid: {', '.join(SCENARIOS)}")
    if n < 2:
        raise ValueError("Size scenarios need n >= 2 (use the edge cases for n < 2)")
    spec = SCENARIOS[scenario]
    seed = derived_seed(base_seed, scenario, n)
    generator: Callable[[int, random.Random], list[int]] = spec["generator"]
    data = generator(n, random.Random(seed))
    return BenchmarkCase(scenario, spec["label"], "size scenario", data, spec["expected"], seed)


# ---------------------------------------------------------------------------
# Edge cases (slide 9: empty list, one element, all equal, all unique, ...)
# ---------------------------------------------------------------------------

def build_edge_cases() -> list[BenchmarkCase]:
    def case(name: str, label: str, data: list[int], expected: bool) -> BenchmarkCase:
        return BenchmarkCase(name, label, "edge case", data, expected)

    extremes = list(range(1, 1_000))
    extremes.append(1)  # the only repeated pair is first/last
    return [
        case("empty_list", "Empty list", [], False),
        case("single_element", "Single element", [7], False),
        case("two_equal", "Two equal elements", [5, 5], True),
        case("two_distinct", "Two distinct elements", [5, 6], False),
        case("all_equal_1000", "All equal (1,000 copies of 4)", [4] * 1_000, True),
        case("all_unique_sorted_1000", "All unique, sorted 0..999", list(range(1_000)), False),
        case("all_unique_reversed_1000", "All unique, reversed 999..0", list(range(999, -1, -1)), False),
        case("first_and_last_equal_1000", "Only first and last are equal (n = 1,000)", extremes, True),
        case("negatives_and_zero", "Negatives and zero with a repeat", [-3, 0, 7, -3, 2], True),
        case("negatives_unique", "Negatives and zero, all unique", [-5, -1, 0, 3, 9], False),
        case("slide_example", "Slide 5 example [8, 3, 12, 8, 5, 9, 3, 20]",
             [8, 3, 12, 8, 5, 9, 3, 20], True),
    ]
