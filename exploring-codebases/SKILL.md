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
  version: 2.1.0
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

### Phase 0: Localize the Repo

**If the input is a GitHub URL (or `owner/repo`), clone before anything else.**
Every subsequent phase needs a local filesystem path — treesit scans directories,
featuring reads files. You cannot `curl` your way through this workflow.

```bash
# Public repo
git clone --depth=1 https://github.com/OWNER/REPO /tmp/REPO

# Private repo (uses GH_TOKEN from env)
git clone --depth=1 "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO" /tmp/REPO
```

Then use `/tmp/REPO` as the `/path/to/repo` in every subsequent command.

**Anti-pattern: API-fetching individual files before cloning.** If you find
yourself running `curl .../contents/README.md` or `curl .../contents/src/foo.py`
at the start of a review, stop. A shallow clone gets every file at once and
unlocks treesit. Single-file API fetches are only appropriate for targeted
lookups *after* the structural exploration has identified what to read.

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

**Rule: batch queries on the same path into a single invocation.** Every
treesit call pays a ~700ms scan cost. Multiple queries added to the same
command share that scan and each additional query adds ~0ms. If you're
about to make a second treesit call on the same path, fold it into the
first one instead.

```bash
# GOOD — one scan, three answers
$PYTHON $TREESIT /path/to/repo --path=src/core --detail=full \
  'find:*Handler*:function' 'refs:AuthToken'

# BAD — three scans, three answers (3x the cost for the same information)
$PYTHON $TREESIT /path/to/repo --path=src/core --detail=full
$PYTHON $TREESIT /path/to/repo 'find:*Handler*:function'
$PYTHON $TREESIT /path/to/repo 'refs:AuthToken'
```

Individual commands as reference:

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

Same batching rule applies: combine `source:` and `refs:` queries into one call.

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
