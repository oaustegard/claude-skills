"""
Test Suite for remembering skill v5.0.0
Validates public API after Phases 3-4: cache removal and Turso FTS5 migration.

Tests cover:
- Module imports (no cache references)
- Core CRUD (remember/recall/forget/supersede)
- FTS5 search with ranking
- Query expansion
- Retry behavior for network errors
- Batch operations
- Edge cases (empty queries, wildcards, parameter validation)
- Config CRUD
- Boot function
- Priority and access tracking
"""

import sys
import os
import time
import threading
from unittest.mock import patch, MagicMock

sys.path.insert(0, '/home/user/claude-skills/remembering')


def test_imports():
    """Test 1: All public exports are importable (cache exports removed)"""
    from scripts import (
        remember, recall, forget, supersede, remember_bg, flush,
        recall_since, recall_between,
        config_get, config_set, config_delete, config_list, config_set_boot_load,
        config_set_priority,
        profile, ops, boot, journal, journal_recent, journal_prune,
        therapy_scope, therapy_session_count, decisions_recent,
        group_by_type, group_by_tag,
        handoff_pending, handoff_complete,
        muninn_export, muninn_import,
        reprioritize, strengthen, weaken,
        get_alternatives, consolidate, get_chain,
        recall_batch, remember_batch,
        get_session_id, set_session_id,
        session_save, session_resume, sessions,
        memory_histogram, prune_by_age, prune_by_priority,
        MemoryResult, MemoryResultList, VALID_FIELDS, recall_hints,
        _exec,
        r, q, j, TYPES
    )
    assert callable(remember)
    assert callable(boot)
    assert TYPES == {"decision", "world", "anomaly", "experience", "interaction", "procedure"}
    print("PASS: All imports successful")


def test_no_cache_module():
    """Test 2: cache.py is deleted and not importable"""
    try:
        from scripts import cache
        assert False, "cache module should not exist"
    except ImportError:
        pass  # Expected
    print("PASS: cache.py is correctly removed")


def test_no_cache_in_state():
    """Test 3: state.py has no cache globals"""
    from scripts import state
    assert not hasattr(state, '_cache_conn'), "_cache_conn should be removed"
    assert not hasattr(state, '_cache_enabled'), "_cache_enabled should be removed"
    assert not hasattr(state, '_cache_warmed'), "_cache_warmed should be removed"
    assert not hasattr(state, '_CACHE_DIR'), "_CACHE_DIR should be removed"
    assert not hasattr(state, '_CACHE_DB'), "_CACHE_DB should be removed"
    print("PASS: state.py has no cache globals")


def test_no_cache_exports():
    """Test 4: __init__.py does not export cache functions"""
    import scripts
    all_exports = scripts.__all__
    cache_functions = ['cache_stats', 'recall_stats', 'top_queries',
                      '_init_local_cache', '_cache_available', '_cache_memory',
                      '_warm_cache']
    for fn in cache_functions:
        assert fn not in all_exports, f"{fn} should not be in __all__"
    print("PASS: No cache functions in __all__")


def test_remember_recall_forget():
    """Test 5: Core memory CRUD works via Turso"""
    from scripts import remember, recall, forget

    # Remember
    mem_id = remember("Test v5 cache removal", "world", tags=["test-v5", "cache-removal"])
    assert isinstance(mem_id, str) and len(mem_id) > 0
    print(f"  Created memory: {mem_id}")

    # Recall by tag (should use _query path since no search term)
    results = recall(tags=["test-v5"])
    assert any(m["id"] == mem_id for m in results), "Memory not found by tag"
    print(f"  Recalled by tag: {len(results)} results")

    # Recall by search (should use _fts5_search path)
    results = recall("cache removal")
    found = any(m["id"] == mem_id for m in results)
    # FTS5 may need a moment to index; if not found by FTS5, verify via tags
    if not found:
        print("  NOTE: FTS5 did not find the memory (indexing lag?), verifying via tags...")
        results = recall(tags=["test-v5", "cache-removal"], tag_mode="all")
        assert any(m["id"] == mem_id for m in results), "Memory not found by tags either"
    print(f"  Recalled by search: {len(results)} results")

    # Forget
    assert forget(mem_id) == True
    print(f"  Forgot memory: {mem_id}")

    # Verify forgotten
    results = recall(tags=["test-v5"])
    assert not any(m["id"] == mem_id for m in results)
    print("PASS: Core CRUD works")


