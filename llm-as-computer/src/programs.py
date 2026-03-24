"""Program generators for the compiled transformer stack machine.

Consolidated from phase4, phase13, phase14. Contains all test program
generators and the ALL_TESTS regression list.
"""

import math

from isa_lite import (
    Instruction,
    OP_PUSH, OP_POP, OP_ADD, OP_DUP, OP_HALT,
    OP_SUB, OP_JZ, OP_JNZ, OP_NOP,
    OP_SWAP, OP_OVER, OP_ROT,
    OP_MUL, OP_DIV_S, OP_DIV_U, OP_REM_S, OP_REM_U,
    OP_EQZ, OP_EQ, OP_NE,
    OP_LT_S, OP_LT_U, OP_GT_S, OP_GT_U,
    OP_LE_S, OP_LE_U, OP_GE_S, OP_GE_U,
    OP_AND, OP_OR, OP_XOR,
    OP_SHL, OP_SHR_S, OP_SHR_U, OP_ROTL, OP_ROTR,
    OP_CLZ, OP_CTZ, OP_POPCNT, OP_ABS, OP_NEG, OP_SELECT,
    _trunc_div, _trunc_rem, _to_i32, MASK32,
    _shr_u, _shr_s, _rotl32, _rotr32,
    _clz32, _ctz32, _popcnt32,
    program,
)


# ─── Phase 4 Test Programs ──────────────────────────────────────

def test_basic():
    """PUSH 3, PUSH 5, ADD, HALT -> top should be 8."""
    prog = program(("PUSH", 3), ("PUSH", 5), ("ADD",), ("HALT",))
    return prog, 8

def test_push_halt():
    """PUSH 42, HALT -> top should be 42."""
    prog = program(("PUSH", 42), ("HALT",))
    return prog, 42

def test_push_pop():
    """PUSH 10, PUSH 20, POP, HALT -> top should be 10."""
    prog = program(("PUSH", 10), ("PUSH", 20), ("POP",), ("HALT",))
    return prog, 10

def test_dup_add():
    """PUSH 7, DUP, ADD, HALT -> top should be 14."""
    prog = program(("PUSH", 7), ("DUP",), ("ADD",), ("HALT",))
    return prog, 14

def test_multi_add():
    """PUSH 1, PUSH 2, PUSH 3, ADD, ADD, HALT -> top should be 6."""
    prog = program(("PUSH", 1), ("PUSH", 2), ("PUSH", 3), ("ADD",), ("ADD",), ("HALT",))
    return prog, 6

def test_stack_depth():
    """PUSH 1, PUSH 2, PUSH 3, POP, POP, HALT -> top should be 1."""
    prog = program(("PUSH", 1), ("PUSH", 2), ("PUSH", 3), ("POP",), ("POP",), ("HALT",))
    return prog, 1

def test_overwrite():
    """PUSH 5, POP, PUSH 9, HALT -> top should be 9."""
    prog = program(("PUSH", 5), ("POP",), ("PUSH", 9), ("HALT",))
    return prog, 9

def test_complex():
    """PUSH 10, PUSH 20, PUSH 30, ADD, DUP, ADD, HALT -> 100."""
    prog = program(("PUSH", 10), ("PUSH", 20), ("PUSH", 30),
                   ("ADD",), ("DUP",), ("ADD",), ("HALT",))
    return prog, 100

def test_many_pushes():
    """Push values 1..10, then ADD them all."""
    instrs = [("PUSH", i) for i in range(1, 11)]
    instrs += [("ADD",)] * 9
    instrs.append(("HALT",))
    prog = program(*instrs)
    return prog, 55

def test_alternating():
    """PUSH 1, PUSH 2, ADD, PUSH 3, ADD, PUSH 4, ADD, HALT -> 10."""
    prog = program(("PUSH", 1), ("PUSH", 2), ("ADD",),
                   ("PUSH", 3), ("ADD",),
                   ("PUSH", 4), ("ADD",), ("HALT",))
    return prog, 10


