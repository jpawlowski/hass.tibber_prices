---
comments: false
---

# Release Management

Releases come from [release-please](https://github.com/googleapis/release-please). Nobody picks a
version or runs a release script: the version and the release notes follow from the
[Conventional Commits](https://www.conventionalcommits.org/) on `main`.

## 🚀 How a Release Happens

1. **Every push to `main`** updates one open **release pull request** (`chore(main): release X.Y.Z`).
   It shows the next version and the `CHANGELOG.md` section that will become the release notes,
   so you always see what the next release would contain.
2. **Merging the release pull request** writes the version into `manifest.json` and
   `.release-please-manifest.json`, creates the tag `vX.Y.Z` and a **draft** GitHub release.
3. The **Release** workflow (`.github/workflows/release.yml`) then:
    - **build** (read-only): `./scripts/release/build-asset` packs `custom_components/tibber_prices/`
      of the tag into `tibber_prices.zip`, adds a gzip copy of every card module (`*.js.gz`,
      which Home Assistant sends to browsers that accept gzip: about 200 KB instead of 700 KB)
      and checks its version and the layout the store installs
    - **publish**: attaches the zip, appends the Buy Me a Coffee footer
      (`.github/release-notes-footer.md`) and publishes the release (a draft until then, so no
      install ever finds the asset missing)
    - **docs**: starts `docusaurus.yml` to version the docs

The repository setting "Allow GitHub Actions to create and approve pull requests" (Settings →
Actions → General) must be on, or release-please can't open its pull request.

### Which version comes next

| Commits since the last release           | Next version (before 1.0) |
| ---------------------------------------- | ------------------------- |
| a breaking change (`feat!:`, `BREAKING CHANGE:`) | MINOR (0.x.0)     |
| at least one `feat`                      | MINOR (0.x.0)             |
| only `fix`, `perf`, …                    | PATCH (0.0.x)             |

To force a version, put `Release-As: 0.41.0` into the body of a commit on `main`.

### What appears in the release notes

release-please sorts the commits **by type**, never by scope:

| Type                                     | Section                |
| ---------------------------------------- | ---------------------- |
| `feat`                                   | 🎉 What's New          |
| `fix`                                    | 🐛 Fixed               |
| `perf`                                   | ⚡ More Reliable       |
| `build(deps)` (the integration's requirements; other `build` scopes are rejected) | 📦 Updated Dependencies |
| `docs`, `test`, `refactor`, `style`, `ci`, `chore`, `revert` | hidden |

Each commit is one line, its subject. So:

- **Use pull requests and squash-merge them.** The pull request title becomes the commit on
  `main` and thus one line in the release notes, however many commits the branch had. A check
  (`.github/workflows/pr-title.yml`) makes sure the title is a Conventional Commit.
- **Pick the type for the reader of the release notes.** A fix for something that was never
  released is `chore`/`refactor`, not `fix` (`./scripts/release/check-if-released <commit>` tells).
- **To change a line before the release**, edit the body of the merged pull request and add
  `BEGIN_COMMIT_OVERRIDE` … `END_COMMIT_OVERRIDE` with the replacement message; release-please
  picks it up on the next push. A commit pushed directly to `main` has no such way back.
- **Breaking changes** get their own section at the top of the notes, with the text of the
  `BREAKING CHANGE:` footer: write there what users have to do.

---

## 🧪 Beta Releases

A beta skips the release pull request: tag a commit on `main` by hand.

```bash
git tag -a v0.40.0b0 -m "v0.40.0b0"
git push origin v0.40.0b0
```

The Release workflow builds the zip with the beta version (`build-asset` writes it into
`manifest.json`) and creates a **pre-release**, so the stores offer it only with "show beta". Its
notes are GitHub's generated list. release-please ignores beta tags; the next release pull
request still counts from the last stable release. The docs are not versioned for betas.

---

## 📦 The Release Asset

`hacs.json` sets `zip_release` and `filename`, so the store installs every version from the
release asset, never from the repository (the default branch is hidden with
`hide_default_branch`). To see exactly what a release would ship:

```bash
./scripts/release/build-asset v0.40.0 dist   # needs the tag locally
unzip -l dist/tibber_prices.zip
```

**Don't create releases with GitHub's "Draft a new release" button**: a release without
`tibber_prices.zip` can't be installed by the store.

---

## 🐛 Troubleshooting

**No release pull request appears:** check the Release workflow run on `main`, and the setting
"Allow GitHub Actions to create and approve pull requests". With only hidden types since the last
release (`docs`, `chore`, …) there is nothing to release, so there is no pull request either.

**The release is still a draft / has no asset:** re-run the asset jobs for the tag (Actions →
"Release" → Run workflow, tag `v0.40.0`). They upload the asset again and publish.

**Checks don't run on the release pull request:** pull requests opened with `GITHUB_TOKEN` start
no workflows. The release pull request only changes `CHANGELOG.md` and version numbers; the
commits it releases were checked on `main`.

---

## 🔍 Format Requirements

**HACS / Marketplace:** No specific format required, uses GitHub releases as-is; the update
entity shows the release body
**Home Assistant:** No specific format required for custom integrations
**Markdown:** Standard GitHub-flavored Markdown supported
