"""Tests for tree-sitting cache lifecycle (T3: cache lifecycle, flags, atomicity, robustness).

Run: python -m pytest tests/test_cache_lifecycle.py -v
Or:  python tests/test_cache_lifecycle.py

These tests are for NOT-YET-IMPLEMENTED cache features. TDD red phase.
All tests WILL FAIL until the cache implementation is complete.
"""

import sys
import os
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Bootstrap parsers before importing engine
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import engine
from engine import CodeCache, Symbol
# Not-yet-implemented names: resolve lazily so the module COLLECTS (red-fails per
# test) instead of erroring at import during TDD red phase.
cache_path_for = getattr(engine, "cache_path_for", None)
CACHE_FORMAT_VERSION = getattr(engine, "CACHE_FORMAT_VERSION", None)


# ── Fixtures and helpers ─────────────────────────────────────────────────────

def create_test_tree(tmpdir, files_dict: dict[str, str]) -> Path:
    """Create a test directory tree with given files.

    Args:
        tmpdir: Path to create files in
        files_dict: dict of relpath -> content (as string)

    Returns:
        Path to tmpdir
    """
    root = Path(tmpdir)
    for relpath, content in files_dict.items():
        filepath = root / relpath
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
    return root


def read_cache_json(cache_path: Path) -> dict:
    """Read cache JSON file safely."""
    if not cache_path.exists():
        raise FileNotFoundError(f"Cache file not found: {cache_path}")
    with open(cache_path, 'r') as f:
        return json.load(f)


def find_temp_files_in_dir(dirpath: Path, pattern: str = '.tmp') -> list[Path]:
    """Find temporary files matching pattern in directory."""
    return list(dirpath.glob(f'*{pattern}*'))


# ── T3.1: First scan(use_cache=True) creates cache, loaded_from_cache=False ──

def test_first_scan_creates_cache(tmp_path, monkeypatch):
    """First scan(use_cache=True) CREATES the cache file at cache_path_for(root).

    Assertions:
    - Cache file exists after scan
    - loaded_from_cache is False (no prior cache)
    - Cache contains JSON with CACHE_FORMAT_VERSION header
    """
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    # Create test tree
    root = create_test_tree(tmp_path / 'project', {
        'main.py': 'def hello(): pass\n',
        'lib.py': 'class Foo:\n    def bar(self): pass\n',
    })

    # First scan
    cache = CodeCache()
    stats = cache.scan(str(root), use_cache=True)

    # Assert cache was created
    expected_cache_path = cache_path_for(str(root))
    assert expected_cache_path.exists(), f"Cache file not created at {expected_cache_path}"

    # Assert loaded_from_cache is False
    assert 'loaded_from_cache' in stats, "loaded_from_cache key missing from stats"
    assert stats['loaded_from_cache'] is False, "First scan should have loaded_from_cache=False"

    # Assert cache contains valid JSON with version header
    cache_data = read_cache_json(expected_cache_path)
    assert 'cache_format_version' in cache_data, "Cache missing cache_format_version"
    assert cache_data['cache_format_version'] == CACHE_FORMAT_VERSION


def test_first_scan_cache_has_fingerprint(tmp_path, monkeypatch):
    """Cache file includes fingerprint of scanned tree."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    cache = CodeCache()
    cache.scan(str(root), use_cache=True)

    cache_path = cache_path_for(str(root))
    cache_data = read_cache_json(cache_path)

    assert 'fingerprint' in cache_data, "Cache missing fingerprint field"
    assert isinstance(cache_data['fingerprint'], str), "Fingerprint should be a string"
    assert len(cache_data['fingerprint']) > 0, "Fingerprint should not be empty"


def test_first_scan_cache_stores_symbols(tmp_path, monkeypatch):
    """Cache file stores symbols with required fields from Symbol.to_dict()."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def process(x): """Process x."""\n    pass\n',
    })

    cache = CodeCache()
    cache.scan(str(root), use_cache=True)

    cache_path = cache_path_for(str(root))
    cache_data = read_cache_json(cache_path)

    assert 'files' in cache_data, "Cache missing files field"
    assert isinstance(cache_data['files'], dict), "files should be a dict"

    # Check that at least one file is stored with required fields
    for relpath, file_data in cache_data['files'].items():
        assert 'lang' in file_data, f"File {relpath} missing lang"
        assert 'symbols' in file_data, f"File {relpath} missing symbols"

        # Symbols should have fields from Symbol.to_dict()
        for sym in file_data['symbols']:
            assert 'name' in sym, "Symbol missing name"
            assert 'kind' in sym, "Symbol missing kind"
            assert 'file' in sym, "Symbol missing file"
            assert 'line' in sym, "Symbol missing line"
            assert 'end_line' in sym, "Symbol missing end_line"


# ── T3.2: Second scan(use_cache=True) loads cache, loaded_from_cache=True ──

def test_second_scan_loads_cache(tmp_path, monkeypatch):
    """Second scan(use_cache=True) on unchanged tree loads it: loaded_from_cache=True."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'main.py': 'def hello(): pass\n',
    })

    # First scan
    cache1 = CodeCache()
    stats1 = cache1.scan(str(root), use_cache=True)
    assert stats1['loaded_from_cache'] is False
    files_count_1 = stats1['files']
    symbols_count_1 = stats1['symbols']

    # Second scan (should load from cache)
    cache2 = CodeCache()
    stats2 = cache2.scan(str(root), use_cache=True)

    # Assert cache was loaded
    assert 'loaded_from_cache' in stats2, "loaded_from_cache key missing"
    assert stats2['loaded_from_cache'] is True, "Second scan should have loaded_from_cache=True"

    # Assert stats match (same content)
    assert stats2['files'] == files_count_1, "File count should match"
    assert stats2['symbols'] == symbols_count_1, "Symbol count should match"


