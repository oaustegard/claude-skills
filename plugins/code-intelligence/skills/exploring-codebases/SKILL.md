---
name: exploring-codebases
description: >-
  First-encounter orientation on a repository nobody here has worked in yet.
  Runs a fixed five-step workflow — venv setup, tarball fetch, tree-sitting
  structural scan, featuring synthesis, then reasoning over the two — and
  yields an account of what the repo contains and how it is arranged,
  optionally written out as _FEATURES.md. Use for "I just cloned this",
  "what is this repo", "what does this do", "explore this repo", "give me an
  orientation", "what are the main features", "review what's new in this repo",
  or before starting work in a codebase you have not seen. This is the
  divergent what's-here skill. Route elsewhere for: a named symbol, a file's
  structure or a line range (tree-sitting); all callers of a Python symbol
  (searching-codebases); teaching a human the codebase through exercises
  (orienting-codebases); fetching or cloning a repo without analysing it
  (accessing-github-repos, cloning-project).
metadata:
  version: 2.5.1
---

# Exploring Codebases

Exploratory code analysis for unfamiliar repositories. Orchestrates
tree-sitting (structural) and featuring (semantic) over a local copy.

## Workflow

Five numbered steps, in order. Do not skip step 0.

### 0. Setup (once per session)

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter --python /home/claude/.venv/bin/python
export PYTHON=/home/claude/.venv/bin/python
export TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
export GATHER=/mnt/skills/user/featuring/scripts/gather.py
```

If step 2's `--stats` reports `Symbols: 0` on a repo you know contains code,
the `tree-sitter` core package isn't installed — come back here and install it
(the engine bundles its own grammars and does NOT use tree-sitter-language-pack).
Treesit exits 0 and prints no error in that case, so zero symbols is the only
signal you get. There is no `Errors:` line: that one appears for parse
failures, and an absent parser never reaches parsing. The full signal, and the
2026-08-24 measurement behind it, is in the tree-sitting skill's Setup section.

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

**Pick the mode from your DELIVERABLE, before you run it.**

| Your deliverable | Command | Size |
|---|---|---|
| Your own understanding — a review, an orientation read, answering a question | `--orient` | ~115 lines |
| A written `_FEATURES.md` that must cite every symbol | full output | thousands of lines |

```bash
# Default. Complexity assessment, decomposition ranking, directory tree, entry points.
$PYTHON $GATHER /tmp/$REPO --skip tests,.github,node_modules --orient

# Only when you are about to WRITE the inventory into a file:
$PYTHON $GATHER /tmp/$REPO --skip tests,.github,node_modules --source-budget 8000
```

Output includes a "Candidate areas for sub-files (by symbol density)"
list near the top — that's your drill-target picker, ranked.

**Never pipe the full output through `head`.** If you are about to truncate it,
`--orient` was the correct mode and you have paid for thousands of lines you
will not read. Diagnosed 2026-08-22 on a FreeToken review: a 5,697-line gather
was cut at line 120, and every finding in that review came from `treesit`
drilling and targeted reads instead. `--orient` returns the 115 lines that were
actually used. The full mode's symbol inventory exists to be CITED, not read.

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
| "Which files are most about CSRF / sessions / queryset filtering?" | bm25 |
| "Rank these docs by relevance to a multi-word concept" | bm25 |
| "Document what this codebase does" | featuring directly |
| "Teach me this codebase" (a human is learning) | orienting-codebases |
| "Get me this repo" — fetch, no analysis | accessing-github-repos, cloning-project |

Exploring is the **divergent** skill — you don't know what you're looking
for yet. Searching is the **convergent** skill — you know what you want.

`orienting-codebases` runs the same tree-sitting + featuring pipeline and is
the nearest thing in the catalogue to this skill. The split is the audience:
this one builds Claude's understanding so work can proceed; that one builds
the *user's* understanding through guided exercises and HTML artifacts. If
nobody is being taught, this is the right skill.

### Pairing bm25 with this workflow

Once steps 2–3 have surfaced the rough shape of the repo, `bm25` is the
natural complement when you want **ranked content search** beyond grep
and beyond exact-symbol lookup. It ranks files by lexical relevance to a
multi-word query, which is useful for "what's this codebase actually
*about* when I search for X?" — particularly when you don't yet know the
symbol name to feed to `tree-sitting`.

```bash
BM25=/mnt/skills/user/bm25/scripts/bm25.py

# Pass multiple queries — index builds once, all queries reuse it
python3 $BM25 /tmp/$REPO 'auth flow' 'session backend' 'middleware pipeline' \
  --exclude 'tests/*' --exclude '*/tests/*' --top-k 5
```

Two patterns that pair especially well:

1. **bm25 → tree-sitting.** Use bm25 to find the top-ranked files for a
   concept; then `tree-sitting source:Symbol:path/to/file.py` to read
   the actual implementation.
2. **bm25 with `--exclude 'tests/*'`.** Test directories tend to dominate
   keyword queries because test names redundantly mention domain terms.
   Excluding them up front lands you on implementation files.

bm25 is corpus-agnostic — it'll also work on `project` knowledge stores
or `uploads/` if your exploration spans docs, transcripts, or PDFs.

## Delegating to subagents

Only when the repo is large (>1000 files or several distinct subsystems) **and**
this environment exposes a subagent tool (Agent/Task in Claude Code and CCotw).
Claude.ai chat and bare-skill runs have none: run steps 2-4 inline and skip
this entirely. Never simulate fan-out by other means when the tool is absent.

Steps 2-3 stay inline either way. Only step 4's judgment work fans out, one
agent per subsystem, and a subagent inherits nothing -- not the conversation,
not this file, not the knowledge that scan artifacts are already on disk.
Read [references/subagent-delegation.md](references/subagent-delegation.md)
before writing the first agent prompt; it carries the four things every prompt
must include and the 2026-07-16 measurement of what happens when they are
missing.

## Notes

- **Large repos (>100 files)**: use `--skip tests,vendored,docs,...` in
  step 2 to focus the scan.
- **Monorepos**: treat each package/service as a separate exploration.
  Generate per-subsystem `_FEATURES.md` files linked from a root index.
- **Drill heuristics** (if step 2 drilling is warranted): directories
  with high symbol-to-file ratio (dense logic), entry-point names
  (`main`, `cli`, `app`, `server`, `routes`), files with many imports
  (integration points).
