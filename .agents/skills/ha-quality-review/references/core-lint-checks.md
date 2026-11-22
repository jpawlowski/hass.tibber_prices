# Checks Home Assistant Core lints, and this repository cannot

Home Assistant Core ships a pylint plugin (`packages/pylint-home-assistant` in `home-assistant/core`) with
integration-specific checkers that need type inference, `manifest.json`, or cross-file analysis — things a per-file
linter cannot do. Its README states that the checkers target Core's module names and repository layout, and that
installing the package separately does not add support for custom integration layouts.

So these are review checks, not tooling. Ruff, pyright, hassfest and the rule files already cover the rest; the tables
are the part that otherwise reaches nobody, and the last section maps the remaining checks to their owners. The first column is Core's check name — the
form Core uses in `# pylint: disable=` comments — with its numeric code in parentheses, so a finding can be traced
back to the upstream rule. Checks that only verify a quality-scale rule exists (`home-assistant-missing-diagnostics`,
`-missing-parallel-updates`, `-missing-reauthentication-flow`, `-missing-config-entry-unloading`) are covered by the
rule list and not repeated here.

## Unique IDs

Migrating a unique ID after release breaks every existing install, so these are the most expensive to get wrong.

| Core check                                                     | Check                                                                                                                                                                                                                                           |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-entity-unique-id-static` (`W7424`)             | No entity assigns a literal `_attr_unique_id` in the class body. Unique IDs are scoped per `(domain, platform)` across all config entries, so a constant collides on the second entry unless the manifest declares `single_config_entry: true`. |
| `home-assistant-entity-unique-id-redundant-domain` (`W7425`)   | The unique ID does not contain the integration's domain, in a literal or through `DOMAIN` — the registry key already carries it.                                                                                                                |
| `home-assistant-entity-unique-id-redundant-platform` (`W7427`) | The unique ID does not contain the entity platform name (`sensor`, `light`, …) either, for the same reason.                                                                                                                                     |

## Config flow

| Core check                                                                                                   | Check                                                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-config-flow-name-field` (`W7408`)                                                            | No name field (`CONF_NAME`, `"name"`, `CONF_DEVICE_NAME`) in the schema; the name comes from the device or from discovery. Helper integrations and subentry flows are exempt.                                 |
| `home-assistant-flow-call-in-try` (`W7457`)                                                                  | A `try` in a flow step holds only the device or service call. Creating the entry, showing a form, the unique-ID helpers and `async_step_*()` go in `else:` — a broad `except Exception` swallows `AbortFlow`. |
| `home-assistant-config-flow-field-not-translated` (`W7428`), `-options-…` (`W7431`), `-subentry-…` (`W7432`) | Every form field of a config, options or subentry flow has a translation.                                                                                                                                     |
| `home-assistant-config-flow-menu-missing-step` (`W7434`)                                                     | Every `async_show_menu` option has a matching `async_step_<option>` method.                                                                                                                                   |
| `home-assistant-config-flow-connection-class` (`W7438`)                                                      | No `CONNECTION_CLASS` on the flow — Home Assistant no longer reads it.                                                                                                                                        |

## Entities and platforms

| Core check                                                      | Check                                                                                                                                                                                                                                                    |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-missing-has-entity-name` (`W7416`)              | `_attr_has_entity_name = True` holds statically — class level, unconditionally at the top of a method, or via the `EntityDescription`. A conditional assignment does not count.                                                                          |
| `home-assistant-entity-description-redundant-default` (`C7412`) | No `EntityDescription` field is set to a default the class hierarchy already declares (`None`, `True`, `False`). `name=None` is **not** such a case — the field defaults to `UNDEFINED`, and `None` is the deliberate "name it after the device" marker. |
| `home-assistant-enforce-class-module` (`C7411`)                 | An entity class deriving from a platform base lives in that platform's package, never in `__init__.py` or an unrelated module. Core also wants the coordinator in `coordinator.py`; this project's `coordinator/` package is the accepted equivalent.    |
| `home-assistant-unnecessary-format-mac` (`W7429`)               | No `format_mac()` inside a `CONNECTION_NETWORK_MAC` tuple passed as `connections=` — the device registry normalises it already. Comparisons against `device.connections` still need it.                                                                  |

## Service actions and errors

| Core check                                                                                 | Check                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-log-and-raise` (`W7450`)                                                   | An error raised to Home Assistant — `ConfigEntryNotReady`, `UpdateFailed`, `HomeAssistantError`, … — is not also logged at warning or above; Home Assistant reports it already. |
| `home-assistant-exception-message-with-translation` (`W7419`)                              | No positional message next to a `translation_key`.                                                                                                                              |
| `home-assistant-exception-translation-key-missing` (`E7406`), `-domain-mismatch` (`E7408`) | The key exists under `exceptions` in the translations, and `translation_domain` and `translation_key` are set together.                                                         |
| `home-assistant-exception-placeholder-mismatch` (`E7418`)                                  | Every placeholder the translated message expects is supplied in `translation_placeholders`.                                                                                     |
| `home-assistant-mdi-icon-not-found` (`E7409`), `-json-not-found` (`E7410`)                 | Every `mdi:` name in Python and in `icons.json` exists in the Material Design Icons set.                                                                                        |

