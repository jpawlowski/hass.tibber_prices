# Setting up the repository on GitHub

Some settings live on github.com and cannot be committed. A repository made from the blueprint starts without them, so
set them once — and again whenever the blueprint adds one; running the script twice changes nothing.

```bash
script/setup/github --dry-run   # show what would change
script/setup/github             # apply it (needs gh, signed in with admin rights)
```

## What the script sets

| Setting                                                                  | Why                                                                                                                                                                         |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dependabot alerts                                                        | Known vulnerabilities in your dependencies; Renovate reads them for its security PRs                                                                                        |
| Dependabot security updates (while `.github/dependabot.yml` exists)      | A pull request for each fix in the ecosystems Dependabot owns                                                                                                               |
| Secret scanning and push protection (public repositories)                | GitHub blocks a push that contains a known credential format, before anyone can clone it                                                                                    |
| Squash by default and rebase for curated pull requests; no merge commits | One commit per change on `main`, the shape release-please reads; a rebase keeps a pull request's commits when each passes the commit check; follows what the rulesets allow |
| Auto-merge allowed                                                       | Renovate merges a new secret scanner release once its checks are green; nothing else merges itself                                                                          |
| Delete branch after merge                                                | Merged branches do not pile up                                                                                                                                              |
| Fork pull requests run workflows only after a maintainer approves        | Nobody spends your minutes, or tries a workflow change, by opening a pull request                                                                                           |
| Workflow permissions: read by default, may open pull requests            | Every workflow declares what it needs; release-please and the template sync open PRs                                                                                        |
| Every ruleset in [`.github/rulesets/`](../../.github/rulesets/)          | `main`: no deletion or force push, changes through a PR (squash or rebase) with `PR title`, `Lint and test`, `Hassfest validation` and `HACS validation` green              |
| CodeQL default setup off, once `codeql.yml` is on `main`                 | The workflow runs the analysis; the default setup would collide with it                                                                                                     |

Nobody pushes to `main` directly, admins included. Admins can merge a pull request without waiting for its checks,
which a template sync pull request needs: it is opened with the workflow token, which starts no checks, so they never
report. Review it, then merge it with the bypass.

**Squash or rebase?** Squash is the default: a branch's working commits never reach `main`. A pull request whose
commits were written to be read one by one can be rebase-merged instead, so each lands on `main` and in the changelog
— but only when the _Check each commit_ step of the `PR title` check passed, since every commit must then follow the
commit message rules.

**Want it less strict?** The ruleset file is the one place to change: `bypass_mode` `always` lets admins push to `main`
again, and `allowed_merge_methods` decides the merge methods — `script/setup/github` sets the repository to match.
Add `.github/rulesets/main.json` to `.templatesyncignore` in the same change, or the next template sync restores the
blueprint's version. To leave rulesets out entirely, delete the file before running the script, and remove one already
on GitHub under Settings → Rules.

## What only you can do

- **Install the [Renovate app](https://github.com/apps/renovate)** for the repository. Without it
  `.github/renovate.json` does nothing, and `toolchain-update-check.yml` reports outdated tools in an issue instead.
- **Add a `TEMPLATE_SYNC_TARGET_PAT` secret** if workflow files should arrive through the template sync — see
  [CUSTOMIZATION.md](CUSTOMIZATION.md).

## Secrets, three layers

1. **Before a commit:** `script/secret-scan --staged`, the commit hook, with [betterleaks](https://github.com/betterleaks/betterleaks)
   and the rules in `.betterleaks.toml`.
2. **On push:** GitHub's push protection, for public repositories; the lint job scans the commits of every pull
   request again, for a commit made without the hook.
3. **Weekly:** `secret-history-scan.yml` runs TruffleHog over the whole history and fails on a credential it can
   verify as live.

A finding is a credential to rotate first, and a commit to clean second — removing it from the history does not make
a leaked key safe again.

## Costs and free limits

Everything here is free for a **public** repository: Actions minutes on GitHub's standard runners, CodeQL, secret
scanning and push protection, Dependabot and the Renovate app.

A **private** repository pays for what goes beyond the free tier, so the workflows are built to spend little there:

- CodeQL and secret scanning need paid GitHub products on a private repository. `codeql.yml` does not start there, and
  the script leaves secret scanning alone; the commit hook and the lint job's scan still run.
- Actions minutes are counted per job and rounded up to the minute, which is why the secret scan is a step in the
  lint job and not a job of its own. The scheduled jobs — the weekly history scan, the weekly toolchain check, the
  weekly validation — take a few minutes a week in total.
- A draft pull request runs nothing: the checks start when it is marked ready for review, and a later push cancels a
  run still in progress. Open a pull request as a draft while an agent is still pushing to it.
- After a squash merge, the lint job on `main` stops after its first step when the pull request already passed it on
  the same tree; it still runs in full for a pull request that was behind `main` or never ran CI, such as a template
  sync or release pull request.
- A change to Markdown files only — skills, instructions, documentation — skips the Home Assistant install, the type
  check and the tests; the lint job still scans for secrets and runs the Markdown and skill checks. Any other file in
  the change runs everything.
- Nothing runs twice: CodeQL runs either as the default setup or as `codeql.yml`, never both, and each dependency is
  raised by Dependabot or by Renovate, never both.
