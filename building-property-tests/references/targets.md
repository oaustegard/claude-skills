# Targets, properties and generators

Load this when choosing what to test (step 1) and what to generate (step 3).
Each entry names the target, the property, and the oracle. Rank candidates by
how complex the implementation is against how simple the oracle is. A heavily
optimised structure that a list and a linear scan can check is the best target
there is.

## Property kinds

| Kind | Property | Oracle |
|---|---|---|
| Model-based differential | Every read after any history equals the model's read | Plain dict, list or set; linear scans; full recomputation |
| Path agreement | Every API path that promises the same answer gives it: batch vs single, ADC vs dense, packed vs unpacked, index at full probe vs flat scan, GPU vs CPU | The paths themselves, plus one brute-force anchor so they cannot all agree on a wrong answer |
| Round trip | `load(save(x)) == x` for every writer and reader pair, **including cross-class pairs** (class A's file read by class B) | Equality on every field, not only the payload |
| Warm equals cold | An answer is the same whether a cache, lazy table or compiled kernel is cold, warm, or warmed by a different reader | A fresh object built from the same inputs |
| Rejected operation is atomic | An operation that raises leaves every observable exactly as before | A snapshot taken before the call |
| Batch and chunk invariance | Results do not depend on batch size, chunk boundary, thread count or row order | The same input in one batch |
| Copy, pickle and snapshot | A copy behaves like the original after the original is mutated or freed; a pickle round trip works in a fresh process | The original's answers |
| Metamorphic | A known transform of the input gives a known transform of the output: scaling, permutation, negation, adding a constant that must not reorder | The untransformed run |
| Partial oracle | A cheap check of an expensive answer: every returned node is reachable, every edge exists, output sorted, indices in range | The check alone; it is sound and not complete, so pair it with a model |
| Guard totality | Every mismatch the docs say raises does raise, on every read path, with caches warm and cold | The documented error |
| Equality, hash, order | Equal values hash equally; equal values built by different histories compare equal; canonical forms are stable | Deliberately generated equal pairs (random pairs are almost never equal) |
| Validator sensitivity | A validator accepts valid objects and rejects each single-constraint corruption | Constructed corruptions |

## Where bugs were found (diagnosed)

- **Shapes the suite never uses.** remex's `.npz` writers disagreed only when
  `d * bits % 8 != 0`. The existing suite passed because no test read one
  class's file with the other at such a width (2026-11-16). Grep the existing
  tests for the sizes, widths and modes they use, and generate the others first.
- **Warm cache skipping a guard.** `Quantizer.search` checked bits and mean only
  on a cold container. Three of four independent harnesses found it, because
  each crossed "warm" with "foreign reader" (2026-11-16).
- **Rejected first operation.** `RemexIndex.add([])` raised, but set `dim=0`
  first, and every later add failed (2026-11-16).
- **Cache keyed on the wrong thing.** The bm25 skill's index cache hashed the
  path and filters, never the file contents, so an edited file returned stale
  text (2026-11-16).
- **Raw pointers surviving a copy.** An object caching `array.ctypes.data`
  integers segfaulted after pickle or deepcopy (2026-11-16).

## Generators

- **Small pools.** Three or four keys, a handful of values. Large domains
  produce disjoint keys and nothing interacts. Generate unequal overwrite
  values, so a stale read is visible.
- **Cross the classes deliberately.** Build the interesting conjunction in one
  rule (warm × foreign reader × scalar mode) rather than hoping separate rules
  line up. A guard property built from separate rules failed in 5 of 6 runs at
  400 examples. Restructured to cross every kind in one call, it failed every
  time (remex search area, 2026-11-16).
- **Derive, don't filter.** Build dependent inputs with `st.data()`,
  `flatmap` or `builds`. `assume()` or `.filter()` that rejects most cases
  starves the search, and Hypothesis reports it as a health check.
- **Draw domains from the registry.** `st.sampled_from(sorted(REGISTRY))`, not
  a hand-copied list: a copy misses the member someone adds next.
  `declaring-invariants/scripts/totality_lint.py` flags hand lists in
  `parametrize`. Check `sampled_from` lists by eye.
- **Edge values as their own strategy.** Empty, singleton, n < k, k = n,
  duplicates, zero vectors, ties, extremes of every dtype, odd and non-aligned
  sizes, values on boundaries. Mix them in with `st.one_of`.
- **Reads are operations.** A read can populate a cache. Generate histories
  with delayed reads as well as frequent ones, or a stale-cache bug never gets
  the read-then-mutate-then-read it needs.
- **Event every class you rely on.** `event("overwrite-after-read")` and
  `scripts/hypothesis_stats.py --min overwrite-after-read=5`. A class that never
  fires is a property that never ran.

## Tolerances

Derive tolerances from the arithmetic, not from comfort. Use exact equality
where the docs promise it ("byte-identical", "same bits"); several remex
findings were 1-ulp differences that a tolerance would have hidden. Where
float32 cancellation is real, compare path against path at exact equality and
use the float64 oracle only within a tolerance scaled to the magnitude. One
harness flagged a centred large-norm case: CPU and GPU agreed exactly and were
both off from the float64 oracle by float32 cancellation, which is not a bug
(2026-11-16).
