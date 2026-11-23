---
name: "Source Comments"
description: "When a comment is warranted, how long it may be, and where longer explanations belong instead"
applyTo: "**"
paths:
  - "**"
---

# Comment Instructions

**Applies to:** every file in this repository, in whatever comment syntax it has — `#`, `//`, `<!-- -->`, docstrings.

A comment is a claim that the reader needs something the code cannot give them. Usually that claim is false, and an
unnecessary comment is not free: it has to be kept true, it goes stale without failing anything, and it tells the next
reader "this line is unusual" when it is not. **The default is no comment.**

## The five gates

Write the comment only if it passes **all five**. One failure is enough to drop it.

1. **Neighbourhood** — do the sibling entries at the same nesting level carry comments? If they do not, the file's
   convention is "no commentary here", and a lone comment breaks it. Match the file you are in, not your own habit.
2. **Not a restatement** — a comment says _why_, never _what_. If it paraphrases the identifier or the line below it,
   delete it and let the name carry the meaning; rename the thing if the name cannot.
3. **Not lookupable** — could the reader find this in seconds in the reference for a tool they are already using, in
   the language docs, or in the schema the file is validated against? Then it is not yours to repeat. Having had to
   research it once is not a reason to persist it — that cost is already sunk, and copying it here only creates a
   second copy to keep true.
4. **Still true in a year** — apply the half-life test. "No official feature exists yet", "currently the newest
   version", "fixed in the next release" rot silently and mislead precisely when someone finally reads them. A
   short-lived fact goes in the commit message or a tracked issue, never in a file.
5. **Two lines at most** — anything longer is documentation, not a comment. Move it (see the table below) and leave
   at most a one-line pointer behind.

## What does earn a comment

- A **workaround for an external bug or limit**, with the issue URL. Without it, the next reader "cleans up" the
  workaround and reintroduces the bug — this is the single most valuable comment there is.
- A **deliberate deviation** from the approach a reader would expect, and what breaks if it is undone.
- An **ordering, timing or lifecycle constraint** that is not visible from the lines involved.
- The **provenance of a value** that cannot become a named constant — a protocol quirk, a vendor-mandated rounding.
  Prefer the named constant; reach for the comment only when there is nowhere to put one.
- A **security or safety restriction** that looks over-cautious out of context.
- Every `# noqa: CODE` and `# type: ignore[code]` — the code plus the reason, per `blueprint.python`.
- **Docstrings** in Python: module, class and public function. These are structure, not commentary, and Ruff enforces
  them.

## What never earns one

- Restating the code, banner separators (`# --- Setup ---`), or commented-out code — git already has it.
- **Change narration**: "changed from X", "new in v2", "added for issue #12". That is the commit message's job, and
  the file has no way to know when the statement stopped being interesting.
- General knowledge about Python, asyncio, Home Assistant, Docker, VS Code or devcontainer features — the reader has
  the same docs you do.
- Anything the file's schema, its `EntityDescription`, or a translation key already declares.
- A `TODO` with no tracked issue behind it. Fix it, file it, or leave it out.
- **Agent reasoning traces** — alternatives you rejected, what you tried first, why you looked something up. That
  belongs in the answer to the developer, not in their repository.

## Where the information goes instead

Dropping a comment is not dropping the knowledge. Route it:

| The information                                     | Home                                                     |
| --------------------------------------------------- | -------------------------------------------------------- |
| Why this change, now, and what it replaced          | The commit message body — see `blueprint.commit-message` |
| An architectural decision and its alternatives      | a record in `docs/development/decisions/`                |
| How the layers fit together                         | `docs/development/ARCHITECTURE.md`                       |
| How to carry out a recurring task                   | An agent skill under `.agents/skills/`                   |
| A rule agents must follow while editing a file type | An instructions file here                                |
| What a user has to do or expect                     | `docs/user/`                                             |
| What a function does, takes and returns             | Its docstring                                            |
| Working notes for the current task only             | `.agents/scratch/` — never committed                     |
| A mistake an agent must not repeat                  | the `blueprint-lessons` skill                            |
| Public knowledge you happened to look up            | Nowhere. Say it once in chat and let it go.              |

The last row is the one that gets ignored. Research does not need a resting place just because it was work; store it
only if a **future** decision will turn on it, and then store the decision, not the search result.

**When in doubt, leave it out and put it in the commit message.** It reaches exactly the person who needs it, at the
moment they go looking, and it cannot go stale — the code it describes is frozen next to it forever.

## Per-format conventions

| Format                                  | Syntax     | Convention here                                                                                                                                 |
| --------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Python                                  | `#`, `"""` | Docstrings are required; inline comments are rare. Full sentences, capitalised, ending in a period.                                             |
| YAML under `config/` and `.github/`     | `#`        | The one place comments are conventional — a header per logical section. Values a schema already documents still get none.                       |
| JSON (`manifest.json`, translations, …) | none       | The format has none. Say it in the schema, or in `docs/`.                                                                                       |
| JSONC (`.devcontainer/`, `*.jsonc`)     | `//`       | Comments are _possible_ here, which is not the same as wanted. Gate 1 decides, and the answer is usually no.                                    |
| Shell in `script/`                      | `#`        | The header block from `blueprint.shell` (name, description, usage); in the body only for non-obvious logic. Shellcheck disables carry a reason. |
| Markdown                                | `<!-- -->` | Only for machine-read markers such as `blueprint-only`, `repo-role` and `ha-marketplace:exclude-start`/`-end`. Prose explains itself.           |