ALL_TESTS = [
    ("basic_add",      test_basic),
    ("push_halt",      test_push_halt),
    ("push_pop",       test_push_pop),
    ("dup_add",        test_dup_add),
    ("multi_add",      test_multi_add),
    ("stack_depth",    test_stack_depth),
    ("overwrite",      test_overwrite),
    ("complex",        test_complex),
    ("many_pushes",    test_many_pushes),
    ("alternating",    test_alternating),
]


# ─── Phase 13 Algorithm Generators ──────────────────────────────

def fib(n):
    """Reference Fibonacci."""
    if n <= 0: return 0
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


def make_fibonacci(n):
    """Generate a program that computes fib(n).

    Algorithm: iterative [counter, a, b] -> SWAP, OVER, ADD -> [counter, b, a+b]
    with ROT to cycle the counter.
    """
    if n == 0:
        return [Instruction(OP_PUSH, 0), Instruction(OP_HALT)], 0
    if n == 1:
        return [Instruction(OP_PUSH, 1), Instruction(OP_HALT)], 1

    prog = [
        Instruction(OP_PUSH, 0),      # 0: a = fib(0)
        Instruction(OP_PUSH, 1),      # 1: b = fib(1)
        Instruction(OP_PUSH, n - 1),  # 2: counter = n-1
        Instruction(OP_ROT),          # 3: [1, n-1, 0]
        Instruction(OP_ROT),          # 4: [n-1, 0, 1] = [counter, a, b]
        # ── Loop body (addr 5) ──
        Instruction(OP_SWAP),         # 5: [counter, b, a]
        Instruction(OP_OVER),         # 6: [counter, b, a, b]
        Instruction(OP_ADD),          # 7: [counter, b, a+b]
        Instruction(OP_ROT),          # 8: [b, a+b, counter]
        Instruction(OP_PUSH, 1),      # 9
        Instruction(OP_SUB),          # 10: [b, a+b, counter-1]
        Instruction(OP_DUP),          # 11: [..., counter-1, counter-1]
        Instruction(OP_JNZ, 15),      # 12: if counter-1 != 0 -> continue
        Instruction(OP_POP),          # 13: drop counter=0
        Instruction(OP_HALT),         # 14: top = fib(n)
        # ── Continue loop (addr 15) ──
        Instruction(OP_ROT),          # 15: [new_b, counter-1, new_a]
        Instruction(OP_ROT),          # 16: [counter-1, new_a, new_b]
        Instruction(OP_PUSH, 1),      # 17
        Instruction(OP_JNZ, 5),       # 18: always taken
    ]
    return prog, fib(n)


def make_power_of_2(n):
    """Generate a program that computes 2^n via repeated doubling."""
    if n == 0:
        return [Instruction(OP_PUSH, 1), Instruction(OP_HALT)], 1

    prog = [
        Instruction(OP_PUSH, 1),      # 0: value = 1
        Instruction(OP_PUSH, n),      # 1: counter = n
        # ── Loop (addr 2) ──
        Instruction(OP_DUP),          # 2
        Instruction(OP_JZ, 12),       # 3: if counter == 0 -> done
        Instruction(OP_PUSH, 1),      # 4
        Instruction(OP_SUB),          # 5
        Instruction(OP_SWAP),         # 6
        Instruction(OP_DUP),          # 7
        Instruction(OP_ADD),          # 8
        Instruction(OP_SWAP),         # 9
        Instruction(OP_PUSH, 1),      # 10
        Instruction(OP_JNZ, 2),       # 11
        # ── Done ──
        Instruction(OP_POP),          # 12
        Instruction(OP_HALT),         # 13
    ]
    prog[3] = Instruction(OP_JZ, 12)
    return prog, 2 ** n


def make_sum_1_to_n(n):
    """Generate a program that computes 1 + 2 + ... + n."""
    if n == 0:
        return [Instruction(OP_PUSH, 0), Instruction(OP_HALT)], 0

    prog = [
        Instruction(OP_PUSH, 0),      # 0: acc = 0
        Instruction(OP_PUSH, n),      # 1: counter = n
        # ── Loop (addr 2) ──
        Instruction(OP_DUP),          # 2
        Instruction(OP_JZ, 12),       # 3: if counter == 0 -> done
        Instruction(OP_DUP),          # 4
        Instruction(OP_ROT),          # 5
        Instruction(OP_ADD),          # 6
        Instruction(OP_SWAP),         # 7
        Instruction(OP_PUSH, 1),      # 8
        Instruction(OP_SUB),          # 9
        Instruction(OP_PUSH, 1),      # 10
        Instruction(OP_JNZ, 2),       # 11
        # ── Done (addr 12) ──
        Instruction(OP_POP),          # 12
        Instruction(OP_HALT),         # 13
    ]
    return prog, n * (n + 1) // 2


