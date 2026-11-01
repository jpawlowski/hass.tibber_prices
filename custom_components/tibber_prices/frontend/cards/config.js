/**
 * The options every card has and the forecast card's (the now and chart card build on them):
 * what each may hold, its defaults, the checks setConfig and the editors run, and the editor
 * fields more than one card has. The now and chart card's own are in their modules.
 */

import { PRICE_SOURCES } from "./data.js";

// Which scroll buttons the strips show: both sides, only forward (into the future), only back,
// or none (swiping and scrolling work anyway)
export const SCROLL_BUTTONS = ["both", "forward", "back", "none"];

const PRICE_UNITS = ["auto", "base", "subunit"];

// Which average the prices shown and the dashed line in the strips use: as set for the
// integration's average sensors, the mean (default) or the median. The pointers of the parts of
// the day and the line in the day rows always use the median: it shows where prices lean
// within a span. "As set in the integration" comes first in every dropdown
const AVERAGES = ["auto", "mean", "median"];

// The card's sections. Tapping an hour, part of the day or day opens its details, unless turned
// off in the section's hide_details (then a tap runs the card's action, like anywhere else).
// "now" is a line of its own: the current price and what to make of it (it opens the details of
// the hour running now). It goes where it is in the order; first or last it spans the card,
// between strips it joins them. It is no tab of the compact layout: there it stays in view, above
// the tabs when first, else below them
export const SECTIONS = ["now", "hours", "day_parts", "days"];

// Which days the day rows show, and what tomorrow's row does until its prices are published:
// say when they usually come, or stay away (a card left with nothing to show hides itself)
export const DAYS_SHOWN = ["both", "today", "tomorrow"];
export const TOMORROW_PENDING = ["placeholder", "hide"];

// Per section, the details that can be left out (`hide`); what makes the section stays: the
// hours with their bars and prices, the parts of the day with their spans, the days with theirs
export const SECTION_HIDES = {
  now: ["gauge", "verdict", "trend", "day_span"],
  hours: ["reference", "tomorrow", "weekday", "cheapest", "periods", "badge", "low", "high", "steps"],
  day_parts: [
    "pointer",
    "now",
    "range",
    "reference",
    "tomorrow",
    "weekday",
    "cheapest",
    "periods",
    "badge",
    "low",
    "high",
  ],
  days: ["compare", "pointer", "now", "level", "volatility", "badge", "low", "high"],
};

// Options of each section (`hours:`, `day_parts:`, `days:` in YAML) when not set; a card added
// from the card picker carries the days' ones, so the editor shows them selected
export const SECTION_DEFAULTS = {
  now: { now_decimals: "entity" },
  hours: { now_decimals: "entity" },
  day_parts: { now_decimals: "entity" },
  days: { shown: "both", tomorrow_pending: "placeholder", now_decimals: "entity" },
};

// Decimals of the current price in a section's details: as set for the price entity in Home
// Assistant (default), or a fixed number
export const NOW_DECIMALS = ["entity", "0", "1", "2", "3", "4"];

// Where the card's own action button sits: at the bottom (default) or the top of the card
export const ACTION_BUTTON_POSITIONS = ["bottom", "top"];

// Values the card uses when an option isn't set. A card added from the card picker carries them
// (so the editor shows them selected, not empty), and so does the dashboard from get_dashboard_yaml
export const DEFAULTS = {
  price_unit: "auto",
  price_source: "total",
  average: "mean",
  layout: "detailed",
  appearance: "auto",
  scroll_buttons: "both",
  action_button_position: "bottom",
  show_title: false,
  chart_button: false,
  chart_icon: "mdi:chart-line",
  window_width: "medium",
};

// Light or dark: as Home Assistant shows it (default; HA itself follows the browser or the
// user's profile), or always one of them, e.g. a dark card on a light dashboard
const APPEARANCES = ["auto", "light", "dark"];

