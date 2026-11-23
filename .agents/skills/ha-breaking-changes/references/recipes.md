# Recipes for the breaks that can be softened

Two cases where a change that would otherwise break an install has a known way out. The policy around both — warn
first, then migrate or deprecate — is in [`SKILL.md`](../SKILL.md).

## A unit whose spelling changes

Changing a unit normally breaks long-term statistics. When only the **spelling** changes (`"KWh"` to
`UnitOfEnergy.KILO_WATT_HOUR`), declare the pair equivalent instead: a `recorder.py` platform module at the
integration root with

```python
@callback
def async_custom_equivalent_units(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    """Return the units the recorder treats as the same."""
    return {entity_id: {old_unit: new_unit}}
```

keyed by the entity IDs whose unit changed.

## Deprecating an entity

Create the replacement first, and keep the old entity only while someone still uses it. In the platform's
`async_setup_entry`:

1. Look the old entity up with `entity_registry.async_get_entity_id(...)`.
2. Not in the registry — do not create it. New users never get it.
3. Disabled, and `automations_with_entity()` plus `scripts_with_entity()` find nothing — remove it from the registry.
4. Otherwise create it, and raise a non-persistent `WARNING` repair issue per entity ID that lists those automations
   and scripts and says that disabling the entity resolves it
   ([`blueprint.repairs`](../../../instructions/blueprint.repairs.instructions.md)).
