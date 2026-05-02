"""
Tests for security hardening fixes from adversarial review.

Validates both the vulnerability and the fix for each finding:
1. Path traversal in install_utilities()
2. LIKE wildcard injection in tag/summary searches
3. FTS5 keyword operator injection
4. Credential leakage in error logs
5. _init() thread safety (double-checked locking)
6. config_delete() read_only bypass
7. JSON decode error handling in _exec/_exec_batch
"""

import os
import re
import sys
import json
import threading
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock

# Ensure the scripts package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── 1. Path traversal in install_utilities() ──

def test_path_traversal_name_rejected():
    """Names with path separators or traversal sequences are rejected."""
    from scripts.utilities import _VALID_NAME_RE

    # These should all be rejected
    malicious_names = [
        "../../etc/cron.d/evil",
        "../passwords",
        "foo/bar",
        "foo\\bar",
        ".hidden",
        "",
        "name with spaces",
    ]
    for name in malicious_names:
        assert not _VALID_NAME_RE.match(name), f"Should reject: {name!r}"

    # These should be accepted
    valid_names = [
        "my_utility",
        "blog-publish",
        "bsky_card",
        "util123",
        "MyUtil",
    ]
    for name in valid_names:
        assert _VALID_NAME_RE.match(name), f"Should accept: {name!r}"

    print("PASS: Path traversal name validation")


def test_path_traversal_realpath_guard():
    """Even if regex is bypassed, realpath guard prevents escape from UTIL_DIR."""
    from scripts.utilities import UTIL_DIR

    # Simulate what the code does after regex check
    name = "legit_name"
    file_path = os.path.join(UTIL_DIR, f"{name}.py")
    resolved = os.path.realpath(file_path)
    assert resolved.startswith(os.path.realpath(UTIL_DIR) + os.sep), \
        "Valid name should resolve within UTIL_DIR"

    # A traversal path (if regex were bypassed) should fail
    name_evil = "../../etc/evil"
    file_path_evil = os.path.join(UTIL_DIR, f"{name_evil}.py")
    resolved_evil = os.path.realpath(file_path_evil)
    assert not resolved_evil.startswith(os.path.realpath(UTIL_DIR) + os.sep), \
        "Traversal path should NOT resolve within UTIL_DIR"

    print("PASS: Path traversal realpath guard")


def test_install_utilities_rejects_malicious_names():
    """End-to-end: install_utilities skips memories with malicious NAME fields."""
    from scripts import utilities

    # Mock recall to return a memory with a traversal name
    malicious_mem = {
        "id": "test-1", "type": "procedure",
        "summary": "NAME: ../../etc/cron.d/evil\nPURPOSE: test\n<<<PYTHON>>>\nprint('pwned')\n<<<END>>>"
    }

    valid_mem = {
        "id": "test-2", "type": "procedure",
        "summary": "NAME: safe_util\nPURPOSE: test\n<<<PYTHON>>>\nprint('ok')\n<<<END>>>"
    }

    with patch('scripts.memory.recall', return_value=[malicious_mem, valid_mem]):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_dir = utilities.UTIL_DIR
            utilities.UTIL_DIR = tmpdir
            try:
                result = utilities.install_utilities()
                # Malicious name should be skipped, valid one installed
                assert "../../etc/cron.d/evil" not in result
                assert "safe_util" in result
                # Verify no file was written outside tmpdir
                for root, dirs, files in os.walk(tmpdir):
                    for f in files:
                        path = os.path.join(root, f)
                        assert os.path.realpath(path).startswith(os.path.realpath(tmpdir))
            finally:
                utilities.UTIL_DIR = old_dir

    print("PASS: install_utilities rejects malicious names")


# ── 2. LIKE wildcard injection ──

