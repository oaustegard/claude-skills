#!/bin/bash

# Tool verification script for claude_code_remote container
# Outputs formatted list of installed development tools and versions
# Exit with non-zero status if any required tools are missing

# Track validation failures
VALIDATION_FAILED=0

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
if command -v python3 &> /dev/null; then
    echo "✅ python3: $(python3 --version)"
else
    echo "❌ python3: not found"
    VALIDATION_FAILED=1
fi

if command -v python &> /dev/null; then
    echo "✅ python: $(python --version 2>&1)"
else
    echo "❌ python: not found"
    VALIDATION_FAILED=1
fi

if command -v pip &> /dev/null; then
    echo "✅ pip: $(pip --version)"
else
    echo "❌ pip: not found"
    VALIDATION_FAILED=1
fi

if command -v poetry &> /dev/null; then
    echo "✅ poetry: $(poetry --version)"
else
    echo "❌ poetry: not found"
    VALIDATION_FAILED=1
fi

if command -v uv &> /dev/null; then
    echo "✅ uv: $(uv --version)"
else
    echo "❌ uv: not found"
    VALIDATION_FAILED=1
fi

if command -v black &> /dev/null; then
    echo "✅ black: $(black --version 2>&1 | head -1)"
else
    echo "❌ black: not found"
    VALIDATION_FAILED=1
fi

if command -v mypy &> /dev/null; then
    echo "✅ mypy: $(mypy --version | head -1)"
else
    echo "❌ mypy: not found"
    VALIDATION_FAILED=1
fi

if command -v pytest &> /dev/null; then
    echo "✅ pytest: $(pytest --version 2>&1 | head -1)"
else
    echo "❌ pytest: not found"
    VALIDATION_FAILED=1
fi

if command -v ruff &> /dev/null; then
    echo "✅ ruff: $(ruff --version)"
else
    echo "❌ ruff: not found"
    VALIDATION_FAILED=1
fi

echo ""
echo "=================== NodeJS ==================="
if command -v node &> /dev/null; then
    echo "✅ node: $(node --version)"
    # List available Node versions if nvm is installed
    if [[ -s "/opt/nvm/nvm.sh" ]]; then
        # shellcheck source=/dev/null
        source "/opt/nvm/nvm.sh"
        nvm list 2>/dev/null | head -5 || true
    fi
else
    echo "❌ node: not found"
    VALIDATION_FAILED=1
fi

if [[ -s "/opt/nvm/nvm.sh" ]]; then
    echo "✅ nvm: available"
else
    echo "❌ nvm: not found"
fi

if command -v npm &> /dev/null; then
    echo "✅ npm: $(npm --version)"
else
    echo "❌ npm: not found"
    VALIDATION_FAILED=1
fi

if command -v yarn &> /dev/null; then
    echo "✅ yarn: $(yarn --version 2>/dev/null)"
else
    echo "❌ yarn: not found"
fi

if command -v pnpm &> /dev/null; then
    echo "✅ pnpm: $(pnpm --version)"
else
    echo "❌ pnpm: not found"
fi

if command -v eslint &> /dev/null; then
    echo "✅ eslint: v$(eslint --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
else
    echo "❌ eslint: not found"
fi

if command -v prettier &> /dev/null; then
    echo "✅ prettier: $(prettier --version)"
else
    echo "❌ prettier: not found"
fi

if command -v chromedriver &> /dev/null; then
    chromedriver --version 2>&1 | while IFS= read -r line; do
        echo "✅ chromedriver: $line"
    done
else
    echo "❌ chromedriver: not found"
fi

echo ""
echo "=================== Java ==================="
if command -v java &> /dev/null; then
    java -version 2>&1 | head -3 | while IFS= read -r line; do
        if [[ "$line" == *"openjdk"* ]] || [[ "$line" == *"java"* ]]; then
            echo "✅ java: $line"
        else
            echo "  $line"
        fi
    done
else
    echo "❌ java: not found"
    VALIDATION_FAILED=1
fi

if command -v mvn &> /dev/null; then
    echo "✅ maven: $(mvn --version 2>/dev/null | head -1)"
else
    echo "❌ maven: not found"
fi

if command -v gradle &> /dev/null; then
    echo "✅ gradle: $(gradle --version 2>/dev/null | grep -E '^Gradle' || echo 'Gradle installed')"
