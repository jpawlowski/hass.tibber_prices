#!/usr/bin/env bash
# .devcontainer/_load_env.sh — Internal helper: source DevContainer environment files
#
# Sources .devcontainer/.env then .devcontainer/.env.local (later wins).
# Not intended to be run directly — source it from DevContainer lifecycle scripts:
#
#   # shellcheck source=.devcontainer/_load_env.sh
#   source "$(cd "$(dirname "$0")" && pwd)/_load_env.sh"
#
# This makes variables like HA_VERSION available in the script and any user
# hooks it runs, equivalent to containerEnv variables in devcontainer.json.

_dc_env_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# set -a / set +a auto-exports every variable defined in sourced files,
# making them available in child processes — equivalent to containerEnv in devcontainer.json.
set -a
if [[ -f "$_dc_env_dir/.env" ]]; then
    # shellcheck source=/dev/null
    source "$_dc_env_dir/.env"
fi
if [[ -f "$_dc_env_dir/.env.local" ]]; then
    # shellcheck source=/dev/null
    source "$_dc_env_dir/.env.local"
fi
set +a
unset _dc_env_dir
