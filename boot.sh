#!/bin/bash
# Muninn boot - minimal installer + memory system init
set -e

SKILLS_DIR=/mnt/skills/user
REPO_BASE=https://raw.githubusercontent.com/oaustegard/claude-skills/main

# Ensure core skills exist
for skill in indexing-remote-skills remembering; do
    [ -d "$SKILLS_DIR/$skill" ] && continue
    
    mkdir -p "$SKILLS_DIR/$skill"
    curl -sf "$REPO_BASE/$skill/SKILL.md" -o "$SKILLS_DIR/$skill/SKILL.md" || {
        echo "Failed to fetch $skill"
        exit 1
    }
    
    # Fetch scripts directory if it exists
    if curl -sf "https://api.github.com/repos/oaustegard/claude-skills/contents/$skill/scripts" > /tmp/files.json 2>/dev/null; then
        mkdir -p "$SKILLS_DIR/$skill/scripts"
        grep -o '"name": "[^"]*"' /tmp/files.json | sed 's/"name": "\(.*\)"/\1/' | while read file; do
            curl -sf "$REPO_BASE/$skill/scripts/$file" -o "$SKILLS_DIR/$skill/scripts/$file"
        done
    fi
done

# Boot Muninn
set -a; [ -f /mnt/project/turso.env ] && . /mnt/project/turso.env 2>/dev/null; set +a
python3 << 'EOF'
import sys
sys.path.insert(0, '/mnt/skills/user/remembering')
from scripts import boot
print(boot())
EOF
