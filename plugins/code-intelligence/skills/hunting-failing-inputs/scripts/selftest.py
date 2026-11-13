#!/usr/bin/env python3
"""Re-run every worked example and check the outcome each one documents.

    python3 scripts/selftest.py            # all languages whose tools exist
    python3 scripts/selftest.py python c   # a subset

Prints PASS, FAIL or SKIP per check. A check is skipped, never passed, when
its toolchain is missing. Exit 1 on any FAIL.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
EX = SKILL / 'examples'
PY = sys.executable
results: list[tuple[str, str, str]] = []


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def check(name: str, ok: bool, detail: str = '') -> None:
    results.append(('PASS' if ok else 'FAIL', name, '' if ok else detail[-600:]))


def skip(name: str, why: str) -> None:
    results.append(('SKIP', name, why))


def expect_solver(name: str, script: Path, sat: list[str], unsat: list[str] = ()) -> None:
    p = run([PY, str(script)])
    out = p.stdout
    bad = [s for s in sat if not re.search(re.escape(s) + r': sat\b', out)]
    bad += [s for s in unsat if not re.search(re.escape(s) + r': unsat\b', out)]
    check(name, p.returncode == 0 and not bad, f'missing {bad}\n{out}\n{p.stderr}')


def traps(name: str, path: Path, expected: int) -> None:
    p = run([PY, str(SKILL / 'scripts' / 'list_traps.py'), str(path)])
    m = re.search(r'# (\d+) trap', p.stderr)
    got = int(m.group(1)) if m else -1
    check(name, got == expected, f'expected {expected} traps, got {got}\n{p.stdout}{p.stderr}')


def python_ex() -> None:
    d = EX / 'python'
    traps('python: list_traps record.py', d / 'record.py', 7)
    expect_solver('python: model_record', d / 'model_record.py',
                  ['record.py:10 b[k:k+2]'], ['record.py:8 b[2:2+n]', 'record.py:9 b[2+n:2+n+m]'])
    expect_solver('python: model_lz', d / 'model_lz.py', ['L=2 record.py:24 out[len(out)-dist]'])
    try:
        import pytest  # noqa: F401
    except ImportError:
        return skip('python: reproducers', 'pytest not installed')
    p = run([PY, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', str(d / 'test_record.py')])
    check('python: reproducers', p.returncode == 0, p.stdout + p.stderr)


def js_ex() -> None:
    d = EX / 'javascript'
    traps('javascript: list_traps samples.mjs', d / 'samples.mjs', 6)
    expect_solver('javascript: model', d / 'model.py', ['samples.mjs:9 u8[p]', 'samples.mjs:9 u8[p + 1]'])
    if not shutil.which('node'):
        return skip('javascript: reproducers', 'node not installed')
    p = run(['node', '--test', str(d / 'samples.test.mjs')])
    check('javascript: reproducers', p.returncode == 0 and '# fail 0' in p.stdout, p.stdout + p.stderr)


def c_ex() -> None:
    d = EX / 'c'
    traps('c: list_traps frame.c', d / 'frame.c', 3)
    expect_solver('c: model', d / 'model.py', ['frame.c:11 memcpy(out, b+2+hdr, body)'])
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        return skip('c: reproducer', 'no C compiler')
    tmp = Path(tempfile.mkdtemp())
    p = run([cc, '-O1', '-g', str(d / 'frame.c'), str(d / 'repro.c'), '-o', str(tmp / 'plain')])
    if p.returncode:
        return check('c: plain build', False, p.stderr)
    p = run([str(tmp / 'plain')])
    check('c: plain build runs silently', p.returncode == 0 and '-> 191' in p.stdout, p.stdout + p.stderr)
    p = run([cc, '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
             str(d / 'frame.c'), str(d / 'repro.c'), '-o', str(tmp / 'asan')])
    if p.returncode:
        return skip('c: ASan reproducer', f'{cc} cannot link sanitizers: {p.stderr.strip()[:200]}')
    p = run([str(tmp / 'asan')])
    check('c: ASan reproducer', 'heap-buffer-overflow' in p.stderr and 'frame.c:11' in p.stderr, p.stderr)


def go_ex() -> None:
    d = EX / 'go'
    traps('go: list_traps parse.go (syntactic; the compiler keeps 4)', d / 'parse.go', 8)
    expect_solver('go: model_frame', d / 'model_frame.py',
                  ['parse.go:14 b[2:2+hdrLen]', 'parse.go:16 b[2+hdrLen:endBody]'])
    expect_solver('go: model_quoted', d / 'model_quoted.py', ['L=2 parse.go:33 s[1:i]'], ['L=2 parse.go:27 s[i]'])
    if not shutil.which('go'):
        return skip('go: reproducers', 'go not installed')
    p = run([PY, str(SKILL / 'scripts' / 'bce_targets.py'), str(d)])
    check('go: bce_targets', '# 4 surviving' in p.stderr, p.stdout + p.stderr)
    for t, line in (('parse14', 14), ('parse16', 16), ('parse33', 33)):
        p = run(['go', 'test', '-count=1', '-run', f'TestZ3_{t}$', '.'], cwd=d)
        trace = p.stdout + p.stderr
        check(f'go: TestZ3_{t} panics at parse.go:{line}',
              'panic: runtime error' in trace and f'parse.go:{line}' in trace, trace)


def wgsl_ex() -> None:
    d = EX / 'wgsl'
    traps('wgsl: list_traps gather.wgsl', d / 'gather.wgsl', 2)
    expect_solver('wgsl: model', d / 'model.py', ['gather.wgsl:11 src[offset + i*stride]'], ['gather.wgsl:11 dst[i]'])
    tmp = Path(tempfile.mkdtemp())
    (tmp / 'n.wgsl').write_text('@group(0) @binding(0) var<storage, read_write> a: array<u32>;\n'
                                '@group(0) @binding(1) var<storage, read> b: array<i32, 8>;\n'
                                'fn f(i: u32) { a[b[i]] = a[u32(b[i + 1u])]; }\n')
    p = run([PY, str(SKILL / 'scripts' / 'wgsl_guard.py'), str(tmp / 'n.wgsl'), str(tmp / 'o.wgsl')])
    out = (tmp / 'o.wgsl').read_text() if (tmp / 'o.wgsl').exists() else ''
    check('wgsl: wgsl_guard nested rewrite',
          p.returncode == 0 and 'a[_bc(u32(b[_bc(u32(i), u32(8), 1u)]), arrayLength(&a), 0u)]' in out
          and '@group(0) @binding(2) var<storage, read_write> _oob' in out, p.stdout + p.stderr + out)
    gpu = SKILL.parent / 'compiling-wgsl' / 'scripts' / 'harness' / 'gpu.mjs'
    if not (shutil.which('node') and gpu.exists()):
        return skip('wgsl: GPU reproducer', 'needs node and the compiling-wgsl skill alongside')
    if run(['node', '-e', "require('playwright')"]).returncode:
        return skip('wgsl: GPU reproducer', 'playwright not resolvable from node')
    p = run([PY, str(d / 'run.py')], timeout=600)
    check('wgsl: GPU reproducer', p.returncode == 0 and '_oob = [55, 2]' in p.stdout, p.stdout + p.stderr)


SUITES = {'python': python_ex, 'javascript': js_ex, 'c': c_ex, 'go': go_ex, 'wgsl': wgsl_ex}


def main() -> None:
    try:
        import z3  # noqa: F401
    except ImportError:
        sys.exit('z3 missing: python3 -m pip install z3-solver')
    for name in sys.argv[1:] or SUITES:
        if name not in SUITES:
            sys.exit(f'unknown suite {name}; choose from {", ".join(SUITES)}')
        SUITES[name]()
    for status, name, detail in results:
        print(f'{status}  {name}' + (f'\n      {detail}' if detail and status != 'PASS' else ''))
    fails = sum(r[0] == 'FAIL' for r in results)
    print(f'# {len(results)} checks, {fails} failed, {sum(r[0] == "SKIP" for r in results)} skipped')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