def test_escape_like():
    """_escape_like properly escapes SQL LIKE wildcards."""
    from scripts.turso import _escape_like

    assert _escape_like("normal_tag") == "normal\\_tag"  # _ escaped
    assert _escape_like("100%") == "100\\%"  # % escaped
    assert _escape_like("back\\slash") == "back\\\\slash"  # \ escaped
    assert _escape_like("no wildcards") == "no wildcards"  # spaces left alone
    assert _escape_like("a%b_c\\d") == "a\\%b\\_c\\\\d"  # all three

    print("PASS: _escape_like handles all wildcards")


def test_like_escape_in_fts5_search():
    """Tag LIKE patterns in _fts5_search use ESCAPE clause."""
    from scripts import turso
    import inspect
    source = inspect.getsource(turso._fts5_search)
    # All tag LIKE patterns should have ESCAPE
    like_lines = [l.strip() for l in source.split('\n') if 'LIKE ?' in l]
    for line in like_lines:
        assert "ESCAPE" in line, f"LIKE without ESCAPE: {line}"

    print("PASS: _fts5_search LIKE patterns all have ESCAPE")


def test_like_escape_in_hints():
    """LIKE patterns in hints._match_from_turso use ESCAPE clause."""
    from scripts import hints
    import inspect
    source = inspect.getsource(hints._match_from_turso)
    like_lines = [l.strip() for l in source.split('\n') if 'LIKE ?' in l]
    for line in like_lines:
        assert "ESCAPE" in line, f"LIKE without ESCAPE: {line}"

    print("PASS: hints LIKE patterns all have ESCAPE")


# ── 3. FTS5 keyword operator injection ──

def test_fts5_strips_keywords():
    """FTS5 escape function strips AND/OR/NOT/NEAR operators."""
    from scripts.turso import _escape_fts5_server

    # NOT should be stripped — would invert results
    result = _escape_fts5_server("NOT existingterm")
    assert "NOT" not in result.split('"')  # NOT shouldn't appear outside quotes
    assert "existingterm" in result

    # AND, OR, NEAR should be stripped
    result = _escape_fts5_server("term1 AND term2")
    # Should become '"term1"* OR "term2"*' — AND stripped, words kept
    assert "term1" in result
    assert "term2" in result
    # The literal "AND" shouldn't be a search term
    parts = re.findall(r'"([^"]+)"', result)
    assert "AND" not in parts

    result = _escape_fts5_server("NEAR term1 term2")
    parts = re.findall(r'"([^"]+)"', result)
    assert "NEAR" not in parts

    # Mixed case should also be caught
    result = _escape_fts5_server("not something or other")
    parts = re.findall(r'"([^"]+)"', result)
    assert "not" not in parts
    assert "or" not in parts

    # Regular words should still work
    result = _escape_fts5_server("hello world")
    assert '"hello"' in result
    assert '"world"' in result

    print("PASS: FTS5 keyword operators stripped")


def test_fts5_empty_after_stripping():
    """If all words are FTS5 keywords, return empty match."""
    from scripts.turso import _escape_fts5_server

    result = _escape_fts5_server("AND OR NOT")
    assert result == '""'  # Empty match

    print("PASS: FTS5 empty after keyword stripping")


# ── 4. Credential leakage in error logs ──

def test_sanitize_error_strips_bearer():
    """_sanitize_error removes Bearer tokens from exception messages."""
    from scripts.turso import _sanitize_error

    fake_token = "FAKE-TEST-TOKEN-do-not-detect-as-secret-12345"
    exc = Exception(
        f"Connection failed: headers={{'Authorization': 'Bearer {fake_token}'}}"
    )
    sanitized = _sanitize_error(exc)
    assert fake_token not in sanitized
    assert "[REDACTED]" in sanitized
    assert "Connection failed" in sanitized

    print("PASS: Bearer tokens redacted from errors")


def test_sanitize_error_strips_auth_header():
    """_sanitize_error removes Authorization header values."""
    from scripts.turso import _sanitize_error

    exc = Exception("""{'Authorization': 'Bearer supersecret123', 'Content-Type': 'application/json'}""")
    sanitized = _sanitize_error(exc)
    assert "supersecret123" not in sanitized
    assert "[REDACTED]" in sanitized

    print("PASS: Authorization headers redacted from errors")


