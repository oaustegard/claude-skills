"""Mojo port of NumPyExecutor: full 55-opcode stack machine.

Stage 1 (issue #40): Naive structural translation.
Stage 2 (issue #43): Performance optimizations:
  1. @always_inline on all hot functions (mem_read/write, math helpers)
  2. Pre-allocated List capacity based on program size
  3. SoA (Struct-of-Arrays) memory layout for cache-friendly scans
  4. Write compaction: periodic dedup keeps only latest write per address
  5. SIMD[float64, 4] dot-product in parabolic argmax scan
  6. Direct-mapped O(1) fast path for addresses < 256

I/O contract (normal mode):
  Input:  program as space-separated "op arg op arg ..." via argv or stdin
  Output: one "op arg sp top" line per step, then "RESULT: <top>"

Timing mode (--repeat N):
  Runs the program N times silently, reports median execution time.
  Output: "TIMING_NS: <median_ns>"  (no trace lines)
  Used by the benchmark harness to measure µs/step without subprocess overhead.
"""

from std.sys import argv
from std.time import perf_counter_ns

# ─── Opcode constants ─────────────────────────────────────────────

comptime OP_PUSH = 1
comptime OP_POP = 2
comptime OP_ADD = 3
comptime OP_DUP = 4
comptime OP_HALT = 5
comptime OP_SUB = 6
comptime OP_JZ = 7
comptime OP_JNZ = 8
comptime OP_NOP = 9
comptime OP_SWAP = 10
comptime OP_OVER = 11
comptime OP_ROT = 12
comptime OP_MUL = 13
comptime OP_DIV_S = 14
comptime OP_DIV_U = 15
comptime OP_REM_S = 16
comptime OP_REM_U = 17
comptime OP_EQZ = 18
comptime OP_EQ = 19
comptime OP_NE = 20
comptime OP_LT_S = 21
comptime OP_LT_U = 22
comptime OP_GT_S = 23
comptime OP_GT_U = 24
comptime OP_LE_S = 25
comptime OP_LE_U = 26
comptime OP_GE_S = 27
comptime OP_GE_U = 28
comptime OP_AND = 29
comptime OP_OR = 30
comptime OP_XOR = 31
comptime OP_SHL = 32
comptime OP_SHR_S = 33
comptime OP_SHR_U = 34
comptime OP_ROTL = 35
comptime OP_ROTR = 36
comptime OP_CLZ = 37
comptime OP_CTZ = 38
comptime OP_POPCNT = 39
comptime OP_ABS = 40
comptime OP_NEG = 41
comptime OP_SELECT = 42
comptime OP_LOCAL_GET = 43
comptime OP_LOCAL_SET = 44
comptime OP_LOCAL_TEE = 45
comptime OP_I32_LOAD = 46
comptime OP_I32_STORE = 47
comptime OP_I32_LOAD8_U = 48
comptime OP_I32_LOAD8_S = 49
comptime OP_I32_LOAD16_U = 50
comptime OP_I32_LOAD16_S = 51
comptime OP_I32_STORE8 = 52
comptime OP_I32_STORE16 = 53
comptime OP_CALL = 54
comptime OP_RETURN = 55
comptime OP_TRAP = 99

comptime MASK32 = 0xFFFFFFFF
comptime EPS    = Float64(1e-10)
comptime COMPACT_INTERVAL = 128  # Compact every N writes
comptime DIRECT_LIMIT = 256      # Direct-map fast path for addr < this


# ─── Data structures ──────────────────────────────────────────────

# SoA (Struct-of-Arrays) memory space for parabolic key-value storage.
# Separates k0/k1 from val for better cache utilization during scans.
struct MemSpace:
    var k0s: List[Float64]
    var k1s: List[Float64]
    var vals: List[Int]
    var write_count: Int
    # Direct-mapped fast path: O(1) read for addr < DIRECT_LIMIT
    var direct: List[Int]       # direct[addr] = latest value
    var direct_valid: List[Bool] # whether direct[addr] has been written

    fn __init__(out self, capacity: Int = 0):
        self.k0s = List[Float64]()
        self.k1s = List[Float64]()
        self.vals = List[Int]()
        self.write_count = 0
        self.direct = List[Int]()
        self.direct_valid = List[Bool]()
        # Pre-fill direct-map slots
        for _ in range(DIRECT_LIMIT):
            self.direct.append(0)
            self.direct_valid.append(False)
        if capacity > 0:
            self.k0s.reserve(capacity)
            self.k1s.reserve(capacity)
            self.vals.reserve(capacity)


