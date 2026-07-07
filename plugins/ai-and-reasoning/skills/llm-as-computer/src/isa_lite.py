"""Lightweight ISA definition for the compiled transformer stack machine.

Torch-free version of isa.py for use in the claude.ai skill.
Contains only: opcodes, names, Instruction type, program() builder.
"""

from dataclasses import dataclass
from typing import List


# ─── Types ────────────────────────────────────────────────────────

@dataclass
class Instruction:
    op: int
    arg: int = 0

    def __repr__(self):
        name = OP_NAMES.get(self.op, f"?{self.op}")
        if self.op in (OP_PUSH, OP_JZ, OP_JNZ,
                        OP_LOCAL_GET, OP_LOCAL_SET, OP_LOCAL_TEE,
                        OP_CALL):
            return f"{name} {self.arg}"
        return name


# ─── Opcodes ─────────────────────────────────────────────────────

OP_PUSH = 1;  OP_POP  = 2;  OP_ADD  = 3;  OP_DUP  = 4;  OP_HALT = 5
OP_SUB = 6;   OP_JZ  = 7;   OP_JNZ = 8;   OP_NOP = 9
OP_SWAP = 10; OP_OVER = 11;  OP_ROT  = 12
OP_MUL   = 13; OP_DIV_S = 14; OP_DIV_U = 15; OP_REM_S = 16; OP_REM_U = 17
OP_EQZ   = 18; OP_EQ = 19;    OP_NE = 20
OP_LT_S  = 21; OP_LT_U = 22;  OP_GT_S = 23; OP_GT_U = 24
OP_LE_S  = 25; OP_LE_U = 26;  OP_GE_S = 27; OP_GE_U = 28
OP_AND   = 29; OP_OR = 30;    OP_XOR = 31
OP_SHL   = 32; OP_SHR_S = 33; OP_SHR_U = 34; OP_ROTL = 35; OP_ROTR = 36
OP_CLZ    = 37; OP_CTZ = 38;   OP_POPCNT = 39; OP_ABS = 40; OP_NEG = 41
OP_SELECT = 42
OP_LOCAL_GET = 43; OP_LOCAL_SET = 44; OP_LOCAL_TEE = 45
OP_I32_LOAD    = 46; OP_I32_STORE   = 47
OP_I32_LOAD8_U = 48; OP_I32_LOAD8_S = 49
OP_I32_LOAD16_U = 50; OP_I32_LOAD16_S = 51
OP_I32_STORE8  = 52; OP_I32_STORE16 = 53
OP_CALL   = 54; OP_RETURN = 55
OP_TRAP  = 99

MASK32 = 0xFFFFFFFF

OP_NAMES = {
    OP_PUSH: "PUSH", OP_POP: "POP", OP_ADD: "ADD", OP_DUP: "DUP", OP_HALT: "HALT",
    OP_SUB: "SUB", OP_JZ: "JZ", OP_JNZ: "JNZ", OP_NOP: "NOP",
    OP_SWAP: "SWAP", OP_OVER: "OVER", OP_ROT: "ROT",
    OP_MUL: "MUL", OP_DIV_S: "DIV_S", OP_DIV_U: "DIV_U",
    OP_REM_S: "REM_S", OP_REM_U: "REM_U",
    OP_EQZ: "EQZ", OP_EQ: "EQ", OP_NE: "NE",
    OP_LT_S: "LT_S", OP_LT_U: "LT_U", OP_GT_S: "GT_S", OP_GT_U: "GT_U",
    OP_LE_S: "LE_S", OP_LE_U: "LE_U", OP_GE_S: "GE_S", OP_GE_U: "GE_U",
    OP_AND: "AND", OP_OR: "OR", OP_XOR: "XOR",
    OP_SHL: "SHL", OP_SHR_S: "SHR_S", OP_SHR_U: "SHR_U",
    OP_ROTL: "ROTL", OP_ROTR: "ROTR",
    OP_CLZ: "CLZ", OP_CTZ: "CTZ", OP_POPCNT: "POPCNT",
    OP_ABS: "ABS", OP_NEG: "NEG", OP_SELECT: "SELECT",
    OP_LOCAL_GET: "LOCAL.GET", OP_LOCAL_SET: "LOCAL.SET", OP_LOCAL_TEE: "LOCAL.TEE",
    OP_I32_LOAD: "I32.LOAD", OP_I32_STORE: "I32.STORE",
    OP_I32_LOAD8_U: "I32.LOAD8_U", OP_I32_LOAD8_S: "I32.LOAD8_S",
    OP_I32_LOAD16_U: "I32.LOAD16_U", OP_I32_LOAD16_S: "I32.LOAD16_S",
    OP_I32_STORE8: "I32.STORE8", OP_I32_STORE16: "I32.STORE16",
    OP_CALL: "CALL", OP_RETURN: "RETURN",
    OP_TRAP: "TRAP",
}

