# Hook scripts

Every development script in this repository supports **pre** and **post** hooks. Hooks are plain shell scripts that are
_sourced_ into the calling script's environment, so they can read and set its variables, call functions it has already
defined, and use the same output helpers (`log_header`, `log_success`, `log_error`).

Both hook directories are listed in `.templatesyncignore` and are never touched by template sync — they are the
supported extension point for project-specific behaviour.

## Naming convention

```text
script/hooks/<script-name>.<phase>.sh          # hooks for scripts in script/
.devcontainer/hooks/<script-name>.<phase>.sh   # hooks for .devcontainer/ scripts
```

- `<script-name>` mirrors the script path relative to `script/` — `setup/bootstrap` for `script/setup/bootstrap`.
- `<phase>` is `pre` or `post`.
- A missing hook file is silently ignored.

## Writing a hook

```bash
# script/hooks/setup/bootstrap.post.sh
log_header "Installing project-specific tools"
uv pip install -q some-extra-tool
log_success "Extra tools installed"
```

```bash
# script/hooks/lint.post.sh
if command -v my-custom-linter >/dev/null 2>&1; then
    log_header "Running custom linter"
    my-custom-linter custom_components/
fi
```

```bash
# script/hooks/test.pre.sh
export MY_DEVICE_API_KEY="test-key-123"
export MY_DEVICE_HOST="localhost"
```

```bash
# script/hooks/develop.pre.sh
# Opt out of the script/ha development token, or shorten its life.
export HA_DEV_TOKEN=0        # no token is minted at all
# export HA_DEV_TOKEN_DAYS=1 # or keep it, expiring after a day
```

Scripts under `script/` read the process environment and never source `.devcontainer/.env`, so a hook is the only
place their variables can be set.

Rules:

- Hooks are **sourced**, not executed — `exit` would terminate the calling script. Use `return`.
- Do not `set -e` inside a hook; you inherit the caller's settings.
- Hooks in `script/hooks/` are covered by `script/shell-check`. Hooks in `.devcontainer/hooks/` are **not** validated —
  write them carefully.
- Keep hooks fast. `pre` hooks run on every invocation of the script they attach to.

## Available hooks