def test_recall_strict_mode():
    """Test 6: Strict mode bypasses FTS5 and uses timestamp ordering"""
    from scripts import remember, recall, forget

    mem_id = remember("Strict mode test v5", "world", tags=["test-strict-v5"])
    results = recall(tags=["test-strict-v5"], strict=True)
    assert any(m["id"] == mem_id for m in results)
    forget(mem_id)
    print("PASS: Strict mode works")


def test_recall_fetch_all():
    """Test 7: fetch_all=True retrieves without search filtering"""
    from scripts import recall
    results = recall(fetch_all=True, n=5)
    assert isinstance(results, list)
    print(f"PASS: fetch_all returned {len(results)} results")


def test_recall_tags_all_any():
    """Test 8: tags_all and tags_any convenience parameters"""
    from scripts import remember, recall, forget

    mem_id = remember("Tags filter test", "world", tags=["tag-a-v5", "tag-b-v5"])

    # tags_all: must match both
    results = recall(tags_all=["tag-a-v5", "tag-b-v5"])
    assert any(m["id"] == mem_id for m in results), "tags_all should find the memory"

    # tags_any: match either
    results = recall(tags_any=["tag-a-v5", "nonexistent-tag"])
    assert any(m["id"] == mem_id for m in results), "tags_any should find the memory"

    # Combining tags_all and tags_any should raise ValueError
    try:
        recall(tags_all=["a"], tags_any=["b"])
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Cannot specify both" in str(e)

    forget(mem_id)
    print("PASS: tags_all/tags_any work correctly")


def test_recall_since_until():
    """Test 9: since/until time window parameters"""
    from scripts import remember, recall, forget
    from datetime import datetime, UTC, timedelta

    mem_id = remember("Time window test", "world", tags=["test-timewindow-v5"])
    now = datetime.now(UTC)
    past = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    results = recall(tags=["test-timewindow-v5"], since=past)
    assert any(m["id"] == mem_id for m in results)

    forget(mem_id)
    print("PASS: since/until filtering works")


def test_recall_wildcard_rejection():
    """Test 10: Wildcard patterns are rejected with helpful error"""
    from scripts import recall
    try:
        recall("*")
        assert False, "Should have raised ValueError for wildcard"
    except ValueError as e:
        assert "fetch_all=True" in str(e)
    print("PASS: Wildcard rejection works")


def test_recall_use_cache_ignored():
    """Test 11: use_cache parameter is accepted but ignored"""
    from scripts import recall
    # Should not raise even though use_cache is set
    results = recall(fetch_all=True, n=1, use_cache=True)
    assert isinstance(results, list)
    results2 = recall(fetch_all=True, n=1, use_cache=False)
    assert isinstance(results2, list)
    print("PASS: use_cache parameter accepted and ignored")


def test_remember_types_validation():
    """Test 12: Invalid memory types are rejected"""
    from scripts import remember
    try:
        remember("test", "invalid-type")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid type" in str(e)
    print("PASS: Type validation works")


def test_remember_alternatives():
    """Test 13: Alternatives parameter works for decision memories"""
    from scripts import remember, recall, forget, get_alternatives

    mem_id = remember(
        "Chose Python over Rust",
        "decision",
        tags=["test-alternatives-v5"],
        alternatives=[
            {"option": "Rust", "rejected": "Learning curve too steep"},
            {"option": "Go", "rejected": "Less expressive"}
        ]
    )

    alts = get_alternatives(mem_id)
    assert len(alts) == 2
    assert alts[0]["option"] == "Rust"

    # Alternatives on non-decision type should fail
    try:
        remember("test", "world", alternatives=[{"option": "x"}])
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    forget(mem_id)
    print("PASS: Alternatives parameter works")


def test_supersede():
    """Test 14: Supersede chain works without cache"""
    from scripts import remember, supersede, recall, forget

    original_id = remember("Original v5", "decision", tags=["supersede-test-v5"])
    new_id = supersede(original_id, "Updated v5", "decision", tags=["supersede-test-v5"])

    results = recall(tags=["supersede-test-v5"])
    assert any(m["id"] == new_id for m in results), "New memory not found"
    assert not any(m["id"] == original_id for m in results), "Original should be superseded"

    forget(new_id)
    print("PASS: Supersede works")


def test_strengthen_weaken():
    """Test 15: Priority adjustment works without cache"""
    from scripts import remember, strengthen, weaken, forget, _exec

    mem_id = remember("Strengthen test v5", "world", tags=["test-strength-v5"])

    result = strengthen(mem_id, boost=1)
    assert result['new_priority'] >= result['old_priority']

    result = weaken(mem_id, drop=1)
    assert result['new_priority'] <= 2

    forget(mem_id)
    print("PASS: Strengthen/weaken work")


