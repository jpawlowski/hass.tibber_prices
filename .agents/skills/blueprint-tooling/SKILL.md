---
name: blueprint-tooling
description: >-
  Use this repository's development tooling correctly — the script/ validation and formatting commands, the
  fix-versus-check distinction, hassfest, adding a Python dependency in both manifest.json and requirements.txt,
  the mise toolchain and which dependency bot raises what, extending scripts with pre/post hook scripts, devcontainer environment variables, and template sync from the
  upstream blueprint. Use when asked to "run the checks", "fix the lint errors", "why is CI failing", "add a
  dependency", "add a package", "add a tool", "update mise", "add a hook", "customize the setup", "exclude a file from template sync", or when
  a validation command fails and you need to know which script to reach for. SYMPTOMS — load this if you are about
  to: run `ruff`, `pyright`, `pytest`, or `hass` directly instead of the project script; run a `-check` script
  after a fix script; add a dependency to only one of `manifest.json` and `requirements.txt`; or edit a
  template-managed script instead of adding a hook.
---

# Repository tooling

## Rule zero: use the project scripts

Never craft your own `hass`, `pip`, `pytest`, `ruff`, or `pyright` invocation. The scripts activate the right virtual
environment, set `PYTHONPATH`, manage ports and processes, and run hooks. Agents that bypass them break in ways that
look like code bugs.

## Which script to run

Pick the narrowest one that covers what you changed:

| Changed files                            | Run                                   |
| ---------------------------------------- | ------------------------------------- |
| `*.py` only                              | `script/python` + `script/type-check` |
| `*.yaml` / `*.yml` only                  | `script/yaml-check`                   |
| `*.md` only                              | `script/markdown`                     |
| `script/` or `.devcontainer/*.sh` only   | `script/shell` + `script/shell-check` |
| Multiple types, or unsure                | `script/lint` + `script/type-check`   |
| Integration metadata, translations, YAML | `script/hassfest`                     |

### Fix mode vs. check mode

**Fix-mode scripts auto-heal files _and_ print what they could not fix.** Their output is the complete picture — there
is no need to run the matching `-check` script afterwards.

```bash
# Loop until both exit 0:
script/lint         # formats Python, shell, markdown; checks yaml + shellcheck; reports the rest
script/type-check   # pyright — never auto-fixes, always a manual loop
```

| Fix mode          | Check mode (read-only, for CI)                                                                                  |
| ----------------- | --------------------------------------------------------------------------------------------------------------- |
| `script/lint`     | `script/lint-check`                                                                                             |
| `script/python`   | `script/python-check`                                                                                           |
| `script/shell`    | `script/shell-check`                                                                                            |
| `script/markdown` | `script/markdown-check`                                                                                         |
| `script/spell`    | `script/spell-check`                                                                                            |
| —                 | `script/check` (type-check + lint-check + spell-check), `script/yaml-check`, `script/type-check`, `script/test` |

Agents should use fix mode. `script/check` is the gate to run before saying a task is complete.

**For `script/test`, redirect its output to a log and judge it by exit code instead of streaming it into context** —
`script/test > test.log 2>&1`, then read the log, and only the failing part, if the exit code is non-zero. A green
run costs a handful of tokens instead of the whole suite's output. `script/lint`/`script/type-check` already report
concisely by design, so this only matters for `script/test`, the one command here with potentially large output.

### Other scripts

```bash
script/develop           # take over Home Assistant on :8123, debugpy on :5678 (see below)
script/ha                # query and control the running instance (see below)
script/ha-env            # Home Assistant environments: list, add/remove latest, beta or a pinned custom, use one, refresh
script/setup/seed-auth   # mint the token script/ha uses — run by script/develop
script/hassfest          # official HA validation (first run downloads ~27 MB)
script/test              # integration tests plus synchronized tooling tests
script/skills-check      # validate .agents/skills/ and agent protected paths (also part of lint / lint-check)
script/architecture-check # conservative architecture guardrails (also part of lint / lint-check) — see below
script/push-gate         # git's pre-push hook: clean HEAD only, then lint-check + type-check in parallel
script/version           # read the canonical version from manifest.json
script/second-review     # a review by another agent CLI than this session's — see haci-change-review (--brief: its reviewer brief)
script/build             # build the integration as it ships (--zip, --in-place); hook: build.post.sh
script/decisions         # write (--check: verify) the decision record index (also part of lint / lint-check)
script/ha-version-sync   # align the pinned Home Assistant version across config files, and mise's Python with it
script/setup/toolchain   # install the tools mise.toml pins (--install-mise: mise itself too) — run by bootstrap
script/setup/agent-plugins # install the haci plugins at the tag .claude/settings.json pins (--check: the 3 agents agree)
script/setup/github      # apply the GitHub settings and .github/rulesets/ (--dry-run first) — see REPOSITORY_SETUP.md
script/secret-scan       # betterleaks over --staged changes (the commit hook), a --range, or --all of the history
script/clean             # remove caches, logs, build artifacts
script/prune-blueprint   # list (--apply: remove) blueprint-only leftovers; ignore them and project-owned paths in .templatesyncignore
script/help              # list every script with its description
```

