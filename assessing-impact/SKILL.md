---
name: assessing-impact
description: >-
  Pre-change blast-radius report for a symbol or file. Walks tree-sitting
  references, augments with a plain-text scan over non-parsed files
  (configs, plain docs), and clusters affected sites by feature
  (`_FEATURES.md`) or top-level package. Use when about to refactor,
  rename, or delete something in a repo you don't own — "what breaks if
  I change `validateUser`", "who calls this", "is this safe to remove",
  "where is this used", "blast radius", "impact analysis". This is the
  CONVERGENT pre-change risk skill — for "what is this repo?" use
  exploring-codebases; for "where is X?" use searching-codebases.
metadata:
  version: 0.1.0
---

# Assessing Impact

Cheap, ad-hoc impact analysis for a single target. Not a graph database —
a focused walk over an AST cache plus a complementary text scan, clustered
into a report that's easy to summarize.

**Use this when** you're about to refactor / rename / delete a symbol in
a repo you don't work in daily, and you want a single artifact that says:
"these N files will need to change, in these M packages, with these tests
likely affected."

**Don't use this for** deep ongoing impact analysis on your own codebase
— stand up GitNexus, SourceGraph, or your IDE's index. This skill is for
the one-shot case.

## Setup

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install --python /home/claude/.venv/bin/python tree-sitter
export PYTHON=/home/claude/.venv/bin/python
export IMPACT=/mnt/skills/user/assessing-impact/scripts/impact.py
```

The script depends on the `tree-sitting` skill — it imports `engine.py`
directly. The bundled grammars live with `tree-sitting`; no separate
language-pack install needed.

## Workflow

### 1. Run the report

```bash
$PYTHON $IMPACT /path/to/repo SYMBOL_NAME
```

Or target a whole file:

```bash
$PYTHON $IMPACT /path/to/repo path/to/module.py
```

### 2. Read the data, write the summary

The script prints a structured markdown report. Treat it as **input** for
your final summary, not the deliverable. It deliberately doesn't assign a
"high/medium/low" risk label — that's your job, after weighing:

- Refs concentrated in one package (low blast) vs. fanned across many (high)
- Test refs present (good — the change has a verification surface) vs. absent
- Doc mentions (renames need to update docs too)
- Caveats listed at the bottom (what the script can't see)

### 3. Drill if needed

If a particular package looks suspicious, follow up with `tree-sitting`
to read the actual call sites:

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
$PYTHON $TREESIT /path/to/repo --no-tree 'source:caller_function'
```

## Options

| Flag | Default | Purpose |
|------|---------|---------|
| `--features PATH` | `_FEATURES.md` | Root `_FEATURES.md` — when present, refs get clustered by feature in addition to by package. |
| `--skip DIRS` | (defaults from tree-sitting) | Extra comma-separated dirs to skip. |
| `--limit-per-name N` | 500 | Cap refs per symbol name. Bump if you suspect truncation. |
| `--json` | off | Emit JSON instead of markdown — for downstream tooling. |

## Output Sections

```
# Impact Report: <target>

## Target
  Kind, definition sites with line ranges.

## Direct & Textual References (N total)
  Top-line counts, then refs grouped by:
  - Code references by package
  - Test references
  - Documentation mentions

## Affected Features (from _FEATURES.md)        ← only if file present
  Feature name → ref count + file count.

## Suggested Test Surfaces
  Test files that already reference the target, plus tests neighboring
  the definition. Likely the regression net for the change.

## Caveats
  What the scan can't see (dynamic dispatch, cross-language, cross-repo).
```

## Composition with Other Skills

- **Run after `exploring-codebases`** if the repo also has a freshly
  generated `_FEATURES.md` — the impact report will cluster refs by
  feature, which makes the blast radius story much more legible than
  raw package directories.
- **Use `tree-sitting` to drill** specific call sites once impact has
  identified them.
- **Use `searching-codebases`** when you want regex/AST search over the
  same corpus rather than impact analysis on a known target.

## Honest Limits

- **Text-based ref discovery.** Refs are matched by symbol name, not by
  type-resolved call edges. Common names (`run`, `init`, `handler`) will
  pick up unrelated symbols. Prefer running this on distinctive names;
  otherwise expect noise and read the snippets.
- **No type/MRO resolution.** Dynamic dispatch (`getattr`, duck-typed
  method calls, virtual dispatch in C++) is missed or over-matched.
- **No cross-language tracing.** A TS frontend calling a Python backend
  handler over HTTP appears as zero refs — they're not in the same AST.
- **No cross-repo tracing.** Consumers in separate repos (downstream
  packages, sibling services) are invisible. For multi-repo impact,
  reach for GitNexus / SourceGraph.
- **No persistent index.** Each run re-scans. Fine for single-shot use;
  acceptable cost (~700ms scan + sub-ms queries) for a few hundred files.
- **Diff input not yet supported.** v0.1 takes a symbol or file path.
  Diff → affected-symbols extraction is a planned follow-up.

## Files

- `scripts/impact.py` — Single-entry CLI. Resolves target → walks AST
  refs → augments with text scan → clusters by package and (optionally)
  by feature → renders markdown or JSON.
