---
name: coding-mojo
description: Develop and run Mojo code in Claude.ai containers. Handles installation, compilation, and execution. Use when writing Mojo code, benchmarking Mojo vs Python, or when user mentions Mojo, Modular, or MAX. Routes to Modular's official skills (mojo-syntax, mojo-python-interop, mojo-gpu-fundamentals) for language-specific correction layers.
metadata:
  version: 0.1.0
---

# Mojo Development in Claude.ai Containers

Mojo is a systems programming language from Modular that combines Python-like syntax with C-level performance. This skill handles container setup and execution. For **language syntax and semantics**, defer to Modular's official skills at `github.com/modular/skills` — they are authoritative correction layers for pretrained knowledge.

## Installation

Install once per session. Takes ~30s. Prefer `uv` for speed; fall back to `pip` only if `uv` is not available.

```bash
if command -v uv &>/dev/null; then
  uv pip install --system modular 2>&1 | tail -5
else
  pip install --break-system-packages modular 2>&1 | tail -5
fi
mojo --version
```

Verify:
```bash
mojo -e 'print("Mojo ready")'
```

## Running Mojo Code

**Inline execution** (quick tests):
```bash
mojo -e 'print("hello")'
```

**File execution** (compile + run):
```bash
cat > /home/claude/example.mojo << 'EOF'
def main():
    print("Hello from Mojo")
EOF
mojo run /home/claude/example.mojo
```

**Build binary** (for benchmarking):
```bash
mojo build /home/claude/example.mojo -o /home/claude/example
/home/claude/example
```

Use `mojo build` for benchmarks — `mojo run` includes compilation overhead.

## Critical Syntax Corrections (v26.2)

Pretrained models generate outdated Mojo. These corrections are current as of Mojo 26.2:

| Wrong (pretrained) | Correct (26.2) | Notes |
|---|---|---|
| `fn main():` | `def main():` | `fn` is deprecated; `def` is the only function keyword |
| `let x = 5` | `var x = 5` | `let` removed; `var` for all bindings |
| `inout self` | `mut self` / `out self` | `mut` for mutation, `out` for `__init__` |
| `@parameter for` | `comptime for` | Compile-time loops |
| `List[Int](1, 2, 3)` | `[1, 2, 3]` | Collection literals |
| `from math import sqrt` | `from std.math import sqrt` | `std.` prefix required for stdlib |
| `__str__` / `Stringable` | `write_to` / `Writable` | String conversion protocol |
| `String(self.x)` for int→str | `String(self.x)` | This one is actually correct, but `str()` is not |

## Companion Skills (Modular Official)

These skills from `github.com/modular/skills` provide deep syntax correction layers. If they are installed in the user's skill set, read them before writing Mojo code:

- **mojo-syntax** — Comprehensive syntax corrections, type system, ownership model. **Always use when writing any Mojo code.**
- **mojo-python-interop** — Calling Python from Mojo, type conversion, extension modules. Use when mixing Mojo and Python.
- **mojo-gpu-fundamentals** — GPU programming (no CUDA syntax — Mojo has its own model). Reference only in Claude.ai containers (no GPU available).
- **new-modular-project** — Project scaffolding with Pixi or uv. Use when starting a new Mojo/MAX project locally.

If companion skills are not installed, the correction table above covers the most common pretrained errors. For deeper work, fetch the skill content directly:
```bash
curl -sL -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github.v3.raw" \
  "https://api.github.com/repos/modular/skills/contents/mojo-syntax/SKILL.md?ref=main"
```

## Container Constraints

- **No GPU**: Claude.ai containers are CPU-only. GPU skills are reference material for generating code the user will run locally.
- **Session-ephemeral**: Mojo installation doesn't persist across conversations. Reinstall each session.
- **Build artifacts**: Store in `/home/claude/`. Copy final outputs to `/mnt/user-data/outputs/`.
- **Timeout**: Long compilations or benchmarks may hit the ~200s bash timeout. Break work into smaller units.

## Benchmarking Pattern

Compare Mojo vs Python on the same algorithm:

```bash
# Python baseline
python3 -c "
import time
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
start = time.perf_counter()
fib(90)
print(f'Python: {(time.perf_counter() - start)*1e6:.1f} µs')
"

# Mojo version
cat > /home/claude/fib.mojo << 'EOF'
from std.time import perf_counter_ns

def fib(n: Int) -> Int:
    var a = 0
    var b = 1
    for _ in range(n):
        var tmp = a
        a = b
        b = tmp + b
    return a

def main():
    var start = perf_counter_ns()
    var result = fib(90)
    var elapsed = perf_counter_ns() - start
    print("Mojo:", elapsed, "ns (", result, ")")
EOF
mojo build /home/claude/fib.mojo -o /home/claude/fib
/home/claude/fib
```

Expected: Mojo is 50-100x faster than CPython on tight numeric loops. SIMD and parallelism widen the gap further but require mojo-syntax and mojo-gpu-fundamentals skills for correct usage.
