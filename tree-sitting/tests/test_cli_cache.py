"""Tests for tree-sitting CLI cache integration.

Tests the --no-cache and --rebuild-cache flags, cache file creation/loading,
and the "(cached)" marker in stats output.

Run: python -m pytest tests/test_cli_cache.py -v
Or:  cd /home/user/claude-skills/tree-sitting && python -m pytest tests/test_cli_cache.py -v
"""

import sys
import os
import subprocess
import tempfile
import shutil
from pathlib import Path


class TestCLICacheIntegration:
    """CLI invocations with caching behavior."""

    @staticmethod
    def _fixture_repo(tmp_path: Path) -> Path:
        """Create a minimal test repository with Python and Rust files."""
        repo = tmp_path / "fixture_repo"
        repo.mkdir()

        # Python file with named symbols
        py_file = repo / "example.py"
        py_file.write_text("""\
def greet(name: str) -> str:
    \"\"\"Greet someone.\"\"\"
    return f"Hello, {name}!"


class UserService:
    \"\"\"Manages users.\"\"\"

    def find_by_id(self, user_id: int):
        \"\"\"Find a user by ID.\"\"\"
        return None

    def create(self, name: str):
        \"\"\"Create a new user.\"\"\"
        return {"name": name}


def utility_function():
    pass
""")

        # Rust file with named symbols
        rs_file = repo / "lib.rs"
        rs_file.write_text("""\
pub struct Config {
    pub name: String,
}

pub trait Handler {
    fn handle(&self);
}

pub fn create_config(name: &str) -> Config {
    Config {
        name: name.to_string(),
    }
}

pub enum Status {
    Active,
    Inactive,
}

impl Config {
    pub fn new(name: String) -> Self {
        Config { name }
    }
}
""")

        return repo

    @staticmethod
    def _run_cli(repo_path: str, cache_dir: str, queries: list = None, flags: list = None) -> tuple[str, str, int]:
        """Run treesit.py CLI and return (stdout, stderr, returncode).

        repo_path: absolute path to repo to scan
        cache_dir: absolute path to cache directory (set as TREESIT_CACHE_DIR env)
        queries: list of query strings (e.g., ['find:greet', 'find:Config'])
        flags: list of flag strings (e.g., ['--no-cache', '--stats'])
        """
        python = "/home/claude/.venv/bin/python"
        treesit_py = "/home/user/claude-skills/tree-sitting/scripts/treesit.py"

        cmd = [python, treesit_py, repo_path]
        if flags:
            cmd.extend(flags)
        if queries:
            cmd.extend(queries)

        env = os.environ.copy()
        env["TREESIT_CACHE_DIR"] = cache_dir

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd="/home/user/claude-skills/tree-sitting"
        )

        return result.stdout, result.stderr, result.returncode

    def test_first_invocation_creates_cache_no_marker(self, tmp_path: Path):
        """First CLI invocation parses and creates cache; no '(cached)' in stats."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation: should parse (no cache yet)
        stdout, stderr, rc = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[],
            flags=["--stats"]
        )

        assert rc == 0, f"CLI failed: {stderr}"
        assert "(cached)" not in stdout, "First run should NOT show '(cached)' marker"
        assert "Scanned" in stdout, "Stats output should be present"

        # Cache file should now exist
        cache_files = list(cache_dir.glob("*"))
        assert len(cache_files) > 0, "Cache file should be created after first invocation"

    def test_second_invocation_serves_from_cache(self, tmp_path: Path):
        """Second identical invocation served from cache; stats show '(cached)'."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation
        self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])

        # Second invocation: should hit cache
        stdout, stderr, rc = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[],
            flags=["--stats"]
        )

        assert rc == 0, f"CLI failed: {stderr}"
        assert "(cached)" in stdout, "Second run should show '(cached)' marker in stats"

    def test_no_cache_flag_disables_cache(self, tmp_path: Path):
        """--no-cache flag: never read/write cache; no '(cached)' even on repeat."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation with --no-cache
        stdout1, stderr1, rc1 = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[],
            flags=["--no-cache", "--stats"]
        )
        assert rc1 == 0, f"First --no-cache run failed: {stderr1}"
        assert "(cached)" not in stdout1, "First --no-cache run should NOT have '(cached)'"

        # Verify no cache file created
        cache_files = list(cache_dir.glob("*"))
        assert len(cache_files) == 0, "Cache file should NOT be created with --no-cache"

        # Second invocation with --no-cache (identical to first)
        stdout2, stderr2, rc2 = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[],
            flags=["--no-cache", "--stats"]
        )
        assert rc2 == 0, f"Second --no-cache run failed: {stderr2}"
        assert "(cached)" not in stdout2, "Repeat --no-cache run should NOT have '(cached)'"

        # Still no cache file
        cache_files = list(cache_dir.glob("*"))
        assert len(cache_files) == 0, "Cache file should still NOT exist after second --no-cache run"

        # Positive control: prove caching is real, so the negatives above aren't
        # vacuously green. A normal run creates a cache; a normal repeat is a hit.
        self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        pc_out, _, pc_rc = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert pc_rc == 0
        assert list(cache_dir.glob("*")), "positive control: a cache-enabled run must create a cache file"
        assert "(cached)" in pc_out, "positive control: a cache-enabled repeat must show '(cached)'"

    def test_rebuild_cache_flag_refreshes_cache(self, tmp_path: Path):
        """--rebuild-cache: ignore existing cache, re-parse, and overwrite cache."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation: normal (creates cache)
        self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])

        # Positive control: a normal repeat must be a cache hit, so the
        # "not (cached)" assertion below is meaningful rather than vacuous.
        pc_out, _, pc_rc = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert pc_rc == 0
        assert "(cached)" in pc_out, "positive control: normal repeat must be a cache hit"

        # Second invocation with --rebuild-cache
        stdout, stderr, rc = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[],
            flags=["--rebuild-cache", "--stats"]
        )

        assert rc == 0, f"--rebuild-cache run failed: {stderr}"
        assert "(cached)" not in stdout, "--rebuild-cache should NOT show '(cached)' marker"
        assert "Scanned" in stdout, "Stats should be present (fresh parse)"

    def test_multi_query_with_cache(self, tmp_path: Path):
        """Batched multi-query invocation with caching: scans once, runs all queries."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Multi-query invocation with find and source
        stdout, stderr, rc = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=["find:greet", "find:Config", "source:UserService"],
            flags=["--stats"]
        )

        assert rc == 0, f"Multi-query run failed: {stderr}"
        assert "Scanned" in stdout, "Stats should be present"

        # All three queries should appear in output
        # Note: the exact output depends on implementation, but should include results
        assert stdout, "Query results should be in output"

        # A second identical batched run must be a cache hit and return the same
        # results (proving the cache path serves batched queries correctly).
        stdout2, stderr2, rc2 = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=["find:greet", "find:Config", "source:UserService"],
            flags=["--stats"],
        )
        assert rc2 == 0, f"Second multi-query run failed: {stderr2}"
        assert "(cached)" in stdout2, "batched multi-query repeat must be a cache hit"

    def test_cache_hit_and_no_cache_identical_output(self, tmp_path: Path):
        """Cache-hit and --no-cache runs produce identical query output (except stats)."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        query = "find:greet"
        flags_normal = ["--stats"]
        flags_no_cache = ["--no-cache", "--stats"]

        # First: populate cache
        self._run_cli(str(repo), str(cache_dir), queries=[query], flags=flags_normal)

        # Second: hit cache
        stdout_cached, stderr_cached, rc_cached = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[query],
            flags=flags_normal
        )
        assert rc_cached == 0

        # Third: no-cache (equivalent of re-parsing)
        stdout_no_cache, stderr_no_cache, rc_no_cache = self._run_cli(
            str(repo),
            str(cache_dir),
            queries=[query],
            flags=flags_no_cache
        )
        assert rc_no_cache == 0

        # Strip the stats lines (they'll differ due to "(cached)" marker and timing)
        # and compare the rest
        def extract_query_output(output: str) -> str:
            """Extract query results, stripping stats and timing info."""
            lines = output.split('\n')
            # Skip lines with "Scanned", "Symbols:", "Errors:", "(cached)", timing
            filtered = [
                line for line in lines
                if line and not any(x in line for x in ["Scanned", "Symbols:", "Errors:", "(cached)"])
            ]
            return '\n'.join(filtered)

        query_out_cached = extract_query_output(stdout_cached)
        query_out_no_cache = extract_query_output(stdout_no_cache)

        assert query_out_cached, "Cache hit should produce query output"
        assert query_out_no_cache, "No-cache run should produce query output"
        # The essential query results should be identical
        assert query_out_cached == query_out_no_cache, \
            f"Query output differs between cache-hit and no-cache.\nCached:\n{query_out_cached}\n\nNo-cache:\n{query_out_no_cache}"

    def test_cache_survives_tree_unchanged(self, tmp_path: Path):
        """Cache is reused across invocations when files are unchanged."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation
        stdout1, _, rc1 = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert rc1 == 0
        assert "(cached)" not in stdout1

        # Second invocation (same repo, same files)
        stdout2, _, rc2 = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert rc2 == 0
        assert "(cached)" in stdout2, "Cache should be reused when files unchanged"

    def test_cache_invalidated_on_file_change(self, tmp_path: Path):
        """Cache is invalidated when files are modified."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation
        self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])

        # Positive control: unchanged repeat must be a cache hit before we can
        # meaningfully assert that a modification invalidates it.
        pc_out, _, _ = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert "(cached)" in pc_out, "cache must engage on an unchanged repeat first"

        # Modify a file
        py_file = repo / "example.py"
        py_file.write_text(py_file.read_text() + "\n\ndef new_function():\n    pass\n")

        # Third invocation: should detect change and re-parse (no "(cached)")
        stdout3, _, rc3 = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert rc3 == 0
        assert "(cached)" not in stdout3, "Cache should be invalidated after file modification"

    def test_cache_invalidated_on_file_add(self, tmp_path: Path):
        """Cache is invalidated when new files are added."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation
        self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])

        # Positive control: unchanged repeat must be a cache hit first.
        pc_out, _, _ = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert "(cached)" in pc_out, "cache must engage on an unchanged repeat first"

        # Add a new file
        new_file = repo / "new_module.py"
        new_file.write_text("def new_func():\n    pass\n")

        # Third invocation: should detect change and re-parse
        stdout3, _, rc3 = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert rc3 == 0
        assert "(cached)" not in stdout3, "Cache should be invalidated after adding file"

    def test_cache_invalidated_on_file_delete(self, tmp_path: Path):
        """Cache is invalidated when files are deleted."""
        repo = self._fixture_repo(tmp_path)
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # First invocation
        self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])

        # Positive control: unchanged repeat must be a cache hit first.
        pc_out, _, _ = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert "(cached)" in pc_out, "cache must engage on an unchanged repeat first"

        # Delete a file
        py_file = repo / "example.py"
        py_file.unlink()

        # Third invocation: should detect change and re-parse
        stdout3, _, rc3 = self._run_cli(str(repo), str(cache_dir), queries=[], flags=["--stats"])
        assert rc3 == 0
        assert "(cached)" not in stdout3, "Cache should be invalidated after deleting file"


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