## Runtime and time handling

| Core check                                                    | Check                                                                                                                            |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-coordinator-untyped-config-entry` (`W7447`)   | The coordinator types `config_entry` with the integration's `ConfigEntry[...]` alias, not plain `ConfigEntry`.                   |
| `home-assistant-coordinator-redundant-config-entry` (`W7448`) | The coordinator passes `config_entry=` to `super().__init__()` and does not assign `self.config_entry` again.                    |
| `home-assistant-async-callback-decorator` (`W7402`)           | No coroutine is decorated with `@callback`.                                                                                      |
| `home-assistant-sequential-executor-jobs` (`W7415`)           | Consecutive `async_add_executor_job()` calls are merged into one job instead of bouncing back to the event loop between them.    |
| `home-assistant-enforce-utcnow` (`C7414`)                     | `dt_util.utcnow()` rather than `datetime.now(UTC)`.                                                                              |
| `home-assistant-enforce-now` (`C7425`)                        | `dt_util.now()` rather than `datetime.now(<tz>)`.                                                                                |
| `home-assistant-enforce-naive-now` (`C7427`)                  | `dt_util.naive_now()` rather than a bare `datetime.now()`.                                                                       |
| `home-assistant-enforce-greek-micro-char` (`C7410`)           | Micro-prefixed units use the Greek small letter mu (U+03BC `μ`), not the ANSI micro sign (U+00B5 `µ`) — they render identically. |
| `home-assistant-logger-capital` (`C7402`)                     | Log messages above debug level start with a capital letter; if a message does not warrant one, it belongs at debug level.        |

## Manifest

| Core check                                                     | Check                                                                                                                                               |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-serial-port-selector-usb-dependency` (`W7430`) | A config flow using `SerialPortSelector` declares `usb` in `dependencies` — `after_dependencies` does not force the `usb` integration to be set up. |

## Tests

Also worth raising in a review of `tests/`; the procedure for fixing them is
[`ha-testing`](../../ha-testing/SKILL.md).

| Core check                                                                                        | Check                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `home-assistant-tests-registry-fixtures` (`R7404`)                                                | Registry access goes through the `entity_registry` / `device_registry` / `issue_registry` fixtures, not `er.async_get(hass)`.                                                 |
| `home-assistant-async-load-fixtures` (`W7404`)                                                    | Fixture files are read with async I/O, so the event loop is not blocked.                                                                                                      |
| `home-assistant-tests-direct-async-setup-entry` (`W7418`) and siblings (`W7420`–`W7422`, `W7426`) | Tests drive setup through the public path, not by calling `async_setup_entry()` (or `async_setup`, `async_migrate_entry`, `async_unload_entry`, a platform's setup) directly. |
| `home-assistant-tests-config-flow-unique-id` (`W7440`)                                            | A happy-path config flow test asserts the created entry's unique ID.                                                                                                          |
| `home-assistant-tests-config-flow-error-recovery` (`W7441`)                                       | A config flow test that shows an error finishes the flow afterwards.                                                                                                          |
| `home-assistant-tests-user-flow-no-data` (`R7405`)                                                | A user-source flow is started without `data=` — only discovery flows receive data.                                                                                            |
| `home-assistant-test-flow-start-helper` (`W7445`)                                                 | Reauth and reconfigure flows start with `entry.start_reauth_flow(hass)` / `entry.start_reconfigure_flow(hass)`, not a hand-built `context`.                                   |

## Covered by the rule that owns them

These Core checks only restate a rule another file owns — look the name up there: `home-assistant-unique-id-ip-based`
(`W7406`) → `AGENTS.md` unique-ID contract; `home-assistant-missing-entity-unique-id` (`W7423`),
`-missing-test-before-configure` (`W7433`), `-action-swallowed-exception` (`E7405`), `-exception-not-translated`
(`W7417`), `-use-runtime-data` (`W7405`) → the matching rule in [`quality-scale-rules.md`](quality-scale-rules.md);
`-config-flow-polling-field` (`W7407`), `-step_id-match-method` (`W7443`) →
[`blueprint.config_flow`](../../../instructions/blueprint.config_flow.instructions.md); `-redundant-translation-key`
(`W7442`), `-missing-super-call` (`E7404`) → [`blueprint.entities`](../../../instructions/blueprint.entities.instructions.md);
`-coordinator-entity-available` (`W7449`), `-enforce-sorted-platforms` (`C7409`) →
[`ha-entity-platform`](../../ha-entity-platform/SKILL.md); `-light-missing-color-mode` (`W7436`) / `-supported-color-modes`
(`W7437`) → [`controls.md`](../../ha-entity-platform/references/controls.md); `-service-registered-in-setup-entry`
(`W7414`), `-invalid-setup-services` (`W7453`) →
[`blueprint.service_actions`](../../../instructions/blueprint.service_actions.instructions.md); `-logger-period`
(`C7401`) → [`blueprint.python`](../../../instructions/blueprint.python.instructions.md); `-test-non-deterministic`
(`W7409`), `-unused-test-fixture-argument` (`R7402`), `-json-fixture` (`W7435`), `-tests-coordinator-async-refresh`
(`W7439`) → [`blueprint.tests`](../../../instructions/blueprint.tests.instructions.md).
