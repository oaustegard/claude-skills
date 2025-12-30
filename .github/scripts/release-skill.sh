#!/bin/bash
set -e

# Release skills based on VERSION file changes or manual trigger
# This script is called by the skill-release.yml GitHub Actions workflow

# Configure Git
git config --global user.name 'github-actions[bot]'
git config --global user.email 'github-actions[bot]@users.noreply.github.com'

# Track skills that had changelogs updated (for batch commit at end)
CHANGELOG_UPDATED_SKILLS=""

# Function to generate/update CHANGELOG.md for a skill
update_changelog() {
  local skill_dir="$1"
  local version="$2"
  local last_tag="$3"
  local release_date=$(date +%Y-%m-%d)
  local changelog_file="$skill_dir/CHANGELOG.md"

  # Extract skill display name from SKILL.md frontmatter or use directory name
  local skill_name="$skill_dir"
  if [ -f "$skill_dir/SKILL.md" ]; then
    local extracted_name=$(grep -m1 '^name:' "$skill_dir/SKILL.md" 2>/dev/null | sed 's/name:[[:space:]]*//' | tr -d '\r')
    if [ -n "$extracted_name" ]; then
      skill_name="$extracted_name"
    fi
  fi

  # Collect commits since last tag, categorized by conventional commit type
  local added_items=""
  local changed_items=""
  local fixed_items=""
  local other_items=""

  # Build git log command - use tag range if available, otherwise get recent skill commits
  local git_log_cmd=""
  if [ -n "$last_tag" ]; then
    git_log_cmd="git log --oneline ${last_tag}..HEAD -- ${skill_dir}/"
  else
    # No previous tag - get last 20 commits that touched this skill
    git_log_cmd="git log --oneline -20 -- ${skill_dir}/"
  fi

  # Parse commits and categorize
  while IFS= read -r line; do
    [ -z "$line" ] && continue

    # Extract commit message (skip hash)
    local msg=$(echo "$line" | sed 's/^[a-f0-9]* //')

    # Categorize by conventional commit prefix
    if echo "$msg" | grep -qiE '^feat(\(|:)'; then
      local clean_msg=$(echo "$msg" | sed -E 's/^feat(\([^)]*\))?:[[:space:]]*//')
      added_items="${added_items}- ${clean_msg}\n"
    elif echo "$msg" | grep -qiE '^fix(\(|:)'; then
      local clean_msg=$(echo "$msg" | sed -E 's/^fix(\([^)]*\))?:[[:space:]]*//')
      fixed_items="${fixed_items}- ${clean_msg}\n"
    elif echo "$msg" | grep -qiE '^(refactor|perf|style)(\(|:)'; then
      local clean_msg=$(echo "$msg" | sed -E 's/^(refactor|perf|style)(\([^)]*\))?:[[:space:]]*//')
      changed_items="${changed_items}- ${clean_msg}\n"
    elif echo "$msg" | grep -qiE '^(docs|chore|ci|build|test)(\(|:)'; then
      # Skip docs/chore/ci/build/test commits from changelog
      continue
    else
      # Non-conventional commits go to Other
      other_items="${other_items}- ${msg}\n"
    fi
  done < <(eval "$git_log_cmd" 2>/dev/null)

  # Build the new version entry
  local version_entry="## [$version] - $release_date\n"

  if [ -n "$added_items" ]; then
    version_entry="${version_entry}\n### Added\n\n${added_items}"
  fi

  if [ -n "$changed_items" ]; then
    version_entry="${version_entry}\n### Changed\n\n${changed_items}"
  fi

  if [ -n "$fixed_items" ]; then
    version_entry="${version_entry}\n### Fixed\n\n${fixed_items}"
  fi

  if [ -n "$other_items" ]; then
    version_entry="${version_entry}\n### Other\n\n${other_items}"
  fi

  # If no categorized commits, add a generic entry
  if [ -z "$added_items" ] && [ -z "$changed_items" ] && [ -z "$fixed_items" ] && [ -z "$other_items" ]; then
    version_entry="${version_entry}\n- Release $version\n"
  fi

  # Create or update CHANGELOG.md
  if [ -f "$changelog_file" ]; then
    # Existing changelog - insert new version after header (first two lines typically)
    # Find the line number of the first ## (version header)
    local first_version_line=$(grep -n '^## \[' "$changelog_file" | head -1 | cut -d: -f1)

    if [ -n "$first_version_line" ]; then
      # Insert before first version
      local head_content=$(head -n $((first_version_line - 1)) "$changelog_file")
      local tail_content=$(tail -n +$first_version_line "$changelog_file")

      printf "%s\n\n%b\n%s" "$head_content" "$version_entry" "$tail_content" > "$changelog_file"
    else
      # No version headers found, append after header
      printf "%s\n\n%b" "$(cat "$changelog_file")" "$version_entry" > "$changelog_file"
    fi
  else
    # Create new changelog
    local header="# ${skill_name} - Changelog\n\nAll notable changes to the \`${skill_dir}\` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).\n"

    printf "%b\n%b" "$header" "$version_entry" > "$changelog_file"
  fi

  echo "✓ Updated $changelog_file"
}

