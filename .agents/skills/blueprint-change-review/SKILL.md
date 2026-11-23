---
name: blueprint-change-review
description: >-
  Review a change before it is committed and before its pull request leaves draft — simplify it, run the gates again,
  then have a context that did not write it review it, and on risk a second model of another family. Use when asked
  to "review my changes", "review this before I commit", "check the diff", "is this ready to merge", "get a second
  opinion", "run /simplify", before the first commit of a change, or before `gh pr ready`. Covers the step order and
  why, what the fresh reviewer gets, critical files, turning findings into one fix, the second review, and reporting
  what ran. SYMPTOMS — load this if you are about to: review a change in the session that wrote it; hand the reviewer
  your reasoning or the pull request description; start the review before the tests ran on the simplified code; or
  record an agent's review as human review.
---

# Review a change before it lands

The session that wrote a change reads it through the reasoning that produced it, and confirms itself. This procedure
puts a context that did not write the change between the work and the commit, after the cheaper checks have had
their say.

## Reference files

| File                                                           | When to read                                              |
| -------------------------------------------------------------- | --------------------------------------------------------- |
| [`references/reviewer-brief.md`](references/reviewer-brief.md) | Step 3 and step 5: it is the prompt the reviewer is given |

## When the pass runs, and over what

| Moment                                               | Range                                                                                              |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Before the first commit of a change, made or offered | the working tree against the merge base with `main`                                                |
| Before `gh pr ready`                                 | the commits after the last one with an `Agent-Review:` trailer; the whole branch when none has one |

Give the range as full SHAs — `git fetch origin main` and then `git merge-base origin/main HEAD` for the base, since a
local `main` can be stale or absent — so nothing that happens meanwhile moves what is reviewed. The last reviewed commit is found by its message, so a rebase or a merge of `main` does not lose it:
`git log --no-merges --grep='^Agent-Review:' -1 --format=%H origin/main..HEAD`, and the reviewer gets the commits
after it as `git log -p --no-merges <it>..HEAD ^origin/main`, which leaves out what `main` brought in — or, when the lookup
prints nothing, `git log -p --no-merges origin/main..HEAD`. A working-tree review
has no head SHA: run `git add --intent-to-add` on every new file first, because `git diff` does not show untracked
files, and leave the tree alone until the reviewer returns.

**The tier comes from the files, never from the size of the diff:**

- **Light** — every changed file is Markdown prose, and none is an instructions file or a critical file. Step 1 is
  your own reread for the four angles below, step 2 is `script/lint`, and step 3 is one reviewer on consistency.
- **Full** — everything else. One file outside the light list is enough.

## Critical files

A miss here costs more than a miss elsewhere, so the reviewer of a change that touches one runs on the strongest
model the tool offers, and the change earns the proposal in step 5. Name the ground when you call a file critical;
where it is unclear, it is.

- Anything on the list in _Breaking changes — warn before implementing_ in `AGENTS.md`, and the config entry's
  `VERSION` and migration.
- Credentials and access: the config flow's auth and reauth steps, diagnostics and their redaction, anything that
  logs a payload.
- Runtime dependencies in `manifest.json` → `requirements`.
- What guards the rest or runs code on its own: `.agents/hooks/`, `.claude/settings.json`, `.codex/hooks.json`,
  `.opencode/`, `.devcontainer/`, `.vscode/tasks.json`, `.pre-commit-config.yaml`, `.github/workflows/`,
  `.github/actions/`, `script/push-gate`, the release scripts and `release-please-config.json`. The paths
  `.claude/settings.json` denies agents edits to are the core of this list.
- Text that governs what an agent may do — commit, push, merge, post, close, or act without asking — wherever it
  stands: `AGENTS.md`, `CLAUDE.md` and `AI_POLICY.md`, and skills such as `ha-issue-triage`, `ha-release` and this one
  with its brief.

Where this repository's `AGENTS.md` names critical files of its own, that list decides.

## 1. Simplify

