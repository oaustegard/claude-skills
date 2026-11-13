# Changelog

## 0.1.0 — 2026-11-13

First version. Adapts the method from Google's 2026-11-12 post "Catch Go bugs
that fuzzing misses with Gemini and a constraint solver": list the bounds
checks the compiler kept, model the path to each in Z3, and replay each `sat`
as a `go test` reproducer. Here the agent writes the model, where the post used
Gemini.

- `scripts/bce_targets.py`: lists the surviving checks, with their functions
  and source lines.
- `scripts/z3go.py`: Go index and slice semantics, the cap == len harness,
  per-trap solving with optional in-order reachability, and conversion of a
  model to bytes.
- `references/worked-example.md`: the post's two planted bug classes, run end
  to end on go1.24.7.

## [0.1.0] - 2026-11-13

### Other

- hunting-go-bounds-panics: Z3 path models for Go bounds checks