# Detect which skills to release
if [ "$GITHUB_EVENT_NAME" = "workflow_dispatch" ]; then
  # Manual trigger - use input parameter
  SKILLS="${WORKFLOW_DISPATCH_SKILL:-}"
  if [ -z "$SKILLS" ]; then
    echo "Error: No skill specified for manual dispatch"
    exit 1
  fi
  echo "Manual trigger for skill: $SKILLS"
else
  # Auto-detect from push - find VERSION files that changed
  CHANGED=$(git diff --name-only HEAD~1 HEAD | grep '^[^/]*/VERSION$' | cut -d'/' -f1 | tr '\n' ' ')
  SKILLS="$CHANGED"
fi

if [ -z "$SKILLS" ]; then
  echo "========================================="
  echo "No skills to release"
  echo "========================================="
  exit 0
fi

echo "Skills to release: $SKILLS"

for SKILL_DIR in $SKILLS; do
  echo ""
  echo "========================================="
  echo "Processing: $SKILL_DIR"
  echo "========================================="

  # Validate skill directory exists
  if [ ! -d "$SKILL_DIR" ]; then
    echo "Error: Directory $SKILL_DIR does not exist"
    exit 1
  fi

  # Read version from file or input
  if [ -n "${WORKFLOW_DISPATCH_VERSION:-}" ]; then
    VERSION="$WORKFLOW_DISPATCH_VERSION"
    echo "Using manual version: $VERSION"
  else
    if [ ! -f "$SKILL_DIR/VERSION" ]; then
      echo "Error: No VERSION file found in $SKILL_DIR"
      exit 1
    fi
    VERSION=$(cat "$SKILL_DIR/VERSION" | tr -d '[:space:]')
    echo "Using VERSION file: $VERSION"
  fi

  # Validate version format (basic semver check)
  if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "Error: Invalid version format '$VERSION' (expected semver like 1.0.0)"
    exit 1
  fi

  # Construct tag and release names
  TAG_NAME="$SKILL_DIR-v$VERSION"
  RELEASE_TITLE="$SKILL_DIR v$VERSION"

  echo "Tag: $TAG_NAME"
  echo "Title: $RELEASE_TITLE"

  # Check if release already exists
  if gh release view "$TAG_NAME" &>/dev/null; then
    echo "⚠️  Release $TAG_NAME already exists, skipping"
    continue
  fi

  # Validate skill structure
  if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
    echo "Error: No SKILL.md found in $SKILL_DIR"
    exit 1
  fi

  echo "✓ Skill structure validated"

  # Save repository root before changing directories
  REPO_ROOT=$(pwd)

  # Create ZIP with correct structure
  # The ZIP should contain the skill folder as its root
  TEMP_DIR=$(mktemp -d)
  echo "Creating ZIP in temp directory: $TEMP_DIR"

  # Copy skill folder to temp directory
  cp -r "$SKILL_DIR" "$TEMP_DIR/"

  # Create ZIP from temp directory (exclude README - auto-generated, CHANGELOG - merged to main separately, keep VERSION for runtime version detection)
  cd "$TEMP_DIR"
  zip -r "$SKILL_DIR.zip" "$SKILL_DIR/" -x "$SKILL_DIR/README.md" -x "$SKILL_DIR/CHANGELOG.md"

  echo "✓ Created $SKILL_DIR.zip"
  echo "ZIP contents:"
  unzip -l "$SKILL_DIR.zip" | head -20

  # Return to repository root for git operations
  cd "$REPO_ROOT"

  # Prepare release description content from README
  SKILL_README_CONTENT=$(cat "$SKILL_DIR/README.md" 2>/dev/null || echo "No README found for this skill.")
  SKILL_FOLDER_URL="https://github.com/${GITHUB_REPOSITORY}/tree/main/$SKILL_DIR"
  SKILL_DESCRIPTION_HEADER="$SKILL_README_CONTENT

