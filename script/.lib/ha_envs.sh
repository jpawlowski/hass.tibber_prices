#!/bin/bash
# ha_envs.sh: Home Assistant environments side by side (script/ha-env, bootstrap); source after output.sh.
# What they do: docs/development/CUSTOMIZATION.md, "Testing against a newer Home Assistant".

# shellcheck source=script/.lib/download.sh
source "${BASH_SOURCE[0]%/*}/download.sh"
# shellcheck source=script/.lib/ha_version.sh
source "${BASH_SOURCE[0]%/*}/ha_version.sh"

# shellcheck disable=SC2034 # Read by the scripts that source this file
HA_ENVS_SLOTS=(minimum latest beta custom)
HA_ENVS_ROOT_LINKS=(bin lib lib64 include pyvenv.cfg)
HA_ENVS_REQUIREMENTS=(requirements_dev.txt requirements_test.txt requirements.txt requirements.local.txt)

# ha_envs_resolve SLOT RESULT_VAR — the version a slot should hold now; fails when it breaks the slot's kind. custom
# keeps its pin unless HA_ENVS_CUSTOM_VERSION moves it, never below hacs.json's minimum.
ha_envs_resolve() {
    local slot="$1"
    # shellcheck disable=SC2178 # Intentional nameref assignment
    local -n _her_result="$2"
    local _her_version=""
    case "$slot" in
    minimum) HA_VERSION="" target_ha_version _her_version || return 1 ;;
    latest | beta) resolve_ha_version _her_version "$slot" || return 1 ;;
    custom)
        if [[ -n ${HA_ENVS_CUSTOM_VERSION:-} ]]; then
            resolve_ha_version _her_version "$HA_ENVS_CUSTOM_VERSION" || return 1
            if ! ha_version_released "$_her_version"; then
                log_error "Home Assistant $_her_version is not a release on PyPI"
                return 1
            fi
        else
            _her_version=$(ha_envs_version_of custom)
            if [[ -z $_her_version ]]; then
                log_error "custom needs a version — run: script/ha-env add custom <version>"
                return 1
            fi
        fi
        local _her_floor
        _her_floor=$(hacs_min_ha_version 2>/dev/null) || _her_floor=""
        if [[ -n $_her_floor ]] && ha_version_newer "$_her_floor" "$_her_version"; then
            log_error "Home Assistant $_her_version is older than $_her_floor, the minimum hacs.json promises"
            return 1
        fi
        ;;
    *)
        log_error "Unknown Home Assistant environment: $slot (use ${HA_ENVS_SLOTS[*]})"
        return 1
        ;;
    esac
    if [[ $slot == beta ]] && ! ha_version_is_prerelease "$_her_version"; then
        log_error "beta resolved to $_her_version, which is not a pre-release"
        return 1
    fi
    if [[ $slot == latest ]] && ha_version_is_prerelease "$_her_version"; then
        log_error "latest resolved to $_her_version, which is a pre-release"
        return 1
    fi
    _her_result="$_her_version"
}

# Print the version a slot points at, or nothing when it is not installed.
ha_envs_version_of() {
    local link target
    link="$(ha_venv_preferred_path)/slots/$1"
    [[ -L $link && -f $link/.ha-version ]] || return 0
    target="$(readlink "$link")"
    printf '%s\n' "${target##*/}"
}

# Where uv keeps the Python builds the venvs use: beside them, so the volume that keeps a venv keeps its interpreter.
ha_envs_python_dir() {
    printf '%s/python' "$(ha_venv_preferred_path)"
}

# ha_envs_create_venv DIR VERSION — a venv on the Python that Home Assistant VERSION asks for. Only uv-managed builds:
# one from the OS image or mise could vanish while the venv survives in the volume.
ha_envs_create_venv() {
    local dir="$1" python args=(--python-preference only-managed)
    _pypi_populate_cache >/dev/null 2>&1 || true
    python=$(ha_python_for "$2" 2>/dev/null) || python=""
    if [[ -n $python ]]; then
        log_info "Python $python for Home Assistant $2"
        args+=(--python "$python")
    fi
    UV_PYTHON_INSTALL_DIR="$(ha_envs_python_dir)" uv venv --quiet --prompt "ha-${dir##*/}" "${args[@]}" "$dir"
}

