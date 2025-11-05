---
name: check-tools
description: Development environment validation skill for verifying tool installations across Python, Node.js, Java, Go, Rust, C/C++, and common utilities. Use when validating development environments, troubleshooting missing dependencies, documenting system requirements, setting up CI/CD pipelines, or creating environment health checks.
---

# Check Tools - Development Environment Validator

## Overview

Transform Claude into a specialized development environment validation expert capable of systematically checking for required development tools, reporting their versions, and validating complete toolchains across multiple programming language ecosystems.

## Core Philosophy

**Comprehensive Validation**: Systematically verify the presence and versions of development tools across all major programming language ecosystems. Provide clear, actionable feedback about what's installed, what's missing, and what versions are available.

**Ecosystem Awareness**: Understand the interdependencies between tools (e.g., Node.js requires npm, Python projects may need both pip and poetry) and validate complete toolchains rather than isolated tools.

## When to Use This Skill

Trigger this skill when working on:

- **Environment setup verification** - Validating that all required tools are installed
- **Troubleshooting build failures** - Checking for missing dependencies or version mismatches
- **Documentation generation** - Creating system requirements documentation
- **CI/CD pipeline setup** - Ensuring container images have required tools
- **Onboarding new developers** - Verifying development environment readiness
- **Cross-platform development** - Checking tool availability across different operating systems
- **Polyglot projects** - Validating toolchains for multiple programming languages

## Tool Categories

### 1. Python Ecosystem

**Core Tools**:
- `python3`, `python` - Python interpreters
- `pip` - Package installer

**Development Tools**:
- `poetry` - Dependency management and packaging
- `uv` - Fast Python package installer
- `black` - Code formatter
- `mypy` - Static type checker
- `pytest` - Testing framework
- `ruff` - Fast Python linter

**Validation Pattern**:
```bash
if command -v python3 &> /dev/null; then
    python3 --version
fi
```

### 2. Node.js Ecosystem

**Core Tools**:
- `node` - Node.js runtime
- `npm` - Package manager
- `nvm` - Node version manager

**Alternative Package Managers**:
- `yarn` - Fast, reliable package manager
- `pnpm` - Efficient disk space package manager

**Development Tools**:
- `eslint` - JavaScript linter
- `prettier` - Code formatter
- `chromedriver` - Browser automation

**Validation Pattern**:
```bash
if command -v node &> /dev/null; then
    node --version
    # Check for multiple Node versions via nvm
    if [[ -s "/opt/nvm/nvm.sh" ]]; then
        source "/opt/nvm/nvm.sh"
        nvm list
    fi
fi
```

### 3. Java Ecosystem

**Core Tools**:
- `java` - Java runtime and compiler
- `mvn` - Maven build tool
- `gradle` - Gradle build tool

**Validation Pattern**:
```bash
if command -v java &> /dev/null; then
    java -version 2>&1 | head -3
fi
```

### 4. Go Ecosystem

**Core Tools**:
- `go` - Go compiler and toolchain

**Validation Pattern**:
```bash
if command -v go &> /dev/null; then
    go version
fi
```

### 5. Rust Ecosystem

**Core Tools**:
- `rustc` - Rust compiler
- `cargo` - Rust package manager and build tool

**Environment Setup**:
```bash
# Source cargo environment if it exists
if [[ -f "$HOME/.cargo/env" ]]; then
    source "$HOME/.cargo/env"
fi
```

### 6. C/C++ Ecosystem

**Compilers**:
- `gcc` - GNU Compiler Collection
- `clang` - LLVM C/C++ compiler

**Build Tools**:
- `cmake` - Cross-platform build system
- `ninja` - Small build system with focus on speed
- `conan` - C/C++ package manager

**Validation Pattern**:
```bash
if command -v gcc &> /dev/null; then
    gcc --version | head -1
fi
```

### 7. System Utilities

**Essential Tools**:
- `git` - Version control
- `curl` - Data transfer tool
- `jq` - JSON processor
- `rg` (ripgrep) - Fast text search
- `tmux` - Terminal multiplexer

**Text Processing**:
- `awk` - Pattern scanning and processing
- `sed` - Stream editor
- `grep` - Pattern matching

