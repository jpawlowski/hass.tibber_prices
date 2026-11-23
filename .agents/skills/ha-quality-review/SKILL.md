---
name: ha-quality-review
description: >-
  Perform a structured quality review of this Home Assistant custom integration, either as a full audit or scoped
  to a diff. Use when asked to "review the integration", "audit the code", "check quality scale", "are we
  bronze/silver/gold", "is this ready to release", "what's missing before publishing", or before a release. The
  review of a change before it lands is haci-change-review, from the haci-review plugin. Covers running the automated gates
  first, then auditing architecture, the Integration Quality Scale rules, error handling, security, performance, user
  experience, and documentation — and reporting findings ranked by severity with concrete fixes. SYMPTOMS — load
  this if you are about to: report a review that only restates linter output; claim real-device testing that did
  not happen; give a finding without a file path and a fix; or judge quality without running `script/hassfest` and
  the test suite first.
---

# Review the integration

A review that only restates the linter is worthless. Run the machines first, then spend your attention on what they
cannot see: layering, failure behaviour, and whether a user would understand what this integration does.

## 0. Scope the review

Ask, or infer from the request:

- **Full audit** of the integration, or **diff review** of the current branch?
- Is there a target tier (this project aims for Silver, ideally Gold)?

For a diff review: `git diff main...HEAD --stat`, then read the changed files in full — not just the hunks.

When the diff is an open pull request, read what others already said before adding to it:
`gh pr view <number> --comments` and `gh api repos/{owner}/{repo}/pulls/<number>/comments` for the inline ones. Every
earlier finding — a human's, a bot's, another agent's — is either fixed in the current head, answered in the thread,
or still open; report the open ones instead of rediscovering them, and do not repeat what was already settled.

## 1. Automated gates (always first)

```bash
script/lint          # ruff format+fix, shfmt, prettier/markdownlint, yamllint, zizmor, shellcheck
script/type-check    # pyright — never auto-fixed
script/hassfest      # manifest, services.yaml, translations, integration structure
script/test --cov-html
```

Anything these report is a finding, not something to fix silently mid-review — but do note that `script/lint` already
auto-heals formatting, so only its **remaining** output counts.

## 2. Architecture

- Layering is Entity → Coordinator → source. Any entity importing `api/` directly, or any coordinator holding HTTP
  details, is a finding.
- Package structure matches the fixed set (`api/`, `coordinator/`, `config_flow_handler/`, `entity/`, `entity_utils/`,
  `<platform>/`, `service_actions/`, `utils/`). A `helpers/`, `common/`, `shared/`, or `lib/` package is a finding.
- Files are 200–400 lines, one entity class per file.
- Runtime state lives in `entry.runtime_data`, never `hass.data[DOMAIN]`.
- No circular imports; `TYPE_CHECKING` guards for type-only imports.

**Two upstream requirements this project deliberately does not meet.** Neither is a finding here, and both should be
stated as decisions rather than silently passed over:

- Core requires all device or service communication to be wrapped in a PyPI library. As a custom integration this
  project allows an in-repo client (`AGENTS.md` § Custom Integration Flexibility) — with the consequence that the
  client would have to be extracted before this could ever be submitted to Core.
- Core wants the coordinator in `coordinator.py`, the base entity in `entity.py` and actions in `services.py`. This
  project's `coordinator/`, `entity/` and `service_actions/` packages are the accepted equivalents.

## 3. Quality scale audit

| File                                                                     | When to read                                                                      |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| [`references/quality-scale-rules.md`](references/quality-scale-rules.md) | Auditing a tier. All 54 rule identifiers with one-line criteria, grouped by tier. |

Walk the rules for the target tier and report each as **pass / fail / not applicable**. For every fail, name the file
and the fix.

Home Assistant reports every custom integration's tier as `custom`, whatever `quality_scale` in the manifest says, so
the tier is a self-assessment, not something Home Assistant checks. A claimed Silver or above still needs at least one
entry in `codeowners` (`integration-owner`).

The rules most often missed in this codebase's shape:

