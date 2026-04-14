"""
Entity migration checks for Tibber Prices integration.

Detects obsolete entity keys in the entity registry after upgrades and
performs automatic migration where possible. Creates repair issues to
notify users about breaking changes that require manual action.

Separation of concerns:
- This module: One-time upgrade migrations (entity renames, breaking changes)
- coordinator/repairs.py: Runtime repairs (API issues, missing data)
- __init__.py _migrate_config_options(): Config option format changes
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# ============================================================================
# ENTITY KEY RENAMES
# Add entries here when renaming sensors in future releases.
# old_entity_key -> new_entity_key (auto-migrated, entity_id preserved)
# ============================================================================
ENTITY_KEY_RENAMES: dict[str, str] = {
    "trend_change_in_minutes": "next_price_trend_change_in",
}


@callback
def check_entity_migrations(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """
    Check for entity migrations and create repairs if needed.

    Called during async_setup_entry, before platform forwarding.
    Performs auto-migration of renamed entities and creates
    informational repairs about breaking changes.
    """
    ent_reg = er.async_get(hass)

    # Auto-migrate renamed entity keys
    migrated = _auto_migrate_entity_keys(ent_reg, entry)

    # Create persistent repair about breaking changes
    issue_id = f"entity_migration_{entry.entry_id}"

    if migrated:
        rename_lines = [f"- `{old_key}` → `{new_key}`" for old_key, new_key, _ in migrated]
        entity_list = "\n".join(rename_lines)

        _LOGGER.info(
            "Auto-migrated %d entity key(s) for '%s': %s",
            len(migrated),
            entry.title,
            ", ".join(f"{old} → {new}" for old, new, _ in migrated),
        )

        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="entity_migration",
            translation_placeholders={
                "home_name": entry.title,
                "entity_list": entity_list,
                "count": str(len(migrated)),
            },
            learn_more_url="https://github.com/jpawlowski/hass.tibber_prices/releases",
        )


@callback
def _auto_migrate_entity_keys(
    ent_reg: er.EntityRegistry,
    entry: ConfigEntry,
) -> list[tuple[str, str, str]]:
    """
    Auto-migrate renamed entity keys in the entity registry.

    Updates unique_ids for renamed entities while preserving entity_id
    and all user customizations (history, dashboard references, etc.).

    Returns:
        List of (old_key, new_key, entity_id) tuples for migrated entities

    """
    migrated: list[tuple[str, str, str]] = []
    prefix = f"{entry.entry_id}_"

    # Get all entities for this config entry
    entry_entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    for entity_entry in entry_entities:
        if not entity_entry.unique_id.startswith(prefix):
            continue

        entity_key = entity_entry.unique_id[len(prefix) :]
        if entity_key not in ENTITY_KEY_RENAMES:
            continue

        new_key = ENTITY_KEY_RENAMES[entity_key]
        new_unique_id = f"{prefix}{new_key}"

        # Check if new entity already exists (e.g., from a partial migration)
        new_entity_id = ent_reg.async_get_entity_id(entity_entry.domain, DOMAIN, new_unique_id)

        if new_entity_id:
            # New entity already exists — remove the obsolete old one
            _LOGGER.debug(
                "Removing obsolete entity '%s' (new entity '%s' already exists)",
                entity_entry.entity_id,
                new_entity_id,
            )
            ent_reg.async_remove(entity_entry.entity_id)
        else:
            # Migrate: update unique_id (preserves entity_id and history)
            _LOGGER.debug(
                "Migrating entity '%s': unique_id '%s' → '%s'",
                entity_entry.entity_id,
                entity_entry.unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=new_unique_id,
            )

        migrated.append((entity_key, new_key, entity_entry.entity_id))

    return migrated
