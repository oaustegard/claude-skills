#!/usr/bin/env python3
"""
Validation script for verifying skill structure and basic functionality
without requiring external dependencies like the anthropic library.
"""

import ast
import sys
from pathlib import Path


def validate_python_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate Python file has correct syntax"""
    try:
        with open(file_path, 'r') as f:
            code = f.read()
        ast.parse(code)
        return True, "Valid Python syntax"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def validate_skill_structure(skill_name: str) -> dict:
    """Validate a skill has the correct structure"""
    results = {}
    skill_path = Path(__file__).parent / skill_name

    # Check skill directory exists
    results["Directory exists"] = skill_path.exists()

    if not skill_path.exists():
        return results

    # Check SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    results["SKILL.md exists"] = skill_md.exists()

    if skill_md.exists():
        with open(skill_md, 'r') as f:
            content = f.read()
        results["SKILL.md has frontmatter"] = content.startswith("---")
        results["SKILL.md has name"] = "name:" in content[:200]
        results["SKILL.md has description"] = "description:" in content[:500]

    # Check scripts directory
    scripts_dir = skill_path / "scripts"
    results["scripts/ exists"] = scripts_dir.exists()

    # Check Python files in scripts
    if scripts_dir.exists():
        py_files = list(scripts_dir.glob("*.py"))
        results[f"Python files ({len(py_files)})"] = len(py_files) > 0

        for py_file in py_files:
            valid, msg = validate_python_syntax(py_file)
            results[f"{py_file.name} syntax"] = valid
            if not valid:
                results[f"{py_file.name} error"] = msg

    return results


def main():
    """Run validation on new skills"""
    print("=" * 70)
    print("SKILL VALIDATION")
    print("=" * 70)

    skills_to_validate = ["api-credentials", "invoking-claude"]

    all_passed = True

    for skill_name in skills_to_validate:
        print(f"\n### Validating: {skill_name} ###\n")
        results = validate_skill_structure(skill_name)

        for check, status in results.items():
            if isinstance(status, bool):
                symbol = "✓" if status else "✗"
                print(f"  {symbol} {check}")
                if not status:
                    all_passed = False
            else:
                print(f"    → {check}: {status}")

    print("\n" + "=" * 70)

    # Specific validation for api-credentials
    print("\n### api-credentials specific checks ###\n")

    api_creds_path = Path(__file__).parent / "api-credentials"

    checks = {
        "credentials.py": api_creds_path / "scripts" / "credentials.py",
        "config.json.example": api_creds_path / "assets" / "config.json.example",
        ".gitignore": api_creds_path / ".gitignore",
    }

    for name, path in checks.items():
        exists = path.exists()
        symbol = "✓" if exists else "✗"
        print(f"  {symbol} {name} exists")
        if not exists:
            all_passed = False

    # Check .gitignore contains config.json
    gitignore = api_creds_path / ".gitignore"
    if gitignore.exists():
        with open(gitignore, 'r') as f:
            content = f.read()
        has_config = "config.json" in content
        symbol = "✓" if has_config else "✗"
        print(f"  {symbol} .gitignore includes config.json")
        if not has_config:
            all_passed = False

    # Specific validation for invoking-claude
    print("\n### invoking-claude specific checks ###\n")

    invoking_path = Path(__file__).parent / "invoking-claude"

    checks = {
        "claude_client.py": invoking_path / "scripts" / "claude_client.py",
        "test_integration.py": invoking_path / "scripts" / "test_integration.py",
        "api-reference.md": invoking_path / "references" / "api-reference.md",
    }

    for name, path in checks.items():
        exists = path.exists()
        symbol = "✓" if exists else "✗"
        print(f"  {symbol} {name} exists")
        if not exists:
            all_passed = False

    # Check for key functions in claude_client.py
    claude_client = invoking_path / "scripts" / "claude_client.py"
    if claude_client.exists():
        with open(claude_client, 'r') as f:
            content = f.read()

        required_functions = [
            "invoke_claude",
            "invoke_parallel",
            "ClaudeInvocationError"
        ]

        print("\n  Required functions in claude_client.py:")
        for func in required_functions:
            has_func = f"def {func}" in content or f"class {func}" in content
            symbol = "✓" if has_func else "✗"
            print(f"    {symbol} {func}")
            if not has_func:
                all_passed = False

    print("\n" + "=" * 70)
    print("\nVALIDATION SUMMARY")
    print("=" * 70)

    if all_passed:
        print("✓ All validations passed!")
        print("\nNote: Integration tests require 'anthropic' library:")
        print("  pip install anthropic")
    else:
        print("✗ Some validations failed!")
        return 1

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
