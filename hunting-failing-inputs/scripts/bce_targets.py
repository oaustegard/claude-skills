#!/usr/bin/env python3
"""List the bounds checks the Go compiler could NOT eliminate, with source.

Each surviving check is a place the program can panic with
"index out of range" or "slice bounds out of range". Checks the compiler
removed are already proven safe by its prove pass and need no model.

usage: bce_targets.py [--goarch riscv64] [--func NAME] PKG_DIR [PKG_PATTERN]
  PKG_DIR      module directory to build in (cwd for `go build`)
  PKG_PATTERN  package pattern, default ./...
  --func NAME  keep only checks inside func NAME (matched by source scan)

Exit codes: 0 targets printed (possibly none), 2 build failed.
"""
import argparse, os, re, subprocess, sys

LINE = re.compile(r'^(\S+\.go):(\d+):(\d+): Found (Is\w+)$')
FUNC = re.compile(r'^func\s+(?:\([^)]*\)\s*)?(\w+)')

def enclosing_funcs(path):
    """Map line number -> name of the top-level func that contains it."""
    out, cur = {}, None
    try:
        with open(path) as f:
            for n, text in enumerate(f, 1):
                m = FUNC.match(text)
                if m:
                    cur = m.group(1)
                elif text.startswith('}'):
                    out[n] = cur
                    cur = None
                    continue
                out[n] = cur
    except OSError:
        pass
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg_dir')
    ap.add_argument('pattern', nargs='?', default='./...')
    ap.add_argument('--goarch', default=None)
    ap.add_argument('--func', dest='func', default=None)
    a = ap.parse_args()

    if not os.path.isdir(a.pkg_dir):
        print(f'not a directory: {a.pkg_dir}', file=sys.stderr)
        sys.exit(2)
    env = dict(os.environ)
    if a.goarch:
        env.update(GOOS='linux', GOARCH=a.goarch)
    # The go command replays cached compiler output, so a cached build still
    # prints its checks (checked on go1.24.7).
    cmd = ['go', 'build', '-o', os.devnull,
           '-gcflags=-d=ssa/check_bce/debug=1', a.pattern]
    p = subprocess.run(cmd, cwd=a.pkg_dir, env=env, capture_output=True, text=True)
    hits, other = [], []
    for raw in p.stderr.splitlines():
        m = LINE.match(raw.strip())
        if m:
            hits.append(m.groups())
        elif raw.strip() and not raw.startswith('#'):
            other.append(raw)
    if p.returncode != 0:
        print('build failed:\n' + '\n'.join(other), file=sys.stderr)
        if not hits:
            sys.exit(2)
        print('# partial: listing checks from packages that compiled',
              file=sys.stderr)

    cache, srcs, shown = {}, {}, 0
    for path, line, col, kind in hits:
        full = os.path.join(a.pkg_dir, path)
        if full not in cache:
            cache[full] = enclosing_funcs(full)
            try:
                srcs[full] = open(full).read().splitlines()
            except OSError:
                srcs[full] = []
        fn = cache[full].get(int(line))
        if a.func and fn != a.func:
            continue
        text = srcs[full][int(line) - 1].strip() if srcs[full] else ''
        kind = {'IsInBounds': 'index', 'IsSliceInBounds': 'slice'}.get(kind, kind)
        print(f'{path}:{line}:{col}\t{kind}\t{fn or "?"}\t{text}')
        shown += 1
    print(f'# {shown} surviving bounds check(s)', file=sys.stderr)

if __name__ == '__main__':
    main()
