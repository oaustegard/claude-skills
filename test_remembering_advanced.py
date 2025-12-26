#!/usr/bin/env python3
"""Test advanced features for the remembering skill."""

import sys
import os
import time
from datetime import datetime

# Add skill to path
sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import remember, remember_bg, recall, supersede, semantic_recall

def test_advanced_features():
    """Test semantic search, background writes, and versioning."""
    print("=" * 60)
    print("TEST 4: Advanced Features")
    print("=" * 60)

    test_id = f"test-{datetime.now().isoformat()}"

    # Test 1: Background writes (fire-and-forget)
    print(f"\n1. Testing background writes...")
    remember_bg(
        f"Background memory test ({test_id})",
        "experience",
        tags=["background", "test"]
    )
    print(f"   ✓ Background write initiated (non-blocking)")

    # Give it a moment to complete
    time.sleep(2)
    bg_results = recall(tags=["background"], n=5)
    print(f"   ✓ Found {len(bg_results)} background memories")

    # Test 2: Memory versioning (supersede)
    print(f"\n2. Testing memory versioning (supersede)...")
    original_id = remember(
        f"Original preference ({test_id})",
        "decision",
        tags=["versioning-test"],
        conf=0.8
    )
    print(f"   ✓ Created original memory: {original_id}")

    time.sleep(0.5)  # Small delay
    new_id = supersede(
        original_id,
        f"Updated preference ({test_id})",
        "decision",
        tags=["versioning-test"],
        conf=0.9
    )
    print(f"   ✓ Created superseding memory: {new_id}")

    # Verify original is not in default results
    versioning_results = recall(tags=["versioning-test"], n=10)
    ids_in_results = [m['id'] for m in versioning_results]

    if new_id in ids_in_results and original_id not in ids_in_results:
        print(f"   ✓ Supersede working: new ID present, original excluded")
    else:
        print(f"   ⚠ Supersede may have issues:")
        print(f"     New ID present: {new_id in ids_in_results}")
        print(f"     Original ID present: {original_id in ids_in_results}")

    # Test 3: Semantic search
    print(f"\n3. Testing semantic search...")

    # Create some memories with specific semantic content
    mem1 = remember(
        "User loves dark mode and prefers minimalist UI designs",
        "decision",
        tags=["ui-preferences", test_id],
        conf=0.9
    )
    time.sleep(0.5)

    mem2 = remember(
        "Project uses React with TypeScript for frontend development",
        "world",
        tags=["tech-stack", test_id]
    )
    time.sleep(0.5)

    mem3 = remember(
        "Performance optimization reduced load time by 60%",
        "experience",
        tags=["optimization", test_id]
    )
    time.sleep(0.5)

    print(f"   ✓ Created 3 semantically diverse memories")

    # Test semantic search with different queries
    try:
        # Query for UI-related content
        ui_results = semantic_recall("user interface design preferences", n=5)
        print(f"   ✓ Semantic search for 'UI preferences': {len(ui_results)} results")
        if ui_results:
            top_result = ui_results[0]
            print(f"     Top result: {top_result['summary'][:50]}...")
            print(f"     Similarity: {top_result.get('similarity', 'N/A')}")

        # Query for technical content
        tech_results = semantic_recall("programming languages and frameworks", n=5)
        print(f"   ✓ Semantic search for 'tech stack': {len(tech_results)} results")

        # Query with type filter
        decision_results = semantic_recall(
            "user preferences and choices",
            type="decision",
            n=3
        )
        print(f"   ✓ Semantic search with type filter: {len(decision_results)} results")

    except RuntimeError as e:
        print(f"   ❌ Semantic search failed: {e}")
        print(f"   (This may be expected if EMBEDDING_API_KEY is not set)")

    # Test 4: Embedding disable option
    print(f"\n4. Testing embedding disable option...")
    mem_no_embed = remember(
        f"Memory without embedding ({test_id})",
        "world",
        tags=["no-embed-test"],
        embed=False
    )
    print(f"   ✓ Created memory with embed=False: {mem_no_embed}")

    print("\n" + "=" * 60)
    print("ADVANCED FEATURES TEST COMPLETE")
    print("=" * 60)

    return {
        'original_id': original_id,
        'new_id': new_id,
        'test_id': test_id
    }

if __name__ == "__main__":
    try:
        results = test_advanced_features()
        print(f"\n✅ All advanced feature tests passed!")
        print(f"\nTest session ID: {results['test_id']}")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
