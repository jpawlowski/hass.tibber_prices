/**
 * tibber-prices-chart-card: the price curve of a stretch of time, read by moving a cursor over
 * it. Views like the zoom levels of the ApexCharts dashboard (outlook, today, tomorrow, both
 * days), each in quarter hours or hourly averages. Reads the `outlook_quarters` attribute of
 * the Current Electricity Price sensor, so it draws without a fetch.
 *
 * The cursor is the point of the card. The value it points at sits above the curve, never under
 * the finger. With a mouse it follows the pointer. On a phone a finger held still (or dragged
 * sideways) grabs it like that pointer, ticking at each slot, and leaves it where it's let go;
 * a vertical swipe scrolls the page (touch-action: pan-y), a tap sets it. Set by touch, it goes
 * back to now by itself after a while. With the keyboard the arrow keys move it. It snaps to the
 * quarter hour or hour.
 */

import {
  HOUR_MS,
  LEVEL_COLORS,
  LEVEL_STEPS,
  QUARTER_MS,
  aggregate,
  averageOf,
  capitalize,
  escapeHtml,
  fill,
  firstHomeDevice,
  fixedPriceFormat,
  formatPercent,
  homeEntities,
  levelColor,
  periodsTouching,
  shownChange,
  storeValue,
  storedValue,
  timeRange,
} from "./util.js";
import {
  CONTENT_PATH,
  EXTREME_PATHS,
  GESTURE_TAP_PATH,
  MARK_COLORS,
  MENU_DOWN,
  PERIOD_NUDGE,
  PERIOD_PATHS,
  arcPath,
  cardTitle,
  extremeIcon,
  svgIcon,
  trackKeyboard,
} from "./ui.js";
import { EDITOR_STRINGS, STRINGS, languageStrings, stringsFor } from "./strings.js";
import {
  ACTION_BUTTON_POSITIONS,
  DEFAULTS,
  EDITOR_FIELDS,
  TOMORROW_PENDING,
  dropdown,
  marked,
  validateConfig,
} from "./config.js";
import {
  averageKindOf,
  dayReferences,
  homePeriods,
  priceState,
  priceUnit,
  quarterSeries,
  quarterSlots,
  scalePrices,
} from "./data.js";
import { dayBounds, homeCalendar, zoneOffset } from "./time.js";
import { ACTION_BUTTON_STYLE, BASE_STYLE, LIVE_DOT_STYLE } from "./styles.js";
import { TibberPricesCardBase, loadEditors, validateWindowCards } from "./base.js";

// The views a card can offer; yesterday only where asked for (in `views`, or in tomorrow's place
// until its prices are in: `tomorrow_pending: yesterday`)
const CHART_VIEWS = ["outlook", "yesterday", "today", "tomorrow", "two_days"];
export const CHART_DEFAULT_VIEWS = ["outlook", "today", "tomorrow", "two_days"];
// Until tomorrow's prices are in, its tab says when they usually come, is left out, or makes way
// for yesterday's (so the tabs stay as many and where they are)
const CHART_TOMORROW_PENDING = [...TOMORROW_PENDING, "yesterday"];
// Each view's options, in YAML under its name like the forecast card's sections, and those for all
// views under `all_views` (a view's own win), e.g. `all_views: { resolution: switch_hour }` and
// `today: { hide: [low] }`. The resolution: switchable, starting at 15 or at 60 minutes (the
// choice then holding across the views until the page is loaded again), or one fixed
const CHART_RESOLUTIONS = ["switch", "switch_hour", "quarter_hour", "hour"];
// What a view can leave out; the curve always stays. The line of now separately at 15 and at
// 60 minutes (at 15 it's where the point is anyway). The dashed line is a part of each style
// The names above each day: "Today", "Tomorrow" or "Yesterday" (only where a view shows more than
// one day: else its tab says it) and the weekday, as the forecast card names its days
const CHART_HIDES = [
  "day_word",
  "day_weekday",
  "day_shade",
  "reference_label",
  "header_average",
  "low",
  "high",
  "periods",
  "badge",
  "now_line_quarter_hour",
  "now_line_hour",
];
export const CHART_SINGLE_DAY_VIEWS = ["yesterday", "today", "tomorrow"];
// What's above the curve: a line with the price and chips, a ring with the price in it (where it
// lies between the view's lowest and highest, in the area's color), or nothing
const CHART_HEADERS = ["chips", "dial", "none"];
// The unit with the prices, per place (`units: { header, tag, axis }`): the unit rate's (currency
// per kWh, e.g. ct/kWh), the currency alone (ct), or none. In the top line and the cursor's tag
// by default, at the price axis (small, above its numbers) only where asked for
const CHART_UNIT_DISPLAYS = ["full", "currency", "none"];
const CHART_UNIT_PLACES = { header: "full", tag: "full", axis: "none" };
// What a tap on the card's head opens (without a tap action): nothing, or the forecast card in a
// window (set up under `forecast`, its home the chart card's), as on the now card
const CHART_TAP_OPENS = ["nothing", "forecast"];
// Decimals of the price axis: by the unit (one in €/kr, none in ct/øre), or fixed
const CHART_AXIS_DECIMALS = ["auto", "0", "1", "2", "3"];
/**
 * How a view paints its curve: one or more styles (`styles`, the first is the default; with
 * `style_switch`, a small switch in the chart changes between them, remembered per view). A style
 * is { line, fill, reference }: the line in the price levels' colors, as the area (below and above
 * its average), or one color; the area in the price levels' colors, or below and above the
 * average of the prices shown (one level across the view, as in Tibber's app) or of each day; and
 * whether the dashed line of each day's average shows
 */
export const CHART_LINES = ["level", "average", "single"];
export const CHART_FILLS = ["level", "average_shown", "average_day"];
const CHART_DEFAULT_STYLE = { line: "level", fill: "level", reference: true };
// When the top line shows the price's level and how far it lies from the average: always, only
// while prices are being read (the cursor moved off now at rest), or never; the level only at the
// levels listed (none listed: at all), the gap only from so many percent on
const CHART_CHIP_SHOWS = ["always", "reading", "never"];
export const CHART_VIEW_DEFAULTS = {
  resolution: "switch",
  styles: [CHART_DEFAULT_STYLE],
  style_switch: false,
  hide: [],
  header_level: "always",
  header_level_at: [],
  header_delta: "always",
  header_delta_from: 0,
};
// A view's field set to this is as for all views (the editor's choice for "not set")
export const CHART_INHERIT = "inherit";
// A view's options in its editor panel (styles have their own block)
export const CHART_VIEW_FIELDS = [
  "resolution",
  "hide",
  "header_level",
  "header_level_at",
  "header_delta",
  "header_delta_from",
];
// The views' panels in the editor, with the icons of the dashboard's chart tabs
export const CHART_VIEW_ICONS = {
  all_views: "mdi:layers-outline",
  outlook: "mdi:chart-timeline-variant-shimmer",
  yesterday: "mdi:calendar-arrow-left",
  today: "mdi:calendar-today",
  tomorrow: "mdi:calendar-arrow-right",
  two_days: "mdi:calendar-range",
};
// Own colors per state and mode, for the line (`line_colors`) and the area (`fill_colors`), e.g.
// `line_colors: { cheap_dark: "#2ecc71" }`. The line's: its one color, below and above the
// average, each price level; unset, the theme's or the level's usual one. The area's: the same but
// the one color; unset, as the line's
export const CHART_COLOR_STATES = {
  line_colors: ["now", "single", "below", "above", ...LEVEL_STEPS],
  fill_colors: ["below", "above", ...LEVEL_STEPS],
  day_colors: ["yesterday", "today", "tomorrow"],
};
// The pills of the days (the one of now is in the color of now): yesterday faded, today neutral,
// tomorrow a calm violet, apart from now's blue and the levels' and average's colors
export const CHART_DAY_COLORS = {
  yesterday: "var(--disabled-text-color, #bdbdbd)",
  today: "var(--secondary-text-color, #727272)",
  tomorrow: "var(--purple-color, #926bc7)",
};
// From the theme, so a theme of one's own carries over. Not its primary color: that blue marks
// now, here and in the other cards. One color: the text color (neutral, right in light and dark);
// below the average a calm teal (apart from now's blue and the best price's green); above it the
// warning color (apart from the peak price's red). The levels keep their colors, as in all cards
export const CHART_THEME_COLORS = {
  // Now: the line, the label and the way back, in the blue of now in the other cards
  now: "var(--primary-color, #03a9f4)",
  single: "var(--primary-text-color, #212121)",
  below: "var(--teal-color, #009688)",
  above: "var(--warning-color, #ffa600)",
};
export const CHART_MODES = ["light", "dark"];
const CHART_DEFAULTS = {
  views: [...CHART_DEFAULT_VIEWS],
  price_unit: "auto",
  price_source: "total",
  price_source_switch: false,
  average: "mean",
  appearance: "auto",
  tomorrow_pending: "placeholder",
  show_title: false,
  header: "chips",
};

function validateChartConfig(config) {
  if (config.tap_opens && !CHART_TAP_OPENS.includes(config.tap_opens)) {
    throw new Error("`tap_opens` is `nothing` or `forecast` (the forecast card in a window)");
  }
  if (config.views && !(Array.isArray(config.views) && config.views.every((v) => CHART_VIEWS.includes(v)))) {
    throw new Error(`\`views\` lists the views to offer: ${CHART_VIEWS.join(", ")}`);
  }
  for (const view of ["all_views", ...CHART_VIEWS]) validateChartView(view, config[view]);
  if (config.tomorrow_pending && !CHART_TOMORROW_PENDING.includes(config.tomorrow_pending)) {
    throw new Error(
      "`tomorrow_pending` is `placeholder` (say when the prices come), `hide` or `yesterday` (yesterday in its place)"
    );
  }
  for (const [group, states] of Object.entries(CHART_COLOR_STATES)) {
    const colors = config[group];
    if (colors === undefined || colors === null) continue;
    const keys = states.flatMap((state) => CHART_MODES.map((mode) => `${state}_${mode}`));
    if (typeof colors !== "object" || Array.isArray(colors)) {
      throw new Error(`\`${group}\` holds colors by state and mode, e.g. \`${keys[0]}: "#00b4d8"\``);
    }
    for (const [key, value] of Object.entries(colors)) {
      if (!keys.includes(key)) throw new Error(`\`${group}.${key}\` is none of: ${keys.join(", ")}`);
      if (value !== undefined && value !== null && cssColor(value) === undefined) {
        throw new Error(`\`${group}.${key}\` is a color: [red, green, blue] or a CSS color like \`#00b4d8\``);
      }
    }
  }
  for (const [key, max, what] of [
    ["grid_line_width", 4, "the price lines' thickness in px, 0 (none) to 4"],
    ["day_line_width", 4, "the thickness in px of the line where a day begins, 0 (none) to 4"],
    ["grid_line_strength", 100, "the price lines' strength in percent of the text color, 0 to 100"],
    ["day_line_strength", 100, "the strength of the line where a day begins, in percent of the text color, 0 to 100"],
    [
      "day_shade_strength",
      30,
      "the strength of the shade off a day's line, in percent of the text color, 0 (none) to 30",
    ],
    ["day_shade_width", 6, "how far the shade off a day's line reaches, in hours, 0 to 6"],
  ]) {
    const value = config[key];
    if (value !== undefined && !(typeof value === "number" && value >= 0 && value <= max)) {
      throw new Error(`\`${key}\` is ${what}`);
    }
  }
  if (config.axis_decimals !== undefined && !CHART_AXIS_DECIMALS.includes(String(config.axis_decimals))) {
    throw new Error("`axis_decimals` is `auto` (one in €/kr, none in ct/øre) or 0 to 3");
  }
  for (const key of ["axis_title_x", "axis_title_y"]) {
    if (config[key] !== undefined && typeof config[key] !== "boolean")
      throw new Error(`\`${key}\` is \`true\` or \`false\``);
  }
  if (config.units !== undefined && config.units !== null) {
    const units = config.units;
    const valid =
      typeof units === "object" &&
      !Array.isArray(units) &&
      Object.entries(units).every(([place, mode]) => place in CHART_UNIT_PLACES && CHART_UNIT_DISPLAYS.includes(mode));
    if (!valid) {
      throw new Error(
        "`units` sets per place (`header`, `tag`, `axis`) `full` (e.g. ct/kWh), `currency` (e.g. ct) or `none`"
      );
    }
  }
  if (config.header && !CHART_HEADERS.includes(config.header)) {
    throw new Error("`header` is `chips` (a line with chips), `dial` (a ring) or `none`");
  }
  validateConfig(config);
}

// Errors for a view's options (or those for all views) the card can't use
function validateChartView(view, options) {
  if (options === undefined || options === null) return;
  if (typeof options !== "object" || Array.isArray(options)) {
    throw new Error(`\`${view}\` holds the view's options, e.g. \`resolution: hour\``);
  }
  if (options.resolution && !CHART_RESOLUTIONS.includes(options.resolution)) {
    throw new Error(
      `\`${view}.resolution\` is \`switch\` (15 min / 60 min, from 15), \`switch_hour\` (from 60), \`quarter_hour\` or \`hour\``
    );
  }
  if (options.hide && !(Array.isArray(options.hide) && options.hide.every((x) => CHART_HIDES.includes(x)))) {
    throw new Error(`\`${view}.hide\` lists details to leave out: ${CHART_HIDES.join(", ")}`);
  }
  if (options.styles !== undefined && options.styles !== null) {
    const valid = (style) =>
      style &&
      typeof style === "object" &&
      (style.line === undefined || CHART_LINES.includes(style.line)) &&
      (style.fill === undefined || CHART_FILLS.includes(style.fill)) &&
      (style.reference === undefined || typeof style.reference === "boolean") &&
      (style.name === undefined || typeof style.name === "string");
    if (!(Array.isArray(options.styles) && options.styles.every(valid))) {
      throw new Error(
        `\`${view}.styles\` lists styles like \`{ line: level, fill: average_shown, reference: true }\`: line ${CHART_LINES.join(" / ")}, fill ${CHART_FILLS.join(" / ")}`
      );
    }
  }
  for (const key of ["header_level", "header_delta"]) {
    if (options[key] !== undefined && !CHART_CHIP_SHOWS.includes(options[key])) {
      throw new Error(`\`${view}.${key}\` is \`always\`, \`reading\` (only while the cursor is moved) or \`never\``);
    }
  }
  if (
    options.header_level_at !== undefined &&
    !(Array.isArray(options.header_level_at) && options.header_level_at.every((x) => LEVEL_STEPS.includes(x)))
  ) {
    throw new Error(`\`${view}.header_level_at\` lists the levels to show it at: ${LEVEL_STEPS.join(", ")}`);
  }
  if (
    options.header_delta_from !== undefined &&
    !(typeof options.header_delta_from === "number" && options.header_delta_from >= 0)
  ) {
    throw new Error(`\`${view}.header_delta_from\` is a percentage, e.g. \`10\` (only from 10 % above or below on)`);
  }
  if (options.style_switch !== undefined && typeof options.style_switch !== "boolean") {
    throw new Error(`\`${view}.style_switch\` is \`true\` (a switch in the chart) or \`false\``);
  }
}

