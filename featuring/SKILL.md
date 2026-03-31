---
name: featuring
description: >-
  Generate _FEATURES.md files that describe what a codebase DOES from a user/consumer
  perspective, anchored to source symbols via tree-sitting. Produces top-down feature
  documentation organized by capability, not file structure. Use when someone says
  "what does this do", "document features", "feature inventory", "_FEATURES.md",
  or needs to understand a codebase's purpose before modifying it. Complements
  tree-sitting (structural) with semantic (why/what-for) layer.
metadata:
  version: 0.1.0
---

# Featuring

Generate `_FEATURES.md` files — top-down documentation of what a codebase **does**,
organized by feature/capability, anchored to specific source symbols.

**tree-sitting** tells you WHAT symbols exist.
**_FEATURES.md** tells you WHY they exist and what they accomplish together.

## Dependency

Requires **tree-sitting** skill. Uses its engine for AST scanning.

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

## Workflow

### Step 1: Gather structural data

```bash
/home/claude/.venv/bin/python /mnt/skills/user/featuring/scripts/gather.py /path/to/repo \
  --skip tests,.github,node_modules --source-budget 8000
```

This scans the codebase via tree-sitting and outputs a structured summary:
entry points, public API, types, import graph, and key source excerpts.
The `--source-budget` controls how much source code is included (chars).

### Step 2: Synthesize features (LLM)

Read the gather output. Identify features by asking:

1. **What can a user/consumer DO with this?** (capabilities, commands, API endpoints)
2. **What problems does it solve?** (the WHY behind the code)
3. **What are the main workflows?** (how features compose)
4. **What are the constraints/invariants?** (rules the code enforces)

Group related symbols into features. A feature is NOT a file — it's a capability
that may span multiple files. A single file may contribute to multiple features.

### Step 3: Write _FEATURES.md

Output a single `_FEATURES.md` file at the repo root (or per major subsystem
for large repos).

## _FEATURES.md Format

```markdown
# Features: {project-name}

> One-sentence description of what this codebase is and does.

## {Feature Name}

{2-3 sentences: what this feature does from a user perspective.
What problem it solves. When you'd use it.}

**Key symbols:**
- `file.py#function_name` — role in this feature
- `file.py#ClassName` — role in this feature

**Workflow:** {Brief description of how a user exercises this feature,
or how the symbols collaborate to deliver it.}

**Constraints:** {Invariants, limits, rules this feature enforces.}

---

## {Next Feature}
...
```

### Format rules

- **Organized by capability**, not by file/directory
- **Symbol references** use `file#symbol` notation (relative paths)
- **Leading paragraph** per feature: what a user gets, not implementation details
- **Key symbols**: the 2-6 most important symbols, with their role explained
- **Workflow**: how the feature works end-to-end (optional, include when non-obvious)
- **Constraints**: rules/invariants (optional, include when they exist)
- **No source code** in _FEATURES.md — it's a map, not a mirror

### What makes a good feature entry

Good: "**Memory Storage** — Persist observations across sessions. Stores typed,
tagged memories to a Turso database with BM25 full-text search. Memories have
priority levels that affect retrieval ranking."

Bad: "**memory.py** — Contains `remember()`, `recall()`, `forget()`, and
`supersede()` functions."

The first tells you WHAT you can do. The second describes file contents —
tree-sitting already gives you that.

### Identifying features

Heuristics for finding feature boundaries:

- **Entry points** (main, CLI commands, route handlers) often map 1:1 to features
- **Public API functions** that aren't helpers are usually feature surfaces
- **Type hierarchies** (class + methods) often represent a cohesive feature
- **Config/constants clusters** sometimes reveal features (e.g., a group of
  timeout constants → a retry feature)
- **Import clusters** — files that import each other heavily are likely
  co-implementing a feature

Features to SKIP in _FEATURES.md:
- Pure infrastructure (logging, error handling) unless it's the project's purpose
- Internal utilities that only serve other features
- Test code (unless the testing approach IS a feature, e.g., a testing framework)

## Keeping _FEATURES.md in Sync

Three mechanisms, layered:

### 1. Check script (detect drift)

```bash
/home/claude/.venv/bin/python /mnt/skills/user/featuring/scripts/check.py /path/to/repo \
  [--features _FEATURES.md] [--skip tests,.github]
```

Parses `file#symbol` references from _FEATURES.md, resolves them against the
live codebase via tree-sitting, and reports:

