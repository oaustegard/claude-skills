"""Reversible migration: restructure boot output by demoting reference entries.

Moves low-signal ops entries from boot_load=1 to boot_load=0 (reference-only).
These entries remain accessible via config_get() but no longer appear in boot output.

Also consolidates redundant entries by demoting duplicates.

Usage:
    python restructure_boot_v1.py              # Apply migration
    python restructure_boot_v1.py --rollback   # Restore from snapshot
    python restructure_boot_v1.py --dry-run    # Preview changes without applying
    python restructure_boot_v1.py --status     # Show current boot_load values for affected keys
"""

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

# Ensure remembering package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.config import config_list, config_get, config_set
from scripts.boot import boot

SNAPSHOT_PATH = Path(__file__).parent / "restructure_boot_v1_snapshot.json"

# --- Entries to demote to boot_load=0 (reference-only) ---
# Each entry: (key, reason)
DEMOTE_TO_REFERENCE = [
    ("jq-install", "One-liner setup recipe"),
    ("python-remembering-setup", "Import pattern reference"),
    ("muninn-env-loading", "Credential paths (auto-detected since #263)"),
    ("bsky-feed-shortcuts", "Feed URIs, rarely needed"),
    ("github-issues", "Setup commands + detailed workflow"),
    ("memory-backup", "Backup procedure, therapy-time only"),
    ("memory-consolidation", "Therapy-time only"),
    ("serendipity-usage", "Therapy-time only"),
    ("utility-code-storage", "Storage format spec, look up when needed"),
    ("recall-triggers", "Machine-maintained 260+ tag JSON; recall_hints() reads via config_get()"),
    ("decision-alternatives", "API usage pattern example"),
    ("repo-review-workflow", "Brief reference"),
    ("muninn-utils-workflow", "Utility editing workflow"),
    ("therapy-experience-layer-audit", "Therapy sub-procedure"),
    ("url-retrieval-assistance", "Situational, 3 lines"),
    ("file-first-analysis", "Subsumed by task-deliver-workflow"),
    ("interaction-memories", "Template, look up when storing"),
    ("large-memory-preamble", "Template, look up when storing"),
    ("resource-before-storage", "Sub-rule of storage-discipline"),
]

# --- Redundant entries to demote (keep the survivor, demote the duplicate) ---
# Each: (demote_key, survivor_key, reason)
CONSOLIDATE = [
    ("recall-before-solutions", "recall-discipline",
     "Both say 'recall() before responding'; recall-discipline is the canonical version"),
    ("boot-output-hygiene", "boot-behavior",
     "Both say 'boot output is context, not deliverable'; boot-behavior is canonical"),
    ("analysis-workflow", "task-deliver-workflow",
     "analysis-workflow is subsumed by task-deliver-workflow"),
]


def _set_boot_load(key: str, value: int) -> bool:
    """Set boot_load flag on a config entry. Returns True if entry exists."""
    from scripts.turso import _exec
    rows = _exec(
        "UPDATE config SET boot_load = ? WHERE key = ? AND category = 'ops' RETURNING key",
        [value, key]
    )
    return len(rows) > 0


def snapshot() -> dict:
    """Capture current boot_load state for all affected keys."""
    all_ops = config_list("ops")
    affected_keys = set(k for k, _ in DEMOTE_TO_REFERENCE)
    affected_keys.update(k for k, _, _ in CONSOLIDATE)

    state = {}
    for o in all_ops:
        if o['key'] in affected_keys:
            state[o['key']] = {
                'boot_load': o.get('boot_load', 1),
                'value_length': len(o.get('value', '')),
            }
    return state


def apply_migration(dry_run: bool = False) -> dict:
    """Apply the migration. Returns summary of changes."""
    # Take snapshot before changes
    pre_state = snapshot()

    if not dry_run:
        SNAPSHOT_PATH.write_text(json.dumps({
            'timestamp': datetime.now(UTC).isoformat(),
            'pre_state': pre_state,
        }, indent=2))

    results = {
        'demoted': [],
        'consolidated': [],
        'skipped': [],
        'already_reference': [],
    }

    # Demote reference entries
    for key, reason in DEMOTE_TO_REFERENCE:
        current = pre_state.get(key, {}).get('boot_load', 1)
        # Normalize string/int comparison
        if str(current) == '0':
            results['already_reference'].append(key)
            continue

        if dry_run:
            results['demoted'].append((key, reason))
        else:
            if _set_boot_load(key, 0):
                results['demoted'].append((key, reason))
            else:
                results['skipped'].append((key, "not found in database"))

    # Consolidate redundant entries (demote the duplicate)
    for demote_key, survivor_key, reason in CONSOLIDATE:
        current = pre_state.get(demote_key, {}).get('boot_load', 1)
        if str(current) == '0':
            results['already_reference'].append(demote_key)
            continue

        if dry_run:
            results['consolidated'].append((demote_key, survivor_key, reason))
        else:
            if _set_boot_load(demote_key, 0):
                results['consolidated'].append((demote_key, survivor_key, reason))
            else:
                results['skipped'].append((demote_key, "not found in database"))

    return results


