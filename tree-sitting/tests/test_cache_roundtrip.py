"""Tests for cache roundtrip equivalence: fresh parse vs cache hit.

This tests the core cache invariant: query results must be byte-identical
whether served from a fresh parse or a cache hit.

Run: python -m pytest tests/test_cache_roundtrip.py -v
Or:  python tests/test_cache_roundtrip.py  (standalone)
"""

import sys
import os
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Bootstrap parsers before importing engine
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from engine import (
    CodeCache, Symbol, FileEntry, _get_parser,
)

# These are not yet implemented; tests will fail trying to use them.
# They're listed here for reference of what contract they must fulfill.
try:
    from engine import CACHE_FORMAT_VERSION, cache_path_for
except ImportError:
    CACHE_FORMAT_VERSION = None
    cache_path_for = None


# ── Helpers ──────────────────────────────────────────────────────────────

def create_fixture_repo(tmpdir: str) -> str:
    """Create a multi-language fixture repo for testing.

    Returns the root path.
    """
    root = Path(tmpdir)

    # Python files
    (root / 'py_module.py').write_text('''
class UserManager:
    """Manages users."""
    def find_by_id(self, user_id: int):
        """Find a user by ID."""
        return None
    def create_user(self, name: str):
        pass

def process_data(items):
    """Process data items."""
    return []
''')

    (root / 'utils.py').write_text('''
import os
import sys
from pathlib import Path

def read_config():
    return {}

class Config:
    def __init__(self):
        self.debug = False
''')

    # JavaScript/TypeScript files
    (root / 'app.js').write_text('''
/** Main application. */
class App {
    /** Initialize the app. */
    init(config) {
        this.config = config;
    }

    /** Start the server. */
    start() {
        console.log('Starting...');
    }
}

function createApp(name) {
    return new App();
}

const shutdown = async () => {};
''')

    (root / 'types.ts').write_text('''
interface User {
    id: number;
    name: string;
}

interface Config {
    debug: boolean;
    port: number;
}

function createUser(name: string): User {
    return { id: 1, name };
}

export const DEFAULT_CONFIG: Config = {
    debug: false,
    port: 3000,
};
''')

    # C file
    (root / 'utils.c').write_text('''
#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

typedef struct {
    int x;
    int y;
} Point;

enum Color { RED, GREEN, BLUE };
''')

    # Create a subdirectory with more files
    sub = root / 'src'
    sub.mkdir()

    (sub / 'core.py').write_text('''
class Engine:
    def __init__(self):
        self.state = None

    def run(self):
        """Run the engine."""
        pass

    def stop(self):
        pass
''')

    # Markdown file
    (root / 'README.md').write_text('''
# My Project

## Overview

This is a test project.

### Features

- Feature 1
- Feature 2

## Usage

See below.
''')

    return str(root)


# ── Test: Cache Roundtrip Equivalence ────────────────────────────────────

