# hunting-failing-inputs

Find inputs that make a parser, decoder or WGSL compute shader index out of
bounds, slice past its end, divide by zero or overflow. Each operation that can
fail on bad input (a **trap**) is modelled in Z3. A satisfying input is then
replayed inside a strict harness that makes silent failures loud.

It finds the inputs random fuzzing misses: those that reach a trap only
through a narrow arithmetic condition, such as a length field that wraps, or a
negative index that Python or JavaScript silently accepts.

## Languages

| Language | Trap listing | Strict harness |
|---|---|---|
| Python | `scripts/list_traps.py` | `scripts/strict.py` |
| JavaScript / TypeScript | `scripts/list_traps.py` | `scripts/strict.mjs` |
| C | `scripts/list_traps.py` | ASan + UBSan, input in an exact-size `malloc` |
| WGSL | `scripts/list_traps.py` | `scripts/wgsl_guard.py` (counts bad indexes in an `_oob` buffer) |
| Go | `scripts/bce_targets.py` (from `-d=ssa/check_bce`) | `d = d[:len(d):len(d)]` |

## Quick start

```bash
python3 -m pip install z3-solver tree-sitter-language-pack
SKILL=/mnt/skills/user/hunting-failing-inputs
python3 $SKILL/scripts/list_traps.py parser.py --func parse_record
python3 $SKILL/scripts/selftest.py      # optional; SKIP means a missing toolchain
```

Then model one pure function with `scripts/z3traps.py`, copying the nearest
example in `examples/<lang>/`. Each language's failure semantics and the
predicate for each trap kind are in `references/<lang>.md`.

## What a result means

- A `sat` that fails at the trap inside the strict harness is a bug, with a
  reproducer.
- `unsat` means none was found within the stated length bound, not "safe". It
  counts only alongside a negative control that went `sat`.
- `unknown`, or a model that needs more than about 15 unrolled iterations, is
  reported as **unmodelled**.

## Related skills

- `building-property-tests`: wrong results that no precondition expresses,
  checked against a reference model.
- `gating`: whether an existing check can go red at all.

## Contents

| Path | What |
|---|---|
| `SKILL.md` | The procedure, routing, verification and failure modes |
| `scripts/z3traps.py` | Harness, trap predicates per language, literal rendering |
| `scripts/list_traps.py`, `scripts/bce_targets.py` | Trap listing (tree-sitter; Go via the compiler) |
| `scripts/strict.py`, `strict.mjs`, `wgsl_guard.py` | Strict harnesses |
| `references/<lang>.md` | Semantics and predicates for Python, JavaScript, C, WGSL and Go |
| `examples/<lang>/` | A planted-bug model and reproducer per language |

The method follows the Google Developers blog post "Catch Go bugs that fuzzing
misses with Gemini and a constraint solver" (2026-11-12). This skill
generalises it from Go to five languages.
