#!/usr/bin/env bash
# Sibyl Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/hyperb1iss/sibyl/main/install.sh | sh
#
# This script:
#   1. Installs uv (if not present)
#   2. Installs the Sibyl CLI via uv
#   3. Prints explicit local, remote, and Docker next steps

set -eu

# ============================================================================
# Colors (SilkCircuit palette)
# ============================================================================
PURPLE=$(printf '\033[38;2;225;53;255m')
CYAN=$(printf '\033[38;2;128;255;234m')
GREEN=$(printf '\033[38;2;80;250;123m')
YELLOW=$(printf '\033[38;2;241;250;140m')
RED=$(printf '\033[38;2;255;99;99m')
DIM=$(printf '\033[2m')
BOLD=$(printf '\033[1m')
RESET=$(printf '\033[0m')

# ============================================================================
# Helpers
# ============================================================================
info() { printf '%s\n' "${CYAN}▸${RESET} $1"; }
success() { printf '%s\n' "${GREEN}✓${RESET} $1"; }
warn() { printf '%s\n' "${YELLOW}!${RESET} $1"; }
error() { printf '%s\n' "${RED}✗${RESET} $1"; exit 1; }

banner() {
    printf '%s' "${PURPLE}${BOLD}"
    cat << 'EOF'
   _____ _ __          __
  / ___/(_) /_  __  __/ /
  \__ \/ / __ \/ / / / /
 ___/ / / /_/ / /_/ / /
/____/_/_.___/\__, /_/
             /____/
EOF
    printf '%s\n' "${RESET}"
    printf '%s\n' "${DIM}Collective Intelligence Runtime${RESET}"
    echo
}

# ============================================================================
# Checks
# ============================================================================
check_os() {
    case "$(uname -s)" in
        Linux*)  OS=linux ;;
        Darwin*) OS=macos ;;
        *)       error "Unsupported OS: $(uname -s). Use Linux or macOS." ;;
    esac
}

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        error "Docker is required but not installed.\n\n  Install from: https://docs.docker.com/get-docker/"
    fi

    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running.\n\n  Start Docker and try again."
    fi

    success "Docker is available"
}

# ============================================================================
# Installation
# ============================================================================
install_uv() {
    if command -v uv >/dev/null 2>&1; then
        success "uv is already installed ($(uv --version))"
        return
    fi

    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv >/dev/null 2>&1; then
        success "uv installed successfully"
    else
        error "Failed to install uv"
    fi
}

install_sibyl() {
    info "Installing sibyl-dev..."

    if uv tool list 2>/dev/null | grep -q "sibyl-dev"; then
        warn "sibyl-dev is already installed, upgrading..."
        uv tool upgrade sibyl-dev
    else
        uv tool install sibyl-dev
    fi

    # Ensure tool bin is in PATH
    export PATH="$HOME/.local/bin:$PATH"

    if command -v sibyl >/dev/null 2>&1; then
        success "sibyl-dev installed successfully"
    else
        error "Failed to install sibyl-dev"
    fi
}

install_sibyld() {
    info "Installing sibyld..."

    if uv tool list 2>/dev/null | grep -q "sibyld"; then
        warn "sibyld is already installed, upgrading..."
        uv tool upgrade sibyld
    else
        uv tool install sibyld
    fi

    export PATH="$HOME/.local/bin:$PATH"

    if command -v sibyld >/dev/null 2>&1; then
        success "sibyld installed successfully"
    else
        error "Failed to install sibyld"
    fi
}

# ============================================================================
# Main
# ============================================================================
setup_agent_integration() {
    info "Setting up agent integration (skills + hooks)..."
    if sibyl local setup >/dev/null 2>&1; then
        success "Agent integration configured"
    else
        warn "Agent integration setup skipped (run 'sibyl local setup' later)"
    fi
}

print_next_steps() {
    echo
    printf '%s\n' "${GREEN}${BOLD}Installation complete!${RESET}"
    echo
    printf '%s\n' "${BOLD}Local embedded daemon:${RESET}"
    printf '%s\n' "  sibyl init --local"
    printf '%s\n' "  sibyl serve"
    echo
    printf '%s\n' "${BOLD}Remote server:${RESET}"
    printf '%s\n' "  sibyl init --remote https://sibyl.example.com"
    printf '%s\n' "  sibyl auth login"
    echo
    printf '%s\n' "${BOLD}Docker self-host:${RESET}"
    printf '%s\n' "  sibyl docker init"
    printf '%s\n' "  sibyl docker up"
}

main() {
    banner
    MODE="${SIBYL_INSTALL_MODE:-${1:-cli}}"

    check_os

    echo
    install_uv
    install_sibyl

    case "$MODE" in
        cli|remote)
            ;;
        local)
            install_sibyld
            ;;
        docker)
            check_docker
            ;;
        *)
            error "Unknown install mode: $MODE (use cli, remote, local, or docker)"
            ;;
    esac

    echo
    setup_agent_integration
    print_next_steps
}

main "$@"
