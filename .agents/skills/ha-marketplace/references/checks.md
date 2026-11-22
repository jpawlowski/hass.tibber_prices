# Marketplace checks and `hacs.json` keys

Lookup tables for [`ha-marketplace`](../SKILL.md). Sources:
[hacs.json](https://contributors.home-assistant.io/marketplace/reference/hacs-json/),
[validation checks](https://contributors.home-assistant.io/marketplace/reference/validation/),
[get into the catalog](https://contributors.home-assistant.io/marketplace/guides/catalog/#what-the-review-checks).

## `hacs.json` keys

The Marketplace reads the file of every version it installs. A key with a value of the wrong type is dropped with a
warning; unknown keys are ignored. Versions compare with AwesomeVersion.

| Key                    | Type           | Effect, and whether this repository uses it                                                     |
| ---------------------- | -------------- | ----------------------------------------------------------------------------------------------- |
| `name`                 | string         | Name users see. Required by HACS and the catalog. ✅ set                                        |
| `homeassistant`        | string         | Minimum Home Assistant for this release; `b0` suffix admits betas. Releases only. ✅ set        |
| `hacs`                 | string         | Minimum HACS version. The Marketplace reads it but does not compare it. ✅ set                  |
| `persistent_directory` | string         | Subfolder of the integration kept across updates. ⚠️ prefer `Store`                             |
| `zip_release`          | boolean        | Install from the ZIP asset named by `filename`; the release workflow builds it. ✅ set          |
| `filename`             | string         | The ZIP asset's name with `zip_release`; `release-please.yml` reads it. ✅ set                  |
| `content_in_root`      | boolean        | Integration files in the repository root instead of `custom_components/<domain>/`. ❌           |
| `hide_default_branch`  | boolean        | The default branch is not offered as an installable version. ✅ set, required by `zip_release`  |
| `country`              | string or list | ISO 3166-1 alpha-2 codes for a region-bound integration; the catalog asks for it then. Optional |

## Catalog review checks

All must pass when the pull request comes up for review, unless the HACS team agreed otherwise beforehand.

| Check           | Passes when                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------ |
| Brands          | `custom_components/<domain>/brand/icon.png` exists (or the domain has images in the brands repo) |
| Manifest        | `domain`, `documentation`, `issue_tracker`, `codeowners`, `name` and `version` are present       |
| HACS validation | the same validation HACS runs on a repository                                                    |
| HACS manifest   | `hacs.json` has at least `name`                                                                  |
| Archived        | the repository is not archived                                                                   |
| Releases        | at least one published release                                                                   |
| Owner           | the submitter owns the repository or is a major contributor                                      |
| Repository      | description set, issues enabled, topics set                                                      |
| Lint            | the changed `integration` file is valid JSON and sorted                                          |

## HACS action checks that `ignore` could skip

`archived`, `brands`, `description`, `hacsjson`, `images`, `information`, `integration_categories`, `issues`,
`topics`. Skipping any of them makes the run worthless for the catalog. `integration_categories` fails on an unknown
or duplicate category, or more than three, and only warns when `categories` is missing.

## What the Marketplace refuses at install time

Stricter than HACS. Checks after writing roll the files back on failure.

| Check                     | Fails when                                                                       |
| ------------------------- | -------------------------------------------------------------------------------- |
| `hacs.json` in the root   | it is missing — no install and no update                                         |
| Not archived, not removed | the repository is archived, or removed from the catalog                          |
| Files in place            | nothing under `custom_components/` (the first folder there is the one installed) |
| Minimum Home Assistant    | `homeassistant` is newer than the user's; older releases are offered instead     |
| Domain characters         | `domain` has anything but lowercase letters, digits, `_` and `-`                 |
| Owner of the domain       | another installed repository has the same domain                                 |
| Replaces a Core domain    | the domain is a Core integration's and the user did not confirm                  |
| Loadable manifest (after) | `manifest.json` names another domain, or has no `version` the loader accepts     |
| Download size             | more than 100 MiB, or more than 50,000 files, downloaded or unpacked             |
