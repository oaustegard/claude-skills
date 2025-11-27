#!/bin/bash
set -e

# Process skill uploads from the uploads/ directory
# This script is called by the skill-upload.yml GitHub Actions workflow

# Check if this is a manual trigger (workflow_dispatch) or automatic (push)
EVENT_NAME="${GITHUB_EVENT_NAME:-push}"

if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
  echo "========================================="
  echo "Manual workflow trigger detected"
  echo "Will process all zip files in uploads/"
  echo "========================================="
  echo ""
else
  # For push events, only process zip files that were added or modified
  # Use HEAD~1 as fallback if before commit is not available
  BEFORE_COMMIT="${GITHUB_BEFORE_COMMIT:-}"
  if [ -z "$BEFORE_COMMIT" ] || ! git rev-parse --verify "$BEFORE_COMMIT" >/dev/null 2>&1; then
    BEFORE_COMMIT="HEAD~1"
  fi

  ADDED_OR_MODIFIED=$(git diff --name-status "$BEFORE_COMMIT" HEAD 2>/dev/null | grep -E '^(A|M)\s+uploads/.*\.zip$' || true)

  if [ -z "$ADDED_OR_MODIFIED" ]; then
    echo "========================================="
    echo "No zip files were added or modified in this push."
    echo "Only deletions or non-zip changes detected."
    echo "Exiting gracefully."
    echo "========================================="
    exit 0
  fi

  echo "Detected zip file changes:"
  echo "$ADDED_OR_MODIFIED"
  echo ""
fi

# Find all zip files in uploads directory
ZIP_FILES=$(find uploads -name "*.zip" -type f 2>/dev/null || true)

if [ -z "$ZIP_FILES" ]; then
  echo "========================================="
  echo "No .zip files found in uploads directory."
  echo "This is normal if:"
  echo "  - Zip files were already processed"
  echo "  - Zip files were manually deleted"
  echo "  - Only non-zip files were modified"
  echo "Exiting gracefully."
  echo "========================================="
  exit 0
fi

# Count how many files we're processing
FILE_COUNT=$(echo "$ZIP_FILES" | wc -l)
echo "Found $FILE_COUNT skill(s) to process"

# Configure git once for all operations
git config --global user.name 'github-actions[bot]'
git config --global user.email 'github-actions[bot]@users.noreply.github.com'

# Store the main branch name
MAIN_BRANCH=$(git branch --show-current)

