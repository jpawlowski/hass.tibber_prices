# shellcheck shell=bash
# script/hooks/lint-check.post.sh: Fail when a generated file no longer matches its source
#
# Sourced by script/lint-check, which CI runs and script/check calls. Both generators read the translations:
# - docs/user/docs/sensor-reference.md, the multi-language entity lookup table (script/docs/generate-sensor-reference.py)
# - the attribute names under state_attributes in translations/*.json (script/i18n/generate-attribute-translations.py)
# Run the generator without --check to update the file.

log_header "Checking generated files against the translations"
python3 script/docs/generate-sensor-reference.py --check
python3 script/i18n/generate-attribute-translations.py --check
