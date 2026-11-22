#!/usr/bin/env bash
#
# .devcontainer/post-create.sh - DevContainer Post-Create Hook
#
# Runs once after the container is created (after onCreateCommand and
# updateContentCommand). Sets up shell environment, Git configuration,
# and installs all project dependencies via script/setup/setup.
#
# Customization:
#   Create .devcontainer/hooks/post-create.pre.sh  — runs before setup
#   Create .devcontainer/hooks/post-create.post.sh — runs after setup
#

set -e

CYAN='\033[0;36m'
NC='\033[0m'

print_info() {
    echo -e "${CYAN}ℹ $1${NC}" >&2
}

# Load DevContainer environment overrides (.env → .env.local, later wins).
# Makes HA_VERSION and other vars available in this script and user hooks.
# shellcheck source=.devcontainer/_load_env.sh
source "$(cd "$(dirname "$0")" && pwd)/_load_env.sh"

# Run pre-hook if present
_hook_file="$(cd "$(dirname "$0")" && pwd)/hooks/post-create.pre.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/post-create.pre.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file

bash .devcontainer/setup-shell.sh
bash .devcontainer/setup-git.sh
script/setup/setup

# Run post-hook if present
_hook_file="$(cd "$(dirname "$0")" && pwd)/hooks/post-create.post.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/post-create.post.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file