# Print what an environment is built from — its version and the requirements files — so an unchanged one is skipped.
ha_envs_inputs() {
    printf '%s\n' "$1"
    python3 - "${HA_ENVS_REQUIREMENTS[@]}" <<'PY'
import hashlib, os, sys
for name in sys.argv[1:]:
    if os.path.isfile(name):
        with open(name, "rb") as handle:
            print(f"{hashlib.sha256(handle.read()).hexdigest()}  {name}")
PY
}

# ha_envs_install DIR VERSION — install the project, its tests and Home Assistant VERSION into the venv DIR.
ha_envs_install() {
    local dir="$1" version="$2" base="https://raw.githubusercontent.com/home-assistant/core/$2"
    local tmp pinned status=0
    tmp=$(mktemp -d)
    pinned=$(ha_test_pin_version)
    (
        set -euo pipefail
        _use_venv "$dir"
        log_header "Installing development dependencies into Home Assistant $version"
        uv pip install --requirement requirements_dev.txt

        log_header "Installing test dependencies"
        # requirements_test.txt pins the plugin release of the minimum version; another version needs its own.
        if [[ -n $pinned && $pinned != "$version" ]]; then
            printf 'pytest-homeassistant==%s\n' "$version" >"$tmp/override.txt"
            if ! uv pip install --requirement requirements_test.txt --override "$tmp/override.txt"; then
                log_warning "No pytest-homeassistant $version — the tests run the $pinned fixtures against it"
                uv pip install --requirement requirements_test.txt
            fi
        else
            uv pip install --requirement requirements_test.txt
        fi

        if grep -qE '^[[:space:]]*[^[:space:]#]' requirements.txt 2>/dev/null; then
            log_header "Installing runtime dependencies"
            uv pip install --requirement requirements.txt
        fi
        if [[ -f requirements.local.txt ]]; then
            log_header "Installing local extra dependencies (requirements.local.txt)"
            uv pip install --requirement requirements.local.txt
        fi

        log_header "Installing Home Assistant $version runtime dependencies"
        mkdir -p "$tmp/homeassistant"
        _download "$base/homeassistant/package_constraints.txt" "$tmp/homeassistant/package_constraints.txt"
        _download "$base/requirements.txt" "$tmp/requirements.txt"
        _download "$base/requirements_all.txt" "$tmp/requirements_all.txt"
        uv pip install --requirement "$tmp/requirements_all.txt"

        log_header "Installing Home Assistant $version test dependencies"
        _download "$base/requirements_test_pre_commit.txt" "$tmp/requirements_test_pre_commit.txt"
        _download "$base/requirements_test.txt" "$tmp/requirements_test.txt"
        uv pip install --requirement "$tmp/requirements_test.txt"

        log_header "Installing Home Assistant $version core"
        uv pip install "homeassistant==$version"
    ) || status=$?
    rm -rf "$tmp"
    return "$status"
}

# ha_envs_build VERSION — create versions/VERSION if needed and bring its packages up to date. A venv that never
# completed is rebuilt from scratch; a complete one that fails to update is kept as it was.
ha_envs_build() {
    local version="$1" dir inputs
    dir="$(ha_venv_preferred_path)/versions/$1"
    inputs="$(ha_envs_inputs "$version")"
    if [[ -f $dir/.ha-version ]]; then
        if [[ -f $dir/.ha-inputs && $(<"$dir/.ha-inputs") == "$inputs" ]]; then
            log_info "Home Assistant $version is up to date"
            return 0
        fi
        if ! ha_envs_install "$dir" "$version"; then
            log_warning "Could not update the Home Assistant $version environment — keeping it as it was"
            return 1
        fi
    else
        rm -rf "$dir"
        mkdir -p "${dir%/*}"
        log_info "Creating the Home Assistant $version environment"
        if ! ha_envs_create_venv "$dir" "$version" || ! ha_envs_install "$dir" "$version"; then
            rm -rf "$dir"
            log_error "Could not build the Home Assistant $version environment"
            return 1
        fi
        printf '%s\n' "$version" >"$dir/.ha-version"
    fi
    printf '%s\n' "$inputs" >"$dir/.ha-inputs"
}

