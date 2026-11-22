#!/usr/bin/env bash
# Setup shell configuration for DevContainer
# This script is idempotent and can be run multiple times safely.

set -e

echo "Setting up shell configuration..."

# Function to add custom config to shell rc file
add_custom_config() {
    local rc_file=$1
    local custom_file=$2
    local marker="# DevContainer custom configuration"

    if [ ! -f "$rc_file" ]; then
        echo "⚠ $rc_file not found, skipping"
        return
    fi

    if [ ! -f "$custom_file" ]; then
        echo "⚠ $custom_file not found, skipping"
        return
    fi

    # Refresh managed custom section if already present.
    if grep -q "$marker" "$rc_file" 2>/dev/null; then
        local tmp_file
        tmp_file=$(mktemp)
        awk -v marker="$marker" '
            index($0, marker) {exit}
            {print}
        ' "$rc_file" >"$tmp_file"
        mv "$tmp_file" "$rc_file"
        echo "✓ Refreshed custom configuration in $rc_file"
    fi

    # Add custom configuration
    {
        echo ""
        echo "$marker"
        echo "# Added by setup-shell.sh"
        cat "$custom_file"
    } >>"$rc_file"
    echo "✓ Added custom configuration to $rc_file"
}

# Setup zsh
if [ -f ".devcontainer/.zshrc" ]; then
    add_custom_config "$HOME/.zshrc" ".devcontainer/.zshrc"
fi

# Setup bash
if [ -f ".devcontainer/.bashrc" ]; then
    add_custom_config "$HOME/.bashrc" ".devcontainer/.bashrc"
fi

echo "✓ Shell configuration complete"

_hook_dir="$(cd "$(dirname "$0")" && pwd)/hooks"
if [[ -f "$_hook_dir/setup-shell.post.sh" ]]; then
    echo "ℹ Running hook: .devcontainer/hooks/setup-shell.post.sh"
    # shellcheck source=/dev/null
    source "$_hook_dir/setup-shell.post.sh"
fi
unset _hook_dir