# Call-stack frame
@fieldwise_init
struct CallFrame(Copyable, Movable):
    var ret_addr: Int
    var saved_sp: Int
    var saved_locals_base: Int


# ─── Parabolic memory primitives ─────────────────────────────────

fn compact(mut ms: MemSpace):
    """Remove stale entries: keep only latest write per address.

    Walk backward (latest first); keep first occurrence of each address.
    Re-encode parabolic keys with fresh write_count for correct ordering.
    """
    var n = len(ms.k0s)
    if n < COMPACT_INTERVAL:
        return

    # Collect unique (addr, val) pairs, latest first
    var seen_addrs = List[Int]()  # addresses we've already seen
    var kept_addrs = List[Int]()  # addresses to keep (in reverse order)
    var kept_vals  = List[Int]()  # corresponding values

    for ri in range(n):
        var i = n - 1 - ri  # walk backward
        var addr = Int(ms.k0s[i] / 2.0 + 0.5)
        # Check if already seen
        var found = False
        for j in range(len(seen_addrs)):
            if seen_addrs[j] == addr:
                found = True
                break
        if not found:
            seen_addrs.append(addr)
            kept_addrs.append(addr)
            kept_vals.append(ms.vals[i])

    # Rebuild SoA arrays with fresh sequential write_counts
    var new_n = len(kept_addrs)
    ms.k0s.clear()
    ms.k1s.clear()
    ms.vals.clear()
    ms.k0s.reserve(new_n + COMPACT_INTERVAL)
    ms.k1s.reserve(new_n + COMPACT_INTERVAL)
    ms.vals.reserve(new_n + COMPACT_INTERVAL)

    # Reverse to restore chronological order (oldest kept first)
    var new_wc = 0
    for ri in range(new_n):
        var i = new_n - 1 - ri
        var a = Float64(kept_addrs[i])
        ms.k0s.append(2.0 * a)
        ms.k1s.append(-(a * a) + EPS * Float64(new_wc))
        ms.vals.append(kept_vals[i])
        new_wc += 1
    ms.write_count = new_wc


@always_inline
fn mem_write(mut ms: MemSpace, addr: Int, val: Int):
    var a = Float64(addr)
    ms.k0s.append(2.0 * a)
    ms.k1s.append(-(a * a) + EPS * Float64(ms.write_count))
    ms.vals.append(val)
    ms.write_count += 1
    # Update direct-map fast path
    if addr >= 0 and addr < DIRECT_LIMIT:
        ms.direct[addr] = val
        ms.direct_valid[addr] = True


@always_inline
fn mem_write_compact(mut ms: MemSpace, addr: Int, val: Int):
    """Write + trigger periodic compaction. Use for stack/heap, NOT locals."""
    mem_write(ms, addr, val)
    if len(ms.k0s) >= COMPACT_INTERVAL and len(ms.k0s) % COMPACT_INTERVAL == 0:
        compact(ms)


comptime SIMD_W = 4  # SIMD width for dot-product scan

