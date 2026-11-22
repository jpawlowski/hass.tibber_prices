---
name: "Repair Flows"
description: "Creating issues, implementing RepairsFlow, and the issue lifecycle"
applyTo: "custom_components/**/repairs.py"
paths:
  - "custom_components/**/repairs.py"
---

# Repairs Instructions

**Procedure:** [`ha-breaking-changes`](../skills/ha-breaking-changes/SKILL.md) — load it before creating an issue.
This file is the rule set; the skill is what a repair issue is _for_ — a migration or a deprecation the user has to
act on — and the warn-first policy that comes before either.

**Official Documentation:**

- [Repairs Framework](https://contributors.home-assistant.io/core/integrations/repairs/)
- [Issue Registry](https://contributors.home-assistant.io/core/integrations/repairs/#create-an-issue)

## Overview

Repair Flows guide users through fixing issues (expired credentials, deprecated settings, missing configuration, etc.).

**Key differences from Config Flow:**

- **Location**: `repairs.py` in integration root (NOT in `config_flow_handler/`)
- **Base class**: `homeassistant.components.repairs.RepairsFlow` (NOT `ConfigFlow`)
- **Trigger**: System creates issue → user clicks "Fix" → Repair Flow runs
- **Purpose**: Fix existing problems, not create new config entries

## Architecture

**Lifecycle:**

1. Integration detects issue → `async_create_issue()`
2. User clicks "Fix" → `async_create_fix_flow()` called with issue_id
3. Repair flow guides user through steps
4. Flow ends with `async_create_entry()` → Home Assistant deletes the issue itself. An abort, including a hand-over
   through `next_flow`, leaves it in place.

## Creating Issues

```python
from homeassistant.helpers import issue_registry as ir

ir.async_create_issue(
    hass,
    DOMAIN,
    f"deprecated_option_{entry.entry_id}",
    is_fixable=True,  # Shows "Fix" button; requires a fix flow
    severity=ir.IssueSeverity.WARNING,
    translation_key="deprecated_option",
    translation_placeholders={"key": "value"},  # Optional
    breaks_in_ha_version="2027.1",  # Optional: when this stops working
    learn_more_url="https://…",  # Optional: link to docs/user/
    issue_domain=DOMAIN,  # Optional: only when raising on another integration's behalf
    data={"entry_id": entry.entry_id},  # Optional: reaches async_create_fix_flow
)
```

**An issue about one config entry carries the entry ID in its `issue_id`.** Issue IDs are unique per domain only;
without it, the issues of two entries overwrite each other. Put the entry ID in `data` as well — the repair flow reads
it from there, not from `self.handler`, which is the domain.

**Entry-scoped issues:** `config_entry_id=entry.entry_id` on `async_create_issue` ties the issue to the entry — hidden
while it is disabled, deleted when it is removed, so no cleanup code is needed — and `ir.async_refresh_issues()`
re-checks a whole set of issues (one per device, say) without deleting and re-creating the ones that still apply.
Never delete an entry's issues in `async_unload_entry`: a reload unloads too, and every issue the user ignored would
come back.

`is_persistent=True` marks an issue that only exists because it was observed once — an update that failed, an
unknown action in an automation — so it must survive a restart. Leave it off for anything the integration re-checks
on its own, such as a deprecated option found during setup; that one comes back by itself if it is still true.

**Only raise an issue the user can act on.** Something broken that they cannot fix themselves is a log entry, not a
repair.

**Ignoring is sticky.** An ignored issue stays ignored across restarts until it is deleted — by the integration or by
the user completing its flow — and then created again. Re-creating the same `issue_id` on every coordinator update is
therefore harmless; inventing a new id each time defeats the user's choice.

`ir.async_create_issue` must run in the event loop. From a worker thread use `ir.create_issue` / `ir.delete_issue`.

**When to create:**

- During `async_setup_entry()` - Config validity, API compatibility
- In coordinator updates - Deprecated endpoints, expired features
- On API responses - Device warnings, missing capabilities

## Repair Flow Implementation

**Without a `repairs.py`, Home Assistant answers every fixable issue with `ConfirmRepairFlow`.** Once the file exists,
`async_create_fix_flow` decides for every issue of the domain, so it returns `ConfirmRepairFlow()` for the ones that
only need an acknowledgement.

**Required function in repairs.py:**

```python
async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow for issue_id."""
    return MyRepairFlow()
```

**When the fix is just "acknowledge and I will handle it", do not write a flow class** — return the built-in one:

```python
from homeassistant.components.repairs import ConfirmRepairFlow

return ConfirmRepairFlow()
```

**Flow class structure** (only when the user has something to enter or choose):

```python
from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.repairs.models import RepairsFlowResult

class MyRepairFlow(RepairsFlow):
    async def async_step_init(self, user_input=None) -> RepairsFlowResult:
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(str(self.data["entry_id"]))
            # Apply the fix to entry, then:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")
```

Home Assistant sets `self.issue_id` and `self.data` (the issue's `data`) on the flow after `async_create_fix_flow`
returns it — do not pass them in yourself, they would be overwritten. `self.handler` is the **domain**, never an entry
ID.

The form mechanics are Data Entry Flow's and are identical to the config flow's — see
[`blueprint.config_flow`](blueprint.config_flow.instructions.md). What differs here: `async_create_entry(data={})`
always takes an **empty** dict, and it removes the issue on its own.

**Redirecting to reauth** — start the flow, then finish; the issue goes with the `create_entry`:

```python
async def async_step_init(self, user_input=None):
    if user_input is not None:
        entry = self.hass.config_entries.async_get_entry(str(self.data["entry_id"]))
        entry.async_start_reauth(self.hass)
        return self.async_create_entry(data={})
    return self.async_show_form(step_id="init")
```

When the fix continues in a reconfigure or options flow, hand over with
`self.async_abort(reason=…, next_flow=(FlowType.CONFIG_FLOW, flow_id))`. An abort does not remove the issue: delete it
in the step that completes the fix.

## Translations

**Exactly one of `fix_flow` and `description` per issue** — never both. Which one depends on `is_fixable`. `title` is
required; `short_title` is an optional shorter form for tight spaces.

**What the text says.** The description or the flow step explains what is happening and why it matters, gives the
exact steps to fix it — a numbered list when there are several, and how, not just "update the firmware" — says what to
expect afterwards, and names the device or entry concerned through a placeholder.

Not fixable (`is_fixable=False`) — the user reads it and acts elsewhere:

```json
{
  "issues": {
    "api_key_expired": {
      "title": "Issue title",
      "description": "Description with {placeholder}"
    }
  }
}
```

Fixable (`is_fixable=True`) — the flow's own steps carry the text. `ConfirmRepairFlow` shows its form in step
`confirm`; a custom flow uses the `step_id`s it passes to `async_show_form`:

```json
{
  "issues": {
    "deprecated_option": {
      "title": "Issue title",
      "fix_flow": {
        "step": {
          "confirm": {
            "title": "Repair step title",
            "description": "Instructions"
          }
        }
      }
    }
  }
}
```

## Rules

**MUST:**

- Place `repairs.py` in integration root (NOT in `config_flow_handler/`)
- Implement `async_create_fix_flow()` function returning `RepairsFlow` subclass
- Delete the issue yourself when the problem goes away on its own, or after a fix that ended in an abort — a flow that
  ends in `async_create_entry` needs no delete
- Set `is_fixable=True` only if repair flow exists
- Provide translations for all text (title, description, fix_flow steps)
- Validate user input before applying fixes
- Pick severity by tense, not by urgency: `ERROR` — something is broken **now** and needs attention; `WARNING` —
  something breaks **later** (an API shutdown, a removal). A deprecation issue is `WARNING` while the old behaviour
  still works and becomes `ERROR` once it has stopped — the removal shipped, or a migration failed. `CRITICAL` is
  reserved for true panic and has no use in this integration.

**SHOULD:**

- Keep repair steps simple (1-2 steps maximum)
- Use existing patterns (reauth, reconfigure) when applicable
- Reload entry after config changes: `hass.config_entries.async_schedule_reload(entry.entry_id)`, which also cancels
  a pending setup retry

**NEVER:**

- Copy `from __future__ import annotations` out of the upstream examples — this repository dropped it repo-wide and
  Ruff rejects it
- Put repair flows in `config_flow_handler/` (separate system)
- Delete an issue only to create it again — that resets the user's "ignore"
- Use repair flows for normal config changes (use reconfigure instead)
- Create issues without translations
- Skip validation of user input
