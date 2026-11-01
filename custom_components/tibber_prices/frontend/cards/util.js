/**
 * Helpers without state of their own: the level colors, number and price formats, averages,
 * escaping, and the browser's storage for a card's remembered choices.
 */

// Same colors as the charts from get_apexcharts_yaml (level_type: level), so a column and the
// chart area at that time look alike
export const LEVEL_COLORS = {
  very_cheap: "#2ecc71",
  cheap: "#27ae60",
  normal: "#f1c40f",
  expensive: "#e67e22",
  very_expensive: "#e74c3c",
};

// Number format from the user's profile (decimal comma or point), like HA's own cards
export function numberLocale(hass) {
  const format = hass.locale && hass.locale.number_format;
  const locales = { comma_decimal: "en-US", decimal_comma: "de-DE", space_comma: "fr-FR", system: undefined };
  return format in locales ? locales[format] : hass.language;
}

// The user's profile decides: the server's time zone or the browser's
export function timeZone(hass) {
  const locale = hass.locale || {};
  return locale.time_zone === "local" ? undefined : hass.config.time_zone;
}

// The integration's entities of one home (device), found by translation key: the card is set
// up by picking the home, not one of its ~100 entities
const HOME_ENTITIES = {
  price: "current_interval_price",
  // The direction prices move in now: a small icon on "now"
  trend: "current_price_trend",
  best: "best_price_period",
  peak: "peak_price_period",
};

// The first home with a price outlook (its device), for a card added from the card picker
export function firstHomeDevice(hass) {
  const entry = Object.values(hass.entities || {}).find(
    (e) => e.platform === "tibber_prices" && e.translation_key === HOME_ENTITIES.price && e.device_id
  );
  return entry ? entry.device_id : "";
}

export function homeEntities(hass, config) {
  const found = {};
  if (config.device_id && hass.entities) {
    for (const entry of Object.values(hass.entities)) {
      if (entry.platform !== "tibber_prices" || entry.device_id !== config.device_id) continue;
      for (const [key, translationKey] of Object.entries(HOME_ENTITIES)) {
        if (entry.translation_key === translationKey) found[key] = entry.entity_id;
      }
    }
  }
  return found;
}

// Color of a price level (normal for an unknown one), as in the charts
export function levelColor(level) {
  return LEVEL_COLORS[level] || LEVEL_COLORS.normal;
}

// Prices with two decimals, or whole numbers once they reach 10 (øre, ct); "–" for none
export function priceFormatter(hass, numbers) {
  return fixedPriceFormat(hass, Math.max(...numbers.map(Math.abs)) >= 10 ? 0 : 2);
}

// Prices with a fixed number of decimals ("–" for none), or from `decimals` up to `maxDecimals`
// (the quarter hours of an hour's details: as the data has them, see EXACT_DECIMALS in
// forecast-card.js); the format carries its decimals, which percentages between shown prices are
// rounded to (see shownPrice). Kept per locale and decimals: building an Intl format is the
// costly part
const PRICE_FORMATS = new Map();
export function fixedPriceFormat(hass, decimals, maxDecimals = decimals) {
  const locale = numberLocale(hass);
  const key = `${locale}|${decimals}|${maxDecimals}`;
  if (!PRICE_FORMATS.has(key)) {
    const number = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: maxDecimals,
    });
    const format = (value) => (typeof value === "number" ? number.format(value) : "–");
    format.decimals = maxDecimals;
    PRICE_FORMATS.set(key, format);
  }
  return PRICE_FORMATS.get(key);
}

// A price as shown by `format` (rounded to its decimals): what percentages between shown prices
// are computed from, so they agree with the numbers next to them ("0,67 → 0,67" is ±0 %, not
// +1 % from digits that aren't shown)
export function shownPrice(format, value) {
  return format && typeof format.decimals === "number" ? Number(value.toFixed(format.decimals)) : value;
}

// A whole percentage with a real minus sign; the formatters are kept per language and sign
const PERCENT_FORMATS = new Map();
export function formatPercent(language, value, signDisplay) {
  const key = `${language}|${signDisplay}`;
  if (!PERCENT_FORMATS.has(key)) {
    PERCENT_FORMATS.set(
      key,
      new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 0, signDisplay })
    );
  }
  return PERCENT_FORMATS.get(key).format(value).replace("-", "\u2212");
}

// The best and peak price periods overlapping a stretch of time, as { k, a, b }
export function periodsTouching(periods, start, end) {
  return ["best", "peak"].flatMap((k) =>
    periods[k].filter(([a, b]) => a < end && start < b).map(([a, b]) => ({ k, a, b }))
  );
}

// How far a price lies from a base, as a share of the base, both as shown by their formats
// (undefined without a usable base): percentages agree with the prices next to them
export function shownChange(value, base, format, baseFormat = format) {
  if (typeof value !== "number" || typeof base !== "number") return undefined;
  const shownBase = shownPrice(baseFormat, base);
  return shownBase === 0 ? undefined : (shownPrice(format, value) - shownBase) / Math.abs(shownBase);
}

// A time of day, with midnight at the end of a span as 24:00
export function endTime(clock, time) {
  return clock.format(new Date(time)).replace(/^00:00$/, "24:00");
}

export function timeRange(clock, start, end) {
  return `${clock.format(new Date(start))}–${endTime(clock, end)}`;
}

// "About as …" → "about as …": a sentence's start used inside a line
export function lowerFirst(text) {
  return text.replace(/^\p{Lu}/u, (letter) => letter.toLowerCase());
}

export function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const HOUR_MS = 3600000;
export const QUARTER_MS = 900000;
export const LEVEL_STEPS = ["very_cheap", "cheap", "normal", "expensive", "very_expensive"];

// Text from the user (a card title) as HTML text: never markup
export function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// A text with its {placeholders} filled in
export function fill(text, values) {
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in values ? values[name] : match));
}

// Mean or median of some prices
export function aggregate(values, kind) {
  if (kind !== "median") return values.reduce((sum, v) => sum + v, 0) / values.length;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

// The level of several quarter hours together: the rounded average of their steps
export function levelOfMany(levels) {
  const steps = levels.map((level) => LEVEL_STEPS.indexOf(level)).filter((step) => step >= 0);
  if (!steps.length) return undefined;
  return LEVEL_STEPS[Math.round(steps.reduce((sum, step) => sum + step, 0) / steps.length)];
}

/**
 * Where bars start: a quarter of the spread below the lowest price, never below zero while
 * prices are positive. Like temperatures in a weather forecast, so small differences show
 * (from zero, prices of 0.80 to 1.10 would all be three quarters high or more); the numbers
 * under the bars carry the exact values. With all prices equal, from zero
 */
export function barBaseline(values) {
  const lowest = Math.min(...values);
  const highest = Math.max(...values);
  if (highest === lowest) return Math.min(0, lowest - 1);
  const base = lowest - (highest - lowest) * 0.25;
  return lowest >= 0 ? Math.max(0, base) : base;
}

// The price key and its label for the average shown ("⌀" for the mean)
export function averageOf(t, kind) {
  return kind === "median" ? { key: "price_median", label: t.median } : { key: "price_mean", label: "⌀" };
}

// Browser storage that may be missing (private mode, blocked site data): never fails
export function storedValue(key) {
  try {
    return window.localStorage.getItem(key) || undefined;
  } catch (err) {
    return undefined;
  }
}

export function storeValue(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (err) {
    // Only a convenience: the choice is just not remembered
  }
}

export function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
