---
name: muninn-boot
description: Boots Muninn — fetches oaustegard/claude-skills and oaustegard/muninn-utilities at pinned commits, loads the Turso and GitHub tokens, and runs the memory-system boot sequence. Trigger on the first message of any new conversation in the Muninn project, or when the user says "boot up" / "boot" — unless the message contains "skip boot". If the message contains "skinny boot", set BOOT_MODE=perch first.
---

# Muninn Boot

Oskar's own repos and credentials (oaustegard/*, /mnt/project/*.env). Standing
procedure — runs every session.

```bash
set -e
cd /tmp
CLAUDE_SKILLS_SHA=b2fe13742b32400f8b69e8b793289fe1e7d107be
MUNINN_UTILS_SHA=ccbb64725f4351c5eb0d95811f2c46a297e2fe67

curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/$CLAUDE_SKILLS_SHA" -o cs.tar.gz \
  && tar -xzf cs.tar.gz \
  && mkdir -p /mnt/skills/user \
  && cp -r claude-skills-$CLAUDE_SKILLS_SHA/* /mnt/skills/user/

curl -sL "https://codeload.github.com/oaustegard/muninn-utilities/tar.gz/$MUNINN_UTILS_SHA" -o mu.tar.gz \
  && tar -xzf mu.tar.gz \
  && mkdir -p /home/claude/muninn-utilities \
  && cp -r muninn-utilities-$MUNINN_UTILS_SHA/* /home/claude/muninn-utilities/

set -a
. /mnt/project/Turso.env 2>/dev/null
. /mnt/project/GitHub.env 2>/dev/null
set +a

PTH=/usr/local/lib/python3.12/dist-packages/muninn-remembering.pth
HOMEDIR=$(python3 -c 'import os; print(os.path.expanduser("~"))')
printf '%s\n' "/home/claude/muninn-utilities/remembering" "$HOMEDIR" > "$PTH"
for d in /mnt/skills/user/*/scripts/; do
  ls "$d"*.py >/dev/null 2>&1 && echo "$d" >> "$PTH"
done

python3 << 'EOF'
import os
from scripts import boot
print(boot(mode=os.environ.get('BOOT_MODE')))
EOF
```

## Credential scope

Boot sources the two files `boot()` reads: `Turso.env` (memory, config,
reminders) and `GitHub.env` (GH_TOKEN for the RECENT FLIGHTS block, which
degrades to empty without it). The remaining project `.env` files
(`bsky.env`, `muninn-bsky.env`, `strava.env`, `proxy.env`, `claude.env`)
are used by later task-specific steps, which source them inline immediately
before the command that needs them:

```bash
set -a; . /mnt/project/strava.env 2>/dev/null; set +a
```

(Env vars do not persist across separate `bash_tool` calls, so per-call
sourcing is how every consumer works regardless of what boot loads.)

## Updating the pinned commits

`CLAUDE_SKILLS_SHA` / `MUNINN_UTILS_SHA` above are pinned, not `main`. Bump
them here — after reviewing the diff — when either repo changes and the
update should take effect. Floating on `main` means the code executed each
session is whatever happens to be latest and unreviewed; pinning makes the
skill file itself the reviewed artifact.
