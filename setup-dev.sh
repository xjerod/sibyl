#!/usr/bin/env bash
# Sibyl Development Environment Setup
# Ensures all toolchain dependencies are installed and configured

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# SilkCircuit Neon Palette
# ═══════════════════════════════════════════════════════════════════════════════

ELECTRIC_PURPLE='\033[38;2;225;53;255m'
NEON_CYAN='\033[38;2;128;255;234m'
CORAL='\033[38;2;255;106;193m'
ELECTRIC_YELLOW='\033[38;2;241;250;140m'
SUCCESS_GREEN='\033[38;2;80;250;123m'
ERROR_RED='\033[38;2;255;99;99m'
DIM='\033[2m'
ITALIC='\033[3m'
BOLD='\033[1m'
RESET='\033[0m'

# Banner gradient (electric purple → neon cyan, sampled across the wordmark)
GRAD_1='\033[38;2;225;53;255m'
GRAD_2='\033[38;2;201;88;247m'
GRAD_3='\033[38;2;176;130;241m'
GRAD_4='\033[38;2;152;172;238m'
GRAD_5='\033[38;2;128;255;234m'

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

info() { echo -e "${NEON_CYAN}→${RESET} $1"; }
success() { echo -e "${SUCCESS_GREEN}✓${RESET} $1"; }
warn() { echo -e "${ELECTRIC_YELLOW}!${RESET} $1"; }
error() { echo -e "${ERROR_RED}✗${RESET} $1" >&2; }
header() { echo -e "\n${ELECTRIC_PURPLE}${BOLD}═══ $1 ═══${RESET}\n"; }

command_exists() { command -v "$1" &>/dev/null; }

check_os() {
    case "$(uname -s)" in
        Darwin) OS="macos" ;;
        Linux) OS="linux" ;;
        *) error "Unsupported OS: $(uname -s)"; exit 1 ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════════════════════

print_banner() {
    echo
    echo -e "         ${CORAL}✦${RESET}"
    echo -e "      ${GRAD_1}╔═╗${GRAD_2}╦${GRAD_3}╔╗ ${GRAD_4}╦ ╦${GRAD_5}╦${RESET}"
    echo -e "      ${GRAD_1}╚═╗${GRAD_2}║${GRAD_3}╠╩╗${GRAD_4}╚╦╝${GRAD_5}║${RESET}"
    echo -e "      ${GRAD_1}╚═╝${GRAD_2}╩${GRAD_3}╚═╝ ${GRAD_4}╩ ${GRAD_5}╩═╝${RESET}"
    echo -e "      ${DIM}${ELECTRIC_PURPLE}─────────────────${RESET}"
    echo -e "      ${DIM}${ITALIC}${NEON_CYAN}collective intelligence runtime${RESET}"
    echo
}

# ═══════════════════════════════════════════════════════════════════════════════
# Proto Installation
# ═══════════════════════════════════════════════════════════════════════════════