else
    echo "❌ gradle: not found"
fi

echo ""
echo "=================== Go ==================="
if command -v go &> /dev/null; then
    echo "✅ go: $(go version)"
else
    echo "❌ go: not found"
    VALIDATION_FAILED=1
fi

echo ""
echo "=================== Rust ==================="
# Source cargo environment if it exists
if [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck source=/dev/null
    source "$HOME/.cargo/env"
fi

if command -v rustc &> /dev/null; then
    echo "✅ rustc: $(rustc --version 2>/dev/null || echo 'installed')"
else
    echo "❌ rustc: not found"
    VALIDATION_FAILED=1
fi

if command -v cargo &> /dev/null; then
    echo "✅ cargo: $(cargo --version 2>/dev/null || echo 'installed')"
else
    echo "❌ cargo: not found"
    VALIDATION_FAILED=1
fi

echo ""
echo "=================== C/C++ Compilers ==================="
if command -v clang &> /dev/null; then
    echo "✅ clang: $(clang --version 2>&1 | head -1)"
else
    echo "❌ clang: not found"
fi

if command -v gcc &> /dev/null; then
    echo "✅ gcc: $(gcc --version | head -1)"
else
    echo "❌ gcc: not found"
    VALIDATION_FAILED=1
fi

if command -v cmake &> /dev/null; then
    echo "✅ cmake: $(cmake --version | head -1)"
else
    echo "❌ cmake: not found"
    VALIDATION_FAILED=1
fi

if command -v ninja &> /dev/null; then
    echo "✅ ninja: $(ninja --version)"
else
    echo "❌ ninja: not found"
fi

if command -v conan &> /dev/null; then
    echo "✅ conan: $(conan --version 2>/dev/null || echo 'Conan installed')"
else
    echo "❌ conan: not found"
fi

echo ""
echo "=================== Other Utilities ==================="
if command -v awk &> /dev/null; then
    echo "✅ awk: $(awk --version | head -1)"
else
    echo "❌ awk: not found"
fi

if command -v curl &> /dev/null; then
    echo "✅ curl: $(curl --version | head -1)"
else
    echo "❌ curl: not found"
fi

if command -v git &> /dev/null; then
    echo "✅ git: $(git --version)"
else
    echo "❌ git: not found"
    VALIDATION_FAILED=1
fi

if command -v grep &> /dev/null; then
    echo "✅ grep: $(grep --version | head -1)"
else
    echo "❌ grep: not found"
fi

if command -v gzip &> /dev/null; then
    echo "✅ gzip: $(gzip --version | head -1)"
else
    echo "❌ gzip: not found"
fi

if command -v jq &> /dev/null; then
    echo "✅ jq: $(jq --version)"
else
    echo "❌ jq: not found"
    VALIDATION_FAILED=1
fi

if command -v make &> /dev/null; then
    echo "✅ make: $(make --version | head -1)"
else
    echo "❌ make: not found"
fi

if command -v rg &> /dev/null; then
    echo "✅ rg: $(rg --version | head -1)"
else
    echo "❌ rg: not found"
    VALIDATION_FAILED=1
fi

if command -v sed &> /dev/null; then
    echo "✅ sed: $(sed --version | head -1)"
else
    echo "❌ sed: not found"
fi

if command -v tar &> /dev/null; then
    echo "✅ tar: $(tar --version | head -1)"
else
    echo "❌ tar: not found"
fi

if command -v tmux &> /dev/null; then
    echo "✅ tmux: $(tmux -V)"
else
    echo "❌ tmux: not found"
    VALIDATION_FAILED=1
fi

if command -v yq &> /dev/null; then
    echo "✅ yq: $(yq --version 2>/dev/null || echo 'yq installed')"
else
    echo "❌ yq: not found"
fi

if command -v vim &> /dev/null; then
    echo "✅ vim: $(vim --version | head -1)"
else
    echo "❌ vim: not found"
fi

if command -v nano &> /dev/null; then
    echo "✅ nano: $(nano --version | head -1)"
else
    echo "❌ nano: not found"
fi

echo ""

# Exit with failure status if any tools failed validation
if [[ $VALIDATION_FAILED -eq 1 ]]; then
    echo "❌ Tool validation failed: One or more required tools are missing"
    exit 1
fi

echo "✅ All tool validations passed"
exit 0
