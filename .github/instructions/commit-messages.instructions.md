---
description: "Use when writing or suggesting git commit messages, deciding commit type/scope, or preparing release-note-relevant commit trailers."
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

## Type Selection

- Use feat for new user-visible capability.
- Use fix only for user-visible bug fixes.
- Use perf for user-visible reliability/performance improvements.
- Use docs, test, refactor, chore, ci, build for non-user-facing work.

## Critical Rule: Internal/Unreleased Fixes

If a fix addresses code that was not released to users yet, DO NOT treat it as a user-facing fix.

In that case:

- Prefer chore(...) or refactor(...) instead of fix(...), and/or
- Add an explicit trailer in the commit body:
  - Release-Notes: skip
  - User-Impact: none
  - Released-Bug: no

Any one of these trailers is enough.

## How To Decide Released vs Unreleased

When uncertain whether users were affected, check if the introducing commit was part of a release tag:

./scripts/release/check-if-released <commit-hash>

Interpretation:

- NOT RELEASED -> treat as internal/non-user-facing.
- ALREADY RELEASED -> user-facing fix is possible.

## Release Notes Alignment

This repository's release notes generator excludes commits with any of these trailers:

- Release-Notes: skip
- User-Impact: none
- Released-Bug: no

Therefore, add one of them whenever you intentionally want to exclude a commit from release notes.

## Examples

### User-facing fix

fix(config_flow): prevent setup failure on invalid home selection

Validate home selection before entry creation to avoid runtime errors when stale API data is returned.

Impact: Setup wizard no longer fails for users when home data changes during configuration.

### Internal-only fix for unreleased code

chore(periods): adjust extension guard for new geometric matcher

Tune guard conditions in the new matcher implementation to avoid edge-case misclassification during development.

User-Impact: none

### Alternative with explicit skip marker

fix(periods): correct follow-up edge case in unreleased geometric matcher

Adjust comparison threshold in iterative matcher pass.

Release-Notes: skip
