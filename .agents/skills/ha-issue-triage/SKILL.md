---
name: ha-issue-triage
description: >-
  Work through a backlog of GitHub issues on this repository — categorize, then walk bugs and feature requests one
  at a time, fixing approved ones on a branch through a pull request instead of committing straight to main. Use
  when asked to "triage my issues", "go through the issue backlog", "work through the issues", "let's triage",
  or invoked via the `/issues` command. This is opt-in tooling for backlog work, not a replacement for the normal
  ad-hoc flow in AGENTS.md — a single "fix this bug" request in conversation still goes through that flow, not this
  one. SYMPTOMS — load this if you are about to: fix several issues in a row by committing each straight to main
  with nobody reviewing between commits; dump the whole backlog in one message instead of walking it one issue at a
  time; merge a pull request this flow opened without either explicit confirmation or an explicit full-autonomy
  invocation; bump a version by hand; or skip the breaking-changes warn-first check on an issue fix that needs it.
---

# Issue triage and branch/PR-based fixing

A backlog-scale companion to the ad-hoc flow in `AGENTS.md`. That flow (commit directly, on explicit request, no
push) is still correct for a single request handled live with the developer watching. This skill is for the
different situation: working through several issues in a row, where a branch + pull request + green CI is the
review surface, because nobody is watching each individual commit in real time. Both are legitimate; pick based on
whether you're handling one request or a backlog, not out of habit.

## Merge autonomy — read this before the fix flow below

By default, **ask for explicit confirmation before merging** any pull request this flow opens — merging is a
shared-state, hard-to-reverse action (`AGENTS.md`, "Executing actions with care"), and a backlog run touches several
of them in a row.

