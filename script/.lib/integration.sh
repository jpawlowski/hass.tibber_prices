#!/bin/bash
# Integration detection library
# shellcheck disable=SC2034  # INTEGRATION_DOMAIN and INTEGRATION_PATH are used by sourcing scripts
#
# Automatically detects the custom integration domain by scanning custom_components/
# for a directory that contains a manifest.json, excluding the HACS dev dependency.
#
# Exported variables (available after sourcing):
#   INTEGRATION_DOMAIN  — e.g. "my_integration"
#   INTEGRATION_PATH    — e.g. "custom_components/my_integration"
#
# Override by setting INTEGRATION_DOMAIN before sourcing:
#   INTEGRATION_DOMAIN=my_integration source script/.lib/integration.sh

# _detect_integration_domain: scan custom_components/ and return the first
# real (non-symlink) directory that contains a manifest.json.
#
# Marketplace- and HACS-installed integrations are symlinks created by script/setup/sync-hacs
# (custom_components/<name> → ../../config/custom_components/<name>), so
# excluding symlinks reliably isolates the blueprint's own integration.
_detect_integration_domain() {
    local dir name
    for dir in custom_components/*/; do
        [[ -d "$dir" ]] || continue
        # Skip symlinks — installed integrations are linked from config/custom_components/
        [[ -L "${dir%/}" ]] && continue
        name="${dir%/}"
        name="${name##*/}"
        # Skip Python cache artefacts
        [[ "$name" == "__pycache__" ]] && continue
        [[ -f "${dir}manifest.json" ]] || continue
        echo "$name"
        return 0
    done
    return 1
}

if [[ -z "${INTEGRATION_DOMAIN:-}" ]]; then
    INTEGRATION_DOMAIN="$(_detect_integration_domain)" || {
        echo "error: could not detect integration domain in custom_components/" >&2
        exit 1
    }
fi

INTEGRATION_PATH="custom_components/${INTEGRATION_DOMAIN}"
