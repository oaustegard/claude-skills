#!/bin/bash
# Muninn boot — fetch pinned repos, load boot env, run boot().
# Pins below are the reviewed artifact; bump only after reviewing the diff.
set -e

# ---- warm-container fast path -------------------------------------------
# The project instruction is reinjected with every message, so this script
# may be invoked many times per conversation. The sentinel couples its
# lifetime to the container's: a recycled container has no sentinel and
# boots fully; a warm one exits here in ~0s. Content = the pins, so bumping
# either SHA self-invalidates the fast path. `rm` the sentinel to force.
CLAUDE_SKILLS_SHA=b2fe13742b32400f8b69e8b793289fe1e7d107be
MUNINN_UTILS_SHA=ccbb64725f4351c5eb0d95811f2c46a297e2fe67
SENTINEL=/home/claude/.muninn-booted
WANT="$CLAUDE_SKILLS_SHA $MUNINN_UTILS_SHA"
if [ -z "$BOOT_MODE" ] \
   && [ "$(cat "$SENTINEL" 2>/dev/null)" = "$WANT" ] \
   && [ -d /home/claude/muninn-utilities/muninn_utils ]; then
  echo "warm boot: already booted this container ($WANT). rm $SENTINEL to force."
  exit 0
fi
# --------------------------------------------------------------------------

cd /tmp

curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/$CLAUDE_SKILLS_SHA" -o cs.tar.gz \
  && tar -xzf cs.tar.gz \
  && rm -rf "claude-skills-$CLAUDE_SKILLS_SHA/remembering" \
  && mkdir -p /mnt/skills/user \
  && cp -r claude-skills-$CLAUDE_SKILLS_SHA/* /mnt/skills/user/
# (the repo's remembering/ dir is a relocation stub — excluded above so it
#  can never clobber a project-uploaded remembering skill at the same path)

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

# written last, only on success; content = pins so a pin bump invalidates it
printf '%s' "$WANT" > "$SENTINEL"
