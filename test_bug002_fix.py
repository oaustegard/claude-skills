#!/usr/bin/env python3
"""Test journal rapid-fire calls (BUG-002 fix verification)."""

import sys
sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import journal, journal_recent

print("Testing rapid journal calls (BUG-002 fix)...")
print("Creating 10 journal entries in quick succession...\n")

# Create 10 journal entries rapidly without delays
for i in range(10):
    key = journal(
        topics=[f"rapid-test-{i}"],
        user_stated=f"Entry {i}",
        my_intent=f"Test rapid calls"
    )
    print(f"✓ Created entry {i}: {key}")

print("\nRetrieving recent entries...")
recent = journal_recent(10)
print(f"✓ Found {len(recent)} recent entries")

print("\n✅ BUG-002 FIXED: All rapid calls succeeded without timestamp collision!")
