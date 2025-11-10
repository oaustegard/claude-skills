#!/bin/bash

# Unified Environment Diagnostic Tool
# Combines development tool validation with comprehensive system diagnostics
# Exit with non-zero status if any required tools are missing

# Configuration
MODE="${1:-full}"  # Options: tools, system, full
OUTPUT_FILE="${2:-}"
VALIDATION_FAILED=0

# Helper function to check required tools (fail validation if missing)
check_required_tool() {
    local tool=$1
    if command -v "$tool" &> /dev/null; then
        echo "✅ $tool: $($tool --version 2>&1 | head -1)"
        return 0
    else
        echo "❌ $tool: not found (REQUIRED)"
        VALIDATION_FAILED=1
        return 1
    fi
}

# Helper function to check optional tools (warn only if missing)
check_optional_tool() {
    local tool=$1
    if command -v "$tool" &> /dev/null; then
        echo "✅ $tool: $($tool --version 2>&1 | head -1)"
        return 0
    else
        echo "⚠️  $tool: not found (optional)"
        return 1
    fi
}

# Output function (supports both stdout and file)
output() {
    echo "$@"
    if [[ -n "$OUTPUT_FILE" ]]; then
        echo "$@" >> "$OUTPUT_FILE"
    fi
}

# Initialize output file
if [[ -n "$OUTPUT_FILE" ]]; then
    cat > "$OUTPUT_FILE" << 'HEADER'
=== ENVIRONMENT DIAGNOSTIC REPORT ===
HEADER
    echo "Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
fi

