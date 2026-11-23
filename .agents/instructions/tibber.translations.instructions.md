---
name: "Tibber Translations and User Docs"
description: "Five languages, the two translation folders, generated attribute names and sensor reference, store names, user docs"
applyTo: "custom_components/tibber_prices/translations/**, custom_components/tibber_prices/custom_translations/**, custom_components/tibber_prices/blueprints/**, script/i18n/**, docs/user/docs/**, README.md"
paths:
  - "custom_components/tibber_prices/translations/**"
  - "custom_components/tibber_prices/custom_translations/**"
  - "custom_components/tibber_prices/blueprints/**"
  - "script/i18n/**"
  - "docs/user/docs/**"
  - "README.md"
---

# Translation and User Documentation Instructions

**Procedure:** [`ha-translations`](../skills/ha-translations/SKILL.md) — load it before adding or changing strings.
This file adds this integration's own rules to `blueprint.translations` and to the `docs/user/` section of
`blueprint.markdown`. Which languages a change covers: the project rules in [`AGENTS.md`](../../AGENTS.md).

## Traps

- **Address the reader informally in every language: German "du", Dutch "je"/"jouw", Swedish and Norwegian "du".**
  Home Assistant's own translations do, and `tests/test_translation_tone.py` holds it. Its patterns are narrow on
  purpose — German "Sie wurde entfernt" or "ihr Zuhause" refer to a feminine noun, Dutch "u" can be "uur" — so
  rephrase a sentence that reads like formal address at a glance even when the test passes.
- **`translations/` holds only what Home Assistant's schema allows; everything else — entity descriptions, usage
  tips, store names, hints of the service actions — goes into `custom_translations/`.** Both are loaded once at setup
  (`async_load_translations()`, `async_load_standard_translations()`) and read synchronously with `get_translation()`
  from `const.py`; never open a translation file at runtime.
- **Never edit `state_attributes` in `translations/*.json` by hand; change `script/i18n/attribute-names.json` and run
  `python3 script/i18n/generate-attribute-translations.py`.** The names derive from the attribute declarations, and
  the lint check fails on any difference.
- **After adding or renaming an entity or changing its name, run `python3 script/docs/generate-sensor-reference.py`.**
  `docs/user/docs/sensor-reference.md` is generated from the translations, and the lint check fails while it is
  stale.
- **Never write a store name into a string that takes `{store}`.** `store_name()` in
  `service_actions/get_apexcharts_yaml.py` fills it per Home Assistant version, with the article each language
  needs, to match the link `_store_link()` builds.
- **Text that cannot branch on the version — blueprints, service descriptions in `translations/`, the README — keeps
  the `hacs_repository` My link and names both stores ("the Marketplace or HACS").** That link works on every
  supported version.
- **Keep the "Not affiliated with Tibber" notice and the AI development note in the README outside the
  `ha-marketplace:exclude` markers.** Store users must see both before they install.
- **In user docs, name an entity by its translated display name and add its `translation_key` on first mention in a
  section: ``**Best Price Period** (`best_price_period`)``.** Users read the UI in their language; the key finds the
  entity in any of them.
- **A user doc page with entity ID examples opens with the `:::tip Entity ID tip` box, in the wording the existing
  pages use.** It links the multi-language sensor reference, which is where users find an entity that looks missing.
- **Examples use a European home: heat pump, dishwasher ECO program, EV charging, water heater; prices in ct/kWh or
  øre/kWh; 24-hour times; ISO dates.** Tibber's markets are European, and US appliance habits mislead there.