Read the change for four things and fix what holds: reuse of something the repository already has, dead weight, a
simpler shape, and the right level of abstraction. Bugs are step 3's. In Claude Code, `/simplify` runs exactly this
and edits the files; elsewhere, make the pass yourself or give those four questions to a subagent.

Do not skip it because the change looks small, and do not count on step 3 instead: the reviewer is told that style is
no finding.

## 2. Run the gates again

`script/lint`, `script/type-check` and `script/test`, plus whatever else the change calls for in
[`blueprint-tooling`](../blueprint-tooling/SKILL.md). Step 1 edits code and can change behaviour, so the tests have to
pass on what it left, and the reviewer should not spend its reading on what a gate already reports. `script/push-gate`
runs no tests.

Where the gates already passed on this tree and step 1 changed nothing, that run is step 2. A red gate is fixed and
step 2 runs again; step 1 does not.

## 3. Review in a fresh context

**Who:** a context that has none of this session's reasoning.

- Claude Code: first `/code-review --fix` for correctness bugs. It runs as a fork of this session and applies what it
  finds, so when it changed files, step 2 runs again. Then a subagent started with the brief, on the result — that is
  the fresh context, and the one that reads the repository's rules.
- Copilot, Codex, OpenCode, Cursor: a new chat, thread or session, with the brief pasted in.
- No way to start one: say so, and ask the developer to start the session. The absence of a reviewer never becomes
  the absence of a review.

**What it gets:** the brief, the range, the tier with the files that made it full or critical, and the commit
subjects as claims to check against the diff.

**What it does not get:** why you made the change, the pull request description, what you expect it to find, or what
you already checked.

## 4. From finding to fix

1. **Judge each finding.** A reviewer asked for gaps finds some in sound work too; take a finding over only when it
   holds. One you do not apply gets its reason in the commit body or the pull request. What `/code-review --fix`
   already applied is judged the same way, from its diff, and reverted where it does not hold.
2. **Fix the class, not the case** — _A fixed bug stays fixed_ in `AGENTS.md`: one fix, one commit once the change is
   committed.
3. **Fix pass.** Give the fix alone and every finding it answers to the reviewer that found them — continued where the
   tool can continue it, fresh with the brief otherwise. Rework after a review is hastier than the first draft.
4. **Three passes at most.** A P0 or P1 still open after the third goes to the developer with one line on its impact,
   and the commit or `gh pr ready` waits for their word.

## 5. A second review on another model family

A reviewer of the same family as the author shares its blind spots. Propose a second review in one line, with the
ground, when:

- the change touches a critical file;
- the pass found a P0 or P1, or two reviewers disagreed on a finding;
- a finding needed all three fix passes.

Otherwise propose nothing. It runs only on the developer's word — it spends their quota under their account — and the
work does not wait for the answer. Its findings go through step 4.

`script/second-review` runs it: it takes another installed agent CLI than the one this session runs in — signed in,
where the CLI can tell — exports the committed head into a temporary directory outside any checkout, and gives that
CLI the brief and the diff, to read and to run and write nothing. It reviews commits, so before the first commit a
fresh session of another family takes its place. The range is the whole branch; `--base` with the last commit an `Agent-Review:`
trailer marks narrows it. The script recognises a Claude Code session and one that sets `AI_AGENT`; in any other,
name the CLI with `AGENT_CLI`. A different CLI is not yet a different family — Copilot and OpenCode can run Claude
models — so name the model with `AGENT_MODEL` where the CLI's default may be the author's. Where the script cannot
run, a fresh session of another family with the same brief and range does the same.

## 6. Say what ran

- In chat: which steps ran, on which range, and which did not and why.
- In the commit that ends a pass — the first commit after a working-tree pass, or the last fix commit — a trailer
  `Agent-Review: <the steps that ran>`. It marks that commit itself as covered, which is where the next pass starts.
- In the pull request, the _Verification context_ line `Agent review` names the steps. It is never written into
  `Human review`: an agent's review is not a person's ([`AI_POLICY.md`](../../../AI_POLICY.md)).
