---
name: blueprint-decisions
description: >-
  Record, supersede or look up an architectural decision in this repository's decision records, and keep their index
  current. Use when asked to "write an ADR", "document this decision", "record a decision", "supersede a decision",
  "why did we choose X", or when a plan reaches a choice that is hard to reverse — library versus own API client,
  polling versus push, the coordinator's data shape, the device model, the unique ID scheme. Covers the bar a decision
  must clear, where records live, the file format, superseding, the rule a decision leaves behind, and the index script.
  SYMPTOMS — load this if you are about to: edit a record that has already landed; record a choice that made itself;
  record a breaking change made before 1.0.0; write the index by hand; or make a hard-to-reverse choice without reading
  the index first.
---

# Record decisions

## Reference files

| File                                                               | When to read                                          |
| ------------------------------------------------------------------ | ----------------------------------------------------- |
| [`references/decision-records.md`](references/decision-records.md) | Writing or superseding a record, or the rule it makes |

## When a decision is worth recording

Record it when it is expensive to reverse and the reasoning would otherwise be lost:

- Third-party library versus own API client — the most common one; the criteria are in `AGENTS.md` › _Custom
  Integration Flexibility_.
- Polling versus push, and the update interval.
- The data structure of `coordinator.data`, or the shape of `entry.data`.
- Device modelling: one device per entry, per subentry, or a hub with children.
- The unique ID scheme.
- Anything you had to argue yourself into.

Do **not** record routine implementation choices, anything the code already makes obvious, a restatement of a Home
Assistant convention, or a breaking change made before `1.0.0` — its record is the `BREAKING CHANGE:` footer
([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)).

The bar is all three of: hard to reverse, a genuine trade-off rather than the one sensible option, and surprising to a
reader who was not there — would the choice, without the record, read as an oversight someone fixes? **Most sessions
produce no record, and that is the normal outcome.** A log padded with decisions that made themselves is one nobody
reads when a real one is in it.

Before deciding, read the index, as `AGENTS.md` › _Documentation_ says: a new decision must not silently contradict an
old one. The format, superseding, the rule a decision produces and the index script are in the reference above.