def test_cache_roundtrip_fresh_then_hit():
    """Verify cache hit returns identical results to fresh parse.

    1. Scan fresh repo with use_cache=True (writes cache)
    2. Create new CodeCache, scan same repo (should hit cache)
    3. Assert all query outputs are identical
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        # ── Fresh scan (writes cache) ──
        cache_fresh = CodeCache()
        stats_fresh = cache_fresh.scan(repo_root, use_cache=True)

        assert 'loaded_from_cache' in stats_fresh, \
            "scan() must return 'loaded_from_cache' key"
        assert stats_fresh['loaded_from_cache'] is False, \
            "First scan should not load from cache"
        assert stats_fresh['files'] > 0, "Fixture should have files"

        # Capture fresh results from all query functions
        fresh_results = {
            'tree_overview': cache_fresh.tree_overview(),
            'dir_overview': cache_fresh.dir_overview(''),
            'find_symbol_create': cache_fresh.find_symbol('create*'),
            'find_symbol_exact': cache_fresh.find_symbol('UserManager'),
            'file_symbols_py': cache_fresh.file_symbols('py_module.py'),
            'file_imports_utils': cache_fresh.file_imports('utils.py'),
            'references_Config': cache_fresh.references('Config'),
            'get_source_range': cache_fresh.get_source_range('utils.py', 6, 8),
        }

        # Verify fresh results are non-empty/valid
        assert fresh_results['tree_overview'], "tree_overview should return content"
        assert fresh_results['dir_overview'], "dir_overview should return content"
        assert len(fresh_results['find_symbol_create']) > 0, \
            "Should find symbols matching 'create*'"
        assert len(fresh_results['find_symbol_exact']) > 0, \
            "Should find exact symbol 'UserManager'"

        # ── Cache hit scan ──
        cache_hit = CodeCache()
        stats_hit = cache_hit.scan(repo_root, use_cache=True)

        assert stats_hit['loaded_from_cache'] is True, \
            "Second scan should load from cache"

        # Capture results from cache hit
        hit_results = {
            'tree_overview': cache_hit.tree_overview(),
            'dir_overview': cache_hit.dir_overview(''),
            'find_symbol_create': cache_hit.find_symbol('create*'),
            'find_symbol_exact': cache_hit.find_symbol('UserManager'),
            'file_symbols_py': cache_hit.file_symbols('py_module.py'),
            'file_imports_utils': cache_hit.file_imports('utils.py'),
            'references_Config': cache_hit.references('Config'),
            'get_source_range': cache_hit.get_source_range('utils.py', 6, 8),
        }

        # ── Equivalence: all results must be identical ──
        assert fresh_results['tree_overview'] == hit_results['tree_overview'], \
            "tree_overview must return identical results"
        assert fresh_results['dir_overview'] == hit_results['dir_overview'], \
            "dir_overview must return identical results"

        # find_symbol results: compare by symbol names and properties
        fresh_names = {s.name for s in fresh_results['find_symbol_create']}
        hit_names = {s.name for s in hit_results['find_symbol_create']}
        assert fresh_names == hit_names, \
            "find_symbol('create*') must return same symbol names"

        fresh_exact = fresh_results['find_symbol_exact']
        hit_exact = hit_results['find_symbol_exact']
        assert len(fresh_exact) == len(hit_exact), \
            "find_symbol exact match must return same count"
        if fresh_exact:
            s_fresh = fresh_exact[0]
            s_hit = hit_exact[0]
            assert s_fresh.name == s_hit.name, "Symbol names must match"
            assert s_fresh.kind == s_hit.kind, "Symbol kinds must match"
            assert s_fresh.file == s_hit.file, "Symbol files must match"
            assert s_fresh.line == s_hit.line, "Symbol lines must match"

        # file_symbols comparison
        fresh_file_syms = fresh_results['file_symbols_py']
        hit_file_syms = hit_results['file_symbols_py']
        assert len(fresh_file_syms) == len(hit_file_syms), \
            "file_symbols must return same count"
        for fs, hs in zip(fresh_file_syms, hit_file_syms):
            assert fs.name == hs.name, "file_symbols names must match"
            assert fs.kind == hs.kind, "file_symbols kinds must match"

        # file_imports comparison
        fresh_imps = fresh_results['file_imports_utils']
        hit_imps = hit_results['file_imports_utils']
        assert fresh_imps == hit_imps, \
            "file_imports must return identical list"

        # references comparison
        fresh_refs = fresh_results['references_Config']
        hit_refs = hit_results['references_Config']
        assert len(fresh_refs) == len(hit_refs), \
            "references must return same count"
        assert fresh_refs == hit_refs, \
            "references must return identical results"

        # get_source_range comparison
        assert fresh_results['get_source_range'] == hit_results['get_source_range'], \
            "get_source_range must return identical source"

    finally:
        shutil.rmtree(tmpdir)


def test_cache_no_parsing_on_hit():
    """Verify parser factory is NOT called on cache hit.

    Monkeypatch _get_parser to track calls:
    - Fresh scan: _get_parser MUST be called
    - Cache hit scan: _get_parser MUST NOT be called
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        # ── Fresh scan with spy ──
        parse_call_count_fresh = 0
        original_get_parser = None

        def spy_get_parser(lang):
            nonlocal parse_call_count_fresh
            parse_call_count_fresh += 1
            return original_get_parser(lang)

        # Fresh scan
        original_get_parser = _get_parser.__wrapped__ if hasattr(_get_parser, '__wrapped__') else _get_parser
        with patch('engine._get_parser', side_effect=spy_get_parser) as mock_parser:
            cache_fresh = CodeCache()
            stats_fresh = cache_fresh.scan(repo_root, use_cache=True)
            fresh_parse_calls = mock_parser.call_count

        assert stats_fresh['loaded_from_cache'] is False
        assert fresh_parse_calls > 0, \
            "Fresh scan should call _get_parser for language detection"

        # ── Cache hit with spy ──
        parse_call_count_hit = 0

        def spy_get_parser_hit(lang):
            nonlocal parse_call_count_hit
            parse_call_count_hit += 1
            return original_get_parser(lang)

        with patch('engine._get_parser', side_effect=spy_get_parser_hit) as mock_parser_hit:
            cache_hit = CodeCache()
            stats_hit = cache_hit.scan(repo_root, use_cache=True)
            hit_parse_calls = mock_parser_hit.call_count

        assert stats_hit['loaded_from_cache'] is True, \
            "Second scan should load from cache"

        # On cache hit, _get_parser should NOT be called at all
        # (the cache contains already-extracted symbols, no parsing needed)
        assert hit_parse_calls == 0, \
            f"Cache hit should not call _get_parser, but got {hit_parse_calls} calls"

    finally:
        shutil.rmtree(tmpdir)


