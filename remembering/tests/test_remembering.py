"""
MVP Test Suite for remembering refactoring
Tests validate that public API remains functional after module split
"""

import sys
sys.path.insert(0, '/home/user/claude-skills')


def test_imports():
    """Test 1: All public exports are importable"""
    from remembering import (
        remember, recall, forget, supersede, remember_bg, flush,
        recall_since, recall_between,
        config_get, config_set, config_delete, config_list, config_set_boot_load,
        profile, ops, boot, journal, journal_recent, journal_prune,
        therapy_scope, therapy_session_count, decisions_recent,
        group_by_type, group_by_tag,
        handoff_pending, handoff_complete,
        muninn_export, muninn_import,
        cache_stats, reprioritize,
        r, q, j, TYPES
    )
    assert callable(remember)
    assert callable(boot)
    assert TYPES == {"decision", "world", "anomaly", "experience"}
    print("✓ Test 1: All imports successful")


def test_remember_recall_forget():
    """Test 2: Core memory operations work"""
    from remembering import remember, recall, forget

    # Remember
    mem_id = remember("Test memory for refactor validation", "world", tags=["test", "refactor"])
    assert isinstance(mem_id, str)
    assert len(mem_id) > 0
    print(f"✓ Created memory: {mem_id}")

    # Recall by tag
    results = recall(tags=["refactor"])
    assert any(m["id"] == mem_id for m in results)
    print(f"✓ Recalled by tag: found {len(results)} results")

    # Recall by search
    results = recall("refactor validation")
    assert any(m["id"] == mem_id for m in results)
    print(f"✓ Recalled by search: found {len(results)} results")

    # Forget
    assert forget(mem_id) == True
    print(f"✓ Forgot memory: {mem_id}")

    # Verify forgotten
    results = recall(tags=["refactor"])
    assert not any(m["id"] == mem_id for m in results)
    print("✓ Verified memory was forgotten")


def test_config_crud():
    """Test 3: Config operations work"""
    from remembering import config_get, config_set, config_delete, config_list

    # Set (using 'ops' as a valid category)
    config_set("test-refactor-key", "test-value", "ops")
    print("✓ Config set")

    # Get
    value = config_get("test-refactor-key")
    assert value == "test-value", f"Expected 'test-value', got {value}"
    print(f"✓ Config get: {value}")

    # List
    entries = config_list("ops")
    assert any(e["key"] == "test-refactor-key" for e in entries)
    print(f"✓ Config list: found {len(entries)} entries in ops")

    # Delete
    assert config_delete("test-refactor-key") == True
    assert config_get("test-refactor-key") is None
    print("✓ Config delete successful")


def test_boot_returns_string():
    """Test 4: Boot function returns expected format"""
    from remembering import boot
    result = boot()
    assert isinstance(result, str)
    assert "PROFILE" in result or "identity" in result.lower()
    print(f"✓ Boot returned string ({len(result)} chars)")


def test_supersede():
    """Test 5: Supersede chain works"""
    from remembering import remember, supersede, recall, forget

    original_id = remember("Original content", "decision", tags=["supersede-test"])
    print(f"✓ Created original: {original_id}")

    new_id = supersede(original_id, "Updated content", "decision", tags=["supersede-test"])
    print(f"✓ Created superseding memory: {new_id}")

    # New memory exists
    results = recall(tags=["supersede-test"])
    assert any(m["id"] == new_id for m in results), "New memory not found"
    print(f"✓ New memory found in results")

    # Original should be gone (superseded)
    assert not any(m["id"] == original_id for m in results), "Original still present"
    print("✓ Original memory was superseded")

    # Cleanup
    forget(new_id)
    print("✓ Cleanup complete")


def test_cache_stats():
    """Test 6: Cache stats function works"""
    from remembering import cache_stats
    stats = cache_stats()
    assert isinstance(stats, dict)
    assert "index_count" in stats or "enabled" in stats
    print(f"✓ Cache stats: {stats}")


if __name__ == "__main__":
    import os
    os.environ['TURSO_URL'] = 'https://assistant-memory-oaustegard.aws-us-east-1.turso.io'

    print("=" * 60)
    print("Running MVP Test Suite for remembering refactoring")
    print("=" * 60)
    print()

    tests = [
        test_imports,
        test_remember_recall_forget,
        test_config_crud,
        test_boot_returns_string,
        test_supersede,
        test_cache_stats,
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n{test.__name__}: {test.__doc__}")
        print("-" * 60)
        try:
            test()
            passed += 1
            print(f"✅ PASSED: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"❌ FAILED: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
