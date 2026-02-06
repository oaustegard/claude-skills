# Remembering - Advanced Operations Reference

Detailed documentation for advanced features. Core workflow is in [SKILL.md](../SKILL.md).

## Boot CAPABILITIES Section (v3.5.0)

Boot includes a `# CAPABILITIES` section reporting:

**GitHub Access:**
- Detects `gh` CLI availability and authentication status
- Checks for `GITHUB_TOKEN` / `GH_TOKEN` environment variables
- Reports recommended method (gh-cli preferred when authenticated)
- Shows authenticated user when available

```
# CAPABILITIES

## GitHub Access
  Status: Available
  Methods: gh-cli, api-token
  Recommended: gh-cli
  gh user: oaustegard
  Usage: gh pr view, gh issue list, gh api repos/...
```

**Utilities:**
- Extracts utility-code memories to `/home/claude/muninn_utils/`
- Adds to Python path for direct import
- Lists available utilities with import syntax

### Detecting GitHub Access Programmatically

```python
from remembering import detect_github_access

github = detect_github_access()
if github['available']:
    print(f"Use {github['recommended']} for GitHub operations")
    if github['gh_cli'] and github['gh_cli']['authenticated']:
        print(f"Authenticated as: {github['gh_cli']['user']}")
```

Returns:
```python
{
    'available': True,
    'methods': ['gh-cli', 'api-token'],
    'recommended': 'gh-cli',
    'gh_cli': {'path': '/usr/bin/gh', 'authenticated': True, 'user': 'username'},
    'api_token': True
}
```

## Progressive Disclosure (v2.1.0)

Ops entries can be marked as **boot-loaded** (default) or **reference-only** to reduce boot() output size:

```python
from remembering import config_set_boot_load, ops

# Mark entry as reference-only (won't load at boot)
config_set_boot_load('github-api-endpoints', False)
config_set_boot_load('container-limits', False)

# Mark entry as boot-loaded (loads at boot)
config_set_boot_load('storage-discipline', True)

# Query ops with filtering
boot_ops = ops()                          # Only boot-loaded entries (default)
all_ops = ops(include_reference=True)     # All entries (boot + reference)
```

**How it works:**
- `boot()` outputs only ops with `boot_load=1` (reduces token usage at boot)
- Reference-only ops (`boot_load=0`) appear in a **Reference Entries** index at the end of boot output
- Reference entries remain fully accessible via `config_get(key)` when needed

## Priority-Based Ordering (v3.6.0)

Ops entries within each topic category are sorted by priority (descending). Critical entries appear first.

```python
from remembering import config_set_priority

# Set priority for critical entries (higher = more important)
config_set_priority('storage-rules', 10)       # Critical - show first in category
config_set_priority('boot-behavior', 5)        # Elevated priority
config_set_priority('fly-command', 0)          # Normal priority (default)
```

## Dynamic Topic Categories (v3.6.0)

Topic categories can be loaded from config instead of being hardcoded:

```python
from remembering import config_set, config_get
import json

# View current topic mapping
topics = json.loads(config_get('ops-topics') or '{}')

# Update topic mapping
new_topics = {
    'Core Boot & Behavior': ['boot-behavior', 'dev-workflow'],
    'Memory Operations': ['remembering-api', 'storage-rules'],
    'My Custom Category': ['my-key-1', 'my-key-2']
}
config_set('ops-topics', json.dumps(new_topics), 'ops')
```

## Priority System (v2.0.0)

Memories have a priority field that affects ranking in search results:

| Priority | Value | Description |
|----------|-------|-------------|
| Background | -1 | Low-value, can age out first |
| Normal | 0 | Default for new memories |
| Important | 1 | Boosted in ranking |
| Critical | 2 | Always surface, never auto-age |

```python
from remembering import remember, reprioritize

# Set priority at creation
remember("Critical security finding", "anomaly", tags=["security"], priority=2)

# Adjust priority later
reprioritize("memory-uuid", priority=1)  # Upgrade to important
```

**Ranking formula:**
```
score = bm25_score * recency_weight * (1 + priority * 0.5)
```

### Memory Consolidation (v3.3.0)

Biological memory consolidation pattern: memories that participate in active cognition consolidate more strongly.

