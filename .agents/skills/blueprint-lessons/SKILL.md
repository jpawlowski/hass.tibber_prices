---
name: blueprint-lessons
description: >-
  Keep what this repository learned — from a fixed bug, a repeated correction, or a procedure that had to be
  rediscovered — where the next agent working on that code will meet it, without growing a pile of rules nobody
  reads. Use when asked to "remember this", "don't do that again", "from now on", "write a skill for this", "add a
  project rule", "why does this keep happening", after fixing a bug, or when the developer corrects the same thing a
  second time. SYMPTOMS — load this if you are about to: fix a bug without checking where else the same mistake sits;
  save a project rule only to your own memory; write a lesson as prose where a test or a lint rule could enforce it;
  create a new project skill or instructions file where an existing one could take the rule; copy a shipped rule into
  a project file; or put an issue number into a rule as its justification.
---

# Keep the lessons

A test protects the one place it checks. A lesson protects every place an agent could repeat the mistake — but only if
it lives where the next agent working on that code will meet it.

**Read first:** the rule-versus-procedure split in `AGENTS.md` › _Where the rules live_ and the comment gates in
[`blueprint.comments`](../../instructions/blueprint.comments.instructions.md). Decisions — a trade-off that was
chosen — are [`blueprint-decisions`](../blueprint-decisions/SKILL.md), not this.

## 0. Most lessons need no file

Every rule in prose costs context in every session that loads it, and a set nobody can survey is one agents stop
following. Growth is the failure mode to guard against, not forgetting.

- **The default for a fixed bug is a regression test and a commit body that names the cause — nothing else.**
- A lesson earns prose only when **all three** hold: the same mistake can recur in code that does not exist yet or
  that no test covers; an agent would plausibly make it, because nothing in the code or the shipped rules points the
  other way; and no check (§2) can catch it. **The strongest evidence for the first is that it already happened
  twice** — step 3 in §1 looks for that.
- **A rule goes into a file that already exists.** A new instructions file needs an area no project file covers yet; a
  new skill needs a procedure of several steps with a trigger no existing skill has — capturing a payload from this
  device, debugging this integration's own calculation. A single rule is never a skill.

## 1. After a bug fix: the class, not the case

1. **Name the class** in one sentence — "a sensor reads `coordinator.data[key]` without a default", not "the PM2.5
   sensor crashes" — and use that sentence in the commit body, so the next agent's search finds it.
2. **Sweep for siblings** before fixing: the same pattern in other platforms, entities, code paths, config flow steps.
   `rg` for the shape, not the symptom.
3. **Check whether it was fixed before.** Without a rule in place, the history is the only memory:

   ```bash
   git log -n 20 --oneline -i --grep '<root cause words>'          # commit bodies that named the same cause
   git log -n 20 --oneline -G '<the pattern>' -- custom_components/ # commits that added or removed the shape
   gh issue list --state closed --search '<symptom>'                # only if git finds nothing
   ```

   A revert, a second `fix:` to the same function, or a closed issue with the same symptom means it came back — and,
   if an agent could make it again elsewhere, the lesson needs a home (§2). One earlier fix of a different cause in the
   same file does not.

4. **Regression test** per [`ha-testing`](../ha-testing/SKILL.md).

## 2. Where a lesson goes

Cheapest durable home first. Take the first that can hold it:

| Home                                                                                          | When                                                                                                                  |
| --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| A check that fails — a Ruff `banned-api` entry, a test over every `EntityDescription`, a hook | Whenever the mistake has a shape a tool can recognise. Nobody has to remember it                                      |
| The area's project instructions file (§3)                                                     | The mistake belongs to an area of the code and no check catches it                                                    |
| A SYMPTOMS clause in a project skill's description                                            | The mistake happens during a kind of task, whatever file it touches                                                   |
| A code comment with the issue URL                                                             | Only a workaround for an external bug ([`blueprint.comments`](../../instructions/blueprint.comments.instructions.md)) |
| A decision record                                                                             | Only when a trade-off was chosen ([`blueprint-decisions`](../blueprint-decisions/SKILL.md))                           |
| `AGENTS.md`                                                                                   | Only when it bears on most sessions — `AGENTS.md` costs context in every one                                          |

Never only in your own memory — `AGENTS.md` › _When instructions conflict with a request_ says why.

## 3. The structure: lessons belong to an area, never to a bug