@always_inline
fn mem_read(ms: MemSpace, addr: Int) -> Int:
    # Direct-map fast path: O(1) for small addresses
    if addr >= 0 and addr < DIRECT_LIMIT and ms.direct_valid[addr]:
        return ms.direct[addr]
    var n = len(ms.k0s)
    if n == 0:
        return 0
    var q0 = Float64(addr)
    var q1 = Float64(1.0)
    var best_idx = 0
    var best_score = ms.k0s[0] * q0 + ms.k1s[0] * q1

    # SIMD-accelerated argmax scan over k0/k1 arrays
    var q0_vec = SIMD[DType.float64, SIMD_W](q0)
    var q1_vec = SIMD[DType.float64, SIMD_W](q1)
    var k0_ptr = ms.k0s.unsafe_ptr()
    var k1_ptr = ms.k1s.unsafe_ptr()

    var i = 1
    while i + SIMD_W <= n:
        var scores = k0_ptr.load[width=SIMD_W](i) * q0_vec + k1_ptr.load[width=SIMD_W](i) * q1_vec
        for j in range(SIMD_W):
            if scores[j] > best_score:
                best_score = scores[j]
                best_idx = i + j
        i += SIMD_W

    # Scalar tail
    while i < n:
        var score = ms.k0s[i] * q0 + ms.k1s[i] * q1
        if score > best_score:
            best_score = score
            best_idx = i
        i += 1

    var stored_addr = Int(ms.k0s[best_idx] / 2.0 + 0.5)
    if stored_addr == addr:
        return ms.vals[best_idx]
    return 0


# ─── Math helpers ────────────────────────────────────────────────

@always_inline
fn mask32(v: Int) -> Int:
    return v & MASK32


def trunc_div(b: Int, a: Int) -> Int:
    """Division truncating toward zero (WASM i32 semantics)."""
    # Python-compatible: int(b / a) truncates toward zero
    if a == 0:
        return 0  # caller handles trap
    var fb = Float64(b)
    var fa = Float64(a)
    var q = fb / fa
    if q >= 0.0:
        return Int(q)
    else:
        # truncate toward zero = ceil for negative quotient
        var qi = Int(q)
        # if there's a remainder, qi is already truncated by Float64→Int
        return qi


def trunc_rem(b: Int, a: Int) -> Int:
    """Remainder matching truncated division."""
    return b - trunc_div(b, a) * a


@always_inline
fn to_i32(val: Int) -> Int:
    return val & MASK32


@always_inline
fn shr_u(b: Int, a: Int) -> Int:
    """Logical (unsigned) right shift."""
    return to_i32(b) >> (a & 31)


@always_inline
fn shr_s(b: Int, a: Int) -> Int:
    """Arithmetic (signed) right shift."""
    var v = to_i32(b)
    var shift = a & 31
    if v >= 0x80000000:
        v -= 0x100000000
    var result = v >> shift
    if result < 0:
        return result & MASK32
    return result


@always_inline
fn rotl32(b: Int, a: Int) -> Int:
    var v = to_i32(b)
    var shift = a & 31
    if shift == 0:
        return v
    return ((v << shift) | (v >> (32 - shift))) & MASK32


@always_inline
fn rotr32(b: Int, a: Int) -> Int:
    var v = to_i32(b)
    var shift = a & 31
    if shift == 0:
        return v
    return ((v >> shift) | (v << (32 - shift))) & MASK32


@always_inline
fn clz32(val: Int) -> Int:
    var v = to_i32(val)
    if v == 0:
        return 32
    var n = 0
    if v <= 0x0000FFFF:
        n += 16
        v <<= 16
    if v <= 0x00FFFFFF:
        n += 8
        v <<= 8
    if v <= 0x0FFFFFFF:
        n += 4
        v <<= 4
    if v <= 0x3FFFFFFF:
        n += 2
        v <<= 2
    if v <= 0x7FFFFFFF:
        n += 1
    return n


@always_inline
fn ctz32(val: Int) -> Int:
    var v = to_i32(val)
    if v == 0:
        return 32
    var n = 0
    if (v & 0x0000FFFF) == 0:
        n += 16
        v >>= 16
    if (v & 0x000000FF) == 0:
        n += 8
        v >>= 8
    if (v & 0x0000000F) == 0:
        n += 4
        v >>= 4
    if (v & 0x00000003) == 0:
        n += 2
        v >>= 2
    if (v & 0x00000001) == 0:
        n += 1
    return n


@always_inline
fn popcnt32(val: Int) -> Int:
    var v = to_i32(val)
    v = v - ((v >> 1) & 0x55555555)
    v = (v & 0x33333333) + ((v >> 2) & 0x33333333)
    v = (v + (v >> 4)) & 0x0F0F0F0F
    return (v * 0x01010101) & MASK32
    # Note: >> 24 done by caller; just return popcount
    # actually this formula gives popcount in low byte after shift
    # fix: return the standard result


