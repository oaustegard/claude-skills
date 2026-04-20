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
featuring (semantic) over a local copy of the repo.

## Dependencies

- **tree-sitting** — AST-powered code navigation (structural inventory)
- **featuring** — Feature documentation generator (what/why layer)

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

## Workflow

Four steps, in order. Do not skip step 1.

### 1. Get the repo (tarball, not per-file)

```bash
OWNER=... REPO=... REF=main
curl -sL "https://api.github.com/repos/$OWNER/$REPO/tarball/$REF" -o /tmp/$REPO.tar.gz
mkdir -p /tmp/$REPO && tar -xzf /tmp/$REPO.tar.gz -C /tmp/$REPO --strip-components=1
```

One HTTP call gets the whole repo. Do NOT curl the README, cat individual
files, or fetch via `contents/PATH` before this — they're all in the tarball.
Every pre-tarball `curl`/`cat` on a file that's already in the repo is
wasted tool budget.

For private repos, add `-H "Authorization: Bearer $GH_TOKEN"`.

### 2. Tree-sitting (structural inventory)

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
PYTHON=/home/claude/.venv/bin/python

# Structural overview — files, symbol counts, languages at depth=1
$PYTHON $TREESIT /tmp/$REPO --stats

# Drill into interesting paths. BATCH queries in one call — each extra
# query adds ~0ms on top of the scan cost. Separate invocations re-scan.
$PYTHON $TREESIT /tmp/$REPO --path=SUBDIR --detail=full \
  'find:*Handler*:function' 'source:main' 'refs:Config'
```

### 3. Featuring (feature synthesis)

```bash
$PYTHON /mnt/skills/user/featuring/scripts/gather.py /tmp/$REPO \
  --skip tests,.github,node_modules --source-budget 8000
```

### 4. Reason about the combined output

Synthesize steps 2+3 into understanding — identify capabilities, group symbols
into features, write user-facing descriptions. Produce `_FEATURES.md` when
warranted. This is the LLM step; everything before was mechanical.

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

## Notes

- **Scale**: For large repos (>100 files), use `--skip tests,vendored,docs,...`
  in step 2 to focus the initial scan. Expand scope as needed.
- **Monorepos**: Treat each package/service as a separate exploration.
  Generate per-subsystem `_FEATURES.md` files linked from a root index.
- **Drill heuristics** (for step 2): directories with high symbol count vs
  file count (dense logic), entry-point patterns (`main`, `cli`, `app`,
  `server`, `routes`), files with many imports (integration points).