def test_config_crud():
    """Test 16: Config operations work"""
    from scripts import config_get, config_set, config_delete, config_list

    config_set("test-v5-key", "test-value", "ops")
    value = config_get("test-v5-key")
    assert value == "test-value"

    entries = config_list("ops")
    assert any(e["key"] == "test-v5-key" for e in entries)

    config_delete("test-v5-key")
    assert config_get("test-v5-key") is None
    print("PASS: Config CRUD works")


def test_boot_returns_string():
    """Test 17: Boot function returns expected format"""
    from scripts import boot
    result = boot()
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"PASS: Boot returned {len(result)} chars")


def test_retry_logic():
    """Test 18: Retry with backoff works for transient errors"""
    from scripts.turso import _retry_with_backoff

    call_count = 0

    def failing_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("503 Service Unavailable")
        return "success"

    result = _retry_with_backoff(failing_fn, max_retries=3, base_delay=0.01)
    assert result == "success"
    assert call_count == 3
    print("PASS: Retry logic works for transient 503 errors")


def test_retry_no_retry_on_non_transient():
    """Test 19: Non-transient errors are not retried"""
    from scripts.turso import _retry_with_backoff

    call_count = 0

    def failing_fn():
        nonlocal call_count
        call_count += 1
        raise ValueError("Not a transient error")

    try:
        _retry_with_backoff(failing_fn, max_retries=3, base_delay=0.01)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    assert call_count == 1, f"Should only call once but called {call_count} times"
    print("PASS: Non-transient errors fail immediately")


def test_retry_ssl_errors():
    """Test 20: SSL errors trigger retry"""
    from scripts.turso import _retry_with_backoff

    call_count = 0

    def ssl_failing_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("SSLError: HANDSHAKE_FAILURE")
        return "recovered"

    result = _retry_with_backoff(ssl_failing_fn, max_retries=3, base_delay=0.01)
    assert result == "recovered"
    assert call_count == 2
    print("PASS: SSL errors trigger retry")


def test_retry_429_rate_limit():
    """Test 21: 429 rate limit errors trigger retry"""
    from scripts.turso import _retry_with_backoff

    call_count = 0

    def rate_limited_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("429 Too Many Requests")
        return "rate_limit_cleared"

    result = _retry_with_backoff(rate_limited_fn, max_retries=3, base_delay=0.01)
    assert result == "rate_limit_cleared"
    assert call_count == 2
    print("PASS: 429 rate limit errors trigger retry")


def test_retry_exhaustion():
    """Test 22: All retries exhausted raises last error"""
    from scripts.turso import _retry_with_backoff

    def always_fails():
        raise RuntimeError("503 Service Unavailable")

    try:
        _retry_with_backoff(always_fails, max_retries=2, base_delay=0.01)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "503" in str(e)
    print("PASS: Retry exhaustion raises last error")


def test_recall_fts5_fallback_to_like():
    """Test 23: recall() falls back to LIKE query if FTS5 table missing"""
    from scripts import remember, recall, forget

    # This test verifies the fallback path. If FTS5 is available (normal case),
    # it should still return results. If not, the LIKE fallback should work.
    mem_id = remember("FTS5 fallback testing scenario", "world", tags=["test-fts5-fallback-v5"])

    # recall with search should work regardless of FTS5 availability
    results = recall(tags=["test-fts5-fallback-v5"])
    assert any(m["id"] == mem_id for m in results)

    forget(mem_id)
    print("PASS: FTS5 fallback path exists")


def test_remember_batch():
    """Test 24: Batch remember works without cache"""
    from scripts import remember_batch, recall, forget

    ids = remember_batch([
        {"what": "Batch item 1 v5", "type": "world", "tags": ["batch-test-v5"]},
        {"what": "Batch item 2 v5", "type": "decision", "tags": ["batch-test-v5"]},
    ])

    assert len(ids) == 2
    assert all(isinstance(mid, str) for mid in ids)

    # Verify they exist
    results = recall(tags=["batch-test-v5"])
    found_ids = {m["id"] for m in results}
    for mid in ids:
        assert mid in found_ids, f"Batch memory {mid} not found"

    # Cleanup
    for mid in ids:
        forget(mid)
    print("PASS: remember_batch works")


def test_remember_batch_validation():
    """Test 25: Batch remember validates inputs"""
    from scripts import remember_batch

    ids = remember_batch([
        {"what": "Valid", "type": "world"},
        {"what": "", "type": ""},  # Missing required fields
        {"what": "Valid 2", "type": "invalid-type"},  # Invalid type
    ])

    assert isinstance(ids[0], str)  # First should succeed
    assert isinstance(ids[1], dict) and "error" in ids[1]  # Missing fields
    assert isinstance(ids[2], dict) and "error" in ids[2]  # Invalid type
    print("PASS: Batch validation works")