@always_inline
fn _popcnt32(val: Int) -> Int:
    """Correct popcount for 32-bit value."""
    var v = to_i32(val)
    var count = 0
    while v != 0:
        count += v & 1
        v >>= 1
    return count


@always_inline
fn sign_extend_8(val: Int) -> Int:
    var v = val & 0xFF
    if v >= 0x80:
        return v - 0x100
    return v


@always_inline
fn sign_extend_16(val: Int) -> Int:
    var v = val & 0xFFFF
    if v >= 0x8000:
        return v - 0x10000
    return v


# ─── Main executor ───────────────────────────────────────────────

def execute(prog_ops: List[Int], prog_args: List[Int], verbose: Bool = True, max_steps: Int = 5_000_000) raises -> Int:
    """Execute program; optionally print trace; return final top-of-stack.

    verbose=True  → emit one "op arg sp top" line per step (normal mode)
    verbose=False → silent execution for timing loops
    """

    # Pre-allocate capacity based on program size (opt 2+3: SoA MemSpace)
    var est_cap = len(prog_ops) * 3  # ~3 writes per instruction estimate
    var stack_keys  = MemSpace(est_cap)
    var locals_keys = MemSpace(est_cap // 2)
    var heap_keys   = MemSpace(est_cap // 2)
    var call_stack  = List[CallFrame]()

    var locals_base = 0
    var ip = 0
    var sp = 0

    var prog_len = len(prog_ops)
    for _step in range(max_steps):
        if ip >= prog_len:
            break

        var op  = prog_ops[ip]
        var arg = prog_args[ip]
        var next_ip = ip + 1
        var top = 0

        # ── Stack basics ──────────────────────────────────────────
        if op == OP_PUSH:
            sp += 1
            mem_write_compact(stack_keys, sp, arg)
            top = arg

        elif op == OP_POP:
            sp -= 1
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        elif op == OP_DUP:
            var v = mem_read(stack_keys, sp)
            sp += 1
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_SWAP:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            mem_write_compact(stack_keys, sp,     vb)
            mem_write_compact(stack_keys, sp - 1, va)
            top = vb

        elif op == OP_OVER:
            var vb = mem_read(stack_keys, sp - 1)
            sp += 1
            mem_write_compact(stack_keys, sp, vb)
            top = vb

        elif op == OP_ROT:
            var v_top    = mem_read(stack_keys, sp)
            var v_second = mem_read(stack_keys, sp - 1)
            var v_third  = mem_read(stack_keys, sp - 2)
            mem_write_compact(stack_keys, sp,     v_third)
            mem_write_compact(stack_keys, sp - 1, v_top)
            mem_write_compact(stack_keys, sp - 2, v_second)
            top = v_third

        elif op == OP_NOP:
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        elif op == OP_HALT:
            top = mem_read(stack_keys, sp) if sp > 0 else 0
            if verbose:
                print(op, arg, sp, top)
            return top

        # ── Arithmetic ───────────────────────────────────────────
        elif op == OP_ADD:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = mask32(va + vb)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_SUB:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = mask32(vb - va)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_MUL:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = mask32(va * vb)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_DIV_S or op == OP_DIV_U:
            var va = mem_read(stack_keys, sp)
            if va == 0:
                if verbose:
                    print(OP_TRAP, 0, sp, 0)
                return 0
            var vb = mem_read(stack_keys, sp - 1)
            var res = mask32(trunc_div(vb, va))
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_REM_S or op == OP_REM_U:
            var va = mem_read(stack_keys, sp)
            if va == 0:
                if verbose:
                    print(OP_TRAP, 0, sp, 0)
                return 0
            var vb = mem_read(stack_keys, sp - 1)
            var res = mask32(trunc_rem(vb, va))
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        # ── Comparisons ──────────────────────────────────────────
        elif op == OP_EQZ:
            var va = mem_read(stack_keys, sp)
            var res = 1 if va == 0 else 0
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_EQ:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = 1 if va == vb else 0
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_NE:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = 1 if va != vb else 0
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_LT_S or op == OP_LT_U:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = 1 if vb < va else 0
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_GT_S or op == OP_GT_U:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = 1 if vb > va else 0
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_LE_S or op == OP_LE_U:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = 1 if vb <= va else 0
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_GE_S or op == OP_GE_U:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = 1 if vb >= va else 0
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        # ── Bitwise ──────────────────────────────────────────────
        elif op == OP_AND:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = to_i32(va) & to_i32(vb)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_OR:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = to_i32(va) | to_i32(vb)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_XOR:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = to_i32(va) ^ to_i32(vb)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_SHL:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = mask32(to_i32(vb) << (va & 31))
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_SHR_S:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = shr_s(vb, va)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_SHR_U:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = shr_u(vb, va)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_ROTL:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = rotl32(vb, va)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_ROTR:
            var va = mem_read(stack_keys, sp)
            var vb = mem_read(stack_keys, sp - 1)
            var res = rotr32(vb, va)
            sp -= 1
            mem_write_compact(stack_keys, sp, res)
            top = res

        # ── Unary + parametric ───────────────────────────────────
        elif op == OP_CLZ:
            var va = mem_read(stack_keys, sp)
            var res = clz32(va)
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_CTZ:
            var va = mem_read(stack_keys, sp)
            var res = ctz32(va)
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_POPCNT:
            var va = mem_read(stack_keys, sp)
            var res = _popcnt32(va)
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_ABS:
            var va = mem_read(stack_keys, sp)
            var res = -va if va < 0 else va
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_NEG:
            var va = mem_read(stack_keys, sp)
            var res = mask32(-va)
            mem_write_compact(stack_keys, sp, res)
            top = res

        elif op == OP_SELECT:
            var va = mem_read(stack_keys, sp)      # c (condition)
            var vb = mem_read(stack_keys, sp - 1)  # b (false value)
            var vc = mem_read(stack_keys, sp - 2)  # a (true value)
            var res = vc if va != 0 else vb
            sp -= 2
            mem_write_compact(stack_keys, sp, res)
            top = res

        # ── Locals ───────────────────────────────────────────────
        elif op == OP_LOCAL_GET:
            var actual_idx = locals_base + arg
            var v = mem_read(locals_keys, actual_idx)
            sp += 1
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_LOCAL_SET:
            var v = mem_read(stack_keys, sp)
            sp -= 1
            var actual_idx = locals_base + arg
            mem_write(locals_keys, actual_idx, v)
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        elif op == OP_LOCAL_TEE:
            var v = mem_read(stack_keys, sp)
            var actual_idx = locals_base + arg
            mem_write(locals_keys, actual_idx, v)
            top = v

        # ── Linear memory ────────────────────────────────────────
        elif op == OP_I32_LOAD:
            var addr = mem_read(stack_keys, sp)
            var v = mem_read(heap_keys, addr)
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_I32_STORE:
            var v    = mem_read(stack_keys, sp)
            var addr = mem_read(stack_keys, sp - 1)
            mem_write_compact(heap_keys, addr, v)
            sp -= 2
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        elif op == OP_I32_LOAD8_U:
            var addr = mem_read(stack_keys, sp)
            var v = mem_read(heap_keys, addr) & 0xFF
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_I32_LOAD8_S:
            var addr = mem_read(stack_keys, sp)
            var v = sign_extend_8(mem_read(heap_keys, addr))
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_I32_LOAD16_U:
            var addr = mem_read(stack_keys, sp)
            var v = mem_read(heap_keys, addr) & 0xFFFF
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_I32_LOAD16_S:
            var addr = mem_read(stack_keys, sp)
            var v = sign_extend_16(mem_read(heap_keys, addr))
            mem_write_compact(stack_keys, sp, v)
            top = v

        elif op == OP_I32_STORE8:
            var v    = mem_read(stack_keys, sp) & 0xFF
            var addr = mem_read(stack_keys, sp - 1)
            mem_write_compact(heap_keys, addr, v)
            sp -= 2
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        elif op == OP_I32_STORE16:
            var v    = mem_read(stack_keys, sp) & 0xFFFF
            var addr = mem_read(stack_keys, sp - 1)
            mem_write_compact(heap_keys, addr, v)
            sp -= 2
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        # ── Function calls ───────────────────────────────────────
        elif op == OP_CALL:
            call_stack.append(CallFrame(ip + 1, sp, locals_base))
            locals_base = len(locals_keys.k0s)
            top = mem_read(stack_keys, sp) if sp > 0 else 0
            next_ip = arg

        elif op == OP_RETURN:
            if len(call_stack) == 0:
                if verbose:
                    print(OP_TRAP, 0, sp, 0)
                return 0
            var ret_val = mem_read(stack_keys, sp)
            var frame   = call_stack.pop()
            sp = frame.saved_sp + 1
            mem_write_compact(stack_keys, sp, ret_val)
            locals_base = frame.saved_locals_base
            top = ret_val
            next_ip = frame.ret_addr

        # ── Control flow ─────────────────────────────────────────
        elif op == OP_JZ:
            var cond = mem_read(stack_keys, sp)
            sp -= 1
            top = mem_read(stack_keys, sp) if sp > 0 else 0
            if cond == 0:
                next_ip = arg

        elif op == OP_JNZ:
            var cond = mem_read(stack_keys, sp)
            sp -= 1
            top = mem_read(stack_keys, sp) if sp > 0 else 0
            if cond != 0:
                next_ip = arg

        else:
            # Unknown opcode — treat as NOP (matches NumPyExecutor)
            top = mem_read(stack_keys, sp) if sp > 0 else 0

        if verbose:
            print(op, arg, sp, top)
        ip = next_ip

    return mem_read(stack_keys, sp) if sp > 0 else 0


# ─── Helpers ─────────────────────────────────────────────────────

def sort_list(mut lst: List[Int]):
    """In-place insertion sort for timing samples (small N)."""
    for i in range(1, len(lst)):
        var key = lst[i]
        var j = i - 1
        while j >= 0 and lst[j] > key:
            lst[j + 1] = lst[j]
            j -= 1
        lst[j + 1] = key


# ─── Entry point ─────────────────────────────────────────────────

def main() raises:
    var args = argv()

    # Check for --repeat N flag (timing mode)
    var repeat = 0
    var max_steps = 5_000_000
    var quiet = False
    var arg_start = 1
    if len(args) > 2 and args[1] == "--repeat":
        repeat = atol(args[2])
        arg_start = 3
    if len(args) > arg_start + 1 and args[arg_start] == "--max-steps":
        max_steps = atol(args[arg_start + 1])
        arg_start += 2
    if len(args) > arg_start and args[arg_start] == "--quiet":
        quiet = True
        arg_start += 1

    # Build program string from remaining args or stdin
    var prog_str: String
    if len(args) > arg_start:
        prog_str = String()
        for i in range(arg_start, len(args)):
            if i > arg_start:
                prog_str += " "
            prog_str += args[i]
    else:
        prog_str = input()

    # Parse "op arg op arg ..." into parallel lists
    var tokens = prog_str.split(" ")
    var prog_ops  = List[Int]()
    var prog_args = List[Int]()
    var i = 0
    while i < len(tokens):
        var tok = tokens[i]
        if len(tok) == 0:
            i += 1
            continue
        var op = atol(tok)
        i += 1
        var arg = 0
        if i < len(tokens) and len(tokens[i]) > 0:
            arg = atol(tokens[i])
            i += 1
        prog_ops.append(op)
        prog_args.append(arg)

    if repeat > 0:
        # ── Timing mode: run N times silently, report median ns ──
        var samples = List[Int]()
        for _ in range(repeat):
            var t0 = Int(perf_counter_ns())
            var _ = execute(prog_ops, prog_args, verbose=False, max_steps=max_steps)
            samples.append(Int(perf_counter_ns()) - t0)
        sort_list(samples)
        var median = samples[repeat // 2]
        print("TIMING_NS:", median)
    else:
        # ── Normal mode: print trace + result ──
        var result = execute(prog_ops, prog_args, verbose=not quiet, max_steps=max_steps)
        print("RESULT:", result)
