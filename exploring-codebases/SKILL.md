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
  version: 2.2.1
---

# Exploring Codebases

Exploratory code analysis for unfamiliar repositories. Orchestrates
tree-sitting (structural) and featuring (semantic) over a local copy.

## Workflow

Five numbered steps, in order. Do not skip step 0.

### 0. Setup (once per session)

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
export PYTHON=/home/claude/.venv/bin/python
export TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
export GATHER=/mnt/skills/user/featuring/scripts/gather.py
```

If step 2's `--stats` later reports `Scanned 0 files ... Errors: 1`, the
language pack isn't loaded — come back here and install. Treesit fails
silently on missing deps; it does not raise a useful error.

### 1. Get the repo (tarball, not per-file)

```bash
OWNER=...
REPO=...
REF=main                    # branch name, tag, or SHA. For a PR: pull/N/head
curl -sL -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/tarball/$REF" -o /tmp/$REPO.tar.gz
mkdir -p /tmp/$REPO && tar -xzf /tmp/$REPO.tar.gz -C /tmp/$REPO --strip-components=1
ls /tmp/$REPO | head        # sanity check — did extraction land?
```

One HTTP call gets the whole repo. Do NOT curl README, cat files, or
fetch via `contents/PATH` first — they're in the tarball. The
Authorization header is only needed for private repos; public repos
work without it.

**Ref selection matters.** If exploring a feature branch, PR, or tag,
set `REF` accordingly. The default `main` will silently give you stale
code if the question is about an unmerged branch.

### 2. Structural scan

```bash
$PYTHON $TREESIT /tmp/$REPO --stats
```

Read the output. It gives file counts, symbol counts, languages, and
per-directory symbol density. This IS the orienting artifact — treat it
as the product of this step, not warm-up.

**Drill only if you have a specific question.** For pure "what is this
repo" exploration, skip drilling and go to step 3 — featuring surfaces
the interesting paths for you. Drill when a user asked about a specific
subsystem, or when step 3's output raises a question that needs source.

**When you do drill, batch queries in one invocation.** Every treesit
call pays the full scan cost. Multiple queries added to the same command
share that scan and each additional query adds ~0ms. If you're about to
make a second treesit call on the same path, fold it into the first.

```bash
# GOOD — one scan, three answers
$PYTHON $TREESIT /tmp/$REPO --path=SUBDIR --detail=full \
  'find:*Handler*:function' 'source:main' 'refs:Config'

# BAD — three scans, three answers (3× the cost for the same information)
$PYTHON $TREESIT /tmp/$REPO --path=SUBDIR --detail=full
$PYTHON $TREESIT /tmp/$REPO 'find:*Handler*:function'
$PYTHON $TREESIT /tmp/$REPO 'refs:Config'
```

### 3. Feature synthesis

```bash
$PYTHON $GATHER /tmp/$REPO \
  --skip tests,.github,node_modules --source-budget 8000
```

Output includes a "Candidate areas for sub-files (by symbol density)"
list near the top — that's your drill-target picker, ranked.

### 4. Reason about the combined output

Synthesize 2+3: capabilities, feature groups, architecture, entry
points, anomalies. Produce `_FEATURES.md` when warranted. This is the
LLM step; everything before was mechanical.

## When to Use This vs Other Skills

| Situation | Use |
|-----------|-----|
| "I just cloned this, what is it?" | **exploring-codebases** (this skill) |
| "Where is the retry logic?" | searching-codebases |
| "Find all files matching `class.*Error`" | searching-codebases |
| "Show me the symbols in auth.py" | tree-sitting directly |
| "Document what this codebase does" | featuring directly |

Exploring is the **divergent** skill — you don't know what you're looking
for yet. Searching is the **convergent** skill — you know what you want.

## Notes

- **Large repos (>100 files)**: use `--skip tests,vendored,docs,...` in
  step 2 to focus the scan.
- **Monorepos**: treat each package/service as a separate exploration.
  Generate per-subsystem `_FEATURES.md` files linked from a root index.
- **Drill heuristics** (if step 2 drilling is warranted): directories
  with high symbol-to-file ratio (dense logic), entry-point names
  (`main`, `cli`, `app`, `server`, `routes`), files with many imports
  (integration points).