- `action-setup` — actions registered in `async_setup()`, not per entry.
- `parallel-updates` — every platform package's `__init__.py` defines `PARALLEL_UPDATES` at module level: `0` on a
  read-only coordinator platform, a value the device can take on platforms that send commands.
- `entity-translations` / `icon-translations` — no hardcoded `name=` or `icon=` in `EntityDescription`.
- `exception-translations` — no English strings inside raised exceptions.
- `log-when-unavailable` — the coordinator must not log on every failed poll.
- `entity-category` / `entity-disabled-by-default` — diagnostics entities are marked and often disabled by default.
- `stale-devices` / `dynamic-devices` — devices appear and disappear with upstream reality.

## 4. Code quality

| File                                                               | When to read                                                                                                                            |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| [`references/core-lint-checks.md`](references/core-lint-checks.md) | Any review of integration code. The integration-specific checks Home Assistant Core lints in its own CI and this repository cannot run. |

Look for the failure modes linters miss:

- **Typing** — full annotations, `-> None` on procedures, no bare `Any` where a `TypedDict` or dataclass is meant,
  no `from __future__ import annotations` (banned on Python 3.14).
- **Async** — no blocking I/O in the event loop (`requests`, `open()`, `time.sleep`, sync SDK calls); every network call
  has a timeout; `asyncio.timeout` rather than a deprecated helper.
- **Exceptions** — specific types, never bare `except:`; `raise ... from err` to preserve the chain; the coordinator
  translates client exceptions into `UpdateFailed` / `ConfigEntryAuthFailed` correctly.
- **Properties** — no I/O, no raising, no side effects.
- **Constants** — no magic numbers or duplicated strings; reuse `homeassistant.const` names.
- **Logging** — lazy `%s` formatting, `debug` for the normal path, no secrets in any log line at any level.

Patterns Core reviewers catch that no tool does:

- **Signs of unreviewed AI output** — fixes for problems that do not exist, defensive code for conditions that cannot
  happen, test fixtures changed without a change in behaviour, or a polished description on top of code that shows a
  basic misunderstanding. Agent-written code in this repository is held to the same test.
- **Truthiness on device values** — `bool(value)` or `int(value)` on something that can be `None` or a string:
  `bool(None)` turns a missing value into "off", and `bool("0")` is `True`. Convert explicitly (`value == "1"`).
- **`entry.runtime_data` read where setup may have failed** — error paths, unload, and anything iterating
  `async_entries()`. It is set only for a loaded entry; use `async_loaded_entries()` and handle none.
- **Lifecycle boundaries** — every listener, timer and connection opened in setup or `async_added_to_hass` is released
  through `entry.async_on_unload` / `self.async_on_remove`, and connections also close on Home Assistant stop. A
  `try` that wraps everything is not a fix; small `try` blocks around the call that can raise are.

## 5. Security

Check each; the rule and how to comply live in the linked file.

