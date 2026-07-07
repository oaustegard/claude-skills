---
name: featuring
description: >-
  Generate hierarchical _FEATURES.md files that describe what a codebase DOES from a
  user/consumer perspective, anchored to source symbols via tree-sitting. Supports large
  complex codebases through feature-driven decomposition into sub-feature files. Uses a
  multi-pass synthesis: orientation → detail → overview rewrite. Use when someone says
  "what does this do", "document features", "feature inventory", "_FEATURES.md",
  or needs to understand a codebase's purpose before modifying it. Complements
  tree-sitting (structural) with semantic (why/what-for) layer.
metadata:
  version: 0.3.0
---

# Featuring

Generate `_FEATURES.md` files — top-down documentation of what a codebase **does**,
organized by feature/capability, anchored to specific source symbols.

**tree-sitting** tells you WHAT symbols exist.
**_FEATURES.md** tells you WHY they exist and what they accomplish together.

For large codebases, the root `_FEATURES.md` decomposes into sub-feature files
linked by capability area — not by folder structure. An agent starts at the root
and is drawn into sub-files only when working on a relevant area.

## Dependency

Requires **tree-sitting** skill. Uses its engine for AST scanning.

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

For quick structural orientation before running gather.py, use tree-sitting's CLI:

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py

# Complete tree, sparse detail — see the full shape
/home/claude/.venv/bin/python $TREESIT /path/to/repo --depth=-1 --detail=sparse
```

## Workflow: Multi-Pass Synthesis

Feature documentation is built in three passes. The overview is written LAST,
after all features are understood — not first.

### Pass 1: Orientation (quick scan)

```bash
/home/claude/.venv/bin/python /mnt/skills/user/featuring/scripts/gather.py /path/to/repo \
  --skip tests,.github,node_modules --source-budget 8000
```

Read the gather output. Before writing anything, form a hypothesis:

> "This codebase appears to be a **[what it is]** that provides **[capability A]**,
> **[capability B]**, and **[capability C]**."

Write this down as a DRAFT overview. It will be wrong or incomplete — that's fine.
The point is to orient before diving into detail.

**How to identify capability areas:**

1. **What can a user/consumer DO with this?** (commands, API endpoints, UI actions)
2. **What problems does it solve?** (the WHY behind the code)
3. **What are the main workflows?** (how features compose)
4. **What are the constraints/invariants?** (rules the code enforces)

### Pass 2: Detailed feature extraction

For each capability area identified in Pass 1:

1. Gather the symbols that implement it (from gather output + targeted `get_source()`)
2. Understand how they collaborate — the workflow
3. Identify constraints and invariants
4. Write the feature section

During this pass, you'll discover:
- Capabilities you missed in Pass 1
- Features that are more complex than expected (decomposition candidates)
- Features that are simpler than expected (merge candidates)
- Cross-cutting concerns that span multiple capability areas

**Hierarchy decision** (per feature, during this pass):

| Signal | Action |
|--------|--------|
| ≤6 key symbols, self-contained | Inline in root `_FEATURES.md` |
| >6 key symbols OR clear sub-capabilities | Own `_FEATURES.md` sub-file |
| Spans many files but is ONE capability | Inline (breadth ≠ complexity) |
| Has sub-features that are independently useful | Own sub-file |
| Is infrastructure (logging, DB layer) | Inline briefly, unless it IS the product |

### Pass 3: Overview rewrite

NOW — after all features are documented — rewrite the overview. The Pass 1
draft was a hypothesis. Pass 3 replaces it with a proper progressive-disclosure
overview that:

1. States what the codebase is in one sentence
2. Lists the top-level capability areas (3-8 items)
3. For each area that has a sub-file: one sentence + link + "read when" guidance
4. For inline features: just the list entry (detail is below in the same file)

This is the most important part. The overview IS the entry point for every
agent session. It must be accurate, complete, and fast to scan.


## _FEATURES.md Format

### Root file

```markdown
# Features: {project-name}

> One-sentence description of what this codebase is and does.

**Capability areas:**
- **[Area A]** — one-sentence summary
- **[Area B]** — one-sentence summary → [details](path/to/_FEATURES.md)
- **[Area C]** — one-sentence summary

## {Inline Feature Name}

{2-3 sentences: what this feature does from a user perspective.}

**Key symbols:**
- `file.py#function_name` — role in this feature
- `file.py#ClassName` — role in this feature

**Workflow:** {How a user exercises this feature or how symbols collaborate.}

**Constraints:** {Invariants, limits, rules.}

---

## {Complex Feature Area}

> One-sentence summary of what this area covers.

This area is documented in detail in [{area-name}/_FEATURES.md]({path}).
Read it when working on {specific trigger — e.g., "the memory retrieval pipeline",
"adding a new API endpoint", "modifying the build system"}.

At a glance, this area provides:
- {sub-capability 1} — one line
- {sub-capability 2} — one line
- {sub-capability 3} — one line
```

### Sub-feature files

Sub-feature files follow the SAME format as the root, recursively. They can
contain inline features and further sub-file references. Each sub-file:

- Has its own `# Features: {area-name}` header
- Has its own overview paragraph
- Is self-contained — an agent reading only this file understands the area
- Links back to the root: `← [Root features](../_FEATURES.md)`

### Format rules

- **Organized by capability**, not by file/directory
- **Symbol references** use `file#symbol` notation (relative to repo root)
- **Leading paragraph** per feature: what a user gets, not implementation details
- **Key symbols**: the 2-6 most important symbols, with their role explained
- **Workflow**: how the feature works end-to-end (include when non-obvious)
- **Constraints**: rules/invariants (include when they exist)
- **No source code** in _FEATURES.md — it's a map, not a mirror
- **"Read when" guidance** on every sub-file link — tells agents WHEN to drill in

