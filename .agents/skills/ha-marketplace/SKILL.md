---
name: ha-marketplace
description: >-
  Publish this Home Assistant custom integration through the Marketplace and HACS, and keep it listed — repository
  preconditions, hacs.json, release assets, brand images, the catalog's CI gates, the hacs/default pull request, My
  links, how a release reaches users, and renaming, archiving or removing a listing. Use when asked to "publish the
  integration", "get it into HACS", "submit to the Marketplace", "add it to the default repositories", "why doesn't
  the update show up", "keep files across updates", "rename or archive the repository", or when editing hacs.json,
  brand/ or the README's Marketplace view. SYMPTOMS — load this if you are about to: open the hacs/default pull
  request yourself; add an `ignore` to the HACS action to make it pass; delete a repository that is in the catalog;
  delete an old release; write user data into the integration folder; remove `zip_release`; ship Home Assistant's own
  logo as the brand icon; or raise `homeassistant` in hacs.json without naming the new minimum in the changelog.
---

# Publish through the Marketplace

The Marketplace is the `marketplace` integration in Home Assistant Core from 2026.11 (**Settings** → **Marketplace**).
It is HACS brought into Core: same catalog ([hacs/default](https://github.com/hacs/default)), same `hacs.json`, same
[HACS action](https://github.com/hacs/action). On first start it takes over a HACS installation and Home Assistant
2026.11 blocks the HACS custom integration. With 2026.11 as the minimum in `hacs.json`, every user of this
repository installs and updates through the Marketplace.

Sources, checked against these pages — re-read them before relying on a detail that matters:
[how it works](https://contributors.home-assistant.io/marketplace/how-it-works/),
[custom integrations](https://contributors.home-assistant.io/marketplace/guides/integrations/),
[releases](https://contributors.home-assistant.io/marketplace/guides/releases/),
[catalog](https://contributors.home-assistant.io/marketplace/guides/catalog/),
[hacs.json](https://contributors.home-assistant.io/marketplace/reference/hacs-json/),
[validation](https://contributors.home-assistant.io/marketplace/reference/validation/),
[brands](https://contributors.home-assistant.io/core/integrations/brands/).

## Reference files

| File                                                   | When to read                                                                       |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| [`references/checks.md`](references/checks.md)         | Every `hacs.json` key, the catalog review checks, and what the Marketplace refuses |
| [`references/catalog-pr.md`](references/catalog-pr.md) | Drafting the hacs/default pull request, or the removal request                     |
| [`references/lifecycle.md`](references/lifecycle.md)   | README My links, how a release reaches users, renaming, archiving or removing      |

## 1. Repository preconditions

All of these are GitHub settings, not files — check them with `gh repo view <owner>/<repo> --json
visibility,description,repositoryTopics,hasIssuesEnabled`:

- **Public.** The Marketplace and HACS only read public repositories. `validate.yml` skips HACS validation on a
  private repository with a notice, so a green CI on a private repository proves nothing about the catalog.
- **A description, topics, and issues turned on** — each is a catalog review check.
- **`README.md`** — the Marketplace shows it on the repository page. `initialize.sh` produced it from
  `README.template.md`; it must describe the real integration, not the blueprint's demo
  ([`ha-quality-review`](../ha-quality-review/SKILL.md) §8).
- **At least one published GitHub release** — a bare tag is not enough. [`ha-release`](../ha-release/SKILL.md)
  owns how releases are made.

The manifest side is in [`blueprint.manifest`](../../instructions/blueprint.manifest.instructions.md): the catalog
requires `domain`, `documentation`, `issue_tracker`, `codeowners`, `name` and `version`, and the HACS action fails an
unknown `categories` value.

**Pick a domain that is free.** A domain equal to a Core integration replaces it — the catalog rejects that, and the
Marketplace makes the user confirm. A domain another installed repository already uses is refused outright. Check
both before the domain is public, because changing it later is a breaking change:

```bash
ls .venv/lib/python*/site-packages/homeassistant/components/<domain>   # must not exist
curl -s https://data-v2.hacs.xyz/integration/data.json | jq -r '.[] | select(.domain == "<domain>") | .full_name'
```

## 2. `hacs.json` — when to touch it

The Marketplace reads `hacs.json` from the root **for every version it installs**, so a key applies per release.
The template ships `name`, `homeassistant`, `hacs`, `zip_release`, `filename` (`initialize.sh` sets the domain in
it) and `hide_default_branch`; most integrations never need more. Full key table:
[`references/checks.md`](references/checks.md).

- **`homeassistant`** — the minimum version for _this_ release. The Marketplace does not offer the release to an
  older Home Assistant and shows those users earlier versions instead. Raise it in the release whose code first needs
  the newer version, never ahead of it. Raising it is not breaking, but older installs silently stop getting fixes,
  so the changelog names it ([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md#1-recognise-it));
  `script/ha-version-sync` then makes the pytest plugin pin follow ([`ha-modern-apis`](../ha-modern-apis/SKILL.md)). A `b0` suffix (`"2026.11.0b0"`) also admits that
  release's betas. Only checked for repositories with releases.
- **`persistent_directory`** — an update replaces the whole integration folder; this names one subfolder the
  Marketplace moves aside and restores. ❌ Do not design for it: user data and runtime state belong in
  `homeassistant.helpers.storage.Store` (under `config/.storage/`), which survives updates and is covered by
  backups. Reach for it only for files a library insists on finding inside the integration folder.
- **`zip_release` / `filename`** — ✅ set, and keep both. release-please creates each release as a draft (`draft`,
  `force-tag-creation` in `release-please-config.json`); the `release-asset` job in `release-please.yml` builds the ZIP
  with `script/build` (the tracked files of `custom_components/<domain>/` at the archive root, the build hooks, a check
  that `manifest.json` carries the tag's version), attaches it under the name read from `filename`, and only then
  publishes. The Marketplace installs from that asset, for a catalog version without a GitHub connection.
  Only an asset carries a GitHub download count; a source archive does not. Removing the keys breaks installs; the
  file name lives only in `hacs.json`, never a second time in the workflow. When the job fails, the release stays a
  draft: run the workflow by hand with the tag — "Re-run all jobs" creates no release and skips the job.
- **`hacs`** — the minimum HACS version. The Marketplace reads it but never compares it; HACS still does, so keep it.
- **`hide_default_branch`** — ✅ set, and keep it while `zip_release` is set. With `zip_release` every install
  fetches the release asset, even for the default branch — `releases/download/main/<filename>`, which never exists —
  so offering the branch offers a version that cannot install (`_async_download_version` in the Marketplace). The
  key only hides the branch in the version menu; before the first release the Marketplace still falls back to the
  branch, and that install fails, so the repository has nothing installable until then.
- **What ships can be built, not committed.** A bundled card or generated data comes from
  `script/hooks/build.post.sh` at release time instead of sitting in the repository; the files hassfest and the HACS
  action validate stay committed. How:
  [`blueprint-tooling/references/hooks.md`](../blueprint-tooling/references/hooks.md#the-build-hook).
- `script/tests/test_hacs_json.py` fails CI when `zip_release` is set without `filename`, `hide_default_branch`, or the
  draft settings in `release-please-config.json`.
- **`content_in_root`** — not for this layout; leave it out.
- **`country`** — only when the integration works in some countries only; the catalog asks for it then.

A key with a value of the wrong type is dropped with a logged warning, not an error — validate against
`schemas/json/hacs_schema.json` ([`blueprint.json`](../../instructions/blueprint.json.instructions.md)).

## 3. Brand images

`custom_components/<domain>/brand/` holds `icon.png` (256 × 256), `icon@2x.png` (512 × 512) and optionally
`logo.png` / `logo@2x.png` (shortest side 128–256 / 256–512 px) and `dark_` variants. PNG, trimmed, transparent
background preferred. File names and rules:
[brand images for custom integrations](https://contributors.home-assistant.io/core/integrations/brands/#brand-images-for-custom-integrations).

- The catalog requires at least `icon.png`. Replacing the blueprint's placeholder is a
  [`blueprint-scaffold`](../blueprint-scaffold/SKILL.md) §7 step; ask the developer for the artwork, never invent it.
- ❌ No Home Assistant branded images — users would take the integration for an official one.
- The brands site picks images up **from the latest release**, so a new icon on `main` is invisible in the
  Marketplace until the next release.
- ❌ No pull request to `home-assistant/brands` — that is for Core integrations, and a local `brand/` folder takes
  precedence anyway.

## 4. CI gates

`.github/workflows/validate.yml` runs both gates the catalog requires: **hassfest** and the **HACS action** with
`category: integration`. The catalog review rejects a run that used `ignore`, and the pull request template asks for
a link to a passing run without it.

- `validate.yml` sets `ignore: brands` automatically while `brand/icon.png` is missing. Before submitting, the icon
  must exist so that the step's warning is gone and the run is clean.
- ❌ Never add an `ignore` to get the action green. Fix the repository setting or file it names.
- The workflow runs on pull requests, weekly and on demand — not on every push to `main`. For the link, start it on
  `main` with `gh workflow run validate.yml --ref main` and take the URL of the finished run.

## 5. Get into the catalog

Users can add the repository from a link at any time (a "custom repository"). The catalog makes it searchable for
everyone. The submission is a pull request to [hacs/default](https://github.com/hacs/default), and **the developer
submits it, not the agent**: it must come from the owner or a major contributor, from a personal account, and every
statement in it must be true.

**What the agent does:** confirm §1–§4 with evidence, then draft the pull request text into `.agents/scratch/` with
[`references/catalog-pr.md`](references/catalog-pr.md), and hand the steps over. Order matters: the validation runs
pass first, then a release is published, then the pull request is opened.

Set expectations plainly: reviews take **months**; the backlog is public. Not accepted at all: integrations that
replace a Core integration, and builds for testing an alpha or beta of a Core integration. Never request reviews on
the pull request — it gets closed.

## 6. The README is read in two places

GitHub shows the whole `README.md`. The Marketplace shows it on the repository page too, which already has an install
button, so install instructions, install badges and contributor setup are noise there. Put what is only for GitHub
between two markers; GitHub does not render HTML comments, so it reads as before:

```markdown
<!-- ha-marketplace:exclude-start -->

## Contributing

<!-- ha-marketplace:exclude-end -->
```

- A section runs from a start marker to the next end marker, or to the end of the README without one. Spaces inside
  the marker are optional.
- A marker inside a code block or inline code is text, so a README can show them as an example.
- `README.template.md` excludes the Codespaces blurb, the install badge with its fallbacks, and the contributing
  section. Keep the setup steps, entities, options and troubleshooting visible: users read those before installing.
- Excluded text must not be referred to from visible text ("see the section above").
- A start without its end hides the rest of the README in the Marketplace, and GitHub shows neither marker —
  `tests/test_readme_markers.py` checks that they pair up.

## Do not

- ❌ **Never delete a repository that is in the catalog without the removal request first.** Deleting a listed
  repository bars the owner from adding any repository to the catalog in the future. Archive it, or file the request and wait for it to be handled.
- ❌ Do not open the hacs/default pull request or the removal issue yourself; draft them for the developer.
- ❌ Do not add `ignore` to the HACS action, delete old releases, or remove `zip_release`/`filename`.
- ❌ Do not store user data inside `custom_components/<domain>/`.
- ❌ Do not claim the integration is "in HACS" or "in the Marketplace" before the catalog pull request is merged —
  until then it installs only as a custom repository.
