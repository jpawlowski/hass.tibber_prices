#!/bin/bash
# Coding agent CLI library
# shellcheck disable=SC2034  # AGENT_NAME and AGENT_BIN are used by sourcing scripts
#
# Runs a one-shot prompt through whichever coding agent CLI is installed and signed in — Claude Code, Codex, GitHub
# Copilot or OpenCode, all four of which the dev container installs. agent_prompt gives the agent no tools, so
# everything it needs is in the prompt; agent_review starts it in a directory to read, and lets it run and write
# nothing.
#
# Variables read:
#   AGENT_CLI    claude, codex, copilot or opencode; unset or "auto" picks one (see agent_resolve)
#   AGENT_MODEL  model passed to the CLI; unset leaves the CLI's own default (for copilot: COPILOT_MODEL)
#
# Set after agent_resolve:
#   AGENT_NAME   the chosen CLI's name
#   AGENT_BIN    the command that runs it

AGENT_CLIS=(claude codex copilot opencode)

# _agent_bin NAME: print the command for one CLI, or nothing when it is not installed.
_agent_bin() {
    if [[ "$1" == copilot && -x "$PWD/node_modules/.bin/copilot" ]]; then
        echo "$PWD/node_modules/.bin/copilot"
    elif command -v "$1" >/dev/null 2>&1; then
        echo "$1"
    fi
}

# _agent_login NAME: print how to sign in to one CLI.
_agent_login() {
    case "$1" in
    claude) echo "run claude and type /login" ;;
    codex) echo "codex login" ;;
    copilot) echo "copilot login" ;;
    opencode) echo "opencode auth login" ;;
    esac
}

# _agent_has_key NAME: succeed when the environment holds a key the CLI signs in with — no process needed.
_agent_has_key() {
    case "$1" in
    claude) [[ -n "${ANTHROPIC_API_KEY:-}" ]] ;;
    codex) [[ -n "${CODEX_API_KEY:-}${OPENAI_API_KEY:-}" ]] ;;
    # GH_TOKEN and GITHUB_TOKEN are often set for gh or CI without Copilot access, so they prove nothing.
    copilot) [[ -n "${COPILOT_GITHUB_TOKEN:-}" ]] ;;
    *) return 1 ;;
    esac
}

# _agent_signed_in NAME BIN: 0 when signed in, 1 when not, 2 when the CLI cannot tell without sending a request.
# Every check is local and bounded, so a CLI that waits for input cannot hang the caller.
_agent_signed_in() {
    local out
    _agent_has_key "$1" && return 0
    case "$1" in
    claude)
        timeout 10 "$2" auth status --json </dev/null 2>/dev/null | jq -e '.loggedIn == true' >/dev/null 2>&1
        ;;
    codex)
        timeout 10 "$2" login status </dev/null >/dev/null 2>&1
        ;;
    opencode)
        out="$(timeout 10 "$2" auth list </dev/null 2>/dev/null)" || return 1
        [[ -n "$out" && "$out" != *"No authenticated"* ]]
        ;;
    copilot)
        return 2
        ;;
    esac
}

# _agent_session_cli: print the CLI of the agent session this runs in, as ha_actor in output.sh recognises it.
_agent_session_cli() {
    local agent="${AI_AGENT:-}"
    agent="${agent%%_*}"
    agent="$(printf '%s' "$agent" | tr '[:upper:]' '[:lower:]')"
    if [[ " ${AGENT_CLIS[*]} " == *" $agent "* ]]; then
        echo "$agent"
    elif [[ -n "${CLAUDECODE:-}" ]]; then
        echo claude
    fi
}

# _agent_use NAME BIN: make NAME the chosen CLI.
_agent_use() {
    AGENT_NAME="$1"
    AGENT_BIN="$2"
    if [[ "$1" == copilot && -z "${AGENT_MODEL:-}" ]]; then
        AGENT_MODEL="${COPILOT_MODEL:-}"
    fi
}

