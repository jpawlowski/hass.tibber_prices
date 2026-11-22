---
description: "Triage/fix the GitHub issue backlog via branch + PR, with auto-merge on green CI for this session."
argument-hint: "[issue#] | locks | unlock <issue#> | stop"
allowed-tools: Bash(gh:*), Read, Glob, Grep, Agent, Skill
disable-model-invocation: true
---

Invoking this command is the explicit, session-scoped signal that turns on full autonomy for this run: merge each
pull request automatically once its checks are green, without asking for confirmation on every single one (the
opt-in condition the skill itself defines — see its "Merge autonomy" section). Say once, at the start, that this
session is running in that mode.

Then load the [`ha-issue-triage`](../../.agents/skills/ha-issue-triage/SKILL.md) skill with the `Skill` tool and
follow its procedure, passing `$ARGUMENTS` through as the dispatch argument (`locks`, `unlock <issue#>`, a bare issue
number, `stop`, or nothing for the full flow).