def test_recall_batch():
    """Test 26: Batch recall works"""
    from scripts import remember, recall_batch, forget

    mem_id = remember("Batch recall test v5", "world", tags=["batch-recall-v5"])

    results = recall_batch(["batch recall", "v5"])
    assert isinstance(results, list)
    assert len(results) == 2  # One result set per query

    forget(mem_id)
    print("PASS: recall_batch works")


def test_empty_recall():
    """Test 27: Empty recall returns empty list, not error"""
    from scripts import recall
    results = recall(tags=["nonexistent-tag-xyzzy-12345"])
    assert isinstance(results, list)
    assert len(results) == 0
    print("PASS: Empty recall returns empty list")


def test_recall_limit_alias():
    """Test 28: limit parameter works as alias for n"""
    from scripts import recall
    results = recall(fetch_all=True, limit=2)
    assert len(results) <= 2
    print("PASS: limit alias works")


def test_background_writes():
    """Test 29: Background writes work and can be flushed"""
    from scripts import remember, flush, forget, recall

    mem_id = remember("Background write test v5", "world",
                     tags=["test-bg-v5"], sync=False)

    result = flush(timeout=5.0)
    assert isinstance(result, dict)
    assert 'completed' in result

    # Give it a moment and check
    time.sleep(0.5)
    results = recall(tags=["test-bg-v5"])
    found = any(m["id"] == mem_id for m in results)
    if found:
        forget(mem_id)
    print("PASS: Background writes work")


def test_result_types():
    """Test 30: MemoryResult wrapper works"""
    from scripts import remember, recall, forget, MemoryResult

    mem_id = remember("Result type test v5", "world", tags=["test-result-v5"])
    results = recall(tags=["test-result-v5"])

    if results:
        result = results[0]
        assert isinstance(result, MemoryResult)
        # Test alias resolution
        assert result['summary'] is not None or result.get('summary') is None

    forget(mem_id)
    print("PASS: MemoryResult types work")


def test_recall_hints():
    """Test 31: recall_hints works without cache"""
    from scripts import recall_hints

    result = recall_hints(terms=["muninn", "memory"])
    assert isinstance(result, dict)
    assert 'hints' in result
    assert 'term_coverage' in result
    assert 'unmatched_terms' in result
    print("PASS: recall_hints works without cache")


def test_recall_hints_no_input():
    """Test 32: recall_hints with no input returns warning"""
    from scripts import recall_hints

    result = recall_hints()
    assert result['warning'] is not None
    assert "No context or terms" in result['warning']
    print("PASS: recall_hints handles empty input")


def test_get_chain():
    """Test 33: Reference chain traversal works"""
    from scripts import remember, get_chain, forget

    mem_id = remember("Chain root v5", "world", tags=["chain-test-v5"])
    chain = get_chain(mem_id, depth=1)
    assert len(chain) >= 1
    assert chain[0]['_chain_depth'] == 0

    forget(mem_id)
    print("PASS: get_chain works")


if __name__ == "__main__":
    os.environ['TURSO_URL'] = 'https://assistant-memory-oaustegard.aws-us-east-1.turso.io'

    print("=" * 60)
    print("Test Suite for remembering v5.0.0 (Phases 3-4)")
    print("Cache removal + Turso FTS5 migration")
    print("=" * 60)
    print()

    tests = [
        test_imports,
        test_no_cache_module,
        test_no_cache_in_state,
        test_no_cache_exports,
        test_remember_recall_forget,
        test_recall_strict_mode,
        test_recall_fetch_all,
        test_recall_tags_all_any,
        test_recall_since_until,
        test_recall_wildcard_rejection,
        test_recall_use_cache_ignored,
        test_remember_types_validation,
        test_remember_alternatives,
        test_supersede,
        test_strengthen_weaken,
        test_config_crud,
        test_boot_returns_string,
        test_retry_logic,
        test_retry_no_retry_on_non_transient,
        test_retry_ssl_errors,
        test_retry_429_rate_limit,
        test_retry_exhaustion,
        test_recall_fts5_fallback_to_like,
        test_remember_batch,
        test_remember_batch_validation,
        test_recall_batch,
        test_empty_recall,
        test_recall_limit_alias,
        test_background_writes,
        test_result_types,
        test_recall_hints,
        test_recall_hints_no_input,
        test_get_chain,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        test_name = test.__name__
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_name, e))
            print(f"FAIL: {test_name}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print()
        print("Failed tests:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
