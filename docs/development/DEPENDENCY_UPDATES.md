# Dependency updates

Two bots keep the repository current, and each dependency belongs to exactly one of them, so nothing arrives twice.
Neither raises anything until a release has been out for a few days: a compromised release is usually pulled within
hours.

## Who raises what

| What                                                                                | Raised by                             | Waits                     | Pull request                                                  |
| ----------------------------------------------------------------------------------- | ------------------------------------- | ------------------------- | ------------------------------------------------------------- |
| GitHub Actions, except `jdx/mise-action` and `trufflesecurity/trufflehog`           | Dependabot (`.github/dependabot.yml`) | 7 days                    | weekly, minor and patch grouped                               |
| npm, dev container features, `requirements_dev.txt`                                 | Dependabot                            | 3 days (patch), 7 (minor) | weekly, minor and patch grouped per ecosystem                 |
| `mise.toml`, the mise version in workflows and the dev container, `jdx/mise-action` | Renovate (`.github/renovate.json`)    | 3 days (7 for the action) | weekly, one `tooling` group                                   |
| The secret scanners, betterleaks and TruffleHog with its action pin                 | Renovate                              | 3 days (7 for the action) | as soon as the release is old enough, merged once checks pass |
| The integration's requirements, `manifest.json` with `requirements.txt`             | Renovate                              | 3 days                    | one per package; a major waits on the dependency dashboard    |
| `pytest-homeassistant`                                                              | Renovate                              | 3 days                    | its own                                                       |

An action that takes its tool's version as an input — `jdx/mise-action` and TruffleHog — belongs to Renovate together
with that input, so the pin and the version move in one pull request. `dependabot.yml` ignores both.

Security fixes skip the waiting and the schedule in both bots, provided Dependabot alerts are on —
[`script/setup/github`](REPOSITORY_SETUP.md) turns them on.

**Why Renovate at all:** Dependabot cannot read `mise.toml`, and it cannot read `manifest.json` — so it would raise
`requirements.txt` alone and leave the requirements Home Assistant installs for your users behind. Renovate bumps both
files in one pull request.

**Renovate needs its [GitHub app](https://github.com/apps/renovate)** installed on the repository. Without it
`renovate.json` does nothing and reports no error; `toolchain-update-check.yml` then opens an issue each week listing
the outdated tool pins, so they are at least not forgotten.

## What merges itself, and what does not

Only the secret scanners merge on their own. Their releases mostly add detection rules, and a scan with old rules
misses what the new ones would find. A release that finds something in the history keeps the checks red and the pull
request open — that is the notice to act on.

Everything else waits for a person, the integration's own requirements most of all: Home Assistant Core pins many
libraries itself, and a version that conflicts with Core's breaks the installation for your users. Read the release
notes against the code that uses the library before merging.

## Home Assistant and Python

Python follows Home Assistant, never the newest release: Renovate raises it by patch releases only, and
`script/ha-version-sync` fails when the pin no longer satisfies Home Assistant's own `requires-python`. A new Home
Assistant release train — `pytest-homeassistant` for a newer version — means raising the minimum in
`hacs.json` as well; `script/ha-version-sync` fails until you do, and the HA stability check closes a pull request that
would pin a Home Assistant beta.

## Template sync never lowers a version

The weekly template sync lets the blueprint win where both sides changed the same line, so a pin your bots raised
further than the blueprint would go back down. After the sync, `script/template-sync-guard` compares every pin the bots
manage — the managers and patterns in `.github/renovate.json` — with your default branch, restores each one the sync
lowered, and lists them in a comment on the sync pull request.

## Renovate only

To let Renovate raise everything and remove Dependabot: delete `.github/dependabot.yml` and the first two package rules
in `.github/renovate.json`, whose descriptions say so. The grouping and waiting times for those ecosystems are already
in place. Keep Dependabot alerts on in the repository settings — Renovate reads them for its security pull requests.

## Checking what Renovate would do

```bash
mise run renovate-dry-run
```

It lists what Renovate would raise without opening anything. Renovate's local mode sees only files git knows, so a new
config file has to be committed — or added with `git add -N` — before the dry run reads it.
