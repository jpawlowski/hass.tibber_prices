# Customization & Extensibility

This document explains how to customize and extend the blueprint without modifying files that are managed by the upstream template.

## Template Sync

Repositories created from this blueprint can receive upstream improvements automatically via a weekly pull request created by the [template sync workflow](../../.github/workflows/template-sync.yml).

### How it works

Every Monday at 07:00 UTC, the workflow checks whether the upstream blueprint (`jpawlowski/hass.tibber_prices`) has new commits. If it does, it opens a pull request with the diff against your repository.

The workflow is configured to update an existing open template-sync PR when possible (force-push + PR edit) instead of closing it and opening a new one each run.

You review the PR and merge anything you want to adopt. Changes you don't want can simply be dismissed or partially merged.

### Prerequisites (important)

This blueprint includes workflow files, and they are intended to sync like other template-managed files.
Updating files under `.github/workflows/` requires extra GitHub permissions (`workflows: write`).
Without that permission, this workflow skips only workflow-file updates for that run and still syncs all other changes.

By default, this blueprint handles that gracefully:

- If `TEMPLATE_SYNC_TARGET_PAT` is **not** configured, the workflow creates a temporary ignore file for that run and skips only `.github/workflows/*` updates. All other file updates are still synced.
- If `TEMPLATE_SYNC_TARGET_PAT` **is** configured, workflow-file updates are included as well.

Make sure the target repository has:

- **Allow GitHub Actions to create and approve pull requests** enabled — [`script/setup/github`](REPOSITORY_SETUP.md) sets it, with the default workflow permissions left at read, since every workflow declares its own
- A repository secret named `TEMPLATE_SYNC_TARGET_PAT` with a PAT that has at least: `contents: write`, `pull requests: write`, `workflows: write`, `metadata: read`

The template sync workflow in this blueprint is already configured to use that secret when present and to fall back to `github.token` otherwise.

### Troubleshooting: workflows permission error

If a sync run fails with an error like:

```text
refusing to allow a GitHub App to create or update workflow
'.github/workflows/<file>.yml' without 'workflows' permission
```

it means the run tried to update workflow files without a token that has `workflows` permission.

You have two options:

1. Configure `TEMPLATE_SYNC_TARGET_PAT` as described above (recommended).
2. Keep running without PAT and let this blueprint skip workflow-file updates automatically.

When skipping happens, the workflow writes a short notice to the run summary so it is visible why workflow-file changes are not part of the sync PR.

### How conflicts are handled

The sync workflow uses `-X theirs` when preparing the PR branch — **the template version always wins** when both you and upstream changed the same file. The PR is always clean and mergeable; there are no conflict markers to resolve.

In practice:

- If a synced file changed both locally and upstream, the PR diff shows your changes being replaced by the template version.
- If you changed a synced file that upstream did not touch, the PR contains nothing for that file — your local changes are unaffected.

Review the PR diff before merging. If it would overwrite something you want to keep, close the PR and manually apply the changes you actually want.

**Versions are the exception.** Where your Dependabot or Renovate raised a pin further than the blueprint has, `-X theirs` would lower it again. After the sync, the workflow runs [`script/template-sync-guard`](../../script/template-sync-guard): it compares every pin the dependency bots raise — the managers and patterns in [`.github/renovate.json`](../../.github/renovate.json), so `mise.toml`, the requirements files, `package.json` (regenerating `package-lock.json` to match), the workflows and the mise version pins — with your default branch, restores each occurrence the sync lowered (a release still replaces its own pre-release), commits the higher version back to the sync branch, and comments the list on the PR. A repository made from the blueprint before this step existed does not get it through the sync, since `template-sync.yml` is excluded; copy the _Keep this repository's newer versions_ step from the blueprint's workflow.

