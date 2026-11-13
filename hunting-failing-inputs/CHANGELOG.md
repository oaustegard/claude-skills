# Changelog

## 0.3.1 — 2026-11-13

The references were trimmed the same way (268 lines down to 172). The fuzz-comparison
tables and the story of where the method came from were removed. The
measurements they held: random testing found the Python bug after 1,581 inputs
with `strict` and missed it in 200,000 without; JS, 4,413 with and none in
200,000 without; C libFuzzer, about 250 runs with ASan and none in 77M without;
Go fuzzing, under 1 s with `cap == len` and none in 30 s without.

## 0.3.0 — 2026-11-13

SKILL.md trimmed to procedure only (about 230 lines down to 131). The intro,
provenance and results numbers were removed: they live here and in the
language references. Source: Google Developers blog, 2026-11-12, "Catch Go bugs
that fuzzing misses with Gemini and a constraint solver".

## 0.2.0 — 2026-11-13

Renamed from `hunting-go-bounds-panics` and generalised from Go to Python,
JavaScript/TypeScript, C and WGSL. Go is now one of five language references.

- `scripts/list_traps.py`: lists traps per language using tree-sitter, and
  marks each as raises, silent or UB.
- `scripts/z3traps.py` (was `z3go.py`): adds Python, JS and C predicates
  (`py_index_oob`, `negative_index`, `slice_truncates`, `span_oob`, `js_int32`)
  and literal rendering for each language. `to_int` is now `widen`, and
  `slice_oob` is now `go_slice_oob`.
- Strict harnesses that make silent failures loud: `strict.py`, `strict.mjs`,
  and `wgsl_guard.py`, which instruments WGSL indexes into an `_oob` buffer.
- `examples/<lang>/` and `scripts/selftest.py`: a planted-bug example per
  language, rerun end to end, including the WGSL one on SwiftShader WebGPU.

## 0.1.0 — 2026-11-13

First version, as `hunting-go-bounds-panics`. Go bounds checks listed with
`-d=ssa/check_bce`, modelled in Z3, and replayed with `go test`.

## [0.3.0] - 2026-11-13

### Other

- hunting-failing-inputs: trim SKILL.md to the procedure

## [0.2.1] - 2026-11-13

### Other

- hunting-failing-inputs: cut description to a trigger (870 to 245 chars)

## [0.2.0] - 2026-11-13

### Other

- hunting-failing-inputs: generalise the Z3 trap hunt beyond Go