#!/bin/bash
# Spotify MCP Server Installation Script
#
# This script installs the Spotify MCP Server in ephemeral compute environments.
# It clones the modified repository, installs dependencies, and builds the server.
#
# Usage:
#   bash install-mcp-server.sh [install_dir]
#
# Arguments:
#   install_dir: Directory to install server (default: /home/claude/spotify-mcp-server)

set -e  # Exit on error

# Configuration
INSTALL_DIR="${1:-/home/claude/spotify-mcp-server}"
REPO_URL="https://github.com/YOUR-FORK/spotify-mcp-server.git"  # TODO: Update with actual fork URL
NODE_VERSION="18"  # Minimum Node.js version required

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

            # Verify it's built
            if [ -f "$INSTALL_DIR/build/index.js" ]; then
                log_info "MCP server already installed and built ✓"
                echo
                echo "Installation directory: $INSTALL_DIR"
                echo "Server executable: $INSTALL_DIR/build/index.js"
                echo
                log_info "You can now configure your MCP client to use this server."
                exit 0
            else
                log_warn "Existing installation appears incomplete. Continuing with build..."
            fi
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

    # Install dependencies
    log_info "Installing dependencies (this may take a minute)..."
    npm install --production

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

    # Test the server (quick validation)
    log_info "Validating server installation..."
    if node build/index.js --help &>/dev/null; then
        log_info "Server validation passed ✓"
    else
        log_warn "Server validation inconclusive (this may be normal)"
    fi

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
    echo "1. Ensure you have your Spotify credentials:"
    echo "   - SPOTIFY_CLIENT_ID"
    echo "   - SPOTIFY_CLIENT_SECRET"
    echo "   - SPOTIFY_REFRESH_TOKEN"
    echo
    echo "2. Configure your MCP client with:"
    echo "   {\"
    echo "     \"command\": \"node\","
    echo "     \"args\": [\"$INSTALL_DIR/build/index.js\"],"
    echo "     \"env\": {"
    echo "       \"SPOTIFY_CLIENT_ID\": \"your_client_id\","
    echo "       \"SPOTIFY_CLIENT_SECRET\": \"your_client_secret\","
    echo "       \"SPOTIFY_REFRESH_TOKEN\": \"your_refresh_token\""
    echo "     }"
    echo "   }"
    echo
    log_info "Installation successful!"
}

# Run main function
main "$@"