// Home Assistant's own colors per mode, for the variables the card and ha-card read (taken from
// its frontend). The page carries only the active mode's values, so a forced mode starts here.
// The card's own background and border follow them, unless the theme sets them for that mode:
// a value the theme sets only for the page's mode must not show through
const CARD_COLORS = {
  "ha-card-background": "var(--card-background-color)",
  "ha-card-border-color": "var(--divider-color)",
};
const MODE_COLORS = {
  light: {
    "primary-text-color": "#141414",
    "secondary-text-color": "#5e5e5e",
    "disabled-text-color": "#bdbdbd",
    "card-background-color": "#fff",
    "primary-background-color": "#fafafa",
    "secondary-background-color": "#e5e5e5",
    "divider-color": "#0000001f",
    "outline-color": "#0000001f",
    "rgb-primary-text-color": "33, 33, 33",
    "rgb-card-background-color": "255, 255, 255",
  },
  dark: {
    "primary-text-color": "#e1e1e1",
    "secondary-text-color": "#9b9b9b",
    "disabled-text-color": "#6f6f6f",
    "card-background-color": "#1c1c1c",
    "primary-background-color": "#111",
    "secondary-background-color": "#282828",
    "divider-color": "#e1e1e11f",
    "outline-color": "#e1e1e11f",
  },
};

/**
 * CSS variables for showing the card in `mode` while the page is in the other one, built the way
 * Home Assistant applies a theme: its colors for that mode, then the theme's own values, then the
 * theme's values for that mode. Null for a theme without that mode (an always light or always
 * dark theme): there is nothing to switch to, so the card stays as the page is.
 */
export function modeVariables(themes, mode) {
  const theme = themes.theme && themes.theme !== "default" ? themes.themes?.[themes.theme] : undefined;
  if (theme && !theme.modes?.[mode]) return null;
  const { modes, ...base } = theme || {};
  const vars = { ...MODE_COLORS[mode], ...CARD_COLORS, ...base, ...(modes ? modes[mode] : {}) };
  // Like HA, an rgb-* twin for every hex color the theme doesn't give one for
  for (const [key, value] of Object.entries(vars)) {
    const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(value));
    if (!hex || vars[`rgb-${key}`] !== undefined) continue;
    const digits = hex[1].length === 3 ? [...hex[1]].map((d) => d + d) : hex[1].match(/../g);
    vars[`rgb-${key}`] = digits.map((d) => parseInt(d, 16)).join(", ");
  }
  return vars;
}

// Icons of the compact switch; alone on narrow cards, where three words don't fit
export const SECTION_ICONS = {
  now: "mdi:progress-clock",
  hours: "mdi:clock-outline",
  day_parts: "mdi:weather-sunset",
  days: "mdi:calendar-range",
};

// The price shown, checked alike by the cards and the tile feature
export function validatePriceSource(config) {
  if (config.price_source && !PRICE_SOURCES.includes(config.price_source)) {
    throw new Error("`price_source` is `total` (taxes and fees included) or `energy` (the energy price alone)");
  }
}

// Errors for config values the card can't use; setConfig and the visual editor check the same
export function validateConfig(config) {
  if (config.price_unit && !PRICE_UNITS.includes(config.price_unit)) {
    throw new Error("`price_unit` is `auto`, `base` or `subunit`");
  }
  validatePriceSource(config);
  if (config.average && !AVERAGES.includes(config.average)) {
    throw new Error("`average` is `auto` (as set in the integration), `median` or `mean`");
  }
  if (config.layout && !["detailed", "compact"].includes(config.layout)) {
    throw new Error("`layout` is `detailed` (all sections) or `compact` (one section with a switch)");
  }
  for (const section of SECTIONS) {
    const options = config[section];
    if (options === undefined) continue;
    if (!options || typeof options !== "object" || Array.isArray(options)) {
      throw new Error(`\`${section}\` holds the section's options, e.g. \`hide: [${SECTION_HIDES[section][0]}]\``);
    }
    if (options.now_decimals !== undefined && !NOW_DECIMALS.includes(String(options.now_decimals))) {
      throw new Error(`\`${section}.now_decimals\` is \`entity\` (as the price entity shows it) or 0 to 4`);
    }
    if (
      options.hide &&
      !(Array.isArray(options.hide) && options.hide.every((x) => SECTION_HIDES[section].includes(x)))
    ) {
      throw new Error(`\`${section}.hide\` lists details to leave out: ${SECTION_HIDES[section].join(", ")}`);
    }
  }
  const days = config.days || {};
  if (days.shown && !DAYS_SHOWN.includes(days.shown)) {
    throw new Error("`days.shown` is `both`, `today` or `tomorrow`");
  }
  if (days.tomorrow_pending && !TOMORROW_PENDING.includes(days.tomorrow_pending)) {
    throw new Error("`days.tomorrow_pending` is `placeholder` (say when the prices come) or `hide`");
  }
  if (config.scroll_buttons && !SCROLL_BUTTONS.includes(config.scroll_buttons)) {
    throw new Error("`scroll_buttons` is `both`, `forward`, `back` or `none`");
  }
  if (config.appearance && !APPEARANCES.includes(config.appearance)) {
    throw new Error("`appearance` is `auto` (as Home Assistant shows it), `light` or `dark`");
  }
  if (config.action_button_position && !ACTION_BUTTON_POSITIONS.includes(config.action_button_position)) {
    throw new Error("`action_button_position` is `bottom` or `top`");
  }
  if (config.chart_button !== undefined && typeof config.chart_button !== "boolean") {
    throw new Error("`chart_button` is `true` (an icon top right opening the chart card) or `false`");
  }
  if (config.chart_icon !== undefined && typeof config.chart_icon !== "string") {
    throw new Error("`chart_icon` is an icon, e.g. `mdi:chart-line`");
  }
  if (config.window_width && !WINDOW_WIDTHS.includes(config.window_width)) {
    throw new Error("`window_width` is `narrow`, `medium`, `wide` or `full`");
  }
}

