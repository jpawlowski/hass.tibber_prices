---
name: ha-user-experience
description: >-
  Design what users of this Home Assistant custom integration see and work with — states to show and trigger on,
  attributes for dashboards and automations, icons that follow the state, help inside the UI, options that stay
  navigable, actions shaped for automations, and dashboard helpers. Use when asked to "make it user-friendly",
  "improve the UX", "make it work well on dashboards", "make it easy to automate", "explain the options in the UI",
  "too many options", "add descriptions to the entities", "dynamic icons", or when deciding which entities,
  attributes or actions to offer. Covers reading, operating and automating, each option and its cost, and workarounds for missing
  slots. SYMPTOMS — load this if you are about to: put a value someone triggers on into an attribute; leave an enum
  state untranslated; add an option without saying what it does; chain options flow steps without a menu; return
  action data in an ad-hoc shape; let a library exception escape an action; or overwrite files the user may have
  edited.
---

# Design the user experience

A working integration and a good one differ mostly in what this skill covers: whether the state reads well on a
dashboard, whether the user understands an option without opening the documentation, and whether an automation can
use the integration without a template. None of it comes for free, and none of it is a Quality Scale requirement on
its own.

**Everything here is an option with a cost, not a rule.** The developer decides which ones the integration takes; ask
in their terms ("will people put this on a dashboard, use it in an automation, or both?") and record the answer.
Small integrations need little of it. This skill decides _what_ to build; the rules live in the `blueprint.*`
instructions files and the procedures in the matching `ha-*` skills, linked where they apply.

## Reference files

| File                                               | When to read                                                       |
| -------------------------------------------------- | ------------------------------------------------------------------ |
| [`references/patterns.md`](references/patterns.md) | Implementing one of the patterns below — code, keys, and its traps |

## 1. Three ways to use an integration

User experience is everything a person does with the integration and how it feels to them (ISO 9241-210), not only
what they see — the visual part is the UI. For an integration that is three kinds of use, and the sections follow
them:

| Use        | What the user does                                       | Sections |
| ---------- | -------------------------------------------------------- | -------- |
| Reading    | looks at a dashboard, the more-info dialog, the history  | 2–4      |
| Operating  | sets it up, changes options, reacts to an error          | 5–6      |
| Automating | builds automations and scripts on its states and actions | 7        |

