#!/bin/bash

# Tool verification script for claude_code_remote container
# Outputs formatted list of installed development tools and versions
# Exit with non-zero status if any required tools are missing

# Track validation failures
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
check_optional_tool cmake
check_optional_tool ninja
check_optional_tool conan

echo ""
echo "=================== Other Utilities ==================="
check_required_tool git
check_required_tool curl
check_required_tool awk
check_required_tool grep
check_required_tool gzip
check_required_tool tar
check_required_tool make
check_required_tool sed
check_optional_tool jq
check_optional_tool rg
check_optional_tool tmux
check_optional_tool yq
check_optional_tool vim
check_optional_tool nano

echo ""
echo "=================== Summary ==================="

# Exit with failure status if any REQUIRED tools failed validation
if [[ $VALIDATION_FAILED -eq 1 ]]; then
    echo "❌ Validation failed: One or more REQUIRED tools are missing"
    echo "   Install required tools or use lenient mode for development"
    exit 1
fi

echo "✅ All required tools present"
echo "   (Optional tools marked with ⚠️ can be installed as needed)"
exit 0
