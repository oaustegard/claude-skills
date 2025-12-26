#!/usr/bin/env python3
"""Test supersede() exclusion (BUG-003 fix verification)."""

import sys
import time
from datetime import datetime

sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import remember, supersede, recall

print("Testing supersede() exclusion (BUG-003 fix)...")
test_id = datetime.now().isoformat()

# Create original memory
print("\n1. Creating original memory...")
original_id = remember(
    f"Original preference: User likes light mode ({test_id})",
    "decision",
    tags=["supersede-test", test_id],
    conf=0.7
)
print(f"   ✓ Original ID: {original_id}")

# Verify it appears in results
print("\n2. Verifying original appears in recall()...")
results_before = recall(tags=["supersede-test", test_id], tag_mode="all", n=10)
ids_before = [m['id'] for m in results_before]
print(f"   Found {len(results_before)} memories")
print(f"   Original present: {original_id in ids_before}")

# Supersede with new version
time.sleep(0.5)
print("\n3. Superseding with updated memory...")
new_id = supersede(
    original_id,
    f"Updated preference: User likes dark mode ({test_id})",
    "decision",
    tags=["supersede-test", test_id],
    conf=0.9
)
print(f"   ✓ New ID: {new_id}")

# Check if original is now excluded
print("\n4. Verifying original is excluded after supersede()...")
results_after = recall(tags=["supersede-test", test_id], tag_mode="all", n=10)
ids_after = [m['id'] for m in results_after]

print(f"   Found {len(results_after)} memories")
print(f"   New ID present: {new_id in ids_after}")
print(f"   Original ID present: {original_id in ids_after}")

if new_id in ids_after and original_id not in ids_after:
    print("\n✅ BUG-003 FIXED: Supersede correctly excludes original!")
    print(f"   Only showing: {results_after[0]['summary'][:60]}...")
else:
    print("\n❌ BUG-003 NOT FIXED")
    print(f"   Expected: new_id present, original_id absent")
    print(f"   Actual: new={new_id in ids_after}, original={original_id in ids_after}")
    if len(results_after) > 0:
        print(f"\n   Memories found:")
        for m in results_after:
            print(f"   - {m['id']}: {m['summary'][:50]}")
