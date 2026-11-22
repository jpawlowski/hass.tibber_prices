# Release Management

This document describes the release process for this integration, including automated versioning, changelog generation, and AI-enhanced release notes.

## Overview

Releases are managed with [release-please](https://github.com/googleapis/release-please), which automates version bumping and changelog generation based on [Conventional Commits](https://www.conventionalcommits.org/). An optional local script rewrites the release notes for users with a coding agent CLI.

**Version source of truth:** `custom_components/tibber_prices/manifest.json`

> [!NOTE]
> This document explains _how the release machinery works_ and covers the one-time GitHub repository setup. The
> step-by-step procedure for cutting a release, the commit-message rules that drive it, and the pre-release checklist
> are maintained as the [`ha-release`](../../.agents/skills/ha-release/SKILL.md) agent skill, so humans and AI agents
> follow the same process.

## How It Works

### The Release Cycle

```text
1. Developer commits to main (Conventional Commits format)
        ↓
2. release-please opens/updates a release PR automatically
        ↓
3. Developer reviews and optionally enhances release notes
        ↓
4. Developer merges the PR (intentionally, when ready)
        ↓
5. release-please creates the Git tag and the GitHub Release as a draft
   manifest.json version is already updated in the merged PR
        ↓
6. The release-asset job builds the ZIP with script/build (plus any
   script/hooks/build.*.sh), attaches it as the file named by `filename` in
   hacs.json (zip_release: true), and publishes the release — users install
   from that asset
```

The Home Assistant Marketplace offers users the tag of the latest **published** GitHub Release —
a bare tag is not enough — and refuses an integration whose `manifest.json` has no `version`. Its update entity shows
the release body as the release notes. Release-please writes the version and the body; the release-asset job publishes
the release once its ZIP is attached, and adds a link to the changelog for users who skipped more than the five
releases the update dialog shows. Text for every release — a support link, a standing notice — goes into
`.github/release-notes/header.md` or `footer.md`; the job puts it around the body. A failed job leaves a draft no user
sees — run the workflow by hand with that tag (**Actions** → **Release Please** → **Run workflow**). A pre-release only reaches users who switched on
pre-releases for the repository. Details: [Releases and updates](https://contributors.home-assistant.io/marketplace/guides/releases/).

### The Release PR

After any `feat`, `fix`, or `perf` commit reaches `main`, release-please opens a pull request titled:

```text
chore(main): release X.Y.Z
```

The PR:

- Has the label `autorelease: pending`
- Contains an updated `CHANGELOG.md` (prepended section for the new version)
- Contains the version bump in `manifest.json`
- Is updated automatically as more commits land on `main`

**You decide when to release** by merging the PR. There is no automatic merge.

### Version Bumping Rules

This project is pre-1.0.0. Version bumps follow these rules:

| Commit type                   | Version change                      |
| ----------------------------- | ----------------------------------- |
| `feat`                        | patch bump (e.g. `0.1.0` → `0.1.1`) |
| `fix`, `perf`, `build`        | patch bump                          |
| `feat!` or `BREAKING CHANGE:` | minor bump (e.g. `0.1.0` → `0.2.0`) |

Once the project reaches `1.0.0`, standard SemVer applies (`feat` → minor, `fix` → patch, breaking → major).

### What Appears in the Changelog

Only user-facing changes appear in the public CHANGELOG:

| Type                                      | Visible                    |
| ----------------------------------------- | -------------------------- |
| `feat`                                    | ✅ 🎉 What's new           |
| `fix`                                     | ✅ 🐛 Fixed                |
| `perf`                                    | ✅ ⚡ More reliable        |
| `build`                                   | ✅ 📦 Updated dependencies |
| `refactor`, `chore`, `docs`, `test`, `ci` | hidden                     |

## Developer Scripts

### `script/version`

Reads the canonical version from `manifest.json`.

```bash
./script/version              # Print: 0.1.0
./script/version --tag        # Print: v0.1.0
./script/version --check      # Verify manifest.json matches .release-please-manifest.json
```

### `script/release-notes`

Generates AI-enhanced release notes with a coding agent CLI — Claude Code, Codex, GitHub Copilot or OpenCode. The dev container installs all four; the script takes Claude Code when it runs inside it, otherwise the first one you are signed in to, unless `AGENT_CLI` names one. When none is signed in, it prints each one's sign-in command. It also needs `gh auth login`.

```bash
# Preview enhanced notes on stdout
./script/release-notes

# Update the open release-please PR body with enhanced notes
./script/release-notes --apply

# Open an agent session with the context pre-loaded
./script/release-notes --interactive

# From an agent session: write the prompt for a fresh subagent, then apply its answer
./script/release-notes --prompt
./script/release-notes --apply-file notes.md
```

**How it works:**

1. Finds the open release-please PR (`autorelease: pending` label)
2. Collects rich context since the last tag:
   - Full commit details (subject, body, per-commit file stats)
   - Compact code diff for user-facing paths (sensors, config flow, services, translations)
   - Net file change list as source of truth
   - Revert commit list as chronology hints
3. Builds a detailed prompt with audience definition, jargon rules, and file impact guidance
4. Sends everything to the agent with no tools — the prompt holds all it needs
5. Outputs the result to stdout, or with `--apply` replaces the notes under the version heading in the PR body,
   keeping everything release-please reads back when the PR is merged. Run it last: release-please rewrites the
   body whenever another commit reaches `main`

**What the prompt knows about your integration** comes from `.github/release-notes/prompt.md`, if you add one: what
the integration does for users, your own jargon to keep out of the notes, a title, a commit trailer to prefer. It is
added after the generic rules and wins over them on wording and content; the output format stays fixed apart from
an optional `#` title line, since `--apply` has to read it back. The file is yours; template sync never replaces it, while
`script/release-notes` itself is template-managed.

**`--interactive` mode** writes the full prompt and context to `.agents/scratch/release-notes-context.md` and opens a session of the same agent so you can iterate manually.

**Skip a commit from release notes** by adding a trailer to the commit body:

```text
Release-Notes: skip
```

or:

```text
User-Impact: none
```

**Environment variables:**

| Variable                 | Default             | Description                                                    |
| ------------------------ | ------------------- | -------------------------------------------------------------- |
| `AGENT_CLI`              | first one signed in | `claude`, `codex`, `copilot` or `opencode`                     |
| `AGENT_MODEL`            | the CLI's own       | Model for that CLI; for `copilot`, `COPILOT_MODEL` still works |
| `RELEASE_NOTES_DIFF_MAX` | `8000`              | Max bytes for code diff context                                |

## Typical Release Workflow

The end-to-end procedure — commit conventions, the pre-release checklist, and troubleshooting a release that did not
happen — is documented in the [`ha-release`](../../.agents/skills/ha-release/SKILL.md) skill.

The short version:

```bash
git commit -m "feat(sensor): add air quality index sensor"  # Conventional Commits
# push to main — release-please opens or updates the release PR automatically
./script/release-notes           # preview enhanced notes
./script/release-notes --apply   # write them into the PR body
# review the PR on GitHub, then merge it when you are ready to release
```

## GitHub Repository Setup (One-Time)

> [!NOTE]
> These settings cannot be stored in the repository. [`script/setup/github`](REPOSITORY_SETUP.md) applies them:
> workflows may open pull requests, which release-please needs, and the `main` ruleset requires a pull request with
> `Lint and test`, `Hassfest validation` and `HACS validation` green — so a release PR with failing CI cannot be merged by
> accident.

### Optional: Protect the Release PR from Accidental Merge

release-please labels its PR with `autorelease: pending`, which visually distinguishes it from feature PRs. With branch protection and required checks active, the risk of accidental merges is already very low.

If you want an additional manual gate, you can add a required label (`release: approved`) that must be set before the PR can be merged — configure this via a custom branch ruleset in GitHub.

## Files

| File                                   | Purpose                                                          |
| -------------------------------------- | ---------------------------------------------------------------- |
| `.github/workflows/release-please.yml` | GitHub Actions workflow, triggers on push to `main`              |
| `release-please-config.json`           | Changelog sections, version bump rules, extra-files              |
| `.release-please-manifest.json`        | Current version tracked by release-please                        |
| `CHANGELOG.md`                         | Auto-generated, committed in the same commit as the version bump |
| `script/version`                       | Local version utility                                            |
| `script/release-notes`                 | Local release notes rewrite with a coding agent CLI              |
