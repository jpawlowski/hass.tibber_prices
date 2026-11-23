# shellcheck shell=bash
# script/hooks/build.post.sh: Add a gzip copy of every dashboard card module to the release build
#
# Sourced by script/build after it copied the integration into $BUILD_DIR. aiohttp sends <module>.js.gz to browsers
# that accept gzip and the module itself to the rest; why the copies exist only in a release and never in the
# repository is in the docstring of custom_components/tibber_prices/frontend/__init__.py. A copy that no longer
# matches its module is deleted when the integration starts (_drop_stale_copies()).
#
# --in-place builds the integration folder itself for script/develop: no copies there, the modules are served as they
# are, so the hook does nothing.

if [[ $IN_PLACE == true ]]; then
    log_info "No gzip copies of the card modules for an in-place build"
else
    command -v gzip >/dev/null 2>&1 || die "gzip is required to build the release (apt-get install gzip)"
    cards_dir="$BUILD_DIR/frontend/cards"
    [[ -d $cards_dir ]] || die "$cards_dir is missing: the cards are part of every release"
    # -k keeps the module next to its copy, -n leaves name and time out, so the same module gives the same copy
    find "$cards_dir" -name '*.js' -exec gzip -9 -k -n {} +
    for required in "$cards_dir/tibber-prices-cards.js" "$cards_dir/tibber-prices-cards.js.gz"; do
        [[ -f $required ]] || die "$required is missing from the build"
    done
    log_success "Added gzip copies of $(find "$cards_dir" -name '*.js.gz' | wc -l) card modules"
    unset cards_dir required
fi