// Editor fields both cards share (HA draws the form with its own selectors)
export const dropdown = (options) => ({ select: { mode: "dropdown", options } });
// Options with the one in effect when nothing is set marked "(default)": the editor shows the
// value that applies, and which of them is the default
export function marked(e, values, label, fallback) {
  return values.map((value) => ({
    value,
    label: value === fallback ? `${label(value)} (${e.default_mark})` : label(value),
  }));
}
export const EDITOR_FIELDS = {
  // The icon top right opening the chart card in a window, and which icon
  chartButton: () => [
    { name: "chart_button", selector: { boolean: {} } },
    { name: "chart_icon", visible: { field: "chart_button", value: true }, selector: { icon: {} } },
  ],
  // How wide the window of another card is
  windowWidth: (e) => ({
    name: "window_width",
    selector: dropdown(marked(e, WINDOW_WIDTHS, (value) => e[`window_width_${value}`], DEFAULTS.window_width)),
  }),
  // Only Tibber Prices homes (and their time-travel views): no wrong entity to pick
  device: () => ({ name: "device_id", selector: { device: { filter: { integration: "tibber_prices" } } } }),
  priceUnit: (e) => ({
    name: "price_unit",
    selector: dropdown(marked(e, PRICE_UNITS, (value) => e[`unit_${value}`], DEFAULTS.price_unit)),
  }),
  priceSource: (e) => ({
    name: "price_source",
    selector: dropdown(marked(e, PRICE_SOURCES, (value) => e[`price_source_${value}`], DEFAULTS.price_source)),
  }),
  average: (e) => ({
    name: "average",
    selector: dropdown(
      marked(e, AVERAGES, (value) => (value === "auto" ? e.unit_auto : e[`average_${value}`]), DEFAULTS.average)
    ),
  }),
  appearance: (e) => ({
    name: "appearance",
    selector: dropdown(marked(e, APPEARANCES, (value) => e[`appearance_${value}`], DEFAULTS.appearance)),
  }),
  nowDecimals: (e) => ({
    name: "now_decimals",
    selector: dropdown(
      marked(e, NOW_DECIMALS, (value) => (value === "entity" ? e.now_decimals_entity : value), "entity")
    ),
  }),
  // Tap, then hold and double tap (added on demand), and the entity "More info" opens
  // (`helper` names the tap's help text where it differs)
  gestures: (helper) => [
    { name: "tap_action", selector: { ui_action: { default_action: "none" } }, helper },
    {
      name: "",
      type: "optional_actions",
      flatten: true,
      schema: [
        { name: "hold_action", selector: { ui_action: { default_action: "none" } } },
        { name: "double_tap_action", selector: { ui_action: { default_action: "none" } } },
      ],
    },
    // Any entity in Home Assistant; empty: the home's price sensor
    { name: "entity", selector: { entity: {} } },
  ],
};

// How wide that window is (on phones it's full screen anyway): about HA's more-info dialog, a
// medium width (default), wide, or the whole screen
const WINDOW_WIDTHS = ["narrow", "medium", "wide", "full"];
