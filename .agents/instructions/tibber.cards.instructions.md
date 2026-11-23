---
name: "Tibber Cards"
description: "The bundled dashboard cards: module layering, cards inside cards, the energy card, price source, serving"
applyTo: "custom_components/tibber_prices/frontend/**"
paths:
  - "custom_components/tibber_prices/frontend/**"
---

# Dashboard Card Instructions

The cards are plain JavaScript web components in `frontend/cards/`, served by `frontend/__init__.py` and loaded into
every frontend with `add_extra_js_url`; users add no dashboard resource. How the parts fit together:
[`ARCHITECTURE.md`](../../docs/development/ARCHITECTURE.md#dashboard-cards).

## Traps

- **Put the version into the directory URL, never into a `?v=` query.** A query does not reach the modules the entry
  imports, so after an update the browser mixes new modules with cached old ones.
- **No bundler or minifier; gzip copies exist only in the release zip.** Add a build tool only after measuring it
  against the gzip copies, and never commit a `*.js.gz`: an edit during development would hide behind it.
  Source: docs/development/decisions/20261123-cards-plain-es-modules.md
- **A card module imports only from the layers before it, never in a cycle.** The order is in the header of
  `tibber-prices-cards.js`; `extends` and interpolated styles run while a module is evaluated, so a cycle breaks at
  load time. A new module is also imported by name in the entry, so the browser fetches it right away.
- **Side effects — registering elements, `customCards`, the tile feature — happen only in the entry.** The exception
  is `editors.js`, loaded by `import()` from `loadEditors()` in `base.js` and registering itself, so no page without
  an open editor loads it.
- **A cache lives in the module that uses it; a shared declaration goes into the lowest layer all its users share.**
  Icon paths stay together in `ui.js`. Moving a declaration higher than needed pulls modules into each other's
  layer.
- **Cards refer to each other by element name (`WINDOW_CARDS`), never by import.** Importing another card couples two
  layers that the window mechanism keeps apart.
- **A card shown inside another card is opened through `windowCards` and edited through `nestedCards`; never copy its
  `getConfigForm()` schema into an expandable.** A copied schema drifts from the card's real editor with the next
  option. Whether a card opens another is decided only in `_opens(key)` of the base class.
- **The energy card is the chart card plus hooks, never a copy.** A change to the chart card reaches it only through
  the hooks the chart card offers (`_tomorrowShown()`, `_drawsWithoutPrices()`, `_extraParts()` and the others).
- **Keep the energy card's rules that look arbitrary.** The solar forecast is drawn only after the recorded
  production, so a recording gap stays a gap; the sun's curves only between sunrise and sunset (`sunTimes()`), the
  battery's at all times; the right axis fits every curve with data, whatever the legend shows.
- **Read the price sensor only through `priceState()` in `data.js`.** A card that reads `hass.states[...]` directly
  ignores the `price_source` option. Levels, volatility and periods stay those of the total price, and costs use the
  totals, so the cards never disagree with the integration's sensors.
- **A state a script sets on a container is a class `is-…`, `has-…` or `no-…`; an element's kind is a bare word.** A
  bare word on a container also matches an element of that name inside it. Shared style pieces (`BASE_STYLE`,
  `LIVE_DOT_STYLE`, `ACTION_BUTTON_STYLE`) are interpolated, never copied.
- **Only `reload.js` tells a page its cards are outdated, and it only shows a notice, never reloads by itself.** A
  page reloading on its own loses what the user was doing. The check is called from the `hass` setters of the card
  base class and the tile feature, and from `loadEditors()` when loading fails.
