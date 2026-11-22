#!/usr/bin/env bash
#
# .devcontainer/on-create.sh - DevContainer On-Create Hook
#
# Runs once when the container is first created, before postCreateCommand.
# Fixes ownership of named Docker volume mount points that Docker initializes
# as root:root so that subsequent scripts (pipx, uv, bootstrap) can write to
# ~/.local and ~/.cache without permission errors.
#
# Customization:
#   Create .devcontainer/hooks/on-create.pre.sh  — runs before ownership fix
#   Create .devcontainer/hooks/on-create.post.sh — runs after ownership fix
#

set -e

CYAN='\033[0;36m'
NC='\033[0m'

print_info() {
    echo -e "${CYAN}ℹ $1${NC}" >&2
}

_devcontainer_dir="$(cd "$(dirname "$0")" && pwd)"

install_agent_config() {
    local label=$1 relative_source=$2 destination=$3
    if [[ -f "$_devcontainer_dir/$relative_source" ]]; then
        print_info "Installing ${label} from .devcontainer/${relative_source}..."
        sudo mkdir -p "$(dirname "$destination")"
        sudo install -m 0644 "$_devcontainer_dir/$relative_source" "$destination"
    else
        print_info "No .devcontainer/${relative_source} found; skipping ${label} install."
    fi
}

link_into_volume() {
    local target=$1 link=$2
    mkdir -p "$target"
    if [[ -e "$link" || -L "$link" ]]; then
        print_info "${link} already exists; leaving it untouched."
    else
        mkdir -p "$(dirname "$link")"
        ln -s "$target" "$link"
    fi
}

# Load DevContainer environment overrides (.env → .env.local, later wins).
# Makes HA_VERSION and other vars available in this script and user hooks.
# shellcheck source=.devcontainer/_load_env.sh
source "$_devcontainer_dir/_load_env.sh"

# Run pre-hook if present
_hook_file="$_devcontainer_dir/hooks/on-create.pre.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/on-create.pre.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file

# Docker creates each volume mount point as root:root. Volumes sit directly under $HOME so that Docker never
# creates ~/.config, ~/.local or ~/.cache as root, which VS Code server writes to before this script runs.
print_info "Fixing ownership of Docker volume mount points..."
for _volume_mount in \
    /home/vscode/ha-venv \
    /home/vscode/mise-data \
    /home/vscode/.claude \
    /home/vscode/.codex \
    /home/vscode/.opencode \
    /home/vscode/.cache; do
    if [[ -e "$_volume_mount" ]]; then
        sudo find "$_volume_mount" \( ! -user vscode -o ! -group vscode \) -exec chown -h vscode:vscode {} +
    fi
done
unset _volume_mount

# Install agent defaults from the repository. Keeping them versioned here allows project-level customization
# without modifying this script.
install_agent_config "Claude Code managed settings" claude-code/managed-settings.json \
    /etc/claude-code/managed-settings.json
install_agent_config "Codex system defaults" codex/config.toml /etc/codex/config.toml
install_agent_config "OpenCode managed settings" opencode/opencode.json /etc/opencode/opencode.json

# OpenCode reads ~/.config/opencode and ~/.local/share/opencode, so its volume is linked there.
print_info "Setting up symlinks for OpenCode config and data..."
link_into_volume /home/vscode/.opencode/config /home/vscode/.config/opencode
link_into_volume /home/vscode/.opencode/data /home/vscode/.local/share/opencode

# Bootstrap Copilot CLI wrapper/defaults from the repository when present.
# GitHub CLI (and its Copilot CLI command) is provided by devcontainer features;
# this block does NOT install gh or Copilot binaries.
# It only installs project-managed files under ~/.copilot and ~/.local/bin.
# Optional env overrides (from .devcontainer/.env and .env.local):
#   COPILOT_CLI_INSTALL=0                                    -> disable Copilot wrapper/defaults bootstrap block
#   COPILOT_CLI_DEFAULT_FLAGS_SOURCE=/absolute/or/relative   -> custom flags source file
#   COPILOT_CLI_WRAPPER_SOURCE=/absolute/or/relative         -> custom wrapper source file
_copilot_cli_install="${COPILOT_CLI_INSTALL:-1}"

if [[ "$_copilot_cli_install" == "0" ]]; then
    print_info "COPILOT_CLI_INSTALL=0; skipping Copilot CLI defaults and wrapper install."
else
    _copilot_default_flags_rel=".devcontainer/copilot/default-flags.txt"
    _copilot_wrapper_rel=".devcontainer/copilot/copilot-safe"

    _copilot_flags_source="${COPILOT_CLI_DEFAULT_FLAGS_SOURCE:-$_copilot_default_flags_rel}"
    if [[ "$_copilot_flags_source" != /* ]]; then
        _copilot_flags_source="$(pwd)/$_copilot_flags_source"
    fi

    if [[ -f "$_copilot_flags_source" ]]; then
        print_info "Installing Copilot CLI default flags from ${_copilot_flags_source}..."
        mkdir -p /home/vscode/.copilot
        install -m 0644 "$_copilot_flags_source" /home/vscode/.copilot/default-flags.txt
    else
        print_info "No Copilot CLI flags file found at ${_copilot_flags_source}; skipping default flags install."
    fi

    _copilot_wrapper_source="${COPILOT_CLI_WRAPPER_SOURCE:-$_copilot_wrapper_rel}"
    if [[ "$_copilot_wrapper_source" != /* ]]; then
        _copilot_wrapper_source="$(pwd)/$_copilot_wrapper_source"
    fi

    if [[ -f "$_copilot_wrapper_source" ]]; then
        print_info "Installing Copilot CLI wrapper from ${_copilot_wrapper_source}..."
        mkdir -p /home/vscode/.local/bin
        install -m 0755 "$_copilot_wrapper_source" /home/vscode/.local/bin/copilot-safe
    else
        print_info "No Copilot CLI wrapper found at ${_copilot_wrapper_source}; skipping wrapper install."
    fi

    unset _copilot_default_flags_rel
    unset _copilot_wrapper_rel
fi
unset _copilot_flags_source
unset _copilot_wrapper_source
unset _copilot_cli_install

# Run post-hook if present
_hook_file="$_devcontainer_dir/hooks/on-create.post.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/on-create.post.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file
