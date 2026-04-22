---
name: finding-skills
description: Discover and load skills on demand from /mnt/skills/user/. Use when you need a capability but don't know which skill provides it, when the boot-emitted skill list is names-only and you need a full description, or when you want to list the catalog. Verbs are list (names only), search (rank by name/description match against a query), and show (emit the full SKILL.md for a named skill).
metadata:
  version: 0.1.0
---

# Finding Skills

Skills on disk at `/mnt/skills/user/` are a catalog — too expensive to preload as descriptions in every session's context. This skill is the on-demand accessor, analogous to Anthropic's ToolSearch for MCP tools.

## Usage

```bash
PY=/home/user/.spokes/claude-skills/finding-skills/scripts/skills.py

# List every skill by name (cheap, ~1.4KB)
python3 "$PY" list

# Search by keyword — ranks name matches above description matches
python3 "$PY" search "adversarial review"

# Load the full SKILL.md of a specific skill
python3 "$PY" show challenging
```

In a live CCotw session the script lives at `/mnt/skills/user/finding-skills/scripts/skills.py`.

## When to reach for this

- You have a task where a skill might help but no obvious name comes to mind → `search <keywords>`
- The boot emitted names-only and you want the description of a candidate → `show <name>`
- You want catalog breadth before picking an approach → `list`

## Pattern

1. `search "<what you want to do>"` — get 3–10 ranked candidates
2. `show <top-pick>` — read its SKILL.md
3. Follow the SKILL.md's instructions (which may point at `scripts/`, `references/`, etc.)

Stop at step 1 if none of the candidates fit — don't shoehorn an unrelated skill onto the task.

## Ranking

- Exact match on skill name: 100
- Substring match on skill name: 10
- Substring match in description: 1 per match (multiple hits compound)

Case-insensitive throughout. Results sorted high-to-low, ties broken by name.

## Output format

- `list`: one skill name per line
- `search`: tab-separated `<name>\t<description (truncated to 200 chars)>`, one per line
- `show`: raw SKILL.md contents to stdout; exit 1 with a stderr message if not found

All three are line-oriented so they compose with `grep`, `head`, etc.
