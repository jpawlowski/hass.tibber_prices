#!/bin/bash
# Setup Git configuration from host
# This script is idempotent and can be run multiple times safely.

# Exit on error
set -e

# Check if host gitconfig exists
if [ ! -f ~/.gitconfig.host ]; then
    echo "No host .gitconfig found, skipping Git setup"
    exit 0
fi

echo "Setting up Git configuration from host..."

# Extract and set user info
USER_NAME=$(grep -A 2 '^\[user\]' ~/.gitconfig.host | grep 'name' | sed 's/.*= //' | xargs)
USER_EMAIL=$(grep -A 2 '^\[user\]' ~/.gitconfig.host | grep 'email' | sed 's/.*= //' | xargs)

if [ -n "$USER_NAME" ]; then
    CURRENT_NAME=$(git config --global user.name 2>/dev/null || echo "")
    if [ "$CURRENT_NAME" != "$USER_NAME" ]; then
        git config --global user.name "$USER_NAME"
        echo "✓ Set user.name: $USER_NAME"
    else
        echo "  user.name already set: $USER_NAME"
    fi
fi

if [ -n "$USER_EMAIL" ]; then
    CURRENT_EMAIL=$(git config --global user.email 2>/dev/null || echo "")
    if [ "$CURRENT_EMAIL" != "$USER_EMAIL" ]; then
        git config --global user.email "$USER_EMAIL"
        echo "✓ Set user.email: $USER_EMAIL"
    else
        echo "  user.email already set: $USER_EMAIL"
    fi
fi

# Set safe defaults for container
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global merge.conflictStyle diff3
git config --global submodule.recurse true
git config --global color.ui true
echo "✓ Set Git defaults"

# Copy useful aliases (skip if they have macOS-specific paths)
if grep -q '^\[alias\]' ~/.gitconfig.host; then
    echo "✓ Syncing Git aliases..."

    # First, collect all aliases from host config
    TEMP_ALIASES=$(mktemp)
    sed -n '/^\[alias\]/,/^\[/p' ~/.gitconfig.host | \
        grep -v '^\[' | \
        grep -v '^$' | \
        while IFS= read -r line; do
            # Skip aliases with macOS-specific paths
            if echo "$line" | grep -q -E '/(Applications|usr/local)'; then
                continue
            fi
            echo "$line" >> "$TEMP_ALIASES"
        done

    # Apply each alias (git config --global overwrites existing values = idempotent)
    if [ -s "$TEMP_ALIASES" ]; then
        while IFS= read -r line; do
            ALIAS_NAME=$(echo "$line" | awk '{print $1}')
            ALIAS_VALUE=$(echo "$line" | sed "s/^$ALIAS_NAME = //")
            git config --global "alias.$ALIAS_NAME" "$ALIAS_VALUE" 2>/dev/null || true
        done < "$TEMP_ALIASES"
        echo "  Synced $(wc -l < "$TEMP_ALIASES") aliases"
    fi

    rm -f "$TEMP_ALIASES"
fi

# Disable GPG signing in container (1Password SSH signing doesn't work in DevContainers)
# SSH agent forwarding works for git push/pull, but SSH signing requires direct
# access to 1Password app which isn't available in the container.
#
# For signed commits: Make final commits on host macOS where 1Password is available.
# The container is for development/testing - pre-commit hooks will still run.
CURRENT_SIGNING=$(git config --global commit.gpgsign 2>/dev/null || echo "false")
if [ "$CURRENT_SIGNING" != "false" ]; then
    echo "ℹ Disabling commit signing in container (1Password not accessible)"
    echo "  → For signed commits, commit from macOS terminal outside container"
    git config --global commit.gpgsign false
else
    echo "  Commit signing already disabled"
fi

# Keep the signing key info for reference, but don't use it
SIGNING_KEY=$(grep 'signingkey' ~/.gitconfig.host 2>/dev/null | sed 's/.*= //' | xargs || echo "")
if [ -n "$SIGNING_KEY" ]; then
    echo "  → Your signing key: ${SIGNING_KEY:0:20}... (available on host)"
fi

echo "✓ Git configuration complete"