# agent_resolve [--any] [--other]: set AGENT_NAME and AGENT_BIN, or fail saying what is missing.
#
# AGENT_CLI names one CLI, which must be installed and, unless --any, not known to be signed out. Otherwise, in order:
# the CLI of the agent session this runs in, then the first CLI with a key in the environment, then the first that
# reports being signed in, then one that cannot tell. --any takes the first installed CLI without asking: an
# interactive session lets the user sign in there. --other never takes the CLI of the session this runs in, for a
# second opinion from a different agent.
agent_resolve() {
    local any="" other="" session="" arg i name bin status unknown="" unknown_bin="" installed=() bins=()
    for arg in "$@"; do
        case "$arg" in
        --any) any=1 ;;
        --other) other=1 ;;
        esac
    done
    if [[ -n "$other" ]]; then
        session="$(_agent_session_cli)"
    fi

    if [[ -n "${AGENT_CLI:-}" && "$AGENT_CLI" != auto ]]; then
        if [[ " ${AGENT_CLIS[*]} " != *" $AGENT_CLI "* ]]; then
            echo "AGENT_CLI=$AGENT_CLI is not one of: ${AGENT_CLIS[*]}" >&2
            return 1
        fi
        if [[ -n "$session" && "$AGENT_CLI" == "$session" ]]; then
            echo "AGENT_CLI=$AGENT_CLI is the CLI this session runs in, which --other excludes" >&2
            return 1
        fi
        bin="$(_agent_bin "$AGENT_CLI")"
        if [[ -z "$bin" ]]; then
            echo "AGENT_CLI=$AGENT_CLI, but $AGENT_CLI is not installed" >&2
            return 1
        fi
        if [[ -z "$any" ]]; then
            status=0
            _agent_signed_in "$AGENT_CLI" "$bin" || status=$?
            if [[ $status -eq 1 ]]; then
                echo "AGENT_CLI=$AGENT_CLI, but it is not signed in — $(_agent_login "$AGENT_CLI")" >&2
                return 1
            fi
        fi
        _agent_use "$AGENT_CLI" "$bin"
        return 0
    fi

    if [[ -z "$other" ]]; then
        name="$(_agent_session_cli)"
        if [[ -n "$name" ]] && bin="$(_agent_bin "$name")" && [[ -n "$bin" ]]; then
            _agent_use "$name" "$bin"
            return 0
        fi
    fi

    for name in "${AGENT_CLIS[@]}"; do
        [[ "$name" == "$session" ]] && continue
        bin="$(_agent_bin "$name")"
        [[ -n "$bin" ]] || continue
        if [[ -n "$any" ]] || _agent_has_key "$name"; then
            _agent_use "$name" "$bin"
            return 0
        fi
        installed+=("$name")
        bins+=("$bin")
    done

    for ((i = 0; i < ${#installed[@]}; i++)); do
        status=0
        _agent_signed_in "${installed[$i]}" "${bins[$i]}" || status=$?
        if [[ $status -eq 0 ]]; then
            _agent_use "${installed[$i]}" "${bins[$i]}"
            return 0
        fi
        if [[ $status -eq 2 && -z "$unknown" ]]; then
            unknown="${installed[$i]}"
            unknown_bin="${bins[$i]}"
        fi
    done

    if [[ -n "$unknown" ]]; then
        _agent_use "$unknown" "$unknown_bin"
        return 0
    fi
    if [[ ${#installed[@]} -eq 0 ]]; then
        echo "No coding agent CLI${session:+ other than $session} found — install one of: ${AGENT_CLIS[*]}" >&2
        return 1
    fi
    echo "No agent CLI is signed in. Sign in to one of them:" >&2
    for name in "${installed[@]}"; do
        echo "  $name: $(_agent_login "$name")" >&2
    done
    return 1
}

# _agent_run MODE DIR FILE: send the prompt in FILE through the chosen CLI and print only the agent's answer.
#
# MODE "prompt" runs the CLI in an empty directory (Copilot, which would ask to trust it, with
# --no-custom-instructions instead) and without tools, so it loads none of this repository's agent instructions or
# session hooks. MODE "review" runs it in DIR with its agent instructions and lets it read, but run and write
# nothing: no shell, since git and rg take options that write files or run commands, and for Claude Code none of the
# project's settings or MCP servers, which would widen that. The caller writes the diff into a file in DIR, and
# makes DIR no git checkout, so no session-start hook acts there.
_agent_run() {
    local mode="$1" dir="$2" prompt_file work answer status=0
    prompt_file="$(cd "$(dirname "$3")" && pwd)/$(basename "$3")"
    work="$(mktemp -d)"
    [[ "$mode" == prompt ]] && dir="$work"
    set --
    if [[ -n "${AGENT_MODEL:-}" ]]; then
        set -- --model "$AGENT_MODEL"
    fi
    case "$AGENT_NAME" in
    claude)
        if [[ "$mode" == review ]]; then
            set -- --restricted --strict-mcp-config --setting-sources user --permission-mode dontAsk \
                --tools "Read,Grep,Glob" "$@" --allowedTools Read Grep Glob
        else
            set -- --tools "" "$@"
        fi
        (cd "$dir" && "$AGENT_BIN" --print "$@") <"$prompt_file" || status=$?
        ;;
    codex)
        answer="$work/answer.md"
        (cd "$dir" && "$AGENT_BIN" exec --sandbox read-only --skip-git-repo-check "$@" \
            --output-last-message "$answer" -) <"$prompt_file" >/dev/null || status=$?
        if [[ $status -eq 0 ]]; then
            cat "$answer"
        fi
        ;;
    copilot)
        if [[ "$mode" == review ]]; then
            (cd "$dir" && "$AGENT_BIN" --silent --trust-folder --deny-tool='write' --deny-tool='shell' "$@") \
                <"$prompt_file" || status=$?
        else
            "$AGENT_BIN" --silent --no-custom-instructions --deny-tool='write' --deny-tool='shell' "$@" \
                <"$prompt_file" || status=$?
        fi
        ;;
    opencode)
        (cd "$dir" && "$AGENT_BIN" run --agent plan --archived "$@" --file "$prompt_file" \
            "Follow the instructions in the attached file and reply with nothing else.") || status=$?
        ;;
    esac
    rm -rf "$work"
    return "$status"
}

# agent_prompt FILE: send the prompt in FILE, with no tools and none of this repository's instructions.
agent_prompt() {
    _agent_run prompt "" "$1"
}

# agent_review DIR FILE: run the prompt in FILE inside DIR, reading only, with DIR's agent instructions.
agent_review() {
    _agent_run review "$1" "$2"
}

# agent_session: replace the shell with an interactive session of the chosen CLI.
agent_session() {
    if [[ -n "${AGENT_MODEL:-}" ]]; then
        exec "$AGENT_BIN" --model "$AGENT_MODEL"
    fi
    exec "$AGENT_BIN"
}
