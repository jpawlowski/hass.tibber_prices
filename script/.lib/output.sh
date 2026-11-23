#!/bin/bash
# Output formatting library for consistent script styling
# Source this file in your scripts with: source "$(dirname "$0")/../.lib/output.sh"
# shellcheck disable=SC2034  # All variables in this library are used by sourcing scripts

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly NC='\033[0m' # No Color

readonly CHECK='✓'
readonly CROSS='✗'
readonly ARROW='→'
readonly INFO='ℹ'
readonly WARNING='⚠'
# shellcheck disable=SC2034  # These symbols are available to sourcing scripts
readonly ROCKET='🚀'
readonly PACKAGE='📦'
readonly WRENCH='🔧'
readonly SPARKLES='✨'
readonly BUG='🐛'
readonly BOOKS='📚'

log_header() {
    printf "\n%b==> %b%b\n" "$BOLD$BLUE" "$1" "$NC"
}

log_success() {
    printf "%b%s %b%b\n" "$GREEN" "$CHECK" "$1" "$NC"
}

log_error() {
    printf "%b%s %b%b\n" "$RED" "$CROSS" "$1" "$NC" >&2
}

log_warning() {
    printf "%b%s %b%b\n" "$YELLOW" "$WARNING" "$1" "$NC"
}

log_info() {
    printf "%b%s %b%b\n" "$CYAN" "$INFO" "$1" "$NC"
}

log_step() {
    printf "    %b%s%b %b\n" "$DIM" "$ARROW" "$NC" "$1"
}

log_result() {
    local status=$1
    shift
    if [[ $status -eq 0 ]]; then
        printf "    %b%s %s%b\n" "$GREEN" "$CHECK" "$*" "$NC"
    else
        printf "    %b%s %s%b\n" "$RED" "$CROSS" "$*" "$NC"
    fi
}

log_separator() {
    printf "%b%s%b\n" "$DIM" "────────────────────────────────────────────────────────────" "$NC"
}

die() {
    log_error "$1"
    exit "${2:-1}"
}

require_command() {
    local cmd=$1
    local install_hint=${2:-""}

    if ! command -v "$cmd" >/dev/null 2>&1; then
        log_error "Required command not found: $cmd"
        if [[ -n $install_hint ]]; then
            log_info "Install with: $install_hint"
        fi
        exit 1
    fi
}

# Print the path of the virtual environment this environment should use.
# Returns 1 and prints nothing when none exists.
#
# The location must agree with script/setup/bootstrap, which creates and
# maintains it: DevContainer and Codespaces keep the venv in $HOME (a named
# volume), GitHub Actions and local development keep it in the workspace.
# Preferring $HOME/ha-venv unconditionally fails quietly in the one case that
# matters: a leftover $HOME/ha-venv from an earlier DevContainer session
# outranks the workspace venv that bootstrap actually updates, so every script
# keeps running against a stale Home Assistant version while looking perfectly
# healthy. Fall back to the other locations, but say so.
resolve_venv_path() {
    local preferred candidate
    preferred="$(ha_venv_preferred_path)"

    if [[ -f "$preferred/bin/activate" ]]; then
        printf '%s' "$preferred"
        return 0
    fi

    for candidate in "$HOME/ha-venv" "$PWD/.local/ha-venv" "$HOME/.local/ha-venv"; do
        if [[ "$candidate" != "$preferred" && -f "$candidate/bin/activate" ]]; then
            # To stderr: this function's stdout is the resolved path.
            log_warning "Expected the virtual environment at $preferred, using $candidate instead — run script/setup/bootstrap to rebuild it where this environment looks for it" >&2
            printf '%s' "$candidate"
            return 0
        fi
    done

    return 1
}

# Print where bootstrap keeps the venv here: a named volume in the dev container, the workspace everywhere else.
ha_venv_preferred_path() {
    if [[ -n ${REMOTE_CONTAINERS:-} || -n ${CODESPACES:-} ]]; then
        printf '%s' "$HOME/ha-venv"
    elif [[ -n ${GITHUB_ACTIONS:-} ]]; then
        printf '%s' "${GITHUB_WORKSPACE:-$PWD}/.local/ha-venv"
    else
        printf '%s' "$PWD/.local/ha-venv"
    fi
}

# Print the active Home Assistant environment (script/ha-env), or nothing for a venv without environments.
ha_current_slot() {
    local venv_path link
    venv_path="$(resolve_venv_path 2>/dev/null)" || return 0
    link="$(readlink "$venv_path/current" 2>/dev/null)" || return 0
    printf '%s' "${link##*/}"
}

