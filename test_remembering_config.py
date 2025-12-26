#!/usr/bin/env python3
"""Test config operations for the remembering skill."""

import sys
import os
from datetime import datetime

# Add skill to path
sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import config_set, config_get, config_delete, config_list, profile, ops

def test_config_operations():
    """Test config storage and retrieval."""
    print("=" * 60)
    print("TEST 2: Config Operations")
    print("=" * 60)

    test_id = f"test-{datetime.now().isoformat()}"

    # Test 1: Basic config set/get
    print(f"\n1. Basic config set/get...")
    config_set(f"test-key-{test_id}", "test value", "profile")
    value = config_get(f"test-key-{test_id}")
    print(f"   ✓ Set and retrieved value: {value}")
    assert value == "test value", "Value mismatch"

    # Test 2: Config categories
    print(f"\n2. Testing different categories...")
    config_set(f"test-profile-{test_id}", "profile data", "profile")
    config_set(f"test-ops-{test_id}", "ops data", "ops")
    config_set(f"test-journal-{test_id}", "journal data", "journal")
    print(f"   ✓ Created config entries in all 3 categories")

    # Test 3: Profile shorthand
    print(f"\n3. Testing profile() shorthand...")
    profile_data = profile()
    print(f"   ✓ Retrieved {len(profile_data)} profile entries")
    profile_keys = [p['key'] for p in profile_data]
    assert f"test-profile-{test_id}" in profile_keys, "Profile entry not found"

    # Test 4: Ops shorthand
    print(f"\n4. Testing ops() shorthand...")
    ops_data = ops()
    print(f"   ✓ Retrieved {len(ops_data)} ops entries")
    ops_keys = [o['key'] for o in ops_data]
    assert f"test-ops-{test_id}" in ops_keys, "Ops entry not found"

    # Test 5: Config list with filter
    print(f"\n5. Testing config_list() with category filter...")
    journal_data = config_list("journal")
    print(f"   ✓ Retrieved {len(journal_data)} journal entries")

    # Test 6: Config with char_limit constraint
    print(f"\n6. Testing char_limit constraint...")
    config_set(f"test-limited-{test_id}", "short", "profile", char_limit=100)
    print(f"   ✓ Set config with char_limit=100")

    # Try to violate char_limit
    try:
        config_set(f"test-limited-{test_id}", "x" * 150, "profile", char_limit=100)
        print(f"   ❌ ERROR: Should have raised ValueError for exceeding char_limit")
    except ValueError as e:
        print(f"   ✓ Correctly raised ValueError: {e}")

    # Test 7: Read-only constraint
    print(f"\n7. Testing read_only constraint...")
    config_set(f"test-readonly-{test_id}", "immutable value", "ops", read_only=True)
    print(f"   ✓ Set read-only config")

    # Try to modify read-only
    try:
        config_set(f"test-readonly-{test_id}", "new value", "ops")
        print(f"   ❌ ERROR: Should have raised ValueError for modifying read-only")
    except ValueError as e:
        print(f"   ✓ Correctly raised ValueError: {e}")

    # Test 8: Config delete
    print(f"\n8. Testing config delete...")
    config_set(f"test-delete-{test_id}", "to be deleted", "profile")
    config_delete(f"test-delete-{test_id}")
    deleted_value = config_get(f"test-delete-{test_id}")
    assert deleted_value is None, "Deleted config still exists"
    print(f"   ✓ Successfully deleted config entry")

    # Test 9: Invalid category
    print(f"\n9. Testing invalid category handling...")
    try:
        config_set("test-invalid", "value", "invalid_category")
        print(f"   ❌ ERROR: Should have raised ValueError for invalid category")
    except ValueError as e:
        print(f"   ✓ Correctly raised ValueError: {e}")

    # Cleanup test entries
    print(f"\n10. Cleaning up test entries...")
    config_delete(f"test-key-{test_id}")
    config_delete(f"test-profile-{test_id}")
    config_delete(f"test-ops-{test_id}")
    config_delete(f"test-journal-{test_id}")
    config_delete(f"test-limited-{test_id}")
    config_delete(f"test-readonly-{test_id}")
    print(f"   ✓ Cleanup complete")

    print("\n" + "=" * 60)
    print("CONFIG OPERATIONS TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_config_operations()
        print(f"\n✅ All config tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