**Skill folder:** [$SKILL_DIR]($SKILL_FOLDER_URL)"

  # Generate release notes
  # Try to get last tag for this skill
  LAST_TAG=$(git tag -l "$SKILL_DIR-v*" | sort -V | tail -n1 || echo "")

  if [ -n "$LAST_TAG" ]; then
    echo "Generating changelog from $LAST_TAG to HEAD"
    CHANGELOG=$(git log --oneline "$LAST_TAG..HEAD" -- "$SKILL_DIR/" | head -10 || echo "No changes found")
  else
    echo "No previous release found, using recent commits"
    CHANGELOG=$(git log --oneline HEAD~5..HEAD -- "$SKILL_DIR/" | head -10 || echo "Initial release")
  fi

  # Construct direct download URL
  DOWNLOAD_URL="https://github.com/${GITHUB_REPOSITORY}/releases/download/$TAG_NAME/$SKILL_DIR.zip"

  # Create release notes
  RELEASE_NOTES="$SKILL_DESCRIPTION_HEADER

---

Release of **$SKILL_DIR** version $VERSION

## 📥 Download & Install

**[⬇️ Download $SKILL_DIR.zip]($DOWNLOAD_URL)**

To install:
1. Click the download link above (ignore the \"Source code\" archives below - they're auto-generated by GitHub)
2. Go to [Claude.ai Skills Settings](https://claude.ai/settings/capabilities)
3. Upload the downloaded ZIP file
4. Requires paid Claude Pro or Team account

See [official documentation](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills) for more details.

## Recent Changes
\`\`\`
$CHANGELOG
\`\`\`"

  # Create GitHub release
  echo "Creating GitHub release..."
  gh release create "$TAG_NAME" \
    "$TEMP_DIR/$SKILL_DIR.zip" \
    --title "$RELEASE_TITLE" \
    --notes "$RELEASE_NOTES"

  if [ $? -eq 0 ]; then
    echo "✓ Successfully released $SKILL_DIR v$VERSION"
    echo "   View at: https://github.com/${GITHUB_REPOSITORY}/releases/tag/$TAG_NAME"

    # Update CHANGELOG.md for this skill
    echo "Updating CHANGELOG.md..."
    update_changelog "$SKILL_DIR" "$VERSION" "$LAST_TAG"
    CHANGELOG_UPDATED_SKILLS="${CHANGELOG_UPDATED_SKILLS} ${SKILL_DIR}"
  else
    echo "✗ Failed to create release for $SKILL_DIR"
    exit 1
  fi

  # Clean up temp directory
  rm -rf "$TEMP_DIR"

  echo ""
done

echo "========================================="
echo "All releases completed successfully!"
echo "========================================="

# Batch commit all changelog updates to main
# This won't trigger another release because the workflow only watches */VERSION paths
if [ -n "$CHANGELOG_UPDATED_SKILLS" ]; then
  echo ""
  echo "========================================="
  echo "Committing CHANGELOG updates to main"
  echo "========================================="

  # Stage all changelog files
  for skill in $CHANGELOG_UPDATED_SKILLS; do
    if [ -f "$skill/CHANGELOG.md" ]; then
      git add "$skill/CHANGELOG.md"
      echo "Staged: $skill/CHANGELOG.md"
    fi
  done

  # Check if there are staged changes
  if git diff --cached --quiet; then
    echo "No changelog changes to commit"
  else
    # Create commit message listing all updated skills
    SKILL_LIST=$(echo "$CHANGELOG_UPDATED_SKILLS" | tr ' ' '\n' | grep -v '^$' | sort | tr '\n' ', ' | sed 's/,$//')
    COMMIT_MSG="docs: Update CHANGELOG.md for released skills

Skills updated: $SKILL_LIST

[skip ci]"

    git commit -m "$COMMIT_MSG"
    echo "✓ Committed changelog updates"

    # Push to main
    echo "Pushing to main..."
    git push origin HEAD:main
    if [ $? -eq 0 ]; then
      echo "✓ Successfully pushed changelog updates to main"
    else
      echo "⚠️  Failed to push changelog updates (releases were still successful)"
      echo "   Changelog updates may need to be pushed manually"
    fi
  fi
fi
