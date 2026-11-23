# Manual steps

What an integration repository has to do by hand because template sync cannot do it, newest first. Each step has an id
for the `skipped` list in `.agents/blueprint-update.json`, the date it entered the blueprint, and a check that passes
once it is done. Run the check from the repository root.

## `agent-plugins` — 2026-11-23

**Check:** `grep -q 'ha-custom-integration-skills' AGENTS.md && ! grep -qE 'skills/(ha-grill|ha-planning|ha-issue-triage|blueprint-change-review)/' AGENTS.md && ! grep -q 'and the review below ran' AGENTS.md && test ! -e .agents/skills/ha-grill && test ! -e .agents/skills/ha-planning && test ! -e .agents/skills/ha-issue-triage && test ! -e .agents/skills/blueprint-change-review && test ! -e .claude/commands/issues.md && test ! -e .github/skills/issues && ! grep -q 'Review before a commit and before a pull request leaves draft' AGENTS.md`

Interviewing, planning and backlog triage are now plugins from
[ha-custom-integration-skills](https://github.com/jpawlowski/ha-custom-integration-skills) that a developer can turn
off: `haci-grill` and `haci-planning` (`haci-plan`), backlog triage with `haci-issue-triage` and `haci-issues`, which
replaces the `/issues` command (`haci-triage`, off by default), and the review pass `haci-change-review` (`haci-review`),
which now runs once before a push instead of before every commit. The sync brings the agent settings that pin and
enable them and `script/setup/agent-plugins`, which bootstrap runs; recording decisions moves to the new
`blueprint-decisions` skill. In Claude Code they are invoked as `/haci-plan:haci-grill` and so on.

1. Delete `.agents/skills/ha-grill/`, `.agents/skills/ha-planning/`, `.agents/skills/ha-issue-triage/`,
   `.agents/skills/blueprint-change-review/`, `.claude/commands/issues.md` and `.github/skills/issues/` where the sync
   left them. A copy you kept on purpose in
   `.templatesyncignore` has its `haci-` counterpart now; drop the copy or the entry.
2. In `AGENTS.md`, replace their routing rows with the `blueprint-decisions` row; if you took the earlier step
   `change-review-pass`, also remove the section _Review before a commit and before a pull request leaves draft_ and
   the words "and the review below ran" in the draft bullet; carry over the section _Agent
   plugins_ with its table and the critical files, and point _Decisions_ and _Scope of a change_ at the new names.
3. Run `script/setup/agent-plugins`.

## `release-notes-sentence-case` — 2026-11-22

**Check:** `! grep -qE "What's New|More Reliable|Updated Dependencies" release-please-config.json`

The release notes sections are now in sentence case, like every heading in Home Assistant: 🎉 What's new,
⚡ More reliable and 📦 Updated dependencies. `release-please-config.json` is not synced: rename those sections in its
`changelog-sections`, and in the table in `docs/development/RELEASE.md`.

## `release-notes-sections` — 2026-11-22

**Check:** `grep -q '"type": "build"' release-please-config.json && grep -q 'include-v-in-tag' release-please-config.json`

The release notes are what users read in the update dialog, so their sections now speak to users: 🎉 What's New,
🐛 Fixed, ⚡ More Reliable, and 📦 Updated Dependencies for the new commit type `build`. The sync brings `build` to
commitlint and Renovate, which now commits an update of a library in `manifest.json` → `requirements` as `build`.
`release-please-config.json` is not synced: copy the blueprint's `changelog-sections` and add
`"include-component-in-tag": false` and `"include-v-in-tag": true`, which pin the tag format at `v1.2.3`. Without the
`build` section those commits stay out of the changelog. The table in `docs/development/RELEASE.md` names the
sections too.

## `lessons-routing` — 2026-11-22

**Check:** `grep -q 'A fixed bug stays fixed' AGENTS.md && grep -q 'never only in your own memory' AGENTS.md && grep -q '^| .*blueprint-lessons/SKILL.md' AGENTS.md`

The sync brings the skill `blueprint-lessons` — where a lesson from a fixed bug or a repeated correction goes so the
next agent does not repeat it, and when to create or extend a project skill. `AGENTS.md` is not synced: carry over
the routing row, the paragraph _A fixed bug stays fixed_ under _Scope of a change_, and the rewritten paragraph on a
permanent change of approach under _When instructions conflict with a request_. From now on `script/skills-check`
fails while a project instructions file — one not named `blueprint.*` — has no row in the routing table.

## `decision-records` — 2026-11-22

**Check:** `test ! -e docs/development/DECISIONS.md && test -f docs/development/decisions/README.md && grep -q 'docs/development/decisions' AGENTS.md`

Decisions are now one record per file in `docs/development/decisions/`, with an index `script/decisions` writes and
checks — see [`blueprint-decisions`](../../blueprint-decisions/references/decision-records.md). The script arrives through the sync and
passes while the old single file is still there; `docs/` and `AGENTS.md` are not synced:

1. Move each entry of `docs/development/DECISIONS.md` this project made into a record of its own, keeping its text,
   with `status: accepted` and `migrated-from: docs/development/DECISIONS.md`; name it after the entry's date.
2. Drop the four entries headed "Template initialization" and the "Future Considerations" section, if the developer
   agrees: they came with the blueprint and restate Home Assistant conventions the instructions files already hold.
3. Delete `docs/development/DECISIONS.md` and run `script/decisions`, which writes the index.
4. Carry over the _Decisions_ paragraph in the blueprint's `AGENTS.md` (section _Documentation_), and point the
   project's own mentions of `DECISIONS.md` at the new folder.

## `template-sync-prune` — 2026-11-22

**Check:** `grep -q 'prune-blueprint --apply' .github/workflows/template-sync.yml && test ! -e script/import-overlay`

The sync brings every file the blueprint adds, including the ones that only make sense in the blueprint itself — now
`script/import-overlay` and its test. The blueprint's `template-sync.yml` gained a step _Drop blueprint-only files_
that runs `script/prune-blueprint --apply` on the sync branch, so such files never reach `main`. The workflow is
excluded from the sync:

1. Copy that step from the blueprint's `template-sync.yml` to the end of this repository's; `script/blueprint-update`
   shows it in context.
2. Run `script/prune-blueprint --apply` once, for what earlier syncs already brought.

## `branch-and-pr-rules` — 2026-11-22

**Check:** `grep -q 'Commits, branches and pull requests' AGENTS.md`

The blueprint now has rules for branches and pull requests: branch names, one logical change per pull request,
force push only with a lease, and pushing only when asked. The procedures — updating a branch from `main`, conflicts,
splitting mixed work, stacked pull requests — arrive through the sync in `ha-release`. `AGENTS.md` is not synced:
replace its _Commits_ section with the blueprint's _Commits, branches and pull requests_, keeping anything this
repository added there.

## `translation-test` — 2026-11-22

**Check:** `test -f tests/test_translations.py`

Optional. Copy `tests/test_translations.py` from the blueprint (`tests/` is never synced) and replace the
blueprint's domain in its `const` import. It checks what hassfest does not: a state translation for every enum and
select option, a display name for every attribute the integration adds, and no key in another language file that
`en.json` lacks. It uses the `init_integration` fixture from the blueprint's `tests/conftest.py` — copy that fixture
too if this repository's conftest has none. A failure after copying lists the keys this integration still lacks.

## `ux-skill-routing` — 2026-11-22

**Check:** `grep -q 'ha-user-experience' AGENTS.md`

The sync brings the skill `ha-user-experience` and corrected rules in `blueprint.entities`. `AGENTS.md` is not
synced, so carry over two changes from the blueprint's `AGENTS.md`: the routing row above the `tests` row — agents
that only read the routing table otherwise never load the skill — and the _Entity metadata_ contract, which now
points to `blueprint.entities` for its exceptions instead of listing them.

## `readme-marketplace-markers` — 2026-11-22

**Check:** `grep -q 'ha-marketplace:exclude-start' README.md`

The Marketplace shows the README on the repository page, next to its own install button. Put what is only for GitHub —
the install badge and its fallbacks, a Codespaces blurb, the contributing section — between
`<!-- ha-marketplace:exclude-start -->` and `<!-- ha-marketplace:exclude-end -->`; GitHub renders nothing for them.
`README.md` is never synced, so copy the placement from the blueprint's `README.template.md`, and copy
`tests/test_readme_markers.py`, which checks that the markers pair up. Optional, and the reasoning is in
[`ha-marketplace`](../../ha-marketplace/SKILL.md#6-the-readme-is-read-in-two-places).

## `release-zip-asset` — 2026-11-22

**Check:** `jq -e '.zip_release == true and (.filename | type == "string") and .hide_default_branch == true' hacs.json && jq -e '.packages["."] | .draft == true and .["force-tag-creation"] == true' release-please-config.json`

Every release now carries a ZIP of `custom_components/<domain>/` as a release asset, and `hacs.json` tells the
Marketplace to install from it. A source archive has no download count, an asset does. The sync brings the
`release-asset` job in `release-please.yml`. Until this step is done it attaches nothing and only publishes the
release, because `hacs.json` and `release-please-config.json` are not synced:

1. Add `"zip_release": true`, `"filename": "<domain>.zip"` and `"hide_default_branch": true` to `hacs.json`. The
   default branch has no release asset, so it must not be offered for install.
2. Add `"draft": true` and `"force-tag-creation": true` to the `"."` package in `release-please-config.json`. The
   release then stays a draft until the job has attached the asset, so no user is offered a version whose ZIP is
   not there yet; a failed job leaves a draft to re-run, not a broken release.
3. If this repository customised `release-please.yml`, copy the blueprint's `release-asset` job and the `outputs` and
   `id: release` it relies on.
4. Land all of it in the same pull request. Older releases keep installing from the source tree: the Marketplace
   reads `hacs.json` from the tag of the version it installs. `script/tests/test_hacs_json.py`, which the sync
   brings, fails CI while the keys of steps 1 and 2 do not match.

[`ha-marketplace`](../../ha-marketplace/SKILL.md#2-hacsjson--when-to-touch-it) has the reasoning.

## `test-timeout` — 2026-11-21

**Check:** `grep -q '^timeout = ' pyproject.toml && grep -q -- '--picked' .vscode/tasks.json`

Like Home Assistant Core, every test now fails after 10 seconds instead of hanging a whole run, and VS Code gets tasks
for the changed tests and for snapshot updates. Neither file is synced:

1. Add `timeout = 10` under `[tool.pytest.ini_options]` in `pyproject.toml` (`pytest-timeout` is installed already).
2. Copy the blueprint's `Run Changed Tests` and `Update Test Snapshots` tasks into `.vscode/tasks.json`.

## `ha-environments` — 2026-11-21

**Check:** `grep -q 'script/ha-env' .vscode/tasks.json`

The sync brings `script/ha-env`, the environment-aware `script/setup/bootstrap` and `script/develop`, and the prompt
hook; `minimum` stays the default and `latest` or `beta` are added on demand
([`CUSTOMIZATION.md`](../../../../docs/development/CUSTOMIZATION.md#testing-against-a-newer-home-assistant)).

1. Run `script/setup/bootstrap` once, then `bash .devcontainer/setup-shell.sh`. The first moves the venv to one
   directory per Home Assistant version inside the same volume, the second brings the `ha-env` alias and the prompt
   hook into `.bashrc` and `.zshrc` — no container rebuild.
2. Copy the blueprint's `Run Home Assistant (Environment)`, `Switch`, `Add` and `Refresh Home Assistant
Environment(s)` and `Pin Home Assistant Version (custom Environment)` tasks and the `inputs` block into
   `.vscode/tasks.json`, which the sync leaves alone.

## `pytest-homeassistant` — 2026-11-21

**Check:** `! grep -rq pytest_homeassistant_custom_component tests/ && script/ha-version-sync >/dev/null 2>&1`

The sync replaces `pytest-homeassistant-custom-component` in `requirements_test.txt` with Home Assistant's own
`pytest-homeassistant`, which starts at 2026.11. `tests/` and `hacs.json` are not synced, so until this is done
`script/test` fails on the imports and `script/ha-version-sync` on the release train:

1. Raise `homeassistant` in `hacs.json` to `2026.11.0`. Users on an older Home Assistant get no further updates, so
   name the new minimum in your changelog; it is not a breaking change on its own
   ([`ha-breaking-changes`](../../ha-breaking-changes/SKILL.md#1-recognise-it)).
2. Replace `pytest_homeassistant_custom_component` with `pytest_homeassistant` in every import under `tests/`.
3. Delete the autouse `auto_enable_custom_integrations` fixture from `tests/conftest.py` — the new `hass` fixture
   loads custom integrations itself.
4. Move recorded payloads to `tests/fixtures/`: `load_fixture()` now resolves there, no longer next to the test file.
5. Add `-p no:respx` to `addopts` under `[tool.pytest.ini_options]` in `pyproject.toml`. Some Home Assistant releases
   otherwise abort the test run with "httpx was already imported".
6. Run `script/setup/bootstrap`, which rebuilds the virtual environment for the new Home Assistant version, then
   `script/test`.

To stay below 2026.11 instead, record this step as skipped and keep the old pin as
[`CUSTOMIZATION.md`](../../../../docs/development/CUSTOMIZATION.md#staying-on-an-older-home-assistant-version)
describes — including the 2026.11 APIs from the synced skills that such a repository must not adopt.

## `upstream-rename` — 2026-11-02

**Check:** `grep -q 'jpawlowski/ha-integration-blueprint' .github/workflows/template-sync.yml`

The blueprint moved from `jpawlowski/hacs.integration_blueprint` to `jpawlowski/ha-integration-blueprint`. GitHub
redirects the old name, so the sync keeps working, but only for as long as nobody claims that name again. Replace the
old name in `source_repo_path` of this repository's `template-sync.yml`; the workflow is excluded from the sync.

## `brand-images` — 2026-11-02

**Check:** `ls custom_components/*/brand/icon.png`

Replace `custom_components/<domain>/brand/` with the product's images — what is required:
[`ha-marketplace`](../../ha-marketplace/SKILL.md#3-brand-images). `custom_components/` is never synced, so only new repositories get the blueprint's placeholder. Once the file exists,
the HACS validation in `validate.yml` stops skipping its `brands` check.

## `root-gitignore` — 2026-11-02

**Check:** `grep -qE '^![^/]+/$' custom_components/.gitignore && ! grep -qxF '.gitignore' .templatesyncignore`

The root `.gitignore` is now template-synced and no longer generated from toptal, whose unanchored patterns such as
`image`, `tts` and `lib` hid integration platforms of that name. Opt in in this order: first create
`custom_components/.gitignore` containing `!<domain>/`, then delete the `.gitignore` line from `.templatesyncignore`.
The other way round, Git silently ignores every new file in the integration, and already tracked files hide that.
Move anything this repository added to its root `.gitignore` into `custom_components/.gitignore` or
`.git/info/exclude` first — the next sync overwrites the root file.

## `squash-pull-requests` — 2026-11-01

**Check:** `gh api "repos/{owner}/{repo}" --jq '.allow_merge_commit == false' | grep -q true`

The blueprint's `main` ruleset now takes every change through a pull request, admins included — squash by default,
rebase for a pull request whose commits each pass the commit rules — and a new workflow `pr-title.yml` checks the
title, which becomes the squash commit, and reports whether each commit would survive a rebase.
Ask the developer whether they want that: if so, copy the workflow (`script/blueprint-update` lists it) and run
`script/setup/github`; if not, follow _Want it less strict?_ in `docs/development/REPOSITORY_SETUP.md` of the
blueprint and record the step as skipped.

## `lint-and-test-check` — 2026-11-01

**Check:** `! gh api "repos/{owner}/{repo}/rules/branches/main" --jq '.[].parameters.required_status_checks[]?.context' 2>/dev/null | grep -qx Ruff`

The lint workflow's job is now called _Lint and test_ and also runs `script/type-check` and `script/test`. A ruleset
or branch protection that still requires the old `Ruff` check waits for it forever and blocks every pull request:
replace it with `Lint and test` — `script/setup/github` does that for the `main` ruleset it manages.

## `repository-settings` — 2026-11-01

**Check:** `gh api "repos/{owner}/{repo}/rulesets" --jq 'map(.name) | index("main") != null' | grep -q true`

Run `script/setup/github --dry-run`, show the developer what it would change, and run it without the flag once they
agree. It turns on Dependabot alerts and, on a public repository, secret scanning and push protection, and imports the
`main` ruleset; `docs/development/REPOSITORY_SETUP.md` in the blueprint explains each setting and what it costs on a
private repository. The new workflows `codeql.yml` and `secret-history-scan.yml` arrive through the sync only with a
`TEMPLATE_SYNC_TARGET_PAT`; otherwise `script/blueprint-update` lists them as new files to copy.

## `blueprint-identity` — 2026-11-01

**Check:** `grep -q '"identity"' .agents/blueprint-update.json`

Record this repository's names in `.agents/blueprint-update.json`, as `initialize.sh` now does for a new one:
`"identity": {"domain": …, "title": …, "prefix": …, "owner": …, "repository": …, "author": …}` beside `reviewed`.
Without it `script/blueprint-update` infers them from the manifest, the coordinator class and `LICENSE`, and a renamed
class lets the blueprint's own class prefix through into the diff. The values are what `initialize.sh` asked for:
the domain, the title, the class prefix, the GitHub owner and repository name, and the author.

## `template-sync-guard` — 2026-11-01

**Check:** `grep -q template-sync-guard .github/workflows/template-sync.yml`

Copy the step _Keep this repository's newer versions_ from the blueprint's `template-sync.yml` to the end of this
repository's; `script/blueprint-update` shows it in context. Without it, a sync lowers every version this repository's
Dependabot or Renovate raised further than the blueprint has. The script it calls, `script/template-sync-guard`,
already arrives through the sync — only the workflow is excluded.

## `mise-project-tools` — 2026-11-01

**Check:** `grep -qxF '.config/mise/conf.d/project.toml' .templatesyncignore`

Add `.config/mise/conf.d/project.toml` to `.templatesyncignore`, in the section for project-owned files. It is where
this repository's own command-line tools go; `mise.toml` holds the blueprint's and is overwritten by the sync.
Create the file from the blueprint's copy if the project wants a tool of its own now.

## `agents-md-outside-container` — 2026-11-01

**Check:** `grep -q '^## Outside the dev container' AGENTS.md && grep -q 'never wait for an answer' AGENTS.md`

Carry over three changes to `AGENTS.md`: the CLI tools paragraph now names `mise.toml` instead of the dev container,
_Commands you run yourself never wait for an answer_ joined the validation section, and _Outside the dev container_
is new. They tell agents how the repository works in a cloud session or on a machine without the dev container.
`script/blueprint-update` shows all three as hunks.
