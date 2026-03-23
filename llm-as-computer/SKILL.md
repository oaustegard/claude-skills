---
name: llm-as-computer
description: Execute programs through a compiled transformer — every instruction fetch and stack read is a parabolic attention head (dot-product → argmax → value). Use when user wants to run stack machine programs, compute Fibonacci/multiply/power/sums via attention, demonstrate LLM-as-computer concepts, or mentions Percepta.
---

# LLM-as-Computer

A Forth-like stack machine where every memory access is a real attention head operation: parabolic key encoding → dot product → argmax → value extraction. Programs are compiled into weight matrices, not trained.

Based on [Percepta's "Can LLMs Be Computers?"](https://percepta.ai/blog/can-llms-be-computers) and validated in [oaustegard/llm-as-computer](https://github.com/oaustegard/llm-as-computer).

## Quick Start

```python
import sys; sys.path.insert(0, "/mnt/skills/user/llm-as-computer")
from run import run, fib, multiply, power2, sum_n

# Run raw assembly
result, output = run("PUSH 3\nPUSH 4\nADD\nHALT")
print(output)  # RESULT: 7

# Built-in algorithms
result, output = fib(10)          # 55 (111 steps, ~80µs)
result, output = multiply(7, 8)   # 56
result, output = power2(16)       # 65536
result, output = sum_n(100)       # 5050

# Without trace (just result + timing)
result, output = fib(20, trace=False)
```

## ISA

| Op | Stack effect | Description |
|---|---|---|
| `PUSH n` | → n | Push immediate value |
| `POP` | a → | Drop top |
| `ADD` | a b → (a+b) | Add top two |
| `SUB` | a b → (b-a) | Subtract (second minus top) |
| `DUP` | a → a a | Duplicate top |
| `SWAP` | a b → b a | Swap top two |
| `OVER` | a b → a b a | Copy second to top |
| `ROT` | a b c → b c a | Rotate third to top |
| `JZ addr` | a → | Jump if top == 0 (pops) |
| `JNZ addr` | a → | Jump if top ≠ 0 (pops) |
| `NOP` | — | No operation |
| `HALT` | — | Stop execution |

## Assembly Format

One instruction per line. `#` and `;` start comments. Case-insensitive.

```
PUSH 10    # push 10
PUSH 3     # push 3
SUB        # 10 - 3 = 7
HALT
```

Jump targets are instruction addresses (0-indexed line numbers after stripping comments/blanks).

## How It Works

The executor is a Mojo binary (~18M steps/sec). Under the hood:

1. **Program memory**: Each instruction becomes a 6-dim embedding with parabolic keys `k = (2j, -j²)` where `j` is the address
2. **Instruction fetch**: Query `q = (ip, 1)` → dot product with all program keys → argmax selects the instruction at IP (the parabolic score `-(j-ip)² + ip²` peaks exactly at `j=ip`)
3. **Stack memory**: Same mechanism — stack entries get parabolic keys by address, with epsilon recency bias for overwrites
4. **FF dispatch**: Opcode one-hot gating selects the right arithmetic per instruction

This is the same attention mechanism transformers use internally. The weights are analytically compiled, not trained.

## Build

First invocation per session builds the Mojo binary (~30s). Subsequent calls are instant. Requires the `coding-mojo` skill for Mojo installation.

## Writing Programs

Address labels are manual — count your instruction lines (after removing comments/blanks) to get jump targets. The built-in generators (`fib`, `multiply`, `power2`, `sum_n`) handle this automatically.

For custom programs, `run()` accepts assembly text and returns `(result_int, output_string)`.
