#!/bin/bash
# Install GitHub CLI (gh) using official method
# https://github.com/cli/cli/blob/trunk/docs/install_linux.md

set -e

mkdir -p -m 755 /etc/apt/keyrings
out=$(mktemp)
wget -nv -O"$out" https://cli.github.com/packages/githubcli-archive-keyring.gpg
cat "$out" | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg

mkdir -p -m 755 /etc/apt/sources.list.d
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/github-cli.list > /dev/null

apt update -qq 2>/dev/null || true
apt install gh -y -qq

echo "gh $(gh --version | head -1 | awk '{print $3}') installed successfully"
