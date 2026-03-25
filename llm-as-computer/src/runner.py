"""Runner for the LLM-as-Computer compiled transformer stack machine.

Handles: Mojo installation, compilation, program execution, trace formatting.
Falls back to a pure-Python executor if Mojo is unavailable.
"""

import os
import subprocess
import sys
import time

# Add this directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from isa_lite import Instruction, OP_NAMES, OP_PUSH, OP_JZ, OP_JNZ, OP_HALT, OP_TRAP, OP_CALL, OP_LOCAL_GET, OP_LOCAL_SET, OP_LOCAL_TEE


SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
MOJO_SRC = os.path.join(SKILL_DIR, "executor.mojo")
MOJO_BIN = os.path.join(SKILL_DIR, "percepta_exec")


def _instrs_to_tokens(prog):
    """Convert List[Instruction] → space-separated 'op arg op arg ...' string."""
    parts = []
    for instr in prog:
        parts.append(str(instr.op))
        parts.append(str(instr.arg))
    return " ".join(parts)


# ─── Setup ────────────────────────────────────────────────────────

def ensure_mojo():
    """Install Mojo if not present. Returns True if available."""
    try:
        r = subprocess.run(["mojo", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("Installing Mojo (~20s)...")
    # Slim install: modular --no-deps gets compiler binary without ML serving deps
    # Then mojo + max for entry points and base stdlib
    r = subprocess.run(
        ["uv", "pip", "install", "--system", "--break-system-packages",
         "modular", "--no-deps"],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        print(f"Mojo install failed (modular): {r.stderr[-200:]}")
        return False
    
    r = subprocess.run(
        ["uv", "pip", "install", "--system", "--break-system-packages",
         "mojo", "max"],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        print(f"Mojo install failed (mojo+max): {r.stderr[-200:]}")
        return False
    
    try:
        r = subprocess.run(["mojo", "--version"], capture_output=True, text=True, timeout=5)
        print(f"Mojo installed: {r.stdout.strip()}")
        return True
    except Exception:
        return False


def compile_mojo():
    """Compile executor.mojo → binary. Returns path or None."""
    if os.path.exists(MOJO_BIN):
        return MOJO_BIN
    
    if not os.path.exists(MOJO_SRC):
        print(f"Mojo source not found: {MOJO_SRC}")
        return None
    
    print("Compiling Mojo executor (~6s)...")
    r = subprocess.run(
        ["mojo", "build", MOJO_SRC, "-o", MOJO_BIN],
        capture_output=True, text=True, timeout=60
    )
    if r.returncode != 0:
        print(f"Compilation failed: {r.stderr[-300:]}")
        return None
    
    print(f"Compiled: {MOJO_BIN}")
    return MOJO_BIN


def setup():
    """Full setup: install Mojo + compile. Returns (binary_path, backend_name)."""
    if os.path.exists(MOJO_BIN):
        return MOJO_BIN, "mojo"
    if ensure_mojo():
        path = compile_mojo()
        if path:
            return path, "mojo"
    return None, "python"


# ─── Execution ────────────────────────────────────────────────────

def _run_mojo(prog, max_steps=5000000, repeat=0):
    """Execute via Mojo binary. Returns (output_lines, elapsed_ns)."""
    token_str = _instrs_to_tokens(prog)
    
    if repeat > 0:
        cmd = [MOJO_BIN, "--repeat", str(repeat), "--max-steps", str(max_steps)] + token_str.split()
    else:
        cmd = [MOJO_BIN, "--max-steps", str(max_steps)] + token_str.split()
    
    timeout = max(30, max_steps // 100000)  # scale timeout with step count
    t0 = time.perf_counter_ns()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    elapsed = time.perf_counter_ns() - t0
    
    if r.returncode != 0:
        raise RuntimeError(f"Mojo executor failed: {r.stderr[:200]}")
    
    return r.stdout.strip().split("\n"), elapsed


def _run_python(prog, max_steps=5000000):
    """Pure Python fallback executor (no deps beyond stdlib)."""
    # Minimal stack machine - same semantics as Mojo executor
    from isa_lite import MASK32
    
    stack = {}
    sp = 0
    ip = 0
    lines = []
    
    for _step in range(max_steps):
        if ip >= len(prog):
            break
        instr = prog[ip]
        op, arg = instr.op, instr.arg
        next_ip = ip + 1
        top = 0
        
        if op == 1:  # PUSH
            sp += 1; stack[sp] = arg; top = arg
        elif op == 2:  # POP
            sp -= 1; top = stack.get(sp, 0) if sp > 0 else 0
        elif op == 3:  # ADD
            a, b = stack.get(sp, 0), stack.get(sp-1, 0)
            sp -= 1; stack[sp] = (a + b) & MASK32; top = stack[sp]
        elif op == 4:  # DUP
            v = stack.get(sp, 0); sp += 1; stack[sp] = v; top = v
        elif op == 5:  # HALT
            top = stack.get(sp, 0) if sp > 0 else 0
            lines.append(f"{op} {arg} {sp} {top}")
            return lines, top
        elif op == 6:  # SUB
            a, b = stack.get(sp, 0), stack.get(sp-1, 0)
            sp -= 1; stack[sp] = (b - a) & MASK32; top = stack[sp]
        elif op == 7:  # JZ
            cond = stack.get(sp, 0); sp -= 1
            top = stack.get(sp, 0) if sp > 0 else 0
            if cond == 0: next_ip = arg
        elif op == 8:  # JNZ
            cond = stack.get(sp, 0); sp -= 1
            top = stack.get(sp, 0) if sp > 0 else 0
            if cond != 0: next_ip = arg
        elif op == 10:  # SWAP
            a, b = stack.get(sp, 0), stack.get(sp-1, 0)
            stack[sp] = b; stack[sp-1] = a; top = b
        elif op == 11:  # OVER
            v = stack.get(sp-1, 0); sp += 1; stack[sp] = v; top = v
        elif op == 12:  # ROT
            a, b, c = stack.get(sp, 0), stack.get(sp-1, 0), stack.get(sp-2, 0)
            stack[sp] = c; stack[sp-1] = a; stack[sp-2] = b; top = c
        elif op == 13:  # MUL
            a, b = stack.get(sp, 0), stack.get(sp-1, 0)
            sp -= 1; stack[sp] = (a * b) & MASK32; top = stack[sp]
        else:
            top = stack.get(sp, 0) if sp > 0 else 0
        
        lines.append(f"{op} {arg} {sp} {top}")
        ip = next_ip
    
    return lines, stack.get(sp, 0) if sp > 0 else 0


def execute(prog, max_steps=5000000, verbose=True, benchmark_repeat=0):
    """Execute a program. Returns (result, trace_lines, backend, timing_info).
    
    Args:
        prog: List[Instruction] or (List[Instruction], expected) tuple
        max_steps: execution limit
        verbose: whether to collect trace
        benchmark_repeat: if >0, run N times and report median timing
    """
    prog = _unpack(prog)
    backend = "mojo" if os.path.exists(MOJO_BIN) else "python"
    
    if backend == "mojo":
        if benchmark_repeat > 0:
            lines, wall_ns = _run_mojo(prog, max_steps, repeat=benchmark_repeat)
            # Parse TIMING_NS from output
            for line in lines:
                if line.startswith("TIMING_NS:"):
                    median_ns = int(line.split(":")[1].strip())
                    return None, [], "mojo", {"median_ns": median_ns, "repeat": benchmark_repeat}
        
        lines, wall_ns = _run_mojo(prog, max_steps)
        # Last line is "RESULT: N"
        result = None
        trace_lines = []
        for line in lines:
            if line.startswith("RESULT:"):
                result = int(line.split(":")[1].strip())
            else:
                trace_lines.append(line)
        return result, trace_lines, "mojo", {"wall_ns": wall_ns}
    else:
        t0 = time.perf_counter_ns()
        lines, result = _run_python(prog, max_steps)
        elapsed = time.perf_counter_ns() - t0
        return result, lines, "python", {"wall_ns": elapsed}


# ─── Formatting ───────────────────────────────────────────────────

def format_trace(prog, trace_lines, result, backend, timing):
    """Format execution output for display."""
    out = []
    out.append(f"Program: {len(prog)} instructions | Backend: {backend}")
    
    if "median_ns" in timing:
        ns = timing["median_ns"]
        steps = len(trace_lines) if trace_lines else _count_steps(prog)
        out.append(f"Benchmark: {ns/1000:.2f} µs/exec ({timing['repeat']} runs)")
        if steps > 0:
            out.append(f"Throughput: {steps * 1e9 / ns:,.0f} steps/s")
        return "\n".join(out)
    
    # Show program listing
    out.append("")
    out.append("Instructions:")
    for i, instr in enumerate(prog):
        out.append(f"  {i:3d}: {instr}")
    
    # Show trace (abbreviated if long)
    if trace_lines:
        n = len(trace_lines)
        out.append(f"\nExecution trace ({n} steps):")
        out.append(f"{'Step':>5}  {'Op':<12} {'SP':>3}  {'Top':>8}")
        out.append("-" * 35)
        
        show_lines = trace_lines
        truncated = False
        if n > 40:
            show_lines = trace_lines[:15] + trace_lines[-10:]
            truncated = True
        
        step_i = 0
        for i, line in enumerate(show_lines):
            if truncated and i == 15:
                out.append(f"  ... ({n - 25} steps omitted) ...")
                step_i = n - 10
            parts = line.strip().split()
            if len(parts) >= 4:
                op_num, arg, sp, top = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                name = OP_NAMES.get(op_num, f"?{op_num}")
                if op_num in (1, 7, 8, 43, 44, 45, 54):  # ops with args
                    instr_str = f"{name} {arg}"
                else:
                    instr_str = name
                out.append(f"{step_i:5d}  {instr_str:<12} {sp:3d}  {top:8d}")
            step_i += 1
    
    if result is not None:
        out.append(f"\n→ Result: {result}")
    
    if "wall_ns" in timing:
        out.append(f"  Wall time: {timing['wall_ns']/1e6:.1f} ms")
    
    return "\n".join(out)


def _count_steps(prog):
    """Estimate step count by running silently."""
    try:
        _, lines, _, _ = execute(prog, verbose=False)
        return len(lines)
    except Exception:
        return 0


# ─── High-level API ───────────────────────────────────────────────

def _unpack(prog):
    """Handle both List[Instruction] and (List[Instruction], expected) tuples."""
    if isinstance(prog, tuple) and len(prog) == 2 and isinstance(prog[0], list):
        return prog[0]
    return prog


def run(prog, benchmark=False, repeat=200):
    """Execute and format a program. Returns formatted string.
    
    Args:
        prog: List[Instruction], or (List[Instruction], expected) tuple
        benchmark: if True, run timing benchmark
        repeat: number of benchmark iterations
    """
    prog = _unpack(prog)
    if benchmark:
        result, lines, backend, timing = execute(prog, benchmark_repeat=repeat)
    else:
        result, lines, backend, timing = execute(prog)
    
    return format_trace(prog, lines, result, backend, timing)


def demo():
    """Run a demo showing the concept: fibonacci via compiled transformer attention."""
    from programs import make_fibonacci
    
    print("=" * 60)
    print("LLM-as-Computer: Compiled Transformer Stack Machine")
    print("=" * 60)
    print()
    print("Every instruction fetch and stack read is a parabolic")
    print("attention head: dot-product → argmax → value extraction.")
    print("The transformer's weights ARE the interpreter.")
    print()
    
    prog, expected = make_fibonacci(10)
    output = run(prog)
    print(output)
    
    backend = "mojo" if os.path.exists(MOJO_BIN) else "python"
    if backend == "mojo":
        print("\n--- Benchmark ---")
        bench = run(prog, benchmark=True)
        print(bench)


if __name__ == "__main__":
    demo()