There is **no regressions skill**, no file per bug, and no reference file per regression. A list of past bugs grows
with every fix, an agent cannot tell which entry applies to the code in front of it, and none of it loads at the moment
it would help. A lesson is attached to the **area of the code** where the mistake can happen again, so it loads exactly
when an agent works there.

The whole project set, and nothing besides it:

```text
.agents/instructions/<prefix>.<area>.instructions.md   rules for one area of the code, path-scoped
.agents/skills/<prefix>-<task>/SKILL.md                procedures for a task the shipped skills do not cover
.agents/skills/<prefix>-<task>/references/<topic>.md   long background that one procedure needs — rarely
AGENTS.md                                              the few rules that bear on most sessions
```

- **`<prefix>`** is the integration's short name, the same for every file: `tibber`, `myinverter`.
- **`<area>`** follows the integration's own packages and the shipped instructions files it extends: `coordinator`,
  `api`, `entities`, `config_flow`, `translations`, or one of the integration's own packages (`periods`, `cards`).
  One file per area; its `paths` are that area's folders; it adds to the matching `blueprint.<area>` file and never
  repeats it.
- **`<task>`** names something someone does: `tibber-periods` (change or debug the period calculation). Not a topic,
  not a bug.

Inside an instructions file, every lesson is one bullet in a section `## Traps`, at the end:

```markdown
## Traps

- **Read the subscription phase from its status, never from a missing `current` price.** A contract that has not
  started yet has no current price either, and was shown as expired.
```

The rule, then one sentence of why — no issue number, no date, no story; the commit carries those.

**Expect a handful of files, not dozens:** zero to five instructions files and zero to three skills.

### A lesson no single file owns

Most still have one place they start from. Take the first that fits:

- **It is about data that reaches many files** — the vendor sends local times, a price is gross per kWh → make the
  code carry it first: normalise where the data enters, so no other file can get it wrong. The rule then belongs to
  that area (`api`, `coordinator`), and a test there holds it.
- **It happens during a task, whatever file it touches** → the project skill for that task, if one exists; otherwise
  the area file of the files that task changes.
- **It is a word of the domain** → `docs/development/GLOSSARY.md` (`haci-grill`, where the plugin is on).
- **It holds in almost every session** → `AGENTS.md`.

The list is closed: no `LESSONS.md`, no rules folder of its own, no second always-loaded file, no nested `AGENTS.md`.
The routing table in `AGENTS.md` is the one index — every project file has a row there. `script/skills-check` enforces
it for instructions files; a project skill's row is yours to add.

### Create, extend, or nothing

Search first — `.agents/skills/<prefix>-*`, `.agents/instructions/<prefix>.*`, and the rule's own words across
`.agents/` with `rg`:

- **A shipped file already says it** → nothing to write. If the agent ignored it, the shipped description or SYMPTOMS
  clause may be what failed — worth reporting upstream.
- **A shipped rule is wrong for every integration** → propose the change to the blueprint repository (never to a Home
  Assistant one, [`AI_POLICY.md`](../../../AI_POLICY.md)).
- **A shipped rule is wrong only for this project** → a bullet in the area's project file that states the deviation
  and why. Never edit the shipped file in place ([`.agents/README.md`](../../README.md)).
- **The area's project file exists** → add the bullet to its `## Traps`.
- **It does not** → create it with the frontmatter from
  [`blueprint.markdown`](../../instructions/blueprint.markdown.instructions.md), and add its row to the routing table
  in `AGENTS.md`.

## 4. A correction from the developer

Propose where it goes (§2) and its wording in the chat, and write it once the developer agrees — or right away if they
asked you to remember it. Offer it as its own commit, so a parallel session meets it through the normal review rather
than mid-task.

## 5. Keeping project rules current

- **A correction runs over every copy.** Search the rule's words across the repository and fix every place in the same
  commit.
- **A rule found false while editing the code it governs** is fixed in that change.
- **After a template-sync pull request or a Home Assistant version bump**, check the project's own files against the
  shipped ones they extend: a shipped file may now cover them, or contradict them.
- **Prune** whenever a rule goes in, and with every release review ([`ha-quality-review`](../ha-quality-review/SKILL.md)):
  a rule a check now enforces, or that the code no longer needs, goes; bullets that state one rule twice merge. Past
  about fifteen bullets in one `## Traps`, consolidate before adding. A shorter set that is followed beats a complete
  one that is not.
- Validate with `script/skills-check` and `script/lint`.
