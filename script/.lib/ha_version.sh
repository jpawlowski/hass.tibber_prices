#!/bin/bash
# ha_version.sh: Home Assistant version resolution for setup and validation scripts.
#
# Provides resolve_ha_version(), which resolves flexible version specifiers to
# concrete version numbers via PyPI, and target_ha_version(), which picks the
# version the tooling targets.
#
# Source this file after output.sh:
#   # shellcheck source=script/.lib/ha_version.sh
#   source "$SCRIPT_DIR/.lib/ha_version.sh"
#
# Or run it to print the targeted version, for workflows:
#   bash script/.lib/ha_version.sh
#
# Supported version formats:
#   "latest"          → newest stable release on PyPI
#   "beta"            → newest pre-release (alpha/beta/RC) on PyPI
#   "YEAR.MONTH"      → latest stable patch for that month on PyPI
#   "YEAR.MONTH.N"    → returned as-is (explicit stable pin, e.g. 2026.8.0, 2026.8.2)
#   "YEAR.MONTH.NbM"  → returned as-is (explicit pre-release pin, e.g. 2026.8.0b1)
#   "YEAR.MONTH.NrcM" → returned as-is (explicit release-candidate pin)
#
# A hacs.json minimum of YEAR.MONTH.0 means the latest patch; target_ha_version
# strips the .0 before resolving it.

# _PYPI_JSON_CACHE holds the raw PyPI JSON after the first successful fetch so
# that multiple resolve_ha_version calls in the same shell session only hit the
# network once.
_PYPI_JSON_CACHE=""

# _pypi_populate_cache
#
# Fetches the homeassistant PyPI JSON with retry and timeout handling and stores
# it in _PYPI_JSON_CACHE.  Runs in the CURRENT shell (not a subshell) so the
# cache variable is visible to the caller after the function returns.
#
# Retry policy: up to 3 attempts with doubling back-off (2 s → 4 s).
# Timeouts:     10 s to establish a connection, 30 s for the full transfer.
#
# Returns 0 if the cache is populated (either from a prior call or a fresh
# fetch), 1 if all attempts fail.
_pypi_populate_cache() {
    [[ -n "$_PYPI_JSON_CACHE" ]] && return 0

    local attempt max_attempts delay output
    max_attempts=3
    delay=2

    for ((attempt = 1; attempt <= max_attempts; attempt++)); do
        if output=$(curl -fsSL \
            --connect-timeout 10 \
            --max-time 30 \
            https://pypi.org/pypi/homeassistant/json); then
            _PYPI_JSON_CACHE="$output"
            return 0
        fi
        if ((attempt < max_attempts)); then
            log_warning "PyPI request failed (attempt ${attempt}/${max_attempts}), retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done

    log_error "Failed to reach PyPI after ${max_attempts} attempts"
    return 1
}

# _pypi_sort_key VERSION
#
# Emits a zero-padded sort key so pre-releases (a < b < rc) sort before the
# corresponding stable release without requiring external Python packages.
# Used internally; not intended to be called directly.
_PYPI_SORT_KEY_PY='
import sys, re
def key(v):
    m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:(a|b|rc|\.dev)(\d+))?$", v)
    if not m:
        return (0, 0, 0, 4, 0)
    year, month, patch = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    prank = {".dev": 0, "a": 1, "b": 2, "rc": 3}.get(m.group(4), 4)
    pnum = int(m.group(5) or 0)
    return (year, month, patch, prank, pnum)
versions = [v.strip() for v in sys.stdin]
print(sorted(versions, key=key)[-1] if versions else "")
'

