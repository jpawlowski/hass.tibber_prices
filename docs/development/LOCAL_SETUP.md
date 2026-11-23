# Working without the dev container

The dev container is the quickest way in, not a requirement. The same scripts run on your own machine and in the
cloud sessions of coding agents, with the same tool versions, because `mise.toml` pins them for every environment.

## On your own machine

**You need** git, bash, Node.js (any current LTS) and [mise](https://mise.jdx.dev/getting-started.html). The scripts
are written for Linux and macOS; on Windows, work inside WSL2. Without mise the scripts fall back to whatever tools are on your `PATH`, which
works as long as their versions happen to fit.

```bash
script/setup/bootstrap   # mise's tools, a venv with Home Assistant and the test dependencies, the git hooks
script/develop           # Home Assistant at http://localhost:8123
```

`bootstrap` takes several minutes the first time; running it again only updates what changed. The venv lives in
`.local/ha-venv` in the checkout, linked as `.venv`, and `mise.toml` names it, so every script — and any shell that runs
`mise env` — gets its Python ahead of mise's own. Activating mise in your shell (`mise activate`) is optional: the
scripts apply it themselves.

`.local/ha-venv` always is the active Home Assistant environment: by default the minimum version from `hacs.json`.
`script/ha-env` adds and switches to the newest stable or beta release next to it —
[Testing against a newer Home Assistant](CUSTOMIZATION.md#testing-against-a-newer-home-assistant).

**Tools of your own** go in `mise.local.toml`, which git ignores. Tools the integration itself needs go in
`.config/mise/conf.d/project.toml`, which the template sync leaves alone; `mise.toml` belongs to the blueprint.

### What only the dev container has

| In the dev container                                                                    | On your own machine                                                                                                          |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Terminal tools from `mise.devcontainer.toml` (`bat`, `fzf`, `just`, …)                  | Install them yourself, or load the file with `MISE_ENV=devcontainer`                                                         |
| System libraries some Home Assistant wheels build against (`libturbojpeg`, `ffmpeg`, …) | Your package manager, when an install asks for one                                                                           |
| The agent CLIs (Claude Code, Codex, OpenCode, Copilot)                                  | Install the ones you use                                                                                                     |
| Managed agent settings in `/etc` (`bypassPermissions` for Claude Code)                  | The committed `.claude/settings.json` and `opencode.json` protect the same paths, with the agent asking before other actions |

## With a coding agent

When a session starts, `.agents/hooks/session-start.sh` prepares the checkout — Claude Code and Copilot run it through
`.claude/settings.json`, Codex through `.codex/hooks.json`, OpenCode through its plugin. Nothing slow happens in front of
the session; long work runs in the background and reports in `.local/<script>.status` and `.local/<script>.log`.

- **On your machine** it checks the pinned tools and tells the agent when the checkout still needs
  `script/setup/bootstrap`. It never installs mise there.
- **In a Claude Code cloud session** it installs mise and runs `script/setup/bootstrap` in the background. Nothing has
  to be configured in the cloud environment; wait for `.local/bootstrap.status` to read `done` before running tests.
- **In Codex cloud**, Codex builds the environment from the repository. `AGENTS.md` names the install command it
  should record: `script/setup/toolchain --install-mise && script/setup/bootstrap`.

The Claude desktop app can open Home Assistant in its browser pane (`.claude/launch.json` starts `script/develop`).
Cloud sessions have no such preview; there, `script/ha` is how an agent looks at the running instance.

## Keeping it current

After a pull that changed `mise.toml` or the requirements, run `script/setup/bootstrap` again. Agents' sessions check
the tools on their own; the venv is only rebuilt when Home Assistant's version changes.
