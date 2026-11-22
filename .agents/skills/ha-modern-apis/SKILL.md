---
name: ha-modern-apis
description: >-
  Verify that Home Assistant APIs used in this custom integration are current, and replace deprecated ones. Use
  when a DeprecationWarning, "Detected that custom integration", or "will be removed in HA Core X.Y" appears in logs
  or tests, when asked to "modernize", "update to the latest HA version", "fix deprecations", "is this still the
  right API", "bump the HA version", or before copying a pattern from an older integration, blog post, or model
  memory. Covers checking the installed Home Assistant source instead of guessing, the device
  registry single-owner rules, runtime_data, config flow helpers, entity metadata, async I/O, and the
  version bump procedure. SYMPTOMS — load this if you are about to: write `hass.data[DOMAIN]` instead of
  `runtime_data`; call the unscoped `async_get_device()`; use `FlowResult`, `DEVICE_CLASS_*`, or `async_timeout`;
  create your own aiohttp session; add a warning filter to make a deprecation go away; or adopt an undocumented API
  or config key on an issue's say-so.
---

# Keep the integration on current Home Assistant APIs

Home Assistant changes fast enough that any pattern remembered from training data or copied from a blog post is suspect.
This skill exists because the most common failure mode is confidently writing a 2023 API.

## The rule: check the source, do not recall

The devcontainer has the exact Home Assistant version this integration is developed against. It is the authority.

```bash
# Which version are we on?
.venv/bin/python -c "from homeassistant.const import __version__; print(__version__)"

# Does this API still exist, and is it deprecated?
rg -n "def async_get_device_by_identifier" .venv/lib/python*/site-packages/homeassistant/helpers/device_registry.py
rg -n "deprecated|breaks_in_ha_version" .venv/lib/python*/site-packages/homeassistant/helpers/update_coordinator.py

# How do current core integrations do it?
rg -n "runtime_data" .venv/lib/python*/site-packages/homeassistant/components/<similar_integration>/
```

`breaks_in_ha_version=` in a `@deprecated_function` decorator tells you the actual removal deadline. Prefer that over
any secondary source.

When the installed source is not enough — a pattern that is new rather than deprecated — check the current
documentation before implementing. Every page of <https://contributors.home-assistant.io/> is available as Markdown
(append `index.md` to its URL), and <https://contributors.home-assistant.io/llms.txt> indexes the site; each area has
its own list, such as <https://contributors.home-assistant.io/core/llms.txt>, and a full-text `llms-full.txt` next to
it. Fetch the area you need, not the whole site. Announcements and removal dates are on the
[developer blog](https://contributors.home-assistant.io/blog/).

**The docs follow Home Assistant's development branch, not the pinned version.** A page can describe an API that
arrives only in the next release — check that it exists in the installed source before using it; if it does not,
it is upcoming and needs the minimum version in `hacs.json` raised first.

## The same rule, generalised: what counts as verified

This applies to any API, tool or configuration key you are about to commit to. Only a **primary** source settles a
question — the installed source you import, or the current documentation of the tool you are configuring. A GitHub
issue, a blog post, another tool's convention and your own recall are leads, never answers.

Two traps make a secondary source feel primary:

- **Silent failure.** Most configuration rejects nothing: an unknown key is ignored, and the resulting default often
  looks like success. Before believing "X works", ask what a broken X would look like — if the answer is "the same
  thing", the observation proved nothing. Test the case that can fail: the file that should _not_ match, the entry
  that should _not_ load.
- **A key that belongs to a neighbouring tool.** Copilot, Cursor and Claude Code each name the same idea differently
  (`applyTo`, `globs`, `paths`). That a key works in one tool is no evidence for the next, and the wrong one will not
  complain.

When you deviate from documented behaviour, the bar is: name the primary source you checked, and design an observation
that could have come out the other way. If neither is possible, follow the documentation and say you could not verify
it. When the answer matters enough to encode, put a check in `script/` rather than a comment.

## Reference files

| File                                                             | When to read                                                                                                                                                                                                                                                 |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`references/deprecations.md`](references/deprecations.md)       | Fixing a specific deprecation. "Do not use → use instead" tables with the removal version — moved imports, config entry setup, config flow, entities and per-platform changes, actions and conditions, async and I/O, recorder statistics, upcoming changes. |
| [`references/device-registry.md`](references/device-registry.md) | Anything that registers, looks up, links or removes a device: single ownership, scoped lookups, `via_device_id` versus child devices, helper entities, and the device registry deprecations with their removal versions.                                     |

Read it when you have a concrete symbol to replace — do not pull it into context speculatively.

## The three that matter most in this codebase

**1. Device registry single ownership.** A device belongs to exactly one config entry and at most one
subentry. Identifiers are unique only within their owning entry. Always scope lookups:

```python
device = device_registry.async_get_device_by_identifier((DOMAIN, serial), entry.entry_id)
```

Never the unscoped `async_get_device()` — it is deprecated, and with two entries sharing an
identifier it resolves ambiguously. Parts of one product are child devices, not `via_device_id` devices —
[`references/device-registry.md`](references/device-registry.md#hub-or-parts-via_device_id-versus-child-devices).

**2. Typed `runtime_data`.** State belongs on the entry, not in `hass.data`:

```python
type {ClassPrefix}ConfigEntry = ConfigEntry[{ClassPrefix}Data]
entry.runtime_data = {ClassPrefix}Data(client=client, coordinator=coordinator, integration=integration)
```

**3. Tests catch Home Assistant's deprecations through a fixture, not through `warnings`** — see
[`ha-testing`](../ha-testing/SKILL.md#two-settings-that-surprise-people). Fix the deprecation; never filter it.

## Fixing a deprecation warning

1. Read the log line — it names the symbol, and usually the replacement and the removal version.
2. Confirm the replacement's real signature in the installed source. Signatures shift between the announcement and the
   release.
3. Replace every occurrence, including tests, diagnostics, repairs, and migrations. A half-migrated codebase is worse
   than an un-migrated one.
4. `script/lint && script/type-check && script/test`. For a path no test reaches, restart Home Assistant, exercise
   it, and confirm the line is gone — many are logged only once per run, and only when the code runs:
   `rg -n "Detected that custom integration|The deprecated .* from <domain>" config/home-assistant.log`.

## Bumping the Home Assistant version

```bash
script/ha-version-sync        # keeps hacs.json, .devcontainer/.env and friends aligned
```

Then rebuild the container (or re-run `script/setup/bootstrap`), and:

```bash
script/hassfest && script/test
rg -n "Detected that custom integration|The deprecated|DeprecationWarning|will be removed" config/home-assistant.log
```

When `script/test` reports that the manifest schema's categories differ from the installed Home Assistant, run
`python3 script/.lib/manifest_categories.py` in the project virtualenv to copy them over.

Raising the minimum version is a separate decision:
[`ha-marketplace`](../ha-marketplace/SKILL.md#2-hacsjson--when-to-touch-it) for where it lives,
[`ha-breaking-changes`](../ha-breaking-changes/SKILL.md#1-recognise-it) for why it is not breaking and how to
announce it.

## Do not

- Do not "fix" a deprecation by suppressing the warning.
- Do not trust an example from an older Home Assistant release, a Stack Overflow answer, or your own recall without
  checking the installed source first.
