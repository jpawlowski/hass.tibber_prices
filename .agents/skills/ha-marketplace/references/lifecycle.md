# After publishing — links, releases, lifecycle

For [`ha-marketplace`](../SKILL.md) once the repository is listed or installable as a custom repository.

## Links in the README

Badge targets from [My Home Assistant](https://my.home-assistant.io/create-link/):

| Link                     | Opens                                                  | Use                                                 |
| ------------------------ | ------------------------------------------------------ | --------------------------------------------------- |
| `marketplace_repository` | the Marketplace                                        | ✅ the install badge                                |
| `hacs_repository`        | HACS before 2026.11, the Marketplace from 2026.11      | ❌ only for a minimum below 2026.11                 |
| `config_flow_start`      | the setup of `?domain=<domain>` in the user's instance | the "add the integration" badge, after installation |

Both repository links take `owner`, `repository` and `category=integration`; with the category, an unknown
repository is offered as a custom repository first. `README.template.md` already carries `marketplace_repository` and
`config_flow_start` — keep their parameters in step with a rename.

## Releases as users see them

- **Propagation:** the catalog data is regenerated every 4 hours and the Marketplace reads it every 6 hours, so a
  release can take most of a day to appear. Custom repositories update through the GitHub API every 48 hours, and only
  with a GitHub connection. "The update does not show" within that window is not a bug.
- **The release body is what users read** — the update entity shows it under **Settings** → **Updates**, joined for
  every release since the installed one, but only within the last five releases; further behind, a user sees the
  newest notes alone. Anything the user must do first goes at the top, and a step they must not miss is also a repair
  issue ([`ha-breaking-changes`](../../ha-breaking-changes/SKILL.md) §5; [`ha-release`](../../ha-release/SKILL.md)
  owns the notes).
- **Pre-releases** reach only users who switched on **Pre-release** for the repository, and only while newer than the
  latest regular release.
- **Keep old releases.** Users roll back by picking one from the repository menu. A deleted release or tag falls back
  to the default version for anyone who had it.
- **Restarts:** a first install of an integration with a config flow loads at once. Every update or removal of an
  already-loaded integration needs a restart; the Marketplace raises a repair with a restart button. Do not write
  release notes or docs that promise otherwise.
- **Size limits:** a download over 100 MiB or 50,000 files is refused. Keep test fixtures and assets outside
  `custom_components/<domain>/`.

## Renaming, archiving, removing

- **Rename or transfer:** nothing to file — the HACS team updates the catalog. Update the README's My links and the
  manifest's `documentation` / `issue_tracker` in the same change.
- **Archive:** the repository leaves the catalog. Installed copies keep working, get no more updates, and users see a
  repair explaining why. Say so in a final release note before archiving.
- **Removal for any other reason:** the developer files the removal request — draft it with
  [`catalog-pr.md`](catalog-pr.md#removal-request), do not file it.
- **Critical:** a repository found harmful (stealing credentials, breaking Home Assistant) is uninstalled from every
  instance at once and Home Assistant restarts. That is the consequence of shipping anything that phones home with
  credentials ([`ha-quality-review`](../../ha-quality-review/SKILL.md) §5).
