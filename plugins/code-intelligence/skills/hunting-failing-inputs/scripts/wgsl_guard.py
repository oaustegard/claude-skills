#!/usr/bin/env python3
"""Instrument a WGSL compute shader so out-of-range array indexing is recorded.

WebGPU never faults on a bad index. A read past the end returns some value
inside the buffer (or zero) and a write may be dropped, depending on the
implementation. This rewrite wraps every index into a module-scope array as

    a[_bc(u32(i), <length>, <site>)]

where _bc returns i unchanged and, when i >= length, adds 1 to _oob[0] and
records the largest site number + 1 in _oob[1]. A negative i32 index becomes a
huge u32 and is caught too. The pass adds one binding:

    @group(G) @binding(B) var<storage, read_write> _oob: array<atomic<u32>, 2>;

Bind an 8-byte zeroed buffer there, run the kernel, read it back:
_oob[0] == 0 means no out-of-range index on that input.

usage: wgsl_guard.py IN.wgsl OUT.wgsl [--group G] [--binding B]
Prints the site table (site, line, array, index) to stdout.
Compute shaders only: vertex stages cannot write storage buffers.
Exit codes: 0 ok, 2 bad input or nothing to instrument.
"""
from __future__ import annotations

import argparse
import re
import sys

try:
    from tree_sitter_language_pack import get_parser
except ImportError:
    print('missing dependency: pip install tree-sitter-language-pack', file=sys.stderr)
    sys.exit(2)

HELPER = """
@group({g}) @binding({b}) var<storage, read_write> _oob: array<atomic<u32>, 2>;
fn _bc(i: u32, n: u32, site: u32) -> u32 {{
  if (i >= n) {{ atomicAdd(&_oob[0], 1u); atomicMax(&_oob[1], site + 1u); }}
  return i;
}}
"""

VAR = re.compile(
    r'var\s*(?:<\s*(\w+)[^>]*>)?\s+(\w+)\s*:\s*array\s*<\s*(.+?)\s*>\s*;', re.S)


def array_lengths(src: str) -> dict[str, str]:
    """Module-scope array variables -> WGSL expression for their length."""
    out = {}
    for m in VAR.finditer(src):
        space, name, inner = m.group(1), m.group(2), m.group(3)
        # inner is "T" (runtime-sized) or "T, N"; T itself may contain commas
        depth, split = 0, None
        for k, ch in enumerate(inner):
            depth += ch == '<'
            depth -= ch == '>'
            if ch == ',' and depth == 0:
                split = k
        if split is None:
            if space == 'storage':
                out[name] = f'arrayLength(&{name})'
        else:
            out[name] = f'u32({inner[split + 1:].strip()})'
    return out


def used_bindings(src: str) -> tuple[int, int]:
    """(group, next free binding in group 0)."""
    pairs = [(int(g), int(b)) for g, b in
             re.findall(r'@group\(\s*(\d+)\s*\)\s*@binding\(\s*(\d+)\s*\)', src)]
    in0 = [b for g, b in pairs if g == 0]
    return 0, (max(in0) + 1 if in0 else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--group', type=int, default=None)
    ap.add_argument('--binding', type=int, default=None)
    a = ap.parse_args()

    text = open(a.src, encoding='utf-8').read()
    if '_oob' in text or '_bc(' in text:
        print('input already uses _oob/_bc: instrumented twice?', file=sys.stderr)
        sys.exit(2)
    lengths = array_lengths(text)
    if not lengths:
        print('no module-scope array variables found', file=sys.stderr)
        sys.exit(2)
    g0, b0 = used_bindings(text)
    g = a.group if a.group is not None else g0
    b = a.binding if a.binding is not None else b0

    data = text.encode()
    tree = get_parser('wgsl').parse(data)
    if tree.root_node.has_error:
        print('WGSL did not parse cleanly; fix the shader first', file=sys.stderr)
        sys.exit(2)
    sites: list[tuple[int, int, str, str]] = []
    targets: dict[int, tuple[int, str]] = {}   # index node id -> (site, array name)

    def node_text(n) -> str:
        return data[n.start_byte:n.end_byte].decode()

    def mark(idx, name: str, at) -> None:
        site = len(sites)
        sites.append((site, at.start_point[0] + 1, name, node_text(idx)))
        targets[idx.id] = (site, name)

    def collect(node) -> None:
        """Find index expressions into guarded arrays: reads and assignment targets."""
        if node.type == 'subscript_expression' and node.named_child_count >= 2:
            obj, idx = node.named_children[0], node.named_children[-1]
            if obj.type == 'identifier' and node_text(obj) in lengths:
                mark(idx, node_text(obj), node)
        elif node.type == 'lhs_expression' and node.named_child_count >= 2:
            # dst[i] = ... parses as lhs_expression(identifier, postfix_expression('[' i ']' ...))
            obj, post = node.named_children[0], node.named_children[1]
            if (obj.type == 'identifier' and node_text(obj) in lengths
                    and post.type == 'postfix_expression' and post.child_count
                    and node_text(post.children[0]) == '[' and post.named_child_count):
                mark(post.named_children[0], node_text(obj), node)
        for c in node.children:
            collect(c)

    def render(node) -> str:
        """Source of node with every guarded index wrapped (handles a[b[i]])."""
        if node.child_count == 0:
            body = node_text(node)
        else:
            parts, pos = [], node.start_byte
            for c in node.children:
                parts.append(data[pos:c.start_byte].decode())
                parts.append(render(c))
                pos = c.end_byte
            parts.append(data[pos:node.end_byte].decode())
            body = ''.join(parts)
        if node.id in targets:
            site, name = targets[node.id]
            body = f'_bc(u32({body}), {lengths[name]}, {site}u)'
        return body

    collect(tree.root_node)
    rendered = data[:tree.root_node.start_byte].decode() + render(tree.root_node) \
        + data[tree.root_node.end_byte:].decode()
    if not sites:
        print('no indexing into module-scope arrays found', file=sys.stderr)
        sys.exit(2)

    out = rendered + HELPER.format(g=g, b=b)
    open(a.dst, 'w', encoding='utf-8').write(out)
    print(f'# _oob at @group({g}) @binding({b}); {len(sites)} site(s)')
    for site, line, name, itext in sites:
        print(f'{site}\t{a.src}:{line}\t{name}[{itext}]')


if __name__ == '__main__':
    main()