# ASCII Banner
cat << 'EOF'

   _____ _                 _        _____           _
  / ____| |               | |      / ____|         | |
 | |    | | __ _ _   _  __| | ___  | |     ___   __| | ___
 | |    | |/ _` | | | |/ _` |/ _ \ | |    / _ \ / _` |/ _ \
 | |____| | (_| | |_| | (_| |  __/ | |___| (_) | (_| |  __/
  \_____|_|\__,_|\__,_|\__,_|\___|  \_____\___/ \__,_|\___|

      Environment Diagnostic Report
      ==============================

EOF

# System Information Section
if [[ "$MODE" == "system" || "$MODE" == "full" ]]; then
    echo ""
    echo "=================== SYSTEM INFORMATION ==================="
    echo "Kernel: $(uname -a)"
    echo "Hostname: $(hostname)"
    echo ""

    if [[ -f /etc/os-release ]]; then
        echo "OS Release:"
        cat /etc/os-release | grep -E "^(NAME|VERSION|ID)=" | sed 's/^/  /'
        echo ""
    fi

    echo "=================== HARDWARE RESOURCES ==================="
    echo "CPU:"
    if command -v lscpu &> /dev/null; then
        lscpu | grep -E "^(Architecture|CPU\(s\)|Model name|Thread)" | sed 's/^/  /'
    else
        echo "  lscpu not available"
    fi
    echo ""

    echo "Memory:"
    if command -v free &> /dev/null; then
        free -h | sed 's/^/  /'
    else
        echo "  free command not available"
    fi
    echo ""

    echo "Disk Usage:"
    df -h | grep -E "^Filesystem|^/dev" | sed 's/^/  /'
    echo ""
fi

# Development Tools Section
if [[ "$MODE" == "tools" || "$MODE" == "full" ]]; then
    echo ""
    echo "=================== Python ==================="
    check_required_tool python3
    check_required_tool pip
    check_optional_tool python
    check_optional_tool uv
    check_optional_tool poetry
    check_optional_tool black
    check_optional_tool mypy
    check_optional_tool pytest
    check_optional_tool ruff

    # Show installed packages if requested
    if [[ "$MODE" == "full" ]] && command -v pip &> /dev/null; then
        echo ""
        echo "Installed Python packages (top 10):"
        pip list 2>/dev/null | head -12 | tail -10 | sed 's/^/  /'
    fi

    echo ""
    echo "=================== NodeJS ==================="
    check_required_tool node

    # Check for nvm in common locations
    if [[ -s "/opt/nvm/nvm.sh" ]]; then
        echo "✅ nvm: available at /opt/nvm/nvm.sh"
        source "/opt/nvm/nvm.sh"
        nvm list 2>/dev/null | head -5 || true
    elif [[ -s "$HOME/.nvm/nvm.sh" ]]; then
        echo "✅ nvm: available at $HOME/.nvm/nvm.sh"
    elif command -v nvm &> /dev/null; then
        echo "✅ nvm: $(nvm --version 2>/dev/null || echo 'available')"
    else
        echo "⚠️  nvm: not found (optional)"
    fi

    check_required_tool npm
    check_optional_tool yarn
    check_optional_tool pnpm
    check_optional_tool eslint
    check_optional_tool prettier
    check_optional_tool chromedriver

    # Show global packages if requested
    if [[ "$MODE" == "full" ]] && command -v npm &> /dev/null; then
        echo ""
        echo "Global npm packages (top 10):"
        npm list -g --depth=0 2>/dev/null | head -11 | tail -10 | sed 's/^/  /'
    fi

    echo ""
    echo "=================== Java ==================="
    check_required_tool java
    check_optional_tool mvn
    check_optional_tool gradle

    echo ""
    echo "=================== Go ==================="
    check_optional_tool go

    echo ""
    echo "=================== Rust ==================="
    # Source cargo environment if it exists
    if [[ -f "$HOME/.cargo/env" ]]; then
        source "$HOME/.cargo/env"
    fi

    check_optional_tool rustc
    check_optional_tool cargo

    echo ""
    echo "=================== C/C++ Compilers ==================="
    check_required_tool gcc
    check_optional_tool clang
    check_optional_tool "g++"
    check_optional_tool cmake
    check_optional_tool ninja
    check_optional_tool conan

    echo ""
    echo "=================== Other Language Runtimes ==================="
    check_optional_tool ruby
    check_optional_tool perl
    check_optional_tool php

    echo ""
    echo "=================== System Utilities ==================="
    check_required_tool git
    check_required_tool curl
    check_required_tool awk
    check_required_tool grep
    check_required_tool gzip
    check_required_tool tar
    check_required_tool make
    check_required_tool sed
    check_optional_tool wget
    check_optional_tool jq
    check_optional_tool rg
    check_optional_tool tmux
    check_optional_tool yq
    check_optional_tool vim
    check_optional_tool nano
    check_optional_tool zip
    check_optional_tool unzip
    check_optional_tool bzip2
fi

# Extended System Diagnostics
if [[ "$MODE" == "system" || "$MODE" == "full" ]]; then
    echo ""
    echo "=================== MOUNT POINTS ==================="
    mount | grep "^/dev\|^/mnt" | sed 's/^/  /'

    echo ""
    echo "=================== DIRECTORY STRUCTURE ==================="
    for dir in /home/claude /mnt /mnt/skills /mnt/user-data; do
        if [[ -d "$dir" ]]; then
            echo ""
            echo "$dir:"
            ls -lah "$dir" 2>/dev/null | head -10 | sed 's/^/  /'
        fi
    done

    if [[ -d /mnt/skills ]]; then
        echo ""
        echo "=================== AVAILABLE SKILLS ==================="
        find /mnt/skills -name "SKILL.md" -type f 2>/dev/null | sed 's|/mnt/skills/||' | sed 's|/SKILL.md||' | sed 's/^/  /' | head -20
    fi

    echo ""
    echo "=================== ENVIRONMENT VARIABLES (selected) ==================="
    env | grep -E "^(PATH|HOME|USER|SHELL|LANG|PWD|OLDPWD|TERM)" | sort | sed 's/^/  /'

    echo ""
    echo "=================== NETWORK CONFIGURATION ==================="
    if [[ -f /etc/resolv.conf ]]; then
        echo "DNS Configuration:"
        cat /etc/resolv.conf | grep -v "^#" | grep -v "^$" | sed 's/^/  /'
    fi

    echo ""
    echo "=================== RESOURCE LIMITS ==================="
    echo "ulimit -a:"
    ulimit -a | sed 's/^/  /'

    if [[ "$MODE" == "full" ]]; then
        echo ""
        echo "=================== RUNNING PROCESSES (top 10 by CPU) ==================="
        ps aux --sort=-%cpu | head -11 | sed 's/^/  /'
    fi
fi

# Summary
echo ""
echo "=================== Summary ==================="

# Exit with failure status if any REQUIRED tools failed validation
if [[ $VALIDATION_FAILED -eq 1 ]]; then
    echo "❌ Validation failed: One or more REQUIRED tools are missing"
    echo "   Install required tools or use lenient mode for development"
    exit 1
fi

echo "✅ All required tools present"
if [[ "$MODE" == "tools" || "$MODE" == "full" ]]; then
    echo "   (Optional tools marked with ⚠️ can be installed as needed)"
fi

if [[ -n "$OUTPUT_FILE" ]]; then
    echo ""
    echo "Full diagnostic report saved to: $OUTPUT_FILE"
fi

exit 0