# ha_envs_refresh SLOT — resolve the slot, build its version, and point the slot at it only once the build succeeded.
# The environment a running Home Assistant uses is left as it is, with status 2.
ha_envs_refresh() {
    local slot="$1" version="" root
    if [[ $slot == "$(ha_running_slot)" && -n $(ha_envs_version_of "$slot") ]]; then
        log_warning "$slot: left as it is while Home Assistant runs on it — stop it first, then run this again"
        return 2
    fi
    ha_envs_resolve "$slot" version || return 1
    ha_envs_build "$version" || return 1
    root="$(ha_venv_preferred_path)"
    mkdir -p "$root/slots"
    ln -sfn "../versions/$version" "$root/slots/$slot"
    touch "$root/slots/.$slot.refreshed"
    log_success "$slot: Home Assistant $version"
}

# Make SLOT the active environment and mirror it at the venv root. A switch is recorded in .switched (from, to,
# who, when; tab-separated), which the prompt hook reports in every open terminal.
ha_envs_use() {
    local root entry previous
    root="$(ha_venv_preferred_path)"
    if [[ -z $(ha_envs_version_of "$1") ]]; then
        log_error "$1 is not installed — run: script/ha-env add $1"
        return 1
    fi
    previous="$(ha_current_slot)"
    ln -sfn "slots/$1" "$root/current"
    if [[ -n $previous && $previous != "$1" ]]; then
        printf '%s\t%s\t%s\t%s\n' "$previous" "$1" "$(ha_actor)" "$(date +%H:%M)" >"$root/.switched"
    fi
    for entry in "${HA_ENVS_ROOT_LINKS[@]}"; do
        if [[ -e $root/current/$entry ]]; then
            ln -sfn "current/$entry" "$root/$entry"
        else
            rm -f "$root/$entry"
        fi
    done
}

ha_envs_remove() {
    local slot="$1"
    if [[ $slot == minimum ]]; then
        log_error "minimum cannot be removed — it is the version hacs.json promises"
        return 1
    fi
    if [[ $slot == "$(ha_current_slot)" ]]; then
        log_error "$slot is the active environment — run: script/ha-env use minimum"
        return 1
    fi
    rm -f "$(ha_venv_preferred_path)/slots/$slot" "$(ha_venv_preferred_path)/slots/.$slot.refreshed"
}

# Delete every version no slot points at, unfinished builds included, then every downloaded Python no venv uses.
ha_envs_prune() {
    local root dir link target
    root="$(ha_venv_preferred_path)"
    local -A keep=()
    for link in "$root"/slots/*; do
        [[ -L $link ]] || continue
        target="$(readlink "$link")"
        keep[${target##*/}]=1
    done
    for dir in "$root"/versions/*; do
        [[ -d $dir && -z ${keep[${dir##*/}]:-} ]] || continue
        log_step "Removing the unused Home Assistant ${dir##*/} environment"
        rm -rf "$dir"
    done
    [[ -d $(ha_envs_python_dir) ]] || return 0
    UV_PYTHON_INSTALL_DIR="$(ha_envs_python_dir)" uv python list --only-installed --python-preference only-managed \
        --output-format json 2>/dev/null | python3 -c '
import json, os, sys
homes = set()
for name in os.listdir(sys.argv[1]) if os.path.isdir(sys.argv[1]) else ():
    try:
        cfg = open(os.path.join(sys.argv[1], name, "pyvenv.cfg"), encoding="utf-8").read()
    except OSError:
        continue
    homes |= {os.path.realpath(line.split("=", 1)[1].strip()) for line in cfg.splitlines() if line.startswith("home")}
try:
    builds = json.load(sys.stdin)
except ValueError:
    builds = []
for build in builds:
    if os.path.realpath(os.path.dirname(build["path"])) not in homes:
        print(build["key"])
' "$root/versions" | while read -r build; do
        log_step "Removing the unused Python $build"
        uv python uninstall --quiet --install-dir "$(ha_envs_python_dir)" "$build"
    done
    return 0
}

