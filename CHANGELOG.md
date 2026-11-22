# Changelog

## [0.40.1](https://github.com/jpawlowski/hass.tibber_prices/compare/v0.40.0...v0.40.1) (2026-11-22)


### ⚡ More Reliable

* **cards:** load the dashboard cards gzip-compressed ([#278](https://github.com/jpawlowski/hass.tibber_prices/issues/278)) ([4e1d93e](https://github.com/jpawlowski/hass.tibber_prices/commit/4e1d93ebeb27643db6539d6656f4063893f7d1e6))

## [0.40.0](https://github.com/jpawlowski/hass.tibber_prices/compare/v0.39.1...v0.40.0) (2026-11-22)

### ⚠️ Before You Update: Some Attribute Names Change

- **Attributes that ended in `_%` now end in `_percent`**, for example `rating_difference_%` → `rating_difference_percent`. They belong to the best and peak price period sensors and to the trend, rating and volatility sensors.

**What this means for you:** If a template, automation or dashboard card reads one of these attributes, change the name. After the update, a notice in **Settings → Repairs** lists every renamed attribute.

### 🎉 What's New

- **Attribute names in your language.** The more-info dialog now shows attribute names translated into English, German, Norwegian, Dutch and Swedish instead of the technical key, for example "Difference from daily maximum (%)". The dialog sorts attributes by their displayed name, so the order differs per language.

### 🐛 Fixed

- **Diagnostics files no longer contain personal data.** The home's address, coordinates, home ID, names and account email are removed from the diagnostics download, so you can attach it to a public issue.
- **The connection sensor and the chart export show readable attribute names** instead of raw keys.
- **The chart export no longer fills the database.** Its full result was stored in the history; now only the attributes it declares are kept, and unknown attributes of other entities aren't stored either.
- **The attribute rename notice reads fully in your language.** Its hint about the rating sensors was still in English in the German, Norwegian, Dutch and Swedish texts.

### ⚡ More Reliable

- **The Home Assistant database grows more slowly.** Attributes that repeat the state or can be recalculated from the recorded prices are no longer kept in the history, for example the trend percentages, next-hours averages, volatility statistics and timing minutes. The states and the main numbers stay in the history, and rows already stored are unchanged.
