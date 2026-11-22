---
name: ha-grill
description: >-
  Interview the developer until the requirements of a change are actually settled, before any code is written.
  Use when asked to "grill me", "roast me", "interview me", "ask me what you need to know", "I want to build an
  integration for <device>", "let's add <feature>", "challenge my idea", or whenever a request names a goal but
  none of the decisions underneath it. Covers when to run the interview, the one-question-at-a-time loop, the
  Home Assistant decisions that must be closed before code, the tone switch between direct and roast, when to
  stop, and the brief that hands off to the other skills. SYMPTOMS — load this
  if you are about to: start implementing from a one-line feature request; send a wall of numbered questions;
  ask something the repository already answers; ask in Home Assistant vocabulary the developer has no reason to
  know; accept "like the example one" as a requirement; agree with a design you can already see a problem with;
  or keep the brief in your head until the end.
---

# Grill the developer before writing code

An agent that builds exactly what was asked builds the wrong thing surprisingly often. The request is the tip of a
decision tree, and every branch left unasked gets guessed.

Here the guesses are expensive in a specific way: unique IDs, entity IDs, `entry.data` and the coordinator's data
shape reach users with the first release and are breaking to change afterwards
([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)). A question costs a minute now; the same question answered
by a migration costs a release. **Interrogate first — that is the whole point of this skill.**

## When to run it

| Situation                                                            | Grill?                                                                                                |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Fresh blueprint, no real code yet                                    | **Yes** — it produces the facts `blueprint-scaffold` demands                                          |
| An existing integration about to be imported                         | **Yes** — before its baseline is taken; the install base decides how much of the import is affordable |
| First real feature after an import or migration                      | **Yes** — the imported code answers less than it looks like                                           |
| A new platform, entity set, service action or flow step              | Yes, once more than two or three decisions are open                                                   |
| A one-line request whose scope you cannot state back in one sentence | Yes                                                                                                   |
| A bug with a known cause                                             | No — debug it ([`ha-coordinator-debug`](../ha-coordinator-debug/SKILL.md))                            |
| A complete spec is already on the table                              | No. Say so, name the two or three real gaps, ask only those.                                          |

Do not run it as a ritual. If nothing you could ask would change a file, you are stalling, not scoping.

## The loop

1. **Read before you ask.** Every question the repository already answers spends the developer's patience on
   nothing. Check `manifest.json`, the coordinator's `_async_update_data`, the existing `EntityDescription` sets,
   `translations/en.json`, the index in `docs/development/decisions/` and recent commits first. Then _state_ what you found and
   ask for confirmation instead — "you poll every 30 s and there is no push path; still true?" is one word to answer.
2. **One question at a time.** A numbered list of twelve gets one reply covering three of them, and the other nine
   turn into assumptions. Ask, wait, use the answer to pick the next question.
3. **Every question carries your recommendation.** "A, B or C? I would take B, because the payload already gives us
   the serial." The developer confirms in a word or corrects you in a sentence — either way you learn more than an
   open question would have got you.
4. **Follow the dependencies, do not tour the topics.** Resolve what other decisions hang off first: push or poll
   before the update interval, one device or many before the unique ID scheme, library or own client before anything
   about the API surface. A decided branch usually kills three questions further down.
5. **Say it when you disagree.** If an answer creates a problem later — a unique ID that will not survive a router
   swap, an attribute that should be an entity — name it in the same turn, with the consequence. Silent compliance
   here is the failure this skill exists to prevent.
6. **Show the running state every few questions**, read back from the brief file you are already appending to. A
   short "settled so far" list lets the developer catch a misunderstanding at question 8 instead of in the diff.

**Stop when no remaining question would change a file** — not at a question count, and not when the developer sounds
tired. A new integration usually takes twenty to forty questions; a second sensor takes four. If they break off early,
that is their call: record what is unresolved under **Open** and say what it blocks.

## Ask in the developer's language

The bank below is written in this project's vocabulary because it is a working list for you. **The question you
actually put to the developer is not.** Someone can know their device or service inside out and never have met a
coordinator — see "Do not assume the developer speaks Home Assistant's vocabulary" in
[`AGENTS.md`](../../../AGENTS.md). Translate on the way out, and translate the answer back yourself.

| Do not ask                                 | Ask                                                                                                 |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Push or poll, and at what interval?        | Does it tell us when something changes, or do we have to ask? How often does the value really move? |
| What should the unique ID be derived from? | Is there a number or code on it that stays the same even after a reset?                             |
| Should this be `assumed_state`?            | After we send a command, can we read back whether it actually happened?                             |
| Which values need a `state_class`?         | Which of these numbers should Home Assistant keep long-term history and statistics for?             |
| Entity or attribute?                       | Should this stand on its own in a dashboard and in automations, or is it just extra detail?         |
| Does this need an options flow?            | Which settings must be changeable later, without deleting the integration and adding it again?      |

When the decision has to be recorded in this project's terms, give both: "that means `local_push` — Home Assistant
will not poll it." The developer picks up the word from a decision they just made, which is the only way it sticks.

## What has to be closed before code

The question bank is the working list — do not improvise it from memory:

