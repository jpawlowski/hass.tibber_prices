# Decision records

For [`blueprint-decisions`](../SKILL.md), which says when a decision is worth recording. This is how.

A **record** says why a choice was made, and is not edited once it lands. A **rule** says what holds now, and is what
an agent follows while it works. Keeping them apart means a superseded decision never reaches an agent's context,
while the rule it left behind still leads back to its reasoning.

## Where

| Decisions about                              | Folder                        |
| -------------------------------------------- | ----------------------------- |
| this integration                             | `docs/development/decisions/` |
| the blueprint itself (only in the blueprint) | `docs/blueprint/decisions/`   |

Each folder has a `README.md` index that `script/decisions` writes — part of `script/lint`; `script/lint-check`
fails while it is out of date. Never edit the index by hand; how agents read it is in `AGENTS.md` › _Documentation_.

## The file

Name and `id`: `YYYYMMDD-slug.md`, the date the decision was made and a few words. A date rather than a running
number, so two branches — two agents working in parallel — cannot take the same one.

```markdown
---
id: 20261122-own-api-client
status: accepted
rule: .agents/instructions/<prefix>.api.instructions.md
---

# Write an own API client instead of the vendor library

## Context

What forced a choice, and the constraint that made it non-obvious.

## Decision

What was decided, stated plainly, and why this option won.

## Consequences

What this now obliges the code to do; what becomes harder, accepted as the trade-off.
```

| Field           | Value                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------- |
| `id`            | the file name without `.md`                                                                       |
| `status`        | `accepted`, `rejected` (decided against — kept so nobody proposes it again unaware), `superseded` |
| `supersedes`    | the id, or a list of ids, this record replaces                                                    |
| `superseded-by` | set on the old record when a new one replaces it; required for `superseded`                       |
| `rule`          | the file or files holding the rule this decision produced, if any                                 |
| `migrated-from` | where a record moved from — an old `DECISIONS.md`, a section of an imported repository's docs     |

A decision still open is an issue, not a record — there is no `proposed`.

**Size:** about 250 words. Add a `## Considered options` section, one short paragraph per option, only when a rejected
option is likely to be proposed again — library versus own client is the typical case. A record moved in from
elsewhere keeps its text as it was.

Write `accepted` only for a decision the developer made. A record an agent drafts from someone else's reasoning — an
imported repository's comments, an old document — is shown to the developer before it is written.

## The rule it produces

Most decisions leave a rule behind: "use the own client in `api/`, never the vendor package". The rule goes where an
agent working on that code already looks:

- one area of the code → that area's project instructions file `.agents/instructions/<prefix>.<area>.instructions.md`
  ([`blueprint-lessons`](../../blueprint-lessons/SKILL.md) §3)
- the whole repository → `AGENTS.md`

Never put it into a `blueprint.*` instructions file — template sync replaces those. The rule ends with a line naming
its record, which `script/decisions` checks:

```text
Source: docs/development/decisions/20261122-own-api-client.md
```

and the record lists the rule file in `rule`.

## Superseding

In one change: write the new record with `supersedes`, set the old one's `status: superseded` and `superseded-by` —
the only edit an old record ever gets — and rewrite or delete the rule, so it names the new record in `Source:`. A
reversed decision stays in the folder; the index moves it to its history.

## An older single `DECISIONS.md`

A repository made before the decisions folder existed may still keep one `docs/development/DECISIONS.md`.
`script/decisions` passes without a folder. Moving over is the `decision-records` step of
[`blueprint-update`](../../blueprint-update/SKILL.md).
