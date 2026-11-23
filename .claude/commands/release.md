---
description: "Cut a release: follow the ha-release skill's procedure end to end."
argument-hint: "[check|notes|apply-notes]"
allowed-tools: Bash, Read, Grep, Glob, Skill
disable-model-invocation: true
---

Load the [`ha-release`](../../.agents/skills/ha-release/SKILL.md) skill with the `Skill` tool and follow its
procedure exactly — this command does not restate it, so re-read that file rather than relying on what you already
know about it, in case it has changed.

With no arguments, inspect the unreleased commits and report the version release-please will derive; do not edit a
version or create a release PR manually. `check` runs the skill's pre-release checklist, `notes` previews
`script/release-notes`, and `apply-notes` updates the body of an existing release-please PR after the draft is read.
