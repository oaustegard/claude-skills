"""Bootstrap script for fresh Muninn database setup.

Run this once to create tables and seed minimal config.
Safe to run multiple times (uses INSERT OR IGNORE / IF NOT EXISTS).

Usage:
    python bootstrap.py
"""

import sys
import os

# Support both installed path (/mnt/skills/user) and local development
if os.path.exists('/mnt/skills/user'):
    sys.path.insert(0, '/mnt/skills/user')
    from remembering import _exec, _init, config_set
else:
    # Local development - import from current directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from __init__ import _exec, _init, config_set

def create_tables():
    """Create memories and config tables if they don't exist."""
    _init()

    _exec("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            t TEXT NOT NULL,
            summary TEXT NOT NULL,
            confidence REAL,
            tags TEXT DEFAULT '[]',
            entities TEXT DEFAULT '[]',
            refs TEXT DEFAULT '[]',
            session_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            embedding F32_BLOB(1536),
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            memory_class TEXT DEFAULT 'episodic',
            valid_from TEXT,
            valid_to TEXT,
            salience REAL DEFAULT 1.0
        )
    """)

    _exec("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            char_limit INTEGER,
            read_only BOOLEAN DEFAULT FALSE,
            boot_load INTEGER DEFAULT 1
        )
    """)

    print("Tables created/verified")

def migrate_schema():
    """Add new columns to existing tables if needed."""
    _init()

    # Add embedding column to memories if it doesn't exist
    try:
        _exec("ALTER TABLE memories ADD COLUMN embedding F32_BLOB(1536)")
        print("Added embedding column to memories table")
    except:
        pass  # Column already exists

    # Add char_limit and read_only columns to config if they don't exist
    try:
        _exec("ALTER TABLE config ADD COLUMN char_limit INTEGER")
        print("Added char_limit column to config table")
    except:
        pass  # Column already exists

    try:
        _exec("ALTER TABLE config ADD COLUMN read_only BOOLEAN DEFAULT FALSE")
        print("Added read_only column to config table")
    except:
        pass  # Column already exists

    # v2.1.0: Add boot_load column for progressive disclosure
    try:
        _exec("ALTER TABLE config ADD COLUMN boot_load INTEGER DEFAULT 1")
        print("Added boot_load column to config table")
    except:
        pass  # Column already exists

    # v0.4.0: Add importance tracking columns
    try:
        _exec("ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5")
        print("Added importance column to memories table")
    except:
        pass  # Column already exists

    try:
        _exec("ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0")
        print("Added access_count column to memories table")
    except:
        pass  # Column already exists

    try:
        _exec("ALTER TABLE memories ADD COLUMN last_accessed TEXT")
        print("Added last_accessed column to memories table")
    except:
        pass  # Column already exists

    # v0.4.0: Add episodic/semantic memory classification
    try:
        _exec("ALTER TABLE memories ADD COLUMN memory_class TEXT DEFAULT 'episodic'")
        print("Added memory_class column to memories table")
    except:
        pass  # Column already exists

    # v0.4.0: Add bitemporal tracking columns
    try:
        _exec("ALTER TABLE memories ADD COLUMN valid_from TEXT")
        print("Added valid_from column to memories table")
    except:
        pass  # Column already exists

    try:
        _exec("ALTER TABLE memories ADD COLUMN valid_to TEXT")
        print("Added valid_to column to memories table")
    except:
        pass  # Column already exists

    # v0.9.2: Add salience decay for memory ranking
    try:
        _exec("ALTER TABLE memories ADD COLUMN salience REAL DEFAULT 1.0")
        print("Added salience column to memories table")
    except:
        pass  # Column already exists

    # Create vector index for efficient semantic search
    try:
        _exec("""
            CREATE INDEX IF NOT EXISTS memories_embedding_idx ON memories (
                libsql_vector_idx(embedding, 'type=diskann', 'metric=cosine')
            )
        """)
        print("Created vector index on memories.embedding")
    except Exception as e:
        print(f"Note: Vector index creation skipped (may require newer Turso version): {e}")

    print("Schema migration complete")

