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

from .const import CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_BASE, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# A notice (only to read and confirm) is "fixable": HA then offers to confirm it instead of only
# to ignore it, and deletes it once confirmed (with no repairs platform, HA's own confirm flow
# shows the fix_flow text). Ignored, it would stay in the registry for good
NOTICES: frozenset[str] = frozenset(
    {
        "entity_migration",
        "period_day_price_unit",
        "currency_display_mode_changed",
        "period_flex_base",
        "attribute_percent_renamed",
    }
)


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
    _tidy_notices(hass, entry)

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
            is_fixable=True,  # A notice to confirm (see NOTICES)
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

    # Get all entities for this config entry (including its time-travel views)
    entry_entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    for entity_entry in entry_entities:
        # Entities of a time-travel view carry the subentry in their unique_id
        # (see device.entity_unique_id) - strip that too, so key renames reach
        # the views as well and not just the live entities.
        prefix = f"{entry.entry_id}_"
        if entity_entry.config_subentry_id:
            prefix = f"{prefix}{entity_entry.config_subentry_id}_"

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


def _notify(hass: HomeAssistant, entry: ConfigEntry, key: str) -> None:
    """Create the confirmable notice `key` for this entry (see NOTICES)."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{key}_{entry.entry_id}",
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=key,
        translation_placeholders={"home_name": entry.title},
        learn_more_url="https://github.com/jpawlowski/hass.tibber_prices/releases",
    )


@callback
def async_migrate_entry_version(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Bring a config entry from an older version to the current one (VERSION 1, MINOR_VERSION 3).

    1.0 -> 1.1: day_price_min, day_price_max and day_price_span of the best/peak price periods
    are in the display unit like price_mean, no longer always in ct/øre. That changes their
    values only where prices show in the base currency (€, kr): those homes get a notice to
    review automations and templates.
    1.1 -> 1.2: period flex is a share of the gap between the daily min/max and the mean (#259),
    so the same setting gives narrower best/peak price periods (peak on every day, best on flat
    days). Every home gets a notice to review flex and automations.
    1.2 -> 1.3: attribute names ending in `_%` (rating_difference_%, ...) now end in `_percent`,
    because translated attribute names allow no `%` in their key (#267). Every home gets a notice
    to review templates and automations that read them.
    New entries start at the current version and never see these notices.
    """
    if entry.version > 1:
        # A newer version of the integration was installed before: can't go back
        return False
    if entry.minor_version < 1 and entry.options.get(CONF_CURRENCY_DISPLAY_MODE) == DISPLAY_MODE_BASE:
        _notify(hass, entry, "period_day_price_unit")
    if entry.minor_version < 2:
        _notify(hass, entry, "period_flex_base")
    if entry.minor_version < 3:
        _notify(hass, entry, "attribute_percent_renamed")
        _LOGGER.info("[%s] Migrated config entry to version 1.3", entry.title)
        hass.config_entries.async_update_entry(entry, minor_version=3)
    return True


@callback
def _tidy_notices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Bring this entry's stored notices up to date.

    - Ignored ones are deleted: an ignored issue stays in the registry, hidden, for good, and a
      notice has nothing left to say.
    - Open ones created as not fixable (by an older version) become fixable: their text now
      lives in fix_flow only, which HA shows for a fixable issue alone; otherwise the notice
      would show its bare key, and could only be ignored.
    """
    registry = ir.async_get(hass)
    for (domain, issue_id), issue in list(registry.issues.items()):
        if domain != DOMAIN or issue.translation_key not in NOTICES or not issue_id.endswith(entry.entry_id):
            continue
        if issue.dismissed_version is not None:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
        elif issue.active and not issue.is_fixable:
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                is_persistent=issue.is_persistent,
                severity=issue.severity or ir.IssueSeverity.WARNING,
                translation_key=issue.translation_key,
                translation_placeholders=issue.translation_placeholders,
                learn_more_url=issue.learn_more_url,
            )