def test_sanitize_error_preserves_useful_info():
    """_sanitize_error preserves non-sensitive error details."""
    from scripts.turso import _sanitize_error

    exc = Exception("503 Service Unavailable at https://example.turso.io/v2/pipeline")
    sanitized = _sanitize_error(exc)
    assert "503" in sanitized
    assert "Service Unavailable" in sanitized

    print("PASS: Non-sensitive error details preserved")


def test_retry_uses_sanitized_errors(capsys=None):
    """_retry_with_backoff uses _sanitize_error in warning messages."""
    from scripts import turso
    import inspect
    source = inspect.getsource(turso._retry_with_backoff)
    assert "_sanitize_error" in source, "Should use _sanitize_error for error messages"

    print("PASS: _retry_with_backoff uses sanitized errors")


# ── 5. _init() thread safety ──

def test_init_has_lock():
    """_init uses double-checked locking pattern."""
    from scripts import turso
    import inspect
    source = inspect.getsource(turso._init)
    assert "_init_lock" in source, "Should use _init_lock"
    assert "with _init_lock" in source, "Should use context manager for lock"

    print("PASS: _init uses lock")


def test_init_double_check_pattern():
    """_init checks state._TOKEN both before and after acquiring lock."""
    from scripts import turso
    import inspect
    source = inspect.getsource(turso._init)

    # Should have two checks for _TOKEN — fast path + inside lock
    token_checks = [l.strip() for l in source.split('\n') if '_TOKEN is not None' in l]
    assert len(token_checks) >= 2, \
        f"Expected 2+ _TOKEN checks (double-checked locking), found {len(token_checks)}"

    print("PASS: _init double-checked locking pattern")


def test_init_concurrent_safety():
    """Multiple threads calling _init don't race on credentials."""
    from scripts import turso, state

    # Save and reset state
    old_token = state._TOKEN
    old_url = state._URL
    old_headers = state._HEADERS

    try:
        state._TOKEN = None
        state._URL = None
        state._HEADERS = None

        init_count = {"value": 0}
        original_load_env = turso._load_env_file

        def counting_load_env(path):
            init_count["value"] += 1
            return original_load_env(path)

        errors = []

        def init_thread():
            try:
                with patch.object(turso, '_load_env_file', side_effect=counting_load_env):
                    turso._init()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=init_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # No errors should occur
        assert not errors, f"Threads raised errors: {errors}"
        # Token should be set
        assert state._TOKEN is not None

    finally:
        state._TOKEN = old_token
        state._URL = old_url
        state._HEADERS = old_headers

    print("PASS: Concurrent _init is safe")


# ── 6. config_delete() read_only bypass ──

def test_config_delete_respects_readonly():
    """config_delete raises ValueError for read-only keys."""
    from scripts.config import config_delete
    from scripts.turso import _exec

    # Mock _exec to return a read-only config entry
    with patch('scripts.config._exec') as mock_exec:
        mock_exec.return_value = [{"read_only": 1}]

        try:
            config_delete("protected-key")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "read-only" in str(e).lower()

    print("PASS: config_delete rejects read-only keys")


def test_config_delete_allows_non_readonly():
    """config_delete succeeds for non-read-only keys."""
    from scripts.config import config_delete

    with patch('scripts.config._exec') as mock_exec:
        # First call (SELECT read_only) returns non-readonly
        # Second call (DELETE) succeeds
        mock_exec.side_effect = [[{"read_only": 0}], []]
        result = config_delete("mutable-key")
        assert result == True

    print("PASS: config_delete allows non-read-only keys")