def make_multiply(a, b):
    """Generate a program that computes a * b via repeated addition."""
    if b == 0 or a == 0:
        return [Instruction(OP_PUSH, 0), Instruction(OP_HALT)], 0

    prog = [
        Instruction(OP_PUSH, a),      # 0: a
        Instruction(OP_PUSH, 0),      # 1: result = 0
        Instruction(OP_PUSH, b),      # 2: counter = b
        # ── Loop (addr 3) ──
        Instruction(OP_DUP),          # 3
        Instruction(OP_JZ, 14),       # 4: if counter == 0 -> done
        Instruction(OP_PUSH, 1),      # 5
        Instruction(OP_SUB),          # 6
        Instruction(OP_ROT),          # 7
        Instruction(OP_ROT),          # 8
        Instruction(OP_OVER),         # 9
        Instruction(OP_ADD),          # 10
        Instruction(OP_ROT),          # 11
        Instruction(OP_PUSH, 1),      # 12
        Instruction(OP_JNZ, 3),       # 13
        # ── Done (addr 14) ──
        Instruction(OP_POP),          # 14
        Instruction(OP_SWAP),         # 15
        Instruction(OP_POP),          # 16
        Instruction(OP_HALT),         # 17
    ]
    return prog, a * b


def make_is_even(n):
    """Generate a program that returns 1 if n is even, 0 if odd."""
    prog = [
        Instruction(OP_PUSH, n),      # 0: n
        # ── Loop (addr 1) ──
        Instruction(OP_DUP),          # 1
        Instruction(OP_JZ, 11),       # 2: if n == 0 -> even
        Instruction(OP_PUSH, 1),      # 3
        Instruction(OP_SUB),          # 4
        Instruction(OP_DUP),          # 5
        Instruction(OP_JZ, 14),       # 6: if n-1 == 0 -> odd
        Instruction(OP_PUSH, 1),      # 7
        Instruction(OP_SUB),          # 8
        Instruction(OP_PUSH, 1),      # 9
        Instruction(OP_JNZ, 1),       # 10
        # ── Even (addr 11) ──
        Instruction(OP_POP),          # 11
        Instruction(OP_PUSH, 1),      # 12
        Instruction(OP_HALT),         # 13
        # ── Odd (addr 14) ──
        Instruction(OP_POP),          # 14
        Instruction(OP_PUSH, 0),      # 15
        Instruction(OP_HALT),         # 16
    ]
    return prog, 1 if n % 2 == 0 else 0


# ─── Phase 14 Native-Op Algorithm Generators ─────────────────────

def make_native_multiply(a, b):
    """Compute a*b using native MUL. 4 instructions."""
    return [
        Instruction(OP_PUSH, a),
        Instruction(OP_PUSH, b),
        Instruction(OP_MUL),
        Instruction(OP_HALT),
    ], a * b


def make_native_divmod(a, b):
    """Compute b/a and b%a. Returns (program, expected_quotient)."""
    if a == 0:
        return [
            Instruction(OP_PUSH, b),
            Instruction(OP_PUSH, a),
            Instruction(OP_DIV_S),
            Instruction(OP_HALT),
        ], None
    return [
        Instruction(OP_PUSH, b),
        Instruction(OP_PUSH, a),
        Instruction(OP_DIV_S),
        Instruction(OP_HALT),
    ], _trunc_div(b, a)


def make_native_remainder(a, b):
    """Compute b%a using REM_S. Returns (program, expected_remainder)."""
    if a == 0:
        return [
            Instruction(OP_PUSH, b),
            Instruction(OP_PUSH, a),
            Instruction(OP_REM_S),
            Instruction(OP_HALT),
        ], None
    return [
        Instruction(OP_PUSH, b),
        Instruction(OP_PUSH, a),
        Instruction(OP_REM_S),
        Instruction(OP_HALT),
    ], _trunc_rem(b, a)