// A color from the config: [r, g, b] from the color picker, or any CSS color written in YAML
export function cssColor(value) {
  if (Array.isArray(value) && value.length === 3 && value.every((n) => Number.isFinite(Number(n)))) {
    return `rgb(${value.map(Number).join(" ")})`;
  }
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

// The price lines: how thick (px; 0: none), and how strong (percent of the text color; unset:
// the theme's divider color)
const CHART_GRID_WIDTH = 0.75;
// How long the line above the curve takes to change over: quick, but no hard cut
const CHART_TWEEN_MS = 180;
const REDUCED_MOTION = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : undefined;
// The line where a day begins: a little thicker than the price lines
const CHART_DAY_LINE_WIDTH = 1;
// The shade off a day's line: how strong at the line (percent of the text color on light
// themes; on dark ones a sixth more, where a light tint on a dark card shows less than a dark one
// on light), and how far it reaches (hours of the view, 24 px at least)
const CHART_DAY_SHADE = { strength: 6, width: 2.5, dark: 7 / 6 };
// The outlook starts this long before now: what just happened, for comparison
const CHART_BEFORE_NOW_MS = 2 * HOUR_MS;
// A cursor set by touch or keyboard goes back to now after this long without use: time to read
// and compare, not left standing for good
const CHART_RETURN_MS = 30000;
// How far a touch moves sideways before it's a drag of the cursor (not a tap or a scroll)
const CHART_DRAG_PX = 6;
// How near the mouse comes to the switches in the chart's corner before they take precedence over
// the cursor's tag
const CHART_SWITCH_ZONE_PX = 24;
// mdi:restore, on the button back to now
const RESTORE_PATH =
  "M13,3A9,9 0 0,0 4,12H1L4.89,15.89L4.96,16.03L9,12H6A7,7 0 0,1 13,5A7,7 0 0,1 20,12A7,7 0 0,1 13,19C11.07,19 9.32,18.21 8.06,16.94L6.64,18.36C8.27,20 10.5,21 13,21A9,9 0 0,0 22,12A9,9 0 0,0 13,3Z";

/**
 * The line above the curve, changed in place instead of rebuilt: elements that stay (matched by
 * `data-key`, else by tag and class) keep their identity, so their colors and the ring's arc ease
 * over (CSS transitions) and numbers marked `data-tween` count over to the new value; what's new
 * fades in. Rebuilding it from scratch would make every move of the cursor a hard cut
 */
function morphInto(target, html, tween) {
  const next = document.createElement("template");
  next.innerHTML = html;
  morphChildren(target, next.content, tween);
}

function nodeKey(node) {
  if (node.nodeType !== 1) return `#${node.nodeType}`;
  return node.getAttribute("data-key") || `${node.tagName}.${node.getAttribute("class") || ""}`;
}

function morphChildren(old, next, tween) {
  const pool = [...old.childNodes];
  const kept = [...next.childNodes].map((node) => {
    const index = pool.findIndex((candidate) => candidate && nodeKey(candidate) === nodeKey(node));
    if (index < 0) return node;
    const match = pool[index];
    pool[index] = null;
    morphNode(match, node, tween);
    return match;
  });
  for (const node of pool) if (node) node.remove();
  kept.forEach((node, i) => {
    if (old.childNodes[i] !== node) old.insertBefore(node, old.childNodes[i] || null);
  });
}

function morphNode(old, next, tween) {
  if (old.nodeType !== 1) {
    if (old.nodeValue !== next.nodeValue) old.nodeValue = next.nodeValue;
    return;
  }
  const before = old.getAttribute("data-value");
  for (const { name } of [...old.attributes]) if (!next.hasAttribute(name)) old.removeAttribute(name);
  for (const { name, value } of [...next.attributes])
    if (old.getAttribute(name) !== value) old.setAttribute(name, value);
  if (old.hasAttribute("data-tween")) {
    tween(old, next.textContent, Number(before));
    return;
  }
  morphChildren(old, next, tween);
}

// Text as wide as the room text at least (both in one cell, the room unseen), aligned to its end
// (or start)
function steadyText(room, text, align = "end") {
  return `<span class="steady${align === "end" ? "" : ` ${align}`}"><span class="room" aria-hidden="true">${room}</span><span>${text}</span></span>`;
}

/**
 * The best or peak price period a slot falls in: its kind, its parts within the slot (more than
 * one period of a kind can touch an hour), whether it covers only part of the slot (an hour of
 * which a period holds a quarter or two), and where the whole period starts and ends
 */
function slotPeriod(periods, start, end) {
  const touching = periodsTouching(periods, start, end);
  if (!touching.length) return undefined;
  const { k } = touching[0];
  const own = touching.filter((p) => p.k === k);
  const parts = own.map((p) => [Math.max(start, p.a), Math.min(end, p.b)]).sort((a, b) => a[0] - b[0]);
  const covered = parts.reduce((sum, [a, b]) => sum + (b - a), 0);
  return {
    k,
    parts,
    partial: covered < end - start - 1000,
    // The whole period, beyond the slot too (the hours next to it may share it)
    start: Math.min(...own.map((p) => p.a)),
    end: Math.max(...own.map((p) => p.b)),
  };
}

// A style with its defaults, and a key for it (to remember the one picked)
export function chartStyle(style) {
  return { ...CHART_DEFAULT_STYLE, ...(style || {}) };
}

// Whether a view's option is set: a list left empty counts as not set
export function isSet(value) {
  return value !== undefined && value !== null && value !== "" && !(Array.isArray(value) && !value.length);
}

/**
 * A view's options, for the card and its editor alike: its own, else those for all views, else
 * the defaults (`all_views`: what a view without its own gets). A list left empty counts as not
 * set; the styles and their switch go together (a view with styles of its own switches between
 * those as it says)
 */
export function chartViewOptions(config, view, defaults = CHART_VIEW_DEFAULTS) {
  const own = view === "all_views" ? {} : config[view] || {};
  const all = config.all_views || {};
  const pick = (key) => (isSet(own[key]) ? own[key] : isSet(all[key]) ? all[key] : defaults[key]);
  const stylesFrom = isSet(own.styles) ? own : isSet(all.styles) ? all : defaults;
  return {
    ...Object.fromEntries(CHART_VIEW_FIELDS.map((key) => [key, pick(key)])),
    styles: stylesFrom.styles.map(chartStyle),
    style_switch: Boolean(stylesFrom.style_switch),
  };
}

export function chartStyleId(style) {
  return `${style.line}.${style.fill}.${style.reference ? 1 : 0}`;
}

/**
 * The colors of lines and areas in light or dark: own ones from the config, else the theme's (one
 * color, below and above the average) or the level's usual one; the area's, unset, as the line's
 */
export function chartColors(config, dark) {
  const mode = dark ? "dark" : "light";
  const own = (group, state) => cssColor((config[group] || {})[`${state}_${mode}`]);
  const line = Object.fromEntries(
    CHART_COLOR_STATES.line_colors.map((state) => [
      state,
      own("line_colors", state) || CHART_THEME_COLORS[state] || LEVEL_COLORS[state],
    ])
  );
  const fill = Object.fromEntries(
    CHART_COLOR_STATES.fill_colors.map((state) => [state, own("fill_colors", state) || line[state]])
  );
  const days = Object.fromEntries(
    CHART_COLOR_STATES.day_colors.map((state) => [state, own("day_colors", state) || CHART_DAY_COLORS[state]])
  );
  return { line, fill, days };
}

// The line and the dashed average of a style's icon (see chartStyleIcon), wherever it shows
export const STYLE_ICON_STYLE = `
  .icon-line path { fill: none; stroke-width: 1.6; stroke-linejoin: round; }
  .icon-reference { stroke: var(--secondary-text-color); stroke-width: 1; stroke-dasharray: 2 1.5; }
`;

// A style as a small curve: four steps, two of them above the average, in its colors
export function chartStyleIcon(style, colors) {
  const ref = 6.5;
  const steps = [
    { x: 0, w: 6, y: 9.5, level: "cheap" },
    { x: 6, w: 5, y: 5.5, level: "normal" },
    { x: 11, w: 5, y: 2, level: "very_expensive" },
    { x: 16, w: 6, y: 10.5, level: "very_cheap" },
  ];
  const above = (step) => step.y < ref;
  const area = steps
    .map((step) => {
      if (style.fill === "level") {
        return `<rect x="${step.x}" y="${step.y}" width="${step.w}" height="${14 - step.y}" style="fill:${colors.fill[step.level]};opacity:0.4"></rect>`;
      }
      const top = above(step)
        ? `<rect x="${step.x}" y="${step.y}" width="${step.w}" height="${ref - step.y}" style="fill:${colors.fill.above};opacity:0.45"></rect>`
        : "";
      const lowest = Math.max(step.y, ref);
      return `${top}<rect x="${step.x}" y="${lowest}" width="${step.w}" height="${14 - lowest}" style="fill:${colors.fill.below};opacity:0.4"></rect>`;
    })
    .join("");
  const stroke = (step) =>
    style.line === "level"
      ? colors.line[step.level]
      : style.line === "single"
        ? colors.line.single
        : above(step)
          ? colors.line.above
          : colors.line.below;
  const path = steps
    .map((step, i) => {
      const from = i ? `M${step.x},${steps[i - 1].y}V${step.y}` : `M${step.x},${step.y}`;
      return `<path d="${from}H${step.x + step.w}" style="stroke:${stroke(step)}"></path>`;
    })
    .join("");
  const reference = style.reference
    ? `<line class="icon-reference" x1="0" x2="22" y1="${ref}" y2="${ref}"></line>`
    : "";
  return `<svg viewBox="0 0 22 14" aria-hidden="true">${area}${reference}<g class="icon-line">${path}</g></svg>`;
}

// A short fingerprint of a text (a card's config), for keys in browser storage
export function hashText(text) {
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 33 + text.charCodeAt(i)) | 0;
  return (hash >>> 0).toString(36);
}

// The start of the local hour (or quarter hour) a moment falls in, in the home's time zone
export function localFloor(time, size, zone) {
  const local = time + zoneOffset(time, zone);
  return time - (((local % size) + size) % size);
}

/**
 * The price axis of a plot `span` pixels high: the prices fill it, with just the room their marks
 * need (`headroom` pixels above the highest price for its number, `footroom` below the lowest).
 * The range is not widened to whole steps, which would leave up to a step empty; the lines go at
 * the multiples of a step of 1, 2, 2.5 or 5 times a power of ten that fall inside, about `count`
 * of them and at least two. Negative prices are just lower values: zero is a line like any other
 * (drawn stronger where the prices cross it)
 */
