---
name: exploring-codebases
description: >-
  First-encounter codebase orientation. Chains tree-sitting (structural
  inventory) and featuring (feature synthesis) into an EDA workflow for
  unfamiliar repositories. Use when someone says "explore this repo",
  "what does this do", "I just cloned this", "help me understand this
  codebase", or when starting work on an unfamiliar repository. This is
  the divergent "what's here?" skill — for targeted "where is X?" queries,
  use searching-codebases instead.
metadata:
  version: 1.0.0
---

# Exploring Codebases

Exploratory code analysis for unfamiliar repositories. This skill is a
**workflow**, not a tool — it orchestrates tree-sitting (structural) and
featuring (semantic) into a progressive disclosure sequence.

## Dependencies

- **tree-sitting** — AST-powered code navigation (structural inventory)
- **featuring** — Feature documentation generator (what/why layer)

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack fastmcp --python /home/claude/.venv/bin/python
```

## Workflow

### Phase 1: Structural Inventory (tree-sitting)

Get oriented — what's here, how big, what languages?

```bash
cd /mnt/skills/user/tree-sitting/scripts
/home/claude/.venv/bin/python -c "
import sys; sys.path.insert(0, '.')
from engine import cache

stats = cache.scan('/path/to/repo')
print(cache.tree_overview())
"
```

This gives you the directory tree with file counts, symbol counts, and
languages per directory. Takes ~700ms for a 250-file repo, then all
subsequent queries are sub-millisecond.

### Phase 2: Drill Into Structure

Follow what looks interesting. Use tree-sitting queries to build understanding:

```bash
/home/claude/.venv/bin/python -c "
import sys; sys.path.insert(0, '/mnt/skills/user/tree-sitting/scripts')
from engine import cache

# Already scanned — these are instant
print(cache.dir_overview('src/core'))       # Files + top symbols in a directory
print(cache.find_symbol('*Handler*'))       # Glob search across codebase
print(cache.file_symbols('src/api/routes.py'))  # Full API of a single file
print(cache.get_source('handle_request'))   # Read a specific implementation
"
```

**Heuristics for what to drill into first:**
- Directories with high symbol counts relative to file counts (dense logic)
- Entry point patterns: `main`, `cli`, `app`, `server`, `routes`, `handler`
- Files with many imports (integration points)
- The root directory's top-level files (often config + entry points)

### Phase 3: Feature Synthesis (featuring)

Once you understand the structure, generate the "what does it DO?" layer:

```bash
/home/claude/.venv/bin/python /mnt/skills/user/featuring/scripts/gather.py /path/to/repo \
  --skip tests,.github,node_modules --source-budget 8000
```

Read the gather output, then synthesize `_FEATURES.md` following the featuring
skill's format. This is the LLM step — identify capabilities, group symbols
into features, write user-facing descriptions.

### Phase 4: Targeted Deep Dives

With structural inventory + feature map in hand, use tree-sitting's
`get_source()` to read specific implementations where the feature
narrative needs verification or where behavior isn't clear from signatures.

```bash
/home/claude/.venv/bin/python -c "
import sys; sys.path.insert(0, '/mnt/skills/user/tree-sitting/scripts')
from engine import cache

# Read implementations that matter
print(cache.get_source('authenticate'))
print(cache.references('AuthToken'))
"
```

## When to Use This vs Other Skills

| Situation | Use |
|-----------|-----|
| "I just cloned this, what is it?" | **exploring-codebases** (this skill) |
| "Where is the retry logic?" | searching-codebases |
| "Find all files matching `class.*Error`" | searching-codebases |
| "Show me the symbols in auth.py" | tree-sitting directly |
| "Document what this codebase does" | featuring directly |

Exploring is the **divergent** skill — you don't know what you're looking
for yet. Searching is the **convergent** skill — you know what you want,
you need to find it.

## Output

The exploration produces understanding, not necessarily files. But the
concrete artifacts, when warranted, are:

- `_FEATURES.md` — top-down feature documentation (via featuring)
- Mental model of codebase structure, entry points, and architecture

## Scaling

For large repos (>100 files), use `--skip` aggressively in Phase 1 to
exclude tests, vendored code, generated files, and docs. Focus the initial
scan on `src/` or the primary source directory. Expand scope as needed.

For monorepos, treat each package/service as a separate exploration.
Generate per-subsystem `_FEATURES.md` files linked from a root index.