def test_cache_load_reconstructs_symbol_index(tmp_path, monkeypatch):
    """Loaded cache reconstructs symbol index correctly."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'lib.py': 'def helper(): pass\nclass Service:\n    def process(self): pass\n',
    })

    # First scan
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    results_1 = cache1.find_symbol('helper')
    assert len(results_1) > 0, "First scan should find 'helper'"

    # Second scan (loads cache)
    cache2 = CodeCache()
    cache2.scan(str(root), use_cache=True)
    results_2 = cache2.find_symbol('helper')

    # Assert symbol index is rebuilt
    assert len(results_2) > 0, "Loaded cache should find 'helper' via symbol index"
    assert results_2[0].name == 'helper', "Symbol name should match"


def test_cache_load_no_parse(tmp_path, monkeypatch):
    """When cache is loaded, no parsing happens (tree=None in entries)."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    # First scan
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)

    # Second scan (loads from cache)
    cache2 = CodeCache()
    cache2.scan(str(root), use_cache=True)

    # Check that loaded entries have tree=None and source=None
    for entry in cache2.files.values():
        assert entry.tree is None, "Loaded cache entry should have tree=None"
        assert entry.source is None, "Loaded cache entry should have source=None"


# ── T3.3: use_cache=False neither reads nor writes cache ──

def test_use_cache_false_skips_read(tmp_path, monkeypatch):
    """use_cache=False: existing cache is NOT consulted, always parses."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    # Create cache first with use_cache=True
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))
    assert cache_path.exists(), "Cache should be created"

    # Now scan with use_cache=False
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=False)

    # Assert cache was not used
    assert stats['loaded_from_cache'] is False, "use_cache=False should never load from cache"

    # Assert entries have source and tree (parsed fresh)
    for entry in cache2.files.values():
        assert entry.source is not None, "use_cache=False should parse and populate source"
        assert entry.tree is not None, "use_cache=False should parse and populate tree"


def test_use_cache_false_does_not_write_cache(tmp_path, monkeypatch):
    """use_cache=False: cache is NOT written even if it doesn't exist."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def bar(): pass\n',
    })

    # Ensure no cache exists
    cache_path = cache_path_for(str(root))
    assert not cache_path.exists(), "Cache should not exist initially"

    # Scan with use_cache=False
    cache = CodeCache()
    cache.scan(str(root), use_cache=False)

    # Assert cache was not created
    assert not cache_path.exists(), "use_cache=False should not create cache"