# Clear a venv root that still holds the single venv of the old layout; the slots are rebuilt from scratch.
ha_envs_migrate() {
    local root
    root="$(ha_venv_preferred_path)"
    [[ -f $root/pyvenv.cfg && ! -L $root/pyvenv.cfg ]] || return 0
    if ha_running; then
        log_error "Home Assistant is running from $root — stop it first, then run this again"
        return 1
    fi
    log_warning "Moving $root to one environment per Home Assistant version — the old one is rebuilt"
    if declare -F deactivate >/dev/null 2>&1; then
        deactivate
    fi
    # The root can be a Docker volume mount point, which only lets its contents be deleted.
    find "$root" -mindepth 1 -maxdepth 1 ! -name versions ! -name slots ! -name python ! -name .uv-cache \
        -exec rm -rf {} +
    hash -r
}

# ha_envs_prepare_config DIR VERSION — link the files a slot's config directory shares with config/. Only a directory
# this creates starts from config/'s .storage, and only when VERSION can migrate it forward.
ha_envs_prepare_config() {
    local dir="$1" version="$2" item ran config new=false
    [[ -d $dir ]] || new=true
    mkdir -p "$dir"
    config=$(python3 -c 'import os, sys; print(os.path.relpath(*sys.argv[1:]))' config "$dir")
    for item in configuration.yaml secrets.yaml automations.yaml scripts.yaml scenes.yaml custom_components blueprints www; do
        if [[ -e config/$item && ! -e $dir/$item && ! -L $dir/$item ]]; then
            ln -s "$config/$item" "$dir/$item"
        fi
    done
    [[ $new == true && -d config/.storage && -f config/.HA_VERSION ]] || return 0
    ran=$(<config/.HA_VERSION)
    if ha_version_newer "$ran" "$version"; then
        log_info "$dir starts empty: config/ was last run by Home Assistant $ran, newer than $version"
        return 0
    fi
    log_step "Starting $dir from the state in config/ (Home Assistant $ran)"
    cp -a config/.storage "$dir/.storage"
    cp config/.HA_VERSION "$dir/.HA_VERSION"
}

# ha_envs_guard_config DIR VERSION — move aside what a newer Home Assistant than VERSION migrated in DIR.
ha_envs_guard_config() {
    local dir="$1" version="$2" ran item
    [[ -f $dir/.HA_VERSION ]] || return 0
    ran=$(<"$dir/.HA_VERSION")
    ha_version_newer "$ran" "$version" || return 0
    log_warning "$dir was last run by Home Assistant $ran, newer than $version — moving its state aside"
    for item in .storage home-assistant_v2.db home-assistant_v2.db-shm home-assistant_v2.db-wal; do
        [[ -e $dir/$item ]] && mv "$dir/$item" "$dir/$item.$ran.bak"
    done
    return 0
}

# Print what is stale, without the network: a latest or beta not refreshed for a week, a minimum on another release
# than hacs.json, or a custom older than it.
ha_envs_notice() {
    local root slot stamp minimum custom hacs
    root="$(ha_venv_preferred_path)"
    for slot in latest beta; do
        stamp="$root/slots/.$slot.refreshed"
        if [[ -L $root/slots/$slot && -f $stamp && -n $(find "$stamp" -mtime +7 2>/dev/null) ]]; then
            log_warning "$slot ($(ha_envs_version_of "$slot")) was last refreshed over 7 days ago — run: script/ha-env refresh $slot"
        fi
    done
    minimum=$(ha_envs_version_of minimum)
    custom=$(ha_envs_version_of custom)
    hacs=$(hacs_min_ha_version 2>/dev/null) || return 0
    if [[ -n $custom ]] && ha_version_newer "$hacs" "$custom"; then
        log_warning "custom holds Home Assistant $custom, older than $hacs from hacs.json — run: script/ha-env add custom <version>"
    fi
    hacs=$(ha_release_train "$hacs")
    if [[ -n $minimum && -n $hacs && $minimum != "$hacs".* ]]; then
        log_warning "minimum runs Home Assistant $minimum, but hacs.json asks for $hacs — run: script/ha-env refresh minimum"
    fi
    return 0
}