def make_native_is_even(n):
    """Test parity using native REM_S + JZ."""
    prog = [
        Instruction(OP_PUSH, n),      # 0: n
        Instruction(OP_PUSH, 2),      # 1: 2
        Instruction(OP_REM_S),        # 2: n % 2
        Instruction(OP_JZ, 6),        # 3: if remainder == 0 -> even
        Instruction(OP_PUSH, 0),      # 4
        Instruction(OP_HALT),         # 5
        Instruction(OP_PUSH, 1),      # 6
        Instruction(OP_HALT),         # 7
    ]
    return prog, 1 if n % 2 == 0 else 0


def make_factorial(n):
    """Compute n! using native MUL."""
    if n <= 1:
        return [Instruction(OP_PUSH, 1), Instruction(OP_HALT)], 1

    prog = [
        Instruction(OP_PUSH, 1),      # 0: result = 1
        Instruction(OP_PUSH, n),      # 1: counter = n
        # ── Loop (addr 2) ──
        Instruction(OP_DUP),          # 2
        Instruction(OP_JZ, 12),       # 3: if counter == 0 -> done
        Instruction(OP_DUP),          # 4
        Instruction(OP_ROT),          # 5
        Instruction(OP_MUL),          # 6
        Instruction(OP_SWAP),         # 7
        Instruction(OP_PUSH, 1),      # 8
        Instruction(OP_SUB),          # 9
        Instruction(OP_PUSH, 1),      # 10
        Instruction(OP_JNZ, 2),       # 11
        # ── Done (addr 12) ──
        Instruction(OP_POP),          # 12
        Instruction(OP_HALT),         # 13
    ]
    expected = 1
    for i in range(2, n + 1):
        expected *= i
    return prog, expected


def make_gcd(a, b):
    """Compute GCD(a, b) via Euclidean algorithm using native REM_S."""
    if a == 0 and b == 0:
        return [Instruction(OP_PUSH, 0), Instruction(OP_HALT)], 0

    prog = [
        Instruction(OP_PUSH, a),      # 0: a
        Instruction(OP_PUSH, b),      # 1: b
        # ── Loop (addr 2) ──
        Instruction(OP_DUP),          # 2
        Instruction(OP_JZ, 10),       # 3: if b == 0 -> done
        Instruction(OP_SWAP),         # 4
        Instruction(OP_OVER),         # 5
        Instruction(OP_REM_S),        # 6
        Instruction(OP_PUSH, 1),      # 7
        Instruction(OP_JNZ, 2),       # 8
        Instruction(OP_NOP),          # 9: padding
        # ── Done (addr 10) ──
        Instruction(OP_POP),          # 10
        Instruction(OP_HALT),         # 11
    ]
    return prog, math.gcd(a, b)


# ─── Comparison Program Generators ──────────────────────────────

def make_compare_eqz(a):
    """Test a == 0 using EQZ."""
    return [
        Instruction(OP_PUSH, a),
        Instruction(OP_EQZ),
        Instruction(OP_HALT),
    ], 1 if a == 0 else 0


def make_compare_binary(op, a, b):
    """Generic binary comparison: PUSH a, PUSH b, OP, HALT."""
    CMP_SEMANTICS = {
        OP_EQ:   lambda va, vb: vb == va,
        OP_NE:   lambda va, vb: vb != va,
        OP_LT_S: lambda va, vb: vb < va,
        OP_LT_U: lambda va, vb: vb < va,
        OP_GT_S: lambda va, vb: vb > va,
        OP_GT_U: lambda va, vb: vb > va,
        OP_LE_S: lambda va, vb: vb <= va,
        OP_LE_U: lambda va, vb: vb <= va,
        OP_GE_S: lambda va, vb: vb >= va,
        OP_GE_U: lambda va, vb: vb >= va,
    }
    expected = 1 if CMP_SEMANTICS[op](b, a) else 0
    return [
        Instruction(OP_PUSH, a),
        Instruction(OP_PUSH, b),
        Instruction(op),
        Instruction(OP_HALT),
    ], expected