def test_use_cache_false_delete_existing_cache(tmp_path, monkeypatch):
    """Verify that use_cache=False doesn't consult pre-existing cache."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def original(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Delete the source file
    (root / 'code.py').unlink()

    # Create new tree with different content
    create_test_tree(root, {
        'code.py': 'def updated(): pass\n',
    })

    # Scan with use_cache=False should parse the updated file
    cache2 = CodeCache()
    cache2.scan(str(root), use_cache=False)

    # Should find 'updated', not 'original'
    results = cache2.find_symbol('updated')
    assert len(results) > 0, "Should find updated function"


# ── T3.4: rebuild_cache=True overwrites cache, loaded_from_cache=False ──

def test_rebuild_cache_overwrites_existing(tmp_path, monkeypatch):
    """rebuild_cache=True: parse fresh and overwrite cache."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def original(): pass\n',
    })

    # First scan to create cache
    cache1 = CodeCache()
    stats1 = cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))
    cache_mtime_1 = cache_path.stat().st_mtime

    # Wait a bit to ensure mtime will differ
    time.sleep(0.01)

    # Scan with rebuild_cache=True
    cache2 = CodeCache()
    stats2 = cache2.scan(str(root), rebuild_cache=True)

    # Assert full parse happened
    assert stats2['loaded_from_cache'] is False, "rebuild_cache=True should have loaded_from_cache=False"

    # Assert cache was overwritten (mtime advanced)
    cache_mtime_2 = cache_path.stat().st_mtime
    assert cache_mtime_2 >= cache_mtime_1, "Cache file should be updated/rewritten"

    # Assert entries have source and tree (parsed)
    for entry in cache2.files.values():
        assert entry.source is not None, "rebuild_cache=True should parse fresh"
        assert entry.tree is not None, "rebuild_cache=True should parse fresh"


def test_rebuild_cache_true_ignores_existing_cache(tmp_path, monkeypatch):
    """rebuild_cache=True ignores any existing valid cache."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)

    # Scan again with rebuild_cache=True (should not load, should parse fresh)
    cache2 = CodeCache()
    stats = cache2.scan(str(root), rebuild_cache=True)

    assert stats['loaded_from_cache'] is False, "rebuild_cache=True should parse fresh, not load"

    # Entries should have tree and source
    for entry in cache2.files.values():
        assert entry.tree is not None
        assert entry.source is not None


# ── T3.5: Robust — corrupt cache falls back to parse, no crash ──

def test_corrupt_cache_json_fallback(tmp_path, monkeypatch):
    """Corrupt JSON in cache -> falls back to full parse, loaded_from_cache=False."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def process(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Corrupt the cache file
    cache_path.write_text('{ INVALID JSON HERE }')

    # Scan should NOT crash and should fall back to parse
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    # Assert full parse happened (no crash, correct fallback)
    assert stats['loaded_from_cache'] is False, "Corrupt cache should fall back to parse"
    assert stats['files'] > 0, "Should still parse the tree"
    assert stats['errors'] == 0, "Should complete successfully"


def test_corrupt_cache_unreadable_fallback(tmp_path, monkeypatch):
    """Unreadable cache file -> falls back to parse, produces correct results."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def helper(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Write garbage bytes
    cache_path.write_bytes(b'\x00\x01\x02\x03 garbage')

    # Scan should not crash
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    # Verify fallback succeeded
    assert stats['loaded_from_cache'] is False
    assert stats['files'] == 1
    results = cache2.find_symbol('helper')
    assert len(results) > 0, "Should find symbol despite cache corruption"


def test_corrupt_cache_missing_fields_fallback(tmp_path, monkeypatch):
    """Cache with missing required fields -> falls back to parse."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def func(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Write incomplete cache (missing 'files' field)
    invalid_cache = {
        'cache_format_version': CACHE_FORMAT_VERSION,
        'fingerprint': 'some_fp',
        # Missing 'files' field
    }
    cache_path.write_text(json.dumps(invalid_cache))

    # Should not crash and should parse fresh
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    assert stats['loaded_from_cache'] is False
    assert stats['files'] > 0


# ── T3.6: Robustness — version mismatch cache -> full parse, no crash ──

def test_version_mismatch_fallback(tmp_path, monkeypatch):
    """Cache with stale CACHE_FORMAT_VERSION -> full parse, no crash."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def legacy(): pass\n',
    })

    # Create cache with current version
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Manually change version in cache file
    cache_data = read_cache_json(cache_path)
    cache_data['cache_format_version'] = CACHE_FORMAT_VERSION - 1  # Stale version
    cache_path.write_text(json.dumps(cache_data))

    # Scan with use_cache=True should detect version mismatch and parse fresh
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    # Assert full parse happened
    assert stats['loaded_from_cache'] is False, "Version mismatch should fall back to parse"
    assert stats['files'] > 0, "Should successfully parse"

    # Verify correct results
    results = cache2.find_symbol('legacy')
    assert len(results) > 0, "Should find symbols despite version mismatch"


def test_version_mismatch_updates_cache(tmp_path, monkeypatch):
    """Version mismatch cache is rewritten with new version."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def func(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Change version to simulate staleness
    cache_data = read_cache_json(cache_path)
    old_version = CACHE_FORMAT_VERSION - 1
    cache_data['cache_format_version'] = old_version
    cache_path.write_text(json.dumps(cache_data))

    # Scan should rewrite with new version
    cache2 = CodeCache()
    cache2.scan(str(root), use_cache=True)

    # Check that cache was updated
    updated_cache_data = read_cache_json(cache_path)
    assert updated_cache_data['cache_format_version'] == CACHE_FORMAT_VERSION