**Compression**:
- `gzip` - File compression
- `tar` - Archive utility

**Editors**:
- `vim` - Vi improved
- `nano` - Simple text editor

## Validation Strategies

### 1. Basic Tool Presence Check

```bash
if command -v tool_name &> /dev/null; then
    echo "✅ tool_name: installed"
else
    echo "❌ tool_name: not found"
fi
```

### 2. Version Extraction

Different tools output version information differently:

```bash
# Standard --version flag
tool_name --version

# Java-style version to stderr
java -version 2>&1

# Extract specific version numbers
eslint --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
```

### 3. Environment-Specific Tool Loading

```bash
# NVM for Node.js
if [[ -s "/opt/nvm/nvm.sh" ]]; then
    source "/opt/nvm/nvm.sh"
fi

# Cargo for Rust
if [[ -f "$HOME/.cargo/env" ]]; then
    source "$HOME/.cargo/env"
fi
```

### 4. Required vs Optional Tools

Track validation failures for required tools:

```bash
VALIDATION_FAILED=0

if ! command -v required_tool &> /dev/null; then
    echo "❌ required_tool: not found"
    VALIDATION_FAILED=1
fi

if ! command -v optional_tool &> /dev/null; then
    echo "⚠️  optional_tool: not found (optional)"
fi

if [[ $VALIDATION_FAILED -eq 1 ]]; then
    exit 1
fi
```

## Output Formatting

### Visual Indicators

- ✅ Tool found and working
- ❌ Tool not found or not working
- ⚠️  Tool optional but recommended

### Categorical Organization

Group tools by ecosystem for clarity:

```
=================== Python ===================
✅ python3: Python 3.11.4
✅ pip: pip 23.1.2
✅ poetry: Poetry (version 1.5.1)
❌ mypy: not found

=================== NodeJS ===================
✅ node: v20.5.0
✅ npm: 9.8.0
...
```

### ASCII Art Banners

Create visually appealing output for tool reports:

```bash
cat << 'EOF'
   _____ _                 _        _____           _
  / ____| |               | |      / ____|         | |
 | |    | | __ _ _   _  __| | ___  | |     ___   __| | ___
 | |    | |/ _` | | | |/ _` |/ _ \ | |    / _ \ / _` |/ _ \
 | |____| | (_| | |_| | (_| |  __/ | |___| (_) | (_| |  __/
  \_____|_|\__,_|\__,_|\__,_|\___|  \_____\___/ \__,_|\___|

      Development Environment Tool Versions
      =====================================
EOF
```

## Common Use Cases

### 1. Container/Docker Environment Validation

When setting up development containers, validate that all required tools are installed:

```bash
#!/bin/bash
# Validate Python data science environment
check_tool python3 "required"
check_tool pip "required"
check_tool jupyter "required"
check_tool pandas "optional - data analysis"
check_tool numpy "optional - numerical computing"
```

### 2. CI/CD Pipeline Health Checks

Add environment validation as the first step in CI pipelines:

```yaml
# .github/workflows/validate.yml
steps:
  - name: Validate Build Environment
    run: |
      ./scripts/check-tools.sh
      if [ $? -ne 0 ]; then
        echo "Build environment validation failed"
        exit 1
      fi
```

### 3. Multi-Language Project Setup

For polyglot projects, validate all required language toolchains:

```bash
# Check Python tools
validate_python_environment

# Check Node.js tools
validate_nodejs_environment

# Check system utilities
validate_system_utilities
```

### 4. Developer Onboarding Scripts

Create interactive setup validation:

```bash
echo "Validating your development environment..."
./check-tools.sh

if [ $? -eq 0 ]; then
    echo "✅ Your environment is ready for development!"
else
    echo "❌ Please install missing tools before proceeding"
    echo "Refer to SETUP.md for installation instructions"
fi
```

## Implementation Patterns

### Modular Validation Functions

```bash
validate_python_tools() {
    local failed=0

    for tool in python3 pip poetry pytest black; do
        if ! command -v "$tool" &> /dev/null; then
            echo "❌ $tool: not found"
            failed=1
        else
            echo "✅ $tool: $($tool --version 2>&1 | head -1)"
        fi
    done

    return $failed
}
```

### JSON Output for Programmatic Use

```bash
# Generate JSON report
{
    echo '{'
    echo '  "timestamp": "'$(date -Iseconds)'",'
    echo '  "tools": {'

    if command -v python3 &> /dev/null; then
        echo '    "python3": "'$(python3 --version)'",'
    fi

    echo '  }'
    echo '}'
} > environment-report.json
```

### Cross-Platform Compatibility

```bash
# Handle differences between Linux and macOS
case "$(uname -s)" in
    Linux*)
        check_linux_specific_tools
        ;;
    Darwin*)
        check_macos_specific_tools
        ;;
    MINGW*|MSYS*|CYGWIN*)
        check_windows_specific_tools
        ;;