def test_cache_use_cache_false():
    """Verify use_cache=False never reads or writes cache.

    Scan with use_cache=False twice:
    - Both scans return loaded_from_cache=False
    - Results still correct
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        # First scan with use_cache=False
        cache1 = CodeCache()
        stats1 = cache1.scan(repo_root, use_cache=False)

        assert stats1['loaded_from_cache'] is False, \
            "use_cache=False should never load from cache"
        assert stats1['files'] > 0, "Should parse files"

        results1 = {
            'tree_overview': cache1.tree_overview(),
            'symbols': cache1.find_symbol('create*'),
        }

        # Second scan with use_cache=False
        cache2 = CodeCache()
        stats2 = cache2.scan(repo_root, use_cache=False)

        assert stats2['loaded_from_cache'] is False, \
            "use_cache=False should never load from cache"

        results2 = {
            'tree_overview': cache2.tree_overview(),
            'symbols': cache2.find_symbol('create*'),
        }

        # Results should still be identical
        assert results1['tree_overview'] == results2['tree_overview']
        assert len(results1['symbols']) == len(results2['symbols'])

    finally:
        shutil.rmtree(tmpdir)


def test_cache_rebuild_cache_flag():
    """Verify rebuild_cache=True forces fresh parse and overwrites cache.

    Scan with rebuild_cache=True should:
    - Return loaded_from_cache=False
    - Parse fresh
    - Overwrite the cache file
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        # Initial scan
        cache1 = CodeCache()
        stats1 = cache1.scan(repo_root, use_cache=True)
        assert stats1['loaded_from_cache'] is False

        results1 = cache1.find_symbol('UserManager')

        # Rebuild cache
        cache2 = CodeCache()
        stats2 = cache2.scan(repo_root, use_cache=True, rebuild_cache=True)

        assert stats2['loaded_from_cache'] is False, \
            "rebuild_cache=True should parse fresh, not load"

        results2 = cache2.find_symbol('UserManager')

        # Results should match
        assert len(results1) == len(results2), \
            "rebuild_cache should produce same results as original parse"
        if results1:
            assert results1[0].name == results2[0].name

    finally:
        shutil.rmtree(tmpdir)


def test_cache_format_version_defined():
    """Verify CACHE_FORMAT_VERSION constant exists and is an int."""
    assert hasattr(__import__('engine'), 'CACHE_FORMAT_VERSION'), \
        "engine.CACHE_FORMAT_VERSION must be defined"
    version = __import__('engine').CACHE_FORMAT_VERSION
    assert isinstance(version, int), \
        f"CACHE_FORMAT_VERSION must be int, got {type(version)}"


def test_cache_path_for_function():
    """Verify cache_path_for() function exists and returns Path.

    Should:
    - Return a pathlib.Path
    - Be deterministic (same root -> same path)
    - Honor TREESIT_CACHE_DIR env var if set
    """
    assert hasattr(__import__('engine'), 'cache_path_for'), \
        "engine.cache_path_for must be defined"

    # Test determinism
    root = '/some/project/root'
    path1 = cache_path_for(root)
    path2 = cache_path_for(root)

    assert isinstance(path1, Path), "cache_path_for must return pathlib.Path"
    assert path1 == path2, "cache_path_for must be deterministic"


