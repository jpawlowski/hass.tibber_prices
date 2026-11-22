# Repository and git strategy

Read this during phase 1, before running `initialize.sh`.

## Keep the existing repository

Issues, pull requests, stars, release tags and the catalog listing are tied to the repository **URL**, not to the commit
history inside it. Creating a new repository from the template and abandoning the old one throws all of that away, and
users who installed it through the Marketplace end up on a repository that no longer receives updates.

All three strategies below work inside the existing repository.

## Option A — Overlay onto the existing history (recommended)

The import becomes one ordinary commit on top of the existing `main`, delivered as one pull request: the full history
stays, nothing is force-pushed, and no unrelated histories are merged. The integration folder is never touched by the
mechanics; only the files around it change. Everything up to the classification is mechanical — the agent's judgement
starts at step 5.

**`script/import-overlay` does steps 1 to 4** from a clone of the blueprint, before its `initialize.sh` runs — it
initialises a temporary copy itself, takes the domain from the target, and writes the groups to the target's
`.agents/scratch/import-overlay.md`:

```bash
git clone https://github.com/jpawlowski/ha-integration-blueprint.git /tmp/blueprint
/tmp/blueprint/script/import-overlay --target <project> -- \
  --title "<Title>" --namespace <Prefix> --repo <owner>/<repo> --author "<Name>"
```

The steps below are what it runs, for reading its result and for doing it by hand.

1. **Initialise the blueprint outside the project**, with the identifiers the integration already has
   ([phase 1](../SKILL.md#phase-1--repository-then-initializesh)):

   ```bash
   git clone https://github.com/jpawlowski/ha-integration-blueprint.git /tmp/blueprint
   cd /tmp/blueprint
   git remote set-url origin https://github.com/<owner>/<repo>.git
   ./initialize.sh --dry-run --force --domain <domain> --title "<Title>" --namespace <Prefix> --repo <owner>/<repo> --author "<Name>"
   ./initialize.sh --force --domain <domain> --title "<Title>" --namespace <Prefix> --repo <owner>/<repo> --author "<Name>"
   git add -A
   ```

2. **Branch in the project**, never on `main`:

   ```bash
   cd <project>
   git switch -c chore/adopt-blueprint main
   ```

3. **Remove every tracked file except the integration folder**, then **copy the initialised blueprint in** — its
   tracked files only, without its example integration and without its `tests/`, which test that example:

   ```bash
   git ls-files -z | grep -zv '^custom_components/<domain>/' | xargs -0 git rm -q --
   git -C /tmp/blueprint ls-files -z \
     | grep -zv -e '^custom_components/<domain>/' -e '^tests/' \
     | tar -C /tmp/blueprint --null -T - -cf - | tar -xf -
   git add -A
   ```

4. **List the groups** against the old `main` — the script also sets the agent instructions apart (step 5):

   ```bash
   git diff --cached --no-renames --name-only --diff-filter=D HEAD    # only in the old repository
   git diff --cached --no-renames --name-only --diff-filter=MT HEAD   # in both — the blueprint's version is staged now
   git diff --cached --no-renames --name-only --diff-filter=A HEAD    # only in the blueprint
   ```

5. **Decide each file of the first two groups**, and write every decision into the pull request description:
   - **Only in the old repository** — restore what the project still needs with `git checkout HEAD -- <path>`: its
     `tests/`, its documentation, workflows the blueprint has no counterpart for. Leave out what the blueprint
     replaces: old CI that `validate.yml` and `lint.yml` cover, old release scripts, a second linter configuration.
   - **In both** — merge: start from the blueprint's version and carry over what the project added
     (`git show HEAD:<path>`). Typical: `README.md`, `.gitignore`, `hacs.json`, `pyproject.toml`,
     `requirements*.txt`. A file `.templatesyncignore` lists as project-owned keeps the project's content.
   - **Agent instructions** — `script/import-overlay` lists them apart. The blueprint's version stays; the old content
     is sorted in phase 3 ([`agent-knowledge.md`](agent-knowledge.md)), not restored or merged here.
   - **Only in the blueprint** — keep.

6. Continue with phase 2 of the skill: the code is already in place, so "get it green" starts right away.

Issues, pull requests, releases and the whole commit history stay. The blueprint's own history is not imported; the
template sync does not need it.

## Option B — Clean history, force-push

Only when the commit history is genuinely not worth keeping.

1. Clone the blueprint locally:
   `git clone https://github.com/jpawlowski/ha-integration-blueprint.git`
2. Point the remote at the existing repository **before** initialising:
   `git remote set-url origin https://github.com/<you>/<your-repo>.git`
   Doing this first also avoids `initialize.sh` refusing to run against the blueprint's own remote.
3. `./initialize.sh --force` with the **existing** domain, title and — ideally — the existing class prefix.
   `--force` is needed because a direct clone carries the blueprint's full history rather than the single commit a
   "Use this template" repository has.
4. Copy `custom_components/<domain>/` from the old code in, replacing the generated one.
5. `git push --force origin main`.

Issues and pull requests survive; the commit history starts fresh.

> Force-pushing rewrites public history. Anyone with a local clone must re-clone or hard-reset. Say so before doing
> it, and never do it without an explicit instruction.

## Option C — Merge unrelated histories

Superseded by option A, which keeps the same history without the conflicts; kept for a repository that wants the
blueprint's own history in its log.

1. `git remote add blueprint https://github.com/jpawlowski/ha-integration-blueprint.git`
2. `git fetch blueprint`
3. `git merge blueprint/main --allow-unrelated-histories`
4. Resolve the conflicts — expect nearly every file to conflict, since the blueprint touches the whole tree.
5. `./initialize.sh --force` to finalise the identifiers.

## Before running `initialize.sh`

Always do a `--dry-run` pass first, and confirm:

- `--domain` is the **existing** domain, character for character.
- `--namespace` is the class prefix the code already uses, unless a rename is deliberate.
- The working tree is committed or stashed, so the run is revertable.

## Repository settings to re-check afterwards

- **Actions permissions** — _Settings → Actions → General_ → allow GitHub Actions to create and approve pull
  requests, or the release and template-sync workflows cannot open their pull requests.
- **Branch protection** — the workflows assume a `main` branch.
- **Secrets** — anything the old workflows used has to exist in this repository too.
- **`hacs.json`** — `initialize.sh` sets `name` and `homeassistant`, but does not preserve other fields the old
  repository may have had, such as `render_readme`. Restore them by hand, but keep the template's `zip_release`,
  `filename` and `hide_default_branch` ([`ha-marketplace`](../../ha-marketplace/SKILL.md#2-hacsjson--when-to-touch-it)).
- **`manifest.json`** — `documentation` and `issue_tracker` must point at this repository.
