"""Bootstrap script for fresh Muninn database setup.

Run this once to create tables and seed minimal config.
Safe to run multiple times (uses INSERT OR IGNORE / IF NOT EXISTS).

Usage:
    python bootstrap.py
"""

import sys
import os

# Import from scripts package - add skill root (parent of scripts/) to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts import _exec, _init, config_set

def create_tables():
    """Create memories and config tables if they don't exist.

    Schema reflects v2.0.0+ with session_id re-added in v3.2.0.
    Removed columns (from v2.0.0): entities, importance, memory_class, valid_to, salience
    """
    _init()

    _exec("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            t TEXT NOT NULL,
            summary TEXT NOT NULL,
            confidence REAL DEFAULT 0.8,
            tags TEXT DEFAULT '[]',
            refs TEXT DEFAULT '[]',
            priority INTEGER DEFAULT 0,
            session_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            valid_from TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT
        )
    """)

    # Create indexes for memories table
    _exec("CREATE INDEX IF NOT EXISTS idx_memories_t ON memories(t DESC)")
    _exec("CREATE INDEX IF NOT EXISTS idx_memories_priority ON memories(priority DESC, t DESC)")
    _exec("CREATE INDEX IF NOT EXISTS idx_memories_session_id ON memories(session_id)")

    _exec("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            char_limit INTEGER,
            read_only BOOLEAN DEFAULT FALSE,
            boot_load INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0
        )
    """)

    print("Tables created/verified")

def migrate_schema():
    """Add new columns to existing v2.0.0+ tables if needed.

    Only includes migrations for current schema. Pre-v2.0.0 migrations removed.
    """
    _init()

    # Config table migrations
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

    try:
        _exec("ALTER TABLE config ADD COLUMN boot_load INTEGER DEFAULT 1")
        print("Added boot_load column to config table")
    except:
        pass  # Column already exists

    # v3.6.0: Add priority column for ordering within categories
    try:
        _exec("ALTER TABLE config ADD COLUMN priority INTEGER DEFAULT 0")
        print("Added priority column to config table")
    except:
        pass  # Column already exists

    # v3.2.0: Re-enable session_id column (was removed in v2.0.0, now re-added)
    try:
        _exec("ALTER TABLE memories ADD COLUMN session_id TEXT")
        print("Added session_id column to memories table")
    except:
        pass  # Column already exists

    # v3.2.0: Add index for session_id for better query performance
    try:
        _exec("CREATE INDEX IF NOT EXISTS idx_memories_session_id ON memories(session_id)")
        print("Added index on session_id column")
    except:
        pass  # Index already exists

    # Ensure core indexes exist (in case database was created before indexes were added)
    try:
        _exec("CREATE INDEX IF NOT EXISTS idx_memories_t ON memories(t DESC)")
        print("Added index on t column")
    except:
        pass  # Index already exists

    try:
        _exec("CREATE INDEX IF NOT EXISTS idx_memories_priority ON memories(priority DESC, t DESC)")
        print("Added index on priority column")
    except:
        pass  # Index already exists

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
    from scripts import profile, ops

    print("\n=== Profile ===")
    for p in profile():
        print(f"  {p['key']}")

    print("\n=== Ops ===")
    for o in ops():
        print(f"  {o['key']}")


if __name__ == "__main__":
    create_tables()
    migrate_schema()
    seed_config()
    verify()
    print("\nBootstrap complete")
