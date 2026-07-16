"""Tests for lazy source correctness on cache hits — T4.

This module tests that FileEntry objects loaded from the persistent cache
have source=None and tree=None, and that code paths requiring source bytes
(get_source_range, references) lazily read from disk and return identical
results to a fresh parse.

Run: python -m pytest tests/test_cache_lazy_source.py -v
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

# Bootstrap parsers before importing engine
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from engine import CodeCache, FileEntry


# ── Helpers ──────────────────────────────────────────────────────────────

def _cache_dir_for_root(root: str) -> Path:
    """Return the cache file path for a root, using TREESIT_CACHE_DIR if set."""
    # This mirrors the engine.cache_path_for() logic that will be implemented
    cache_dir = os.environ.get('TREESIT_CACHE_DIR')
    if cache_dir:
        return Path(cache_dir)
    # Fallback: use system temp
    return Path(tempfile.gettempdir()) / 'treesit-cache'


def _read_cache_json(root: str) -> dict:
    """Read raw cache JSON from disk (for inspection)."""
    import hashlib
    root_resolved = str(Path(root).resolve())
    cache_hash = hashlib.sha256(root_resolved.encode()).hexdigest()
    cache_dir = _cache_dir_for_root(root)
    cache_file = cache_dir / f'{cache_hash}.json'
    if not cache_file.exists():
        return {}
    return json.loads(cache_file.read_text())


# ── T4.1: Cache hit, get_source_range returns same as fresh parse ───────

def test_cache_hit_get_source_range_matches_fresh():
    """After cache-hit scan, get_source_range returns same text as fresh parse."""
    tmpdir = tempfile.mkdtemp()
    cache_dir = tempfile.mkdtemp()
    try:
        os.environ['TREESIT_CACHE_DIR'] = cache_dir

        # Create a test file with recognizable content
        test_file = Path(tmpdir) / 'module.py'
        test_file.write_text(
            'def alpha():\n'
            '    """Line 2 docstring."""\n'
            '    return 42\n'
            'def beta():\n'
            '    pass\n'
        )

        # Scan fresh (populates cache)
        cache_fresh = CodeCache()
        cache_fresh.scan(tmpdir)
        src_fresh = cache_fresh.get_source_range('module.py', 2, 4)

        # Clear in-memory cache, scan from disk cache (cache hit)
        cache_hit = CodeCache()
        hit_stats = cache_hit.scan(tmpdir)  # must be a cache hit
        assert hit_stats.get('loaded_from_cache') is True, \
            "second scan must load from cache, else this test is vacuous"
        src_hit = cache_hit.get_source_range('module.py', 2, 4)

        # Results must be identical
        assert src_fresh == src_hit, \
            f"Fresh: {src_fresh!r} != Hit: {src_hit!r}"
        assert 'Line 2 docstring' in src_hit

    finally:
        if 'TREESIT_CACHE_DIR' in os.environ:
            del os.environ['TREESIT_CACHE_DIR']
        shutil.rmtree(tmpdir)
        shutil.rmtree(cache_dir)


# ── T4.2: Cache hit, references returns same as fresh parse ────────────

def test_cache_hit_references_matches_fresh():
    """After cache-hit scan, references() returns same results as fresh parse."""
    tmpdir = tempfile.mkdtemp()
    cache_dir = tempfile.mkdtemp()
    try:
        os.environ['TREESIT_CACHE_DIR'] = cache_dir

        # Create test files with a symbol used in multiple places
        Path(tmpdir, 'def.py').write_text(
            'class UserConfig:\n'
            '    """Holds user settings."""\n'
            '    def __init__(self):\n'
            '        pass\n'
        )
        Path(tmpdir, 'use.py').write_text(
            'from def import UserConfig\n'
            'cfg = UserConfig()\n'
            'settings = UserConfig()\n'
        )

        # Scan fresh
        cache_fresh = CodeCache()
        cache_fresh.scan(tmpdir)
        refs_fresh = cache_fresh.references('UserConfig', limit=10)

        # Scan from cache hit
        cache_hit = CodeCache()
        hit_stats = cache_hit.scan(tmpdir)
        assert hit_stats.get('loaded_from_cache') is True, \
            "second scan must load from cache, else this test is vacuous"
        refs_hit = cache_hit.references('UserConfig', limit=10)

        # Results must be identical: same files, same line numbers, same text
        assert len(refs_fresh) == len(refs_hit), \
            f"Fresh found {len(refs_fresh)} refs, hit found {len(refs_hit)}"

        for ref_f, ref_h in zip(refs_fresh, refs_hit):
            assert ref_f == ref_h, \
                f"Fresh: {ref_f} != Hit: {ref_h}"

        # Verify we found references in both files
        files = [r['file'] for r in refs_hit]
        assert any('def.py' in f for f in files)
        assert any('use.py' in f for f in files)

    finally:
        if 'TREESIT_CACHE_DIR' in os.environ:
            del os.environ['TREESIT_CACHE_DIR']
        shutil.rmtree(tmpdir)
        shutil.rmtree(cache_dir)


# ── T4.3: Cache file does NOT contain raw source text ───────────────────

def test_cache_file_omits_raw_source():
    """Cache JSON does not contain the raw source bytes of fixture files."""
    tmpdir = tempfile.mkdtemp()
    cache_dir = tempfile.mkdtemp()
    try:
        os.environ['TREESIT_CACHE_DIR'] = cache_dir

        # Create test file with a distinctive marker comment
        marker = '### DISTINCTIVE_CACHE_TEST_MARKER_12345 ###'
        test_file = Path(tmpdir) / 'sample.py'
        test_file.write_text(
            f'# {marker}\n'
            'def function():\n'
            '    return "value"\n'
        )

        # Scan to write cache
        cache = CodeCache()
        cache.scan(tmpdir)

        # Read raw cache JSON from disk — it must actually exist, else the
        # marker-absence check below is vacuously true.
        cache_json = _read_cache_json(tmpdir)
        assert cache_json, "cache file must exist and be non-empty"
        cache_text = json.dumps(cache_json)

        # Verify the distinctive marker is NOT in the cache JSON
        assert marker not in cache_text, \
            f"Marker found in cache JSON: {cache_text[:500]}"
        assert 'function' not in cache_text or 'function' in str(cache_json.get('files', [])), \
            "Source code should not be in cache (only symbol names)"

    finally:
        if 'TREESIT_CACHE_DIR' in os.environ:
            del os.environ['TREESIT_CACHE_DIR']
        shutil.rmtree(tmpdir)
        shutil.rmtree(cache_dir)


# ── T4.4: Graceful degradation when source file deleted ────────────────

def test_cache_hit_missing_file_degrades_gracefully():
    """After cache written, delete source file, cache-hit scan with get_source_range
    and references must degrade gracefully (no crash, empty/skipped result)."""
    tmpdir = tempfile.mkdtemp()
    cache_dir = tempfile.mkdtemp()
    try:
        os.environ['TREESIT_CACHE_DIR'] = cache_dir

        # Create and scan test files
        Path(tmpdir, 'exists.py').write_text('def keep_me(): pass\n')
        Path(tmpdir, 'delete_me.py').write_text(
            'def symbol_in_deleted():\n'
            '    return 42\n'
        )

        cache = CodeCache()
        cache.scan(tmpdir)  # writes cache
        initial_refs = cache.references('symbol_in_deleted', limit=5)
        assert len(initial_refs) > 0, "Should find symbol before deletion"

        # Load from cache (entry.source lazily None), THEN delete the file so the
        # lazy source read must cope with a now-missing file on a cached entry.
        cache2 = CodeCache()
        hit_stats = cache2.scan(tmpdir)
        assert hit_stats.get('loaded_from_cache') is True, \
            "must be a cache hit so the lazy-read path is exercised"
        (Path(tmpdir) / 'delete_me.py').unlink()

        # get_source_range on deleted file should not crash
        result = cache2.get_source_range('delete_me.py', 1, 2)
        # Should either be empty, or return a "not found" message, not crash
        assert isinstance(result, str)

        # references should not crash even if file is missing
        refs = cache2.references('symbol_in_deleted', limit=5)
        # Should either be empty list or skip the missing file gracefully
        assert isinstance(refs, list)

    finally:
        if 'TREESIT_CACHE_DIR' in os.environ:
            del os.environ['TREESIT_CACHE_DIR']
        shutil.rmtree(tmpdir)
        shutil.rmtree(cache_dir)


# ── T4.5: FileEntry from cache has source=None, tree=None immediately ───

def test_file_entry_lazy_fields_null_after_cache_hit():
    """FileEntry objects loaded from cache have source=None and tree=None
    immediately after scan (before any lazy read)."""
    tmpdir = tempfile.mkdtemp()
    cache_dir = tempfile.mkdtemp()
    try:
        os.environ['TREESIT_CACHE_DIR'] = cache_dir

        # Create and scan test file
        Path(tmpdir, 'lazy.py').write_text(
            'def lazy_function():\n'
            '    pass\n'
        )

        # First scan: writes cache
        cache1 = CodeCache()
        cache1.scan(tmpdir)
        entry1 = cache1.files.get('lazy.py')
        assert entry1 is not None
        # First scan may have source loaded (depends on implementation)
        # Just verify the structure exists
        assert isinstance(entry1, FileEntry)

        # Second scan: should hit cache
        cache2 = CodeCache()
        cache2.scan(tmpdir)

        # Check FileEntry from cache hit
        entry2 = cache2.files.get('lazy.py')
        assert entry2 is not None, "FileEntry should be populated from cache"

        # CRITICAL: source and tree must be None on cache hit
        # to force lazy loading behavior
        assert entry2.source is None, \
            "FileEntry.source must be None on cache hit (lazy loading required)"
        assert entry2.tree is None, \
            "FileEntry.tree must be None on cache hit (lazy loading required)"

        # But symbols should be populated from cache
        assert entry2.symbols is not None
        assert len(entry2.symbols) > 0, "Symbols should be loaded from cache"

    finally:
        if 'TREESIT_CACHE_DIR' in os.environ:
            del os.environ['TREESIT_CACHE_DIR']
        shutil.rmtree(tmpdir)
        shutil.rmtree(cache_dir)