function fitScale(min, max, span, headroom, footroom, count, decimals) {
  const flat = max === min;
  // All prices equal: the line in the middle, with a range around it
  const spread = flat ? Math.abs(max) * 0.2 || 1 : max - min;
  const usable = Math.max(span - headroom - footroom, span * 0.5, 1);
  const perPixel = spread / usable;
  const high = flat ? max + spread / 2 : max + headroom * perPixel;
  const low = flat ? min - spread / 2 : min - footroom * perPixel;
  const steps = (magnitude) => [1, 2, 2.5, 5].map((m) => m * magnitude);
  const raw = (high - low) / Math.max(count, 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  // With a fixed number of decimals only steps those can show (one decimal: 0.1, 0.2, 0.5, not
  // 0.25, whose lines would round to the same numbers)
  const all = [...steps(magnitude / 100), ...steps(magnitude / 10), ...steps(magnitude), ...steps(magnitude * 10)];
  const shown = (step) =>
    decimals === undefined || Math.abs(step * 10 ** decimals - Math.round(step * 10 ** decimals)) < 1e-9;
  const candidates = all.filter(shown).length ? all.filter(shown) : all;
  const ticksOf = (step) => {
    const ticks = [];
    for (let v = Math.ceil(low / step) * step; v <= high + step / 1000; v += step) ticks.push(Number(v.toFixed(10)));
    return ticks;
  };
  // The smallest step not denser than asked, finer again where fewer than two lines fall inside
  let index = candidates.findIndex((s) => s >= raw * 0.999);
  while (index > 0 && ticksOf(candidates[index]).length < 2) index -= 1;
  const step = candidates[index];
  return { low, high, step, ticks: ticksOf(step) };
}

// What a day's low or high takes beside its dot on the price axis: the gap and the pill (8 + 16
// px), and a little air to the plot's edge
const EXTREME_ROOM = 28;

const CHART_STYLE = `
  ${BASE_STYLE}
  :host { display: block; height: 100%; }
  ha-card { padding: 12px 12px 10px; height: 100%; box-sizing: border-box; display: flex; flex-direction: column;
            container: chart / inline-size; transition: none; overflow: hidden; }
  .card-title { margin: 0 4px 2px; font-size: var(--ha-font-size-l, 16px); font-weight: var(--ha-font-weight-medium, 500);
                line-height: 24px; color: var(--primary-text-color); }
  /* What the cursor points at: always in the same place, out of the finger's way */
  .readout { flex: none; display: flex; align-items: flex-start; gap: 8px; padding: 0 4px; min-height: 52px; }
  .readout .main { flex: 1; min-width: 0; }
  /* "Now" as on the other cards: a pill in the color of now, its dot pulsing like a live broadcast */
  .day-pill { display: inline-flex; align-items: center; gap: 6px; height: 20px; padding: 0 8px; border-radius: 10px;
              font-size: 12px; font-weight: var(--ha-font-weight-bold, 600); color: var(--primary-text-color); vertical-align: middle;
              white-space: nowrap; background: color-mix(in srgb, var(--pill, var(--secondary-text-color)) 20%, transparent); }
  .day-pill.now { --pill: var(--now-color, var(--primary-color, #03a9f4)); }
  .day-pill b { font-weight: var(--ha-font-weight-bold, 600); font-variant-numeric: tabular-nums; }
  ${LIVE_DOT_STYLE}
  .live-dot { --live-dot-size: 7px; --live-dot-color: var(--now-color, var(--primary-color, #03a9f4)); }
  .when-line { height: 20px; font-size: 13px; line-height: 20px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden;
               text-overflow: ellipsis; }
  .value-line { display: flex; align-items: center; gap: 6px; height: 34px; white-space: nowrap; overflow: hidden; }
  /* The price's box as high as its digits (line height 1), so the line centers the digits
     themselves, the chips and the average's sign beside them; the unit on the price's baseline */
  .price { font-size: 28px; line-height: 1; font-weight: var(--ha-font-weight-bold, 600); font-variant-numeric: tabular-nums;
           letter-spacing: -0.01em; color: var(--primary-text-color); }
  .amount { display: inline-flex; align-items: baseline; gap: 6px; }
  .unit { font-size: 13px; color: var(--secondary-text-color); }
  .avg-mark { margin-right: -2px; font-size: 16px; line-height: 1; color: var(--secondary-text-color); }
  .pending { font-size: 18px; color: var(--primary-text-color); }
  /* The chips: small, tinted in their color, in a row that never wraps (the line keeps its
     height while the cursor moves); the last ones give way on narrow cards */
  .chips { display: flex; gap: 6px; margin-left: 6px; min-width: 0; overflow: hidden; }
  .chip { flex: none; display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 9px; border-radius: 12px;
          font-size: 13px; color: var(--primary-text-color); font-variant-numeric: tabular-nums;
          background: color-mix(in srgb, var(--chip, var(--secondary-text-color)) 16%, transparent); }
  .chip b { font-weight: var(--ha-font-weight-medium, 500); }
  .chip-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--chip); }
  .chip svg { width: 14px; height: 14px; fill: var(--chip, currentColor); }
  /* A day's low and high: the forecast card's arrows (drawn as lines), green and red */
  .chip .extreme-icon { width: 12px; height: 12px; fill: none; stroke-width: 1.6; stroke-linecap: round;
                        stroke-linejoin: round; }
  .chip.extreme-low .extreme-icon { stroke: var(--success-color, #43a047); }
  .chip.extreme-high .extreme-icon { stroke: var(--error-color, #db4437); }
  .chip.delta { color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  /* Text that keeps the width of its widest usual value (the gap's "↑ 100 %") */
  .steady { display: inline-grid; justify-items: end; }
  .steady > * { grid-area: 1 / 1; }
  .steady > .room { visibility: hidden; }
  .steady.start { justify-items: start; }
  .steady.center { justify-items: center; }
  .when-line .steady, .dial-day .steady { font-variant-numeric: tabular-nums; }
  /* Price and unit in the top line: laid out as they were on the line itself */
  .value-line .steady { align-self: stretch; }
  .value-line .steady > span { display: flex; align-items: center; gap: 6px; }
  .chip.plain { background: none; padding: 0 2px; color: var(--secondary-text-color); }
  /* The ring: on the left with the day, time and chips beside it; centered with them below it
     where the card has a lot of height. Its size from the card's room (see _dialLayout) */
  .readout.has-dial { position: relative; min-height: 0; align-items: center; }
  .readout.has-dial .main { flex: 1; display: flex; align-items: center; gap: 14px; min-width: 0; }
  .readout.has-dial.is-dial-centered { justify-content: center; }
  .readout.has-dial.is-dial-centered .main { flex: none; flex-direction: column; gap: 4px; max-width: 100%; }
  .readout.has-dial.is-dial-centered .to-now, .readout.has-dial.is-dial-centered .head-action { position: absolute; top: 0; }
  .readout.has-dial.is-dial-centered .to-now { right: 0; }
  .readout.has-dial.is-dial-centered .head-action { left: 0; }
  .readout.has-dial.is-dial-centered .dial-side { flex-direction: row; align-items: center; max-width: 100%; }
  .readout.has-dial .to-now, .readout.has-dial .head-action { align-self: flex-start; }
  .dial { position: relative; flex: none; width: var(--dial-size, 100px); height: var(--dial-size, 100px); }
  .dial svg { position: absolute; inset: 0; width: 100%; height: 100%; }
  .dial-track { fill: none; stroke: rgba(127, 127, 127, 0.18); stroke-width: 5; }
  .dial.small .dial-track, .dial.small .dial-arc { stroke-width: 6.5; }
  .dial-arc { fill: none; stroke-width: 5; stroke-linecap: round; }
  /* The line above the curve changes over softly: the ring's arc and the colors ease, what's new
     fades in (numbers count over, see _tween) */
  @media (prefers-reduced-motion: no-preference) {
    .dial-arc { transition: stroke-dasharray 0.18s ease-out, stroke 0.18s ease-out; }
    .readout .chip, .readout .day-pill { transition: background-color 0.18s ease-out, color 0.18s ease-out; }
    .readout .chip-dot, .readout .chip svg { transition: background-color 0.18s ease-out, fill 0.18s ease-out; }
    .readout .chip, .readout .day-pill { animation: readout-in 0.18s ease-out; }
    @keyframes readout-in { from { opacity: 0; } }
  }
  /* In the ring, centered as a group: the price (its box as high as its digits), the unit and, in
     a large ring, the time span below it; sizes and gaps all in proportion to the ring, so it
     looks the same at every size */
  .dial-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
                 gap: calc(var(--dial-size, 100px) * 0.045); }
  /* The price centered in the ring, the average's sign hung before it (not counted in) */
  .dial-value { position: relative; display: flex; align-items: center; white-space: nowrap; }
  .dial .price { font-size: calc(var(--dial-size, 100px) * 0.22); }
  .dial.small .price { font-size: calc(var(--dial-size, 100px) * 0.25); }
  .dial .avg-mark { position: absolute; right: 100%; margin-right: calc(var(--dial-size, 100px) * 0.025);
                   font-size: calc(var(--dial-size, 100px) * 0.11); }
  .dial-unit { font-size: clamp(10px, calc(var(--dial-size, 100px) * 0.1), 13px); line-height: 1; color: var(--secondary-text-color); }
  .dial.small .dial-unit { font-size: calc(var(--dial-size, 100px) * 0.15); }
  .dial-range { font-size: clamp(11px, calc(var(--dial-size, 100px) * 0.09), 13px); line-height: 1; color: var(--secondary-text-color);
                font-variant-numeric: tabular-nums; }
  .dial-side { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  .dial-day { font-size: 14px; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dial-side .chips { margin-left: 0; }
  .chip.level.compact { padding: 0 8px; }
  .chip.level.compact .chip-text { display: none; }
  .to-now { flex: none; display: inline-flex; align-items: center; gap: 4px; height: 30px; margin-top: 2px; padding: 0 12px 0 8px;
            border: 0; border-radius: 15px; font: inherit; font-size: 13px; cursor: pointer; color: var(--primary-text-color);
            background: color-mix(in srgb, var(--now-color, var(--primary-color, #03a9f4)) 16%, transparent); }
  .to-now svg { width: 16px; height: 16px; fill: currentColor; }
  .overlay .to-now { height: 26px; margin-top: 0; padding: 0 10px 0 6px; border-radius: 13px; font-size: 12px; }
  .overlay .to-now svg { width: 14px; height: 14px; }
  /* The head running the card's action: a hint on hover, as HA's own cards */
  .readout.is-interactive { cursor: pointer; border-radius: 8px; }
  @media (hover: hover) { .readout.is-interactive:hover { background: rgba(127, 127, 127, 0.06); } }
  .readout.is-interactive:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  ${ACTION_BUTTON_STYLE}
  .action-button { padding: 0 10px; }
  .head-action { flex: none; margin-top: 2px; }
  .card-footer { flex: none; display: flex; justify-content: flex-end; margin-top: 6px; }
  /* The curve: as high as the card leaves (rows in a sections view), else from its width */
  .chart { position: relative; flex: 1 1 clamp(150px, 46cqw, 320px); min-height: 96px; margin: 4px 0 2px; }
  .plot { position: absolute; inset: 0; touch-action: pan-y; user-select: none; -webkit-user-select: none; -webkit-tap-highlight-color: transparent;
          cursor: crosshair; border-radius: 8px; }
  .plot:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  .plot svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
  .plot svg text { font-family: inherit; font-size: 11px; fill: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  /* The price lines: thin, in the theme's divider color; or as strong as set, a share of the text
     color, which is dark on light themes and light on dark ones, so one value suits both */
  .plot .grid { stroke: var(--grid-color, var(--divider-color, rgba(127, 127, 127, 0.2))); stroke-width: var(--grid-width, 0.75px); }
  /* The line where a day begins: as strong as the price lines unless set, twice as thick */
  .plot .divider { stroke: var(--day-line-color, var(--grid-color, var(--divider-color, rgba(127, 127, 127, 0.3))));
                   stroke-width: var(--day-line-width, 1.5px); }
  /* Midnight on the time axis: its hour in the text's color and bold, its tick longer */
  .plot text.midnight { fill: var(--primary-text-color); font-weight: var(--ha-font-weight-bold, 600); }
  .plot .zero { stroke: var(--secondary-text-color); stroke-width: 1; opacity: 0.5; }
  .plot .reference { stroke: var(--secondary-text-color); stroke-width: 1.25; stroke-dasharray: 4 4; opacity: 0.7; fill: none; }
  .plot .line { fill: none; stroke-width: 2.25; stroke-linejoin: round; stroke-linecap: round; }
  .plot .past { opacity: 0.4; }
  .plot .period-track { fill: rgba(127, 127, 127, 0.2); }
  .plot .reference-label rect { fill: var(--ha-card-background, var(--card-background-color, #fff)); opacity: 0.85; }
  .plot .reference-label text { font-size: 11px; fill: var(--secondary-text-color); }
  .plot .reference-label { transition: transform 0.12s ease-out, opacity 0.12s; }
  .plot .reference-label.is-yielding { opacity: 0.12; }
  @media (prefers-reduced-motion: reduce) { .plot .reference-label { transition: none; } }
  .plot .now-line { stroke: var(--now-color, var(--primary-color, #03a9f4)); stroke-width: 1.5; opacity: 0.8; }
  /* At 15 min the line of now shows only while prices are read (at rest the cursor is on now) */
  .plot .now-line.while-reading { transition: opacity 0.18s ease-out; }
  .plot:not(.is-reading) .now-line.while-reading { opacity: 0; }
  /* In the numbers' color, not fainter: it's text to read, and lighter grey than this falls below
     a readable contrast on light themes */
  .plot text.axis-title { font-size: 11px; fill: var(--secondary-text-color); letter-spacing: 0.02em; }
  .plot text.day { font-size: 12px; fill: var(--primary-text-color); opacity: 0.75; }
  .plot text.day.inside { font-size: 11px; paint-order: stroke; stroke: var(--ha-card-background, var(--card-background-color, #fff));
                          stroke-width: 3px; stroke-linejoin: round; }
  /* A day's low and high: a pill like the averages' numbers, its arrow in green and red as on
     the forecast card */
  .plot .extreme-label rect { fill: var(--ha-card-background, var(--card-background-color, #fff)); opacity: 0.85; }
  .plot .extreme-label text { font-size: 11px; font-weight: var(--ha-font-weight-medium, 500); fill: var(--primary-text-color); }
  .plot .extreme-label path { fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  .plot .extreme-label.low path { stroke: var(--success-color, #43a047); }
  .plot .extreme-label.high path { stroke: var(--error-color, #db4437); }
  .plot .extreme-dot { stroke: var(--ha-card-background, var(--card-background-color, #fff)); stroke-width: 1.5; }
  /* The cursor: the slot it points at, a line and a dot on the curve, its time above */
  .plot .cursor-band { fill: rgba(var(--rgb-primary-text-color, 33, 33, 33), 0.07); }
  .plot .cursor-line { stroke: var(--secondary-text-color); stroke-width: 1; stroke-dasharray: 2 3; }
  .plot .cursor-halo { opacity: 0.22; transition: r 0.12s ease-out; }
  .plot.is-dragging .cursor-halo { r: 16px; }
  .plot .cursor-halo.live { transform-box: fill-box; transform-origin: center; animation: halo-breathe 2.4s ease-in-out infinite; }
  @keyframes halo-breathe {
    0%, 100% { transform: scale(1); opacity: 0.22; }
    50% { transform: scale(1.4); opacity: 0.1; }
  }
  .plot .cursor-dot { stroke: var(--ha-card-background, var(--card-background-color, #fff)); stroke-width: 2.5; }
  .plot .cursor-pill { fill: var(--primary-text-color); }
  .plot text.cursor-price { fill: var(--ha-card-background, var(--card-background-color, #fff)); font-size: 14px;
                            font-weight: var(--ha-font-weight-bold, 600); }
  .plot .tag-badge circle { stroke: var(--ha-card-background, var(--card-background-color, #fff)); stroke-width: 2; }
  .plot .tag-badge path { fill: #fff; }
  .plot .tag-badge.partial circle { fill: var(--ha-card-background, var(--card-background-color, #fff)); }
  .plot .tag-badge.partial .track { fill: none; stroke-width: 2.5; opacity: 0.25; }
  .plot .tag-badge.partial .part { fill: none; stroke-width: 2.5; }
  .plot tspan.cursor-avg { font-size: 11px; font-weight: var(--ha-font-weight-normal, 400); opacity: 0.8; }
  .plot tspan.cursor-day { opacity: 0.8; }
  .plot tspan.cursor-unit { font-size: 10.5px; font-weight: var(--ha-font-weight-normal, 400); opacity: 0.8; }
  .plot .cursor-swatch { stroke: var(--ha-card-background, var(--card-background-color, #fff)); stroke-width: 1.5; }
  @media (prefers-reduced-motion: no-preference) {
    .plot .cursor-swatch.changed { animation: swatch-over 0.18s ease-out; }
    @keyframes swatch-over { from { fill: var(--from); } }
    .plot .tag-badge.is-appearing { animation: readout-in 0.18s ease-out; }
  }
  .plot text.cursor-time { fill: var(--ha-card-background, var(--card-background-color, #fff)); font-size: 10.5px;
                           font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; }
  .plot .base { animation: chart-in 0.18s ease-out; }
  @keyframes chart-in { from { opacity: 0; } to { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) { .plot .base { animation: none; } .plot .cursor-halo { transition: none; } .plot .cursor-halo.live { animation: none; } }
  .placeholder { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px;
                 text-align: center; font-size: 14px; line-height: 20px; color: var(--secondary-text-color); }
  /* The resolution switch, small in the top right corner of the chart (in the row of the day
     names, which make room for it); its buttons reach a little beyond it for a finger */
  .overlay { position: absolute; top: 0; right: 0; display: flex; gap: 6px; transition: opacity 0.12s; }
  .overlay.is-yielding { opacity: 0; pointer-events: none; }
  .resolution, .styles { display: flex; padding: 2px; border-radius: 13px; background: rgba(127, 127, 127, 0.15); }
  .styles button { position: relative; display: flex; align-items: center; height: 22px; padding: 0 6px; border: 0;
                   border-radius: 11px; background: none; cursor: pointer; opacity: 0.6; transition: background-color 0.15s, opacity 0.15s; }
  .styles button::after { content: ""; position: absolute; inset: -9px -1px; }
  .styles button svg { width: 22px; height: 14px; overflow: hidden; border-radius: 2px; }
  ${STYLE_ICON_STYLE}
  .styles button[aria-pressed="true"] { opacity: 1; background: var(--ha-card-background, var(--card-background-color, #fff));
                                        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18); }
  .styles button:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  .style-pick { position: relative; display: flex; align-items: center; gap: 1px; height: 22px; padding: 0 2px 0 6px;
                border: 0; border-radius: 11px; cursor: pointer; background: var(--ha-card-background, var(--card-background-color, #fff));
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18); }
  .style-pick::after { content: ""; position: absolute; inset: -9px -2px; }
  .style-pick > svg:first-child { width: 22px; height: 14px; overflow: hidden; border-radius: 2px; }
  .style-pick .chevron { width: 16px; height: 16px; fill: var(--secondary-text-color); }
  .style-pick:focus-visible { outline: var(--focus-ring); outline-offset: 1px; }
  /* The menu of styles: in the top layer, below its button */
  .style-menu { position: fixed; inset: auto; margin: 0; padding: 4px; min-width: 180px; max-width: calc(100vw - 16px);
                border: 0; border-radius: 12px; color: var(--primary-text-color);
                background: var(--ha-card-background, var(--card-background-color, #fff));
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.24); }
  .style-menu:not(:popover-open):not(.is-open) { display: none; }
  .style-menu button { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 40px; padding: 0 12px 0 8px; border: 0;
                       border-radius: 8px; background: none; font: inherit; font-size: 14px; color: inherit; cursor: pointer; text-align: left; }
  .style-menu button:hover, .style-menu button:focus-visible { background: rgba(127, 127, 127, 0.12); outline: none; }
  .style-menu button[aria-checked="true"] { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.14); font-weight: var(--ha-font-weight-medium, 500); }
  .style-menu button svg { width: 33px; height: 21px; flex: none; border-radius: 3px; overflow: hidden; }
  @media (any-pointer: coarse) { .style-menu button { min-height: 48px; font-size: 15px; } }
  .resolution button { position: relative; height: 22px; padding: 0 9px; border: 0; border-radius: 11px; background: none;
                       font: inherit; font-size: 12px; line-height: 22px; color: var(--secondary-text-color); cursor: pointer;
                       white-space: nowrap; transition: background-color 0.15s, color 0.15s; }
  .resolution button::after { content: ""; position: absolute; inset: -9px -2px; }
  .resolution button[aria-pressed="true"] { background: var(--ha-card-background, var(--card-background-color, #fff));
                                           color: var(--primary-text-color); font-weight: var(--ha-font-weight-medium, 500);
                                           box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18); }
  .resolution button:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  /* The views, like a segmented control */
  .controls { flex: none; display: flex; gap: 8px; align-items: center; margin-top: 6px; }
  .price-source { flex: none; display: inline-flex; align-items: center; gap: 4px; margin-left: auto; min-height: 32px;
    font-size: 13px; color: var(--secondary-text-color); cursor: pointer; white-space: nowrap; }
  .price-source input { margin: 0; width: 16px; height: 16px; accent-color: var(--primary-color); cursor: pointer; }
  .price-source input:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  .segments { display: flex; padding: 2px; border-radius: 18px; background: rgba(127, 127, 127, 0.15); min-width: 0; }
  /* The views: spread over the width, or scrolled sideways where their names don't fit (never cut
     off); a soft edge shows there's more */
  .segments.views { flex: 1; overflow-x: auto; scrollbar-width: none; overscroll-behavior-x: contain; }
  .segments.views::-webkit-scrollbar { display: none; }
  .segments.views button { flex: 1 0 auto; overflow: visible; text-overflow: clip; }
  .segments.views.has-more-right { mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent); }
  .segments.views.has-more-left { mask-image: linear-gradient(to left, #000 calc(100% - 28px), transparent); }
  .segments.views.has-more-left.has-more-right {
    mask-image: linear-gradient(to right, transparent, #000 28px, #000 calc(100% - 28px), transparent); }
  .segments button { flex: 1 1 0; min-width: 0; min-height: 32px; padding: 0 8px; border: 0; border-radius: 16px; background: none;
                     font: inherit; font-size: 13px; color: var(--secondary-text-color); cursor: pointer; white-space: nowrap;
                     overflow: hidden; text-overflow: ellipsis; transition: background-color 0.15s, color 0.15s; }
  .segments button[aria-selected="true"], .segments button[aria-pressed="true"] {
    background: var(--ha-card-background, var(--card-background-color, #fff)); color: var(--primary-text-color);
    font-weight: var(--ha-font-weight-medium, 500); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18); }
  .segments button:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  .empty { padding: 16px; color: var(--secondary-text-color); }
  /* Fingers: 44 px to hit, the controls looking as they do (their hit areas reach beyond them) */
  @media (any-pointer: coarse) {
    .resolution button::after, .styles button::after, .style-pick::after { inset: -11px -2px; }
    .styles button { padding: 0 10px; }
    .to-now { position: relative; }
    .to-now::after { content: ""; position: absolute; inset: -7px -2px; }
    .overlay .to-now::after { inset: -9px -2px; }
    /* (The views scroll sideways, which cuts off any hit area beyond them: they grow instead) */
    .segments button { min-height: 40px; }
    .price-source { min-height: 44px; }
    .price-source input { width: 20px; height: 20px; }
  }
  @container chart (max-width: 360px) {
    .price { font-size: 24px; }
    .chip { padding: 0 7px; font-size: 12px; }
    .segments button { font-size: 12px; padding: 0 10px; }
    .price-source { font-size: 12px; }
  }
`;

// A view's name, as on its tab
export function chartViewName(t, view) {
  return t[view] || t.chart[view];
}

/**
 * The views a card shows: those listed (else the default ones), tomorrow before its prices are
 * in as set: with a note on when they come, not at all, or with yesterday standing in (unless
 * yesterday has a tab of its own), in time's order: before today, else where tomorrow was. With
 * `all`, everything the card can show (tomorrow and its stand-in: the editor's panels)
 */
export function chartViews(config, { tomorrowKnown = false, all = false }) {
  const listed = Array.isArray(config.views) && config.views.length ? config.views : CHART_DEFAULT_VIEWS;
  const pending = config.tomorrow_pending;
  const waiting = listed.includes("tomorrow") && !tomorrowKnown && Boolean(pending) && pending !== "placeholder";
  const views = waiting && !all ? listed.filter((view) => view !== "tomorrow") : [...listed];
  if (waiting && pending === "yesterday" && !listed.includes("yesterday")) {
    views.splice(views.includes("today") ? views.indexOf("today") : listed.indexOf("tomorrow"), 0, "yesterday");
  }
  return views;
}

// A style's name: "Line price level · area below/above ⌀ of the view · ⌀ line"
export function chartStyleName(e, style) {
  const name = fill(e.style_name, { line: e[`style_line_${style.line}`], fill: e[`style_fill_${style.fill}`] });
  return style.reference ? `${name}${e.style_name_reference}` : name;
}

// What a style is called in the chart: its own name, else "Style 2" by its place
export function chartStyleLabel(e, style, index) {
  const own = typeof style.name === "string" ? style.name.trim() : "";
  return own ? escapeHtml(own) : fill(e.style_number, { n: index + 1 });
}

export class TibberPricesChartCard extends TibberPricesCardBase {
  // The forecast card, from a tap (tap_opens)
  static windowCards = [{ key: "forecast", when: (config) => config.tap_opens === "forecast" }];

  static assertConfig(config) {
    validateChartConfig(config);
    validateWindowCards(config);
  }

  setConfig(config) {
    TibberPricesCardBase.requireHome(config);
    TibberPricesChartCard.assertConfig(config);
    this._config = { ...CHART_DEFAULTS, ...config };
    // The view and style picked last, remembered per browser and card (by its config): each chart
    // card on a dashboard switches on its own
    const key = `tibber-prices-chart:${hashText(JSON.stringify(config))}`;
    this._viewKey = `${key}:view`;
    this._styleKey = `${key}:style`;
    this._view = storedValue(this._viewKey);
    this._cursor = undefined;
    // A new config sets the price shown again (the tick box's pick is kept with the card only)
    this._pickedSource = undefined;
    this._viewCache = new Map();
    this._configApplied();
  }

  connectedCallback() {
    // The line of now moves on, and the outlook with it, also while the prices stay the same
    clearInterval(this._ticker);
    this._ticker = setInterval(() => this._data && this._draw(), 60000);
    if (this._config && this._hass) this._scheduleRender();
  }

  disconnectedCallback() {
    clearInterval(this._ticker);
    clearTimeout(this._returnTimer);
    if (this._resizeObserver) this._resizeObserver.disconnect();
    this._observed = false;
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: "full", rows: 6, min_columns: 6, min_rows: 4 };
  }

  // How a view's resolution is set: its own setting, else the card's
  _resolutionMode(view = this._view) {
    return this._viewOptions(view).resolution;
  }

  _styleIcon(style) {
    return chartStyleIcon(style, this._colors());
  }

  // The styles a view offers (the first is its default)
  _styles(view = this._view) {
    return this._viewOptions(view).styles;
  }

  // Whether the chart shows a switch between them
  _styleSwitch(view = this._view) {
    return this._viewOptions(view).style_switch && this._styles(view).length > 1;
  }

  // The style a view is painted in: the one picked last (with a switch), else its first
  _style(view = this._view) {
    return this._styles(view)[this._styleIndex(view)];
  }

  // Its place among the view's styles (compared by place: the styles are built anew each time)
  _styleIndex(view = this._view) {
    const picked = this._styleSwitch(view) && storedValue(`${this._styleKey}:${view}`);
    return Math.max(
      0,
      this._styles(view).findIndex((style) => chartStyleId(style) === picked)
    );
  }

  // The forecast card in a window counts as an action
  _hasAction() {
    return this._opensForecast() || super._hasAction();
  }

  _actionText(t) {
    return this._opensForecast() && !this._config.action_button_text ? t.action_button.open : super._actionText(t);
  }

  // Whether a tap opens the forecast card: set so, and no tap action of its own
  _opensForecast() {
    return this._opens("forecast") && !this._configured("tap");
  }

  // A tap on the head or the card's button: the forecast card in a window, or the tap action
  _tap(opener) {
    if (this._opensForecast()) this._openInWindow("forecast", opener);
    else this._action("tap");
  }

  /**
   * Tap, hold and double tap on the card's head (price and time, the title) run its actions, as
   * on the other cards; the curve is the cursor's, the switches and tabs are their own. With its
   * own button, only that button runs the action
   */
  _bindCardActions(card) {
    card.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-card-action]");
      if (button) this._tap(button);
    });
    const head = (event) =>
      this._config.action_button || event.target.closest("button, .chart, .controls, .style-menu")
        ? null
        : event.target.closest(".readout, .card-title");
    this._bindGestures(card, head, (target) => this._tap(target));
    card.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && event.target.classList.contains("readout")) {
        event.preventDefault();
        this._tap(event.target);
      }
    });
  }

  // The head as a button where it runs an action; the card's own button where one is set
  _updateActions() {
    const root = this.shadowRoot;
    const t = this._t;
    const readout = this._els.readout;
    const interactive = !this._config.action_button && this._hasAction();
    readout.classList.toggle("is-interactive", interactive);
    if (interactive) {
      readout.setAttribute("role", "button");
      readout.setAttribute("tabindex", "0");
    } else {
      readout.removeAttribute("role");
      readout.removeAttribute("tabindex");
    }
    const footer = root.querySelector(".card-footer");
    const button = this._config.action_button
      ? `<button type="button" class="action-button" data-card-action>${escapeHtml(this._actionText(t))} ›</button>`
      : "";
    const top = this._config.action_button_position === "top" && this._config.header !== "none";
    footer.hidden = !button || top;
    footer.innerHTML = top ? "" : button;
    root.querySelector(".head-action").innerHTML = top ? button : "";
  }

  // A style picked with the switch or the menu (kept per view)
  _pickStyle(index) {
    const style = this._styles()[index];
    if (!style || index === this._styleIndex()) return;
    storeValue(`${this._styleKey}:${this._view}`, chartStyleId(style));
    this._render();
  }

  /**
   * The menu of styles under its button: a row each in their fixed order (the one shown checked),
   * as large as a finger needs. In the top layer (popover), so the card doesn't cut it off; it
   * closes on a pick, a tap outside or Escape, and the arrow keys move through it
   */
  _openStyleMenu(button) {
    const menu = this.shadowRoot.querySelector(".style-menu");
    const e = languageStrings(EDITOR_STRINGS);
    const current = this._styleIndex();
    menu.setAttribute("aria-label", this._t.chart.styles);
    menu.innerHTML = this._styles()
      .map(
        (style, i) =>
          `<button type="button" role="menuitemradio" data-style="${i}" aria-checked="${i === current}" title="${chartStyleName(e, style)}">${this._styleIcon(style)}<span>${chartStyleLabel(e, style, i)}</span></button>`
      )
      .join("");
    this._styleMenuButton = button;
    if (menu.showPopover) menu.showPopover();
    else menu.classList.add("is-open");
    button.setAttribute("aria-expanded", "true");
    // Below the button, its right edges aligned, kept within the window
    const box = button.getBoundingClientRect();
    const width = menu.offsetWidth;
    const left = Math.max(8, Math.min(box.right - width, window.innerWidth - width - 8));
    const below = box.bottom + 6 + menu.offsetHeight <= window.innerHeight;
    menu.style.left = `${left}px`;
    menu.style.top = `${below ? box.bottom + 6 : Math.max(8, box.top - 6 - menu.offsetHeight)}px`;
    const checked = menu.querySelector('[aria-checked="true"]') || menu.querySelector("button");
    if (checked) checked.focus();
  }

  _closeStyleMenu() {
    const menu = this.shadowRoot.querySelector(".style-menu");
    if (menu.hidePopover && menu.matches(":popover-open")) menu.hidePopover();
    menu.classList.remove("is-open");
  }

  _bindStyleMenu(menu) {
    menu.addEventListener("click", (ev) => {
      const item = ev.target.closest("button[data-style]");
      if (!item) return;
      this._closeStyleMenu();
      this._pickStyle(Number(item.dataset.style));
    });
    menu.addEventListener("keydown", (ev) => {
      const items = [...menu.querySelectorAll("button")];
      const at = items.indexOf(this.shadowRoot.activeElement);
      const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: items.length - 1 }[ev.key];
      if (to !== undefined) {
        ev.preventDefault();
        items[(to + items.length) % items.length].focus();
      } else if (ev.key === "Escape" || ev.key === "Tab") {
        this._closeStyleMenu();
      }
    });
    // Closed (also by a tap outside or Escape): the focus back on its button
    menu.addEventListener("toggle", (ev) => {
      if (ev.newState !== "closed" || !this._styleMenuButton) return;
      this._styleMenuButton.setAttribute("aria-expanded", "false");
      if (this.shadowRoot.activeElement === null || menu.contains(this.shadowRoot.activeElement)) {
        this._styleMenuButton.focus();
      }
    });
  }

  // What a view does where nothing is set (the solar card draws hours)
  static get viewDefaults() {
    return CHART_VIEW_DEFAULTS;
  }

  // A view's options (see chartViewOptions), built once per config
  _viewOptions(view = this._view) {
    if (!this._viewCache.has(view))
      this._viewCache.set(view, chartViewOptions(this._config, view, this.constructor.viewDefaults));
    return this._viewCache.get(view);
  }

  // What the view shown leaves out
  get _hide() {
    return this._viewOptions().hide;
  }

  /**
   * The resolution a view shows: a fixed one; else the one picked with the switch, in whichever
   * view (it holds across the views, so they don't jump between resolutions, until the page is
   * left or loaded again: kept with the card, not stored); else the one the view starts at
   */
  _resolution(view = this._view) {
    const mode = this._resolutionMode(view);
    if (mode === "quarter_hour" || mode === "hour") return mode;
    if (this._pickedResolution) return this._pickedResolution;
    return mode === "switch_hour" ? "hour" : "quarter_hour";
  }

  /**
   * The price shown: the one ticked in the card (with `price_source_switch`; kept with the card,
   * not stored, like the resolution picked), else the one set
   */
  _priceSource() {
    if (this._config.price_source_switch && this._pickedSource) return this._pickedSource;
    return super._priceSource();
  }

  _build() {
    this.attachShadow({ mode: "open" });
    trackKeyboard(this);
    this.shadowRoot.innerHTML = `<style>${CHART_STYLE}</style><ha-card>
      <div class="card-title" hidden></div>
      <div class="readout"><div class="main"></div>
        <span class="head-action"></span>
        <button type="button" class="to-now" hidden>${svgIcon(RESTORE_PATH)}<span></span></button>
      </div>
      <div class="chart"><div class="plot" tabindex="0" role="slider"></div><div class="overlay"><div class="styles" role="group" hidden></div><div class="resolution" role="group" hidden></div></div></div>
      <div class="controls"></div>
      <div class="card-footer" hidden></div>
    </ha-card><div class="style-menu" role="menu" popover></div>`;
    const root = this.shadowRoot;
    // The nodes that stay (the plot's content is drawn anew)
    this._els = {
      plot: root.querySelector(".plot"),
      main: root.querySelector(".readout .main"),
      readout: root.querySelector(".readout"),
      toNow: root.querySelector(".to-now"),
      overlay: root.querySelector(".overlay"),
    };
    const choose = (ev) => {
      const button = ev.target.closest("button");
      if (!button) return;
      if (button.dataset.view && button.dataset.view !== this._view) {
        this._view = button.dataset.view;
        storeValue(this._viewKey, this._view);
        this._cursor = undefined;
        this._render();
      } else if (button.dataset.styleMenu !== undefined) {
        this._openStyleMenu(button);
      } else if (button.dataset.style !== undefined) {
        this._pickStyle(Number(button.dataset.style));
      } else if (button.dataset.resolution && button.dataset.resolution !== this._resolution()) {
        this._pickedResolution = button.dataset.resolution;
        this._render();
      }
    };
    root.querySelector(".controls").addEventListener("click", choose);
    root.querySelector(".controls").addEventListener("change", (ev) => {
      if (!ev.target.matches("[data-price-source]")) return;
      this._pickedSource = ev.target.checked ? "energy" : "total";
      this._render();
    });
    this._els.overlay.addEventListener("click", choose);
    this._bindStyleMenu(root.querySelector(".style-menu"));
    this._bindCardActions(root.querySelector("ha-card"));
    this._els.toNow.addEventListener("click", () => this._backToNow());
    this._bindPlot(this._els.plot);
  }

  _observe() {
    if (this._observed) return;
    this._observed = true;
    if (!this._resizeObserver) {
      this._resizeObserver = new ResizeObserver(() => {
        if (this._drawPending) return;
        this._drawPending = true;
        requestAnimationFrame(() => {
          this._drawPending = false;
          if (this._data) this._draw();
          const tabs = this.shadowRoot.querySelector(".controls .views");
          if (tabs) this._showSelectedView(tabs);
        });
      });
    }
    this._resizeObserver.observe(this._els.plot);
    this._resizeObserver.observe(this.shadowRoot.querySelector(".controls"));
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this._build();
    this._observe();
    const t = stringsFor(this._hass);
    this._t = t;
    const root = this.shadowRoot;
    const title = root.querySelector(".card-title");
    title.hidden = !this._config.show_title;
    title.innerHTML = this._config.show_title ? cardTitle(this._config, t) : "";
    this._data = this._collect(t);
    const controls = root.querySelector(".controls");
    if (!this._data) {
      this._els.main.innerHTML = "";
      this._els.plot.innerHTML = `<div class="placeholder">${t.no_data}</div>`;
      controls.hidden = true;
      root.querySelector(".resolution").hidden = true;
      root.querySelector(".styles").hidden = true;
      return;
    }
    const views = chartViews(this._config, { tomorrowKnown: this._tomorrowShown() });
    this._views = views;
    if (!views.includes(this._view)) this._view = views[0];
    const resolution = this._resolution();
    const viewButtons =
      views.length > 1
        ? `<div class="segments views" role="tablist" aria-label="${t.chart.views}">${views
            .map(
              (view) =>
                `<button type="button" role="tab" data-view="${view}" aria-selected="${view === this._view}">${this._viewName(view)}</button>`
            )
            .join("")}</div>`
        : "";
    const switcher = root.querySelector(".resolution");
    switcher.hidden = !this._resolutionMode().startsWith("switch");
    switcher.setAttribute("aria-label", t.chart.resolution);
    switcher.innerHTML = switcher.hidden
      ? ""
      : ["quarter_hour", "hour"]
          .map(
            (value) =>
              `<button type="button" data-resolution="${value}" aria-pressed="${value === resolution}">${t.chart[value]}</button>`
          )
          .join("");
    // The styles to switch between: two side by side, each a small curve in its colors; more as
    // one button with the current one's curve, opening a menu of them in their fixed order (in
    // the top layer, so the card never cuts it off)
    const styles = root.querySelector(".styles");
    styles.hidden = !this._styleSwitch();
    styles.setAttribute("aria-label", t.chart.styles);
    const current = this._style();
    const e = languageStrings(EDITOR_STRINGS);
    const offered = this._styles();
    if (styles.hidden) {
      styles.innerHTML = "";
    } else if (offered.length > 2) {
      const index = this._styleIndex();
      const label = chartStyleLabel(e, offered[index], index);
      styles.innerHTML = `<button type="button" class="style-pick" data-style-menu aria-haspopup="menu" aria-expanded="false" title="${label}" aria-label="${t.chart.styles}: ${label}">${this._styleIcon(current)}<svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="${MENU_DOWN}"></path></svg></button>`;
    } else {
      styles.innerHTML = offered
        .map((style, i) => {
          const label = chartStyleLabel(e, style, i);
          return `<button type="button" data-style="${i}" aria-pressed="${i === this._styleIndex()}" title="${label}" aria-label="${label}">${this._styleIcon(style)}</button>`;
        })
        .join("");
    }
    const sourceSwitch = this._config.price_source_switch
      ? `<label class="price-source"><input type="checkbox" data-price-source${this._priceSource() === "energy" ? " checked" : ""}><span>${e.price_source_energy}</span></label>`
      : "";
    controls.innerHTML = viewButtons + sourceSwitch;
    controls.hidden = !viewButtons && !sourceSwitch;
    const tabs = controls.querySelector(".views");
    if (tabs) {
      tabs.addEventListener("scroll", () => this._markScrolled(tabs), { passive: true });
      this._showSelectedView(tabs);
    }
    // Without the line above the curve, the way back to now joins the switches in its corner
    const headless = this._config.header === "none";
    const readout = this._els.readout;
    readout.hidden = headless;
    readout.classList.toggle("has-dial", this._config.header === "dial");
    const toNow = this._els.toNow;
    if (headless) this._els.overlay.prepend(toNow);
    else readout.append(toNow);
    this._updateActions();
    root.querySelector(".to-now span").textContent = t.now;
    this._els.toNow.setAttribute("aria-label", t.chart.back_to_now);
    this._els.plot.setAttribute("aria-label", t.chart.label);
    this._draw();
  }

  // The picked view in sight in a scrolled row of views (without scrolling the page)
  _showSelectedView(tabs) {
    const selected = tabs.querySelector('[aria-selected="true"]');
    if (selected) {
      const start = selected.offsetLeft - tabs.offsetLeft;
      if (start < tabs.scrollLeft) tabs.scrollLeft = start - 8;
      else if (start + selected.offsetWidth > tabs.scrollLeft + tabs.clientWidth) {
        tabs.scrollLeft = start + selected.offsetWidth - tabs.clientWidth + 8;
      }
    }
    this._markScrolled(tabs);
  }

  // Soft edges where more views lie beyond
  _markScrolled(tabs) {
    const end = tabs.scrollWidth - tabs.clientWidth;
    tabs.classList.toggle("has-more-left", tabs.scrollLeft > 1);
    tabs.classList.toggle("has-more-right", tabs.scrollLeft < end - 1);
  }

  _viewName(view) {
    const t = this._t;
    return chartViewName(t, view);
  }

  // Everything a view is drawn from, once per update of the sensors
  _collect(t) {
    const entities = this._entities || homeEntities(this._hass, this._config);
    const stateObj = priceState(this._hass, entities.price && this._hass.states[entities.price], this._priceSource());
    const { factor, unit } = stateObj ? priceUnit(stateObj, this._config.price_unit) : {};
    const quarters = stateObj && quarterSeries(stateObj, factor);
    if (!quarters || !quarters.prices.length) return undefined;
    const { start, step, prices } = quarters;
    let last = prices.length - 1;
    while (last >= 0 && prices[last] === null) last -= 1;
    if (last < 0) return undefined;
    const units = stateObj.attributes.outlook_units;
    const calendar = homeCalendar(this._hass);
    const { zone, dateOf } = calendar;
    const now = Date.now();
    const today = dateOf(now);
    const [todayStart, tomorrowStart] = dayBounds(today, zone);
    const tomorrow = dateOf(tomorrowStart);
    const dayAfter = dayBounds(tomorrow, zone)[1];
    const yesterday = dateOf(todayStart - 1);
    const yesterdayStart = dayBounds(yesterday, zone)[0];
    const end = start + (last + 1) * step;
    const days = scalePrices(stateObj.attributes.outlook_days || [], factor);
    const averageKind = averageKindOf(this._config, days);
    const average = averageOf(t, averageKind);
    return {
      ...calendar,
      // The quarter hours (start, step, prices, totals, levels) on the data itself
      ...quarters,
      unit,
      // Prices in the subunit (ct, øre), not the base currency (€, kr)
      subunit: units ? unit === units.subunit : false,
      // The base currency's unit rate (€/kWh), for sums in the subunit that grow large
      baseUnit: units ? units.base : undefined,
      end,
      yesterday,
      today,
      tomorrow,
      todayStart,
      tomorrowStart,
      dayAfter,
      yesterdayStart,
      tomorrowKnown: end > tomorrowStart,
      averageKind,
      averageLabel: average.label,
      references: dayReferences(stateObj, factor, days, average.key),
      // Each day's lowest and highest price and when (the whole day's, from the sensor: a view
      // may show only part of a day), yesterday's too
      extremes: [
        ...scalePrices(stateObj.attributes.outlook_yesterday ? [stateObj.attributes.outlook_yesterday] : [], factor),
        ...days,
      ].flatMap((day) =>
        [
          ["low", day.price_min, day.price_min_at],
          ["high", day.price_max, day.price_max_at],
        ]
          .filter(([, price, at]) => typeof price === "number" && at)
          .map(([kind, price, at]) => ({ kind, price, at: Date.parse(at) }))
      ),
      periods: homePeriods(this._hass, entities, stateObj),
    };
  }

  // The stretch of time a view shows, [from, to)
  _span(view, resolution, now) {
    const d = this._data;
    if (view === "yesterday") return [d.yesterdayStart, d.todayStart];
    if (view === "today") return [d.todayStart, d.tomorrowStart];
    if (view === "tomorrow") return [d.tomorrowStart, d.dayAfter];
    // Both days: today and tomorrow, until tomorrow's prices are in yesterday and today
    if (view === "two_days")
      return this._tomorrowShown() ? [d.todayStart, d.dayAfter] : [d.yesterdayStart, d.tomorrowStart];
    // Outlook: from shortly before now to the last price known (at least the end of today)
    const size = resolution === "hour" ? HOUR_MS : d.step;
    const from = Math.max(localFloor(now, size, d.zone) - CHART_BEFORE_NOW_MS, d.start);
    return [from, Math.max(d.end, d.tomorrowStart)];
  }

  // A day's cheapest and dearest clock hour (their quarters' average), of the whole day
  _hourExtremes(date) {
    const d = this._data;
    const [start, end] = dayBounds(date, d.zone);
    const hours = quarterSlots(d, start, end, HOUR_MS, d.averageKind).filter((slot) => slot.price !== null);
    if (hours.length < 2) return [];
    return [
      { kind: "low", slot: hours.reduce((a, b) => (b.price < a.price ? b : a)) },
      { kind: "high", slot: hours.reduce((a, b) => (b.price > a.price ? b : a)) },
    ];
  }

  // The quarter hours of a stretch, or its clock hours (whole) with their quarters' average and level
  _slots(from, to, resolution) {
    const d = this._data;
    if (resolution !== "hour") return quarterSlots(d, from, to, d.step, d.averageKind);
    const start = localFloor(from, HOUR_MS, d.zone);
    return quarterSlots(d, start, localFloor(to - 1, HOUR_MS, d.zone) + HOUR_MS, HOUR_MS, d.averageKind);
  }

  _dayWord(date, time) {
    const d = this._data;
    const t = this._t;
    if (date === d.today) return t.today;
    if (date === d.tomorrow) return t.tomorrow;
    if (date === d.yesterday) return t.yesterday;
    return capitalize(d.weekday.format(new Date(time)));
  }

  // Hooks for cards that add curves to this one (the energy card): whether tomorrow has something
  // to show (its prices, else the added curves), whether a stretch without prices is drawn (for the
  // added curves), room kept at the right for a second axis, whether the price curve is filled
  // below, and the SVG of the added curves
  _tomorrowShown() {
    return this._data.tomorrowKnown;
  }

  _drawsWithoutPrices() {
    return false;
  }

  _rightRoom() {
    return 0;
  }

  _fills() {
    return true;
  }

  // More to draw in the plot's geometry: `under` goes below the price line (areas, which get their
  // gradients added to `defs`), `over` on top of it
  _extraParts() {
    return { under: [], over: [] };
  }

  // Room under the hours' labels for a row of its own (the solar card's sunrise and sunset)
  _footRoom() {
    return 0;
  }

  // The marks of the cursor on the added curves (SVG), and chips for the line above the curve
  _extraCursor() {
    return "";
  }

  _extraChips() {
    return [];
  }

  /** The curve of the view in the plot's size; the cursor goes on top (see _drawCursor) */
  _draw() {
    const root = this.shadowRoot;
    const plot = this._els.plot;
    const width = plot.clientWidth;
    const height = plot.clientHeight;
    if (!width || !height) return;
    this._dialMemo = undefined;
    const d = this._data;
    const t = this._t;
    const now = Date.now();
    const view = this._view;
    const resolution = this._resolution();
    if (view === "tomorrow" && !this._tomorrowShown()) {
      this._geo = undefined;
      plot.innerHTML = `<div class="placeholder">${t.tomorrow_pending}</div>`;
      plot.removeAttribute("aria-valuetext");
      if (this._config.header === "dial") {
        // (The tab says it's tomorrow)
        this._setReadout("", "–", [this._chip(t.detail.pending.title)]);
      } else {
        this._els.main.innerHTML = `<div class="when-line"></div><div class="value-line"><span class="pending">${t.detail.pending.title}</span></div>`;
      }
      this._els.toNow.hidden = true;
      return;
    }
    const [from, to] = this._span(view, resolution, now);
    const slots = this._slots(from, to, resolution);
    const known = slots.filter((slot) => slot.price !== null);
    // What's over is paled where the view reaches from the past to now; a view all past
    // (yesterday) stays as clear as the others
    const isPast = (end) => from <= now && now < to && end <= now;
    if (!known.length && !this._drawsWithoutPrices()) {
      this._geo = undefined;
      plot.innerHTML = `<div class="placeholder">${t.no_data}</div>`;
      return;
    }
    const values = known.map((slot) => slot.price);
    // The scale of the quarter hours in both resolutions (an hour's average lies within its
    // quarter hours'), over the stretch either shows (the outlook starts at the hour in hours):
    // switching between them leaves the axis where it is. A view without prices (only added
    // curves) takes the scale of all prices known
    const scaleFrom = Math.min(this._span(view, "quarter_hour", now)[0], this._span(view, "hour", now)[0]);
    let scaleValues = this._slots(scaleFrom, to, "quarter_hour")
      .filter((slot) => slot.price !== null)
      .map((slot) => slot.price);
    if (!scaleValues.length) scaleValues = d.prices.filter((price) => typeof price === "number");
    const min = Math.min(...scaleValues);
    const max = Math.max(...scaleValues);
    // The top row holds the day names, and the switches at its right end (taller then)
    const switchWidth = this._els.overlay.offsetWidth;
    const top = switchWidth ? 32 : 20;
    const rowMiddle = switchWidth ? 13 : 8.5;
    // Where the switch begins: the day names and the cursor's time keep clear of it
    const clearOf = width - switchWidth - 6;
    const periodsShown = !this._hide.includes("periods");
    // Axis titles, where asked for: "Time" under the hours, "Price" up the price axis
    const xTitle = Boolean(this._config.axis_title_x);
    const yTitle = Boolean(this._config.axis_title_y);
    const foot = this._footRoom();
    const bottomRoom = 18 + (periodsShown ? 6 : 0) + (xTitle ? 14 : 0) + foot;
    // Room for the high's pill above the curve and the low's below it (their dot, a gap and the
    // pill: EXTREME_ROOM), else a little below the lowest price: the area under the line (and the
    // shade of the slot pointed at, a pointer of its own) stays visible at the day's low too. A
    // line of the axis per 40 px or so
    const span = height - bottomRoom - top;
    // The axis's decimals: as set, else one in the base currency (€, kr) and none in its subunit
    // (ct, øre)
    const setting = this._config.axis_decimals;
    const decimals = setting === undefined || setting === "auto" ? (d.subunit ? 0 : 1) : Number(setting);
    const scale = fitScale(
      min,
      max,
      span,
      this._hide.includes("high") ? 8 : EXTREME_ROOM,
      Math.max(this._hide.includes("low") ? 18 : EXTREME_ROOM, span * 0.1),
      Math.max(2, Math.floor(span / 40)),
      decimals
    );
    const axisFormat = fixedPriceFormat(this._hass, decimals);
    // (A view without prices keeps the lines as a backdrop, without the numbers of a price axis)
    const tickLabels = scale.ticks.map((v) => (known.length ? axisFormat(v) : ""));
    // Up the price axis, left of its numbers and read from the bottom up: its title and unit,
    // "Price (ct/kWh)", or either alone (where asked for)
    const axisUnit = this._unitShown("axis");
    const yLabel = !known.length
      ? ""
      : yTitle && axisUnit
        ? `${t.chart.axis_price} (${axisUnit})`
        : yTitle
          ? t.chart.axis_price
          : axisUnit;
    // (Its line 11 px high around x = 8, then 8 px to the numbers, as between them and the plot)
    const gutter = yLabel ? 22 : 0;
    const left = gutter + Math.max(...tickLabels.map((label) => label.length)) * 6.5 + 8;
    // (A card with a second axis at the right keeps room for its numbers, see _rightRoom)
    const right = width - 2 - this._rightRoom();
    const bottom = height - bottomRoom;
    const plotWidth = right - left;
    const x = (time) => left + ((time - from) / (to - from)) * plotWidth;
    const y = (value) => top + ((scale.high - value) / (scale.high - scale.low)) * (bottom - top);
    const parts = [];
    // Gradients per level, from the top of the plot to its bottom (the per-day ones of the
    // average style join them below)
    const colors = this._colors();
    const card = root.querySelector("ha-card");
    card.style.setProperty("--now-color", colors.line.now);
    // The price lines and the line where a day begins: as thick as set, as strong as set (a share
    // of the text color, one value for light and dark themes; unset: the theme's divider color,
    // the day's line the price lines')
    const strength = (value) =>
      typeof value === "number" ? `color-mix(in srgb, var(--primary-text-color, #212121) ${value}%, transparent)` : "";
    const gridWidth =
      typeof this._config.grid_line_width === "number" ? this._config.grid_line_width : CHART_GRID_WIDTH;
    const dayWidth =
      typeof this._config.day_line_width === "number" ? this._config.day_line_width : CHART_DAY_LINE_WIDTH;
    card.style.setProperty("--grid-width", `${gridWidth}px`);
    card.style.setProperty("--day-line-width", `${dayWidth}px`);
    card.style.setProperty(
      "--day-shade",
      `color-mix(in srgb, var(--primary-text-color, #212121) ${(this._shadeStrength() * (this._dark() ? CHART_DAY_SHADE.dark : 1)).toFixed(1)}%, transparent)`
    );
    for (const [property, value] of [
      ["--grid-color", this._config.grid_line_strength],
      ["--day-line-color", this._config.day_line_strength],
    ]) {
      if (strength(value)) card.style.setProperty(property, strength(value));
      else card.style.removeProperty(property);
    }
    const defs = LEVEL_STEPS.map(
      (level) =>
        `<linearGradient id="fill-${level}" gradientUnits="userSpaceOnUse" x1="0" y1="${top}" x2="0" y2="${bottom}"><stop offset="0" style="stop-color:${colors.fill[level]};stop-opacity:0.34"></stop><stop offset="1" style="stop-color:${colors.fill[level]};stop-opacity:0.02"></stop></linearGradient>`
    );
    if (yLabel) {
      parts.push(
        `<text class="axis-title" transform="translate(8 ${(top + bottom) / 2}) rotate(-90)" text-anchor="middle" dominant-baseline="central">${yLabel}</text>`
      );
    }
    if (xTitle) {
      parts.push(
        `<text class="axis-title" x="${(left + right) / 2}" y="${height - 2}" text-anchor="middle">${t.chart.axis_time}</text>`
      );
    }
    // Price lines with their numbers in the gutter
    scale.ticks.forEach((value, i) => {
      const ty = y(value);
      parts.push(`<line class="grid" x1="${left}" x2="${right}" y1="${ty}" y2="${ty}"></line>`);
      parts.push(`<text x="${gutter}" y="${ty}" dominant-baseline="middle">${tickLabels[i]}</text>`);
    });
    if (scale.low < 0 && scale.high > 0) {
      parts.push(`<line class="zero" x1="${left}" x2="${right}" y1="${y(0)}" y2="${y(0)}"></line>`);
    }
    // The days in the view: a divider where one begins, its name above its part
    const dayParts = [];
    for (let start = from; start < to;) {
      const date = d.dateOf(start);
      const end = Math.min(dayBounds(date, d.zone)[1], to);
      dayParts.push({ date, start, end });
      start = end;
    }
    const multiDay = dayParts.length > 1;
    // The style painted, whether it colors below and above an average, and where that average is:
    // of the prices shown (one level across the view) or each day's
    const style = this._style(view);
    const shownBasis = style.fill === "average_shown";
    const shownAverage = values.length ? aggregate(values, d.averageKind) : undefined;
    const referenceShown = style.reference !== false;
    // A soft shade off each day's line, away from today (right into tomorrow, left into
    // yesterday): half an ellipse on the line, fading out every way (no edge anywhere), about two
    // to three hours wide (24 to 80 px). A share of the text color, a little more on dark themes:
    // a light tint on a dark card shows less than a dark one on light
    const shades = [];
    const shaded = multiDay && !this._hide.includes("day_shade") && this._shadeStrength() > 0;
    if (shaded) {
      const hoursWide =
        typeof this._config.day_shade_width === "number" ? this._config.day_shade_width : CHART_DAY_SHADE.width;
      const reach = Math.min(Math.max((plotWidth / ((to - from) / HOUR_MS)) * hoursWide, 24), hoursWide * 32);
      // Its middle 30 % down; upwards it fades out into the row of the day names, downwards
      // further, by the plot's bottom (two halves, alike along their seam)
      const cy = top + (bottom - top) * 0.3;
      const halves = [
        ["up", 0, cy, (bottom - top) * 0.5],
        ["down", cy, bottom, (bottom - top) * 0.7],
      ];
      // Eased: most of it near its middle, a long soft tail
      const stops = [
        [0, 1],
        [0.3, 0.7],
        [0.6, 0.3],
        [0.85, 0.08],
        [1, 0],
      ]
        .map(([o, a]) => `<stop offset="${o}" style="stop-color:var(--day-shade);stop-opacity:${a}"></stop>`)
        .join("");
      dayParts.slice(1).forEach((day, i) => {
        const lx = x(day.start);
        // At or before today's start the other day lies to the left, else to the right
        const sign = day.start > d.todayStart ? 1 : -1;
        const a = sign > 0 ? lx : Math.max(lx - reach, left);
        const b = sign > 0 ? Math.min(lx + reach, right) : lx;
        for (const [half, y1, y2, ry] of halves) {
          defs.push(
            `<radialGradient id="shade-${i}-${half}" gradientUnits="userSpaceOnUse" cx="${lx}" cy="${cy}" r="${reach}" gradientTransform="translate(${lx} ${cy}) scale(1 ${ry / reach}) translate(${-lx} ${-cy})">${stops}</radialGradient>`
          );
          shades.push(
            `<rect class="day-shade" x="${a}" y="${y1}" width="${b - a}" height="${y2 - y1}" fill="url(#shade-${i}-${half})"></rect>`
          );
        }
      });
    }
    dayParts.forEach((day, i) => {
      if (i > 0)
        parts.push(
          `<line class="divider" x1="${x(day.start)}" x2="${x(day.start)}" y1="${top - 4}" y2="${bottom}"></line>`
        );
      // Its name centered over its part ("Today · Friday"; a view of one day only its weekday, its
      // tab says the rest), moved left of the switch where they'd meet. Where that's too long for
      // its part: one of the words, then the short weekday; else none
      const date = new Date(day.start);
      const word =
        !CHART_SINGLE_DAY_VIEWS.includes(view) &&
        !this._hide.includes("day_word") &&
        this._dayWord(day.date, day.start);
      const weekday = !this._hide.includes("day_weekday") && capitalize(d.weekday.format(date));
      const words = [...new Set([word, weekday].filter(Boolean))];
      const names = [words.join(" · "), ...words, weekday && capitalize(d.weekdayShort.format(date))].filter(Boolean);
      const limit = switchWidth ? clearOf : right;
      const placed = names.some((name) => {
        const half = (name.length * 7) / 2;
        const center = Math.min((x(day.start) + x(day.end)) / 2, limit - half);
        if (center - half < x(day.start) + 4) return false;
        parts.push(
          `<text class="day" x="${center}" y="${rowMiddle}" dominant-baseline="central" text-anchor="middle">${name}</text>`
        );
        return true;
      });
      // The switches take the top row above it (a phone): just below, at the start of its day
      const inside = !placed && names.find((name) => x(day.start) + 6 + name.length * 6.5 <= x(day.end) - 4);
      if (inside) {
        parts.push(
          `<text class="day inside" x="${x(day.start) + 6}" y="${top + 9}" dominant-baseline="central">${inside}</text>`
        );
      }
      // The average the day's part is measured against (where the average style changes color)
      if (shownBasis) {
        day.reference = shownAverage;
      } else {
        const inDay = known.filter((slot) => slot.start >= day.start && slot.start < day.end).map((slot) => slot.price);
        const reference = d.references[day.date];
        day.reference =
          typeof reference === "number" ? reference : inDay.length ? aggregate(inDay, d.averageKind) : undefined;
      }
    });
    // The dashed line: over each day's part at that day's average (with its number on it, see
    // below), in the styles that show it
    const averageSpans = dayParts.map((day) => ({ start: day.start, end: day.end, reference: d.references[day.date] }));
    if (referenceShown) {
      for (const span of averageSpans) {
        if (typeof span.reference !== "number") continue;
        const ry = y(span.reference);
        parts.push(`<line class="reference" x1="${x(span.start)}" x2="${x(span.end)}" y1="${ry}" y2="${ry}"></line>`);
      }
    }
    // The average style per day: below the day's average a calm color fading to the bottom, a
    // quick change at the average, above it the signal color without further fading (so the
    // dearer part stands out as one); the line in the same colors, changing sharply
    const plotHeight = bottom - top;
    dayParts.forEach((day, i) => {
      if (day.reference === undefined) return;
      const at = Math.min(Math.max((y(day.reference) - top) / plotHeight, 0), 1);
      const blend = 3 / plotHeight;
      const stop = (offset, color, opacity) =>
        `<stop offset="${Math.min(Math.max(offset, 0), 1)}" style="stop-color:${color};stop-opacity:${opacity}"></stop>`;
      defs.push(
        `<linearGradient id="avg-fill-${i}" gradientUnits="userSpaceOnUse" x1="0" y1="${top}" x2="0" y2="${bottom}">${stop(0, colors.fill.above, 0.3)}${stop(at - blend, colors.fill.above, 0.3)}${stop(at + blend, colors.fill.below, 0.32)}${stop(1, colors.fill.below, 0.03)}</linearGradient>`,
        `<linearGradient id="avg-line-${i}" gradientUnits="userSpaceOnUse" x1="0" y1="${top}" x2="0" y2="${bottom}">${stop(0, colors.line.above, 1)}${stop(at, colors.line.above, 1)}${stop(at, colors.line.below, 1)}${stop(1, colors.line.below, 1)}</linearGradient>`
      );
    });
    const dayOf = (slot) => dayParts.findIndex((day) => slot.start >= day.start && slot.start < day.end);
    // The curve: the area to the bottom, then the step line over it, each in runs of one paint
    // (a price level, or a day in the average style), past runs paled
    const lineMode = style.line;
    const fillMode = style.fill === "level" ? "level" : "average";
    const level = (slot) => (LEVEL_COLORS[slot.level] ? slot.level : "normal");
    const runsOf = (paint) => {
      const runs = [];
      let run;
      slots.forEach((slot, i) => {
        if (slot.price === null) {
          run = undefined;
          return;
        }
        const past = isPast(slot.end);
        const key = `${paint(slot)}|${past}`;
        if (!run || run.key !== key) {
          const before = slots[i - 1];
          run = {
            key,
            paint: paint(slot),
            past,
            items: [],
            from: before && before.price !== null ? before.price : undefined,
          };
          runs.push(run);
        }
        run.items.push(slot);
      });
      return runs;
    };
    const paintOf = (mode) =>
      mode === "level" ? (slot) => `url(#fill-${level(slot)})` : (slot) => `url(#avg-fill-${dayOf(slot)})`;
    const strokeOf = {
      level: (slot) => colors.line[level(slot)],
      average: (slot) => `url(#avg-line-${dayOf(slot)})`,
      single: () => colors.line.single,
    }[lineMode];
    const pastClass = (r) => (r.past ? ' class="past"' : "");
    // Where prices cross zero the area starts at zero: negative prices hang below it, so they
    // read as below zero, not as a lower floor
    // Added curves (the solar card's): their areas lie below the price line, the rest above it
    const extra = this._extraParts({
      x,
      from,
      to,
      left,
      right,
      top,
      bottom,
      now,
      defs,
      footY: height - (xTitle ? 14 : 0) - foot / 2,
    });
    parts.push(...extra.under);
    const base = scale.low < 0 && scale.high > 0 ? y(0) : bottom;
    for (const r of this._fills() ? runsOf(paintOf(fillMode)) : []) {
      const first = r.items[0];
      let area = `M${x(first.start)},${base}V${y(first.price)}`;
      r.items.forEach((slot, i) => {
        area += `H${x(slot.end)}`;
        if (r.items[i + 1]) area += `V${y(r.items[i + 1].price)}`;
      });
      area += `V${base}H${x(first.start)}Z`;
      parts.push(`<path${pastClass(r)} d="${area}" style="fill:${r.paint}"></path>`);
    }
    // The step between two runs goes with the higher price: where the price falls, the run that
    // ends draws it down in its color; where it rises, the next run draws it up in its own
    const lineRuns = runsOf(strokeOf);
    lineRuns.forEach((r, n) => {
      const first = r.items[0];
      const last = r.items[r.items.length - 1];
      const next = lineRuns[n + 1];
      const rises = r.from !== undefined && first.price > r.from;
      let line = rises ? `M${x(first.start)},${y(r.from)}V${y(first.price)}` : `M${x(first.start)},${y(first.price)}`;
      r.items.forEach((slot, i) => {
        line += `H${x(slot.end)}`;
        if (r.items[i + 1]) line += `V${y(r.items[i + 1].price)}`;
      });
      if (next && next.from !== undefined && next.items[0].start === last.end && next.items[0].price < last.price) {
        line += `V${y(next.items[0].price)}`;
      }
      parts.push(`<path class="line${r.past ? " past" : ""}" d="${line}" style="stroke:${r.paint}"></path>`);
    });
    // The area's color at a slot (the ring above the curve takes it: it stays the level's or the
    // average's also with a line of one color)
    const fillColorAt = (slot) => {
      if (fillMode === "level") return colors.fill[level(slot)];
      const day = dayParts[dayOf(slot)];
      return day && day.reference !== undefined && slot.price > day.reference ? colors.fill.above : colors.fill.below;
    };
    // The color a point of the line has (its marks take it): its level's, the average style's
    // above or below the day's average, or the one color
    const colorAt = (slot) => {
      if (lineMode === "level") return colors.line[level(slot)];
      if (lineMode === "single") return colors.line.single;
      const day = dayParts[dayOf(slot)];
      return day && day.reference !== undefined && slot.price > day.reference ? colors.line.above : colors.line.below;
    };
    // Best and peak price periods: as in the forecast card, a grey track under each hour a
    // period falls in (joined where such hours follow each other), the periods colored on it
    if (periodsShown) {
      const touched = periodsTouching(d.periods, from, to);
      const tracks = [];
      for (const { a, b } of [...touched].sort((p, q) => p.a - q.a)) {
        const start = Math.max(localFloor(Math.max(a, from), HOUR_MS, d.zone), from);
        const end = Math.min(localFloor(Math.min(b, to) - 1, HOUR_MS, d.zone) + HOUR_MS, to);
        const last = tracks[tracks.length - 1];
        if (last && start <= last[1]) last[1] = Math.max(last[1], end);
        else tracks.push([start, end]);
      }
      for (const [start, end] of tracks) {
        parts.push(
          `<rect class="period-track" x="${x(start)}" y="${bottom + 3}" width="${x(end) - x(start)}" height="3" rx="1.5"></rect>`
        );
      }
      for (const p of touched) {
        const a = x(Math.max(p.a, from));
        const b = x(Math.min(p.b, to));
        parts.push(
          `<rect x="${a}" y="${bottom + 3}" width="${Math.max(b - a, 2)}" height="3" rx="1.5" fill="${MARK_COLORS[p.k]}"${isPast(p.b) ? ' opacity="0.45"' : ""}></rect>`
        );
      }
    }
    // Each day's lowest and highest price, of the whole day (a view may show only part of it),
    // labelled where it falls in view: in quarter hours the sensor's, in hours the day's cheapest
    // and dearest hour (on the curve, as its average)
    const format = this._readoutFormat(values);
    const extremes =
      resolution === "hour"
        ? dayParts.flatMap((day) => this._hourExtremes(day.date))
        : d.extremes.map(({ kind, price, at }) => ({
            kind,
            slot: { ...quarterSlots(d, at, at + d.step, d.step, d.averageKind)[0], price },
          }));
    for (const { kind, slot } of extremes) {
      if (this._hide.includes(kind) || slot.start < from || slot.start >= to) continue;
      const cx = (x(slot.start) + x(slot.end)) / 2;
      const cy = y(slot.price);
      // A pill like the averages' numbers, with the arrow the forecast card marks a day's low and
      // high with: the low's under its dot, the high's above it (the scale leaves room for them,
      // see EXTREME_ROOM), centered on the dot within the plot
      const text = format(slot.price);
      const w = 4 + 10 + 3 + text.length * 6.2 + 6;
      const lx = Math.min(Math.max(cx - w / 2, left), right - w);
      const ly = kind === "low" ? Math.min(cy + 8, bottom - 16) : Math.max(cy - 8 - 16, top - 4);
      parts.push(
        `<g${isPast(slot.end) ? ' class="past"' : ""}><circle class="extreme-dot" cx="${cx}" cy="${cy}" r="3.5" style="fill:${colorAt(slot)}"></circle><g class="extreme-label ${kind}"><rect x="${lx}" y="${ly}" width="${w}" height="16" rx="8"></rect><path d="${EXTREME_PATHS[kind]}" transform="translate(${lx + 4} ${ly + 3}) scale(${10 / 12})"></path><text x="${lx + 17}" y="${ly + 11.5}">${text}</text></g></g>`
      );
    }
    // The day's average in numbers at the right end of its dashed line, always in view; below
    // the line where it runs close to the top. Kept with their room, so they make way for the
    // cursor's dot (see _clearLabels): their box, the other place they may go to, and how far
    // they may move sideways
    const labels = [];
    if (referenceShown && !this._hide.includes("reference_label")) {
      for (const span of averageSpans) {
        const { reference } = span;
        if (typeof reference !== "number") continue;
        const label = `${d.averageLabel} ${format(reference)}`;
        const w = label.length * 6.2 + 10;
        const end = x(span.end) - 4;
        if (end - w < x(span.start) + 2) continue;
        const ry = y(reference);
        const py = ry - 19 < top - 4 ? ry + 3 : ry - 19;
        labels.push({ x: end - w, y: py, w, other: py < ry ? ry + 3 : ry - 19, min: x(span.start) + 2, max: end });
        parts.push(
          `<g class="reference-label" data-label="${labels.length - 1}"><rect x="${end - w}" y="${py}" width="${w}" height="16" rx="8"></rect><text x="${end - w / 2}" y="${py + 11.5}" text-anchor="middle">${label}</text></g>`
        );
      }
    }
    // Hours along the bottom, as many as fit
    const hours = (to - from) / HOUR_MS;
    const every = [1, 2, 3, 4, 6, 12].find((n) => (plotWidth / hours) * n >= 34) || 24;
    for (let time = localFloor(from, HOUR_MS, d.zone); time <= to; time += HOUR_MS) {
      if (time < from) continue;
      const hour = Math.floor(((time + zoneOffset(time, d.zone)) % (24 * HOUR_MS)) / HOUR_MS);
      if (hour % every) continue;
      const tx = x(time);
      if (tx < left + 6 || tx > right - 6) continue;
      // Under the periods' track where it's shown
      const tick = bottom + (periodsShown ? 7 : 0);
      // Midnight stands out, as the next step up on a time axis: a new day begins
      const midnight = hour === 0;
      parts.push(`<line class="grid" x1="${tx}" x2="${tx}" y1="${tick}" y2="${tick + (midnight ? 5 : 3)}"></line>`);
      parts.push(
        `<text${midnight ? ' class="midnight"' : ""} x="${tx}" y="${height - 3 - (xTitle ? 14 : 0) - foot}" text-anchor="middle">${d.hourTag(time)}</text>`
      );
    }
    // Now: in the middle of the quarter hour running, also in hours (where it's more precise than
    // the hour's point); left out in the views set for the resolution
    const nowHidden = this._hide.includes(`now_line_${resolution}`);
    const nowAt = localFloor(now, d.step, d.zone) + d.step / 2;
    if (!nowHidden && from <= nowAt && nowAt < to) {
      // At 15 min only while prices are read: at rest the cursor marks now already (at 60 min
      // it marks the hour, the line the quarter hour in it)
      parts.push(
        `<line class="now-line${resolution === "quarter_hour" ? " while-reading" : ""}" x1="${x(nowAt)}" x2="${x(nowAt)}" y1="${top - 4}" y2="${bottom}"></line>`
      );
    }
    parts.push(...extra.over);
    const animate = this._drawnView !== `${view}|${resolution}`;
    this._drawnView = `${view}|${resolution}`;
    plot.innerHTML = `<svg aria-hidden="true" viewBox="0 0 ${width} ${height}"><defs>${defs.join("")}</defs><g class="${animate ? "base" : ""}">${shades.join("")}${parts.join("")}</g><g class="cursor"></g></svg>`;
    const nowIndex = slots.findIndex((slot) => slot.start <= now && now < slot.end);
    this._geo = {
      // The cursor's layer and the averages' numbers, as drawn
      layer: plot.querySelector(".cursor"),
      labelEls: [...plot.querySelectorAll("[data-label]")].sort((a, b) => a.dataset.label - b.dataset.label),
      slots,
      from,
      to,
      left,
      right,
      top,
      bottom,
      x,
      y,
      nowIndex,
      format,
      colorAt,
      fillColorAt,
      valueMin: min,
      valueMax: max,
      // An hour's price is its quarter hours' average: marked so wherever it's shown
      averaged: resolution === "hour",
      labels,
      // The average of the prices shown, where the view is measured against it
      viewAverage: shownBasis ? shownAverage : undefined,
      referenceShown,
      rowMiddle,
      clearOf: switchWidth ? clearOf : right,
      // Fixed per draw, read on every move of the cursor: the colors, the view's options, the
      // widest price (the top line keeps its width) and the widest time span (12-hour clocks)
      colors,
      view: this._viewOptions(view),
      priceRoom: [format(min), format(max)].reduce((a, b) => (b.length > a.length ? b : a)),
      widestRange: [10, 11, 22, 23]
        .map((hour) => {
          const at = new Date(from).setHours(hour, 45, 0, 0);
          return timeRange(d.clockLong, at, at + QUARTER_MS);
        })
        .reduce((a, b) => (b.length > a.length ? b : a)),
    };
    plot.setAttribute("aria-valuemin", "0");
    plot.setAttribute("aria-valuemax", String(slots.length - 1));
    // A cursor outside the view (another day) is let go
    if (this._cursor !== undefined && !(from <= this._cursor && this._cursor < to)) this._cursor = undefined;
    this._drawCursor();
  }

  // The colors of the line and of the average style, as set for the mode the card shows in
  _colors() {
    return chartColors(this._config, this._dark());
  }

  // How strong the shade off a day's line is, as set (0: none), in percent on light themes
  _shadeStrength() {
    const value = this._config.day_shade_strength;
    return typeof value === "number" ? value : CHART_DAY_SHADE.strength;
  }

  // Whether the card shows in dark: as set, else as the theme
  _dark() {
    const appearance = this._config.appearance;
    return (
      appearance === "dark" || (appearance !== "light" && Boolean(this._hass.themes && this._hass.themes.darkMode))
    );
  }

  // Prices in the line above: one decimal in ct and øre, two in € and kr
  _readoutFormat(values) {
    const format = fixedPriceFormat(this._hass, Math.max(...values.map(Math.abs)) >= 10 ? 1 : 2);
    // Negative prices with a real minus sign
    return Object.assign((value) => format(value).replace("-", "\u2212"), { decimals: format.decimals });
  }

  // The slot the cursor points at: hovered, set, or now (undefined: none, e.g. tomorrow)
  _shownIndex() {
    const g = this._geo;
    if (!g) return -1;
    const time = this._hover !== undefined ? this._hover : this._cursor;
    if (time !== undefined) return g.slots.findIndex((slot) => slot.start <= time && time < slot.end);
    return g.nowIndex;
  }

  _drawCursor() {
    const g = this._geo;
    if (!g) return;
    const { layer } = g;
    const index = this._shownIndex();
    const slot = g.slots[index];
    const pinned = this._cursor !== undefined || this._hover !== undefined;
    this._els.plot.classList.toggle("is-reading", pinned);
    this._els.toNow.hidden = !(this._cursor !== undefined && g.nowIndex >= 0);
    // The switches back in view, unless the tag drawn below needs their place again (also in a
    // view without now, like tomorrow, where nothing is drawn once the pointer has gone)
    this._yieldSwitch(false);
    if (!slot) {
      layer.innerHTML = "";
      this._clearLabels();
      this._readoutSummary();
      return;
    }
    const d = this._data;
    const a = g.x(slot.start);
    const b = g.x(slot.end);
    const cx = (a + b) / 2;
    this._clearLabels(cx, slot.price !== null ? g.y(slot.price) : undefined);
    // The slot shaded from the bottom up to the underside of the price line; above the line, up
    // to the tag, a dashed line while prices are being read (not for now at rest)
    let marks = "";
    if (slot.price !== null) {
      const color = g.colorAt(slot);
      const cy = g.y(slot.price);
      const under = Math.min(cy + 1.5, g.bottom);
      marks += `<rect class="cursor-band" x="${a}" y="${under}" width="${Math.max(b - a, 1)}" height="${g.bottom - under}"></rect>`;
      if (pinned) marks += `<line class="cursor-line" x1="${cx}" x2="${cx}" y1="${g.top - 4}" y2="${cy}"></line>`;
      // At rest on now, where neither the pill nor the line of now says so (15 min), the halo
      // breathes softly: the card shows the price live. Still while prices are read
      const live = !pinned && index === g.nowIndex && !g.averaged;
      marks += `<circle class="cursor-halo${live ? " live" : ""}" cx="${cx}" cy="${cy}" r="11" style="fill:${color}"></circle><circle class="cursor-dot" cx="${cx}" cy="${cy}" r="5" style="fill:${color}"></circle>`;
    }
    marks += this._extraCursor(slot, cx);
    layer.innerHTML = marks;
    // A best or peak price period the slot is in (or part of it)
    const period = slotPeriod(d.periods, slot.start, slot.end);
    if (pinned) this._drawCursorTag(layer, slot, cx, period);
    else this._tagShown = undefined;
    this._readout(slot, index, { live: index === g.nowIndex && !pinned, reading: pinned, period });
  }

  // The price of the quarter hour a moment falls in (null: not known), of the prices shown or of
  // `prices` on the same quarter hours
  _quarterPrice(time, prices = this._data.prices) {
    const d = this._data;
    const i = Math.floor((time - d.start) / d.step);
    return i >= 0 && i < prices.length ? prices[i] : null;
  }

  // The resolution switch out of the way of the cursor's tag, for as long as the mouse reads the
  // prices under it
  _yieldSwitch(yields) {
    this._els.overlay.classList.toggle("is-yielding", yields);
  }

  /**
   * The averages' numbers make way for the cursor's dot at (cx, cy): to the other side of their
   * line, else beside the cursor within their day, else nearly out of sight; back in place once
   * the dot has moved on
   */
  _clearLabels(cx, cy) {
    const g = this._geo;
    const room = 14; // The dot's halo and a little air
    const hits = (x, y, w) =>
      cy !== undefined && cx > x - room && cx < x + w + room && cy > y - room && cy < y + 16 + room;
    g.labels.forEach((label, i) => {
      const el = g.labelEls[i];
      if (!el) return;
      let dx = 0;
      let dy = 0;
      let hidden = false;
      if (hits(label.x, label.y, label.w)) {
        if (!hits(label.x, label.other, label.w)) dy = label.other - label.y;
        else if (cx - room - label.w >= label.min) dx = cx - room - label.w - label.x;
        else if (cx + room + label.w <= label.max) dx = cx + room - label.x;
        else hidden = true;
      }
      // (Written only where it changes: most moves leave the numbers be)
      const transform = dx || dy ? `translate(${dx}px, ${dy}px)` : "";
      if (el.style.transform !== transform) el.style.transform = transform;
      if (el.classList.contains("is-yielding") !== hidden) el.classList.toggle("is-yielding", hidden);
    });
  }

  /**
   * What the cursor points at, in a tag above the curve on its line: day, time span and price,
   * with a dot in the color of the point on the curve. Up there, not beside the point: a finger
   * on the curve covers its surroundings, and the tag stays in one row, over nothing the curve
   * shows. Laid out from the text's measured width
   */
  _drawCursorTag(layer, slot, cx, inPeriod) {
    const g = this._geo;
    const d = this._data;
    // The time first, as in the top line, then the day, set apart by a dot (it's no pill here)
    const when = `${timeRange(d.clockLong, slot.start, slot.end)}<tspan class="cursor-day"> · ${this._dayWord(d.dateOf(slot.start), slot.start)}</tspan>`;
    const priced = slot.price !== null;
    // Price and time change at once (they belong to the slot under the finger); the swatch's
    // color eases over from the last slot's, a period's badge fades in where it comes up
    const color = priced ? g.colorAt(slot) : "";
    const last = this._tagShown || {};
    const swatchFrom = last.color && color && last.color !== color ? last.color : "";
    const unit = this._unitShown("tag");
    const tag = document.createElementNS("http://www.w3.org/2000/svg", "g");
    tag.setAttribute("class", "cursor-tag");
    tag.innerHTML = `<rect class="cursor-pill" rx="8"></rect><text class="cursor-time" text-anchor="middle">${when}</text>${
      priced
        ? `<circle class="cursor-swatch${swatchFrom ? " changed" : ""}" r="3.5" style="fill:${color}${swatchFrom ? `;--from:${swatchFrom}` : ""}"></circle><text class="cursor-price">${g.averaged ? `<tspan class="cursor-avg">${d.averageLabel} </tspan>` : ""}${g.format(slot.price)}${unit ? `<tspan class="cursor-unit"> ${unit}</tspan>` : ""}</text>`
        : ""
    }`;
    layer.append(tag);
    const [time, price] = tag.querySelectorAll("text");
    const widthOf = (text, perChar) => text.getComputedTextLength() || text.textContent.length * perChar;
    // Two lines: day and time span small, the price below it large; as wide as the wider one
    const timeWidth = widthOf(time, 6);
    const priceWidth = price ? 7 + 5 + widthOf(price, 7) : 0;
    // In a best or peak price period: its badge centered on the tag's top right corner, as on
    // the columns of the forecast card (the tag a little wider, so it covers no text)
    const period = !g.view.hide.includes("badge") && inPeriod;
    const w = Math.max(timeWidth, priceWidth) + 16 + (period ? 6 : 0);
    const h = price ? 32 : 18;
    // Centered on the cursor's line in the top row, below it where the resolution switch is;
    // while the mouse reads the prices, the switch makes way instead (see _yieldSwitch). Beside
    // the line where the point on the curve would be under the tag, and there too below the
    // switches where a finger has left the tag (a high peak is the case: the tag would else
    // lie under them). Below, a period's badge on the tag's corner keeps clear of them too
    const mouse = this._hover !== undefined;
    const badgeRoom = period ? 9 : 0;
    const clamp = (x) => Math.min(Math.max(x, g.left), g.right - w - badgeRoom);
    const belowSwitch = g.top - 2 + (period ? 8 : 0);
    const rowFor = (x) => (!mouse && x + w + badgeRoom > g.clearOf ? belowSwitch : 1);
    const dot = priced ? g.y(slot.price) : undefined;
    let px = clamp(cx - w / 2);
    let py = rowFor(px);
    if (dot !== undefined && dot < py + h + 10) {
      px = clamp(cx - 14 - w >= g.left ? cx - 14 - w : cx + 14);
      py = rowFor(px);
    }
    this._yieldSwitch(mouse && px + w + badgeRoom > g.clearOf);
    const rect = tag.querySelector("rect");
    rect.setAttribute("x", px);
    rect.setAttribute("y", py);
    rect.setAttribute("width", w);
    rect.setAttribute("height", h);
    if (period) {
      const bx = px + w;
      const by = py;
      const nudge = PERIOD_NUDGE[period.k] ? ` ${PERIOD_NUDGE[period.k]}` : "";
      // A part of the slot only: a ring like a dial, the hour from the top round, colored where
      // the period lies (the 15 min view shows it exactly), the sign inside in its color
      const ring = (a, b) => {
        const share = (time) => ((time - slot.start) / (slot.end - slot.start)) * 360;
        return `<path class="part" d="${arcPath(9, 7, share(a), Math.min(share(b), 359.9))}" style="stroke:${MARK_COLORS[period.k]}"></path>`;
      };
      const badge = period.partial
        ? `<g class="tag-badge partial" transform="translate(${bx - 9} ${by - 9})"><circle cx="9" cy="9" r="8.5"></circle><circle class="track" cx="9" cy="9" r="7" style="stroke:${MARK_COLORS[period.k]}"></circle>${period.parts
            .map(([a, b]) => ring(a, b))
            .join(
              ""
            )}<path class="sign" d="${PERIOD_PATHS[period.k]}" transform="translate(4.5 4.5) scale(0.375)${nudge}" style="fill:${MARK_COLORS[period.k]}"></path></g>`
        : `<g class="tag-badge"><circle cx="${bx}" cy="${by}" r="8.5" style="fill:${MARK_COLORS[period.k]}"></circle><path d="${PERIOD_PATHS[period.k]}" transform="translate(${bx - 6} ${by - 6}) scale(0.5)${nudge}"></path></g>`;
      tag.insertAdjacentHTML("beforeend", badge);
      if (last.badge !== `${period.k}${period.partial}`) tag.lastElementChild.classList.add("is-appearing");
    }
    this._tagShown = { color, badge: period ? `${period.k}${period.partial}` : "" };
    time.setAttribute("x", px + (w - (period ? 6 : 0)) / 2);
    time.setAttribute("y", py + 12.5);
    if (price) {
      const start = px + (w - (period ? 6 : 0) - priceWidth) / 2;
      const swatch = tag.querySelector("circle");
      swatch.setAttribute("cx", start + 3.5);
      swatch.setAttribute("cy", py + 22.5);
      price.setAttribute("x", start + 12);
      price.setAttribute("y", py + 27);
    }
  }

  /**
   * The line above the curve: when, small on top; below it the price, large, and beside it the
   * rest as small chips to take in at a glance (the full sentences in their tooltips and for
   * screen readers): the price level in its color, a best or peak price period (with its times
   * where it covers part of the slot), how far off the average (an arrow, tinted as below and
   * above the average are), and in hours the quarter hour's price now
   */
  _readout(slot, index, { live, reading, period }) {
    const d = this._data;
    const t = this._t;
    const g = this._geo;
    const plot = this._els.plot;
    const date = d.dateOf(slot.start);
    const range = timeRange(d.clockLong, slot.start, slot.end);
    // The slot running now is "now" (also with the cursor on it), in hours with the quarter
    // hour's price in its pill: the large price there is the hour's average
    const now = Date.now();
    const holdsNow = slot.start <= now && now < slot.end;
    const nowPrice = g.averaged && holdsNow && slot.price !== null ? this._quarterPrice(now) : null;
    const when = holdsNow ? `${t.now} · ${range}` : `${this._dayWord(date, slot.start)} · ${range}`;
    // At rest in quarter hours the price shown is the one now, plainly: no pill then. While prices
    // are read it tells now apart, and in hours it carries the quarter hour's price
    // In a view of one day its tab names the day: no pill for it (now's still tells now apart)
    const oneDay = CHART_SINGLE_DAY_VIEWS.includes(this._view);
    const pill =
      live && !g.averaged
        ? ""
        : holdsNow
          ? this._dayPill(null, slot.start, nowPrice)
          : oneDay
            ? ""
            : this._dayPill(date, slot.start);
    // The time first, at the width of the widest (digits of one width, the longest hours of a
    // 12-hour clock), then the day: the pills differ in width (now, today, a weekday), so the time
    // after one would jump from slot to slot
    const steadyRange = steadyText(g.widestRange, range, "start");
    const whenHtml = pill ? `${steadyRange} ${pill}` : steadyRange;
    if (slot.price === null) {
      this._setReadout(whenHtml, "–", [this._chip(t.detail.unknown)], "", {
        day: pill,
        range,
      });
      plot.setAttribute("aria-valuetext", `${when}, ${t.detail.unknown}`);
      return;
    }
    // Against the average the dashed line shows: the view's where it spans more than a day (the
    // outlook, both days), else the day's
    const viewWide = g.viewAverage !== undefined && t.chart.vs_view[this._view];
    const reference = viewWide ? g.viewAverage : d.references[date];
    const change = typeof reference === "number" ? shownChange(slot.price, reference, g.format) : undefined;
    const percent = change !== undefined ? formatPercent(this._hass.language, change, "always") : "";
    const delta = percent
      ? fill((viewWide ? t.chart.vs_view[this._view] : t.detail.pick.vs_day)[d.averageKind], { percent })
      : "";
    // Over part of the slot only (an hour): when exactly
    const periodName =
      period && (period.partial ? `${t[period.k]} ${timeRange(d.clockLong, period.start, period.end)}` : t[period.k]);
    const level = slot.level && t.levels[slot.level];
    const colors = g.colors;
    // Level and gap as the view wants them: always, only while reading prices, never; the level
    // only at some levels, the gap only from some size on (as shown, in whole percent)
    const view = g.view;
    const shows = (mode) => mode === "always" || (mode === "reading" && reading);
    const levelShown =
      shows(view.header_level) && (!view.header_level_at.length || view.header_level_at.includes(slot.level));
    const deltaShown =
      shows(view.header_delta) &&
      change !== undefined &&
      Math.round(Math.abs(change) * 100) >= (Number(view.header_delta_from) || 0);
    // The average itself where the chart doesn't show it as its dashed line (unless left out)
    const averageChip =
      typeof reference === "number" &&
      !g.referenceShown &&
      !view.hide.includes("header_average") &&
      this._chip(`${d.averageLabel} ${g.format(reference)}`, {
        title: viewWide ? delta : t.day_reference[d.averageKind],
        cls: "plain",
      });
    const levelChip =
      level &&
      levelShown &&
      this._chip(`<span class="chip-text">${level}</span>`, {
        color: levelColor(slot.level),
        dot: true,
        title: level,
        cls: "level",
      });
    const periodChip =
      period &&
      this._chip(period.partial ? timeRange(d.clockLong, period.start, period.end) : t[period.k], {
        color: MARK_COLORS[period.k],
        icon: PERIOD_PATHS[period.k],
        title: periodName,
        cls: `period ${period.k}`,
      });
    const gapChip =
      delta &&
      deltaShown &&
      this._chip(
        // As wide as for three digits whatever it holds, the arrow in front and the percent
        // sign at fixed places, so moving the cursor doesn't shake the line (wider only from
        // 1000 % on)
        `${steadyText("↑", change > 0 ? "↑" : change < 0 ? "↓" : "=", "center")} ${steadyText(
          formatPercent(this._hass.language, 1),
          `<span data-tween="percent" data-value="${Math.abs(change)}">${formatPercent(this._hass.language, Math.abs(change))}</span>`
        )} ${d.averageLabel}`,
        { color: change > 0 ? colors.line.above : colors.line.below, title: delta, cls: "delta" }
      );
    // The gap first, at a steady width, then the average; the level and the period last: the
    // level's names differ in length and the period comes and goes, so what followed them would
    // jump from slot to slot (the line and the ring alike)
    const chips = [gapChip, averageChip, levelChip, periodChip, ...this._extraChips(slot)];
    // The ring: the price where it lies between the view's lowest and highest, in the area's
    // color; below it the day (or now), the average it's measured against, how far off, a period
    const span = g.valueMax - g.valueMin;
    const dial = {
      day: pill,
      range,
      steadyRange,
      share: span > 0 ? (slot.price - g.valueMin) / span : 0.5,
      color: g.fillColorAt(slot),
      title: [level, periodName].filter(Boolean).join(", "),
    };
    this._setReadout(whenHtml, slot.price, chips, g.averaged ? d.averageLabel : "", dial);
    plot.setAttribute("aria-valuenow", String(index));
    plot.setAttribute(
      "aria-valuetext",
      [
        when,
        `${g.averaged ? `${d.averageLabel} ` : ""}${g.format(slot.price)} ${d.unit}`,
        nowPrice !== null && `${t.now} ${g.format(nowPrice)} ${d.unit}`,
        level,
        periodName,
        delta,
      ]
        .filter(Boolean)
        .join(", ")
    );
  }

  /**
   * The unit as the card is set to show it at a place (header, tag, axis): the unit rate's whole
   * (ct/kWh), the currency alone (ct; also where `short`, e.g. a small ring), or none. Read out
   * whole for screen readers anyway
   */
  _unitShown(place, short = false) {
    const unit = this._data ? this._data.unit : "";
    const mode = (this._config.units || {})[place] || CHART_UNIT_PLACES[place];
    if (mode === "none") return "";
    return mode === "currency" || short ? unit.split("/")[0] : unit;
  }

  /**
   * The day as a pill: "now" in the color of now, its dot pulsing (in hours with the price of the
   * quarter hour now), yesterday, today, tomorrow in theirs (a weekday further off as today's)
   */
  _dayPill(date, time, price = null) {
    const t = this._t;
    if (date === null) {
      const now = price !== null ? ` <b>${this._geo.format(price)}</b>` : "";
      return `<span class="day-pill now"><span class="live-dot" aria-hidden="true"></span>${t.now}${now}</span>`;
    }
    const d = this._data;
    const kind =
      date === d.today ? "today" : date === d.tomorrow ? "tomorrow" : date === d.yesterday ? "yesterday" : "today";
    const colors = this._geo ? this._geo.colors : this._colors();
    return `<span class="day-pill" style="--pill:${colors.days[kind]}">${this._dayWord(date, time)}</span>`;
  }

  // A chip of the line above the curve: tinted in its color, with a dot or a sign in front
  _chip(html, { color, dot = false, icon, title, cls = "" } = {}) {
    const lead = icon ? `${svgIcon(icon)}` : dot ? '<span class="chip-dot"></span>' : "";
    return `<span class="chip ${cls}" data-key="chip-${cls.split(" ")[0] || "plain"}"${color ? ` style="--chip:${color}"` : ""}${title ? ` title="${title}"` : ""}>${lead}${html}</span>`;
  }

  // The line above the curve: when, then the price (an average marked as such) and its chips
  _setReadout(when, price, chips = [], mark = "", dial = {}) {
    const d = this._data;
    // A price as a number counts over to the next one; text ("–") is set as it is
    const priceHtml =
      typeof price === "number"
        ? `<span data-tween="price" data-value="${price}">${this._geo.format(price)}</span>`
        : price;
    if (this._config.header === "dial") {
      this._setDial(priceHtml, mark, chips, dial);
      return;
    }
    // Price and unit as wide as with the view's widest price (its lowest or highest, as shown), the
    // unit right after the price: the chips after them stay put while the cursor moves (a wider
    // price than those pushes them on)
    const g = this._geo;
    const room = g ? g.priceRoom : "";
    const headerUnit = d ? this._unitShown("header") : "";
    const unit = headerUnit ? `<span class="unit">${headerUnit}</span>` : "";
    const value = (text) => `<span class="amount"><span class="price">${text}</span>${unit}</span>`;
    this._morph(`<div class="when-line">${when}</div>
      <div class="value-line">${mark ? `<span class="avg-mark">${mark}</span>` : ""}${
        room ? steadyText(value(room), value(priceHtml), "start") : value(priceHtml)
      }<span class="chips">${chips.filter(Boolean).join("")}</span></div>`);
    this._fitChips();
  }

  // The line above the curve changed in place, its numbers counting over (see morphInto)
  _morph(html) {
    morphInto(this._els.main, html, (el, text, before) => this._tween(el, text, before));
  }

  /**
   * A number counting over to its new value, quick and easing out (about a fifth of a second), as
   * Tibber's app does; at once where motion is reduced. From what it shows right now, so moving
   * on before it's done carries on smoothly
   */
  _tween(el, text, before) {
    const to = Number(el.dataset.value);
    const from = el._running ? el._shown : before;
    const format =
      el.dataset.tween === "percent"
        ? (value) => formatPercent(this._hass.language, value)
        : (value) => (this._geo ? this._geo.format(value) : text);
    cancelAnimationFrame(el._frame);
    el._running = false;
    const still = REDUCED_MOTION && REDUCED_MOTION.matches;
    if (still || from === to || !Number.isFinite(from) || !Number.isFinite(to)) {
      el.textContent = text;
      return;
    }
    const start = performance.now();
    const step = (now) => {
      // (A frame's time can lie just before the start: its frame began earlier)
      const t = Math.min(Math.max((now - start) / CHART_TWEEN_MS, 0), 1);
      const eased = 1 - (1 - t) ** 3;
      el._shown = from + (to - from) * eased;
      el.textContent = t < 1 ? format(el._shown) : text;
      el._running = t < 1;
      if (t < 1) el._frame = requestAnimationFrame(step);
    };
    el._running = true;
    el._shown = from;
    el._frame = requestAnimationFrame(step);
  }

  /**
   * How large the ring is, and what goes in it, from the card's room: about a fifth of its
   * height (with a height set in a sections view; else from its width), 60 to 140 px, at most a
   * third of its width. Large: price, unit and time span in the ring; medium: price and unit,
   * the time beside it; small: the price alone. On the left with the rest beside it, so the curve
   * keeps its height and the width is used; centered (as in Tibber's app) only where a card is
   * narrow and tall (a phone): beside it there'd be no room
   */
  _dialLayout() {
    // Once per draw (a resize draws anew), not on every move of the cursor: it reads the layout
    if (this._dialMemo) return this._dialMemo;
    const card = this.shadowRoot.querySelector("ha-card");
    const width = Math.max(card.clientWidth - 24, 0);
    const fixed = Boolean(getComputedStyle(this).getPropertyValue("--row-size").trim());
    const height = fixed ? card.clientHeight : width * 0.5 + 140;
    const size = Math.round(Math.max(60, Math.min(140, height * 0.21, width * 0.33)));
    const center = size >= 124 && height >= 520 && width < 480;
    const detail = center || size >= 104 ? "large" : size >= 80 ? "medium" : "small";
    this._dialMemo = { size, center, detail };
    return this._dialMemo;
  }

  /**
   * The ring above the curve: a track round, colored from the top clockwise as far as the price
   * lies between the view's lowest and highest (in the area's color there); in it the price (and
   * as room allows its unit and time span); beside it (below it, centered) the day and the time,
   * and the chips
   */
  _setDial(price, mark, chips, { day = "", range = "", steadyRange = "", share, color, title = "" }) {
    const d = this._data;
    const { size, center, detail } = this._dialLayout();
    const box = 100;
    const radius = 46;
    // The arc: a circle drawn as far as the share, from the top clockwise (a dash, so its length
    // and color ease over to the next)
    const arc =
      typeof share === "number"
        ? `<circle class="dial-arc" cx="${box / 2}" cy="${box / 2}" r="${radius}" pathLength="100" transform="rotate(-90 ${box / 2} ${box / 2})" style="stroke:${color};stroke-dasharray:${(Math.max(4 / 360, Math.min(share, 0.999)) * 100).toFixed(2)} 100"></circle>`
        : "";
    // The unit in the ring under the price: whole, or where the ring is small its first part ("ct"
    // of "ct/kWh"), in proportion
    const unit = d ? this._unitShown("header", detail === "small") : "";
    const rangeInside = detail === "large" && range;
    // (After a pill no dot: it stands apart by itself)
    // Beside the ring the time first (at a steady width), then the day, as in the line with chips
    const rest = rangeInside ? "" : steadyRange || range;
    const when = day && rest ? `${rest}${day.includes("day-pill") ? " " : " · "}${day}` : day || rest;
    const readout = this._els.readout;
    readout.classList.toggle("is-dial-centered", center);
    readout.style.setProperty("--dial-size", `${size}px`);
    this._morph(
      `<div class="dial ${detail}"${title ? ` title="${title}"` : ""}>
        <svg viewBox="0 0 ${box} ${box}" aria-hidden="true"><circle class="dial-track" cx="${box / 2}" cy="${box / 2}" r="${radius}"></circle>${arc}</svg>
        <div class="dial-center"><div class="dial-value">${mark ? `<span class="avg-mark">${mark}</span>` : ""}<span class="price">${price}</span></div>${
          unit ? `<div class="dial-unit">${unit}</div>` : ""
        }${rangeInside ? `<div class="dial-range">${range}</div>` : ""}</div>
      </div>
      <div class="dial-side"><div class="dial-day">${when}</div><span class="chips">${chips.filter(Boolean).join("")}</span></div>`
    );
    this._fitChips();
  }

  // Chips that don't fit aren't cut in half: the level's goes down to its dot first, then the
  // last ones give way, whole
  _fitChips() {
    const row = this.shadowRoot.querySelector(".readout .chips");
    if (!row || !row.clientWidth) return;
    const chips = [...row.children];
    // Measured once each way (a chip hidden never moves those before it), not in a loop
    const right = row.getBoundingClientRect().right + 1;
    const ends = () => chips.map((chip) => chip.getBoundingClientRect().right);
    if (ends().every((end) => end <= right)) return;
    const level = row.querySelector(".chip.level");
    if (level) level.classList.add("compact");
    ends().forEach((end, i) => {
      if (i > 0 && end > right) chips[i].hidden = true;
    });
  }

  // Without a slot to point at (a view without now): the day's average, its low and high
  _readoutSummary() {
    const d = this._data;
    const t = this._t;
    const g = this._geo;
    const known = g.slots.filter((slot) => slot.price !== null);
    const date = d.dateOf(g.from);
    const reference = d.references[date];
    const values = known.map((slot) => slot.price);
    const average = typeof reference === "number" ? reference : aggregate(values, d.averageKind);
    const name = `${this._dayWord(date, g.from)} · ${t.day_reference[d.averageKind]}`;
    // Shown as the price with ⌀ before it, the day named by the view's tab: the line above stays
    // empty (no "daily average" label, which nothing else has)
    const label = CHART_SINGLE_DAY_VIEWS.includes(this._view) ? "" : this._dayPill(date, g.from);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const extreme = (kind, value) =>
      this._chip(`${extremeIcon(kind)}${g.format(value)}`, {
        title: `${t[`day_${kind}`]} ${g.format(value)} ${d.unit}`,
        cls: `extreme-${kind}`,
      });
    const span = g.valueMax - g.valueMin;
    this._setReadout(label, average, [extreme("low", low), extreme("high", high)], d.averageLabel, {
      day: label,
      share: span > 0 ? (average - g.valueMin) / span : 0.5,
      color: "var(--secondary-text-color)",
    });
    this._els.plot.setAttribute(
      "aria-valuetext",
      `${name}, ${g.format(average)} ${d.unit}, ${t.day_low} ${g.format(low)}, ${t.day_high} ${g.format(high)}`
    );
  }

  _indexAt(clientX) {
    const g = this._geo;
    const box = this._els.plot.getBoundingClientRect();
    const share = (clientX - box.left - g.left) / (g.right - g.left);
    return Math.min(Math.max(Math.floor(share * g.slots.length), 0), g.slots.length - 1);
  }

  _setCursor(index, { haptic = false } = {}) {
    const g = this._geo;
    if (!g) return;
    const slot = g.slots[index];
    if (!slot) return;
    const changed = this._cursor !== slot.start;
    // (A drag within the same slot changes nothing)
    if (!changed && this._hover === undefined) return;
    this._cursor = slot.start;
    this._hover = undefined;
    if (haptic && changed) this._haptic("selection");
    this._drawCursor();
  }

  // The pointer over a slot, as a mouse hovering (ticking at each new slot where asked)
  _hoverAt(clientX, haptic) {
    const slot = this._geo && this._geo.slots[this._indexAt(clientX)];
    if (!slot || slot.start === this._hover) return;
    this._hover = slot.start;
    if (haptic) this._haptic("selection");
    this._drawCursor();
  }

  _backToNow() {
    clearTimeout(this._returnTimer);
    this._cursor = undefined;
    this._hover = undefined;
    this._drawCursor();
  }

  _scheduleReturn() {
    clearTimeout(this._returnTimer);
    if (this._cursor === undefined) return;
    this._returnTimer = setTimeout(() => this._backToNow(), CHART_RETURN_MS);
  }

  /**
   * Touch, like the pointer of a mouse: a finger held still for a moment grabs it (a short buzz),
   * then it follows the finger in any direction (the page doesn't scroll meanwhile), ticking at
   * each slot; a sideways drag grabs it at once. Let go, it stays there; a vertical swipe
   * scrolls the page as usual, a tap sets the cursor (either goes back to now by itself). Mouse:
   * it follows the pointer and a click keeps it there. Keyboard: arrows by one slot, Page Up/Down
   * by an hour or six, Home/End, Escape for now
   */
  _bindPlot(plot) {
    // The mouse's press (a click keeps the cursor until the pointer leaves); touch is _bindHold's
    let pressed;
    plot.addEventListener("pointerdown", (ev) => {
      if (!this._geo || ev.button > 0 || ev.pointerType !== "mouse") return;
      clearTimeout(this._returnTimer);
      pressed = ev.pointerId;
      this._setCursor(this._indexAt(ev.clientX));
    });
    this._bindHold(plot, {
      start: () => {
        if (!this._geo) return false;
        clearTimeout(this._returnTimer);
        return true;
      },
      // Sideways grabs at once, not only after the hold
      early: (dx, dy) => Boolean(this._geo) && dx > CHART_DRAG_PX && dx > dy,
      grab: (x) => {
        plot.classList.add("is-dragging");
        this._hoverAt(x, false);
      },
      move: (x) => this._geo && this._hoverAt(x, true),
      end: (ev, held, cancelled) => {
        plot.classList.remove("is-dragging");
        if (held) {
          // Let go: the cursor stays where the finger left it, like after a tap
          if (this._hover !== undefined) this._cursor = this._hover;
          this._hover = undefined;
          this._drawCursor();
        } else if (!cancelled) {
          // A tap sets the cursor until the timer runs out
          this._setCursor(this._indexAt(ev.clientX));
        }
        this._scheduleReturn();
      },
    });
    plot.addEventListener("pointermove", (ev) => {
      if (!this._geo || ev.pointerType !== "mouse") return;
      if (pressed === ev.pointerId) {
        this._setCursor(this._indexAt(ev.clientX));
        return;
      }
      // Near the (hidden) switches, not only on them: they come back to be clicked before the
      // pointer reaches them, the cursor goes
      const box = this._els.overlay.getBoundingClientRect();
      const near = CHART_SWITCH_ZONE_PX;
      if (
        box.width &&
        ev.clientX >= box.left - near &&
        ev.clientX <= box.right + near &&
        ev.clientY >= box.top - near &&
        ev.clientY <= box.bottom + near
      ) {
        if (this._hover !== undefined) {
          this._hover = undefined;
          this._drawCursor();
        }
        return;
      }
      this._hoverAt(ev.clientX, false);
    });
    const release = (ev) => {
      if (pressed === ev.pointerId) pressed = undefined;
    };
    plot.addEventListener("pointerup", release);
    plot.addEventListener("pointercancel", release);
    plot.addEventListener("pointerleave", (ev) => {
      if (ev.pointerType !== "mouse" || pressed !== undefined) return;
      this._hover = undefined;
      this._drawCursor();
      this._scheduleReturn();
    });
    plot.addEventListener("keydown", (ev) => {
      const g = this._geo;
      if (!g) return;
      const hourly = this._resolution() === "hour";
      const current = this._shownIndex() >= 0 ? this._shownIndex() : 0;
      const jump = hourly ? 6 : 4;
      const target = {
        ArrowLeft: current - 1,
        ArrowRight: current + 1,
        PageUp: current - jump,
        PageDown: current + jump,
        Home: 0,
        End: g.slots.length - 1,
      }[ev.key];
      if (ev.key === "Escape" && this._cursor !== undefined) {
        ev.preventDefault();
        this._backToNow();
        return;
      }
      if (target === undefined) return;
      ev.preventDefault();
      this._setCursor(Math.min(Math.max(target, 0), g.slots.length - 1));
      this._scheduleReturn();
    });
  }

  // The editor's form for the card as a whole; each view's panel has a form of its own (viewSchema)
  static getConfigForm() {
    const e = languageStrings(EDITOR_STRINGS);
    const t = languageStrings(STRINGS);
    return {
      schema: [
        EDITOR_FIELDS.device(),
        {
          name: "views",
          selector: {
            select: {
              multiple: true,
              reorder: true,
              options: CHART_VIEWS.map((value) => ({ value, label: chartViewName(t, value) })),
            },
          },
        },
        // Right under the views: what Tomorrow does until its prices are in (Yesterday in its
        // place, say), a setting of the card's, not of one view
        {
          name: "tomorrow_pending",
          required: true,
          helper: "chart_tomorrow_pending_help",
          selector: dropdown(
            marked(
              e,
              CHART_TOMORROW_PENDING,
              (value) => e[`tomorrow_pending_${value}`],
              CHART_DEFAULTS.tomorrow_pending
            )
          ),
        },
        {
          name: "content",
          type: "expandable",
          flatten: true,
          iconPath: CONTENT_PATH,
          schema: [
            { name: "show_title", selector: { boolean: {} } },
            { name: "title", visible: { field: "show_title", value: true }, selector: { text: {} } },
            EDITOR_FIELDS.priceUnit(e),
            EDITOR_FIELDS.priceSource(e),
            // The tick box "Energy price only" beside the views, to switch while looking
            { name: "price_source_switch", selector: { boolean: {} } },
            // Where the unit shows, and how much of it (nested under units)
            {
              name: "units",
              type: "expandable",
              icon: "mdi:currency-eur",
              schema: Object.entries(CHART_UNIT_PLACES).map(([place, fallback]) => ({
                name: place,
                label: e[`unit_place_${place}`],
                helper: place === "header" ? "unit_display_help" : undefined,
                selector: dropdown(marked(e, CHART_UNIT_DISPLAYS, (value) => e[`unit_display_${value}`], fallback)),
              })),
            },
            { ...EDITOR_FIELDS.average(e), helper: "chart_average_help" },
            EDITOR_FIELDS.appearance(e),
            {
              name: "header",
              selector: dropdown(marked(e, CHART_HEADERS, (value) => e[`header_${value}`], CHART_DEFAULTS.header)),
            },
            {
              name: "axis_decimals",
              selector: dropdown(
                marked(e, CHART_AXIS_DECIMALS, (value) => (value === "auto" ? e.axis_decimals_auto : value), "auto")
              ),
            },
            // The price lines: thickness and strength (one value for light and dark themes)
            {
              name: "",
              type: "grid",
              schema: [
                {
                  name: "grid_line_width",
                  selector: { number: { min: 0, max: 4, step: 0.25, mode: "box", unit_of_measurement: "px" } },
                },
                {
                  name: "grid_line_strength",
                  selector: { number: { min: 0, max: 100, step: 1, mode: "box", unit_of_measurement: "%" } },
                },
                {
                  name: "day_line_width",
                  selector: { number: { min: 0, max: 4, step: 0.25, mode: "box", unit_of_measurement: "px" } },
                },
                {
                  name: "day_line_strength",
                  selector: { number: { min: 0, max: 100, step: 1, mode: "box", unit_of_measurement: "%" } },
                },
                {
                  name: "day_shade_strength",
                  selector: { number: { min: 0, max: 30, step: 0.5, mode: "box", unit_of_measurement: "%" } },
                },
                {
                  name: "day_shade_width",
                  selector: { number: { min: 0.5, max: 6, step: 0.5, mode: "box", unit_of_measurement: "h" } },
                },
              ],
            },
            // Axis titles, off unless asked for
            {
              name: "",
              type: "grid",
              schema: [
                { name: "axis_title_x", selector: { boolean: {} } },
                { name: "axis_title_y", selector: { boolean: {} } },
              ],
            },
          ],
        },
        // As the other cards: the card's actions (on its head; the curve is the cursor's)
        {
          name: "interactions",
          type: "expandable",
          flatten: true,
          iconPath: GESTURE_TAP_PATH,
          schema: [
            {
              name: "tap_opens",
              selector: {
                select: {
                  mode: "box",
                  options: marked(e, CHART_TAP_OPENS, (value) => e[`tap_opens_${value}`], "nothing"),
                },
              },
            },
            { ...EDITOR_FIELDS.windowWidth(e), visible: { field: "tap_opens", value: "forecast" } },
            { name: "action_button", selector: { boolean: {} } },
            {
              name: "action_button_text",
              visible: { field: "action_button", value: true },
              selector: { text: {} },
            },
            {
              name: "action_button_position",
              visible: { field: "action_button", value: true },
              selector: {
                select: {
                  mode: "box",
                  options: marked(
                    e,
                    ACTION_BUTTON_POSITIONS,
                    (value) => e[`action_button_position_${value}`],
                    DEFAULTS.action_button_position
                  ),
                },
              },
            },
            ...EDITOR_FIELDS.gestures("chart_tap_action_help"),
          ],
        },
      ],
      computeLabel: (schema) => schema.label || e[schema.name] || t[schema.name],
      computeHelper: (schema) => e[schema.helper || `${schema.name}_help`],
      assertConfig: (config) => TibberPricesChartCard.assertConfig(config),
    };
  }

  // The form of a view's panel (or the one for all views): its resolution and what it leaves
  // out; a view's fields left empty are as for all views
  static viewSchema(target, inherited = CHART_VIEW_DEFAULTS, defaults = CHART_VIEW_DEFAULTS) {
    const e = languageStrings(EDITOR_STRINGS);
    const own = target !== "all_views";
    const label = (value) => e[`resolution_${value}`];
    // A view: "as for all views" first (what that is, in brackets); all views: the default marked
    const resolutions = own
      ? [
          { value: CHART_INHERIT, label: fill(e.view_inherit_option, { value: label(inherited.resolution) }) },
          ...CHART_RESOLUTIONS.map((value) => ({ value, label: label(value) })),
        ]
      : marked(e, CHART_RESOLUTIONS, label, defaults.resolution);
    const schema = [
      {
        name: "resolution",
        required: true,
        selector: dropdown(resolutions),
      },
      {
        name: "hide",
        helper: own ? "view_inherit_help" : "chart_hide_help",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: CHART_HIDES.map((value) => ({ value, label: e.hide_option[value] })),
          },
        },
      },
    ];
    // When the top line shows the level and the gap: in a view "as for all views" first
    const shows = (name) =>
      own
        ? [
            {
              value: CHART_INHERIT,
              label: fill(e.view_inherit_option, { value: e[`chip_show_${inherited[name]}`] }),
            },
            ...CHART_CHIP_SHOWS.map((value) => ({ value, label: e[`chip_show_${value}`] })),
          ]
        : marked(e, CHART_CHIP_SHOWS, (value) => e[`chip_show_${value}`], defaults[name]);
    schema.push({
      name: "header_details",
      type: "expandable",
      flatten: true,
      icon: "mdi:tag-text-outline",
      schema: [
        { name: "header_level", required: true, selector: dropdown(shows("header_level")) },
        {
          name: "header_level_at",
          helper: own ? "view_inherit_help" : "header_level_at_help",
          selector: {
            select: {
              multiple: true,
              mode: "list",
              options: LEVEL_STEPS.map((value) => ({ value, label: languageStrings(STRINGS).levels[value] })),
            },
          },
        },
        { name: "header_delta", required: true, selector: dropdown(shows("header_delta")) },
        {
          name: "header_delta_from",
          helper: own ? "view_inherit_help" : "header_delta_from_help",
          selector: { number: { min: 0, max: 200, step: 1, mode: "box", unit_of_measurement: "%" } },
        },
      ],
    });
    return schema;
  }

  // The form above plus a table of own colors (HA's color selector shows an empty color as black
  // with its label on top of it)
  static async getConfigElement() {
    await loadEditors();
    return document.createElement("tibber-prices-chart-card-editor");
  }

  static getStubConfig(hass) {
    return { device_id: firstHomeDevice(hass), views: [...CHART_DEFAULT_VIEWS] };
  }

  static configDefaults() {
    return {
      ...CHART_DEFAULTS,
      units: { ...CHART_UNIT_PLACES },
      axis_title_x: false,
      axis_title_y: false,
      axis_decimals: "auto",
      grid_line_width: CHART_GRID_WIDTH,
      day_line_width: CHART_DAY_LINE_WIDTH,
      day_shade_strength: CHART_DAY_SHADE.strength,
      day_shade_width: CHART_DAY_SHADE.width,
      action_button: false,
      action_button_position: DEFAULTS.action_button_position,
      tap_opens: "nothing",
      window_width: DEFAULTS.window_width,
    };
  }
}
