"""Correctness tests for both duplicate-detection algorithms and their counters."""

import random
import sys
import unittest
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from algorithms import (  # noqa: E402
    first_duplicate_pair_a,
    has_duplicates_hash_set,
    has_duplicates_nested_loops,
    predicted_comparisons_a,
    predicted_comparisons_b,
    worst_case_comparisons_a,
)

BOTH = (has_duplicates_nested_loops, has_duplicates_hash_set)


def brute_force_truth(data):
    return len(set(data)) != len(data)


class EdgeCaseTests(unittest.TestCase):
    """Slide 9 edge cases: empty list, one element, all equal, all unique."""

    CASES = [
        ([], False),
        ([7], False),
        ([5, 5], True),
        ([5, 6], False),
        ([4] * 1000, True),
        (list(range(1000)), False),
        (list(range(999, -1, -1)), False),
        ([-3, 0, 7, -3, 2], True),
        ([-5, -1, 0, 3, 9], False),
        ([8, 3, 12, 8, 5, 9, 3, 20], True),  # slide 5 example
        ([0, 0], True),
        ([10 ** 12, -10 ** 12, 10 ** 12], True),
    ]

    def test_expected_answers(self):
        for data, expected in self.CASES:
            for algorithm in BOTH:
                with self.subTest(algorithm=algorithm.__name__, data=data[:10]):
                    self.assertIs(algorithm(data).has_duplicates, expected)

    def test_empty_list_counts(self):
        self.assertEqual(has_duplicates_nested_loops([]).comparisons, 0)
        self.assertEqual(has_duplicates_hash_set([]).comparisons, 0)

    def test_single_element_counts(self):
        self.assertEqual(has_duplicates_nested_loops([1]).comparisons, 0)
        self.assertEqual(has_duplicates_hash_set([1]).comparisons, 1)

    def test_all_equal_stops_immediately(self):
        data = [4] * 1000
        self.assertEqual(has_duplicates_nested_loops(data).comparisons, 1)
        self.assertEqual(has_duplicates_hash_set(data).comparisons, 2)


class AgreementTests(unittest.TestCase):
    """A and B must always return the same (correct) answer."""

    def test_exhaustive_small_lists(self):
        # Every list of length 0..6 over the alphabet {0, 1, 2, 3}: 5,461 lists.
        for length in range(7):
            for combo in product(range(4), repeat=length):
                data = list(combo)
                truth = brute_force_truth(data)
                a = has_duplicates_nested_loops(data)
                b = has_duplicates_hash_set(data)
                self.assertEqual(a.has_duplicates, truth, data)
                self.assertEqual(b.has_duplicates, truth, data)

    def test_random_lists(self):
        rng = random.Random(12345)
        for _ in range(2000):
            n = rng.randint(0, 60)
            data = [rng.randint(-50, 50) for _ in range(n)]
            truth = brute_force_truth(data)
            self.assertEqual(has_duplicates_nested_loops(data).has_duplicates, truth)
            self.assertEqual(has_duplicates_hash_set(data).has_duplicates, truth)

    def test_input_is_not_modified(self):
        rng = random.Random(7)
        data = [rng.randint(0, 100) for _ in range(200)]
        copy = list(data)
        for algorithm in BOTH:
            algorithm(data)
            self.assertEqual(data, copy)


class CounterTests(unittest.TestCase):
    """The instrumented counters must equal the analytical formulas."""

    def test_worst_case_a_is_n_choose_2(self):
        for n in (0, 1, 2, 3, 10, 100, 1000):
            data = list(range(n))
            self.assertEqual(has_duplicates_nested_loops(data).comparisons, n * (n - 1) // 2)
            self.assertEqual(worst_case_comparisons_a(n), n * (n - 1) // 2)

    def test_worst_case_b_is_n(self):
        for n in (0, 1, 2, 10, 1000, 10_000):
            data = list(range(n))
            self.assertEqual(has_duplicates_hash_set(data).comparisons, n)

    def test_predictors_match_counters_on_random_lists(self):
        rng = random.Random(2026)
        for _ in range(1500):
            n = rng.randint(0, 80)
            data = [rng.randint(0, rng.randint(1, 200)) for _ in range(n)]
            self.assertEqual(has_duplicates_nested_loops(data).comparisons,
                             predicted_comparisons_a(data), data)
            self.assertEqual(has_duplicates_hash_set(data).comparisons,
                             predicted_comparisons_b(data), data)

    def test_late_duplicate_counts(self):
        n = 500
        data = list(range(n))
        data[-1] = data[-2]
        # A scans rows 0..n-3 completely (n(n-1)/2 - 1 comparisons) and then makes the
        # single comparison of row n-2: exactly n(n-1)/2, the same as the worst case.
        self.assertEqual(has_duplicates_nested_loops(data).comparisons,
                         worst_case_comparisons_a(n))
        self.assertEqual(has_duplicates_hash_set(data).comparisons, n)

    def test_first_pair(self):
        self.assertEqual(first_duplicate_pair_a([8, 3, 12, 8, 5, 9, 3, 20]), (0, 3))
        self.assertIsNone(first_duplicate_pair_a([1, 2, 3]))

    def test_auxiliary_memory(self):
        a = has_duplicates_nested_loops(list(range(100)))
        b = has_duplicates_hash_set(list(range(100)))
        self.assertEqual((a.aux_elements, a.aux_bytes), (0, 0))
        self.assertEqual(b.aux_elements, 100)
        self.assertGreater(b.aux_bytes, 0)


if __name__ == "__main__":
    unittest.main()
