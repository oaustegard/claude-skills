#!/usr/bin/env python3
"""
Generate README.md from SKILL.md frontmatter.

Usage: generate-readme.py <skill_directory>
"""

import sys
import os
import re
import yaml


def generate_readme(skill_dir):
    """Generate README.md from SKILL.md frontmatter in the given skill directory."""
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')
    readme_path = os.path.join(skill_dir, 'README.md')

    if not os.path.exists(skill_md_path):
        print(f'⚠️  SKILL.md not found in {skill_dir}')
        return False

    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'^---\s*\n(.*?\n)---\s*\n', content, re.DOTALL)

            if not match:
                print('⚠️  Could not find frontmatter in SKILL.md.')
                return False

            frontmatter_str = match.group(1)
            frontmatter = yaml.safe_load(frontmatter_str)

            if not frontmatter or 'name' not in frontmatter or 'description' not in frontmatter:
                print('⚠️  Frontmatter is missing name or description.')
                return False

            readme_content = f"# {frontmatter['name']}\n\n{frontmatter['description']}\n"

            with open(readme_path, 'w', encoding='utf-8') as rf:
                rf.write(readme_content)

            print('✓ Generated README.md')
            return True

    except Exception as e:
        print(f'Error: {e}')
        return False


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: generate-readme.py <skill_directory>')
        sys.exit(1)

    skill_dir = sys.argv[1]
    success = generate_readme(skill_dir)
    sys.exit(0 if success else 1)