| File                                                         | When to read                                                                 |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| [`references/question-bank.md`](references/question-bank.md) | Every grill. Pick the section matching the change, and the "never ask" list. |

The bank is organised by change type: new integration, new platform or entity, new service action, setup and config
flow change, anything touching existing installs, and importing an integration that already has users. It also lists
what **not** to ask — questions this project's rules have already decided, where asking invites an answer you would
have to overrule anyway.

## Tone

**Default: direct.** No opening praise, no "great question", no agreeing with something you can see a problem with.
"Sounds good" is not information — if part of the idea is genuinely right, say which part and move on. Equally: do
not manufacture objections to look rigorous. Direct means the assessment is honest in both directions.

**`--roast`** — the developer asked for it, in the invocation or in plain words ("roast me", "be brutal", "don't be
nice"). It changes the wording, never the substance:

- Every jab still lands on something concrete — a file, a line, a decision, a consequence. A roast without a
  reference is just noise, and the developer cannot act on it.
- The design, the code and the plan get roasted. The developer never does.
- The questions do not get fewer or softer. Harder tone, same rigour, same recommendations.

Both modes obey [`AI_POLICY.md`](../../../AI_POLICY.md): do not claim to have verified something you did not run.

## The brief — written as you go, not at the end

An interview that produces no artefact was a chat. **Open `.agents/scratch/grill-<topic>.md` at the first settled
decision and append to it as each one lands** — the same gitignored directory plans live in
([`ha-planning`](../ha-planning/SKILL.md)).

Writing it up at the end is the failure mode this section exists to prevent. Forty questions outlast a context
window: what is on disk survives a summarisation, a crash, and tomorrow, and what is only in the conversation does
not. Appending also forces the decision to be stated in one line at the moment it is made, which is when it is still
possible to notice that it was never actually settled.

The file, not your memory, is the "settled so far" list that loop rule 6 shows the developer.

```markdown
# Brief: <what is being built>

## Decided

- <decision> — <the reason, one line>

## Rejected

- <option> — <why it lost>

## Open

- <what the developer deferred> — blocks <what>

## Terms

- <the developer's word> — <what it means here, one line>

## Next

<skill to load, and the first file to touch>
```

Being wrong in the **Decided** list is the cheapest bug this project has — but only while it is still a list. Read it
back to the developer before implementing.

## Words that outlive the conversation

The developer's domain has words of its own — what the vendor calls a zone, a session, a profile, a slot; which of
five readings is "the" temperature; what "presence" means in this product. **These end up in translation keys, entity
names and the documentation, where they become user-visible and breaking to change** — so a term used loosely in the
grill is a rename in six months.

Pin one the moment it is settled, in one tight line, in the brief. Once three or four have accumulated and they will
outlive this feature, offer the developer a `docs/development/GLOSSARY.md` and move them there — permanent
documentation is created on their yes, never silently ("Documentation" in [`AGENTS.md`](../../../AGENTS.md)).

Two things do not belong in it: **Home Assistant's own vocabulary**, which is one lookup away and is handled by
explaining it in the conversation instead, and anything that is a specification rather than a definition. A glossary
entry says what a word means, not what the code does with it.

## Hand off

| The brief describes                                      | Continue with                                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------------------------- |
| A whole integration on the fresh blueprint               | [`blueprint-scaffold`](../blueprint-scaffold/SKILL.md)                           |
| An integration that already has users, being migrated in | [`blueprint-import`](../blueprint-import/SKILL.md) — the brief feeds its phase 0 |
| More than ~10 files, or a structural change              | [`ha-planning`](../ha-planning/SKILL.md) — plan, then confirm                    |
| A choice that is expensive to reverse                    | `ha-planning` → a record in `docs/development/decisions/`                        |
| Entities or a platform                                   | [`ha-entity-platform`](../ha-entity-platform/SKILL.md)                           |
| A service action                                         | [`ha-service-action`](../ha-service-action/SKILL.md)                             |
| Setup, options, reauth or discovery                      | [`ha-config-flow`](../ha-config-flow/SKILL.md)                                   |
| Anything reaching installs that already exist            | [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md) **first**               |

Small and fully settled goes straight to implementation — the brief has already done the planning a plan would repeat.

## Do not

- Do not ask what the repository, the manifest or a decision record already states. Confirm it in one line instead.
- Do not send a wall of questions, and do not ask one without a recommendation attached.
- Do not ask in vocabulary the developer never signed up for, and do not read a vague answer as agreement — it more
  often means the question was in the wrong language.
- Do not accept "like the example one" as an answer. The blueprint's demo platforms are demonstrations of the file
  layout, not of anyone's device; carrying their shape over ships entities nobody wanted.
- Do not accept an invented payload. If nobody has seen a real response, that goes under **Open**, not into a guess.
- Do not hold the brief in your head until the end. Append as each decision lands, or a long grill loses the early
  half of itself to a context window.
- Do not close a grill without a brief and a named next step.
- Do not create `docs/development/GLOSSARY.md` unasked, and do not fill it with Home Assistant's vocabulary.
- Do not grill a bug report, and do not grill again over a spec that is already complete.
- Do not soften a finding because the developer sounds attached to the idea, and do not turn `--roast` into an
  insult with no file attached to it.
