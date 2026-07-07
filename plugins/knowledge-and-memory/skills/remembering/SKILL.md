---
name: remembering
description: Memory operations for Muninn (recall, remember, supersede, config). The canonical implementation has moved to oaustegard/muninn-utilities/remembering/. This file is a pointer; do not load skills from this path.
metadata:
  version: 6.0.0
  status: relocated
  canonical: https://github.com/oaustegard/muninn-utilities/tree/main/remembering
---

# remembering — moved

The `remembering` skill (memory architecture, `recall`/`remember`/`supersede`/`config_*`,
boot orchestration, profile/ops loading) now lives in its own repo:

**→ https://github.com/oaustegard/muninn-utilities/tree/main/remembering**

That repo is also the home of `muninn_utils/`, the utilities package boot installs
into `~/muninn_utils/`. Co-locating the two ended a drift problem (e.g. `recall(query=)`
alias landing in one copy but not the other).

## What to do

- **Boot scripts**: clone `oaustegard/muninn-utilities` and add
  `<clone>/remembering` to your `.pth`. The boot block in Muninn's project
  instructions already does this.
- **Local development**: edit in `oaustegard/muninn-utilities/remembering/` and
  open PRs against that repo.
- **Cross-references in other skills**: update any path that points at
  `claude-skills/remembering/` to the new location.

## Why this is just a pointer

Other skills (and external readers) may link to
`claude-skills/remembering/SKILL.md`. Removing the directory entirely would
404 those links; leaving a one-page redirect costs almost nothing and routes
people to the live source.