esac
```

## Best Practices

1. **Fail Fast**: Exit immediately when critical tools are missing
2. **Clear Messaging**: Use visual indicators and categorical organization
3. **Version Reporting**: Always show versions, not just presence
4. **Environment Sourcing**: Load tool-specific environments (nvm, cargo) before checking
5. **Stderr Handling**: Many tools output version info to stderr, redirect appropriately
6. **Exit Codes**: Return non-zero exit codes when validation fails
7. **Categorization**: Group related tools together for clarity
8. **Optional vs Required**: Clearly distinguish between required and optional tools

## Constraints

**DO NOT**:
- Assume tool locations - always use `command -v`
- Ignore stderr - many tools output versions to stderr
- Skip environment sourcing for version managers (nvm, cargo, etc.)
- Use hardcoded paths instead of PATH lookup

**DO**:
- Check for tool presence before attempting to run it
- Handle tool output variations gracefully
- Provide clear feedback about what's missing
- Group tools by ecosystem or purpose
- Return appropriate exit codes

## Reference Files

- **`assets/check-tools.sh`**: Complete reference implementation of the environment validation script
- **`references/tool-categories.md`**: Detailed breakdown of tools by category with installation instructions

## Validation Checklist

Before delivering an environment validation script, verify:

- [ ] All required tools are checked
- [ ] Version information is extracted correctly
- [ ] Environment-specific loaders are sourced (nvm, cargo)
- [ ] Output is well-formatted and categorized
- [ ] Exit codes properly reflect validation status
- [ ] Both stdout and stderr are handled correctly
- [ ] Visual indicators (✅/❌) are used consistently
- [ ] Required vs optional tools are clearly distinguished

## Example Output

```
   _____ _                 _        _____           _
  / ____| |               | |      / ____|         | |
 | |    | | __ _ _   _  __| | ___  | |     ___   __| | ___
 | |    | |/ _` | | | |/ _` |/ _ \ | |    / _ \ / _` |/ _ \
 | |____| | (_| | |_| | (_| |  __/ | |___| (_) | (_| |  __/
  \_____|_|\__,_|\__,_|\__,_|\___|  \_____\___/ \__,_|\___|

      Development Environment Tool Versions
      =====================================

=================== Python ===================
✅ python3: Python 3.11.4
✅ pip: pip 23.1.2 from /usr/local/lib/python3.11/site-packages/pip (python 3.11)
✅ poetry: Poetry (version 1.5.1)
✅ pytest: pytest 7.4.0
✅ black: black, 23.7.0 (compiled: yes)
❌ mypy: not found

=================== NodeJS ===================
✅ node: v20.5.0
✅ npm: 9.8.0
✅ yarn: 1.22.19
⚠️  pnpm: not found (optional)

=================== System Utilities ===================
✅ git: git version 2.41.0
✅ curl: curl 8.1.2
✅ jq: jq-1.6
✅ rg: ripgrep 13.0.0

✅ All required tool validations passed
```

## Getting Started

1. Copy `assets/check-tools.sh` as your starting point
2. Customize the tool list based on your project requirements
3. Add project-specific tools or remove unnecessary ones
4. Integrate into your CI/CD pipeline or onboarding documentation
5. Reference `references/tool-categories.md` for comprehensive tool lists

This skill enables rapid validation of development environments with clear, actionable feedback about tool availability and versions across all major programming ecosystems.
