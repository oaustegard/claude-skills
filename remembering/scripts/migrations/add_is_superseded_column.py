"""Reversible migration: add is_superseded column to memories table.

Replaces the `id NOT IN (SELECT value FROM memories, json_each(refs) ...)`
subquery in recall — the top Turso row-read offender on the 7-day dashboard
(~60% of total reads). The new column is flag-maintained on insert/supersede
and recomputed on forget(); recall queries prune via a compact index.

Usage:
    python add_is_superseded_column.py              # Apply migration
    python add_is_superseded_column.py --status     # Show column + backfill state
    python add_is_superseded_column.py --dry-run    # Preview changes without applying
    python add_is_superseded_column.py --rollback   # Drop column + index (DESTRUCTIVE)

Idempotent: safe to run repeatedly. The boot sequence also runs this on every
boot via scripts.boot._ensure_is_superseded_schema(), so most deployments never
need to invoke this manually — it exists for explicit diagnostics and rollback.
"""

import sys
import argparse
from pathlib import Path

# Ensure remembering package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.turso import _exec, _init


def column_exists() -> bool:
    """Return True if is_superseded is already a column of memories."""
    rows = _exec("PRAGMA table_info(memories)")
    return any(r.get("name") == "is_superseded" for r in rows)


def index_exists() -> bool:
    """Return True if idx_memories_active already exists."""
    rows = _exec(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        ["idx_memories_active"],
    )
    return bool(rows)


def backfill_needed_count() -> int:
    """Count memories that would be flagged by a fresh backfill."""
    rows = _exec("""
        SELECT COUNT(DISTINCT value) AS n
        FROM memories, json_each(refs)
        WHERE deleted_at IS NULL AND value IS NOT NULL
    """)
    return int(rows[0].get("n", 0)) if rows else 0


def currently_flagged_count() -> int:
    """Count memories currently marked is_superseded=1."""
    try:
        rows = _exec("SELECT COUNT(*) AS n FROM memories WHERE is_superseded = 1")
        return int(rows[0].get("n", 0)) if rows else 0
    except Exception:
        return 0


def status():
    """Print current migration state."""
    _init()
    print(f"is_superseded column exists:  {column_exists()}")
    print(f"idx_memories_active exists:   {index_exists()}")
    print(f"Memories that SHOULD be flagged (from refs): {backfill_needed_count()}")
    if column_exists():
        print(f"Memories currently flagged:   {currently_flagged_count()}")


def apply(dry_run: bool = False):
    """Apply the migration: ALTER + INDEX + backfill."""
    _init()

    if column_exists():
        print("is_superseded column already exists — skipping ALTER")
        did_alter = False
    else:
        if dry_run:
            print("[dry-run] would: ALTER TABLE memories ADD COLUMN is_superseded INTEGER NOT NULL DEFAULT 0")
            did_alter = True
        else:
            _exec("ALTER TABLE memories ADD COLUMN is_superseded INTEGER NOT NULL DEFAULT 0")
            print("Added is_superseded column")
            did_alter = True

    if index_exists():
        print("idx_memories_active already exists — skipping CREATE INDEX")
    elif dry_run:
        print("[dry-run] would: CREATE INDEX idx_memories_active ON memories(is_superseded, deleted_at)")
    else:
        _exec("CREATE INDEX idx_memories_active ON memories(is_superseded, deleted_at)")
        print("Created idx_memories_active")

    if did_alter:
        expected = backfill_needed_count()
        if dry_run:
            print(f"[dry-run] would backfill is_superseded=1 on {expected} memories")
        else:
            _exec("""
                UPDATE memories SET is_superseded = 1
                WHERE id IN (
                    SELECT DISTINCT value FROM memories, json_each(refs)
                    WHERE deleted_at IS NULL AND value IS NOT NULL
                )
            """)
            flagged = currently_flagged_count()
            print(f"Backfill complete: {flagged} memories flagged (expected {expected})")
    else:
        print("Skipping backfill (column was already present)")


def rollback():
    """Drop the column and index. DESTRUCTIVE — removes the flag; recall
    performance reverts to the old json_each subquery path.

    NOTE: After rollback, the updated query code will fail until reverted. Only
    use this if you are also reverting the code changes in the same commit.
    """
    _init()

    print("ROLLBACK: this will drop is_superseded and idx_memories_active.")
    print("The updated recall code expects this column — roll back the code too,")
    print("or recall queries will fail with 'no such column: is_superseded'.")
    confirm = input("Type 'yes' to proceed: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    if index_exists():
        _exec("DROP INDEX idx_memories_active")
        print("Dropped idx_memories_active")

    if column_exists():
        # SQLite supports DROP COLUMN since 3.35.0 (2021). Turso is modern.
        _exec("ALTER TABLE memories DROP COLUMN is_superseded")
        print("Dropped is_superseded column")

    print("Rollback complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="Show current migration state")
    group.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    group.add_argument("--rollback", action="store_true", help="Drop column + index (DESTRUCTIVE)")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.rollback:
        rollback()
    else:
        apply(dry_run=args.dry_run)
