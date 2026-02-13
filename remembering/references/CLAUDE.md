# Muninn Memory System - Claude Code Context

**VERSION:** See SKILL.md frontmatter

---

## ⚠️ CRITICAL REQUIREMENT: VERSION BUMPING ⚠️

**BEFORE ANY COMMIT TO THIS SKILL:**

You **MUST** update `metadata.version` in `SKILL.md` frontmatter:
- Bug fixes/cleanup: Patch bump (3.3.3 → 3.3.4)
- New features/improvements: Minor bump (3.3.3 → 3.4.0)
- Breaking changes: Major bump (3.3.3 → 4.0.0)

**This is MANDATORY and NON-NEGOTIABLE.**

- Version changes trigger releases to users
- Committing code changes without a version bump = users don't get the update
- NO EXCEPTIONS - even trivial fixes require a version bump

**Workflow:**
1. Make code changes
2. Update `SKILL.md` frontmatter: `metadata.version: X.Y.Z`
3. Refresh code maps: `python mapping-codebases/scripts/codemap.py /home/user/claude-skills --skip uploads,assets`
4. Commit with version bump included in the same commit or separate commit
5. Push

**If you forget:** The PR will be rejected and you'll have to amend.

---

## Boot

Unless message contains "skip boot", IMMEDIATELY execute:

```bash
set -a; . /mnt/project/muninn.env 2>/dev/null; set +a
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/user/claude-skills')
from remembering import boot
print(boot())
EOF
```

**Note:** For Claude.ai projects, see `references/claude-ai-project-instructions.md` which uses `/mnt/skills/user` paths.


## Meta: Using Muninn During Development

**When working on this skill, USE IT for tracking development progress!** Examples:

```python
from remembering import remember, journal, recall

# Record design decisions
remember("FTS5 Porter stemmer handles morphological variants automatically", "decision",
         tags=["fts5", "search", "performance"], conf=0.9)

# Track implementation progress
journal(topics=["muninn-v0.13.0"],
        my_intent="Removed embeddings, added Porter stemmer and query expansion")

# Remember discovered issues
remember("Config read_only flag should be checked before updates", "anomaly",
         tags=["bug", "config"], conf=0.7)

# Recall related context when debugging
issues = recall("configuration", tags=["bug"], n=10)
```

This creates a **feedback loop**: improve the skill while using it to track improvements.

## Quick Reference

**Database**: Turso SQLite via HTTP API
**URL**: `https://assistant-memory-oaustegard.aws-us-east-1.turso.io`
**Auth**: JWT token in `TURSO_TOKEN` environment variable

## Environment Variables

**Option 1: Using muninn.env file (recommended for Claude Code)**

Create `/mnt/project/muninn.env` with your credentials:
```bash
TURSO_TOKEN=your_token_here
TURSO_URL=https://assistant-memory-oaustegard.aws-us-east-1.turso.io
```

The skill will automatically load this file on first use.

**Option 2: Environment variables**

Set these in your environment or Claude Code settings:

| Variable | Purpose | Default |
|----------|---------|---------|
| `TURSO_TOKEN` | JWT auth token for Turso HTTP API | (required) |
| `TURSO_URL` | Turso database URL | `https://assistant-memory-oaustegard.aws-us-east-1.turso.io` |

**Priority**: Environment variables → muninn.env → defaults

## Architecture

Two-table design:

### `config` table
Boot-time context loaded at conversation start.

```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    category TEXT,  -- 'profile', 'ops', or 'journal'
    updated_at TEXT
);
```

Categories:
- `profile`: Identity and behavior (who is Muninn, memory rules)
- `ops`: Operational guidance (API reference, skill delivery rules)
- `journal`: Session summaries for cross-conversation context

### `memories` table
Runtime memories stored during conversations.

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    type TEXT,           -- decision, world, anomaly, experience
    t TEXT,              -- ISO timestamp
    summary TEXT,        -- the actual memory content
    confidence REAL,     -- 0.0-1.0
    tags TEXT,           -- JSON array
    entities TEXT,       -- JSON array
    refs TEXT,           -- JSON array (for versioning)
    session_id TEXT,
    created_at TEXT,
    updated_at TEXT,
    deleted_at TEXT      -- soft delete
);
```

## Core API

```python
from remembering import remember, recall, forget, supersede, remember_bg
from remembering import recall_since, recall_between
from remembering import config_get, config_set, config_list, profile, ops, boot
from remembering import journal, journal_recent, journal_prune
from remembering import therapy_scope, therapy_session_count, decisions_recent
from remembering import group_by_type, group_by_tag
from remembering import handoff_pending, handoff_complete
from remembering import muninn_export, muninn_import
from remembering import strengthen, weaken
from remembering import cache_stats
# v3.4.0: Type-safe results and proactive hints
from remembering import MemoryResult, MemoryResultList, VALID_FIELDS, recall_hints
# v3.5.0: GitHub access detection
from remembering import detect_github_access