def make_native_max(a, b):
    """Compute max(a, b) using GT_S + JZ."""
    expected = max(a, b)
    prog = [
        Instruction(OP_PUSH, a),      # 0
        Instruction(OP_PUSH, b),      # 1
        Instruction(OP_OVER),         # 2
        Instruction(OP_OVER),         # 3
        Instruction(OP_GT_S),         # 4
        Instruction(OP_JZ, 9),        # 5
        Instruction(OP_POP),          # 6
        Instruction(OP_HALT),         # 7
        Instruction(OP_NOP),          # 8
        Instruction(OP_SWAP),         # 9
        Instruction(OP_POP),          # 10
        Instruction(OP_HALT),         # 11
    ]
    return prog, expected


def make_native_abs(n):
    """Compute abs(n) using LT_S comparison + conditional negate."""
    expected = abs(n)
    prog = [
        Instruction(OP_PUSH, n),      # 0
        Instruction(OP_DUP),          # 1
        Instruction(OP_PUSH, 0),      # 2
        Instruction(OP_LT_S),         # 3
        Instruction(OP_JZ, 9),        # 4
        Instruction(OP_PUSH, 0),      # 5
        Instruction(OP_SWAP),         # 6
        Instruction(OP_SUB),          # 7
        Instruction(OP_HALT),         # 8
        Instruction(OP_HALT),         # 9
    ]
    return prog, expected


def make_native_clamp(val, lo, hi):
    """Clamp val to [lo, hi] using comparisons."""
    expected = max(lo, min(val, hi))
    prog = [
        Instruction(OP_PUSH, val),    # 0
        Instruction(OP_DUP),          # 1
        Instruction(OP_PUSH, lo),     # 2
        Instruction(OP_LT_S),         # 3
        Instruction(OP_JZ, 8),        # 4
        Instruction(OP_POP),          # 5
        Instruction(OP_PUSH, lo),     # 6
        Instruction(OP_HALT),         # 7
        Instruction(OP_DUP),          # 8
        Instruction(OP_PUSH, hi),     # 9
        Instruction(OP_GT_S),         # 10
        Instruction(OP_JZ, 15),       # 11
        Instruction(OP_POP),          # 12
        Instruction(OP_PUSH, hi),     # 13
        Instruction(OP_HALT),         # 14
        Instruction(OP_HALT),         # 15
    ]
    return prog, expected


# ─── Bitwise Program Generators ─────────────────────────────────

def make_bitwise_binary(op, a, b):
    """Generic bitwise binary: PUSH a, PUSH b, OP, HALT."""
    va, vb = b, a
    BITWISE_SEMANTICS = {
        OP_AND:   lambda va, vb: _to_i32(va) & _to_i32(vb),
        OP_OR:    lambda va, vb: _to_i32(va) | _to_i32(vb),
        OP_XOR:   lambda va, vb: _to_i32(va) ^ _to_i32(vb),
        OP_SHL:   lambda va, vb: (_to_i32(vb) << (int(va) & 31)) & MASK32,
        OP_SHR_S: lambda va, vb: _shr_s(vb, va),
        OP_SHR_U: lambda va, vb: _shr_u(vb, va),
        OP_ROTL:  lambda va, vb: _rotl32(vb, va),
        OP_ROTR:  lambda va, vb: _rotr32(vb, va),
    }
    expected = BITWISE_SEMANTICS[op](va, vb)
    return [
        Instruction(OP_PUSH, a),
        Instruction(OP_PUSH, b),
        Instruction(op),
        Instruction(OP_HALT),
    ], expected


def make_popcount_loop(n):
    """Count set bits of n using AND + SHR_U loop."""
    expected = bin(n & MASK32).count('1')
    prog = [
        Instruction(OP_PUSH, 0),      # 0: count = 0
        Instruction(OP_PUSH, n),      # 1: n
        # ── Loop (addr 2) ──
        Instruction(OP_DUP),          # 2
        Instruction(OP_JZ, 14),       # 3: if n == 0 -> done
        Instruction(OP_DUP),          # 4
        Instruction(OP_PUSH, 1),      # 5
        Instruction(OP_AND),          # 6
        Instruction(OP_ROT),          # 7
        Instruction(OP_ADD),          # 8
        Instruction(OP_SWAP),         # 9
        Instruction(OP_PUSH, 1),      # 10
        Instruction(OP_SHR_U),        # 11
        Instruction(OP_PUSH, 1),      # 12
        Instruction(OP_JNZ, 2),       # 13
        # ── Done (addr 14) ──
        Instruction(OP_POP),          # 14
        Instruction(OP_HALT),         # 15
    ]
    return prog, expected


