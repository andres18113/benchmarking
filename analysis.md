# Technical analysis — Duplicate detection: nested loops (A) vs hash set (B)

## 1. What is counted

Following slide 6, the counted operation is the **comparison**:

* **A:** one evaluation of `data[i] == data[j]`.
* **B:** one membership test `value in seen`.

Both counters are instrumented in the code (`src/algorithms.py`). They are also predicted with
closed-form formulas (below) and the program checks, in every run, that counter = prediction.

## 2. Time complexity

### Algorithm A — nested loops

```
for i in 0 .. n-1:
    for j in i+1 .. n-1:
        comparisons += 1
        if data[i] == data[j]: return True
return False
```

Row `i` of the inner loop performs `n − 1 − i` comparisons. Without a duplicate every row runs to
the end:

$$C_A(n) = \sum_{i=0}^{n-1} (n-1-i) = \frac{n(n-1)}{2} \in \Theta(n^2)$$

If A stops at the first pair `(i, j)` (smallest `i` that has a later equal value, `j` its next
occurrence), all rows before `i` were complete:

$$C_A = i(n-1) - \frac{i(i-1)}{2} + (j - i)$$

| Case | Example | Comparisons | Order |
|---|---|---|---|
| Best | `data[0] == data[1]` | 1 | Θ(1) |
| Worst (no duplicates) | all unique | n(n−1)/2 | Θ(n²) |
| Only the last two are equal | `data[n-2] == data[n-1]` | n(n−1)/2 (exactly the worst case) | Θ(n²) |
| Only the first and last are equal | `data[0] == data[n-1]` | n − 1 | Θ(n) |

### Algorithm B — hash set

```
seen = {}
for value in data:
    comparisons += 1
    if value in seen: return True
    seen.add(value)
return False
```

Each element is tested once. If the first repeated value is at index `k`, B performs `k + 1`
comparisons; without duplicates it performs exactly `n`:

$$C_B(n) = n \in \Theta(n)$$

A Python `set` is a hash table: `in` and `add` cost O(1) on average (amortised for `add`, because
the table occasionally resizes). In the theoretical worst case — every value colliding in the
hash table — one lookup degrades to O(n) and B to O(n²), but this does not happen with integer
keys like the ones used here (Python hashes a small int to itself).

| Case | Comparisons | Order |
|---|---|---|
| Best (`data[0] == data[1]`) | 2 | Θ(1) |
| Worst (no duplicates / duplicate at the end) | n | Θ(n) average |

## 3. Space complexity

| | Extra memory | Why |
|---|---|---|
| **A** | **O(1)** | Only the indices `i`, `j` and the counter. |
| **B** | **O(n)** | The set stores up to n values (n − 1 when the only duplicate is the last element). |

The workbook reports B's extra memory with two real values per run: the number of elements
stored in the set and `sys.getsizeof(seen)`, the size of the hash table itself (the integer
objects are shared with the input list, so the table is the additional memory).

## 4. Why the counted operation is not the whole story

A comparison in A is a cheap integer equality; a comparison in B is a hash-table lookup
(hash, index, probe, compare) plus an insertion. One "operation" of B is therefore several times
more expensive than one of A. Counting operations predicts **growth** (how cost changes with n),
while timing captures the **constant factors** and hardware effects. Both are needed — which is
exactly the point of the lab: *efficiency = measurement + analysis*.
