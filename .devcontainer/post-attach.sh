#!/usr/bin/env bash
#
# .devcontainer/post-attach.sh - DevContainer Post-Attach Hook
#
# Runs automatically when attaching to an existing DevContainer.
# Detects fresh blueprint copies and triggers automatic initialization.
#

set -e

# Color codes for output (matching initialize.sh)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_color() {
    local color=$1
    shift
    echo -e "${color}$*${NC}" >&2
}

print_header() {
    local text="$1"
    # Center text by calculating padding
    local text_length=${#text}
    local total_width=78
    local padding=$(((total_width - text_length) / 2))
    local left_pad
    left_pad=$(printf "%${padding}s" "")

    echo ""
    print_color "$BLUE" "┬──────────────────────────────────────────────────────────────────────────────┬"
    print_color "$BLUE" "${left_pad}${text}"
    print_color "$BLUE" "┴──────────────────────────────────────────────────────────────────────────────┴"
}

print_welcome_header() {
    local text="$1"
    # Character count for centering (not display width, simple approach)
    local text_length=${#text}
    local padding_left=$(((78 - text_length) / 2))
    local padding_right=$((78 - text_length - padding_left))
    local left_spaces right_spaces
    left_spaces=$(printf "%${padding_left}s" "")
    right_spaces=$(printf "%${padding_right}s" "")

    echo ""
    print_color "$BLUE" "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓"
    print_color "$BLUE" "┃                                                                              ┃"
    print_color "$BLUE" "┃${left_spaces}${text}${right_spaces}┃"
    print_color "$BLUE" "┃                                                                              ┃"
    print_color "$BLUE" "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
    echo ""
}

print_info() {
    print_color "$CYAN" "ℹ $1"
}

print_success() {
    print_color "$GREEN" "✓ $1"
}

print_error() {
    print_color "$RED" "✗ $1"
}

print_warning() {
    print_color "$YELLOW" "⚠ $1"
}

# Check if this is the original blueprint repository (jpawlowski's)
check_if_original_blueprint_repo() {
    if git rev-parse --git-dir >/dev/null 2>&1; then
        local remote_url
        remote_url=$(git remote get-url origin 2>/dev/null || echo "")
        if [[ "$remote_url" =~ jpawlowski.*(hacs\.)?integration[_.-]?blueprint ]]; then
            return 0 # This IS the original blueprint repo
        fi
    fi
    return 1 # Not the original blueprint repo
}

# Check if this is still a blueprint (not yet initialized)
check_if_needs_initialization() {
    # Check 1: initialize.sh must exist
    if [[ ! -f "initialize.sh" ]]; then
        return 1 # Already initialized (script removed)
    fi

    # Check 2: Template domain must still exist
    if ! grep -q "ha_integration_domain" custom_components/*/manifest.json 2>/dev/null; then
        return 1 # Already initialized (domain renamed)
    fi

    # Check 3: Not the original blueprint repo
    if check_if_original_blueprint_repo; then
        return 1 # Original repo, skip initialization
    fi

    return 0 # Needs initialization
}

# Load DevContainer environment overrides (.env → .env.local, later wins).
# Makes HA_VERSION and other vars available in this script and user hooks.
# shellcheck source=.devcontainer/_load_env.sh
source "$(cd "$(dirname "$0")" && pwd)/_load_env.sh"

# Run pre-hook if present
_hook_file="$(cd "$(dirname "$0")" && pwd)/hooks/post-attach.pre.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/post-attach.pre.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file

# Hide the default Codespaces first-run notice so project MOTD stays primary.
mkdir -p "$HOME/.config/vscode-dev-containers"
touch "$HOME/.config/vscode-dev-containers/first-run-notice-already-displayed"

# Main logic
if check_if_needs_initialization; then
    print_welcome_header "🚀 Welcome to your new Home Assistant Integration!"

    print_info "This appears to be a fresh copy of the blueprint template."
    print_info "Starting automatic initialization process..."
    echo ""

    # Run initialization script
    ./initialize.sh
elif check_if_original_blueprint_repo; then
    # Silent for maintainer - original repo doesn't need initialization
    :
elif [[ ! -f "initialize.sh" ]]; then
    # Already initialized, silent success
    :
fi

# Ensure node_modules is populated — the named Docker volume may have been pruned
# while the container was stopped. postCreateCommand only runs on container creation,
# so we must check here (on every attach) and reinstall if the volume is empty.
if command -v npm >/dev/null 2>&1 && [[ -f package.json ]] && [[ -z "$(ls -A node_modules 2>/dev/null)" ]]; then
    print_color "$YELLOW" "⚠ node_modules is empty — running npm ci to restore packages..."
    npm ci --silent
fi

# Run user post-attach hook if present (lives in .devcontainer/hooks/post-attach.post.sh)
_hook_file="$(cd "$(dirname "$0")" && pwd)/hooks/post-attach.post.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/post-attach.post.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file