Skip that per-PR confirmation, and merge automatically on green CI, only when this session was entered through a
dedicated entry point built for full autonomy — a command that exists specifically to invoke this flow (such as
`/issues`, if your client offers slash commands), or an explicit instruction scoped to the session ("auto-merge
these", "don't ask me each time today"). Ad-hoc conversational use of this skill — "hey, can you triage my issues" —
always asks. State which mode you're in once, at the start of a run, rather than leaving it implicit.

## Concurrency: running more than one instance on the same repo

If nothing else is touching this backlog concurrently, skip this section — claim/release below are harmless no-ops.
It exists for when you might be one of several agent sessions working the same repo at once.

**Instance ID:** generate one ID of the form `<epoch>-<rand>` (`` `date +%s` `` seconds, plus a random suffix) at the
start of a run, show it, and reuse the literal value in every later command — shell variables do not survive
between separate tool calls. The lock label is `wip:<id>`; the epoch doubles as its creation timestamp for the TTL
below.

**Locked** means an issue carries a _foreign_ `wip:<epoch>-*` label whose epoch is younger than 6 hours. Don't touch
those — list them, move on. A foreign lock older than 6 hours is orphaned and does not lock (see "Expired locks").

**Claim** (before any write to an issue — categorize, fix, comment, snooze; plain viewing needs no lock):

1. `gh issue view N --json labels` — a foreign non-expired `wip:*` already there? It's taken; say so, move on.
2. Ensure both labels exist with `gh label create "in progress" --color fbca04 --force` and
   `gh label create "wip:<id>" --color 5319e7 --force`, then
   `gh issue edit N --add-label "wip:<id>" --add-label "in progress"`.
3. **Race check:** view the labels again. Several `wip:*` present → the lexicographically smallest ID wins. Not the
   smallest → remove your label, tell the developer, move on. Otherwise you hold the lock.

**Release** immediately after a quick write (categorize/comment/snooze); hold it through a fix until merge. Release
with `gh issue edit N --remove-label "wip:<id>" --remove-label "in progress"` (a merged fix closes the issue anyway).

**Expired locks (TTL 6h):** `now − epoch > 21600` → orphaned. Remove the foreign label, then claim normally with your
own ID.

**Label cleanup:** whenever a `wip:<id>` label is removed (release, race back-off, `unlock`, expired takeover) and no
open issue still carries it, delete the label definition too (`gh label delete "wip:<id>" --yes`) so `wip:*` doesn't
pile up.

## Dispatch

- `locks` — list open issues carrying a `wip:*` label (number, title, holding ID); mark ones older than 6h
  "(expired, treated as free)". Nothing else.
- `unlock <issue#>` — show the issue's `wip:*`/`in progress` labels, confirm, remove them.
- a bare issue number — skip triage, show the issue and its comments, get the developer's read on it before writing
  any code (plan mode / a quick back-and-forth, not straight into the fix flow).
- `stop` / `drain` (as an argument, or said mid-run) — see "Graceful stop" below.
- no argument — the full flow below (generate the instance ID first if concurrency applies).

## Phase 0 — prerequisites and scope (counts only)

List the repository labels first. Create the workflow label once with
`gh label create "in progress" --color fbca04 --force`; claims depend on it and must not fail halfway through. Resolve
the two category labels from what is actually present: prefer `bug` for defects and `enhancement` for feature work,
fall back to `Feature request` if that is the repository's convention, and ask when several plausible labels remain.
Reuse those exact names for the whole run.

Then run `gh issue list --state open --limit 1000 --json number,title,labels,assignees,author`. Run the snooze wake pass
(see below) and set aside issues with a foreign, non-expired `wip:*`. Report only counts — how many need categorizing,
how many bugs, how many feature requests, one line each for anything that woke up or is locked elsewhere. Do not
enumerate the backlog; go straight into the per-issue walk. If the repository has more than 1,000 open issues, say
that this is the first batch rather than presenting the counts as complete.

## Phase 1 — categorize

Use the defect and feature labels resolved in Phase 0. Walk the uncategorized issues one at a time:

1. A short summary (2–3 sentences) of what the issue wants.
2. A weak title? Suggest a better one.
3. Ask about **only this issue**, with a reasoned recommendation (bug vs. feature request; `question`/`duplicate`/
   `wontfix` when in doubt), fold an optional title change into the same question. Wait for the answer.
4. After the decision: claim, `gh issue edit N --add-label "<label>"` (and `--title` if changed), release.

## Phase 2 / 3 — walk the bugs, then the feature requests

One at a time, waiting for the developer after each:

1. `gh issue view N --comments` — explain the cause/context and give an honest read (worth fixing, effort, risk,
   possible duplicate).
2. If there are comments, summarize the thread — who said what, what's open. No comments → skip this step entirely.
3. Ask what should happen, with a recommendation: **Fix** (below) / **Ask the author** / **Reject / decline** /
   **Snooze** / **Skip** (next issue, release any held lock).

For a feature request, "Fix" means "implement," and scope is more often unsettled — clarify with the author or with
`ha-planning` before code appears. Name dependencies between related requests when you see them.

## Fix flow (issue approved)

1. **Claim.**
2. **Breaking-changes check first.** If the fix touches anything on `AGENTS.md`'s breaking-changes list (unique
   IDs, entity IDs, entry data, state values, service signatures, removing a config option), stop and follow
   [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)'s warn-first procedure before writing any code — vutuv,
   the source this skill generalizes from, has no equivalent concern, but this project does.
3. **Isolate and branch.** Run `git status --short` before creating anything. If the current worktree is dirty, do
   not absorb, stash, or discard those changes: create a separate worktree from `main`, or stop if an isolated
   worktree is not available. In a clean tree, create a short kebab-case branch; never commit the fix on `main` in
   this flow.
4. **Implement.** If your agent runtime supports isolated sub-agent dispatch, use it; otherwise work directly on the
   branch. For a bug, write the test that reproduces it first and watch it fail, then fix until it passes — a test
   written after the fix may never have caught the bug. Other tests stay proportionate, per
   [`ha-testing`](../ha-testing/SKILL.md). If the fix turns out to need more than ~10 files or an architectural
   change, stop and hand off to [`ha-planning`](../ha-planning/SKILL.md) instead of continuing inline.
5. **Gate once.** Run `script/check` (type-check + lint-check + spell-check) redirected to a log, judged by its exit
   code — see [`blueprint-tooling`](../blueprint-tooling/SKILL.md)'s token-discipline note. Read the log, and only
   the failing part, on a non-zero exit; iterate on just the failing piece, then re-run the full gate once more
   before moving on. Then run the review pass in [`blueprint-change-review`](../blueprint-change-review/SKILL.md)
   on the fix. This gate runs no tests, so its step 2 is `script/test` on top of it, and the full gate again
   whenever simplifying or `/code-review --fix` changed files.
