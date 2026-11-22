---
description: "Use when writing or suggesting git commit messages or pull request titles, or deciding commit type/scope (the type decides what appears in the release notes)."
---

# Commit Message Rules (Release-Notes Aware)

Use these rules whenever you generate or suggest commit messages.

## Primary Goal

Write technically correct Conventional Commit messages while ensuring release notes only include user-relevant changes.

## Required Format

Use this structure:

<type>(<scope>): <short summary>

<body>

Impact: <user-facing outcome>

### Notes

- Keep summary imperative and concise.
- Keep body technical (what changed and why).
- Keep Impact user-facing (what users notice).
- The subject is the line users read in the release notes (release-please lists subjects only), so write it for them; Impact stays in the body for reviewers and the history.

## Type Selection

Release notes come from release-please (`release-please-config.json`), which reads the commits on main and sorts them **by type only** (it ignores scopes and trailers):

- `feat` → "What's New": new user-visible capability.
- `fix` → "Fixed": user-visible bug fixes only.
- `perf` → "More Reliable": user-visible reliability/performance improvements.
- `build` → "Updated Dependencies": only as `build(deps)`, for requirements of the integration itself (`manifest.json`), which reach users. Renovate writes these; `pr-title.yml` rejects any other `build` scope. Packaging and tooling are `chore` or `ci`.
- `docs`, `test`, `refactor`, `style`, `ci`, `chore`, `revert` are hidden: use them for everything users don't notice.

The type decides whether a change appears in the release notes, so pick it for the reader of the release notes. A pull request title becomes the commit on main (squash merge), so the same rules apply to it (checked by `.github/workflows/pr-title.yml`).

## Not a Breaking Change: Raising the Minimum Home Assistant Version

Raising the minimum supported Home Assistant version (`hacs.json`, installation docs) is NOT a breaking change: users on an older Home Assistant are never offered the update, so nothing breaks for them. Never mark it with `!` or a `BREAKING CHANGE` trailer, and don't write "update Home Assistant first" into Impact. Use `build(deps)` and state the new minimum in the subject or body; the release notes list it, which is enough.

## Critical Rule: Internal/Unreleased Fixes

If a fix addresses code that was not released to users yet, DO NOT treat it as a user-facing fix: use `chore(...)`, `refactor(...)` or `test(...)` instead of `fix(...)`, so release-please leaves it out. Trailers such as `Release-Notes: skip` have no effect any more.

To change a line after the fact, put a `BEGIN_COMMIT_OVERRIDE` … `END_COMMIT_OVERRIDE` block into the body of the squash-merged pull request (release-please reads it instead of the commit message); for a commit pushed directly to main there is no such way, so get the type right before committing.

## How To Decide Released vs Unreleased

When uncertain whether users were affected, check if the introducing commit was part of a release tag:

./scripts/release/check-if-released <commit-hash>

Interpretation:

- NOT RELEASED -> treat as internal/non-user-facing.
- ALREADY RELEASED -> user-facing fix is possible.

## Examples

### User-facing fix

fix(config_flow): prevent setup failure on invalid home selection

Validate home selection before entry creation to avoid runtime errors when stale API data is returned.

Impact: Setup wizard no longer fails for users when home data changes during configuration.

### Internal-only fix for unreleased code

chore(periods): adjust extension guard for new geometric matcher

Tune guard conditions in the new matcher implementation to avoid edge-case misclassification during development.
