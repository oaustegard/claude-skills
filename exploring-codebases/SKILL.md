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
  version: 2.0.0
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
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

## Workflow

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
PYTHON=/home/claude/.venv/bin/python
```

### Phase 1: Structural Orientation

Get oriented — what's here, how big, what languages?

```bash
$PYTHON $TREESIT /path/to/repo --stats
```

Default depth=1 shows root-level files and one level of subdirectories
with file counts, symbol counts, and languages. Takes ~700ms total
(scan + output).

### Phase 2: Drill Into Structure

Follow what looks interesting. Each call auto-scans — no state to manage.

```bash
# Drill into a directory with full detail (signatures, docs, children, imports)
$PYTHON $TREESIT /path/to/repo --path=src/core --detail=full

# Search for patterns across the codebase
$PYTHON $TREESIT /path/to/repo 'find:*Handler*:function'

# Read a specific implementation
$PYTHON $TREESIT /path/to/repo --no-tree 'source:handle_request'
```

**Heuristics for what to drill into first:**
- Directories with high symbol counts relative to file counts (dense logic)
- Entry point patterns: `main`, `cli`, `app`, `server`, `routes`, `handler`
- Files with many imports (integration points)
- The root directory's top-level files (often config + entry points)

### Phase 3: Feature Synthesis (featuring)

Once you understand the structure, generate the "what does it DO?" layer:

```bash
$PYTHON /mnt/skills/user/featuring/scripts/gather.py /path/to/repo \
  --skip tests,.github,node_modules --source-budget 8000
```

Read the gather output, then synthesize `_FEATURES.md` following the featuring
skill's format. This is the LLM step — identify capabilities, group symbols
into features, write user-facing descriptions.

### Phase 4: Targeted Deep Dives

With structural inventory + feature map in hand, read specific implementations
where the feature narrative needs verification or behavior isn't clear:

```bash
$PYTHON $TREESIT /path/to/repo --no-tree 'source:authenticate' 'refs:AuthToken'
```

Multiple queries in one call — each adds ~0ms on top of the scan cost.

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
scan on `--path=src` or the primary source directory. Expand scope as needed.

For monorepos, treat each package/service as a separate exploration.
Generate per-subsystem `_FEATURES.md` files linked from a root index.