`script/develop` is a **takeover**, not a "start if needed" — the run-loop rules, and why, are in
[`ha-coordinator-debug`](../ha-coordinator-debug/SKILL.md).

**HACS validation has no local script.** The `hacs` job in `.github/workflows/validate.yml` runs the
[HACS action](https://github.com/hacs/action) in CI only. It skips itself with a notice on a private repository,
which the action cannot read, and adds `ignore: brands` with a warning while `brand/icon.png` is missing — so a green
job proves less than it looks. What it checks, and why `ignore` is never the fix:
[`ha-marketplace`](../ha-marketplace/SKILL.md).

### architecture-check vs. tests/

`script/architecture-check` enforces a handful of AGENTS.md rules that are source-pattern violations rather than
runtime behaviour: `EntityDescription` hardcoding `name=`/`icon=` instead of `translation_key`, a banned
`device_trigger.py`/`device_condition.py`/`device_action.py` file, an unscoped `async_get_device()` call. It resolves
tracked and untracked, non-ignored integration files with `git ls-files`, not a hardcoded domain, so the same script
runs unmodified in the template repository and in initialized integrations. It follows common import aliases, local
subclasses, literal dictionary unpacking, and known `DeviceRegistry` receivers. General `**kwargs`, factories, and
values assembled through arbitrary data flow remain review concerns; this is a conservative guardrail, not a proof.

That is deliberately not where `tests/` lives: `tests/` is fully excluded from template sync (its imports are tied to
one integration's domain, substituted once by `initialize.sh`), so a regression test shipped there is a one-time
snapshot after a repository has been initialized. The checker and its own tests instead live under synchronized
`script/`; `script/test` collects `script/tests/` alongside the integration suite. Template-sync proposes later
checker fixes in a pull request, which still needs maintainer review and merge.

Runtime-behaviour tests — does a loaded entry actually own one device, does a service call actually raise — belong in
`tests/`. Not every prose rule in AGENTS.md is a good static check: anything that cannot be identified with a low
false-positive rate is safer left as a rule an agent and reviewer apply.

### Talking to the running instance

`script/ha` reads entity states, config entry status, diagnostics, and the error log from the instance
`script/develop` started, calls service actions, and drives config flows — so debugging does not require reading a log
file and asking a human to click through the UI.

Authentication is automatic: `script/develop` runs `script/setup/seed-auth`, which mints a long-lived access token
offline into `config/.storage/dev_access_token`. `script/ha` reads that file itself, so **the token never appears in a
command line or in output**. On a fresh environment the instance has to be onboarded in the browser once; the token
then appears on the next `script/develop`. Every command with its options: [`references/ha-cli.md`](references/ha-cli.md).

### When a check keeps failing

1. Fix the specific error the tool reported.
2. If it fails again, question your understanding rather than repeating the same edit.
3. After three attempts, stop and explain what you tried and what the tool said.

`# noqa: CODE` and `# type: ignore[code]` are allowed for genuine false positives or third-party gaps — always with a
specific code, never bare, and sparingly.

## Adding a Python dependency

The integration's runtime dependencies live in **two** places that must be kept in sync by hand. This is a Home
Assistant design constraint, not a repository quirk.

1. `custom_components/<domain>/manifest.json` → `requirements` — the authoritative list. Home Assistant
   reads it and installs the packages for end users.
2. `requirements.txt` at the repository root — the development mirror, so pytest, pyright, and your editor resolve the
   same imports.
3. `script/setup/bootstrap` (or a container rebuild) to install it.

Pin versions in both, and keep them identical. Renovate raises the two files in one pull request; Dependabot skips
`requirements.txt` on purpose, because it cannot see `manifest.json` and would split the pair. The commit type for such
an update is `build`, which puts it into the changelog; Renovate uses it already.

| File                     | Template sync  | Contents                                         |
| ------------------------ | -------------- | ------------------------------------------------ |
| `requirements.txt`       | ❌ excluded    | your integration's runtime dependencies          |
| `requirements_dev.txt`   | ✅ synced      | shared development tooling — do not add app deps |
| `requirements_test.txt`  | ✅ synced      | shared test dependencies                         |
| `requirements.local.txt` | — (gitignored) | your personal extras (`ipdb`, profilers, …)      |

Before adding a dependency at all, decide whether you want it: the criteria are in `AGENTS.md` § Custom Integration
Flexibility, and the choice belongs in a decision record ([`blueprint-decisions`](../blueprint-decisions/SKILL.md)).
For a serial port that means `serialx`, not `pyserial-asyncio` — the replacement table is in
[`ha-modern-apis`](../ha-modern-apis/references/deprecations.md).

Every package you add ships to every user, so check it like Core does
([`dependency-transparency`](https://contributors.home-assistant.io/core/quality-scale/dependency-transparency/)),
and report what you could not verify rather than assuming it:

- **Adding:** published on PyPI with a source distribution, an OSI-approved licence, a public repository and an open
  issue tracker, and the PyPI version matches a tagged release built by public CI.
- **Bumping**, Renovate's pull requests included: read the upstream diff or changelog, not just the version. Look for
  new network calls, `subprocess` or `os.system`, new file or environment access, new transitive dependencies, a
  changed licence, a new PyPI maintainer, or a repository that moved or was archived. Any of these goes to the
  developer before the merge.

## Command-line tools and dependency updates

`mise.toml` pins the tools the scripts run — Python, `uv`, the shell linters, `jq`, `yq`, `rg`, `fd`, `gron` — for
every environment, and names the Home Assistant venv (`.venv`), so `mise env` — which every script and agent shell
applies — puts that venv ahead of mise's own Python. A new tool goes there with an exact version, never `latest` and never into the dev container's apt
list, which no cloud session or CI job sees. In an integration made from the blueprint, its own tools go into
`.config/mise/conf.d/project.toml` instead: template sync overwrites `mise.toml` and never touches that file, and mise
loads it everywhere `mise.toml` is loaded. A tool in both keeps the blueprint's version. A terminal tool only a person in the dev container uses goes into
`mise.devcontainer.toml` instead, which mise loads there through `MISE_ENV=devcontainer`. apt keeps the system
libraries Home Assistant's wheels build against and the few tools mise has no prebuilt binary for. Python follows Home Assistant: `script/ha-version-sync` fails when the
pin no longer satisfies Home Assistant's `requires-python`. Node is not pinned there; every environment brings one.

Two bots share the updates without overlapping — a dependency raised by both would arrive twice:

| What                                                                | Raised by                             | Pull request                                                                                                 |
| ------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| GitHub Actions, npm, dev container features, `requirements_dev.txt` | Dependabot (`.github/dependabot.yml`) | weekly, minor/patch grouped per ecosystem                                                                    |
| `mise.toml`, the mise version in workflows and the dev container    | Renovate (`.github/renovate.json`)    | weekly, one `tooling` group                                                                                  |
| `manifest.json` + `requirements.txt`                                | Renovate                              | one per package, a major waits for approval; `fix(deps)` only for a security advisory                        |
| `pytest-homeassistant`                                              | Renovate                              | its own; a new release train fails `script/ha-version-sync` until `hacs.json` follows                        |
| the agent plugin tag in the three agent settings files              | Renovate                              | one `agent plugins` pull request for all three; `script/setup/agent-plugins --check` fails on a partial bump |

Renovate needs its GitHub App installed on the repository and does nothing without it: no error, no pull request.
Dependabot has no mise ecosystem, so without the App the tool pins and the runtime requirements only move by hand;
`toolchain-update-check.yml` then keeps one issue open listing the outdated pins, and stays quiet while Renovate is
active.

**A `googleapis/release-please-action` update needs one more step:** replace
`script/tests/fixtures/release-please-pr-body.txt` with the body of a release PR the new version wrote. That test is
what proves `script/release-notes --apply` still writes a body release-please can read back.
`mise run renovate-dry-run` shows what Renovate would raise, without opening anything. The developer-facing version of
this section is `docs/development/DEPENDENCY_UPDATES.md`.

To drop Dependabot and let Renovate raise everything, delete `.github/dependabot.yml` and the first two package rules
in `.github/renovate.json`; the grouping and the release-age settings for those ecosystems are already there. Keep
Dependabot alerts on in the repository settings either way — Renovate reads them for its security pull requests.

## Extending the scripts with hooks

Every script supports sourced `pre` and `post` hook scripts under `script/hooks/` and `.devcontainer/hooks/`. Use them
instead of editing the template-managed scripts themselves — hook directories are excluded from template sync, the
scripts are not.

| File                                           | When to read                                                                                                                                                    |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`references/hooks.md`](references/hooks.md)   | Adding or debugging a hook. Naming convention, the complete pre/post hook table for every script, worked examples, and the rules that apply to sourced scripts. |
| [`references/ha-cli.md`](references/ha-cli.md) | Using `script/ha`. Every command with its options, the token lifecycle, exit codes, and driving config flows from the terminal.                                 |

## Devcontainer environment

Two layers, both sourced by the lifecycle scripts:

| File                       | Committed          | Purpose                        |
| -------------------------- | ------------------ | ------------------------------ |
| `.devcontainer/.env`       | ✅ yes             | project defaults for everyone  |
| `.devcontainer/.env.local` | ❌ no (gitignored) | personal overrides, always win |

| Variable                | Default   | Effect                                                                                                                                                                     |
| ----------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HA_VERSION`            | `minimum` | `latest` or `beta`: the environment bootstrap builds and activates instead; one particular release only by hand, `script/ha-env add custom <version>`                      |
| `HA_ENVS`               | `minimum` | environments bootstrap installs, e.g. `minimum latest beta` — [testing a newer release](../../../docs/development/CUSTOMIZATION.md#testing-against-a-newer-home-assistant) |
| `HA_INSTALL_HACS`       | `1`       | `0` skips the HACS install; ignored from 2026.11, which has the Marketplace built in                                                                                       |
| `APT_UPDATE`            | `0`       | `1` runs `apt-get update && upgrade` during setup                                                                                                                          |
| `INSTALL_AGENT_PLUGINS` | `1`       | `0` stops bootstrap installing the agent plugins the repository enables; the check that the agents' settings agree still runs                                              |

Changes require **Dev Containers: Rebuild Container**. These files are not visible to devcontainer _features_ or
`containerEnv` — those are set at image build time and must be edited in `devcontainer.json`.

Scripts under `script/` read the **process** environment and do not source these files. Variables that steer them are
therefore set in a hook — `script/hooks/develop.pre.sh` for anything `script/develop` runs:

| Variable            | Default                 | Effect                                              |
| ------------------- | ----------------------- | --------------------------------------------------- |
| `HA_DEV_TOKEN`      | `1`                     | `0` skips minting the `script/ha` token entirely    |
| `HA_DEV_TOKEN_DAYS` | `30`                    | token lifetime; it rotates once under 7 days remain |
| `HA_URL`            | `http://127.0.0.1:8123` | which instance `script/ha` talks to                 |
| `HA_TOKEN`          | the seeded token file   | authenticate `script/ha` as someone else            |

## Template sync

A weekly workflow opens a pull request with upstream blueprint changes. It uses `-X theirs`, so **the template version
wins** on any file both sides changed — the PR is always mergeable, and the diff shows your version being replaced.
Review before merging.

- To permanently own a file, add it to `.templatesyncignore` (gitignore glob syntax). Do that rather than resolving the
  same conflict every week.
- Do not add generated or personal files — untracked files are never touched by sync anyway.
- Workflow files under `.github/workflows/` only sync when a `TEMPLATE_SYNC_TARGET_PAT` secret with `workflows: write`
  exists; otherwise those updates are skipped with a notice in the run summary.
- A version pin the repository's own bots raised further than the template survives the sync:
  `script/template-sync-guard` restores it on the sync branch and comments what it kept. That step lives in
  `template-sync.yml`, which the sync never updates, so a repository created before it existed copies the step over
  by hand. A sync PR that lowers a version anyway was produced without the step.
- Blueprint-only files the sync brings are removed on the sync branch by `script/prune-blueprint --apply`, in the last
  step of `template-sync.yml`, and listed in `.templatesyncignore` — the same copy-by-hand caveat applies.
- Changes the sync cannot deliver — to excluded files such as `AGENTS.md`, or steps a repository has to take itself —
  are carried over with [`blueprint-update`](../blueprint-update/SKILL.md) and `script/blueprint-update`.

Background, recovery procedures, and the default exclusion list are in
[`docs/development/CUSTOMIZATION.md`](../../../docs/development/CUSTOMIZATION.md).