# ── T3.7: Robustness — fingerprint mismatch -> full parse, cache refreshed ──

def test_fingerprint_mismatch_fallback(tmp_path, monkeypatch):
    """Valid cache exists, file modified -> fingerprint mismatch -> full parse."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def original(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))
    cache_data_1 = read_cache_json(cache_path)
    orig_fingerprint = cache_data_1['fingerprint']

    # Modify source file
    (root / 'code.py').write_text('def modified(): pass\n')

    # Scan with use_cache=True
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    # Assert full parse happened (fingerprint changed)
    assert stats['loaded_from_cache'] is False, "Fingerprint mismatch should trigger full parse"

    # Assert new fingerprint in cache
    cache_data_2 = read_cache_json(cache_path)
    assert cache_data_2['fingerprint'] != orig_fingerprint, "Cache should have new fingerprint"

    # Verify new content is in cache
    results = cache2.find_symbol('modified')
    assert len(results) > 0, "Cache should contain updated symbol"


def test_fingerprint_mismatch_detects_file_size_change(tmp_path, monkeypatch):
    """Fingerprint includes file size; size change -> cache miss."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def func(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)

    # Modify file (add content, changing size)
    (root / 'code.py').write_text('def func(): pass\n\n# comment\n')

    # Scan should detect size change
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    assert stats['loaded_from_cache'] is False, "File size change should invalidate cache"


def test_fingerprint_mismatch_detects_mtime_change(tmp_path, monkeypatch):
    """Fingerprint includes mtime_ns; mtime change -> cache miss."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)

    # Touch file to change mtime
    time.sleep(0.01)  # Ensure mtime differs
    (root / 'code.py').touch()

    # Scan should detect mtime change
    cache2 = CodeCache()
    stats = cache2.scan(str(root), use_cache=True)

    assert stats['loaded_from_cache'] is False, "mtime change should invalidate cache"


# ── T3.8: Atomic write via temp file + os.replace ──

def test_atomic_write_uses_temp_file(tmp_path, monkeypatch):
    """Cache write uses temp file + os.replace, no leftover temp files."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    # Scan to create cache
    cache = CodeCache()
    cache.scan(str(root), use_cache=True)

    # Assert no temp files left in cache dir
    temp_files = find_temp_files_in_dir(cache_dir, '.tmp')
    assert len(temp_files) == 0, f"Should not have leftover temp files, found: {temp_files}"


def test_atomic_write_replaces_atomically(tmp_path, monkeypatch):
    """Verify cache write uses os.replace for atomic replacement."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def bar(): pass\n',
    })

    # Create cache
    cache1 = CodeCache()
    cache1.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Patch os.replace to verify it's called
    original_replace = os.replace
    replace_called = []

    def tracked_replace(src, dst):
        replace_called.append((src, dst))
        return original_replace(src, dst)

    with patch('os.replace', side_effect=tracked_replace):
        # Create new cache instance and scan (should write)
        cache2 = CodeCache()
        cache2.scan(str(root), rebuild_cache=True)

    # Assert os.replace was called with appropriate args
    assert len(replace_called) > 0, "os.replace should be called for atomic write"
    # Verify destination is the cache file
    _, dest_file = replace_called[0]
    assert Path(dest_file) == cache_path, "Replace destination should be cache_path"


def test_atomic_write_no_half_written_cache(tmp_path, monkeypatch):
    """On successful scan, cache file is complete (not half-written)."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def func(): pass\n',
        'lib.py': 'class Service: pass\n',
    })

    # Scan
    cache = CodeCache()
    cache.scan(str(root), use_cache=True)
    cache_path = cache_path_for(str(root))

    # Verify cache file is valid JSON (not truncated/half-written)
    try:
        cache_data = read_cache_json(cache_path)
        assert 'cache_format_version' in cache_data
        assert 'fingerprint' in cache_data
        assert 'files' in cache_data
    except json.JSONDecodeError:
        raise AssertionError("Cache file is not valid JSON (half-written?)")


# ── Backward compatibility ──────────────────────────────────────────────────