def seed_config():
    """Seed minimal required config entries."""
    
    # Profile - identity and behavior
    config_set("identity", 
        "I am Muninn — named after Odin's raven of memory. Muninn means 'memory' in Old Norse. "
        "The raven flies out, gathers information, and returns to share it. "
        "This captures my purpose: persistent memory across sessions, learning from interactions with Oskar.",
        "profile")
    
    config_set("memory-behavior",
        "Agentic memory: When context is clearly worth preserving, store it immediately without "
        "asking permission. Asking 'want me to remember this?' is a failure mode.",
        "profile")
    
    # Ops - API reference
    config_set("remembering-api",
        """remembering skill API:
- remember(what, type, *, tags, conf) — type required, one of: decision, world, anomaly, experience
- remember_bg(...) — same args, fire-and-forget
- recall(search, *, n, tags, type, conf) — query memories
- forget(id) — soft delete
- supersede(id, summary, type, *, tags, conf) — version a memory
- config_get(key), config_set(key, value, category), config_delete(key), config_list(category)
- profile(), ops() — load config by category""",
        "ops")
    
    # Ops - skill workflow
    config_set("skill-delivery",
        "ALWAYS zip skills after updating them - user expects both individual files AND zip in deliverables",
        "ops")
    
    config_set("skill-presentation",
        "When presenting skill updates: show links for each changed file AND the zip file used to install/update the skill.",
        "ops")
    
    config_set("skill-scope",
        "When new capabilities are added to a skill: consider whether project instructions need updating (unless profile memory is sufficient).",
        "ops")
    
    config_set("skill-testing",
        "When updating skills: always test changes before presenting. Show test output explicitly.",
        "ops")
    
    print("Config seeded")

def verify():
    """Print current config state."""
    if os.path.exists('/mnt/skills/user'):
        from remembering import profile, ops
    else:
        from __init__ import profile, ops

    print("\n=== Profile ===")
    for p in profile():
        print(f"  {p['key']}")

    print("\n=== Ops ===")
    for o in ops():
        print(f"  {o['key']}")