# Store a memory (type required)
id = remember("User prefers dark mode", "decision", tags=["ui"], conf=0.9)
id = remember("Quick note", "world")

# Background write (non-blocking)
remember_bg("Project uses React", "world", tags=["tech"])

# Query memories - FTS5 with Porter stemmer for morphological variants
memories = recall("dark mode")  # FTS5 search with BM25 ranking
memories = recall(type="decision", conf=0.8)  # filtered by type and confidence
memories = recall(tags=["ui"])  # by tag (any match)
memories = recall(tags=["urgent", "task"], tag_mode="all")  # require all tags
# v0.13.0: Query expansion fallback automatically extracts tags from partial results

# Query memories - date-filtered
recent = recall_since("2025-12-01T00:00:00Z", n=50)  # after timestamp
range_mems = recall_between("2025-12-01T00:00:00Z", "2025-12-26T00:00:00Z")

# Soft delete
forget(memory_id)

# Version a memory (creates new, links to old)
new_id = supersede(old_id, "Updated preference", "decision")

# Salience adjustment for memory consolidation
strengthen("memory-id", factor=1.5)  # Boost salience (default 1.5x)
weaken("memory-id", factor=0.5)      # Reduce salience (default 0.5x)

# Config operations with constraints
config_set("identity", "I am Muninn...", "profile")
config_set("bio", "Short bio", "profile", char_limit=500)  # max length
config_set("rule", "Important rule", "ops", read_only=True)  # immutable
value = config_get("identity")
all_profile = profile()  # shorthand for config_list("profile")

# Journal (session summaries)
journal(topics=["coding"], my_intent="helped with refactor")
recent = journal_recent(5)

# Therapy session helpers
cutoff, unprocessed = therapy_scope()  # get memories since last therapy session
session_count = therapy_session_count()  # count therapy sessions

# Boot - load context and populate cache
print(boot())

# Analysis helpers
mems = recall(n=50)
by_type = group_by_type(mems)  # {"decision": [...], "world": [...]}
by_tag = group_by_tag(mems)    # {"ui": [...], "bug": [...]}

# Handoff workflow (cross-environment coordination)
# Note: handoff_pending() queries for memories tagged ["handoff", "pending"]
# However, not all pending work is tagged this way - always check broader queries too
pending = handoff_pending()  # get formal pending handoffs (both tags required)
all_handoffs = recall(tags=["handoff"], n=50)  # broader search for all handoff work
handoff_complete(handoff_id, "COMPLETED: ...", version="0.5.0")  # mark done

# Export/Import
state = muninn_export()  # all config + memories as JSON
stats = muninn_import(state, merge=True)  # merge into existing
stats = muninn_import(state, merge=False)  # replace all (destructive!)
```

## Memory Types

| Type | Use For | Default Confidence |
|------|---------|-------------------|
| `decision` | User preferences, choices | 0.8 |
| `world` | External facts, project state | None |
| `anomaly` | Bugs, errors, unexpected behavior | None |
| `experience` | General observations | None |

## HTTP API Format

All database ops use Turso's HTTP pipeline API:

```python
POST /v2/pipeline
Headers: 
  Authorization: Bearer {TURSO_TOKEN}
  Content-Type: application/json

Body:
{
  "requests": [{
    "type": "execute",
    "stmt": {
      "sql": "SELECT * FROM memories WHERE type = ?",
      "args": [{"type": "text", "value": "decision"}]
    }
  }]
}
```

## Testing

Run the skill locally:

```python
import sys
sys.path.insert(0, '/home/user/claude-skills')  # repo root

from remembering import remember, recall

# Test write
id = remember("Test memory", "experience")
print(f"Created: {id}")