- **Credentials** only in `entry.data`, and the data/options split right for `config-flow` —
  [`blueprint.config_flow`](../../instructions/blueprint.config_flow.instructions.md#data-vs-options).
- **Diagnostics** redact the whole payload, and `TO_REDACT` still matches the API response —
  [`blueprint.diagnostics`](../../instructions/blueprint.diagnostics.instructions.md).
- **TLS verification** on by default; a `CONF_VERIFY_SSL` option defaults to `True`, and no secret has a schema
  default.
- **Log lines** mask keys and IDs with `partial_redact()` — [`blueprint.python`](../../instructions/blueprint.python.instructions.md).
- **Admin-only actions**, and **caller-supplied paths** checked with `is_allowed_path()` —
  [`blueprint.service_actions`](../../instructions/blueprint.service_actions.instructions.md).
- **Webhooks** called from the LAN are `local_only` —
  [`blueprint.coordinator`](../../instructions/blueprint.coordinator.instructions.md).
- Data from a device or service never reaches `eval()`, `exec()` or a shell.
- **Dependencies** pinned identically in `manifest.json` and `requirements.txt`, and reviewed for supply-chain risk —
  [`blueprint-tooling`](../blueprint-tooling/SKILL.md).

## 6. Performance

- One coordinator poll serves all entities; no per-entity API calls.
- Interval appropriate for the source ([`ha-coordinator-debug`](../ha-coordinator-debug/SKILL.md)), a constant —
  a polling-interval field is a finding ([`blueprint.config_flow`](../../instructions/blueprint.config_flow.instructions.md)),
  and removing one users already set goes through [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md).
- No unnecessary `async_write_ha_state()`; no work in `__init__`.
- Data structures let entities read by key rather than scanning lists.

## 7. User experience

- Config flow validates before creating the entry and shows recoverable, translated errors.
- Entity names read well in the UI with `has_entity_name` (no repeated device name).
- Units, device classes, and state classes are set so history and statistics work.
- Failures surface as repair issues or reauth flows rather than silent unavailability.
- Every enum state, selector option and attribute name has a translation; no raw key reaches the UI.
- Every option's `data_description` says what it changes; a long options flow has a menu rather than a chain of
  steps.
- What users would trigger on is a state, not only an attribute; action response data has a stable, documented
  shape; device and library failures in actions are raised as `HomeAssistantError`.
- Whichever of the [`ha-user-experience`](../ha-user-experience/SKILL.md) options the integration took, they are
  applied consistently — a finding is an inconsistency, not a missing option.
- For an integration that depends on a remote endpoint, consider `system_health.py`: a `@callback async_register`
  that calls `register.async_register_info(...)`, whose info callback returns a dict whose values may be coroutines
  (the frontend shows a spinner and resolves them). `system_health.async_check_can_reach_url(hass, ENDPOINT)` covers
  the common case, and every key needs a `system_health.info.<key>` translation. It turns "it is broken" into
  "the API is unreachable" on the user's own system page.

## 8. Documentation and release hygiene

- `README.md`, `docs/user/` describe what actually exists — not the blueprint's placeholder text.
- The `docs-*` rules are met by the integration's own documentation — which file covers which rule:
  [`quality-scale-rules.md`](references/quality-scale-rules.md#where-the-docs--rules-are-met).
- `manifest.json`: correct `integration_type`, `iot_class`, `documentation`, `issue_tracker`, `codeowners`, `version`.
- Publishing readiness, when it is meant to be listed — repository preconditions, brand images, the CI gates the
  catalog requires: [`ha-marketplace`](../ha-marketplace/SKILL.md) has the checklist.
- Architectural choices worth remembering are decision records in `docs/development/decisions/`
  ([`blueprint-decisions`](../blueprint-decisions/SKILL.md)).
- Breaking changes carry a migration path ([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)).
- The project's own skills and instructions files are still worth their context: no rule a check now enforces, none
  the code no longer has, no two files on one topic
  ([`blueprint-lessons`](../blueprint-lessons/SKILL.md) §5).

## Report format

Rank by severity and be specific. A finding without a file path and a fix is noise.

```markdown
## Summary

<2–3 sentences: overall state, current effective tier, biggest risk.>

## Critical — must fix before release

### 1. <Title>

- **Where:** `custom_components/<domain>/coordinator/base.py:82`
- **Problem:** <what is wrong and what it breaks for a user>
- **Fix:** <concrete change>

## Warnings — should fix

## Suggestions — nice to have

## Quality scale

| Tier | Status | Failing rules |
| ---- | ------ | ------------- |

## Verified

<What you actually ran, and what you could not verify — e.g. no real device available.>
```

Be honest in the last section. Do not describe checks you did not run, and do not imply real-device testing happened
when it did not — that is an explicit rule of this project's [`AI_POLICY.md`](../../../AI_POLICY.md).

Verify each finding by running something — a gate, a test, a grep of the installed Home Assistant source — rather than
from memory or from how the code reads. A finding you could not verify that way stays in the report, marked
**unverified**, with what would confirm it.

## After the review

Report findings; do not silently fix them unless the developer asked for fixes. If they did, fix in severity order, run
`script/lint && script/type-check && script/test` after each group, and state what you changed.
