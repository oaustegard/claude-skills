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
  version: 2.4.0
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

If step 2's `--stats` later reports `Scanned 0 files ... Errors: 1`, the
`tree-sitter` core package isn't installed — come back here and install it
(the engine bundles its own grammars and does NOT use tree-sitter-language-pack).
Treesit fails silently on missing deps; it does not raise a useful error.

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
| "Which files are most about CSRF / sessions / queryset filtering?" | bm25 |
| "Rank these docs by relevance to a multi-word concept" | bm25 |
| "Document what this codebase does" | featuring directly |

Exploring is the **divergent** skill — you don't know what you're looking
for yet. Searching is the **convergent** skill — you know what you want.

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

## Delegating to subagents (large repos only, and only if subagents exist)

**Gate first: does this environment expose a subagent tool** (Agent/Task in
Claude Code and CCotw)? Claude.ai chat and bare-skill runs have none — run
steps 2–4 inline and skip this section entirely. Never simulate fan-out by
other means when the tool is absent.

When the tool exists and the repo is large (>1000 files or several distinct
subsystems), keep steps 2–3 inline — they're mechanical and cheap — and fan
out only step 4's judgment work, one agent per subsystem.

**Subagents inherit nothing.** Not your conversation, not this SKILL.md, not
the knowledge that scan artifacts exist on disk. An agent prompted only with
"explore `crates/foo`" will re-derive structure by `ls`/glob crawling at full
tier cost. (Observed 2026-07-16: four Sonnet agents launched onto a
2,300-file repo without the handoff spent their opening turns running `ls`,
with the full symbol index already on disk.)

Every subagent prompt must therefore carry:

1. **Its structure slice, pre-computed.** Partition the gather output's
   `## Public API` section by subsystem path prefix, write each slice to a
   file, and point the agent at its file: "grep/Read this instead of listing
   directories." Small slices (<50KB) can be pasted inline instead.
2. **The treesit recipe verbatim** — the full command including the venv
   python path, plus the batch rule (one invocation, many queries; each
   invocation pays the scan, extra queries are free).
3. **Anti-crawl instructions** — no `ls`/Glob for discovery; `Read` only to
   confirm or expand a line range the slice or treesit already located.
4. **An output spec** — what to report, a line budget, and "file paths +
   line refs" so results are verifiable.

Routing (see the `agent-routing` skill): multi-turn exploration is outside
Haiku's calibrated zone — use `sonnet` for subsystem agents and keep the
final cross-cluster synthesis in the orchestrator.

## Notes

- **Large repos (>100 files)**: use `--skip tests,vendored,docs,...` in
  step 2 to focus the scan.
- **Monorepos**: treat each package/service as a separate exploration.
  Generate per-subsystem `_FEATURES.md` files linked from a root index.
- **Drill heuristics** (if step 2 drilling is warranted): directories
  with high symbol-to-file ratio (dense logic), entry-point names
  (`main`, `cli`, `app`, `server`, `routes`), files with many imports
  (integration points).
