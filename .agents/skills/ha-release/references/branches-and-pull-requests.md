# Branches and pull requests

For [`ha-release`](../SKILL.md). The rules — one branch per change, force push only with a lease and only when asked,
one logical change per pull request — are in `AGENTS.md` under _Commits, branches and pull requests_. This file is how
to carry them out. Push only when the developer asked for the push or for a pull request.

## Bringing a branch up to date with `main`

- **Only when needed.** The `main` ruleset does not require a branch to be up to date, and the run on `main` after the
  merge checks the combined code. Update on a conflict, or when the change depends on something that just landed.
- **Your own branch that nobody else has pulled: rebase.** `gh pr update-branch <number> --rebase` does it on GitHub.
  Afterwards `git fetch` and `git reset --hard origin/<branch>`, and never push the old local head again. Only if
  GitHub refuses, rebase locally and push with `git push --force-with-lease`.
- **A branch someone else has pulled, or a contributor's branch: merge `main` in**, never rewrite it. GitHub's
  _Update branch_ button merges by default.
- A branch that contains a merge commit can only be squash-merged.

## Conflicts

- Read the commits or pull requests behind both sides before resolving a hunk.
- Keep both intents, and add no new behaviour inside a conflict hunk.
- When both sides changed the same logic, stop and ask the developer which one wins.
- Run `script/lint`, `script/type-check` and `script/test` before pushing the result.

## Overlapping pull requests

Before handing a pull request over, check whether another open one touches the same files
(`gh pr list --json number,files`). The one that lands second carries its change into the new structure — a rebase
that applies cleanly can still drop a change the other side moved.

## Splitting mixed work

`git add -p` is interactive and unavailable to an agent.

- Stage named paths, never `git add -A`.
- To split hunks within one file, write the wanted hunk to a patch file and `git apply --cached` it.
- `git checkout <commit> -- <path>` stages what it restores, so check `git status` before the next commit.
- Work already committed together: create a second branch from `main` and take the unrelated part over with
  `git restore --source=<commit> -- <paths>` or `git cherry-pick`, then remove it from the first branch with a new
  commit. Rewrite the first branch instead only if nobody else has pulled it, and push it with a lease.
- Every resulting branch passes the checks on its own.
- A pre-commit hook stashes unstaged changes but not untracked files. When a new directory must not land in the commit
  you are making, commit in an order where each intermediate state passes the hooks.

## Stacked pull requests

Stack only when B needs A's unmerged code; otherwise open both against `main`. B's description names the pull request
it depends on.

Merging deletes A's branch, and **GitHub closes B when its base branch is deleted** — it does not retarget it. The
safe order:

1. `gh pr edit <B> --base main` — retarget B first.
2. Merge A (squash); its branch may be deleted now.
3. Bring B onto `main` without A's original commits, which `main` holds as one squash commit:
   `git rebase --onto origin/main <old-tip-of-A> <B-branch>`, then `git push --force-with-lease`. On a branch someone
   else has pulled, merge `origin/main` instead.

Push each branch while it is checked out; the pre-push hook rejects a push that sends more than the current branch.

## After a squash merge

Never reuse the branch for a second pull request — its commits are not in `main`, only their squash. Clean up:

```bash
git checkout main && git pull --ff-only
git fetch --prune origin
git show-ref --verify --quiet refs/heads/<branch> && git branch -D <branch>
```

`git branch -D` is needed because Git does not see the squash as a merge of the branch. `git branch -vv` shows nothing
marked `[origin/<name>: gone]` afterwards.
