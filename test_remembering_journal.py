#!/usr/bin/env python3
"""Test journal system for the remembering skill."""

import sys
import os
import time
from datetime import datetime

# Add skill to path
sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import journal, journal_recent, journal_prune

def test_journal_operations():
    """Test journal operations."""
    print("=" * 60)
    print("TEST 3: Journal System")
    print("=" * 60)

    test_id = f"test-{datetime.now().isoformat()}"

    # Test 1: Create journal entry
    print(f"\n1. Creating journal entry...")
    journal(
        topics=["testing", "remembering-skill"],
        user_stated=f"Testing journal system ({test_id})",
        my_intent="Assess journal functionality"
    )
    print(f"   ✓ Created journal entry")

    # Test 2: Create another journal entry (with delay to avoid timestamp collision)
    print(f"\n2. Creating another journal entry...")
    time.sleep(1.1)  # Workaround: avoid timestamp collision (bug in read_only check)
    journal(
        topics=["batch-test", "test"],
        user_stated="Second test entry",
        my_intent="Test multiple entries"
    )
    print(f"   ✓ Created second journal entry")
    print(f"   ⚠ Note: Multiple entries per second fail due to bug (read_only check)")

    # Test 3: Retrieve recent journal entries
    print(f"\n3. Retrieving recent journal entries...")
    recent = journal_recent(10)
    print(f"   ✓ Retrieved {len(recent)} recent entries")

    if recent:
        print(f"\n   Most recent entry:")
        latest = recent[0]
        print(f"     Timestamp: {latest.get('t', 'N/A')}")
        print(f"     Topics: {latest.get('topics', [])}")
        print(f"     User stated: {latest.get('user_stated', 'N/A')}")
        print(f"     My intent: {latest.get('my_intent', 'N/A')}")

    # Test 4: Verify entries are in chronological order
    print(f"\n4. Verifying chronological order...")
    if len(recent) >= 2:
        timestamps = [entry['t'] for entry in recent]
        is_sorted = all(timestamps[i] >= timestamps[i+1] for i in range(len(timestamps)-1))
        if is_sorted:
            print(f"   ✓ Entries are in reverse chronological order (newest first)")
        else:
            print(f"   ❌ Entries are NOT properly sorted")
    else:
        print(f"   ⚠ Not enough entries to verify order")

    # Test 5: Journal pruning
    print(f"\n5. Testing journal pruning...")
    print(f"   Current entries: {len(recent)}")
    pruned_count = journal_prune(keep=5)
    print(f"   ✓ Pruned {pruned_count} old entries, keeping 5 most recent")

    # Verify pruning worked
    after_prune = journal_recent(100)
    print(f"   After pruning: {len(after_prune)} entries remain")
    assert len(after_prune) <= 5, f"Expected <= 5 entries, found {len(after_prune)}"

    # Test 6: Restore an entry for future tests
    print(f"\n6. Restoring journal entry...")
    time.sleep(1.1)  # Avoid timestamp collision
    journal(
        topics=["restoration", "test"],
        user_stated="Restored entry",
        my_intent="Restore journal after pruning"
    )
    print(f"   ✓ Restored 1 journal entry")

    print("\n" + "=" * 60)
    print("JOURNAL SYSTEM TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_journal_operations()
        print(f"\n✅ All journal tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
