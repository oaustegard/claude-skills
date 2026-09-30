#!/usr/bin/env python3
"""Compile tree-sitting's grammars from pinned upstream sources.

Produces libtree_sitter_<lang>.dylib on macOS (universal arm64 + x86_64) and
libtree_sitter_<lang>.so elsewhere. Needs git and a C compiler.

    build_grammars.py                 # all grammars -> ~/.cache/tree-sitting/parsers
    build_grammars.py --out DIR mojo  # selected grammars -> DIR

The release workflow runs this on macOS to produce the bundled parsers/*.dylib.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

# lang -> (repo, git ref, grammar subdirectory). Refs match the PyPI wheel
# versions the test suite passes against.
GRAMMARS = {
    'python': ('tree-sitter/tree-sitter-python', 'v0.25.0', '.'),
    'javascript': ('tree-sitter/tree-sitter-javascript', 'v0.25.0', '.'),
    'typescript': ('tree-sitter/tree-sitter-typescript', 'v0.23.2', 'typescript'),
    'tsx': ('tree-sitter/tree-sitter-typescript', 'v0.23.2', 'tsx'),
    'go': ('tree-sitter/tree-sitter-go', 'v0.25.0', '.'),
    'rust': ('tree-sitter/tree-sitter-rust', 'v0.24.2', '.'),
    'ruby': ('tree-sitter/tree-sitter-ruby', 'v0.23.1', '.'),
    'java': ('tree-sitter/tree-sitter-java', 'v0.23.5', '.'),
    'c': ('tree-sitter/tree-sitter-c', 'v0.24.2', '.'),
    'html': ('tree-sitter/tree-sitter-html', 'v0.23.2', '.'),
    'markdown': ('tree-sitter-grammars/tree-sitter-markdown', 'v0.5.1', 'tree-sitter-markdown'),
    'mojo': ('oaustegard/tree-sitter-mojo', '1fe537c4c0f93ea048d95fc9133fd3e0ef691482', '.'),
}


def _checkout(repo: str, ref: str, dest: Path) -> None:
    subprocess.run(['git', 'init', '-q', str(dest)], check=True)
    git = ['git', '-C', str(dest)]
    subprocess.run(git + ['remote', 'add', 'origin', f'https://github.com/{repo}'], check=True)
    subprocess.run(git + ['fetch', '-q', '--depth', '1', 'origin', ref], check=True)
    subprocess.run(git + ['checkout', '-q', 'FETCH_HEAD'], check=True)


def build(langs: list[str], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    mac = sys.platform == 'darwin'
    ext = '.dylib' if mac else '.so'
    arch = ['-arch', 'arm64', '-arch', 'x86_64'] if mac else []
    built = []
    with tempfile.TemporaryDirectory() as tmp:
        checkouts: dict[tuple[str, str], Path] = {}
        for lang in langs:
            repo, ref, sub = GRAMMARS[lang]
            key = (repo, ref)
            if key not in checkouts:
                checkouts[key] = Path(tmp) / f'{len(checkouts)}'
                _checkout(repo, ref, checkouts[key])
            src = checkouts[key] / sub / 'src'
            sources = [str(p) for p in (src / 'parser.c', src / 'scanner.c') if p.is_file()]
            target = out / f'libtree_sitter_{lang}{ext}'
            subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-std=c11', *arch,
                            '-I', str(src), *sources, '-o', str(target)], check=True)
            built.append(target)
            print(f'built {target}')
    return built


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('langs', nargs='*', metavar='LANG',
                    help=f'default: all ({", ".join(GRAMMARS)})')
    ap.add_argument('--out', type=Path,
                    default=Path.home() / '.cache' / 'tree-sitting' / 'parsers')
    args = ap.parse_args()
    unknown = set(args.langs) - set(GRAMMARS)
    if unknown:
        ap.error(f'unknown grammar: {", ".join(sorted(unknown))}')
    build(args.langs or list(GRAMMARS), args.out)


if __name__ == '__main__':
    main()