_NAME_TO_OP = {
    "PUSH": 1, "POP": 2, "ADD": 3, "DUP": 4, "HALT": 5,
    "SUB": 6, "JZ": 7, "JNZ": 8, "NOP": 9,
    "SWAP": 10, "OVER": 11, "ROT": 12,
    "MUL": 13, "DIV_S": 14, "DIV_U": 15, "REM_S": 16, "REM_U": 17,
    "EQZ": 18, "EQ": 19, "NE": 20,
    "LT_S": 21, "LT_U": 22, "GT_S": 23, "GT_U": 24,
    "LE_S": 25, "LE_U": 26, "GE_S": 27, "GE_U": 28,
    "AND": 29, "OR": 30, "XOR": 31,
    "SHL": 32, "SHR_S": 33, "SHR_U": 34, "ROTL": 35, "ROTR": 36,
    "CLZ": 37, "CTZ": 38, "POPCNT": 39, "ABS": 40, "NEG": 41,
    "SELECT": 42,
    "LOCAL.GET": 43, "LOCAL.SET": 44, "LOCAL.TEE": 45,
    "I32.LOAD": 46, "I32.STORE": 47,
    "I32.LOAD8_U": 48, "I32.LOAD8_S": 49,
    "I32.LOAD16_U": 50, "I32.LOAD16_S": 51,
    "I32.STORE8": 52, "I32.STORE16": 53,
    "CALL": 54, "RETURN": 55,
}


def program(*instrs) -> List[Instruction]:
    """Convenience: program(('PUSH', 3), ('PUSH', 5), ('ADD',), ('HALT',))"""
    result = []
    for instr in instrs:
        if isinstance(instr, Instruction):
            result.append(instr)
            continue
        name = instr[0].upper()
        arg = instr[1] if len(instr) > 1 else 0
        op = _NAME_TO_OP[name]
        result.append(Instruction(op, arg))
    return result


# ─── Math helpers (for programs.py) ──────────────────────────────

def _trunc_div(b, a):
    return int(b / a)

def _trunc_rem(b, a):
    return b - _trunc_div(b, a) * a

def _to_i32(val):
    return int(val) & MASK32

def _shr_u(b, a):
    return (_to_i32(b) >> (int(a) & 31))

def _shr_s(b, a):
    val = _to_i32(b)
    if val >= 0x80000000:
        val -= 0x100000000
    shift = int(a) & 31
    result = val >> shift
    return result & MASK32 if result < 0 else result

def _rotl32(b, a):
    val = _to_i32(b)
    shift = int(a) & 31
    return ((val << shift) | (val >> (32 - shift))) & MASK32 if shift else val

def _rotr32(b, a):
    val = _to_i32(b)
    shift = int(a) & 31
    return ((val >> shift) | (val << (32 - shift))) & MASK32 if shift else val

def _clz32(val):
    v = _to_i32(val)
    if v == 0: return 32
    n = 0
    if v <= 0x0000FFFF: n += 16; v <<= 16
    if v <= 0x00FFFFFF: n += 8;  v <<= 8
    if v <= 0x0FFFFFFF: n += 4;  v <<= 4
    if v <= 0x3FFFFFFF: n += 2;  v <<= 2
    if v <= 0x7FFFFFFF: n += 1
    return n

def _ctz32(val):
    v = _to_i32(val)
    if v == 0: return 32
    n = 0
    if (v & 0x0000FFFF) == 0: n += 16; v >>= 16
    if (v & 0x000000FF) == 0: n += 8;  v >>= 8
    if (v & 0x0000000F) == 0: n += 4;  v >>= 4
    if (v & 0x00000003) == 0: n += 2;  v >>= 2
    if (v & 0x00000001) == 0: n += 1
    return n

def _popcnt32(val):
    return bin(_to_i32(val)).count('1')
