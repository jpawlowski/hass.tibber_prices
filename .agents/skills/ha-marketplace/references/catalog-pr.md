# The hacs/default pull request

For [`ha-marketplace`](../SKILL.md) §5. The agent gathers the evidence and drafts the text into `.agents/scratch/`;
**the developer opens the pull request** from their own account. Source:
[get into the catalog](https://contributors.home-assistant.io/marketplace/guides/catalog/).

## Evidence first — collect every link before drafting

| Needed                                 | How to get it                                                                                 |
| -------------------------------------- | --------------------------------------------------------------------------------------------- |
| Public, description, topics, issues    | `gh repo view <owner>/<repo> --json visibility,description,repositoryTopics,hasIssuesEnabled` |
| Passing HACS action without `ignore`   | `gh workflow run validate.yml --ref main`, then the run URL; its log has no brands warning    |
| Passing hassfest                       | the `Hassfest validation` job of the same run                                                 |
| A release published **after** that run | `gh release view --json url,publishedAt` — newer than the run, not a pre-release              |

If any row fails, stop and report it; the template's checklist states each of these as done, and a pull request with
a false statement is closed without notice.

## Steps for the developer

1. Fork [hacs/default](https://github.com/hacs/default) to the **personal** account (not an organisation — the HACS
   team must be able to edit the branch).
2. Create a branch from `master`; never commit to `master` of the fork.
3. Add `"<owner>/<repo>"` to the `integration` file — a JSON list — at its **alphabetical** position, not the end.
4. Open the pull request and fill the template completely (below). Do not request reviews.
5. Wait. The review backlog is months long and public
   ([oldest first](https://github.com/hacs/default/pulls?q=is%3Apr+is%3Aopen+draft%3Afalse+sort%3Acreated-asc)).
   Set to draft means small problems: fix them, then mark it ready again. Major problems close it.

## The template

It lives in `.github/PULL_REQUEST_TEMPLATE.md` of hacs/default and the HACS team changes it — read it fresh before
drafting (`gh api repos/hacs/default/contents/.github/PULL_REQUEST_TEMPLATE.md --jq .content | base64 -d`). Fill every
link it asks for from the evidence table, tick a box only when that table proves it, and keep its hidden marker
comments.

## Removal request

To take a listed repository out for any reason other than archiving, the developer files
[Request for repository removal](https://github.com/hacs/integration/issues/new?template=removal.yml) in
hacs/integration — **before** deleting anything. Draft the reason (one or two sentences: why, and what users should
move to) for them to paste.