- **Broken refs** — symbol deleted or renamed (exit code 1)
- **Moved symbols** — symbol exists but in a different file than referenced
- **Dead features** — ALL key symbols in a feature section are gone
- **Uncovered symbols** — new public API not mentioned in any feature

Exit code 0 = clean, 1 = drift detected. Suitable for CI or pre-commit hooks.

### 2. Agent instructions (prevent drift)

Add to CLAUDE.md or equivalent:

```markdown
## Feature Documentation

- `_FEATURES.md` documents what this codebase does, organized by capability.
- After changing behavior (new feature, renamed API, deleted functionality):
  run `python featuring/scripts/check.py .` and fix any broken refs.
- After adding a new public API surface: add it to the appropriate feature
  section, or create a new feature section if it's a new capability.
- Run check before committing. Broken refs = broken documentation.
```

### 3. Targeted regeneration (fix drift)

When check reports broken refs, the fix is usually surgical: update the
`file#symbol` reference to the new name/location. For dead features (all refs
gone), either delete the section or regenerate it:

```bash
# Re-gather structural data for the affected area
/home/claude/.venv/bin/python /mnt/skills/user/featuring/scripts/gather.py /path/to/repo

# Then use LLM to rewrite just the broken feature sections
```

Full regeneration (re-running gather + LLM synthesis for everything) is the
nuclear option. Prefer targeted updates — they're cheaper and preserve
hand-written narrative.

### CI Integration

```yaml
# .github/workflows/features-check.yml
name: Check _FEATURES.md
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv pip install tree-sitter-language-pack
      - run: python featuring/scripts/check.py . --skip tests
```

## Claude Code Integration

In Claude Code, the tree-sitting MCP server replaces the gather script.
The agent should:

1. Call `scan()` to parse the codebase
2. Call `tree_overview()` for orientation
3. Call `dir_overview()` and `file_symbols()` to understand each module
4. Call `get_source()` for key symbols where intent isn't clear from signatures
5. Write `_FEATURES.md` directly

Add to CLAUDE.md:
```markdown
## Codebase Understanding

Read `_FEATURES.md` for top-down feature orientation before modifying code.
Use tree-sitting MCP tools for structural queries (symbol lookup, source retrieval).
After adding new features or changing behavior, update `_FEATURES.md`.
```

## Example

For the `remembering` skill (memory system), gather.py would produce structural
data showing 21 functions in memory.py, 6 in config.py, etc. The synthesized
_FEATURES.md would group these into:

- **Memory Storage** — `memory.py#remember`, `memory.py#remember_batch`
- **Memory Retrieval** — `memory.py#recall`, `memory.py#recall_batch`, `memory.py#recall_since`
- **Memory Lifecycle** — `memory.py#forget`, `memory.py#supersede`, `memory.py#reprioritize`
- **Memory Maintenance** — `memory.py#consolidate`, `memory.py#curate`, `memory.py#prune_by_age`
- **Decision Tracing** — `memory.py#decision_trace`, `memory.py#get_alternatives`, `memory.py#get_chain`
- **Configuration** — `config.py#config_get`, `config.py#config_set`
- **Task Tracking** — `task.py#Task`, `task.py#task`, `task.py#task_resume`
- **Boot** — `boot.py#boot`, `boot.py#profile`, `boot.py#ops`

Each with narrative explaining what a user gets, not just what the function does.

## Large Repos

For repos with >50 files across distinct subsystems, generate one `_FEATURES.md`
per subsystem directory rather than a single monolithic file. Link them from a
root `_FEATURES.md` index:

```markdown
# Features: {project}

- [{subsystem-a}](subsystem-a/_FEATURES.md) — what subsystem-a does
- [{subsystem-b}](subsystem-b/_FEATURES.md) — what subsystem-b does
```

## Relationship to Other Skills

| Skill | What it provides | Drift detection |
|-------|-----------------|-----------------|
| **tree-sitting** | Structural inventory (symbols, signatures) | N/A (live queries) |
| **featuring** | Feature documentation (what/why) | `check.py` — one-directional (docs → code) |
| **generating-lattice** | Bidirectional knowledge graph | `lat check` — bidirectional (docs ↔ code) |
| **mapping-webapp** | Web app behavioral docs (pages, flows) | None |

featuring's check is lighter than lattice's: no source code annotations needed,
no `@lat:` comments, just reference resolution. The trade-off is that new code
without docs is only flagged as "uncovered symbols" — it's advisory, not
enforced. Use lattice when you need strict bidirectional traceability; use
featuring when you need good-enough orientation docs that catch renames and
deletions.
