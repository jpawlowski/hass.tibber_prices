# Entity lifecycle hooks

Beyond `async_added_to_hass()` and `async_on_remove()` — the rule for those is in
[`blueprint.entities`](../../../instructions/blueprint.entities.instructions.md).

- Work that must run before the entity is added — even for an add that is then aborted, such as a disabled entity —
  goes in `async_prepare_to_add_to_hass()`. Do not rely on `entity_id` or `registry_entry` there, and register its
  cleanup with `async_on_remove`: `async_will_remove_from_hass` is not guaranteed to run after an aborted add.
- **Never override `add_to_platform_start`, `add_to_platform_finish` or `add_to_platform_abort`** — they are internals
  of the entity platform; use the hook above.
- A subscription keyed on `self.entity_id` that is replaced later is released through
  `self.async_on_remove(lambda: self._unsub())`, not `self.async_on_remove(self._unsub)` — the latter keeps calling the
  first, stale unsubscribe function.
- `async_entity_id_changed(old_entity_id)` is a `@callback` that moves such a subscription when the user renames the
  entity ID. A class that defines `async_added_to_hass`, `async_will_remove_from_hass` or
  `async_prepare_to_add_to_hass` must implement it as well: without it, the entity is removed and re-added on a rename,
  a fallback that goes in 2027.11 ([`deprecations.md`](../../ha-modern-apis/references/deprecations.md)).
