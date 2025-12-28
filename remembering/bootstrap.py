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
            read_only BOOLEAN DEFAULT FALSE
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

if __name__ == "__main__":
    create_tables()
    migrate_schema()
    seed_config()
    verify()
    print("\nBootstrap complete")
