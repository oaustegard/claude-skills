---
name: mapping-codebases
description: DEPRECATED — superseded by tree-sitting. This skill generated persistent _MAP.md files; tree-sitting does the same AST extraction at runtime (~700ms for 250 files) with no artifact to write, commit, or keep in sync. Use tree-sitting for "map this codebase", "explore repo", "understand structure", or any code navigation task. The final working version is archived at release mapping-codebases-v0.8.0.
metadata:
  version: 0.9.0
---

# Mapping Codebases (deprecated)

Use [tree-sitting](../tree-sitting/SKILL.md) instead.

## Why

This skill wrote `_MAP.md` files to disk — a persisted symbol inventory per
directory, generated once and read many times. That tradeoff made sense when
scanning was expensive. It isn't: tree-sitting parses a 250-file repo in about
700ms and answers queries against the in-memory AST in under a millisecond.

A persisted map costs what a runtime scan does not — it goes stale, it needs
regenerating, it gets committed, and it must be excluded from every other tool
that walks the tree. Nothing was gained for that.

## Replacement commands

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py

# Was: codemap.py /path/to/repo          → root orientation
python3 $TREESIT /path/to/repo

# Was: reading every _MAP.md in the tree → full inventory
python3 $TREESIT /path/to/repo --depth=-1 --detail=sparse

# Was: grepping _MAP.md for a symbol     → direct lookup
python3 $TREESIT /path/to/repo --no-tree 'find:parse_input'
```

## The archived version

The last working release is
[mapping-codebases-v0.8.0](https://github.com/oaustegard/claude-skills/releases/tag/mapping-codebases-v0.8.0)
(2026-03-31). It carries `scripts/codemap.py` and the eleven bundled
`parsers/*.so` grammars. The release is the snapshot; nothing in this directory
reproduces it.

Note that v0.8.0 ships a latent bug: `codemap.py:1216` calls an unimported
`get_parser()` inside a `try` swallowed by a bare `except Exception`, so HTML
inline-JavaScript symbol extraction silently returned nothing. It will not be
fixed.