# Test read
results = recall("Test")
print(f"Found: {len(results)} memories")
```

Integration tests are in `tests/test_remembering.py` (excluded from release zip).

## File Structure

```
remembering/
├── SKILL.md              # User-facing documentation for Claude.ai
├── __init__.py           # Thin re-export layer (imports from scripts/)
├── scripts/              # Python package (all source code)
│   ├── __init__.py       # Main API implementation (33 exports)
│   ├── boot.py           # Boot sequence, journal, handoffs, GitHub detection
│   ├── bootstrap.py      # Schema creation/migration
│   ├── cache.py          # Local SQLite cache with FTS5
│   ├── config.py         # Config CRUD operations
│   ├── hints.py          # Proactive memory surfacing
│   ├── memory.py         # Core memory operations (remember, recall, etc.)
│   ├── result.py         # Type-safe MemoryResult wrappers
│   ├── state.py          # Module globals and constants
│   ├── turso.py          # Turso HTTP API layer
│   ├── utilities.py      # Utility code injection
│   └── defaults/         # Fallback config when Turso unavailable
│       ├── ops.json
│       └── profile.json
├── references/           # Development docs (excluded from release zip)
│   ├── CLAUDE.md         # This file (for Claude Code development)
│   └── claude-ai-project-instructions.md
└── tests/                # Integration tests (excluded from release zip)
    └── test_remembering.py
```

**Import API is unchanged**: `from remembering import boot, recall, remember` works via the thin root `__init__.py` re-export layer.

## Development Notes

**Version Bumping:** See critical requirement at top of this file.

Other development guidelines:
- Keep dependencies minimal (just `requests`)
- All timestamps are UTC ISO format
- Tags stored as JSON arrays
- Soft delete via `deleted_at` column
- `session_id` currently placeholder ("session")
- **Always test changes before creating a PR**

## Lessons for Claude Code Agents

### ALWAYS Explore Before Executing

When working with this skill, follow this sequence:

1. **Check directory structure first**:
   ```bash
   ls -la /path/to/remembering/
   ```

2. **Identify the module location**:
   - In repo root: `/home/user/claude-skills/remembering/`
   - Skills symlink: `.claude/skills/remembering -> ../../remembering`
   - Source code lives in `scripts/` subdirectory
   - Root `__init__.py` re-exports from `scripts/`, so import path is unchanged

3. **Read the code before running**:
   ```python
   # Use Read tool to examine __init__.py first
   # Then run code with proper import path
   ```

4. **Import correctly**:
   ```python
   import sys
   sys.path.insert(0, '/home/user/claude-skills')  # Repo root
   from remembering import recall, remember
   ```

### Common Mistakes to Avoid

❌ **DON'T** try to import before checking file structure
❌ **DON'T** ignore symlinks - they tell you where code lives
❌ **DON'T** guess import paths
❌ **DON'T** edit `scripts/__init__.py` without updating root `__init__.py` if needed

✅ **DO** use `ls` and `Read` tool first
✅ **DO** follow symlinks to find actual code
✅ **DO** verify imports work in a simple test first
✅ **DO** use absolute paths for sys.path
✅ **DO** remember source code is in `scripts/` directory

### Debugging Import Issues

If imports fail:
```bash
# 1. Find the actual module
find /home/user/claude-skills -name "remembering" -type d

# 2. Check what's in it
ls -la /home/user/claude-skills/remembering/

# 3. Verify __init__.py exists
test -f /home/user/claude-skills/remembering/__init__.py && echo "Found" || echo "Missing"

# 4. Test import
python3 -c "import sys; sys.path.insert(0, '/home/user/claude-skills'); import remembering; print('Success')"
```

## What's New in v3.6.0

**Priority-Based Ops Ordering** (#250): Ops entries within each topic category are now sorted by priority:
- Higher priority entries appear first within their category
- Use `config_set_priority('key', 10)` to set priority (default is 0)
- Equal-priority entries sorted alphabetically by key
- No entry recreation needed—just call `config_set_priority()`

**Dynamic OPS_TOPICS** (#251): Topic categories are now loaded from config:
- `boot()` reads topics from `config_get('ops-topics')` if available
- Falls back to built-in defaults if config is missing or invalid
- Reorganize categories without code changes via `config_set('ops-topics', json.dumps({...}), 'ops')`

```python
from remembering import config_set_priority

# Set priority for critical entries
config_set_priority('storage-rules', 10)  # Critical - appears first
config_set_priority('boot-behavior', 5)   # Elevated priority
```

## What's New in v3.5.0

**GitHub Access Detection**: Boot now automatically detects and reports GitHub access methods:
- Checks for `gh` CLI availability and authentication status
- Detects `GITHUB_TOKEN` / `GH_TOKEN` environment variables
- Reports recommended method in boot output
- Eliminates trial-and-error GitHub access patterns

**Capabilities Section**: Boot output now includes a `# CAPABILITIES` section with:
- GitHub access status and recommended method
- Installed utilities with import syntax
- Clear reporting of what's available