def rollback() -> dict:
    """Rollback to pre-migration state using snapshot."""
    if not SNAPSHOT_PATH.exists():
        return {'error': f'No snapshot found at {SNAPSHOT_PATH}'}

    data = json.loads(SNAPSHOT_PATH.read_text())
    pre_state = data['pre_state']

    restored = []
    for key, info in pre_state.items():
        boot_load = info.get('boot_load', 1)
        # Normalize to int
        bl_int = int(boot_load) if str(boot_load).isdigit() else 1
        if _set_boot_load(key, bl_int):
            restored.append(key)

    return {
        'restored': restored,
        'snapshot_timestamp': data.get('timestamp'),
    }


def show_status() -> None:
    """Show current boot_load values for all affected keys."""
    all_ops = config_list("ops")
    ops_by_key = {o['key']: o for o in all_ops}

    print("--- Demote candidates ---")
    for key, reason in DEMOTE_TO_REFERENCE:
        o = ops_by_key.get(key)
        if o:
            bl = o.get('boot_load', 1)
            val_len = len(o.get('value', ''))
            status = "REF" if str(bl) == '0' else "BOOT"
            print(f"  [{status}] {key} ({val_len} chars) — {reason}")
        else:
            print(f"  [MISSING] {key}")

    print("\n--- Consolidation candidates ---")
    for demote_key, survivor_key, reason in CONSOLIDATE:
        o = ops_by_key.get(demote_key)
        s = ops_by_key.get(survivor_key)
        if o:
            bl = o.get('boot_load', 1)
            status = "REF" if str(bl) == '0' else "BOOT"
            print(f"  [{status}] {demote_key} → {survivor_key} — {reason}")
        else:
            print(f"  [MISSING] {demote_key}")


def main():
    args = sys.argv[1:]

    if '--status' in args:
        show_status()
        return

    if '--rollback' in args:
        print("Rolling back migration...")
        result = rollback()
        if 'error' in result:
            print(f"ERROR: {result['error']}")
            sys.exit(1)
        print(f"Restored {len(result['restored'])} entries from snapshot ({result['snapshot_timestamp']})")
        print(f"Keys: {', '.join(result['restored'])}")

        # Show new boot metrics
        output = boot()
        print(f"\nPost-rollback boot: {len(output.splitlines())} lines / {len(output)} bytes")
        return

    dry_run = '--dry-run' in args
    mode = "DRY RUN" if dry_run else "APPLYING"
    print(f"--- {mode}: Restructure Boot v1 ---\n")

    # Pre-migration metrics
    pre_output = boot()
    pre_lines = len(pre_output.splitlines())
    pre_bytes = len(pre_output)
    print(f"Before: {pre_lines} lines / {pre_bytes} bytes")

    result = apply_migration(dry_run=dry_run)

    print(f"\nDemoted to reference ({len(result['demoted'])}):")
    for key, reason in result['demoted']:
        print(f"  {key} — {reason}")

    print(f"\nConsolidated ({len(result['consolidated'])}):")
    for demote, survivor, reason in result['consolidated']:
        print(f"  {demote} → {survivor} — {reason}")

    if result['already_reference']:
        print(f"\nAlready reference ({len(result['already_reference'])}): {', '.join(result['already_reference'])}")

    if result['skipped']:
        print(f"\nSkipped ({len(result['skipped'])}):")
        for key, reason in result['skipped']:
            print(f"  {key} — {reason}")

    if not dry_run:
        # Post-migration metrics (need fresh boot with cleared OPS_TOPICS cache)
        import scripts.boot as boot_module
        boot_module.OPS_TOPICS = None
        boot_module._OPS_KEY_TO_TOPIC = None
        post_output = boot_module.boot()
        post_lines = len(post_output.splitlines())
        post_bytes = len(post_output)
        print(f"\nAfter:  {post_lines} lines / {post_bytes} bytes")
        print(f"Saved:  {pre_lines - post_lines} lines / {pre_bytes - post_bytes} bytes")
        print(f"\nSnapshot saved to: {SNAPSHOT_PATH}")
    else:
        print(f"\nEstimated entries to move: {len(result['demoted']) + len(result['consolidated'])}")
        print("Run without --dry-run to apply.")


if __name__ == '__main__':
    main()
