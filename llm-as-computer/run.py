"""
LLM-as-Computer: run programs through a compiled transformer.

Every instruction fetch and stack read is a parabolic attention
head: dot-product → argmax → value extraction. The same mechanism
a transformer uses, compiled into weight matrices.

Usage:
    from run import run, fib, multiply, power2, sum_n
    run("PUSH 3\nPUSH 4\nADD\nHALT")
    fib(10)         # → 55
    multiply(7, 8)  # → 56
    power2(8)       # → 256
    sum_n(100)      # → 5050
"""

import subprocess, os, tempfile

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
MOJO_SRC = os.path.join(SKILL_DIR, "executor.mojo")
BINARY = "/home/claude/percepta_exec"

# Opcode table
OPS = {
    "PUSH": 1, "POP": 2, "ADD": 3, "DUP": 4, "HALT": 5,
    "SUB": 6, "JZ": 7, "JNZ": 8, "NOP": 9,
    "SWAP": 10, "OVER": 11, "ROT": 12,
}

def _ensure():
    if os.path.exists(BINARY):
        return True
    if subprocess.run(["mojo", "--version"], capture_output=True).returncode != 0:
        print("Installing Mojo...")
        subprocess.run(["pip", "install", "--break-system-packages", "modular"],
                       capture_output=True)
    print("Building percepta executor...")
    r = subprocess.run(["mojo", "build", MOJO_SRC, "-o", BINARY],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Build failed: {r.stderr}")
        return False
    return True


def _asm_to_numeric(text):
    """Convert assembly text to numeric 'op arg' format."""
    lines = []
    for line in text.strip().split("\n"):
        line = line.split("#")[0].split(";")[0].strip()
        if not line:
            continue
        parts = line.upper().split()
        mnemonic = parts[0]
        if mnemonic not in OPS:
            raise ValueError(f"Unknown opcode: {mnemonic}")
        op = OPS[mnemonic]
        arg = int(parts[1]) if len(parts) > 1 else 0
        lines.append(f"{op} {arg}")
    return "\n".join(lines)


def run(asm_text, trace=True, max_steps=100000):
    """Run assembly through the compiled transformer executor.
    Returns (result, output_text)."""
    if not _ensure():
        return None, "ERROR: could not build executor"

    numeric = _asm_to_numeric(asm_text)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.num', delete=False) as f:
        f.write(numeric)
        prog_file = f.name

    try:
        env = os.environ.copy()
        env["PERCEPTA_PROG"] = prog_file
        if not trace:
            env["PERCEPTA_NOTRACE"] = "1"
        if max_steps != 100000:
            env["PERCEPTA_MAXSTEPS"] = str(max_steps)

        r = subprocess.run([BINARY], capture_output=True, text=True, env=env, timeout=30)
        output = r.stdout

        # Extract result
        result = None
        for line in output.split("\n"):
            if line.startswith("RESULT:"):
                result = int(line.split(":")[1].strip())
        return result, output
    finally:
        os.unlink(prog_file)


# ─── Algorithm generators ──────────────────────────────────────────

def fib(n, trace=True):
    """Fibonacci via compiled attention. SWAP/OVER/ADD + ROT counter."""
    if n == 0: return run("PUSH 0\nHALT", trace)
    if n == 1: return run("PUSH 1\nHALT", trace)
    asm = f"""PUSH 0
PUSH 1
PUSH {n-1}
ROT
ROT
SWAP
OVER
ADD
ROT
PUSH 1
SUB
DUP
JNZ 15
POP
HALT
ROT
ROT
PUSH 1
JNZ 5"""
    return run(asm, trace)


def multiply(a, b, trace=True):
    """a × b via repeated addition through attention heads."""
    if a == 0 or b == 0: return run("PUSH 0\nHALT", trace)
    asm = f"""PUSH {a}
PUSH 0
PUSH {b}
DUP
JZ 14
PUSH 1
SUB
ROT
ROT
OVER
ADD
ROT
PUSH 1
JNZ 3
POP
SWAP
POP
HALT"""
    return run(asm, trace)


def power2(n, trace=True):
    """2^n via repeated doubling (DUP + ADD)."""
    if n == 0: return run("PUSH 1\nHALT", trace)
    asm = f"""PUSH 1
PUSH {n}
DUP
JZ 12
PUSH 1
SUB
SWAP
DUP
ADD
SWAP
PUSH 1
JNZ 2
POP
HALT"""
    return run(asm, trace)


def sum_n(n, trace=True):
    """Sum 1+2+...+n via loop with ROT/ADD."""
    if n == 0: return run("PUSH 0\nHALT", trace)
    asm = f"""PUSH 0
PUSH {n}
DUP
JZ 12
DUP
ROT
ADD
SWAP
PUSH 1
SUB
PUSH 1
JNZ 2
POP
HALT"""
    return run(asm, trace)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        with open(sys.argv[1]) as f:
            text = f.read()
        _, output = run(text, trace="--notrace" not in sys.argv)
        print(output)
    else:
        print("Demo: fib(10)")
        result, output = fib(10)
        print(output)
        print(f"\nDemo: multiply(7, 8)")
        result, output = multiply(7, 8)
        print(output)
        print(f"\nDemo: 2^10")
        result, output = power2(10)
        print(output)
        print(f"\nDemo: sum(1..100)")
        result, output = sum_n(100, trace=False)
        print(output)
