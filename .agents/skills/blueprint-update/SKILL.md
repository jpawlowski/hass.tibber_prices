---
name: blueprint-update
description: >-
  Carry over the blueprint changes the weekly template sync cannot deliver — the steps an integration repository has
  to take by hand, and the blueprint's edits to the files .templatesyncignore keeps out of the sync, such as AGENTS.md,
  the sync workflow and the developer documentation. Use when asked to "update from the blueprint", "what changed in
  the blueprint", "pull in the blueprint changes", "are we up to date with the template", after merging a template
  sync pull request, or when a sync pull request or the tooling skill says a step has to be copied by hand. Covers the
  manual-steps list, script/blueprint-update, merging a blueprint change into a file the project owns, and recording
  what was gone through. SYMPTOMS — load this if you are about to: copy a whole blueprint file over a project-owned
  one; remove a path from .templatesyncignore to get one change through; port a blueprint change with the
  blueprint's domain or class prefix still in it; or run this in the blueprint itself.
---

# Updating from the blueprint

**Read first:** [`blueprint-tooling`](../blueprint-tooling/SKILL.md) § Template sync, for what the sync does and what
`.templatesyncignore` keeps out of it. This skill is the other half: what the sync leaves for a person.

This only applies in an integration repository made from the blueprint. In the blueprint itself, or in a copy that
still has `initialize.sh`, there is nothing to update from — `script/blueprint-update` refuses, and so should you.

| File                                                       | When to read                                          |
| ---------------------------------------------------------- | ----------------------------------------------------- |
| [`references/manual-steps.md`](references/manual-steps.md) | Step 2 — the list of steps, each with how to check it |

## Procedure

1. **Merge the open template sync pull request first**, after reviewing it as usual. It brings this skill, the
   manual-steps list and `script/blueprint-update` up to date; working from an older copy misses the newest steps.
2. **Go through the manual steps.** For each entry in [`references/manual-steps.md`](references/manual-steps.md), run
   its check. A step whose check passes is done, and so is one listed under `skipped` in
   `.agents/blueprint-update.json`. Present the remaining ones to the developer one at a time — what it does and why,
   in their words rather than the blueprint's — and apply what they accept. A step they decline goes into `skipped`
   with its id, so the next run does not ask again.
3. **Review the watched files.** `script/blueprint-update` prints, per file, what the blueprint changed since the
   commit this repository last went through, already spelled with this repository's domain, title, class prefix and
   repository name — the ones `initialize.sh` recorded in `.agents/blueprint-update.json`. The first run has no record yet and shows the whole difference to the blueprint instead, which
   includes everything the project changed on purpose — read it as a list of candidates, not as a patch.
4. **Merge each change into the project's file, never over it.** These files are excluded from the sync because the
   project owns them. Port a hunk where it fits the project, adapt its wording to what the project already says, and
   leave out what the project decided differently. When a hunk is unclear, ask; when it conflicts with something the
   project wrote, show both and let the developer choose.
5. **Validate** with the loop in `AGENTS.md` — `script/lint` and, if code or configuration changed, `script/test`.
6. **Record the blueprint commit** with `script/blueprint-update --record`, so the next run shows only what is new.
   Commit the record together with the changes, as `chore(template): carry over blueprint changes` with one bullet
   per file or step in the body — and only when the developer asks for the commit, as `AGENTS.md` § Commits says.

## Rules

- **Do not remove a path from `.templatesyncignore`** to get a change through. The exclusion protects the project's
  version from the sync's `-X theirs`; lifting it hands the whole file back to the blueprint every week.
- **No blueprint name survives a port.** `script/blueprint-update` renders the blueprint's names away; text you write
  yourself while adapting a hunk must not reintroduce them either.
- **A step is not done because it looks done.** Run its check; the list is ordered by date, and an older repository
  may lack steps a newer one never needed.
