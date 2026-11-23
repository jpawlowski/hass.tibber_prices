#!/usr/bin/env bash
#
# .devcontainer/update-content.sh - DevContainer Update-Content Hook
#
# Runs when container content is updated — primarily relevant for Codespaces
# pre-builds: fires after onCreateCommand on the initial build, and again
# whenever the pre-built image is refreshed (e.g. on new commits to the branch).
# In regular DevContainers it behaves identically to onCreateCommand.
#
# Use this for actions that should re-run when the codebase content changes
# but the container itself is not fully rebuilt (e.g. refreshing dependencies
# in a Codespaces pre-build pipeline).
#
# Execution order: onCreateCommand → updateContentCommand → postCreateCommand
#
# Customization:
#   Create .devcontainer/hooks/update-content.pre.sh  — runs at start of this script
#   Create .devcontainer/hooks/update-content.post.sh — runs at end of this script
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
_hook_file="$(cd "$(dirname "$0")" && pwd)/hooks/update-content.pre.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/update-content.pre.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file

# Re-install all Python dependencies whenever content changes.
# This ensures Codespaces pre-builds have up-to-date packages after
# requirements files or hacs.json changes are committed.
script/setup/bootstrap

# Run post-hook if present
_hook_file="$(cd "$(dirname "$0")" && pwd)/hooks/update-content.post.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/update-content.post.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file
