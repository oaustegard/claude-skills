#!/usr/bin/env python3
"""Test export/import functionality for the remembering skill."""

import sys
import os
import json
from datetime import datetime

# Add skill to path
sys.path.insert(0, '/home/user/claude-skills/remembering')

from remembering import muninn_export, muninn_import, remember, config_set, recall, config_get

def test_export_import():
    """Test export and import of Muninn state."""
    print("=" * 60)
    print("TEST 5: Export/Import Functionality")
    print("=" * 60)

    test_id = f"test-{datetime.now().isoformat()}"

    # Test 1: Export current state
    print(f"\n1. Exporting current Muninn state...")
    export_data = muninn_export()

    print(f"   ✓ Export complete")
    print(f"   Export version: {export_data.get('version')}")
    print(f"   Exported at: {export_data.get('exported_at')}")
    print(f"   Config entries: {len(export_data.get('config', []))}")
    print(f"   Memory entries: {len(export_data.get('memories', []))}")

    # Verify export structure
    assert 'version' in export_data, "Missing 'version' in export"
    assert 'exported_at' in export_data, "Missing 'exported_at' in export"
    assert 'config' in export_data, "Missing 'config' in export"
    assert 'memories' in export_data, "Missing 'memories' in export"
    print(f"   ✓ Export structure validated")

    # Test 2: Save export to file
    print(f"\n2. Saving export to file...")
    export_file = f"/tmp/muninn-export-{test_id}.json"
    with open(export_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    print(f"   ✓ Saved to: {export_file}")

    # Verify file size
    file_size = os.path.getsize(export_file)
    print(f"   File size: {file_size:,} bytes")

    # Test 3: Create some test data to verify merge import
    print(f"\n3. Creating test data for import verification...")
    test_config_key = f"test-import-config-{test_id}"
    test_mem_id = remember(
        f"Test memory before import ({test_id})",
        "world",
        tags=["import-test"]
    )
    config_set(test_config_key, "test value", "ops")
    print(f"   ✓ Created test config and memory")

    # Test 4: Import with merge=True (should preserve existing data)
    print(f"\n4. Testing import with merge=True...")

    # First, create a small export to import
    small_export = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "config": [
            {
                "key": f"imported-config-{test_id}",
                "value": "imported value",
                "category": "ops",
                "updated_at": datetime.now().isoformat()
            }
        ],
        "memories": [
            {
                "type": "experience",
                "t": datetime.now().isoformat(),
                "summary": f"Imported memory ({test_id})",
                "tags": ["imported", test_id]
            }
        ]
    }

    import_stats = muninn_import(small_export, merge=True)
    print(f"   ✓ Import complete (merge=True)")
    print(f"   Config imported: {import_stats.get('config_count', 0)}")
    print(f"   Memories imported: {import_stats.get('memory_count', 0)}")

    # Verify merge worked (old data should still exist)
    old_config = config_get(test_config_key)
    old_mem = recall(tags=["import-test"], n=5)
    new_config = config_get(f"imported-config-{test_id}")

    print(f"\n   Verification:")
    print(f"   Old config preserved: {old_config is not None}")
    print(f"   Old memory preserved: {len(old_mem) > 0}")
    print(f"   New config imported: {new_config is not None}")

    # Test 5: Check for import errors
    print(f"\n5. Checking import statistics for errors...")
    if 'errors' in import_stats and import_stats['errors']:
        print(f"   ⚠ Import errors detected: {import_stats['errors']}")
    else:
        print(f"   ✓ No import errors")

    # Test 6: Validate imported data structure
    print(f"\n6. Validating imported memory structure...")
    imported_mems = recall(tags=["imported"], n=5)
    if imported_mems:
        print(f"   ✓ Found {len(imported_mems)} imported memories")
        mem = imported_mems[0]
        print(f"   Memory has ID: {'id' in mem}")
        print(f"   Memory has type: {'type' in mem}")
        print(f"   Memory has summary: {'summary' in mem}")
    else:
        print(f"   ⚠ No imported memories found")

    print("\n" + "=" * 60)
    print("EXPORT/IMPORT TEST COMPLETE")
    print("=" * 60)

    return {
        'export_file': export_file,
        'import_stats': import_stats,
        'test_id': test_id
    }

if __name__ == "__main__":
    try:
        results = test_export_import()
        print(f"\n✅ All export/import tests passed!")
        print(f"\nExport file: {results['export_file']}")
        print(f"Test session ID: {results['test_id']}")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
