"""LLM-as-Computer: Compiled Transformer Stack Machine"""
from std.time import perf_counter_ns

comptime OP_PUSH = 1; comptime OP_POP = 2; comptime OP_ADD = 3
comptime OP_DUP = 4; comptime OP_HALT = 5; comptime OP_SUB = 6
comptime OP_JZ = 7; comptime OP_JNZ = 8; comptime OP_NOP = 9
comptime OP_SWAP = 10; comptime OP_OVER = 11; comptime OP_ROT = 12
comptime EPS: Float64 = 1e-6; comptime MAX_STEPS = 100000

@fieldwise_init
struct V(ImplicitlyCopyable, Movable):
    var pk0: Float64  # prog key: 2*pos
    var pk1: Float64  # prog key: -pos^2
    var sk0: Float64  # stack key: 2*addr
    var sk1: Float64  # stack key: -addr^2+eps*wc
    var opc: Float64  # opcode
    var val: Float64  # value (arg or stack value)

@always_inline
def ep(pos: Int, op: Int, arg: Int) -> V:
    return V(2.0*Float64(pos), -Float64(pos*pos), 0.0, 0.0, Float64(op), Float64(arg))

@always_inline
def es(addr: Int, val: Int, wc: Int) -> V:
    return V(0.0, 0.0, 2.0*Float64(addr), -Float64(addr*addr)+EPS*Float64(wc), 0.0, Float64(val))

@always_inline
def pf_op(ip: Int, p: List[V], n: Int) -> Int:
    var q = Float64(ip); var bs: Float64 = -1e30; var bi: Int = 0
    for i in range(n):
        var s = p[i].pk0 * q + p[i].pk1
        if s > bs: bs = s; bi = i
    return Int(p[bi].opc + 0.5)

@always_inline
def pf_arg(ip: Int, p: List[V], n: Int) -> Int:
    var q = Float64(ip); var bs: Float64 = -1e30; var bi: Int = 0
    for i in range(n):
        var s = p[i].pk0 * q + p[i].pk1
        if s > bs: bs = s; bi = i
    var v = p[bi].val
    return Int(v + 0.5) if v >= 0.0 else Int(v - 0.5)

@always_inline
def sr(sp: Int, off: Int, stk: List[V], n: Int) -> Int:
    if n == 0: return 0
    var tgt = sp + off; var q = Float64(tgt)
    var bs: Float64 = -1e30; var bi: Int = 0
    for i in range(n):
        var s = stk[i].sk0 * q + stk[i].sk1
        if s > bs: bs = s; bi = i
    if Int(stk[bi].sk0 / 2.0 + 0.5) != tgt: return 0
    var v = stk[bi].val
    return Int(v + 0.5) if v >= 0.0 else Int(v - 0.5)

@always_inline
def sw(mut stk: List[V], mut ns: Int, mut wc: Int, addr: Int, val: Int):
    stk.append(es(addr, val, wc)); ns += 1; wc += 1

@fieldwise_init
struct Step(ImplicitlyCopyable, Movable):
    var op: Int; var arg: Int; var sp: Int; var top: Int