install_proto() {
    if command_exists proto; then
        local version
        version=$(proto --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        success "proto ${CORAL}v${version}${RESET} already installed"
        return 0
    fi

    info "Installing proto (toolchain version manager)..."
    curl -fsSL https://moonrepo.dev/install/proto.sh | bash -s -- --yes

    # Source proto into current shell
    export PROTO_HOME="${PROTO_HOME:-$HOME/.proto}"
    export PATH="$PROTO_HOME/bin:$PATH"

    if command_exists proto; then
        success "proto installed successfully"
    else
        error "proto installation failed"
        echo -e "${DIM}Try manually: curl -fsSL https://moonrepo.dev/install/proto.sh | bash${RESET}"
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Moon Installation
# ═══════════════════════════════════════════════════════════════════════════════

install_moon() {
    if command_exists moon; then
        local version
        version=$(moon --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        success "moon ${CORAL}v${version}${RESET} already installed"
        return 0
    fi

    info "Installing moon (monorepo orchestration)..."
    # Moon is built-in to proto v0.45+, no plugin needed
    proto install moon

    if command_exists moon; then
        success "moon installed successfully"
    else
        error "moon installation failed"
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Toolchain Installation (via proto)
# ═══════════════════════════════════════════════════════════════════════════════

install_toolchain() {
    header "Toolchain"

    if [[ ! -f .prototools ]]; then
        error ".prototools not found - are you in the sibyl directory?"
        exit 1
    fi

    # Make sure proto-managed shims are visible if proto was just installed
    export PROTO_HOME="${PROTO_HOME:-$HOME/.proto}"
    export PATH="$PROTO_HOME/shims:$PROTO_HOME/bin:$PATH"

    info "Resolving toolchain from ${CORAL}.prototools${RESET}..."

    # Install tools one at a time. `proto use --yes` runs installs in parallel
    # and deadlocks if any plugin stalls — pnpm waits on node forever when the
    # node WASM plugin trips on a flaky nodejs.org fetch, even when node is
    # already on disk. Sequential installs surface failures cleanly and let us
    # short-circuit on tools that are already present.
    local tools=("node" "pnpm" "python" "uv")
    for tool in "${tools[@]}"; do
        if command_exists "$tool"; then
            local version
            version=$("$tool" --version 2>/dev/null | head -1)
            success "${tool} ${CORAL}${version}${RESET}"
            continue
        fi

        info "Installing ${CORAL}${tool}${RESET}..."
        if ! timeout 180 proto install "$tool"; then
            error "${tool} install failed or timed out after 180s"
            echo -e "${DIM}  Retry: ${RESET}proto install ${tool}"
            echo -e "${DIM}  If the node plugin keeps failing, clear the cache:${RESET}"
            echo -e "${DIM}    rm -rf ~/.proto/plugins && proto install ${tool}${RESET}"
            exit 1
        fi

        if command_exists "$tool"; then
            local version
            version=$("$tool" --version 2>/dev/null | head -1)
            success "${tool} ${CORAL}${version}${RESET} installed"
        else
            error "${tool} not found on PATH after install"
            exit 1
        fi
    done
}

# ═══════════════════════════════════════════════════════════════════════════════
# Docker Check
# ═══════════════════════════════════════════════════════════════════════════════

check_docker() {
    header "Docker"

    if ! command_exists docker; then
        warn "Docker not installed"
        if [[ "$OS" == "macos" ]]; then
            echo -e "${DIM}Install Docker Desktop: https://docs.docker.com/desktop/install/mac-install/${RESET}"
        else
            echo -e "${DIM}Install Docker: https://docs.docker.com/engine/install/${RESET}"
        fi
        echo -e "${DIM}Docker is required for SurrealDB (and the legacy FalkorDB + PostgreSQL stack)${RESET}"
        return 1
    fi

    if ! docker info &>/dev/null; then
        warn "Docker daemon not running"
        echo -e "${DIM}Start Docker Desktop or run: sudo systemctl start docker${RESET}"
        return 1
    fi

    success "Docker is running"
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# Dependencies Installation
# ═══════════════════════════════════════════════════════════════════════════════

install_dependencies() {
    header "Dependencies"

    # Python dependencies (via uv)
    info "Installing Python dependencies..."
    uv sync --all-groups
    success "Python dependencies installed"

    # Node dependencies (via pnpm)
    info "Installing Node dependencies..."
    pnpm install
    success "Node dependencies installed"
}

# ═══════════════════════════════════════════════════════════════════════════════
# Pre-commit Hooks
# ═══════════════════════════════════════════════════════════════════════════════

setup_precommit() {
    header "Git Hooks"

    if [[ -f .pre-commit-config.yaml ]]; then
        info "Installing pre-commit hooks..."
        uv run pre-commit install
        success "Pre-commit hooks installed"
    else
        info "No pre-commit config found, skipping hooks"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# CLI Installation
# ═══════════════════════════════════════════════════════════════════════════════

verify_cli() {
    header "Sibyl CLI"

    # CLI tools are installed in .venv/bin/ - verify they exist
    if [[ -x ".venv/bin/sibyl" ]] && [[ -x ".venv/bin/sibyld" ]]; then
        success "CLI tools installed: ${NEON_CYAN}sibyl${RESET}, ${NEON_CYAN}sibyld${RESET}"
        echo -e "${DIM}Run via: uv run sibyl ... or uv run sibyld ...${RESET}"
    else
        warn "CLI tools not found in .venv/bin/"
        echo -e "${DIM}Try: uv sync --all-groups${RESET}"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════

print_summary() {
    header "Setup Complete"

    echo -e "${NEON_CYAN}Quick Start:${RESET}"
    echo -e "  ${DIM}Start infrastructure:${RESET}  moon run dev"
    echo -e "  ${DIM}Stop infrastructure:${RESET}   moon run stop"
    echo -e "  ${DIM}Run tests:${RESET}             moon run :test"
    echo -e "  ${DIM}Run linting:${RESET}           moon run :lint"
    echo ""
    echo -e "${NEON_CYAN}Ports:${RESET}"
    echo -e "  ${DIM}API + MCP:${RESET}    ${CORAL}3334${RESET}"
    echo -e "  ${DIM}Frontend:${RESET}     ${CORAL}3337${RESET}"
    echo -e "  ${DIM}SurrealDB:${RESET}    ${CORAL}8000${RESET}    ${DIM}(default)${RESET}"
    echo -e "  ${DIM}FalkorDB:${RESET}     ${CORAL}6380${RESET}    ${DIM}(legacy)${RESET}"
    echo -e "  ${DIM}Postgres:${RESET}     ${CORAL}5433${RESET}    ${DIM}(legacy)${RESET}"
    echo ""

    if ! check_docker 2>/dev/null; then
        echo -e "${ELECTRIC_YELLOW}Note:${RESET} Docker required for databases. Install and start it."
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    print_banner
    check_os

    # Change to script directory
    cd "$(dirname "$0")"

    header "Environment: ${OS}"

    install_proto
    install_moon
    install_toolchain
    check_docker || true  # Don't fail if Docker missing
    install_dependencies
    setup_precommit
    verify_cli

    print_summary
}

main "$@"
