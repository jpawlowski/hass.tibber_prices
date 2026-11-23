# When a config entry migration fails

The contract — raise rather than return `False`, `ConfigEntryNotReady` versus `ConfigEntryError` — is in
[`blueprint.config_flow.instructions.md`](../../../instructions/blueprint.config_flow.instructions.md#version-and-migration).
This is what happens after each, and what the integration has to add for the second.

## `ConfigEntryNotReady`

Raise it when the migration needs the device or the service and cannot reach it right now. Home Assistant retries the
migration on the same backoff as a setup retry; nothing else is needed.

## `ConfigEntryError`

Raise it when retrying unchanged cannot succeed — the stored data is inconsistent, or the user has to do something
first. The entry stays in `migration error`, and without help only a restart of Home Assistant tries again. Give the
user a way out:

1. Before raising, create a fixable repair issue for the entry — `issue_id` and `data` carry the entry ID, severity
   `ERROR`, since the integration has stopped working
   ([`blueprint.repairs`](../../../instructions/blueprint.repairs.instructions.md)).
2. In `repairs.py`, the fix flow explains what the user has to do and, on confirmation, calls
   `await hass.config_entries.async_retry_migration(entry_id)` before finishing with `async_create_entry(data={})`.
3. Delete the issue once the migration succeeds, so a fix done another way — a restart, a manual correction — does
   not leave it behind.
4. Test both paths: the migration that raises creates the issue, and the fix flow re-runs it
   ([`ha-testing`](../../ha-testing/SKILL.md)).