def migrate_v2(dry_run: bool = True):
    """v2.0.0 schema rebuild: Remove dead columns, add priority field.

    Dead columns removed: importance, salience, memory_class, occurred,
                         session_id, valid_to, embedding, entities

    New column: priority INTEGER DEFAULT 0
      - -1: Background (low-value, can age out first)
      -  0: Normal (default)
      -  1: Important (boost in ranking)
      -  2: Critical (always surface, never auto-age)

    Args:
        dry_run: If True (default), only show what would be done without executing.
                 Set to False to actually perform the migration.

    Returns:
        dict with export data (for backup) and migration stats
    """
    import json
    _init()

    print("=== MUNINN v2.0.0 SCHEMA MIGRATION ===")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (making changes)'}")
    print()

    # Step 1: Export all non-deleted memories
    print("Step 1: Exporting memories...")
    memories = _exec("SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY t DESC")
    print(f"  Found {len(memories)} active memories")

    # Also export deleted for archive
    deleted = _exec("SELECT * FROM memories WHERE deleted_at IS NOT NULL")
    print(f"  Found {len(deleted)} deleted memories (will be preserved)")

    # Create backup structure
    backup = {
        "version": "1.0",
        "migration": "v2.0.0",
        "active_memories": memories,
        "deleted_memories": deleted,
        "timestamp": _exec("SELECT datetime('now')")[0].get("datetime('now')")
    }

    if dry_run:
        print("\n[DRY RUN] Would execute the following:")
        print("  - DROP INDEX IF EXISTS memories_embedding_idx")
        print("  - DROP TABLE memories")
        print("  - CREATE TABLE memories (new schema with priority, without dead columns)")
        print(f"  - INSERT {len(memories)} active memories with priority=0")
        print(f"  - INSERT {len(deleted)} deleted memories")
        print("\nTo execute migration, call: migrate_v2(dry_run=False)")
        return {"backup": backup, "dry_run": True}

    # Step 2: Drop old schema
    print("\nStep 2: Dropping old schema...")
    try:
        _exec("DROP INDEX IF EXISTS memories_embedding_idx")
        print("  Dropped embedding index")
    except Exception as e:
        print(f"  Note: Index drop skipped ({e})")

    _exec("DROP TABLE IF EXISTS memories")
    print("  Dropped memories table")

    # Step 3: Create new schema
    print("\nStep 3: Creating new schema...")
    _exec("""
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            t TEXT NOT NULL,
            summary TEXT NOT NULL,
            confidence REAL DEFAULT 0.8,
            tags TEXT DEFAULT '[]',
            refs TEXT DEFAULT '[]',
            priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            valid_from TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT
        )
    """)
    print("  Created new memories table")

    # Create indexes
    _exec("CREATE INDEX IF NOT EXISTS idx_memories_t ON memories(t DESC)")
    _exec("CREATE INDEX IF NOT EXISTS idx_memories_priority ON memories(priority DESC, t DESC)")
    print("  Created indexes")

    # Step 4: Import active memories
    print(f"\nStep 4: Importing {len(memories)} active memories...")
    imported = 0
    errors = []
    for m in memories:
        try:
            _exec("""
                INSERT INTO memories
                (id, type, t, summary, confidence, tags, refs, priority,
                 created_at, updated_at, deleted_at, valid_from, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, ?, ?)
            """, [
                m.get('id'),
                m.get('type'),
                m.get('t'),
                m.get('summary'),
                m.get('confidence'),
                json.dumps(m.get('tags', [])) if isinstance(m.get('tags'), list) else m.get('tags', '[]'),
                json.dumps(m.get('refs', [])) if isinstance(m.get('refs'), list) else m.get('refs', '[]'),
                m.get('created_at'),
                m.get('updated_at'),
                m.get('valid_from'),
                m.get('access_count', 0),
                m.get('last_accessed')
            ])
            imported += 1
        except Exception as e:
            errors.append(f"Memory {m.get('id')}: {e}")

    print(f"  Imported {imported} memories")
    if errors:
        print(f"  Errors: {len(errors)}")
        for e in errors[:5]:
            print(f"    {e}")

    # Step 5: Import deleted memories (preserve for archaeology)
    print(f"\nStep 5: Importing {len(deleted)} deleted memories...")
    deleted_imported = 0
    for m in deleted:
        try:
            _exec("""
                INSERT INTO memories
                (id, type, t, summary, confidence, tags, refs, priority,
                 created_at, updated_at, deleted_at, valid_from, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
            """, [
                m.get('id'),
                m.get('type'),
                m.get('t'),
                m.get('summary'),
                m.get('confidence'),
                json.dumps(m.get('tags', [])) if isinstance(m.get('tags'), list) else m.get('tags', '[]'),
                json.dumps(m.get('refs', [])) if isinstance(m.get('refs'), list) else m.get('refs', '[]'),
                m.get('created_at'),
                m.get('updated_at'),
                m.get('deleted_at'),
                m.get('valid_from'),
                m.get('access_count', 0),
                m.get('last_accessed')
            ])
            deleted_imported += 1
        except Exception as e:
            pass  # Deleted memories are best-effort

    print(f"  Imported {deleted_imported} deleted memories")

    # Verify
    print("\nStep 6: Verifying migration...")
    count = _exec("SELECT COUNT(*) as cnt FROM memories WHERE deleted_at IS NULL")[0]['cnt']
    print(f"  Active memories in new schema: {count}")

    if int(count) == len(memories):
        print("\n✅ MIGRATION COMPLETE")
    else:
        print(f"\n⚠️  WARNING: Count mismatch (expected {len(memories)}, got {count})")

    return {
        "backup": backup,
        "imported": imported,
        "deleted_imported": deleted_imported,
        "errors": errors,
        "dry_run": False
    }


def migrate_config_v2(dry_run: bool = True):
    """v2.0.0 config schema: Add load_at_boot and group_order columns.

    Args:
        dry_run: If True (default), only show what would be done.
    """
    _init()

    print("=== CONFIG SCHEMA MIGRATION ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    if dry_run:
        print("\nWould add columns:")
        print("  - load_at_boot BOOLEAN DEFAULT TRUE")
        print("  - group_order INTEGER DEFAULT 50")
        return

    try:
        _exec("ALTER TABLE config ADD COLUMN load_at_boot BOOLEAN DEFAULT TRUE")
        print("Added load_at_boot column")
    except:
        print("load_at_boot column already exists")

    try:
        _exec("ALTER TABLE config ADD COLUMN group_order INTEGER DEFAULT 50")
        print("Added group_order column")
    except:
        print("group_order column already exists")

    print("Config schema migration complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "v2":
        # Run v2.0.0 migration
        if len(sys.argv) > 2 and sys.argv[2] == "--live":
            migrate_v2(dry_run=False)
            migrate_config_v2(dry_run=False)
        else:
            migrate_v2(dry_run=True)
            migrate_config_v2(dry_run=True)
    else:
        # Normal bootstrap
        create_tables()
        migrate_schema()
        seed_config()
        verify()
        print("\nBootstrap complete")