def execute(ops: List[Int], args: List[Int], np: Int, max_steps: Int) -> List[Step]:
    var p = List[V]()
    for i in range(np): p.append(ep(i, ops[i], args[i]))
    var stk = List[V](); var ns: Int = 0; var wc: Int = 0
    var ip: Int = 0; var sp: Int = 0; var trace = List[Step]()

    for _ in range(max_steps):
        if ip >= np: break
        var op = pf_op(ip, p, np)
        var arg = pf_arg(ip, p, np)
        var a = sr(sp, 0, stk, ns)
        var b = sr(sp, -1, stk, ns)
        var c = sr(sp, -2, stk, ns)
        var sd: Int = 0; var top: Int = 0

        if op == OP_HALT:
            trace.append(Step(op, arg, sp, a)); break
        elif op == OP_PUSH:
            sd = 1; top = arg
        elif op == OP_POP:
            sd = -1; top = b
        elif op == OP_ADD:
            sd = -1; top = a + b
        elif op == OP_SUB:
            sd = -1; top = b - a
        elif op == OP_DUP:
            sd = 1; top = a
        elif op == OP_SWAP:
            sw(stk, ns, wc, sp, b); sw(stk, ns, wc, sp-1, a)
            trace.append(Step(op, arg, sp, b)); ip += 1; continue
        elif op == OP_OVER:
            sd = 1; top = b
        elif op == OP_ROT:
            sw(stk, ns, wc, sp, c); sw(stk, ns, wc, sp-1, a); sw(stk, ns, wc, sp-2, b)
            trace.append(Step(op, arg, sp, c)); ip += 1; continue
        elif op == OP_JZ:
            sd = -1; top = 0
        elif op == OP_JNZ:
            sd = -1; top = 0
        elif op == OP_NOP:
            sd = 0; top = a

        var nsp = sp + sd
        if op == OP_PUSH or op == OP_DUP or op == OP_ADD or op == OP_SUB or op == OP_OVER:
            sw(stk, ns, wc, nsp, top)
        trace.append(Step(op, arg, nsp, top)); sp = nsp

        if op == OP_JZ:
            ip = arg if sr(sp, 1, stk, ns) == 0 else ip + 1
        elif op == OP_JNZ:
            ip = arg if sr(sp, 1, stk, ns) != 0 else ip + 1
        else:
            ip += 1
    return trace^

def opname(op: Int) -> String:
    if op == 1: return "PUSH"
    if op == 2: return "POP"
    if op == 3: return "ADD"
    if op == 4: return "DUP"
    if op == 5: return "HALT"
    if op == 6: return "SUB"
    if op == 7: return "JZ"
    if op == 8: return "JNZ"
    if op == 9: return "NOP"
    if op == 10: return "SWAP"
    if op == 11: return "OVER"
    if op == 12: return "ROT"
    return "???"

def main() raises:
    from std.os import getenv
    var prog_file = getenv("PERCEPTA_PROG", "")
    if len(prog_file) == 0:
        print("Set PERCEPTA_PROG=/path/to/file"); return

    var show_trace = len(getenv("PERCEPTA_NOTRACE", "")) == 0
    var max_steps = MAX_STEPS
    var ms_env = getenv("PERCEPTA_MAXSTEPS", "")
    if len(ms_env) > 0: max_steps = Int(atof(ms_env))

    var ops = List[Int](); var arguments = List[Int](); var n: Int = 0
    var content = open(prog_file, "r").read()
    var lines = content.split("\n")
    for i in range(len(lines)):
        var line = String(lines[i]).strip()
        if len(line) == 0: continue
        var parts = line.split(" ")
        if len(parts) >= 2:
            ops.append(Int(atof(parts[0])))
            arguments.append(Int(atof(parts[1])))
            n += 1

    print("PROGRAM (", n, "instructions):")
    for i in range(n):
        var line = "  " + String(i) + ": " + opname(ops[i])
        if ops[i] == OP_PUSH or ops[i] == OP_JZ or ops[i] == OP_JNZ:
            line = line + " " + String(arguments[i])
        print(line)

    var t0 = perf_counter_ns()
    var trace = execute(ops, arguments, n, max_steps)
    var elapsed = perf_counter_ns() - t0
    var steps = len(trace)

    if show_trace:
        print("\nTRACE (", steps, "steps):")
        for i in range(steps):
            var s = trace[i]
            var on = opname(s.op)
            while len(on) < 5: on = on + " "
            var line = "  " + String(i) + "\t" + on
            if s.op == OP_PUSH or s.op == OP_JZ or s.op == OP_JNZ:
                line = line + " " + String(s.arg)
            line = line + "\t-> sp=" + String(s.sp) + " top=" + String(s.top)
            print(line)

    var last = trace[steps - 1]
    print("\nRESULT:", last.top)
    print("STEPS: ", steps)
    print("TIME:  ", Float64(elapsed)/1000.0, "us (",
          Float64(steps) / (Float64(elapsed)/1e9), "steps/s)")