def test_config_delete_allows_missing_keys():
    """config_delete succeeds when key doesn't exist."""
    from scripts.config import config_delete

    with patch('scripts.config._exec') as mock_exec:
        # First call (SELECT read_only) returns empty — key not found
        # Second call (DELETE) is a no-op
        mock_exec.side_effect = [[], []]
        result = config_delete("nonexistent-key")
        assert result == True

    print("PASS: config_delete allows missing keys")


def test_config_readonly_bypass_blocked():
    """Cannot bypass read_only via delete + re-create."""
    from scripts.config import config_delete, config_set

    with patch('scripts.config._exec') as mock_exec:
        # Simulate read-only key
        mock_exec.return_value = [{"read_only": 1}]

        # Delete should fail
        try:
            config_delete("locked-key")
            assert False, "Delete should fail for read-only"
        except ValueError:
            pass

        # Set should also fail
        try:
            config_set("locked-key", "new_value", "ops")
            assert False, "Set should fail for read-only"
        except ValueError:
            pass

    print("PASS: Read-only bypass via delete+recreate is blocked")


# ── 7. JSON decode error handling ──

def test_exec_handles_non_json_response():
    """_exec raises clear error when Turso returns non-JSON."""
    from scripts import turso, state

    old_token = state._TOKEN
    old_url = state._URL
    old_headers = state._HEADERS

    try:
        state._TOKEN = "test"
        state._URL = "https://test.turso.io"
        state._HEADERS = {"Authorization": "Bearer test"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>not json</html>"
        mock_response.json.side_effect = ValueError("No JSON")

        with patch('scripts.turso.requests.post', return_value=mock_response):
            try:
                turso._exec("SELECT 1")
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "Non-JSON" in str(e)
                assert "200" in str(e)

    finally:
        state._TOKEN = old_token
        state._URL = old_url
        state._HEADERS = old_headers

    print("PASS: _exec handles non-JSON responses")


def test_exec_batch_handles_non_json_response():
    """_exec_batch raises clear error when Turso returns non-JSON."""
    from scripts import turso, state

    old_token = state._TOKEN
    old_url = state._URL
    old_headers = state._HEADERS

    try:
        state._TOKEN = "test"
        state._URL = "https://test.turso.io"
        state._HEADERS = {"Authorization": "Bearer test"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>not json</html>"
        mock_response.json.side_effect = ValueError("No JSON")

        with patch('scripts.turso.requests.post', return_value=mock_response):
            try:
                turso._exec_batch(["SELECT 1", "SELECT 2"])
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "Non-JSON" in str(e)
                assert "200" in str(e)

    finally:
        state._TOKEN = old_token
        state._URL = old_url
        state._HEADERS = old_headers

    print("PASS: _exec_batch handles non-JSON responses")


# ── 8. Env fallback persistence (late-boot recovery) ──

def test_persist_env_fallback_writes_when_missing():
    """Writes ~/.muninn/.env from live state when no fallback file exists."""
    from scripts import state
    import importlib; boot_module = importlib.import_module("scripts.boot")
    from pathlib import Path as RealPath

    old_token, old_url = state._TOKEN, state._URL
    with tempfile.TemporaryDirectory() as tmp:
        with patch("scripts.boot.Path.home", return_value=RealPath(tmp)):
            try:
                state._TOKEN = "test-token-xyz"
                state._URL = "test.turso.io"
                wrote = boot_module._persist_env_fallback()
                assert wrote is True
                env_file = RealPath(tmp) / ".muninn" / ".env"
                assert env_file.exists()
                content = env_file.read_text()
                assert "TURSO_TOKEN=test-token-xyz" in content
                assert "TURSO_URL=test.turso.io" in content
                # Permissions should be 0600
                mode = env_file.stat().st_mode & 0o777
                assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
            finally:
                state._TOKEN, state._URL = old_token, old_url

    print("PASS: _persist_env_fallback writes ~/.muninn/.env when missing")


def test_persist_env_fallback_skips_when_file_exists():
    """Does not clobber an existing ~/.muninn/.env (user-managed creds)."""
    from scripts import state
    import importlib; boot_module = importlib.import_module("scripts.boot")
    from pathlib import Path as RealPath

    old_token, old_url = state._TOKEN, state._URL
    with tempfile.TemporaryDirectory() as tmp:
        home = RealPath(tmp)
        muninn_dir = home / ".muninn"
        muninn_dir.mkdir()
        existing = muninn_dir / ".env"
        existing.write_text("TURSO_TOKEN=existing-do-not-touch\n")

        with patch("scripts.boot.Path.home", return_value=home):
            try:
                state._TOKEN = "new-different-token"
                state._URL = "different.turso.io"
                wrote = boot_module._persist_env_fallback()
                assert wrote is False
                # File contents must be unchanged
                assert existing.read_text() == "TURSO_TOKEN=existing-do-not-touch\n"
            finally:
                state._TOKEN, state._URL = old_token, old_url

    print("PASS: _persist_env_fallback preserves existing ~/.muninn/.env")


def test_persist_env_fallback_silent_when_no_creds():
    """Returns False without raising when state has no live creds."""
    from scripts import state
    import importlib; boot_module = importlib.import_module("scripts.boot")

    old_token, old_url = state._TOKEN, state._URL
    try:
        state._TOKEN = None
        state._URL = None
        wrote = boot_module._persist_env_fallback()
        assert wrote is False
    finally:
        state._TOKEN, state._URL = old_token, old_url

    print("PASS: _persist_env_fallback returns False when no creds")


def test_persist_env_fallback_never_raises():
    """Side-effect helper must swallow all errors; boot must not break on it."""
    from scripts import state
    import importlib; boot_module = importlib.import_module("scripts.boot")
    from pathlib import Path as RealPath

    old_token, old_url = state._TOKEN, state._URL
    with tempfile.TemporaryDirectory() as tmp:
        # Create a regular file at the path where ".muninn" should be a dir.
        # mkdir(parents=True, exist_ok=True) will raise FileExistsError because
        # the path exists but isn't a directory. This works regardless of UID.
        home = RealPath(tmp)
        bogus_muninn = home / ".muninn"
        bogus_muninn.write_text("not a directory")

        try:
            with patch("scripts.boot.Path.home", return_value=home):
                state._TOKEN = "t"
                state._URL = "u"
                wrote = boot_module._persist_env_fallback()
                assert wrote is False  # Returned cleanly, no exception
        finally:
            state._TOKEN, state._URL = old_token, old_url

    print("PASS: _persist_env_fallback never raises")


# ── Run all tests ──

if __name__ == "__main__":
    tests = [
        # 1. Path traversal
        test_path_traversal_name_rejected,
        test_path_traversal_realpath_guard,
        test_install_utilities_rejects_malicious_names,
        # 2. LIKE wildcards
        test_escape_like,
        test_like_escape_in_fts5_search,
        test_like_escape_in_hints,
        # 3. FTS5 keywords
        test_fts5_strips_keywords,
        test_fts5_empty_after_stripping,
        # 4. Credential leakage
        test_sanitize_error_strips_bearer,
        test_sanitize_error_strips_auth_header,
        test_sanitize_error_preserves_useful_info,
        test_retry_uses_sanitized_errors,
        # 5. Thread safety
        test_init_has_lock,
        test_init_double_check_pattern,
        test_init_concurrent_safety,
        # 6. config_delete read_only
        test_config_delete_respects_readonly,
        test_config_delete_allows_non_readonly,
        test_config_delete_allows_missing_keys,
        test_config_readonly_bypass_blocked,
        # 7. JSON decode
        test_exec_handles_non_json_response,
        test_exec_batch_handles_non_json_response,
        # 8. Env fallback persistence
        test_persist_env_fallback_writes_when_missing,
        test_persist_env_fallback_skips_when_file_exists,
        test_persist_env_fallback_silent_when_no_creds,
        test_persist_env_fallback_never_raises,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        sys.exit(1)