| Script                            | pre hook                                     | post hook                                     |
| --------------------------------- | -------------------------------------------- | --------------------------------------------- |
| `script/architecture-check`       | `script/hooks/architecture-check.pre.sh`     | `script/hooks/architecture-check.post.sh`     |
| `script/build`                    | `script/hooks/build.pre.sh`                  | `script/hooks/build.post.sh`                  |
| `script/check`                    | `script/hooks/check.pre.sh`                  | `script/hooks/check.post.sh`                  |
| `script/clean`                    | `script/hooks/clean.pre.sh`                  | `script/hooks/clean.post.sh`                  |
| `script/decisions`                | `script/hooks/decisions.pre.sh`              | `script/hooks/decisions.post.sh`              |
| `script/develop`                  | `script/hooks/develop.pre.sh`                | — (long-running process)                      |
| `script/ha`                       | `script/hooks/ha.pre.sh`                     | `script/hooks/ha.post.sh`                     |
| `script/hassfest`                 | `script/hooks/hassfest.pre.sh`               | `script/hooks/hassfest.post.sh`               |
| `script/help`                     | `script/hooks/help.pre.sh`                   | `script/hooks/help.post.sh`                   |
| `script/lint`                     | `script/hooks/lint.pre.sh`                   | `script/hooks/lint.post.sh`                   |
| `script/lint-check`               | `script/hooks/lint-check.pre.sh`             | `script/hooks/lint-check.post.sh`             |
| `script/markdown`                 | `script/hooks/markdown.pre.sh`               | `script/hooks/markdown.post.sh`               |
| `script/push-gate`                | `script/hooks/push-gate.pre.sh`              | `script/hooks/push-gate.post.sh`              |
| `script/markdown-check`           | `script/hooks/markdown-check.pre.sh`         | `script/hooks/markdown-check.post.sh`         |
| `script/python`                   | `script/hooks/python.pre.sh`                 | `script/hooks/python.post.sh`                 |
| `script/python-check`             | `script/hooks/python-check.pre.sh`           | `script/hooks/python-check.post.sh`           |
| `script/release-notes`            | `script/hooks/release-notes.pre.sh`          | `script/hooks/release-notes.post.sh`          |
| `script/second-review`            | `script/hooks/second-review.pre.sh`          | `script/hooks/second-review.post.sh`          |
| `script/shell`                    | `script/hooks/shell.pre.sh`                  | `script/hooks/shell.post.sh`                  |
| `script/shell-check`              | `script/hooks/shell-check.pre.sh`            | `script/hooks/shell-check.post.sh`            |
| `script/spell`                    | `script/hooks/spell.pre.sh`                  | `script/hooks/spell.post.sh`                  |
| `script/spell-check`              | `script/hooks/spell-check.pre.sh`            | `script/hooks/spell-check.post.sh`            |
| `script/test`                     | `script/hooks/test.pre.sh`                   | `script/hooks/test.post.sh`                   |
| `script/type-check`               | `script/hooks/type-check.pre.sh`             | `script/hooks/type-check.post.sh`             |
| `script/version`                  | `script/hooks/version.pre.sh`                | `script/hooks/version.post.sh`                |
| `script/yaml-check`               | `script/hooks/yaml-check.pre.sh`             | `script/hooks/yaml-check.post.sh`             |
| `script/setup/bootstrap`          | `script/hooks/setup/bootstrap.pre.sh`        | `script/hooks/setup/bootstrap.post.sh`        |
| `script/setup/reset`              | `script/hooks/setup/reset.pre.sh`            | `script/hooks/setup/reset.post.sh`            |
| `script/setup/seed-auth`          | `script/hooks/setup/seed-auth.pre.sh`        | `script/hooks/setup/seed-auth.post.sh`        |
| `script/setup/seed-http-config`   | `script/hooks/setup/seed-http-config.pre.sh` | `script/hooks/setup/seed-http-config.post.sh` |
| `script/setup/setup`              | — (calls bootstrap)                          | `script/hooks/setup/setup.post.sh`            |
| `script/setup/sync-hacs`          | `script/hooks/setup/sync-hacs.pre.sh`        | `script/hooks/setup/sync-hacs.post.sh`        |
| `.devcontainer/on-create.sh`      | `.devcontainer/hooks/on-create.pre.sh`       | `.devcontainer/hooks/on-create.post.sh`       |
| `.devcontainer/update-content.sh` | `.devcontainer/hooks/update-content.pre.sh`  | `.devcontainer/hooks/update-content.post.sh`  |
| `.devcontainer/post-create.sh`    | `.devcontainer/hooks/post-create.pre.sh`     | `.devcontainer/hooks/post-create.post.sh`     |
| `.devcontainer/post-start.sh`     | `.devcontainer/hooks/post-start.pre.sh`      | `.devcontainer/hooks/post-start.post.sh`      |
| `.devcontainer/setup-shell.sh`    | `.devcontainer/hooks/setup-shell.pre.sh`     | `.devcontainer/hooks/setup-shell.post.sh`     |
| `.devcontainer/setup-git.sh`      | `.devcontainer/hooks/setup-git.pre.sh`       | `.devcontainer/hooks/setup-git.post.sh`       |
| `.devcontainer/post-attach.sh`    | `.devcontainer/hooks/post-attach.pre.sh`     | `.devcontainer/hooks/post-attach.post.sh`     |

A hook is the wrong place to change the release notes prompt: what the notes should know about the integration goes into
`.github/release-notes/prompt.md` ([`ha-release`](../../ha-release/SKILL.md)).

## The build hook

`script/build` empties `$BUILD_DIR`, runs `build.pre.sh`, copies the tracked files of the integration over it, runs
`build.post.sh`, checks the result and packs the release ZIP. A hook adds what is generated rather than committed — a
bundled card, a data file — by writing into `$BUILD_DIR`, an absolute path to the integration folder as it ships:

```bash
# script/hooks/build.post.sh
log_step "Bundling the cards"
npm --prefix frontend ci --silent
npm --prefix frontend run build -- --outfile "$BUILD_DIR/frontend/cards.js"
```

- The release job sets up mise only when a build hook exists; put the tools the hook needs into
  `.config/mise/conf.d/project.toml`, never into the workflow.
- `script/build --in-place` runs the hooks on `custom_components/<domain>/` itself, so `script/develop` sees the
  generated files. Ignore them in `custom_components/.gitignore`.
- Generate only additions. `manifest.json`, translations, `services.yaml` and Python modules stay committed: hassfest,
  the HACS action and the tests check the repository, not the ZIP.
- `script/build` alone previews what a release ships, in `.local/build/<domain>/`.
