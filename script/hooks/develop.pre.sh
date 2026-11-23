# shellcheck shell=bash
# script/hooks/develop.pre.sh: Development-only switches of this integration
#
# TIBBER_PRICES_DEV=1 registers the debug_clear_tomorrow action (service_actions/debug_clear_tomorrow.py), which drops
# tomorrow's prices to test the afternoon polling. It never exists outside the development instance.

export TIBBER_PRICES_DEV="${TIBBER_PRICES_DEV:-1}"
