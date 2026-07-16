"""Tests for tree-sitting cache fingerprinting and cache path resolution.

This test suite covers the persistent scan-cache contract (v1, cheap tier):
- _fingerprint stability and invalidation
- cache_path_for determinism and env override behavior

Run: python -m pytest tests/test_cache_fingerprint.py -v
"""

import sys
import os
import tempfile
import time
from pathlib import Path

# Bootstrap parsers before importing engine
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from engine import CodeCache
# cache_path_for will be imported from engine after implementation

# ── Fixtures ────────────────────────────────────────────────────────────

def create_test_repo(tmp_path: Path) -> Path:
    """Create a minimal test repository with real source files."""
    repo = tmp_path / "test_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # Create a Python source file
    py_file = repo / "example.py"
    py_file.write_bytes(b'''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

class Service:
    def start(self) -> None:
        pass
''')

    # Create a Rust source file
    rs_file = repo / "lib.rs"
    rs_file.write_bytes(b'''
pub struct Config {
    pub name: String,
}

pub fn create() -> Config {
    Config { name: String::new() }
}

impl Config {
    pub fn new(name: &str) -> Self {
        Config { name: name.to_string() }
    }
}
''')

    return repo


# ── Fingerprint: Stability ──────────────────────────────────────────────

def test_fingerprint_is_stable_unchanged_tree(tmp_path: Path):
    """Fingerprint is STABLE: two calls on an unchanged tree return the same value."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # First fingerprint
    fp1 = cache._fingerprint(str(repo), skip=None)
    assert isinstance(fp1, str), "Fingerprint should return a string"
    assert len(fp1) > 0, "Fingerprint should not be empty"

    # Second fingerprint on unchanged tree
    fp2 = cache._fingerprint(str(repo), skip=None)
    assert fp2 == fp1, "Fingerprint should be stable across rescans of unchanged tree"


# ── Fingerprint: Content Changes ────────────────────────────────────────

def test_fingerprint_changes_on_file_content_modify(tmp_path: Path):
    """Fingerprint CHANGES when a file's content is modified (mtime/size changes)."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint before modification
    fp_before = cache._fingerprint(str(repo), skip=None)

    # Modify file content (use os.utime to force distinct mtime_ns)
    py_file = repo / "example.py"
    py_file.write_bytes(b'''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

class Service:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
''')
    # Force mtime to be distinct
    mtime_ns = (time.time_ns() + 1000000000)
    os.utime(py_file, ns=(mtime_ns, mtime_ns))

    # Get fingerprint after modification
    fp_after = cache._fingerprint(str(repo), skip=None)

    assert fp_after != fp_before, "Fingerprint should change when file content is modified"


def test_fingerprint_changes_on_file_size_change(tmp_path: Path):
    """Fingerprint CHANGES when file size changes."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint before size change
    fp_before = cache._fingerprint(str(repo), skip=None)

    # Modify file size (truncate to make size noticeably different)
    py_file = repo / "example.py"
    original_size = py_file.stat().st_size
    py_file.write_bytes(b'# Much shorter file\n')
    assert py_file.stat().st_size != original_size

    # Get fingerprint after size change
    fp_after = cache._fingerprint(str(repo), skip=None)

    assert fp_after != fp_before, "Fingerprint should change when file size changes"


# ── Fingerprint: File Operations ────────────────────────────────────────

def test_fingerprint_changes_on_file_added(tmp_path: Path):
    """Fingerprint CHANGES when a file is added."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint before adding file
    fp_before = cache._fingerprint(str(repo), skip=None)

    # Add a new Python file
    new_file = repo / "new_module.py"
    new_file.write_bytes(b'def new_function():\n    pass\n')

    # Get fingerprint after adding file
    fp_after = cache._fingerprint(str(repo), skip=None)

    assert fp_after != fp_before, "Fingerprint should change when a file is added"


def test_fingerprint_changes_on_file_removed(tmp_path: Path):
    """Fingerprint CHANGES when a file is removed."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint before removing file
    fp_before = cache._fingerprint(str(repo), skip=None)

    # Remove a file
    py_file = repo / "example.py"
    py_file.unlink()

    # Get fingerprint after removing file
    fp_after = cache._fingerprint(str(repo), skip=None)

    assert fp_after != fp_before, "Fingerprint should change when a file is removed"


# ── Fingerprint: Skip-set Changes ───────────────────────────────────────

def test_fingerprint_changes_on_skip_set_change(tmp_path: Path):
    """Fingerprint CHANGES when the skip-set changes."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint with no skip set
    fp_no_skip = cache._fingerprint(str(repo), skip=None)

    # Get fingerprint with a skip set (even if it doesn't exclude anything)
    fp_with_skip = cache._fingerprint(str(repo), skip={'nonexistent_dir'})

    # The fingerprints should differ because skip-set is part of the hash
    assert fp_with_skip != fp_no_skip, "Fingerprint should change when skip-set changes"


def test_fingerprint_changes_with_different_skip_sets(tmp_path: Path):
    """Fingerprint differs for different skip-sets (included in hash)."""
    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint with skip set A
    fp_skip_a = cache._fingerprint(str(repo), skip={'dir_a'})

    # Get fingerprint with skip set B
    fp_skip_b = cache._fingerprint(str(repo), skip={'dir_b'})

    assert fp_skip_a != fp_skip_b, "Fingerprint should differ for different skip-sets"