**Blueprint-only files stay out.** Some files only make sense in the blueprint itself, such as `script/import-overlay`,
which imports an existing integration into it. A last step, _Drop blueprint-only files_, runs [`script/prune-blueprint --apply`](../../script/prune-blueprint)
on the sync branch: it removes any of them the sync brought and adds them to `.templatesyncignore`, so they never reach
your `main`. A repository made before this step existed copies it from the blueprint's workflow.

**What the sync cannot bring.** Files in `.templatesyncignore` — `AGENTS.md`, `template-sync.yml`, this documentation — never change through the sync, and some blueprint changes need a step only you can take. Ask your agent to run the `blueprint-update` skill (`/blueprint-update` in Claude Code), or run `script/blueprint-update` yourself: it shows what the blueprint changed in those files since you last went through them, already spelled with your integration's names, and the skill walks through the manual steps one at a time.

### Modifying synced files locally

You can freely modify any synced file. Template sync only affects a file if it changed upstream since the last sync — a file you changed locally but that upstream did not touch is never overwritten.

When the same file changes on both sides, the sync PR replaces your version with the template version. Two strategies:

**Option A — Exclude the file permanently:** Add it to [`.templatesyncignore`](../../.templatesyncignore). The sync workflow then skips it entirely. Use this when you fully own the file's content and don't want upstream changes (for example `requirements.txt` for your integration's dependencies).

**Option B — Handle conflicts case by case:** Review the PR diff before merging. If the PR would overwrite a local change you want to keep, edit the file on the PR branch first — then merge.

**Via GitHub web UI (no command line needed):** Open the PR → _Files changed_ → click `…` next to the file → _Edit file_. The online editor opens on the PR branch. Blend in the upstream changes you want, keep what you want to preserve, and commit directly to the PR branch. Then merge the PR as normal.

**Via VS Code:** Check out the PR branch with `gh pr checkout <number>`, open the file in VS Code, edit to blend the changes, commit, and merge.

**After an accidental merge (recovery):** If you merged before reviewing and lost a local change, you can restore it from the commit before the merge:

```bash
git show HEAD~1:path/to/your-file.ext > path/to/your-file.ext
git commit -m "chore: restore local changes after template sync"
```

> [!TIP]
> If you find yourself editing the same file after every sync PR, switch to Option A and add it to `.templatesyncignore`.

### Excluding files from sync

Files listed in [`.templatesyncignore`](../../.templatesyncignore) are never touched by the sync PR, even if they changed upstream.

The syntax follows `.gitignore` glob patterns. To exclude an additional file or directory, add a line:

```text
# My integration-specific overrides
config/
path/to/my-file.json
```

Files already excluded by default:

| Path                                                                                    | Reason                                                                   |
| --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `custom_components/`                                                                    | Your integration code                                                    |
| `tests/`                                                                                | Test files reference your domain (set by `initialize.sh`)                |
| `pyproject.toml`                                                                        | Your package metadata and tool settings                                  |
| `requirements.txt`                                                                      | Your integration's PyPI dependencies (managed alongside `manifest.json`) |
| `.vscode/launch.json`, `.vscode/tasks.json`                                             | Your own debug configurations and tasks                                  |
| `README.md`, `LICENSE`, etc.                                                            | Replaced by `initialize.sh`                                              |
| `AGENTS.md`, `CLAUDE.md`                                                                | Contain domain-specific references                                       |
| `AI_POLICY.md`, `.github/pull_request_template.md`                                      | Project-specific governance and contribution process                     |
| `.github/CODEOWNERS`, `.github/FUNDING.yml`, `.github/COPILOT_CODING_AGENT.md`          | Per-project GitHub settings                                              |
| `config/`                                                                               | Local HA instance (credentials, test data)                               |
| `docs/`                                                                                 | Your project documentation                                               |
| `script/hooks/`, `.devcontainer/hooks/`                                                 | Your hook scripts                                                        |
| `.devcontainer/project-feature/`                                                        | Your project's dev container additions, such as required extensions      |
| `.devcontainer/.env`                                                                    | Your HA_VERSION pin and DevContainer settings                            |
| `release-please-config.json`, `.release-please-manifest.json`, `.github/release-notes/` | Release management, release header and footer, release notes prompt      |
| `.github/workflows/template-sync.yml`                                                   | Sync workflow itself                                                     |
| `uv.lock`                                                                               | Your pinned dependency lockfile                                          |

> [!TIP]
> If a file keeps causing conflicts in every sync PR, add it to `.templatesyncignore` instead of resolving the conflict every week.

### Staying on an older Home Assistant version

The blueprint tracks the current Home Assistant release, so a sync PR can raise the version your tooling targets. Your integration code and `hacs.json` are never synced, which means your minimum Home Assistant version only changes when you change it.

`requirements_test.txt` is synced, and `pytest-homeassistant` in it is tied to one Home Assistant release. If your integration stays on an older release, the pinned plugin no longer matches your `hacs.json`, tests fail, and `script/ha-version-sync` reports a mismatch. To keep control of the pin, add the file to `.templatesyncignore` and set the plugin to the release matching your minimum version:

```text
requirements_test.txt
```

`pytest-homeassistant` starts at Home Assistant 2026.11. Below that, keep its predecessor `pytest-homeassistant-custom-component` (its last release, 0.13.375, matches 2026.10) and the `pytest_homeassistant_custom_component` imports in your tests; `script/ha-version-sync` checks either. The synced skills and instructions describe the 2026.11 APIs, and some of them break an older Home Assistant: return `True` from `async_setup_entry`, `async_unload_entry` and `async_migrate_entry` instead of nothing, unload with `async_unload_platforms`, and keep the climate and water heater temperature names without the `native_` prefix. The installed Home Assistant source decides ([`ha-modern-apis`](../../.agents/skills/ha-modern-apis/SKILL.md)).

Moving up later needs the minimum in `hacs.json` and the plugin pin raised together. Since Home Assistant 2026.9, schemas use `probatio` instead of `voluptuous`. Existing `import voluptuous as vol` code keeps working at runtime because Home Assistant aliases it, and only the type checker complains. Switching to `import probatio` is optional, and it is only needed for probatio-only features such as dataclass schemas.

### Opting out of template sync entirely

If you don't want automatic update PRs at all, simply delete the two files:

```bash
rm .github/workflows/template-sync.yml
rm .templatesyncignore
```

That's it. No workflow runs, no PRs, no noise. You can still pull upstream changes manually at any time by comparing your repository against `jpawlowski/hass.tibber_prices`.

---

## Hook Scripts

Every development script supports **pre** and **post** hook scripts. Hooks are plain shell scripts that are sourced into the calling script's environment, so they can read and set variables, call functions already defined in the script, and produce output using the same formatting helpers.

### Where hooks live

```text
script/hooks/          # Hooks for scripts in script/
├── lint.pre.sh        # Runs before script/lint
├── lint.post.sh       # Runs after script/lint
├── test.pre.sh        # Runs before script/test
├── test.post.sh       # Runs after script/test
├── setup/
│   ├── bootstrap.pre.sh
│   ├── bootstrap.post.sh
│   └── ...
└── ...

.devcontainer/hooks/   # Hooks for .devcontainer/ scripts
├── setup-shell.pre.sh
├── setup-shell.post.sh
├── setup-git.pre.sh
├── setup-git.post.sh
└── post-attach.post.sh
```

Both directories are listed in `.templatesyncignore` and are never touched by template sync.

### Writing a hook

The naming convention, the complete table of every available pre/post hook, worked examples, and the rules that apply
to sourced scripts are maintained as an agent skill reference so that humans and AI agents work from the same source:

📖 [`.agents/skills/blueprint-tooling/references/hooks.md`](../../.agents/skills/blueprint-tooling/references/hooks.md)

Use hooks instead of editing the scripts themselves — the scripts are template-managed and will be overwritten by
template sync, the hook directories never are.

---

## Environment Variables

The devcontainer setup can be customized through environment variable files without modifying `devcontainer.json`.

### Two-layer system

| File                       | Committed          | Purpose                                              |
| -------------------------- | ------------------ | ---------------------------------------------------- |
| `.devcontainer/.env`       | ✅ Yes             | Project-level defaults, shared with all contributors |
| `.devcontainer/.env.local` | ❌ No (gitignored) | Personal overrides, never affects others             |

Values in `.env.local` always win over `.env`. Both files use standard shell variable syntax:

```bash
HA_VERSION=beta
HA_INSTALL_HACS=1
APT_UPDATE=0
```

A new terminal picks up a change, since the shell setup loads both files. Variables that steer the setup itself,
such as `HA_VERSION` and `HA_ENVS`, take effect with the next `script/setup/bootstrap`.

### Available variables

| Variable          | Default   | Description                                                                                                                                                         |
| ----------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HA_VERSION`      | `minimum` | `latest` or `beta`: the environment bootstrap builds and activates instead of `minimum`. One particular release is pinned by hand: `script/ha-env add custom`.      |
| `HA_ENVS`         | `minimum` | Home Assistant environments bootstrap installs, e.g. `minimum latest beta` — see [Testing against a newer Home Assistant](#testing-against-a-newer-home-assistant). |
| `HA_INSTALL_HACS` | `1`       | Set to `0` to skip HACS installation (speeds up first-time setup). Ignored from Home Assistant 2026.11, which ships HACS as the built-in Marketplace.               |
| `APT_UPDATE`      | `0`       | Set to `1` to run `apt-get update && apt-get upgrade` during setup.                                                                                                 |

### Scope limitations

These files are sourced by lifecycle hook scripts (`onCreateCommand`, `postCreateCommand`, etc.) and written into the shell RC files so interactive terminals also see the values. They are **not** available to:

- **DevContainer features** — features are installed during image build, before the container starts
- **`containerEnv`** — set independently by the Docker runtime

For feature versions (Python, Node.js) or Python runtime flags (`PYTHONASYNCIODEBUG` etc.), edit `devcontainer.json` directly.

Scripts under `script/` are also outside this scope — they read the **process** environment and never source these
files. Variables that steer them belong in a hook script (see [Hook Scripts](#hook-scripts)):

| Variable            | Default                 | Description                                                                                |
| ------------------- | ----------------------- | ------------------------------------------------------------------------------------------ |
| `HA_DEV_TOKEN`      | `1`                     | Set to `0` so `script/develop` does not mint the access token `script/ha` uses.            |
| `HA_DEV_TOKEN_DAYS` | `30`                    | Lifetime of that token in days. It is rotated automatically once fewer than 7 days remain. |
| `HA_URL`            | `http://127.0.0.1:8123` | Which instance `script/ha` talks to.                                                       |
| `HA_TOKEN`          | the seeded token file   | Authenticate `script/ha` as someone else, e.g. against a real installation.                |

```bash
# script/hooks/develop.pre.sh
export HA_DEV_TOKEN=0
```

The token itself lives in `config/.storage/dev_access_token` (mode `0600`), next to the Home Assistant auth store it
belongs to — gitignored, excluded from template sync, and removed by `script/setup/reset` along with that store.
`script/setup/seed-auth --revoke` removes it and its refresh token; `--force` rotates it. Both require Home Assistant
to be stopped.

### Personal overrides

Copy the example file and uncomment what you need:

```bash
cp .devcontainer/.env.local.example .devcontainer/.env.local
```

`.env.local` is gitignored and listed in `.templatesyncignore` — it is never committed and never touched by template sync.

### Testing against a newer Home Assistant

`hacs.json` is the minimum your users need, and by default the dev environment installs exactly that, so tests prove
the minimum works. To develop and test on a newer release without raising it, add another Home Assistant environment
next to it — `latest` (the newest stable release) or `beta` (the newest pre-release) — and switch between them:

```bash
script/ha-env add beta       # install it once; a few minutes, and disk for its own packages
script/ha-env use beta       # switch; seconds
script/test                  # runs against the beta now, as does script/develop
script/ha-env use minimum    # back
script/ha-env refresh        # move every installed environment to its newest version
script/ha-env remove beta    # free the disk again
script/ha-env list           # what is installed and active, and who started a running instance
```

In dev container terminals `ha-env` (or `ha-e`) runs `script/ha-env` from anywhere. `script/develop --env beta`
switches and starts in one step, and VS Code has the same as tasks. Each environment keeps
its kind: `beta` only ever holds a pre-release, even while the newest one is older than `latest`, and `latest` only a
stable release. Each one gets the `pytest-homeassistant` release of its version, so the test fixtures always match
the Home Assistant they run against; `requirements_test.txt` and `hacs.json` stay as they are. Each one also runs on the Python
version its Home Assistant release ships with, so a beta that already needs the next Python works next to a minimum.

- **Config:** `minimum` runs from `config/`. Every other environment runs from `.local/ha-config/<name>/`, which links
  `configuration.yaml` and the other shared files from `config/` but keeps its own `.storage`, database and log, since a
  newer Home Assistant migrates `.storage` in a way an older one may not read. A new one starts from the state in
  `config/` when its version can migrate that forward.
- **Prompt:** dev container terminals show the active environment, such as `(ha-beta 2026.12.0b2)`, follow a switch at
  their next prompt, and say who switched when it was not them.
- **Safety:** `script/ha-env use` and `script/develop --env` refuse to switch while Home Assistant runs, unless you pass
  `--force`. The VS Code task passes it, since you start it yourself, like plain `script/develop`. Neither a refresh
  nor `script/setup/bootstrap` changes the environment a running instance uses.
- **Reset:** `script/setup/reset` starts the active environment over: `config/` for `minimum`, otherwise its own
  directory, which then starts empty instead of from `config/`; `--full` restores `configuration.yaml` from git only
  for `minimum`, since the others share it.
- **Staleness:** `script/ha-env list`, `script/develop` and `script/test` remind you when `latest` or `beta` was last
  refreshed over a week ago — Home Assistant ships a beta a week — or when `minimum` no longer matches `hacs.json`.

To have `latest` and `beta` installed on every container create, set `HA_ENVS` in `.devcontainer/.env.local`:

```bash
HA_ENVS="minimum latest beta"
```

To reproduce a problem in one particular release, pin it as the environment `custom`. Unlike `latest` and `beta` it
is a fixed point: `refresh` keeps its version and only reinstalls when the requirements files change, and bootstrap
leaves it alone.

```bash
script/ha-env add custom 2026.11.1     # build and pin; any release from the hacs.json minimum on, pre-releases too
script/ha-env use custom
script/ha-env add custom 2026.12.0b3   # move the pin, up or down
script/ha-env remove custom
```

Each version is built in its own venv on the Python its release asks for, so moving the pin down to a release that
needs an older Python works, and the version it replaces is removed once no other environment uses it. Its config directory is
`.local/ha-config/custom/`; when a lower version starts on state a higher one already migrated, `script/develop` moves
`.storage` and the database aside first. `custom` is for one investigation at a time, so it is only pinned by hand:
neither `HA_ENVS` nor `HA_VERSION` sets it.

Code written this way must still run on the minimum: use only what the minimum version offers, and let the newer one
show you the deprecations coming. The _Newer Home Assistant_ workflow does the same in CI — against the newest stable
and beta release, whenever one is newer than the pin, without blocking a pull request.

---

## VS Code Settings Overrides

The blueprint ships with `.vscode/settings.default.jsonc` as the shared baseline for workspace settings.

If you want personal or project-local overrides without changing the devcontainer definition, copy it once to
`.vscode/settings.json` and edit only what you want to override:

```bash
cp .vscode/settings.default.jsonc .vscode/settings.json
```

How this works in practice:

- `settings.default.jsonc` stays template-managed and documents the recommended defaults.
- `settings.json` is your override layer (for example different formatter behavior, Python path, or terminal profile).
- This lets you customize editor behavior without having to modify `.devcontainer/devcontainer.json` for most cases.

### Git and template sync behavior

`settings.json` is already ignored by Git via `.gitignore` (`.vscode/*` with explicit allowlist for selected files), so it is not committed by default.

You do **not** need to add `.vscode/settings.json` to `.templatesyncignore`:

- Template sync only operates on tracked files in the repository.
- Your local `settings.json` remains an untracked personal file and will not be deleted by template sync.

If you intentionally want to share a tracked workspace settings file with collaborators, use `settings.default.jsonc` for that purpose.

### Recommended and required extensions

When your project settles on one AI agent ([`AI_AGENTS.md`](AI_AGENTS.md#editor-extensions)), there are two places
for its extension:

- **Recommend only it** by removing the other agents from `.vscode/extensions.json`. VS Code offers it when the
  repository is opened, and contributors can decline. The file is template-managed, so add it to
  `.templatesyncignore` at the same time (see [Modifying synced files locally](#modifying-synced-files-locally)).
- **Require it** in `.devcontainer/project-feature/devcontainer-feature.json`, under
  `customizations.vscode.extensions`. The dev container installs it for everyone on the next rebuild, alongside the
  extensions from `devcontainer.json`. The directory is listed in `.templatesyncignore`, so your entries stay yours;
  a repository created before it existed adds the entry with `./script/prune-blueprint --apply`.

```json
"customizations": {
  "vscode": {
    "extensions": ["anthropic.claude-code"]
  }
}
```

---

## Python Dependencies

### Integration runtime dependencies (`requirements.txt`)

`manifest.json → requirements` is the authoritative list — Home Assistant reads it at runtime and installs those packages automatically. `requirements.txt` exists solely as a development mirror of the same packages, so tools like type-checkers, pytest, and your IDE can resolve imports without running Home Assistant.

Both files must be kept in sync by hand. This is by HA design and is unavoidable. The step-by-step procedure for adding
a dependency — including how to decide whether a third-party library is worth taking on — lives in the
[`blueprint-tooling`](../../.agents/skills/blueprint-tooling/SKILL.md) skill.

`requirements.txt` is **excluded from template sync** because it is integration-specific content.

```text
# requirements.txt
my-device-library>=1.2.0
aiohttp>=3.9.0
```

> [!NOTE]
> `requirements_dev.txt` and `requirements_test.txt` **are** synced from the blueprint — they contain shared tooling dependencies. Add only integration runtime packages to `requirements.txt`.

### Personal extra packages (`requirements.local.txt`)

For personal or machine-specific packages that should not be committed, create a `requirements.local.txt` in the project root. It is gitignored and never committed. Common uses: debugging tools (`ipdb`, `icecream`), profilers, private packages, or additional dev/test packages beyond what `requirements_dev.txt` and `requirements_test.txt` provide.

```text
# requirements.local.txt — gitignored, never committed
ipdb
pytest-sugar
my-private-package @ git+https://github.com/me/my-package.git
```

`script/setup/bootstrap` automatically installs it after `requirements.txt` if the file exists.

| File                     | Template sync  | Purpose                                        |
| ------------------------ | -------------- | ---------------------------------------------- |
| `requirements.txt`       | ❌ Excluded    | Your integration's runtime dependencies        |
| `requirements_dev.txt`   | ✅ Synced      | Development tool dependencies (shared)         |
| `requirements_test.txt`  | ✅ Synced      | Test dependencies (shared)                     |
| `requirements.local.txt` | — (gitignored) | Your personal extra packages (never committed) |
