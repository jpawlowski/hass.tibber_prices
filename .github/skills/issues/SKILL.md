---
name: issues
description: Triage/fix the GitHub issue backlog via branch + PR, with auto-merge on green CI for this session.
disable-model-invocation: true
---

Invoking this prompt is the explicit, session-scoped signal that turns on full autonomy for this run: merge each
pull request automatically once its checks are green, without asking for confirmation on every single one (the
opt-in condition the skill itself defines — see its "Merge autonomy" section). Say once, at the start, that this
session is running in that mode.

Then follow the [`ha-issue-triage`](../../.agents/skills/ha-issue-triage/SKILL.md) skill's procedure, using any
argument given after the command as the dispatch argument (`locks`, `unlock <issue#>`, a bare issue number, `stop`,
or nothing for the full flow).
