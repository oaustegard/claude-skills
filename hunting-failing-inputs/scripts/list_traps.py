#!/usr/bin/env python3
"""List the operations in a source file that can fail on a bad input ("traps").

A trap is an operation with a precondition the input can violate: an index
that must be in range, a slice whose end must not pass the length, a divisor
that must be non-zero, an assert, a fixed-length decode, a memcpy length.

Each trap is printed with what happens when its precondition fails:
  raises  the runtime signals it (IndexError, RangeError, Go panic)
  silent  the program continues with a wrong value (Python slice truncation,
          JS undefined, WGSL clamped access, JS/WGSL division)
  UB      C undefined behaviour: silent unless built with sanitizers

usage: list_traps.py FILE [FILE ...] [--func NAME] [--lang LANG]
Output: file:line:col  kind  on-failure  func  source-line
Exit codes: 0 listed (possibly none), 2 bad input.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass

try:
    from tree_sitter_language_pack import get_parser
except ImportError:
    print('missing dependency: pip install tree-sitter-language-pack', file=sys.stderr)
    sys.exit(2)

EXT = {'.py': 'python', '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
       '.ts': 'typescript', '.c': 'c', '.h': 'c', '.wgsl': 'wgsl', '.go': 'go'}

FUNC_NODES = {
    'python': {'function_definition'},
    'javascript': {'function_declaration', 'method_definition', 'function_expression',
                   'arrow_function', 'function'},
    'typescript': {'function_declaration', 'method_definition', 'function_expression',
                   'arrow_function', 'function'},
    'c': {'function_definition'},
    'wgsl': {'function_declaration'},
    'go': {'function_declaration', 'method_declaration', 'func_literal'},
}

DATAVIEW = re.compile(r'^(get|set)(Int|Uint|Float|BigInt|BigUint)\d+$')
C_LEN_CALLS = {'memcpy', 'memmove', 'memset', 'strncpy', 'strncat', 'memcmp', 'read', 'fread'}
PY_DECODE = {'unpack', 'unpack_from', 'from_bytes', 'decode'}


@dataclass
class Trap:
    line: int
    col: int
    kind: str
    on_fail: str
    func: str


def text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode('utf-8', 'replace')


def func_name(node, src: bytes, lang: str) -> str:
    """Best-effort name of the function node."""
    name = node.child_by_field_name('name')
    if name is not None:
        return text(name, src)
    if lang == 'c':
        d = node.child_by_field_name('declarator')
        while d is not None and d.type not in ('identifier', 'field_identifier'):
            d = d.child_by_field_name('declarator')
        if d is not None:
            return text(d, src)
    parent = node.parent
    if parent is not None and parent.type in ('variable_declarator', 'pair', 'assignment_expression'):
        key = parent.child_by_field_name('name') or parent.child_by_field_name('key') \
            or parent.child_by_field_name('left')
        if key is not None:
            return text(key, src)
    return '<anon>'


def classify(node, src: bytes, lang: str) -> tuple[str, str] | None:
    """Return (kind, on_fail) for a trap node, or None."""
    t = node.type
    if lang == 'python':
        if t == 'subscript':
            if any(c.type == 'slice' for c in node.children):
                return 'slice', 'silent'      # past-the-end slices truncate
            return 'index', 'raises'          # negative indices also wrap silently
        if t == 'binary_operator':
            op = node.child_by_field_name('operator')
            if op is not None and text(op, src) in ('/', '//', '%'):
                return 'divide', 'raises'
        if t == 'assert_statement':
            return 'assert', 'raises'
        if t == 'call':
            fn = node.child_by_field_name('function')
            if fn is not None and fn.type == 'attribute':
                attr = fn.child_by_field_name('attribute')
                if attr is not None and text(attr, src) in PY_DECODE:
                    return 'decode', 'raises'
    elif lang in ('javascript', 'typescript'):
        if t == 'subscript_expression':
            idx = node.child_by_field_name('index')
            if idx is not None and idx.type in ('string', 'template_string'):
                return None                   # property access, not an index
            return 'index', 'silent'          # undefined on read, dropped write on typed arrays
        if t == 'binary_expression':
            op = node.child_by_field_name('operator')
            if op is not None and text(op, src) in ('/', '%'):
                return 'divide', 'silent'     # Infinity / NaN
        if t == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None and fn.type == 'member_expression':
                prop = fn.child_by_field_name('property')
                p = text(prop, src) if prop is not None else ''
                if DATAVIEW.match(p):
                    return 'dataview', 'raises'
                if p in ('slice', 'subarray'):
                    return 'slice', 'silent'  # clamps to length
        if t == 'throw_statement':
            return 'throw', 'raises'
    elif lang == 'c':
        if t == 'subscript_expression':
            return 'index', 'UB'
        if t == 'pointer_expression' and text(node, src).startswith('*'):
            arg = node.child_by_field_name('argument')
            if arg is not None and arg.type in ('binary_expression', 'parenthesized_expression'):
                return 'deref', 'UB'
        if t == 'binary_expression':
            op = node.child_by_field_name('operator')
            o = text(op, src) if op is not None else ''
            if o in ('/', '%'):
                return 'divide', 'UB'
            if o in ('<<', '>>'):
                return 'shift', 'UB'          # shift by >= width
        if t == 'call_expression':
            fn = node.child_by_field_name('function')
            if fn is not None and text(fn, src) in C_LEN_CALLS:
                return 'length', 'UB'
            if fn is not None and text(fn, src) == 'assert':
                return 'assert', 'raises'
    elif lang == 'wgsl':
        if t == 'subscript_expression':
            return 'index', 'silent'          # robust access: clamped or zero, writes may drop
        if t == 'lhs_expression' and node.named_child_count >= 2:
            post = node.named_children[1]     # dst[i] = ... (assignment target)
            if post.type == 'postfix_expression' and post.child_count \
                    and text(post.children[0], src) == '[':
                return 'index', 'silent'
        if t == 'binary_expression':
            ops = [c for c in node.children if not c.is_named]
            o = text(ops[0], src) if ops else ''
            if o in ('/', '%'):
                return 'divide', 'silent'     # integer x/0 is defined to return x
            if o in ('<<', '>>'):
                return 'shift', 'silent'      # shift amount is masked
    elif lang == 'go':
        if t == 'index_expression':
            return 'index', 'raises'
        if t == 'slice_expression':
            return 'slice', 'raises'          # checked against cap, not len
        if t == 'binary_expression':
            op = node.child_by_field_name('operator')
            if op is not None and text(op, src) in ('/', '%'):
                return 'divide', 'raises'
    return None


def scan(path: str, lang: str, only_func: str | None) -> list[Trap]:
    src = open(path, 'rb').read()
    tree = get_parser(lang).parse(src)
    fnodes = FUNC_NODES[lang]
    out: list[Trap] = []

    def walk(node, fname: str) -> None:
        if node.type in fnodes:
            fname = func_name(node, src, lang)
        hit = classify(node, src, lang)
        if hit and (only_func is None or fname == only_func):
            out.append(Trap(node.start_point[0] + 1, node.start_point[1] + 1, hit[0], hit[1], fname))
        for c in node.children:
            walk(c, fname)

    walk(tree.root_node, '-')
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--func', default=None, help='only traps inside this function')
    ap.add_argument('--lang', default=None, choices=sorted(set(EXT.values())))
    a = ap.parse_args()
    total, bad = 0, False
    for path in a.files:
        lang = a.lang or EXT.get(os.path.splitext(path)[1])
        if lang is None:
            print(f'{path}: unknown language, pass --lang', file=sys.stderr)
            bad = True
            continue
        try:
            lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
            traps = scan(path, lang, a.func)
        except OSError as e:
            print(f'{path}: {e}', file=sys.stderr)
            bad = True
            continue
        for t in traps:
            print(f'{path}:{t.line}:{t.col}\t{t.kind}\t{t.on_fail}\t{t.func}\t{lines[t.line - 1].strip()}')
        total += len(traps)
    print(f'# {total} trap(s)', file=sys.stderr)
    sys.exit(2 if bad and total == 0 else 0)


if __name__ == '__main__':
    main()
