"""Program specialization via partial evaluation.

Bakes the compiled stack machine's program table into FFN-style coefficient
tables, so the fetched opcode/arg at each cursor position is computed from
a fixed set of step-function neurons rather than from attention over a
program prefix.

For a program of N instructions, specialization emits:

  - 2N ReGLU step-function neurons realising  1[cursor >= i]  for i in 0..N-1
    (each indicator needs a gate + up half-neuron under the ReGLU product
    formulation).
  - Per fetched field f, a coefficient vector  c = [c0, c1-c0, ..., c_{N-1}-c_{N-2}]
    such that  f(cursor) = sum_{i=0..N-1} c[i] * 1[cursor >= i].

The sum telescopes to f(prog[cursor]) whenever 0 <= cursor < N, so the
specialized representation is bit-exact with direct indexing into the
program table.

Based on the partial-evaluation pass described in
https://www.percepta.ai/blog/constructing-llm-computer (2026-03-25).

In this repo the "FFN" is ordinary arithmetic -- we are not training weights.
The demonstration is that at deployment time the prompt shrinks from
(program || input) to (input), because the fetched fields are now a function
of the cursor alone.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from isa_lite import Instruction


# Fields baked into FFN coefficients. Matches the (op, arg) shape used by
# every other layer of the executor.
FIELDS: Tuple[str, ...] = ("op", "arg")


@dataclass
class SpecializedProgram:
    """A program represented as FFN coefficient tables instead of a prefix.

    Attributes:
        n:
            Number of instructions (and number of step-function neurons).
        coefficients:
            Per field, a list of length n where coefficients[f][0] = c0 and
            coefficients[f][i] = c_i - c_{i-1} for i >= 1. The fetched value
            at cursor t is sum(coefficients[f][i] * 1[t >= i] for i in 0..n-1).
        originals:
            The input instruction list. Retained only so the verification
            helpers can assert specialized-vs-direct parity; fetch() never
            consults it.
    """

    n: int
    coefficients: Dict[str, List[int]]
    originals: List[Instruction] = field(default_factory=list)

    def step_neurons(self, cursor: int) -> List[int]:
        """Return the n step-function activations 1[cursor >= i] for i in 0..n-1."""
        return [1 if cursor >= i else 0 for i in range(self.n)]

    def fetch(self, cursor: int) -> Tuple[int, int]:
        """Reconstruct (op, arg) at `cursor` using only the coefficient tables.

        Implements the Percepta expansion
            f(cursor) = c0 + sum_{i=1..n-1} (c_i - c_{i-1}) * 1[cursor >= i]
        which telescopes to c_cursor for 0 <= cursor < n. Out-of-range cursors
        saturate at c_{n-1}, matching WASM's trap-on-overrun semantics when
        the executor has already halted.
        """
        if cursor < 0:
            return (0, 0)
        ind = self.step_neurons(cursor)
        op = sum(c * s for c, s in zip(self.coefficients["op"], ind))
        arg = sum(c * s for c, s in zip(self.coefficients["arg"], ind))
        return int(op), int(arg)

    def ffn_rows(self) -> List[Tuple[str, int]]:
        """Describe the 2N ReGLU neurons emitted for this program.

        Each instruction i contributes a (gate, up) pair; their product
        realises 1[cursor >= i] (the gate saturates at 1, the up saturates
        at 1, ReGLU multiplies them).
        """
        rows: List[Tuple[str, int]] = []
        for i in range(self.n):
            rows.append(("gate", i))
            rows.append(("up", i))
        return rows

    def token_savings(self, input_tokens: int = 0) -> Dict[str, int]:
        """Compare prompt sizes: universal (program || input) vs specialized (input)."""
        program_tokens = 2 * self.n  # op + arg per instruction
        return {
            "universal_prompt_tokens": program_tokens + input_tokens,
            "specialized_prompt_tokens": input_tokens,
            "program_tokens_saved": program_tokens,
        }


def specialize(prog: List[Instruction]) -> SpecializedProgram:
    """Partial-evaluate a program into FFN coefficient tables.

    For each field f, computes:
        c[0] = f(prog[0])
        c[i] = f(prog[i]) - f(prog[i-1])    for i > 0
    so that sum_{i=0..cursor} c[i] = f(prog[cursor]).
    """
    # Unpack (prog, expected) tuples returned by programs.make_*
    if isinstance(prog, tuple) and len(prog) == 2 and isinstance(prog[0], list):
        prog = prog[0]

    n = len(prog)
    if n == 0:
        raise ValueError("Cannot specialize an empty program.")

    coefficients: Dict[str, List[int]] = {}
    for name in FIELDS:
        seq = [int(getattr(instr, name)) for instr in prog]
        row = [seq[0]]
        for i in range(1, n):
            row.append(seq[i] - seq[i - 1])
        coefficients[name] = row

    return SpecializedProgram(n=n, coefficients=coefficients, originals=list(prog))


def fetch_fn_from_program(prog: List[Instruction]) -> Callable[[int], Tuple[int, int]]:
    """Universal-interpreter fetch: direct indexing into the program prefix."""

    def fetch(ip: int) -> Tuple[int, int]:
        if ip < 0 or ip >= len(prog):
            return (0, 0)
        instr = prog[ip]
        return int(instr.op), int(instr.arg)

    return fetch


def verify_fetch_parity(prog: List[Instruction]) -> bool:
    """Assert specialized.fetch(i) == (prog[i].op, prog[i].arg) for every i."""
    sp = specialize(prog)
    direct = fetch_fn_from_program(prog)
    for i in range(len(prog)):
        if sp.fetch(i) != direct(i):
            raise AssertionError(
                f"specialization mismatch at cursor={i}: "
                f"specialized={sp.fetch(i)} direct={direct(i)}"
            )
    return True
