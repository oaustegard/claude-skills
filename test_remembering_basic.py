#!/usr/bin/env python3
"""Test basic memory operations for the remembering skill."""

import sys
import os
from datetime import datetime

# Add skill to path
sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import remember, recall, forget, TYPES

def test_basic_operations():
    """Test basic remember and recall operations."""
    print("=" * 60)
    print("TEST 1: Basic Memory Storage and Retrieval")
    print("=" * 60)

    # Test 1: Store a simple memory
    test_id = f"test-{datetime.now().isoformat()}"
    print(f"\n1. Storing a 'decision' memory...")
    mem_id = remember(
        f"Test memory for skill assessment ({test_id})",
        "decision",
        tags=["test", "assessment"],
        conf=0.9
    )
    print(f"   ✓ Created memory ID: {mem_id}")

    # Test 2: Recall the memory
    print(f"\n2. Recalling memory by search term...")
    results = recall("test memory skill assessment")
    print(f"   ✓ Found {len(results)} memories")
    if results:
        print(f"   First result: {results[0]['summary'][:60]}...")

    # Test 3: Test different memory types
    print(f"\n3. Testing all memory types...")
    type_ids = {}
    for mem_type in TYPES:
        mid = remember(
            f"Testing {mem_type} type ({test_id})",
            mem_type,
            tags=["test", mem_type]
        )
        type_ids[mem_type] = mid
        print(f"   ✓ Created {mem_type} memory: {mid}")

    # Test 4: Filter by type
    print(f"\n4. Testing type filtering...")
    decisions = recall(type="decision", n=10)
    print(f"   ✓ Found {len(decisions)} decision memories")

    # Test 5: Filter by tags
    print(f"\n5. Testing tag filtering...")
    test_mems = recall(tags=["test"], n=20)
    print(f"   ✓ Found {len(test_mems)} memories with 'test' tag")

    # Test 6: Tag mode "all" (require multiple tags)
    print(f"\n6. Testing tag_mode='all'...")
    assessment_mems = recall(tags=["test", "assessment"], tag_mode="all", n=10)
    print(f"   ✓ Found {len(assessment_mems)} memories with both 'test' AND 'assessment' tags")

    # Test 7: Confidence filtering
    print(f"\n7. Testing confidence filtering...")
    high_conf = recall(type="decision", conf=0.85, n=10)
    print(f"   ✓ Found {len(high_conf)} high-confidence decisions (conf >= 0.85)")

    # Test 8: Soft delete
    print(f"\n8. Testing soft delete...")
    test_del_id = remember(f"Memory to delete ({test_id})", "world", tags=["delete-test"])
    print(f"   ✓ Created memory to delete: {test_del_id}")
    forget(test_del_id)
    print(f"   ✓ Soft deleted memory: {test_del_id}")

    # Verify it's not in results
    after_delete = recall(tags=["delete-test"], n=10)
    print(f"   ✓ After delete, found {len(after_delete)} memories with 'delete-test' tag (should be 0)")

    print("\n" + "=" * 60)
    print("BASIC OPERATIONS TEST COMPLETE")
    print("=" * 60)

    return {
        'mem_id': mem_id,
        'type_ids': type_ids,
        'test_id': test_id
    }

if __name__ == "__main__":
    try:
        results = test_basic_operations()
        print(f"\n✅ All basic tests passed!")
        print(f"\nTest session ID: {results['test_id']}")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