def make_bit_extract(n, bit_pos):
    """Extract bit at position bit_pos from n. Result: 0 or 1."""
    expected = (_to_i32(n) >> (bit_pos & 31)) & 1
    prog = [
        Instruction(OP_PUSH, n),
        Instruction(OP_PUSH, bit_pos),
        Instruction(OP_SHR_U),
        Instruction(OP_PUSH, 1),
        Instruction(OP_AND),
        Instruction(OP_HALT),
    ]
    return prog, expected


# ─── Chunk 4: Unary + Parametric Program Generators ─────────────

def make_native_clz(n):
    """Count leading zeros of n using native CLZ."""
    return [
        Instruction(OP_PUSH, n),
        Instruction(OP_CLZ),
        Instruction(OP_HALT),
    ], _clz32(n)

def make_native_ctz(n):
    """Count trailing zeros of n using native CTZ."""
    return [
        Instruction(OP_PUSH, n),
        Instruction(OP_CTZ),
        Instruction(OP_HALT),
    ], _ctz32(n)

def make_native_popcnt(n):
    """Population count of n using native POPCNT."""
    return [
        Instruction(OP_PUSH, n),
        Instruction(OP_POPCNT),
        Instruction(OP_HALT),
    ], _popcnt32(n)

def make_native_abs_unary(n):
    """Absolute value using native ABS. 3 instructions."""
    return [
        Instruction(OP_PUSH, n),
        Instruction(OP_ABS),
        Instruction(OP_HALT),
    ], abs(int(n))

def make_native_neg(n):
    """Negate n using native NEG. Result is i32-masked (WASM overflow semantics)."""
    return [
        Instruction(OP_PUSH, n),
        Instruction(OP_NEG),
        Instruction(OP_HALT),
    ], (-int(n)) & 0xFFFFFFFF

def make_select(a, b, c):
    """SELECT: push a, b, c; SELECT pops all three -> (c!=0 ? a : b)."""
    expected = a if c != 0 else b
    return [
        Instruction(OP_PUSH, a),
        Instruction(OP_PUSH, b),
        Instruction(OP_PUSH, c),
        Instruction(OP_SELECT),
        Instruction(OP_HALT),
    ], expected

def make_select_max(a, b):
    """Max of two numbers using GT_S + SELECT."""
    expected = max(a, b)
    prog = [
        Instruction(OP_PUSH, a),   # 0
        Instruction(OP_PUSH, b),   # 1
        Instruction(OP_PUSH, a),   # 2
        Instruction(OP_PUSH, b),   # 3
        Instruction(OP_GT_S),      # 4
        Instruction(OP_SELECT),    # 5
        Instruction(OP_HALT),      # 6
    ]
    return prog, expected

def make_log2_floor(n):
    """Floor of log2(n) using CLZ: 31 - CLZ(n)."""
    if n <= 0:
        return [Instruction(OP_PUSH, 0), Instruction(OP_HALT)], 0
    expected = 31 - _clz32(n)
    prog = [
        Instruction(OP_PUSH, n),
        Instruction(OP_CLZ),
        Instruction(OP_PUSH, 31),
        Instruction(OP_SWAP),
        Instruction(OP_SUB),
        Instruction(OP_HALT),
    ]
    return prog, expected

def make_is_power_of_2(n):
    """Check if n is a power of 2 using POPCNT."""
    expected = 1 if (n > 0 and _popcnt32(n) == 1) else 0
    prog = [
        Instruction(OP_PUSH, n),
        Instruction(OP_POPCNT),
        Instruction(OP_PUSH, 1),
        Instruction(OP_EQ),
        Instruction(OP_HALT),
    ]
    return prog, expected