# resolve_ha_version OUTPUT_VAR INPUT_VERSION
#
# Resolves a Home Assistant version specifier and stores the result in OUTPUT_VAR.
# Returns 1 and logs an error if PyPI resolution fails.
#
# Usage:
#   resolve_ha_version HA_VERSION "2026.8"      # → e.g., "2026.8.3"
#   resolve_ha_version HA_VERSION "2026.8.0"    # → "2026.8.0" (no-op, explicit pin)
#   resolve_ha_version HA_VERSION "latest"      # → newest stable release
#   resolve_ha_version HA_VERSION "beta"        # → newest pre-release (a/b/rc)
#   resolve_ha_version HA_VERSION "2026.8.3"    # → "2026.8.3" (no-op)
#   resolve_ha_version HA_VERSION "2026.8.0b1"  # → "2026.8.0b1" (no-op)
resolve_ha_version() {
    # shellcheck disable=SC2178  # intentional nameref assignment
    local -n _rha_result="$1"
    local version="$2"
    local resolved

    # "latest" → newest stable release on PyPI (info.version skips pre-releases)
    if [[ "$version" == "latest" ]]; then
        log_info "Resolving latest Home Assistant version via PyPI..."
        _pypi_populate_cache || return 1
        resolved=$(printf '%s' "$_PYPI_JSON_CACHE" |
            python3 -c 'import sys, json; print(json.load(sys.stdin)["info"]["version"])')
        if [[ -z "$resolved" ]]; then
            log_error "Failed to resolve latest Home Assistant version from PyPI"
            return 1
        fi
        log_info "Resolved to: ${resolved}"
        _rha_result="$resolved"
        return 0
    fi

    # "beta" → newest pre-release (alpha/beta/RC) on PyPI
    if [[ "$version" == "beta" ]]; then
        log_info "Resolving latest Home Assistant pre-release version via PyPI..."
        _pypi_populate_cache || return 1
        resolved=$(printf '%s' "$_PYPI_JSON_CACHE" |
            python3 -c 'import sys, json, re
data = json.load(sys.stdin)
pre = [v for v in data["releases"] if re.match(r"^\d{4}\.\d+\.\d+(a|b|rc)\d+$", v)]
sys.stdout.write("\n".join(pre))
' | python3 -c "$_PYPI_SORT_KEY_PY")
        if [[ -z "$resolved" ]]; then
            log_error "Failed to resolve latest Home Assistant pre-release version from PyPI"
            return 1
        fi
        log_info "Resolved to: ${resolved}"
        _rha_result="$resolved"
        return 0
    fi

    # "YEAR.MONTH" (no patch component) → latest stable patch for that minor
    if [[ "$version" =~ ^[0-9]{4}\.[0-9]+$ ]]; then
        local minor_prefix
        minor_prefix="${version}." # "2026.8" → "2026.8."
        log_info "Resolving latest patch for Home Assistant ${minor_prefix%.} via PyPI..."
        _pypi_populate_cache || return 1
        resolved=$(printf '%s' "$_PYPI_JSON_CACHE" |
            python3 -c 'import sys, json
prefix = sys.argv[1]
data = json.load(sys.stdin)
versions = sorted(
    [v for v in data["releases"] if v.startswith(prefix) and all(p.isdigit() for p in v.split("."))],
    key=lambda v: int(v.split(".")[-1])
)
print(versions[-1] if versions else "")
' "$minor_prefix")
        if [[ -z "$resolved" ]]; then
            log_error "Failed to resolve latest patch for Home Assistant ${minor_prefix%.} from PyPI"
            return 1
        fi
        log_info "Resolved to: ${resolved}"
        _rha_result="$resolved"
        return 0
    fi

    # Explicit version (pinned stable or pre-release) → pass through unchanged
    # Examples: "2026.8.3", "2026.8.0b1", "2026.8.0rc2"
    _rha_result="$version"
}

# Print the minimum Home Assistant version in hacs.json; fails when there is none.
hacs_min_ha_version() {
    local version
    version=$(sed -n 's/.*"homeassistant"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' hacs.json 2>/dev/null | head -1)
    [[ -n $version ]] && printf '%s\n' "$version"
}

# Print the Home Assistant version the pytest-homeassistant pin names: without the plugin's repackaging suffix (.post1,
# .dev1), but with a Home Assistant nightly's dated .dev. Prints nothing for another test package.
ha_test_pin_version() {
    local pin
    pin=$(sed -n 's/^pytest-homeassistant==\([^[:space:]#]*\).*/\1/p' requirements_test.txt 2>/dev/null)
    if [[ $pin =~ ^(.+)\.(post[0-9]+|dev[0-9]{1,7})$ ]]; then
        pin=${BASH_REMATCH[1]}
    fi
    printf '%s\n' "$pin"
}

# Print "<test package> <pin> <Home Assistant version it names>"; for pytest-homeassistant-custom-component that comes
# from PyPI and stays empty when PyPI cannot say. Prints nothing for neither package.
ha_test_pin() {
    local package pin ha=""
    read -r package pin < <(sed -En 's/^(pytest-homeassistant(-custom-component)?)==([^[:space:]#]+).*/\1 \3/p' \
        requirements_test.txt 2>/dev/null) || return 0
    if [[ $package == pytest-homeassistant ]]; then
        ha=$(ha_test_pin_version)
    else
        ha=$(curl -sf --retry 2 --connect-timeout 10 --max-time 30 "https://pypi.org/pypi/$package/$pin/json" | python3 -c '
import json, sys
for req in json.load(sys.stdin)["info"].get("requires_dist") or []:
    if req.startswith("homeassistant=="):
        print(req.split("==", 1)[1].split(";")[0].strip())
        break
' 2>/dev/null) || ha=""
    fi
    printf '%s %s %s\n' "$package" "$pin" "$ha"
}

# Print the release train of a Home Assistant version: 2026.11 for 2026.11, 2026.11.2 or 2026.11.0b3.
ha_release_train() {
    if [[ $1 =~ ^([0-9]+\.[0-9]+) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    fi
}

ha_version_is_prerelease() {
    [[ $1 =~ [0-9](a|b|rc)[0-9]+$|\.dev[0-9]+$ ]]
}

# Whether VERSION is a Home Assistant release on PyPI.
ha_version_released() {
    _pypi_populate_cache || return 1
    printf '%s' "$_PYPI_JSON_CACHE" | python3 -c 'import json, sys; sys.exit(sys.argv[1] not in json.load(sys.stdin)["releases"])' "$1"
}

# Print the Python minor version a Home Assistant release asks for — the lower bound of its requires-python, which
# is what Home Assistant ships it with — or nothing when PyPI does not say.
ha_python_for() {
    _pypi_populate_cache || return 1
    printf '%s' "$_PYPI_JSON_CACHE" | python3 -c '
import json, re, sys
files = json.load(sys.stdin)["releases"].get(sys.argv[1]) or []
spec = next((f["requires_python"] for f in files if f.get("requires_python")), "")
match = re.search(r">=\s*(\d+)\.(\d+)", spec)
print(f"{match[1]}.{match[2]}" if match else "")
' "$1"
}

# ha_version_newer A B — whether Home Assistant version A is newer than B, pre-releases included.
ha_version_newer() {
    [[ $1 != "$2" ]] || return 1
    [[ $(printf '%s\n%s\n' "$1" "$2" | python3 -c "$_PYPI_SORT_KEY_PY") == "$1" ]]
}

# target_ha_version RESULT_VAR
#
# Resolves the Home Assistant version the tooling targets: HA_VERSION when it is
# set, otherwise the minimum in hacs.json, where YEAR.MONTH.0 stands for the
# latest patch of that month.
#
# Usage:
#   target_ha_version HA_VERSION   # hacs.json "2026.8.0" → e.g., "2026.8.3"
target_ha_version() {
    # shellcheck disable=SC2178  # intentional nameref assignment
    local -n _tha_result="$1"
    local _tha_version="${HA_VERSION:-}" _tha_resolved

    if [[ -z "$_tha_version" ]]; then
        if ! _tha_version=$(hacs_min_ha_version); then
            log_error "HA_VERSION not set and could not be determined from hacs.json"
            return 1
        fi
        if [[ "$_tha_version" =~ ^[0-9]{4}\.[0-9]+\.0$ ]]; then
            _tha_version="${_tha_version%.*}"
        fi
    fi
    resolve_ha_version _tha_resolved "$_tha_version" || return 1
    _tha_result="$_tha_resolved"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    set -euo pipefail
    cd "$(dirname "$0")/../.."
    # shellcheck source=script/.lib/output.sh
    source script/.lib/output.sh
    for _env_file in .devcontainer/.env .devcontainer/.env.local; do
        # shellcheck source=/dev/null
        if [[ -f "$_env_file" ]]; then source "$_env_file"; fi
    done
    _version=""
    target_ha_version _version >&2
    printf '%s\n' "$_version"
fi
