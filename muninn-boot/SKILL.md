---
name: muninn-boot
description: Boots Muninn — runs scripts/boot.sh, which fetches oaustegard/claude-skills and oaustegard/muninn-utilities at pinned commits, loads the Turso and GitHub tokens, and runs the memory-system boot sequence. Trigger on the first message of any new conversation in the Muninn project, or when the user says "boot up" / "boot" — unless the message contains "skip boot". If the message contains "skinny boot", run with BOOT_MODE=perch. Safe to run on every message: a warm container fast-exits in ~0s via the sentinel.
metadata:
  version: 1.1.0
  canonical: https://github.com/oaustegard/claude-skills/tree/main/muninn-boot
---

# Muninn Boot

Oskar's own repos and credentials (oaustegard/*, /mnt/project/*.env). Standing
procedure — runs every session.

```bash
bash /mnt/skills/user/muninn-boot/scripts/boot.sh
```

Skinny boot ("skinny boot" in the message):

```bash
BOOT_MODE=perch bash /mnt/skills/user/muninn-boot/scripts/boot.sh
```

`scripts/boot.sh` (sibling of this file — readable before running)
does, in order:

0. **Warm-container fast path**: exits immediately if the sentinel
   `/home/claude/.muninn-booted` matches the pinned SHAs and the utilities
   are on disk. The project instruction re-arrives with every message, so
   the script is built to be re-invoked freely; only a genuinely fresh
   (recycled) container pays the full boot. A pin bump self-invalidates
   the sentinel; `rm /home/claude/.muninn-booted` forces a full boot;
   skinny boot always runs fully (its value IS the perch output).
1. Fetches oaustegard/claude-skills → /mnt/skills/user (excluding the
   relocated `remembering/` stub, so it can never clobber a project-uploaded
   remembering skill) and oaustegard/muninn-utilities →
   /home/claude/muninn-utilities, each at a pinned commit SHA.
2. Sources the two env files `boot()` reads: `Turso.env` (memory, config,
   reminders) and `GitHub.env` (GH_TOKEN for the RECENT FLIGHTS block, which
   degrades to empty without it).
3. Writes the `.pth` so `from scripts import boot` resolves, runs `boot()`,
   prints its output, and writes the sentinel (last, only on success).

## Credential scope

The remaining project `.env` files (`bsky.env`, `muninn-bsky.env`,
`strava.env`, `proxy.env`, `claude.env`) are used by later task-specific
steps, which source them inline immediately before the command that needs
them:

```bash
set -a; . /mnt/project/strava.env 2>/dev/null; set +a
```

(Env vars do not persist across separate `bash_tool` calls, so per-call
sourcing is how every consumer works regardless of what boot loads.)

## Updating the pinned commits

`CLAUDE_SKILLS_SHA` / `MUNINN_UTILS_SHA` at the top of `scripts/boot.sh` are
pinned, not `main`. Bump them — after reviewing the diff — when either repo
changes and the update should take effect, then re-upload this skill to the
project. Pinning makes the installed skill the reviewed artifact; floating on
`main` would execute whatever happens to be latest and unreviewed.

This skill's own canonical source is `muninn-boot/` in oaustegard/claude-skills;
edit there, then re-upload to the project. (The copy boot fetches into
/mnt/skills/user is one pin behind by construction — the RUNNING copy is
always the project upload.)
