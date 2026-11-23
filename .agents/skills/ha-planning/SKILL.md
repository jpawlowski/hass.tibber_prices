---
name: ha-planning
description: >-
  Plan a large change to this Home Assistant custom integration before writing code, or record an architectural
  decision. Use when asked to "create a plan", "plan this feature", "how should we approach", "propose an
  architecture", "write an ADR", "document this decision", "record a decision", "supersede a decision", "should we use
  library X or write our own client", or whenever a change would touch more than about ten files or alter the
  integration's structure. Covers when a plan is mandatory, the phased plan format, where plans live, when a decision
  is worth recording, and the decision record format and index. SYMPTOMS — load this if you are about to: start a
  refactor spanning more than ten files without confirmation; write a plan whose phases name no files; write one in
  prose nobody will finish reading; create a planning markdown file outside `.agents/scratch/`; or make a
  hard-to-reverse architectural choice without recording why.
---

# Plan changes and record decisions

## Reference files

| File                                                               | When to read                                          |
| ------------------------------------------------------------------ | ----------------------------------------------------- |
| [`references/decision-records.md`](references/decision-records.md) | Writing or superseding a decision record, or its rule |

## When a plan is required

| Situation                                        | What to do                                             |
| ------------------------------------------------ | ------------------------------------------------------ |
| Single feature or fix, up to ~8 files            | Just implement it completely; no plan needed           |
| Several independent features                     | Implement one at a time, suggest a commit between each |
| >10 files, or an architectural/structural change | **Write a plan and get explicit confirmation first**   |
| A choice with long-term consequences             | Write the plan _and_ record the decision               |

Do not start a large refactor because it seems obviously right. The developer decides scope.

A plan can only be as good as the requirements under it. If you cannot state the goal back in one sentence, or the
phases would encode a guess, run [`ha-grill`](../ha-grill/SKILL.md) first — its brief is the input this plan needs.

## Writing the plan

Plans are working documents, not deliverables. Put them in `.agents/scratch/` — that directory is gitignored and exists for
exactly this. Do not create markdown files elsewhere in the repository without being asked.

Structure:

```markdown
# Plan: <what and why in one line>

## Goal

<One line: what changes for the user when this is done.>

## Current state

<Bullets. What exists today, with file references, and what specifically is in the way.>

## Approach

<Bullets. The chosen approach, and what you deliberately did not choose.>

## Phases

### Phase 1 — <name>

- **Files:** `custom_components/<domain>/coordinator/base.py`, …
- **Changes:** <specific edits>
- **Verification:** `script/test tests/test_init.py`, and <what to check in the UI>
- **Independently shippable:** yes / no

### Phase 2 — …

## Breaking changes

<None, or: what breaks and the migration path. See ha-breaking-changes.>

## Risks and open questions

<Each one: the question, who answers it, and what it blocks. "None" is a valid section.>
```

**Write it to be read, not to be complete.** A plan over ~10 files exists to be confirmed before implementation — and
a plan nobody finishes reading gets confirmed anyway, which turns that gate into a formality and hands the agent a
mandate the developer never actually gave.

- Notes, not prose. Fragments beat sentences; drop the grammar that carries no information.
- One screen per phase. If a phase needs more, it is two phases.
- Do not restate the request, the repository, or the brief. When a [`ha-grill`](../ha-grill/SKILL.md) brief exists,
  link it — its **Decided** and **Open** lists do not get copied in.
- Concision is about wording, never about scope: what you are not doing still has to be written down.

Rules that make a plan useful:

- Every phase names actual files. "Refactor the coordinator" is not a phase.
- Every phase ends in a verifiable state — the test suite passes and Home Assistant still starts.
- Order phases so the risky, uncertain part comes early. Discovering the approach is wrong in phase 1 is cheap; in
  phase 5 it is not.
- Keep phases independently reviewable, ideally one commit each.
- **Name the seams**, once, under Approach: the shapes one phase fixes and the later ones are then stuck with. Here
  that is almost always the coordinator's data shape, the API client's exception types, and the unique ID scheme.
  Together with what you are not doing, this is the part the developer should actually check — a wrong seam is
  trivial to change while it is a line in a plan, and a migration once three phases have been built on it.
- Say what you are **not** doing. Scope creep in a plan is scope creep in the implementation.

Present the plan, wait for confirmation, then implement phase by phase. Report deviations from the plan as they happen
rather than at the end.

## Recording a decision

A decision is recorded in `docs/development/decisions/` — one file per decision, listed in that folder's generated
`README.md` — when it is expensive to reverse and the reasoning would otherwise be lost:

- Third-party library vs. own API client (this is the most common one — see the decision process in `AGENTS.md`).
- Polling vs. push, and the update interval.
- Data structure of `coordinator.data`, or the shape of `entry.data`.
- Device modelling: one device per entry, per subentry, or a hub with children.
- Unique ID scheme.
- Anything you had to argue yourself into.

Do **not** record: routine implementation choices, anything the code already makes obvious, a restatement of a Home
Assistant convention, or a breaking change made before `1.0.0` — those are expected at that stage, and their record is
the `BREAKING CHANGE:` footer in the commit ([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)).

The bar is all three of: hard to reverse, a genuine trade-off rather than the one sensible option, and surprising to a
reader who was not there — the test for the last one: without the record, would the choice read as an oversight
someone fixes? **Most sessions produce no record, and that is the normal outcome** — a log padded with decisions that
made themselves is one nobody reads when a real one is in it.

Before deciding, read the index, as `AGENTS.md` › _Documentation_ says — a new decision must not silently contradict
an old one.

The format, superseding, the rule a decision produces and the index script:
[`references/decision-records.md`](references/decision-records.md).

## Handoff

When a plan spans more than one session, leave the plan file in `.agents/scratch/` with phase checkboxes updated, so the
next session can pick it up without re-deriving the context.

**`.agents/scratch/` is gitignored**, so it survives the next session but not a fresh clone, a second machine, or a
second contributor. Before the work stretches that far, move anything that must outlive it to its real home: a
hard-to-reverse choice into a decision record, the project's own vocabulary into
`docs/development/GLOSSARY.md` ([`ha-grill`](../ha-grill/SKILL.md)), and everything else into the commit messages of
the phases already shipped. What is left in the scratch file should be losable.