Home Assistant designs for
[three user types](https://contributors.home-assistant.io/design/users/): Outgrowers want it to just work, Tinkerers
know their way around code, Questioners want advanced automation but need support to get there. Check an option
against all three — whom it helps, and whom it gets in the way of.

### Reading and automating pull apart

Every value is read by people and by automations, and what suits one often hinders the other:

| A dashboard needs                                  | An automation needs                                         |
| -------------------------------------------------- | ----------------------------------------------------------- |
| a readable, translated state and a fitting icon    | a stable state value that never changes with the language   |
| rounded numbers (`suggested_display_precision`)    | the full value, and an ordinal it can compare (`< 0`)       |
| a series to draw — a list, more than a state holds | a single fact to trigger on — a state, not an attribute     |
| relative times ("in 20 minutes")                   | an absolute timestamp, and minutes-until for a numeric test |
| few entities, the rest out of sight                | the one entity it needs, even if nobody displays it         |

The answer is rarely to pick a side. Give the entity a state for both, and put each audience's extras where they cost
the other nothing: display-only data in unrecorded attributes or a disabled-by-default entity, automation-only values
as attributes beside the state. Decide this per entity before writing the `EntityDescription` — changing it later
changes entity IDs, states or attributes, which [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md) covers.

## 2. States

- **Something people trigger on is a state.** "Is it in the cheap period", "is a fault active" → a binary sensor or
  an enum sensor. A `state` trigger works on it directly; an attribute needs a template trigger.
- **A fixed set of values is an enum sensor** (`SensorDeviceClass.ENUM` with `options`), every value translated
  ([rule](../../instructions/blueprint.translations.instructions.md#language-aware-from-the-first-line)) —
  untranslated states are the most common gap in custom integrations.
- **An ordered enum gets an ordinal beside it** — `level: "high"` as the state, `level_value: 1` as an attribute — so
  an automation can test "at least high" without listing values. [`patterns.md`](references/patterns.md#ordinal-beside-an-enum).

### Which entities are on after setup

Disabled by default is a decision per entity, and it gets more important the more entities an integration offers.
The mechanics are in
[`blueprint.entities`](../../instructions/blueprint.entities.instructions.md#disabled-and-hidden-by-default); the
choice is:

- **On:** what most users expect to find after setup — the device's main function and its few key readings. The
  device page should read well without the user touching anything.
- **Off:** what only some setups need — a variant of a value already shown (another unit, another time window), a
  per-slot or per-hour breakdown, technical detail, anything that changes every few seconds.
- **With many entities, justify each one that is on.** Twenty enabled sensors on one device is a page nobody reads,
  and every one of them writes to the database.
- **The cost of off is discoverability.** Say in the user documentation which entities exist disabled and what they
  are for, and where an option depends on one, say so in the form ([`patterns.md`](references/patterns.md#context-in-a-form)).
- The default applies only when an entity is first registered — choosing it is cheap now and impossible to change
  for existing installs later.

### The platform that fits

Home Assistant has a platform for most kinds of value and function, and each brings its own UI, voice support and
automation triggers. Modelling everything as a sensor plus an action throws that away. Before adding an entity, find
the most specific fit:

| What it is                                        | Platform                                                        | Instead of                                   |
| ------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------- |
| a yes/no fact                                     | `binary_sensor` with a device class                             | a sensor whose state is "on" or "off"        |
| one of a fixed set of values                      | `sensor` with `ENUM`                                            | a free-text sensor                           |
| a point in time                                   | `sensor` with `TIMESTAMP`, or `date` / `time`                   | a formatted string                           |
| a device setting with a value                     | `number`, `select`, `switch`, `text`, `time` in `CONFIG`        | an action, or an option in the options flow  |
| a one-shot command                                | `button`, with `RESTART`, `UPDATE` or `IDENTIFY` where they fit | an action, a switch that turns itself off    |
| something that happens rather than holds          | `event`                                                         | a sensor holding the last event              |
| firmware and its updates                          | `update`                                                        | a version sensor, a `binary_sensor` `UPDATE` |
| an agenda or a list of items                      | `calendar`, `todo`                                              | a list in an attribute                       |
| a picture                                         | `image`                                                         | a URL in an attribute                        |
| a whole appliance — heating, fan, cover, valve, … | its domain platform (`climate`, `fan`, `cover`, `valve`, …)     | a bundle of sensors and switches             |

- **A device setting is an entity, not an option.** The options flow configures the integration; what configures the
  device belongs on the device page, in `CONFIG`, where automations can change it too.
- The per-platform members and traps are in [`ha-entity-platform`](../ha-entity-platform/SKILL.md).

### Diagnostic or primary

The category answers what an entity is about, and is decided separately from on or off
([rule](../../instructions/blueprint.entities.instructions.md#entity-categories)):

|                | Enabled by default                                  | Disabled by default                                |
| -------------- | --------------------------------------------------- | -------------------------------------------------- |
| **Primary**    | the main readings and controls                      | a secondary reading few need — another time window |
| **Diagnostic** | what users watch for trouble — connection, data age | noisy detail — signal strength, raw API counters   |

- **Give a service integration its own diagnostics too**: last successful update, API status, data age. That is what
  users look at when "the values look stale", and what an automation can alert on.
- **An entity or the diagnostics download?** A value someone watches over time or alerts on is a diagnostic entity; a
  one-off dump for a bug report belongs in `diagnostics.py`.

### Prepared values, not raw data

A user should not need a template sensor, a helper or an automation just to make one of the integration's entities
useful. The device or API delivers raw data; the integration's job is to turn it into what people actually want.

- **The test:** if most users of an entity would build the same template — a sum, a difference, "is it below the
  daily average", the start of the next cheap period, a conversion — the integration provides it.
- **Raw values nobody uses directly** move out of sight: an unrecorded attribute, a disabled-by-default entity, or
  nothing at all.
- **Not every statistic.** Home Assistant's own helpers (statistics, utility meter, derivative, min/max) cover generic
  aggregation; rebuild one only when the device's own data does it better.
- The computation lives in the coordinator, once, not in each entity — the layering in `AGENTS.md`.

### Units users think in

A device picks its unit for technical reasons; the integration picks the one users think in.

- **Where Home Assistant can convert** — a device class with a unit converter (`UNIT_CONVERTERS` in the installed
  `sensor/const.py`): set the unit the device delivers as `native_unit_of_measurement`, choose the default display
  unit with `suggested_unit_of_measurement`, and let the user switch in the entity settings. Do not convert yourself
  ([`blueprint.python`](../../instructions/blueprint.python.instructions.md)).
- **Where it cannot** — money, a currency subunit, a price per kWh, anything without a device class: converting is the
  integration's job. Make it an option with a default from context (the account's currency, the region's custom —
  cents for euro electricity prices, the main unit for kroner), and say so in its `data_description`.
- **Units come from Home Assistant's constants** ([`blueprint.python`](../../instructions/blueprint.python.instructions.md));
  for money, `hass.config.currency` gives the ISO code to pick the symbol from.
- `SensorDeviceClass.MONETARY` takes an ISO 4217 code as its unit and only `state_class: total`; it has no converter.

### One entity per purpose when they conflict

Some Home Assistant features need a fixed unit or shape that is not what people want to read. Do not make the main
entity compromise: give that feature an entity of its own, disabled by default, and keep the main entity for people.

- **The energy dashboard reads a price in the main currency.** It takes only the part after `/` from the unit and
  multiplies the value as the user's currency — a cent price there is off by a factor of 100. So the main price entity
  follows the display option (cents by default where that is the custom), and a second entity, disabled by default,
  always carries the main unit for the energy dashboard. Where the main unit is already the default, the user simply
  does not need the second one. [`patterns.md`](references/patterns.md#units-without-a-converter).
- The same applies wherever a feature fixes the shape: long-term statistics need a `state_class` a display-only
  entity should not have, and a chart card may need a series the main entity has no room for.
- Name the purpose in the entity's name and description ("… for the energy dashboard"), so users find it when the
  feature asks for it.

## 3. Attributes

Entity or attribute is a three-step test in
[`blueprint.entities`](../../instructions/blueprint.entities.instructions.md#custom-state-attributes). What it means
for reading and automating: the automation's trigger becomes an entity, the dashboard's series and the automation's
extras (an ordinal, a minutes-until value) become attributes beside the state, and help text or chart data stays out
of the recorder. Translate attribute names and enum attribute values too
([`ha-translations`](../ha-translations/SKILL.md)), so the more-info dialog shows no raw keys.

**Attributes are part of the UI, not only data for automations.** They are where a curious user finds out more
about a value without opening the documentation — why a period was chosen, what a value is compared to. The rules
for their shape, display names and keys are in
[`blueprint.entities`](../../instructions/blueprint.entities.instructions.md#custom-state-attributes); the design on
top of them:

- **The key is for templates, the display name for people.** Build keys as one hierarchy across the integration,
  subject to detail (`period_start`, `period_end`, `period_duration_minutes`), with the scope in the name
  (`next_3h_average`), the reference of a comparison (`price_diff_from_daily_min`), a singular `_count`, and
  qualified generic words (`data_status`).
- **The dialog sorts by display name, per language** (`ha-more-info-details.ts` in the frontend), so nothing can be
  pinned to the top by ordering the dict. Word display names so related attributes start alike and sort together;
  prominence comes from the state, the name and the icon. Rewording a display name breaks nothing.
- **A plain value gets its own row** with a locale-formatted value; a dict becomes a raw YAML block
  (`ha-attribute-value.ts`). What a person should read is flat.
- **Still keep one order in the dict** — time reference, decision values, further values, comparisons, detail, bulk
  data, help text: it is what the YAML view, developer tools and the API show.

### What belongs in the recorder

The recorder keeps every state change with its attributes for 10 days by default (`purge_keep_days`), and long-term
statistics, indefinitely, only for entities with a `state_class`. An integration cannot exclude an entity's state
from recording; what it controls is:

- **Whether the value is an entity at all**, and whether it is on by default (above) — a disabled entity records
  nothing — and its `state_class`: none for a value whose history is uninteresting tomorrow
  ([rule](../../instructions/blueprint.entities.instructions.md)).
- **Which attributes are recorded.** What matters only now or today — the schedule for the coming hours, a list for
  a chart, help text — goes into `_unrecorded_attributes`.
- **How often the state is written.** `_unrecorded_attributes` keeps a value out of the database, not out of the
  state machine: every change is still a state write and a `state_changed` event. A minutes-until value means a write
  per minute; a long help text travels with every write.

A user who wants less can exclude whole entities with `recorder: exclude` — worth a line in the user documentation for
an integration with many frequently changing entities.

## 4. Icons and colors

- **An icon that changes with the state tells the story at a glance** — `icons.json` `state` or `range`, which also
  shows the right icon in the history and in state selectors; where code is allowed instead is in
  [`blueprint.entities`](../../instructions/blueprint.entities.instructions.md).
- **A color hint is a workaround.** Home Assistant has no color slot; an attribute (`icon_color`) holding a theme
  variable such as `var(--warning-color)` serves custom cards and card templates, and the default frontend ignores
  it. Theme variables, never hex values, so it follows the user's theme. Unrecorded.
  [`patterns.md`](references/patterns.md#color-hints).

## 5. Help inside the UI

The aim: a user can set up and use the integration without opening the documentation. The documentation then explains
more, not the basics.

- **Every option says what it does and what changes** in its `data_description` — the effect, the useful range, an
  example. Markdown works there.
- **Context instead of generic text.** A description placeholder can say what applies to this user right now: "none
  of the entities this page affects are enabled — enable …", or "3 of these fields are currently set by entities".
  [`patterns.md`](references/patterns.md#context-in-a-form).
- **Entity descriptions are a workaround.** Home Assistant has no slot for "what is this entity for". A `description`
  attribute filled from the integration's own translated text, optionally switchable to a long form, answers it on
  the more-info dialog. Cost: the text is in the server's language, not each user's; it needs its own loader; it must
  be unrecorded, and it still travels with every state write — keep it short, the long form in `docs/user/`. [`patterns.md`](references/patterns.md#entity-descriptions).
- **A failure the user can fix is a repair issue** that names the cause and the fix, not a log line.

## 6. Options that stay navigable

- **Up to one screen:** one form, rarely-used fields in a collapsed `section()`.
- **More than that:** a menu (`async_show_menu`) whose entries each open one topic and return to the menu, with
  `menu_option_descriptions` explaining each entry and a "save" entry. The user jumps to what they want instead of
  paging through everything. [`patterns.md`](references/patterns.md#menu-based-options-flow).
- **Defaults from what the account already says** — the currency, the region, the device's capabilities — and the
  `data_description` says that it did.
- **Settings an automation should change** cannot live in the options flow alone, which no automation can drive. A
  `number`, `switch` or `select` entity in `EntityCategory.CONFIG`, disabled by default, can override the option.
  Cost: two sources of truth — the options form must show which fields an entity currently controls.
  [`patterns.md`](references/patterns.md#settings-automations-can-change).

## 7. Automations

[`ha-service-action`](../ha-service-action/SKILL.md) covers how to build an action. What automations need from one:

- **An action earns its place** for computation on demand with parameters, data no state can hold (a range, a list),
  or a one-shot command. Anything that is a state of the device is an entity.
- **Response data is an interface.** Stable keys, ISO 8601 timestamps, units stated in the key or the data, one shape
  per action — or an explicit format parameter. `SupportsResponse.OPTIONAL` when it is both a command and a query.
  [`patterns.md`](references/patterns.md#response-data).
- **Parameters default to what most calls want**, selector options are translated, and fields go into `sections` once
  they pile up.
- **Errors an automation can skip, and calls that are safe twice** — the rules are in
  [`blueprint.service_actions`](../../instructions/blueprint.service_actions.instructions.md).
- Events the integration can detect ("a fault was reported") are a trigger platform, not an event the user has to
  filter — [`ha-service-action`](../ha-service-action/SKILL.md#triggers-and-conditions).

## 8. Dashboards and starting points

Optional, and each one is real work to keep working:

- **An action that returns ready dashboard YAML** (`SupportsResponse.ONLY`) spares users the hardest part of a chart.
  When it needs a custom card or an entity that is disabled, say what is missing and how to fix it.
- **Shipped custom cards** register their own resource, so the user adds nothing by hand.
  [`patterns.md`](references/patterns.md#shipped-cards).
- **Shipped blueprints** are copied only when they are missing — never over a file the user may have edited.
  [`patterns.md`](references/patterns.md#shipped-blueprints).

## 9. Languages

Which languages ship is the developer's product decision. Being ready for them is not optional: every integration is
written language-aware from the first line, even if it stays English-only for years — the rules are in
[`blueprint.translations`](../../instructions/blueprint.translations.instructions.md#language-aware-from-the-first-line).
The agent rule stays: change `en.json` only, and another language file only when asked
([`ha-translations`](../ha-translations/SKILL.md)).

Nothing in Home Assistant's tooling checks that every enum option is translated, that every attribute has a display
name, or that no language file keeps a key `en.json` no longer has. `tests/test_translations.py` checks all three through the
running entities, before a user sees a raw key.

## Do not

- ❌ Do not turn these options into requirements. Ask which ones the integration should take.
- ❌ Do not use an attribute as the only place for something users trigger on.
- ❌ Do not present a workaround (color hints, entity descriptions) as a Home Assistant feature.
- ❌ Do not overwrite a file the integration ships — a blueprint, a dashboard — once its content differs from what
  was shipped: the user edited it.
