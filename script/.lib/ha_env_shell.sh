# shellcheck shell=bash
# Interactive bash and zsh in the dev container: the active Home Assistant environment, kept current in the prompt.

HA_ENV_ROOT="${HA_ENV_ROOT:-$HOME/ha-venv}"
# Through the venv root, whose links follow script/ha-env use: bin/activate would pin the version behind them, which
# VS Code then takes for another venv.
if [[ -f $HA_ENV_ROOT/bin/activate ]]; then
    export VIRTUAL_ENV="$HA_ENV_ROOT" PATH="$HA_ENV_ROOT/bin:$PATH" VIRTUAL_ENV_DISABLE_PROMPT=1
fi
_HA_ENV_BASE_PS1="$PS1"

_ha_env_prompt() {
    local link slot version="" to="" who="" at=""
    HA_ENV_PROMPT=""
    if link="$(readlink "$HA_ENV_ROOT/current" 2>/dev/null)"; then
        slot="${link##*/}"
        read -r version 2>/dev/null <"$HA_ENV_ROOT/current/.ha-version" || true
        HA_ENV_PROMPT="(ha-${slot}${version:+ $version}) "
        # Someone else switched — another terminal, a VS Code task or an agent: say so once, before this prompt.
        if [[ -n ${_HA_ENV_LAST:-} && $_HA_ENV_LAST != "$slot" ]]; then
            IFS=$'\t' read -r _ to who at 2>/dev/null <"$HA_ENV_ROOT/.switched" || true
            [[ $to == "$slot" ]] || who=""
            printf '\033[1;33m⚠ Home Assistant environment switched: %s → %s%s\033[0m\n' \
                "$_HA_ENV_LAST" "$slot" "${who:+ (by $who at $at)}" >&2
        fi
        _HA_ENV_LAST="$slot"
    fi
    PS1="${HA_ENV_PROMPT}${_HA_ENV_BASE_PS1}"
}

if [[ -n ${ZSH_VERSION:-} ]]; then
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd _ha_env_prompt
elif [[ ${PROMPT_COMMAND:-} != *_ha_env_prompt* ]]; then
    PROMPT_COMMAND="_ha_env_prompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
