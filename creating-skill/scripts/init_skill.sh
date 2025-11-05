#!/bin/bash
# Initialize a new skill from template

if [ "$#" -ne 2 ] || [ "$1" != "--name" ]; then
    echo "Usage: init_skill.sh --name <skill-name>"
    echo ""
    echo "Skill name requirements:"
    echo "  - Lowercase letters, numbers, and hyphens only"
    echo "  - Use gerund form (e.g., 'processing-pdfs', 'analyzing-data')"
    echo ""
    echo "Example:"
    echo "  init_skill.sh --name processing-images"
    exit 1
fi

SKILL_NAME="$2"
SKILL_TITLE=$(echo "$SKILL_NAME" | sed 's/-/ /g; s/\b\(.\)/\u\1/g')
OUTPUT_DIR="/home/claude/$SKILL_NAME"

# Check if directory already exists
if [ -d "$OUTPUT_DIR" ]; then
    echo "❌ Error: Directory already exists: $OUTPUT_DIR"
    exit 1
fi

# Create skill directory structure
echo "🚀 Creating skill: $SKILL_NAME"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/scripts"
mkdir -p "$OUTPUT_DIR/references"
mkdir -p "$OUTPUT_DIR/assets"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="$SCRIPT_DIR/../assets/SKILL.md.template"

# Create SKILL.md from template
sed "s/{{SKILL_NAME}}/$SKILL_NAME/g; s/{{SKILL_TITLE}}/$SKILL_TITLE/g" \
    "$TEMPLATE_PATH" > "$OUTPUT_DIR/SKILL.md"

echo "✅ Created skill directory: $OUTPUT_DIR"
echo "✅ Created SKILL.md from template"
echo "✅ Created resource directories"
echo ""
echo "Next steps:"
echo "1. Edit $OUTPUT_DIR/SKILL.md - complete the TODO items"
echo "2. Add scripts, references, or assets as needed (delete unused directories)"
echo "3. Package the skill:"
echo "   cd /home/claude && zip -r /mnt/user-data/outputs/$SKILL_NAME.zip $SKILL_NAME/"
