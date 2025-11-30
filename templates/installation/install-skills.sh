#!/bin/bash
set -e

# install-skills.sh
# Installs Claude Skills from the claude-skills repository to your project

# Configuration
REPO_URL="https://github.com/oaustegard/claude-skills.git"
TEMP_DIR=$(mktemp -d)
SKILLS_TARGET=".claude/skills"

# Skills to install (edit this array to customize)
# Use skill directory names from: https://github.com/oaustegard/claude-skills
SKILLS=(
  "asking-questions"
  "charting-vega-lite"
  "check-tools"
  "cloning-project"
  "convening-experts"
  "crafting-instructions"
  "creating-bookmarklets"
  "creating-mcp-servers"
  "developing-preact"
  "exploring-data"
  "extracting-keywords"
  "generating-patches"
  "hello-demo"
  "invoking-gemini"
  "invoking-github"
  "iterating"
  "mapping-codebases"
  "updating-knowledge"
  "versioning-skills"
)

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Installing Claude Skills...${NC}"

# Clone the repository
echo -e "${YELLOW}Cloning claude-skills repository...${NC}"
git clone --depth 1 "$REPO_URL" "$TEMP_DIR"

# Create skills directory if it doesn't exist
mkdir -p "$SKILLS_TARGET"

# Install each skill
for skill in "${SKILLS[@]}"; do
  if [ -d "$TEMP_DIR/$skill" ]; then
    echo -e "${GREEN}Installing skill: $skill${NC}"

    # Copy skill directory
    cp -r "$TEMP_DIR/$skill" "$SKILLS_TARGET/"

    # Remove workflow metadata files
    rm -f "$SKILLS_TARGET/$skill/VERSION"
    rm -f "$SKILLS_TARGET/$skill/README.md"

    # Remove any symlinks (they're repo-specific)
    find "$SKILLS_TARGET/$skill" -type l -delete
  else
    echo -e "${YELLOW}Warning: Skill '$skill' not found in repository${NC}"
  fi
done

# Cleanup
rm -rf "$TEMP_DIR"

echo -e "${GREEN}✓ Skills installation complete!${NC}"
echo -e "${BLUE}Installed to: $SKILLS_TARGET${NC}"
echo ""
echo "Skills are now available in your Claude Code sessions."
echo "To customize which skills are installed, edit the SKILLS array in this script."