# Whether a local Home Assistant runs in any environment: one holds the lock on its config directory's run lock.
ha_running() {
    python3 - config/.ha_run.lock .local/ha-config/*/.ha_run.lock <<'PY'
import fcntl, sys
for name in sys.argv[1:]:
    try:
        with open(name, "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)
    except OSError:
        continue
sys.exit(1)
PY
}

# Print the environment a running Home Assistant uses — from the record script/develop writes, which stays right after
# script/ha-env use --force — or nothing when none runs.
ha_running_slot() {
    ha_running || return 0
    local slot
    slot=$(jq -r '.slot // empty' .local/ha-develop.json 2>/dev/null) || slot=""
    printf '%s' "${slot:-$(ha_current_slot)}"
}

# Print who runs this script: an agent where the agent says so in its environment, the developer otherwise.
ha_actor() {
    if [[ -n ${AI_AGENT:-} ]]; then
        printf 'agent (%s)' "${AI_AGENT%%_*}"
    elif [[ -n ${CLAUDECODE:-} ]]; then
        printf 'agent (claude-code)'
    else
        printf 'developer'
    fi
}

# Print the config directory of the active Home Assistant environment, relative to the repository root:
# config/ for minimum (and for a venv without environments), its own directory for every other one.
ha_config_dir() {
    local slot
    slot="$(ha_current_slot)"
    case "$slot" in
    "" | minimum) printf 'config' ;;
    *) printf '.local/ha-config/%s' "$slot" ;;
    esac
}

# Point VIRTUAL_ENV and PATH at the venv root, whose links follow script/ha-env use; bin/activate would pin the
# version directory behind them, and an activation that names one is moved back to the root.
_use_venv() {
    export VIRTUAL_ENV="$1" PATH="$1/bin:$PATH" VIRTUAL_ENV_DISABLE_PROMPT=1
    unset PYTHONHOME
    hash -r
}

# Activate the Home Assistant virtual environment if not already active, and export HA_CONFIG_DIR for it.
activate_venv() {
    export HA_CONFIG_DIR
    HA_CONFIG_DIR="$(ha_config_dir)"
    if [[ -n ${VIRTUAL_ENV:-} && $VIRTUAL_ENV != */versions/* ]]; then
        return 0
    fi
    local venv_path
    if ! venv_path="$(resolve_venv_path)"; then
        if [[ "$(run_state bootstrap)" == "running" ]]; then
            log_error "The development environment is still being set up — wait for .local/bootstrap.status to change, progress is in .local/bootstrap.log"
        else
            log_error "Virtual environment not found. Run: script/setup/bootstrap"
        fi
        exit 1
    fi
    log_header "Activating virtual environment"
    _use_venv "$venv_path"
}

# Like activate_venv, for a script that needs the venv only for optional extras: carries on without one.
activate_venv_if_present() {
    if [[ -n ${VIRTUAL_ENV:-} && $VIRTUAL_ENV != */versions/* ]]; then
        return 0
    fi
    local venv_path
    venv_path="$(resolve_venv_path)" || return 0
    _use_venv "$venv_path"
}

# Run a user-defined hook script if it exists.
# Hooks live in script/user/<name>.<phase>.sh and are sourced (not executed),
# so they can read and set variables in the calling script's environment.
#
# Usage:  run_hook <script-name> <phase>
# Phases: pre | post
#
# Example — in script/develop:
#   run_hook "develop" "pre"
#
# The user creates script/user/develop.pre.sh to customize behavior.
# SCRIPT_DIR must be set in the calling script before sourcing output.sh.
run_hook() {
    local script_name="$1"
    local phase="$2"
    local hook_file="script/hooks/${script_name}.${phase}.sh"
    if [[ -f "$hook_file" ]]; then
        log_info "Running hook: script/hooks/${script_name}.${phase}.sh"
        # shellcheck source=/dev/null
        source "$hook_file"
    fi
}

# Print how the last run of a script that calls track_run went: running, done, failed or nothing. A run whose process
# is gone without recording an end counts as failed.
run_state() {
    local state pid
    state="$(cat ".local/$1.status" 2>/dev/null || true)"
    if [[ $state == "running" ]]; then
        pid="$(cat ".local/$1.pid" 2>/dev/null || true)"
        if [[ -z $pid ]] || ! kill -0 "$pid" 2>/dev/null; then
            state="failed"
        fi
    fi
    printf '%s' "$state"
}

# Record this script's run in .local/<name>.status and .local/<name>.pid, and its outcome when it exits. With
# --exclusive, a second run while one is alive stops instead of competing for the same environment.
track_run() {
    local name=$1
    if [[ ${2:-} == "--exclusive" && "$(run_state "$name")" == "running" ]]; then
        die "script/setup/$name is already running (PID $(cat ".local/$name.pid")); wait for it to finish"
    fi
    mkdir -p .local
    echo "$$" >".local/$name.pid"
    echo "running" >".local/$name.status"
    # shellcheck disable=SC2064 # $name is fixed now, the exit status when the trap runs
    trap "_finish_run $name \$?" EXIT
}

# Wait while another run of a tracked script is alive, up to a limit in seconds (default 900). Returns 1 on timeout.
wait_for_run() {
    local name=$1 limit=${2:-900} waited=0
    while [[ "$(run_state "$name")" == "running" ]]; do
        if ((waited >= limit)); then
            return 1
        fi
        if ((waited == 0)); then
            log_info "Waiting for the script/setup/$name run already in progress (PID $(cat ".local/$name.pid" 2>/dev/null))"
        fi
        sleep 1
        waited=$((waited + 1))
    done
}

_finish_run() {
    if [[ $2 -eq 0 ]]; then
        echo "done" >".local/$1.status"
    else
        echo "failed" >".local/$1.status"
    fi
    rm -f ".local/$1.pid"
}

# Apply what mise resolves for this checkout: the pinned tools and the venv mise.toml names, in front of PATH. Every
# script gets them whether or not the calling shell activated mise — an agent's shell, a cloud session and a git hook
# usually have not. Without mise, or before the checkout trusts mise.toml, nothing changes.
use_mise_env() {
    local mise_bin script
    mise_bin="$(command -v mise 2>/dev/null || true)"
    if [[ -z $mise_bin && -x "$HOME/.local/bin/mise" ]]; then
        mise_bin="$HOME/.local/bin/mise"
    fi
    [[ -n $mise_bin && -f mise.toml ]] || return 0
    script="$(MISE_HIDE_UPDATE_WARNING=1 "$mise_bin" env -s bash 2>/dev/null)" || return 0
    eval "$script"
    export _BLUEPRINT_MISE_ENV="$PWD"
}

# A script started by another one inherits the environment already applied, so only the outermost one asks mise.
if [[ ${_BLUEPRINT_MISE_ENV:-} != "$PWD" ]]; then
    use_mise_env
fi
