# The flow types, one by one

Read the section for the flow you are implementing. The rules that hold across all of them — data versus options,
unique IDs, reserved step names, schemas, versioning — are in
[`blueprint.config_flow.instructions.md`](../../../instructions/blueprint.config_flow.instructions.md) and load
automatically.

## User flow

Nothing beyond the general rules: validate before creating, set the unique ID and abort on a duplicate, return errors
by translation key, log unexpected exceptions. With discovery in the manifest, see the `raise_on_progress` rule under
step names in the instructions file.

## Discovery flow

**MUST:**

- Set unique ID in discovery step
- Abort if already configured: `self._abort_if_unique_id_configured()`
- Store placeholders for title: `self.context["title_placeholders"] = {"name": device_name}`
- Forward to user step for confirmation
- Update existing entries via `updates` parameter when device details change
- Type the step's argument with the protocol's service info class from `homeassistant.helpers.service_info.<protocol>`
  — `async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult`. The old imports from
  `homeassistant.components.<protocol>` are gone. Bluetooth is the exception: `BluetoothServiceInfoBleak` from
  `homeassistant.components.bluetooth`; `integration_discovery` takes whatever the starting integration sends.

**NEVER:**

- Auto-create entries without user confirmation
- Skip unique ID check

The `manifest.json` side, and the rule per protocol that fails silently when guessed, is in
[`discovery-matchers.md`](discovery-matchers.md).

## Reauth flow

**MUST:**

- Implement `async_step_reauth()` that forwards to `async_step_reauth_confirm()`
- Use `self._get_reauth_entry()` to access current entry
- Verify unique ID unchanged: `await self.async_set_unique_id(id)` then `self._abort_if_unique_id_mismatch()`
- Check source: `if self.source == SOURCE_REAUTH`
- Update entry: `return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=user_input)`
- Set description placeholders: `description_placeholders={"name": self._get_reauth_entry().title}`

**NEVER:**

- Create new entry (always update existing)
- Skip unique ID verification
- Skip confirmation step

**Translation keys:**

- `config.step.reauth_confirm.title` — Core's wording, `"Authentication expired for {name}"`
  ([copy it out](../../../instructions/blueprint.translations.instructions.md#cores-shared-strings))
- `config.step.reauth_confirm.description` — explain what expired

Which abort reasons need no key of your own:
[`ha-translations`](../../ha-translations/SKILL.md#abort-reasons-home-assistant-translates-itself).

**From outside a flow** — a coordinator or an action handler that hits an auth error — call
`entry.async_start_reauth(hass)`. `ConfigEntryAuthFailed` only starts the flow from `async_setup_entry` in
`__init__.py` or from the coordinator.

## Reconfigure flow

**MUST:**

- Use `self._get_reconfigure_entry()` to access current entry
- Verify unique ID unchanged if applicable: `await self.async_set_unique_id(id)` then
  `self._abort_if_unique_id_mismatch()`
- Check source: `if self.source == SOURCE_RECONFIGURE`
- Update entry: `return self.async_update_reload_and_abort(entry, data_updates=user_input)`
- Pre-fill form: `self.add_suggested_values_to_schema(schema, entry.data)`

**NEVER:**

- Create new entry (always update existing)
- Use for authentication changes (use reauth)

**Optional:** `reload_even_if_entry_is_unchanged=False` skips the reload when nothing changed.

## Options flow

Only for behaviour the user tunes after setup — never the polling interval
([`blueprint.config_flow`](../../../instructions/blueprint.config_flow.instructions.md)). An integration with nothing
to tune ships no options flow.

**MUST:** Return via `async_get_options_flow()`, implement `async_step_init()`, pre-fill with existing options.

The handler is constructed with **no arguments** (`return OptionsFlowHandler()`); the base class provides
`self.config_entry`. Older examples that store it themselves are wrong.

**Auto-reload:** subclass `OptionsFlowWithReload`. Every change has one reload owner: this class for options,
`async_update_reload_and_abort` for reauth and reconfigure. **Do not add an update listener (`entry.add_update_listener`)
next to them** — see [`deprecations.md`](../../ha-modern-apis/references/deprecations.md). Where one genuinely must
stay, finish with `async_update_and_abort` and pass `reload_on_update=False`, and let the listener reload. Any other
reload from code is `hass.config_entries.async_schedule_reload(entry.entry_id)`, not `async_reload`.

## Subentry flow

**MUST:** Return types via `async_get_supported_subentry_types()`, implement `async_step_user()`, finish with
`async_create_entry()` — on `ConfigSubentryFlow` it returns a `SubentryFlowResult`. There is no
`async_create_subentry()`.

**Access and reconfigure:** `self._get_entry()` for the parent entry, `self._get_reconfigure_subentry()` for the
subentry being edited, and `async_update_and_abort()` to finish a reconfigure step.

**NEVER:** Support discovery or reauth in subentries — a subentry flow can only start from `user` or `reconfigure`.

**Unique IDs:** a subentry's unique ID only has to be unique within its config entry, not globally.

**Translations:** subentry strings live under `config_subentries.<type>.…`, not under `config`.

**Devices:** one per subentry, the hub or account device on the parent entry, related by `via_device_id` —
[`device-registry.md`](../../ha-modern-apis/references/device-registry.md).

## Chaining flows

`next_flow` and `async_on_create_entry()` continue into another flow once an entry exists. Subentry and options flows
depend on the config entry already existing, so they **can only** be reached through `async_on_create_entry()`.

## Fields that depend on another field

`data_entry_flow.Required(..., visible={"field": …, "value": …})` hides a field until another one matches, and
`UnitOfMeasurementSelector` narrows its units by a device-class field — no extra step or re-shown form needed. A hidden
field is absent from `user_input`; read it with `.get()` and a fallback.
