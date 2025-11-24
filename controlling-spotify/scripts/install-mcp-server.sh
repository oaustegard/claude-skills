#!/bin/bash
# Spotify MCP Server Installation Script
#
# This script installs the Spotify MCP Server in ephemeral compute environments.
# It clones the repository, patches it for environment variable support, and builds it.
#
# Usage:
#   bash install-mcp-server.sh [install_dir]
#
# Arguments:
#   install_dir: Directory to install server (default: /home/claude/spotify-mcp-server)

set -e  # Exit on error

# Configuration
INSTALL_DIR="${1:-/home/claude/spotify-mcp-server}"
REPO_URL="https://github.com/marcelmarais/spotify-mcp-server.git"
NODE_VERSION="18"  # Minimum Node.js version required

# Script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PATCH_SCRIPT="$SCRIPT_DIR/apply-patch.js"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed"
        return 1
    fi
    return 0
}

# Main installation function
main() {
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║        Spotify MCP Server Installation                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo

    # Check prerequisites
    log_info "Checking prerequisites..."

    if ! check_command node; then
        log_error "Node.js is not installed. Please install Node.js ${NODE_VERSION}+ first."
        exit 1
    fi

    if ! check_command npm; then
        log_error "npm is not installed. Please install npm first."
        exit 1
    fi

    if ! check_command git; then
        log_error "git is not installed. Please install git first."
        exit 1
    fi

    # Check Node.js version
    NODE_CURRENT=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_CURRENT" -lt "$NODE_VERSION" ]; then
        log_error "Node.js version $NODE_CURRENT found, but version $NODE_VERSION or higher is required."
        exit 1
    fi
    log_info "Node.js version: $(node -v) ✓"
    log_info "npm version: $(npm -v) ✓"

    # Check patch script
    if [ ! -f "$PATCH_SCRIPT" ]; then
        log_error "Patch script not found at $PATCH_SCRIPT"
        exit 1
    fi

    # Check if installation directory already exists
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Installation directory already exists: $INSTALL_DIR"
        read -p "Do you want to remove and reinstall? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing existing installation..."
            rm -rf "$INSTALL_DIR"
        else
            log_info "Using existing installation at $INSTALL_DIR"
            exit 0
        fi
    fi

    # Clone repository
    log_info "Cloning Spotify MCP Server repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"

    if [ ! -d "$INSTALL_DIR" ]; then
        log_error "Failed to clone repository"
        exit 1
    fi
    log_info "Repository cloned successfully ✓"

    # Navigate to directory
    cd "$INSTALL_DIR"

    # Patch the server
    log_info "Patching server for environment variable support..."
    if node "$PATCH_SCRIPT"; then
        log_info "Patch applied successfully ✓"
    else
        log_error "Failed to patch server"
        exit 1
    fi

    # Install dependencies
    # We use 'npm install' instead of 'npm install --production' to ensure build tools (devDependencies) are available
    log_info "Installing dependencies..."
    npm install

    if [ $? -ne 0 ]; then
        log_error "Failed to install dependencies"
        exit 1
    fi
    log_info "Dependencies installed successfully ✓"

    # Build the server
    log_info "Building MCP server..."
    npm run build

    if [ $? -ne 0 ]; then
        log_error "Failed to build MCP server"
        exit 1
    fi

    # Verify build output
    if [ ! -f "build/index.js" ]; then
        log_error "Build completed but index.js not found"
        exit 1
    fi
    log_info "MCP server built successfully ✓"

    # Make executable
    chmod +x build/index.js
    log_info "Made server executable ✓"

    # Installation complete
    echo
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║        Installation Complete!                                ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    echo "Installation directory: $INSTALL_DIR"
    echo "Server executable: $INSTALL_DIR/build/index.js"
    echo
    echo "Next steps:"
    echo "1. Run the token helper script if you haven't yet:"
    echo "   node $SCRIPT_DIR/get-refresh-token.js <CLIENT_ID> <CLIENT_SECRET>"
    echo
    echo "2. Configure your MCP client with the credentials."
    echo
    log_info "Installation successful!"
}

# Run main function
main "$@"