```python
from remembering import strengthen, weaken, recall

# Strengthen a memory (increment priority, max 2)
result = strengthen("memory-uuid", boost=1)

# Weaken a memory (decrement priority, min -1)
result = weaken("memory-uuid", drop=1)

# Auto-strengthen top results during recall (opt-in)
results = recall("important topic", auto_strengthen=True, n=10)
```

## Date-Filtered Queries

Query memories by temporal range:

```python
from remembering import recall_since, recall_between

# Get memories after a specific timestamp
recent = recall_since("2025-12-01T00:00:00Z", n=50)
recent_bugs = recall_since("2025-12-20T00:00:00Z", type="anomaly", tags=["critical"])

# Get memories within a time range
december = recall_between("2025-12-01T00:00:00Z", "2025-12-31T23:59:59Z", n=100)
```

**Notes:**
- Timestamps are exclusive (use `>` and `<` not `>=` and `<=`)
- Supports all standard filters: `search`, `type`, `tags`, `tag_mode`
- Sorted by timestamp descending (newest first)

## Therapy Helpers

Support for reflection and memory consolidation workflows:

```python
from remembering import therapy_scope, therapy_session_count

# Get unprocessed memories since last therapy session
cutoff_time, unprocessed_memories = therapy_scope()

# Count how many therapy sessions have been recorded
count = therapy_session_count()
```

**Therapy session workflow:**
1. Call `therapy_scope()` to get unprocessed memories
2. Analyze and consolidate memories (group patterns, extract insights)
3. Record therapy session completion:
   ```python
   remember(f"Therapy Session #{count+1}: Consolidated {len(unprocessed)} memories...",
            "experience", tags=["therapy"])
   ```

## Analysis Helpers

Group and organize memories for pattern detection:

```python
from remembering import group_by_type, group_by_tag

# Get memories and group by type
memories = recall(n=100)
by_type = group_by_type(memories)
# Returns: {"decision": [...], "world": [...], "anomaly": [...], "experience": [...]}

# Group by tags
by_tag = group_by_tag(memories)
# Note: Memories with multiple tags appear under each tag
```

## FTS5 Search with Porter Stemmer (v0.13.0)

Full-text search uses FTS5 with Porter stemmer for morphological variant matching:

```python
from remembering import recall

# Searches match word variants automatically
# "running" matches "run", "runs", "runner"
results = recall("running performance")

# v3.7.0: Configurable expansion threshold
results = recall("term", expansion_threshold=5)  # Expand if < 5 results
results = recall("term", expansion_threshold=0)  # Disable expansion entirely
```

**How it works:**
- FTS5 tokenizer: `porter unicode61` handles stemming
- BM25 ranking for relevance scoring
- Query expansion extracts tags from partial results when below threshold (default 3)
- Composite ranking: BM25 x salience x recency x access patterns

## Handoff Convention

Cross-environment work coordination with version tracking and automatic completion marking.

### Creating Handoffs

From Claude.ai (web/mobile) - cannot persist file changes:

```python
from remembering import remember

remember("""
HANDOFF: Implement user authentication

## Context
User wants OAuth2 + JWT authentication for the API.

## Files to Modify
- src/auth/oauth.py
- src/middleware/auth.py

## Implementation Notes
- Use FastAPI OAuth2PasswordBearer
- JWT tokens with 24h expiry
""", "world", tags=["handoff", "pending", "auth"])
```

### Completing Handoffs

```python
from remembering import handoff_pending, handoff_complete

# Get pending work (excludes completed handoffs)
pending = handoff_pending()

for h in pending:
    print(f"[{h['created_at'][:10]}] {h['summary'][:80]}")

# Complete a handoff (automatically tags with version)
handoff_id = pending[0]['id']
handoff_complete(handoff_id, "COMPLETED: Implemented boot() function...")
```

### Querying History

```python
from remembering import recall

# See what was completed in a specific version
v050_work = recall(tags=["handoff-completed", "v0.5.0"])

# See all completion records
completed = recall(tags=["handoff-completed"], n=50)
```

## Session Scoping (v3.2.0)

Filter memories by conversation or work session using `session_id`:

```python
from remembering import remember, recall, set_session_id

# Set session for all subsequent remember() calls
set_session_id("project-alpha-sprint-1")
remember("Feature spec approved", "decision", tags=["project-alpha"])

# Query by session
alpha_memories = recall(session_id="project-alpha-sprint-1", n=50)
```

**v3.8.0**: Session-filtered queries now use the local cache (~5ms vs ~200ms).

## Retrieval Observability (v3.2.0)

Monitor query performance and usage patterns:

```python
from remembering import recall_stats, top_queries

# Get retrieval statistics
stats = recall_stats(limit=100)
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
print(f"Avg query time: {stats['avg_exec_time_ms']:.1f}ms")

# Find most common searches
for query_info in top_queries(n=10):
    print(f"{query_info['query']}: {query_info['count']} times")
```

## Retention Management (v3.2.0)

Analyze memory distribution and prune old/low-priority memories:

```python
from remembering import memory_histogram, prune_by_age, prune_by_priority

# Get memory distribution
hist = memory_histogram()
print(f"Total: {hist['total']}")
print(f"By type: {hist['by_type']}")

# Preview what would be deleted (dry run)
result = prune_by_age(older_than_days=90, priority_floor=0, dry_run=True)

# Actually delete old low-priority memories
result = prune_by_age(older_than_days=90, priority_floor=0, dry_run=False)

# Delete all background-priority memories
result = prune_by_priority(max_priority=-1, dry_run=False)
```

## Export/Import for Portability

Backup or migrate Muninn state across environments:

```python
from remembering import muninn_export, muninn_import
import json

# Export all state to JSON
state = muninn_export()
with open("muninn-backup.json", "w") as f:
    json.dump(state, f, indent=2)

# Import (merge with existing data)
with open("muninn-backup.json") as f:
    data = json.load(f)
stats = muninn_import(data, merge=True)

# Import (replace all - destructive!)
stats = muninn_import(data, merge=False)
```

## Type-Safe Results (v3.4.0)

`recall()`, `recall_since()`, and `recall_between()` return `MemoryResult` objects that validate field access:

```python
from remembering import recall, MemoryResult, VALID_FIELDS

memories = recall("search term", n=10)

for m in memories:
    print(m.summary)      # Attribute-style
    print(m['summary'])   # Dict-style
    print(m.get('summary', 'default'))  # get() with default

    # v3.7.0: Common aliases resolve transparently
    print(m.content)      # Resolves to m.summary
    print(m.conf)         # Resolves to m.confidence

    # Truly invalid fields still raise errors
    print(m.foo)          # AttributeError with list of valid fields
```

**Transparent aliases (v3.7.0):**
| Alias | Resolves To |
|-------|-------------|
| `m.content` | `m.summary` |
| `m['text']` | `m['summary']` |
| `m.conf` | `m.confidence` |
| `m.timestamp` | `m.t` |
| `m.created` | `m.created_at` |

**Backward compatibility:**
- MemoryResult supports all dict operations: `in`, `len()`, iteration, `keys()`, `values()`, `items()`
- Use `m.to_dict()` to convert back to plain dict when needed
- Use `raw=True` parameter to get plain dicts: `recall("term", raw=True)`

## Proactive Memory Hints (v3.4.0)

`recall_hints()` scans context for terms that match memories:

```python
from remembering import recall_hints

# Scan code context for relevant memories
hints = recall_hints("for m in memories: print(m['content'])")

if hints['hints']:
    for h in hints['hints']:
        print(f"  [{h['type']}] {h['preview']}")
        print(f"    Matched: {h['matched_terms']}")

# Use explicit terms for targeted lookup
hints = recall_hints(terms=["muninn", "field", "summary", "content"])
```

**When to use:**
- Before writing code that uses `recall()` - catch field name errors early
- When starting work on a topic - surface forgotten context
- Before making decisions - check for relevant past decisions

## Unified GitHub API (v3.8.0)

```python
from remembering import github_api

# GET request (default)
issues = github_api('repos/owner/repo/issues')

# POST request with body
pr = github_api('repos/owner/repo/pulls', method='POST',
                body={'title': 'Fix bug', 'head': 'fix-branch', 'base': 'main'})
```

Automatically selects the best available method (gh CLI when authenticated, otherwise GITHUB_TOKEN/GH_TOKEN).