6. **Commit** using Conventional Commits
   ([`blueprint.commit-message.instructions.md`](../../instructions/blueprint.commit-message.instructions.md)).
   **No manual version bump** — release-please derives it from the commit type once this lands on `main`
   ([`ha-release`](../ha-release/SKILL.md)).
7. **Push and open the PR** (`gh pr create`, following `.github/pull_request_template.md` if the repo has one).
   Open it ready for review, not as a draft: the gate above already passed, and CI skips drafts, so a draft would
   leave the next step waiting for checks that never start.
8. **Wait for CI:** `gh pr checks --watch --fail-fast`.
   - Red → do not merge. Fix it and push again, watch again — or stop and report if it isn't yours to fix.
   - Green → continue.
9. **Merge**, per the autonomy rule at the top of this file. `gh pr merge <nr> --squash --delete-branch`. If another
   pull request is stacked on this one, retarget it to `main` first — deleting the branch closes it
   ([stacked pull requests](../ha-release/references/branches-and-pull-requests.md#stacked-pull-requests)).
10. **Branch cleanup — every time, not optional.** `gh pr merge --delete-branch` normally removes both copies of the
    branch. Refresh `main`, prune, and delete the local branch only if it still exists:

    ```bash
    git checkout main && git pull --ff-only
    git fetch --prune origin
    git show-ref --verify --quiet refs/heads/<branch> && git branch -D <branch>
    ```

    The final command returning 1 because the branch is already gone is success, not a cleanup failure. If the fix
    ran in an isolated worktree, remove that worktree before checking for the branch. Before moving on,
    `git branch -vv` should show nothing marked `[origin/<name>: gone]` — that marker is the leak.

11. **Release the claim.** Remove `wip:<id>` and `in progress` even if the merge already closed the issue, then delete
    the now-unused `wip:<id>` label definition.
12. **Close the loop on the issue.** The merge may auto-close it (a `Fixes #N` PR body); either way, draft a short
    shipped note — what now works, and why, in the language of the issue — per `AGENTS.md`'s "Posting on the
    developer's behalf": get explicit sign-off on the draft unless this session is running in full-autonomy mode,
    and disclose per `AI_POLICY.md` when it posts under the developer's identity without another marker.

## Ask the author

Always an option in the per-issue walk. Get the author (`gh issue view N --json author`), draft a friendly question
in their language, following the same posting-on-behalf policy as step 11 above. Claim → comment → release.

## Reject / decline

When the developer decides an issue won't be done — out of scope, a design not wanted, a duplicate — close it
kindly, never leave it to rot. Ask for the reason as part of the same question (a short recommendation is fine; "no
reason, just decline" is a valid answer), then, after claiming: draft the closing note per the posting-on-behalf
policy, get sign-off, comment, `gh issue close N --reason "not planned"` (`--reason completed` only when it's
genuinely resolved another way), and release — a closed issue keeps no lock.

## Snooze

Labels `snoozed` + `snooze:YYYY-MM-DD` (name = wake date). After claiming: `gh label create snoozed --color c5def5
--force`, `gh label create "snooze:<date>" --color ededed --force`, apply both, release. At the start of every run,
do a wake pass: `snooze:<date>` ≤ today → remove both labels, surface it at the top as woken up; delete now-empty
`snooze:*` labels afterward. Bundle future ones into one line ("N snoozed").

## Graceful stop (drain)

The developer can end a run at any point — not an emergency kill. **Finish work already in flight, start nothing
new:**

1. Stop claiming, categorizing, commenting, snoozing, or dispatching anything new. The per-issue walk ends here.
2. Let an in-flight fix finish: when it reports, apply the normal merge rule (green → merge + cleanup + release;
   red/unclear → hold the lock and report).
3. For anything claimed but not yet started, list it and ask once whether to keep the claim for next time or release
   it now (default recommendation: release the lock, keep any assignee).
4. Report what shipped this run, what's still draining, and what was left untouched.