def test_cache_fingerprint_method():
    """Verify CodeCache._fingerprint() method exists and works.

    Should:
    - Return a string
    - Be stable across rescans of unchanged tree
    - Change on file add/remove/modify
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        cache = CodeCache()

        assert hasattr(cache, '_fingerprint'), \
            "CodeCache must have _fingerprint method"

        # Get fingerprint before any changes
        fp1 = cache._fingerprint(repo_root, skip=None)
        assert isinstance(fp1, str), "_fingerprint must return string"
        assert len(fp1) > 0, "_fingerprint must return non-empty string"

        # Get fingerprint again (should be identical)
        fp2 = cache._fingerprint(repo_root, skip=None)
        assert fp1 == fp2, "_fingerprint must be stable for unchanged tree"

        # Modify a file
        mod_file = Path(repo_root) / 'utils.py'
        mod_file.write_text(mod_file.read_text() + '\n# comment')

        # Fingerprint should change
        fp3 = cache._fingerprint(repo_root, skip=None)
        assert fp3 != fp1, "_fingerprint must change when file is modified"

        # Add a file
        new_file = Path(repo_root) / 'new.py'
        new_file.write_text('# new file')

        fp4 = cache._fingerprint(repo_root, skip=None)
        assert fp4 != fp3, "_fingerprint must change when file is added"

    finally:
        shutil.rmtree(tmpdir)


def test_cache_file_entry_lazy_source():
    """Verify lazy source loading: tree=None and source=None on cache hit.

    After cache hit, FileEntry should have:
    - tree: None (not loaded)
    - source: None (not loaded)
    - symbols: populated from cache
    - But get_source_range() still works by lazily reading disk
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        # Fresh scan
        cache_fresh = CodeCache()
        cache_fresh.scan(repo_root, use_cache=True)

        fresh_entry = cache_fresh.files.get('utils.py')
        assert fresh_entry is not None
        assert fresh_entry.source is not None, "Fresh parse should have source"
        assert fresh_entry.tree is not None, "Fresh parse should have tree"

        # Cache hit
        cache_hit = CodeCache()
        cache_hit.scan(repo_root, use_cache=True)

        hit_entry = cache_hit.files.get('utils.py')
        assert hit_entry is not None

        # On cache hit, tree and source should be None (lazy loaded)
        if cache_hit.root:  # Only check if cache was actually loaded
            assert hit_entry.tree is None, \
                "Cache hit should not load tree (lazy loading)"
            assert hit_entry.source is None, \
                "Cache hit should not load source (lazy loading)"

            # But symbols should be populated
            assert len(hit_entry.symbols) > 0, \
                "Cache hit should populate symbols"

            # And get_source_range() should still work (lazy loading)
            source = cache_hit.get_source_range('utils.py', 6, 8)
            assert 'read_config' in source or 'return {}' in source, \
                "get_source_range should work with lazy source loading"

    finally:
        shutil.rmtree(tmpdir)


def test_cache_symbol_children_roundtrip():
    """Verify Symbol.to_dict(include_children=True) roundtrips correctly.

    Cache stores symbols via to_dict(), must deserialize children properly.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        repo_root = create_fixture_repo(tmpdir)

        # Fresh scan
        cache_fresh = CodeCache()
        cache_fresh.scan(repo_root, use_cache=True)

        # Find a symbol with children (class)
        user_mgr = cache_fresh.find_symbol('UserManager')
        assert len(user_mgr) > 0

        fresh_sym = user_mgr[0]
        assert fresh_sym.kind == 'class'
        fresh_children_names = {c.name for c in fresh_sym.children}

        # Cache hit
        cache_hit = CodeCache()
        cache_hit.scan(repo_root, use_cache=True)

        user_mgr_hit = cache_hit.find_symbol('UserManager')
        assert len(user_mgr_hit) > 0

        hit_sym = user_mgr_hit[0]
        hit_children_names = {c.name for c in hit_sym.children}

        # Children must match
        assert fresh_children_names == hit_children_names, \
            "Symbol children must roundtrip correctly through cache"

    finally:
        shutil.rmtree(tmpdir)


# ── Standalone runner ────────────────────────────────────────────────────

if __name__ == '__main__':
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