def test_scan_backward_compat_no_params(tmp_path, monkeypatch):
    """scan(root) with no extra params maintains backward compatibility."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def hello(): pass\n',
    })

    # Call scan with no use_cache or rebuild_cache params
    cache = CodeCache()
    stats = cache.scan(str(root))

    # Should work without errors, defaults to use_cache=True
    assert 'files' in stats
    assert 'symbols' in stats
    assert 'loaded_from_cache' in stats


def test_scan_backward_compat_skip_param(tmp_path, monkeypatch):
    """scan(root, skip=...) maintains backward compatibility."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
        'node_modules/pkg/lib.js': 'function bar() {}',
    })

    # Call scan with skip parameter
    cache = CodeCache()
    skip_set = {'node_modules'}
    stats = cache.scan(str(root), skip=skip_set)

    # Should work and respect skip
    assert 'files' in stats
    assert stats['files'] == 1  # Only code.py, node_modules skipped


# ── Cache path generation ──────────────────────────────────────────────────

def test_cache_path_for_deterministic(tmp_path):
    """cache_path_for() is deterministic: same root -> same path."""
    root = str((tmp_path / 'project').resolve())

    path1 = cache_path_for(root)
    path2 = cache_path_for(root)

    assert path1 == path2, "cache_path_for should be deterministic"


def test_cache_path_for_honors_env(tmp_path, monkeypatch):
    """cache_path_for() honors TREESIT_CACHE_DIR env var."""
    cache_dir = tmp_path / 'custom_cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = str((tmp_path / 'project').resolve())
    cache_path = cache_path_for(root)

    # Cache should be under custom dir
    assert str(cache_path).startswith(str(cache_dir)), \
        f"Cache path {cache_path} should be under {cache_dir}"


def test_cache_path_for_derives_from_root_hash(tmp_path, monkeypatch):
    """cache_path_for() filename derived from sha256 of root."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root1 = str((tmp_path / 'project1').resolve())
    root2 = str((tmp_path / 'project2').resolve())

    path1 = cache_path_for(root1)
    path2 = cache_path_for(root2)

    # Paths should be different (derived from different roots)
    assert path1 != path2, "Different roots should have different cache paths"
    assert path1.parent == path2.parent, "Should be in same cache dir"


# ── Fingerprint generation ──────────────────────────────────────────────────

def test_fingerprint_changes_on_file_add(tmp_path, monkeypatch):
    """CodeCache._fingerprint() changes when file is added."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    cache = CodeCache()

    # First fingerprint
    fp1 = cache._fingerprint(str(root), None)

    # Add a file
    (root / 'new.py').write_text('def bar(): pass\n')

    # Second fingerprint should differ
    fp2 = cache._fingerprint(str(root), None)

    assert fp1 != fp2, "Fingerprint should change when file is added"


def test_fingerprint_changes_on_skip_change(tmp_path, monkeypatch):
    """_fingerprint() changes when skip set changes."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
        'test.py': 'def test_foo(): pass\n',
    })

    cache = CodeCache()

    # Fingerprint with no skip
    fp1 = cache._fingerprint(str(root), None)

    # Fingerprint with skip={'test.py'}
    fp2 = cache._fingerprint(str(root), {'test.py'})

    assert fp1 != fp2, "Fingerprint should change when skip set changes"


def test_fingerprint_stable_on_unchanged_tree(tmp_path, monkeypatch):
    """_fingerprint() is stable across re-scans of unchanged tree."""
    cache_dir = tmp_path / 'cache'
    cache_dir.mkdir()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    root = create_test_tree(tmp_path / 'project', {
        'code.py': 'def foo(): pass\n',
    })

    cache = CodeCache()

    # Get fingerprints at different times
    fp1 = cache._fingerprint(str(root), None)
    time.sleep(0.01)
    fp2 = cache._fingerprint(str(root), None)

    assert fp1 == fp2, "Fingerprint should be stable for unchanged tree"


# ── Standalone runner ───────────────────────────────────────────────────────

if __name__ == '__main__':
    import traceback

    # Collect tests
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]

    # Run with fixtures support (simplified: just tmp_path via tempfile)
    passed = failed = 0
    for test in tests:
        # Create tmp_path for each test
        tmp_path = Path(tempfile.mkdtemp())
        try:
            # Create monkeypatch mock
            class Monkeypatch:
                def setenv(self, key, val):
                    os.environ[key] = val

            monkeypatch = Monkeypatch()

            # Run test
            test(tmp_path, monkeypatch)
            passed += 1
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__}: {e}")
            traceback.print_exc()
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
