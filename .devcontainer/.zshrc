# shellcheck shell=bash disable=SC2139
# Show MOTD once per container lifecycle (new container or rebuild).
WORKSPACE_DIR=""
if [[ -n "${VSCODE_GIT_IPC_HANDLE:-}" || -n "${CODESPACES:-}" ]]; then
    for dir in /workspaces/* /workspace; do
        if [[ -d "$dir" ]]; then
            WORKSPACE_DIR="$dir"
            break
        fi
    done
fi

if [[ -n "$WORKSPACE_DIR" && -f "$WORKSPACE_DIR/.devcontainer/motd" ]]; then
    HOST_TOKEN="${HOSTNAME:-unknown}"
    MOTD_MARKER_DIR="$HOME/.config/ha-devcontainer"
    MOTD_MARKER_FILE="$MOTD_MARKER_DIR/motd-shown-${HOST_TOKEN}"
    if [[ ! -f "$MOTD_MARKER_FILE" ]]; then
        mkdir -p "$MOTD_MARKER_DIR"
        "$WORKSPACE_DIR/.devcontainer/motd" 2>/dev/null || true
        touch "$MOTD_MARKER_FILE"
    fi
fi

# Find workspace directory for aliases
WORKSPACE_ROOT=""
for dir in /workspaces/* /workspace; do
    if [ -d "$dir" ]; then
        WORKSPACE_ROOT="$dir"
        break
    fi
done

# DevContainer environment overrides (.env, then .env.local, which wins); set -a exports them to hass, pytest and uv.
if [ -n "$WORKSPACE_ROOT" ]; then
    set -a
    # shellcheck source=/dev/null
    [ -f "$WORKSPACE_ROOT/.devcontainer/.env" ] && . "$WORKSPACE_ROOT/.devcontainer/.env"
    # shellcheck source=/dev/null
    [ -f "$WORKSPACE_ROOT/.devcontainer/.env.local" ] && . "$WORKSPACE_ROOT/.devcontainer/.env.local"
    set +a
fi

# Home Assistant development aliases (work from anywhere!)
if [ -n "$WORKSPACE_ROOT" ]; then
    if [ -d "$WORKSPACE_ROOT/node_modules/.bin" ]; then
        export PATH="$WORKSPACE_ROOT/node_modules/.bin:$PATH"
    fi

    alias ha-develop="$WORKSPACE_ROOT/script/develop"
    alias ha-test="$WORKSPACE_ROOT/script/test"
    alias ha-lint="$WORKSPACE_ROOT/script/lint"
    alias ha-lint-check="$WORKSPACE_ROOT/script/lint-check"
    alias ha-check="$WORKSPACE_ROOT/script/check"
    alias ha-clean="$WORKSPACE_ROOT/script/clean"
    alias ha-type-check="$WORKSPACE_ROOT/script/type-check"
    alias ha-help="$WORKSPACE_ROOT/script/help"
    alias ha-env="$WORKSPACE_ROOT/script/ha-env"

    # Shorthand for common tasks
    alias ha-t="$WORKSPACE_ROOT/script/test"
    alias ha-l="$WORKSPACE_ROOT/script/lint"
    alias ha-d="$WORKSPACE_ROOT/script/develop"
    alias ha-e="$WORKSPACE_ROOT/script/ha-env"

    # shellcheck source=/dev/null
    [ -f "$WORKSPACE_ROOT/script/.lib/ha_env_shell.sh" ] && . "$WORKSPACE_ROOT/script/.lib/ha_env_shell.sh"

    # Copilot CLI wrapper (project-managed defaults).
    if command -v copilot-safe >/dev/null 2>&1; then
        alias copilot='copilot-safe'
    fi
fi

# Change to workspace directory if we're in /home/vscode
if [ "$PWD" = "$HOME" ] && [ -d "/workspaces" ]; then
    cd /workspaces/* 2>/dev/null || true
fi