**Utility Code Injection**: Memories tagged `utility-code` are now:
- Automatically extracted to `/home/claude/muninn_utils/`
- Added to Python path for direct import
- Listed in boot output with import syntax

```python
from remembering import detect_github_access

# Check GitHub access independently
github = detect_github_access()
if github['available']:
    print(f"Use {github['recommended']} for GitHub operations")
```

## What's New in v3.2.0

**Session Scoping**: Filter memories by conversation or work session using `session_id` parameter.

**Security Hardening**: All SQL queries now use parameterized statements (SQL injection protection).

**Automatic Flush**: Background writes automatically flush on process exit (atexit hook prevents data loss).

**Observability**: New helpers for monitoring retrieval performance and query patterns:
- `recall_stats()` - cache hit rate, avg query time, performance metrics
- `top_queries()` - most common search patterns

**Retention Management**: New helpers for analyzing and pruning memories:
- `memory_histogram()` - distribution by type, priority, age
- `prune_by_age()` - delete old memories with priority filters
- `prune_by_priority()` - delete low-priority memories

## What's New in v3.7.0

**Parameter & Field Aliases** (#262): Common field name mistakes are now transparently resolved instead of raising errors:
- `m.content` / `m['content']` resolves to `m.summary`
- `m.conf` resolves to `m.confidence`
- `recall(limit=20)` works as alias for `recall(n=20)`

**Configurable Query Expansion** (#238): The query expansion threshold is now configurable:
- `recall("term", expansion_threshold=5)` - expand if fewer than 5 results
- `recall("term", expansion_threshold=0)` - disable expansion entirely
- Default remains 3 for backward compatibility

**Standardized Return Format** (#264): All results now include computed fields regardless of source:
- `summary_preview` (first 100 chars) always present
- `bm25_score`, `composite_rank`, `composite_score` added to VALID_FIELDS
- Results from Turso and cache are normalized to the same field set

## What's New in v3.8.0

**Auto-Credential Detection** (#263): Turso credentials are now auto-detected from well-known env file paths:
- Scans `/mnt/project/turso.env`, `/mnt/project/muninn.env`, `~/.muninn/.env`
- No manual `set -a; . turso.env; set +a` needed
- Built-in env file parser eliminates dependency on `configuring` skill

**Session Cache Support** (#237): Session-filtered queries now use the local cache:
- `recall(session_id="my-session")` uses cache (~5ms) instead of Turso (~200ms)
- `session_id` stored in `memory_index` cache table
- Automatic migration adds column on first boot

**Ops Entry Hygiene** (#265): Default ops topic mapping updated:
- Removed stale `muninn-env-loading` (superseded by #263 auto-detection)
- Consolidated `recall-fields` and `recall-discipline` into Memory Operations topic

**Unified GitHub API** (#240): New `github_api()` function:
- `from remembering import github_api`
- Automatically selects gh CLI or GITHUB_TOKEN/GH_TOKEN
- Supports GET, POST, PUT, PATCH, DELETE methods

**Repo Defaults Fallback** (#239): Boot now falls back to version-controlled defaults:
- `defaults/profile.json` and `defaults/ops.json` provide minimal config
- Used when both Turso and local cache are unavailable (fresh install + network outage)

## What's New in v4.2.0

**Decision Alternatives** (#254): Track rejected alternatives on decision memories:
- `remember(..., alternatives=[{"option": "X", "rejected": "reason"}])` stores alternatives in refs
- `get_alternatives(memory_id)` extracts alternatives from a decision memory
- `m.alternatives` computed field auto-extracted on MemoryResult objects
- Only valid for `type='decision'` memories

**Memory Consolidation** (#253): Automated clustering and summarization:
- `consolidate(dry_run=True)` previews clusters of related memories by shared tags
- `consolidate(dry_run=False, min_cluster=3)` creates summary memories and demotes originals
- Summaries are `type=world, tags=[tag, "consolidated"]` with refs to all originals
- Originals demoted to `priority=-1` (background) but not deleted
- Inspired by biological episodic-to-semantic memory conversion

```python
from remembering import remember, get_alternatives, consolidate

# Store decision with alternatives
id = remember("Chose X because Y", "decision",
              alternatives=[{"option": "A", "rejected": "Too complex"}])

# Retrieve alternatives later
alts = get_alternatives(id)

# Consolidate memories sharing common tags
result = consolidate(tags=["architecture"], dry_run=False)
```

## Known Limitations

- None currently tracked
