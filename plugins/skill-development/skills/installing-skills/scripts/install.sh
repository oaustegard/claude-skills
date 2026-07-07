#!/bin/bash
# Install skills from github.com/oaustegard/claude-skills to /mnt/skills/user
set -e

SKILLS_DIR="/mnt/skills/user"
API_URL="https://api.github.com/repos/oaustegard/claude-skills/contents"
BASE_URL="https://raw.githubusercontent.com/oaustegard/claude-skills/main"
EXCLUDE_DIRS="templates|\.github|\.claude|\.uploads"

echo "Installing skills from github.com/oaustegard/claude-skills"

# Fetch repository structure
repo_contents=$(curl -s "$API_URL")
if [ -z "$repo_contents" ] || echo "$repo_contents" | grep -q '"message"'; then
    echo "Error: Failed to fetch repository contents from GitHub API"
    echo "Check network settings allow access to api.github.com"
    exit 1
fi

# Extract skill directory names (directories with SKILL.md files)
skill_names=$(echo "$repo_contents" | grep '"type": "dir"' -B 10 | grep '"name"' | cut -d'"' -f4 | grep -vE "^($EXCLUDE_DIRS)$")

count=0
installed=""
updated=""
skipped=""

for skill_name in $skill_names; do
    skill_url="${BASE_URL}/${skill_name}/SKILL.md"
    
    # Check if SKILL.md exists remotely
    if ! curl -s -f -o /dev/null "$skill_url"; then
        skipped="$skipped $skill_name"
        continue
    fi
    
    skill_path="${SKILLS_DIR}/${skill_name}"
    
    # Determine if new or update
    if [ -d "$skill_path" ]; then
        updated="$updated $skill_name"
    else
        mkdir -p "$skill_path"
        installed="$installed $skill_name"
    fi
    
    # Download SKILL.md
    curl -s "$skill_url" -o "${skill_path}/SKILL.md"
    count=$((count + 1))
done

echo ""
echo "✓ Processed $count skills"
[ -n "$installed" ] && echo "  Installed:$installed"
[ -n "$updated" ] && echo "  Updated:$updated"
[ -n "$skipped" ] && echo "  Skipped (no SKILL.md):$skipped"
