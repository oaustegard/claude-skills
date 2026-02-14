#!/bin/bash
# apply-skillignore.sh — Remove files matching .skillignore patterns from a skill directory
#
# Usage: apply_skillignore <skill_dir>
#
# Reads patterns from <skill_dir>/.skillignore (if present) and combines them
# with built-in default patterns. Deletes matching files/directories from <skill_dir>.
#
# Pattern format (subset of .gitignore):
#   - Lines starting with # are comments
#   - Empty lines are ignored
#   - Patterns are matched against relative paths within the skill directory
#   - Trailing / matches directories only
#   - Leading / anchors to skill root (otherwise matches anywhere)
#   - Standard glob wildcards: * ? [...]
#
# The .skillignore file itself is always removed from the output.
#
# Examples:
#   _ARCH.md          # Remove _ARCH.md anywhere in tree
#   /docs/internal/   # Remove docs/internal/ directory at root only
#   *.log             # Remove all .log files
#   tests/            # Remove all tests/ directories

# Default patterns applied to ALL skills during release packaging.
# These are repo/development artifacts that should never ship to end users.
DEFAULT_SKILLIGNORE_PATTERNS=(
  # Generated repo artifacts
  "README.md"
  "CHANGELOG.md"
  "_MAP.md"

  # Development context files
  "CLAUDE.md"

  # Test suites
  "tests/"

  # Python bytecode
  "__pycache__/"
  "*.pyc"
  "*.pyo"

  # OS metadata
  ".DS_Store"
  "._*"

  # The .skillignore file itself
  ".skillignore"
)

apply_skillignore() {
  local skill_dir="$1"

  if [ -z "$skill_dir" ] || [ ! -d "$skill_dir" ]; then
    echo "Error: apply_skillignore requires a valid directory path"
    return 1
  fi

  local patterns=()
  local files_removed=0
  local dirs_removed=0

  # Load default patterns
  for pattern in "${DEFAULT_SKILLIGNORE_PATTERNS[@]}"; do
    patterns+=("$pattern")
  done

  # Load skill-specific patterns from .skillignore if present
  local skillignore_file="$skill_dir/.skillignore"
  if [ -f "$skillignore_file" ]; then
    echo "  Found .skillignore in $skill_dir"
    while IFS= read -r line || [ -n "$line" ]; do
      # Strip trailing whitespace/CR
      line=$(echo "$line" | sed 's/[[:space:]]*$//')
      # Skip empty lines and comments
      [ -z "$line" ] && continue
      [[ "$line" == \#* ]] && continue
      patterns+=("$line")
    done < "$skillignore_file"
  fi

  # Apply each pattern
  for pattern in "${patterns[@]}"; do
    # Directory pattern (trailing /)
    if [[ "$pattern" == */ ]]; then
      local dir_pattern="${pattern%/}"
      if [[ "$dir_pattern" == /* ]]; then
        # Anchored to root
        dir_pattern="${dir_pattern#/}"
        if [ -d "$skill_dir/$dir_pattern" ]; then
          rm -rf "$skill_dir/$dir_pattern"
          dirs_removed=$((dirs_removed + 1))
        fi
      else
        # Match anywhere in tree
        find "$skill_dir" -type d -name "$dir_pattern" -exec rm -rf {} + 2>/dev/null
        dirs_removed=$((dirs_removed + 1))
      fi
      continue
    fi

    # File pattern
    if [[ "$pattern" == /* ]]; then
      # Anchored to root — single file/glob at skill root
      pattern="${pattern#/}"
      # Use find with -maxdepth based on path depth
      local depth=$(echo "$pattern" | tr -cd '/' | wc -c)
      depth=$((depth + 1))
      local dir_part=$(dirname "$pattern")
      local file_part=$(basename "$pattern")
      if [ "$dir_part" = "." ]; then
        find "$skill_dir" -maxdepth 1 -name "$file_part" -delete 2>/dev/null
      else
        find "$skill_dir/$dir_part" -maxdepth 1 -name "$file_part" -delete 2>/dev/null
      fi
    else
      # Unanchored — match anywhere in tree
      find "$skill_dir" -name "$pattern" -delete 2>/dev/null
    fi
    files_removed=$((files_removed + 1))
  done

  echo "  Applied ${#patterns[@]} ignore patterns to $skill_dir"
}