# ── Fingerprint: Cache Format Version ───────────────────────────────────

def test_fingerprint_changes_on_cache_format_version_bump(tmp_path: Path, monkeypatch):
    """Fingerprint CHANGES when engine.CACHE_FORMAT_VERSION changes."""
    import engine

    repo = create_test_repo(tmp_path)
    cache = CodeCache()

    # Get fingerprint with current version
    original_version = engine.CACHE_FORMAT_VERSION
    fp_v1 = cache._fingerprint(str(repo), skip=None)

    # Bump the cache format version
    monkeypatch.setattr(engine, 'CACHE_FORMAT_VERSION', original_version + 1)

    # Get fingerprint with new version
    fp_v2 = cache._fingerprint(str(repo), skip=None)

    # Restore original version
    monkeypatch.setattr(engine, 'CACHE_FORMAT_VERSION', original_version)

    assert fp_v2 != fp_v1, "Fingerprint should change when CACHE_FORMAT_VERSION is bumped"


# ── cache_path_for: Determinism ────────────────────────────────────────

def test_cache_path_for_is_deterministic(tmp_path: Path):
    """cache_path_for(root) is deterministic for the same resolved abspath."""
    import engine
    repo = create_test_repo(tmp_path)
    repo_path = str(repo)

    # Call cache_path_for twice with the same path
    path1 = engine.cache_path_for(repo_path)
    path2 = engine.cache_path_for(repo_path)

    assert path1 == path2, "cache_path_for should be deterministic for the same root"


def test_cache_path_for_resolves_symlinks(tmp_path: Path):
    """cache_path_for resolves symlinks to canonical path."""
    import engine
    repo = create_test_repo(tmp_path)

    # Create a symlink to the repo
    symlink = tmp_path / "link_to_repo"
    symlink.symlink_to(repo)

    # Get cache paths for both the real and symlinked paths
    path_real = engine.cache_path_for(str(repo))
    path_symlink = engine.cache_path_for(str(symlink))

    # They should be the same (both resolve to the real path)
    assert path_real == path_symlink, "cache_path_for should resolve symlinks to the same canonical path"


def test_cache_path_for_differs_for_different_roots(tmp_path: Path):
    """cache_path_for differs for different roots."""
    import engine
    repo1 = create_test_repo(tmp_path / "root_a")
    repo2 = create_test_repo(tmp_path / "root_b")  # a genuinely distinct root

    path1 = engine.cache_path_for(str(repo1))
    path2 = engine.cache_path_for(str(repo2))

    assert path1 != path2, "cache_path_for should return different paths for different roots"


# ── cache_path_for: Environment Override ────────────────────────────────

def test_cache_path_for_honors_treesit_cache_dir_env(tmp_path: Path, monkeypatch):
    """cache_path_for honors TREESIT_CACHE_DIR environment variable."""
    import engine
    repo = create_test_repo(tmp_path)
    cache_dir = tmp_path / "my_cache"
    cache_dir.mkdir()

    # Set TREESIT_CACHE_DIR env var
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(cache_dir))

    # Get cache path
    cache_path = engine.cache_path_for(str(repo))

    # Verify the cache path is under the specified cache dir
    assert cache_path.parent == cache_dir, (
        f"cache_path_for should use TREESIT_CACHE_DIR; "
        f"got {cache_path.parent}, expected {cache_dir}"
    )


def test_cache_path_for_uses_temp_dir_when_no_env(tmp_path: Path, monkeypatch):
    """cache_path_for uses system temp dir when TREESIT_CACHE_DIR is not set."""
    import engine
    repo = create_test_repo(tmp_path)

    # Ensure TREESIT_CACHE_DIR is not set
    monkeypatch.delenv('TREESIT_CACHE_DIR', raising=False)

    # Get cache path
    cache_path = engine.cache_path_for(str(repo))

    # Verify it's a Path
    assert isinstance(cache_path, Path), "cache_path_for should return a Path object"

    # Verify parent directory exists (temp dir)
    assert cache_path.parent.exists(), "cache_path_for should use an existing directory (temp)"

    # Verify parent is writable
    assert os.access(cache_path.parent, os.W_OK), "cache path parent should be writable"


def test_cache_path_for_filename_derived_from_abspath(tmp_path: Path):
    """cache_path_for filename is deterministically derived from resolved abspath."""
    import engine
    repo1 = create_test_repo(tmp_path / "subdir1")
    repo2 = create_test_repo(tmp_path / "subdir2")

    path1 = engine.cache_path_for(str(repo1))
    path2 = engine.cache_path_for(str(repo2))

    # Filenames should be different (based on different paths)
    assert path1.name != path2.name, (
        "cache filenames should differ for different root paths"
    )

    # Both filenames should look like SHA256 hashes or similar deterministic names
    # (exact format depends on implementation, but should be hex/base64-ish)
    assert len(path1.name) > 8, "cache filename should be long enough to be unique"
    assert len(path2.name) > 8, "cache filename should be long enough to be unique"