# Get the script directory for calling generate-readme.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Process each zip file
COUNTER=1
echo "$ZIP_FILES" | while IFS= read -r ZIP_FILE; do
  echo ""
  echo "========================================="
  echo "Processing skill $COUNTER of $FILE_COUNT: $ZIP_FILE"
  echo "========================================="

  # Extract the zip file
  TEMP_DIR=$(mktemp -d)
  unzip "$ZIP_FILE" -d "$TEMP_DIR/extracted_skill"
  echo "Extracted files:"
  ls -R "$TEMP_DIR/extracted_skill"

  EXTRACTED_PATH="$TEMP_DIR/extracted_skill"

  # Remove macOS metadata if present
  if [ -d "$EXTRACTED_PATH/__MACOSX" ]; then
    echo "Removing macOS metadata folder (__MACOSX)"
    rm -rf "$EXTRACTED_PATH/__MACOSX"
  fi

  # Remove .DS_Store files (macOS Finder metadata)
  find "$EXTRACTED_PATH" -name ".DS_Store" -type f -delete 2>/dev/null || true

  # Remove ._* files (macOS resource forks)
  find "$EXTRACTED_PATH" -name "._*" -type f -delete 2>/dev/null || true

  # Handle case where zip contains a single root directory
  # Count items in extracted path (excluding __MACOSX which we just removed)
  ITEM_COUNT=$(find "$EXTRACTED_PATH" -mindepth 1 -maxdepth 1 | wc -l)
  if [ "$ITEM_COUNT" -eq 1 ]; then
    SINGLE_ITEM=$(find "$EXTRACTED_PATH" -mindepth 1 -maxdepth 1)
    if [ -d "$SINGLE_ITEM" ]; then
      echo "Zip contains single root directory, using it as base path"
      EXTRACTED_PATH="$SINGLE_ITEM"
    fi
  fi

  echo "Using path: $EXTRACTED_PATH"

  # Validate: Check for SKILL.md
  SKILL_MD_PATH="$EXTRACTED_PATH/SKILL.md"
  if [ ! -f "$SKILL_MD_PATH" ]; then
    echo "Error: SKILL.md not found in $ZIP_FILE!"
    echo "Expected at: $SKILL_MD_PATH"
    rm -rf "$TEMP_DIR"
    exit 1
  fi

  # Use the folder name as the skill name (simpler and more reliable)
  SKILL_NAME=$(basename "$EXTRACTED_PATH")
  echo "Skill name: $SKILL_NAME"

  # Security Validations
  echo "Running security checks..."

  # Path Traversal Check
  if find "$EXTRACTED_PATH" -type f | grep -q '/\.\./'; then
    echo "Error: Path traversal detected in $ZIP_FILE"
    rm -rf "$TEMP_DIR"
    exit 1
  fi

  # File Type Check - Block compiled executables, binaries, and nested archives
  # Scripts (.sh, .py, .bat, etc.) are allowed since they're reviewable text files
  BLOCKED_EXTENSIONS=("exe" "dll" "so" "dylib" "bin" "app" "jar" "zip" "tar" "gz" "7z" "rar" "dmg" "iso" "msi" "deb" "rpm")
  for file in $(find "$EXTRACTED_PATH" -type f); do
    extension="${file##*.}"
    # Convert to lowercase for comparison
    extension_lower=$(echo "$extension" | tr '[:upper:]' '[:lower:]')
    if [[ " ${BLOCKED_EXTENSIONS[@]} " =~ " ${extension_lower} " ]]; then
      echo "Error: Blocked file type found in $ZIP_FILE: $file"
      echo "Blocked extensions: executables, binaries, archives, and system scripts"
      rm -rf "$TEMP_DIR"
      exit 1
    fi
  done

  # Zip Bomb check
  MAX_FILES=1000
  EXTRACTED_FILE_COUNT=$(find "$EXTRACTED_PATH" -type f | wc -l)
  if [ "$EXTRACTED_FILE_COUNT" -gt "$MAX_FILES" ]; then
    echo "Error: Too many files in $ZIP_FILE (max $MAX_FILES)"
    rm -rf "$TEMP_DIR"
    exit 1
  fi

  echo "Security checks passed!"

  # Prepare skill directory name
  SKILL_DIR_NAME=$(echo "$SKILL_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/ /-/g')
  echo "Skill directory: $SKILL_DIR_NAME"

  # Create unique branch name for this skill (includes run ID to avoid conflicts)
  BRANCH_NAME="skill-upload/$SKILL_DIR_NAME-${GITHUB_RUN_ID:-$(date +%s)}"
  echo "Creating branch: $BRANCH_NAME"

  git checkout -b "$BRANCH_NAME"

  # Copy skill files (exclude VCS directories and VERSION file)
  # VERSION files are workflow metadata, not part of the skill content
  rsync -av --delete --exclude='.git' --exclude='.svn' --exclude='.hg' --exclude='VERSION' "$EXTRACTED_PATH/" "$SKILL_DIR_NAME/"

  # Generate README.md from SKILL.md frontmatter
  echo "Generating README.md using Python..."
  python3 "$SCRIPT_DIR/generate-readme.py" "$SKILL_DIR_NAME"

  # Create symlink in .claude/skills/ for project-level skill availability
  echo "Creating symlink in .claude/skills/"
  mkdir -p .claude/skills
  ln -sf "../../$SKILL_DIR_NAME" ".claude/skills/$SKILL_DIR_NAME"
  echo "✓ Symlink created: .claude/skills/$SKILL_DIR_NAME -> ../../$SKILL_DIR_NAME"

  # Add the new skill files, symlink, and remove the original zip file
  git add "$SKILL_DIR_NAME"
  git add .claude/skills/"$SKILL_DIR_NAME"
  git rm "$ZIP_FILE"

  git commit -m "feat(skills): Add/Update skill: $SKILL_NAME"
  git push origin "$BRANCH_NAME"

  # Create Pull Request
  gh pr create \
    --title "feat(skills): Add/Update skill: $SKILL_NAME" \
    --body "Automated skill upload for **$SKILL_NAME**.

*This PR was generated automatically from the file \`$ZIP_FILE\`.*

Please review the skill contents, especially \`SKILL.md\`, before merging."

  echo "✓ Successfully created PR for $SKILL_NAME"

  # Clean up temp directory
  rm -rf "$TEMP_DIR"

  # Return to main branch for next iteration
  git checkout "$MAIN_BRANCH"

  COUNTER=$((COUNTER + 1))
done

echo ""
echo "========================================="
echo "All skills processed successfully!"
echo "========================================="