### What makes a good feature entry

Good: "**Memory Storage** — Persist observations across sessions. Stores typed,
tagged memories to a Turso database with BM25 full-text search. Memories have
priority levels that affect retrieval ranking."

Bad: "**memory.py** — Contains `remember()`, `recall()`, `forget()`, and
`supersede()` functions."

The first tells you WHAT you can do. The second describes file contents —
tree-sitting already gives you that.

### Hierarchy design principles

The hierarchy is **feature-driven**, not folder-driven. Folders are natural
candidates for decomposition boundaries, but the decision is based on:

1. **Does this capability area have enough complexity to warrant its own file?**
   (>6 key symbols, multiple sub-workflows, or independently useful sub-features)
2. **Would an agent working on this area benefit from focused context?**
   (if yes, a sub-file saves them from parsing unrelated features)
3. **Is this area likely to be read independently of the rest?**
   (if yes, it should be self-contained in its own file)

Counter-examples — do NOT split just because:
- The code lives in a separate folder (folder ≠ feature)
- There are many files (files ≠ complexity)
- A class has many methods (one class = one feature unless methods serve
  distinct user-facing purposes)


## Identifying features

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

Parses `file#symbol` references from ALL _FEATURES.md files (root + sub-files),
resolves them against the live codebase via tree-sitting, and reports:

- **Broken refs** — symbol deleted or renamed (exit code 1)
- **Moved symbols** — symbol exists but in a different file than referenced
- **Dead features** — ALL key symbols in a feature section are gone
- **Uncovered symbols** — new public API not mentioned in any feature
- **Orphan sub-files** — sub-feature files not linked from any parent

Exit code 0 = clean, 1 = drift detected. Suitable for CI or pre-commit hooks.

### 2. Agent instructions (prevent drift)

Add to CLAUDE.md or equivalent:

```markdown
## Feature Documentation

- `_FEATURES.md` documents what this codebase does, organized by capability.
- Start here when orienting to the codebase. Follow sub-file links as needed.
- After changing behavior (new feature, renamed API, deleted functionality):
  run `python featuring/scripts/check.py .` and fix any broken refs.
- After adding a new public API surface: add it to the appropriate feature
  section, or create a new feature section if it's a new capability.
- Run check before committing. Broken refs = broken documentation.
```

### 3. Targeted regeneration (fix drift)

When check reports broken refs, the fix is usually surgical: update the
`file#symbol` reference to the new name/location. For dead features (all refs
gone), either delete the section or regenerate it.

Full regeneration (re-running all three passes) is the nuclear option.
Prefer targeted updates — they're cheaper and preserve hand-written narrative.

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

In Claude Code, use tree-sitting's CLI or engine directly. The agent should:

1. Run `treesit.py /path --depth=-1 --detail=sparse` for full structural overview
2. **Pass 1:** Form a hypothesis about what the codebase does
3. Run `treesit.py /path --path=DIR --detail=full` for each capability area
4. Run `treesit.py /path --no-tree 'source:symbol_name'` where intent isn't clear
5. **Pass 2:** Write detailed feature sections, deciding hierarchy per-feature
6. **Pass 3:** Rewrite the overview now that all features are documented

Add to CLAUDE.md:
```markdown
## Codebase Understanding

Read `_FEATURES.md` for top-down feature orientation before modifying code.
Follow links to sub-feature files when working on a specific area.
Use tree-sitting MCP tools for structural queries (symbol lookup, source retrieval).
After adding new features or changing behavior, update the relevant _FEATURES.md.
```

## Example: Small Codebase (flat)

A CLI tool with 15 public symbols → single `_FEATURES.md`, all features inline.
No sub-files needed.

## Example: Large Codebase (hierarchical)

The `remembering` skill (memory system for an AI agent) has ~60 public symbols
across 8 files. Hierarchical decomposition:

```
_FEATURES.md              (root — overview + 3 inline features + 3 sub-file refs)
├── scripts/_FEATURES.md  (memory operations — storage, retrieval, lifecycle, maintenance)
└── utils/_FEATURES.md    (utility modules — therapy, reminders, blog publishing)
```

Root `_FEATURES.md` would contain:
- **Overview**: "Persistent memory system for Muninn. Stores, retrieves, and
  maintains typed memories across sessions via Turso."
- **Inline**: Boot Sequence, Configuration, Task Tracking (simple, ≤4 symbols each)
- **Sub-file ref**: Memory Operations → `scripts/_FEATURES.md`
  ("Read when working on storage, retrieval, or memory lifecycle")
- **Sub-file ref**: Utility Modules → `utils/_FEATURES.md`
  ("Read when working on therapy sessions, reminders, or blog publishing")

## Relationship to Other Skills

| Skill | What it provides | Drift detection |
|-------|-----------------|-----------------|
| **tree-sitting** | Structural inventory (symbols, signatures) | N/A (live queries) |
| **featuring** | Feature documentation (what/why), hierarchical | `check.py` — docs → code |
| **generating-lattice** | Bidirectional knowledge graph | `lat check` — docs ↔ code |
| **mapping-webapp** | Web app behavioral docs (pages, flows) | None |

featuring's check is lighter than lattice's: no source code annotations needed,
no `@lat:` comments, just reference resolution. The trade-off is that new code
without docs is only flagged as "uncovered symbols" — it's advisory, not
enforced. Use lattice when you need strict bidirectional traceability; use
featuring when you need good-enough orientation docs that catch renames and
deletions.
