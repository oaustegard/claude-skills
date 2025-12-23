"""Bootstrap script for fresh Muninn database setup.

Run this once to create tables and seed minimal config.
Safe to run multiple times (uses INSERT OR IGNORE / IF NOT EXISTS).

Usage:
    python bootstrap.py
"""

import sys
sys.path.insert(0, '/mnt/skills/user')

from remembering import _exec, _init, config_set

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
            deleted_at TEXT
        )
    """)
    
    _exec("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    print("Tables created/verified")

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
    from remembering import profile, ops
    
    print("\n=== Profile ===")
    for p in profile():
        print(f"  {p['key']}")
    
    print("\n=== Ops ===")
    for o in ops():
        print(f"  {o['key']}")

if __name__ == "__main__":
    create_tables()
    seed_config()
    verify()
    print("\nBootstrap complete")
