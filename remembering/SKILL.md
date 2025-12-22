---
name: remembering
description: Minimal persistent memory across Claude sessions. Use when storing user preferences, project context, decisions, or facts that should persist. Triggers on "remember this", "save for later", "don't forget", or when context should survive session boundaries.
---

# Remembering

One-liner memory operations. Store what matters, retrieve when needed.

## Store

```python
from remembering import remember

remember("User prefers concise answers")
remember("Deadline Dec 15", tags=["project-x"])
remember("Always use dark mode", conf=0.95)
```

Type auto-inferred from content:
- "prefers", "should", "always" → `decision`
- "TODO", "deadline", "blocked" → `world`
- "error", "bug", "failed" → `anomaly`
- Default → `experience`

Override with `type="decision"` if needed.

## Retrieve

```python
from remembering import recall

recall()                      # recent 10
recall(20)                    # recent 20
recall("deadline")            # search summaries
recall(tags=["task"])         # filter by tags
recall(type="decision")       # filter by type
recall(conf=0.8)              # min confidence
```

## Forget

```python
from remembering import forget

forget("memory-uuid-here")    # soft delete
```

## Short Form

```python
import remembering as m
m.r("fact")   # remember
m.q()         # query/recall
```

## Workflow

**Conversation start:** Load relevant context
```python
prefs = recall(type="decision", conf=0.7)
recent = recall(5)
```

**During conversation:** Save insights as they emerge
```python
remember("User's project uses Python 3.12 with FastAPI")
```

**Conversation end:** Consolidate learnings
```python
remember("When user asks about APIs, show curl examples first", conf=0.85)
```

## Memory Quality

Write complete, narrative summaries:

✓ "User prefers direct answers with code examples over conceptual explanations"

✗ "User asked question" + "gave code" + "seemed happy"

## Technical

- Backend: Turso SQLite (HTTP API)
- Token: `/mnt/project/turso-token.txt`
- Same database as personal-memory skill (compatible)
