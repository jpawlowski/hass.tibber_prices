/**
 * tibber-prices-forecast-card: the coming hours and parts of the day, shaped like a weather
 * forecast. Reads the `outlook_hours` / `outlook_day_parts` attributes of the Current
 * Electricity Price sensor; best/peak price periods come from the period binary sensors.
 */

import {
  HOUR_MS,
  LEVEL_COLORS,
  QUARTER_MS,
  aggregate,
  averageOf,
  barBaseline,
  capitalize,
  endTime,
  escapeHtml,
  fill,
  firstHomeDevice,
  fixedPriceFormat,
  formatPercent,
  homeEntities,
  levelColor,
  levelOfMany,
  lowerFirst,
  periodsTouching,
  priceFormatter,
  shownChange,
  shownPrice,
  storeValue,
  storedValue,
  timeRange,
} from "./util.js";
import {
  CHEVRON_LEFT,
  CHEVRON_RIGHT,
  CONTENT_PATH,
  FADE,
  GESTURE_TAP_PATH,
  MARK_COLORS,
  PERIOD_NUDGE,
  PERIOD_PATHS,
  REF_OFF_ICONS,
  TRACK_COLOR,
  arcPath,
  cardTitle,
  dialogHead,
  extremeIcon,
  keyboardInput,
  polar,
  svgIcon,
  trackKeyboard,
} from "./ui.js";
import { EDITOR_STRINGS, STRINGS, languageStrings, stringsFor } from "./strings.js";
import {
  ACTION_BUTTON_POSITIONS,
  DAYS_SHOWN,
  DEFAULTS,
  EDITOR_FIELDS,
  NOW_DECIMALS,
  SCROLL_BUTTONS,
  SECTIONS,
  SECTION_DEFAULTS,
  SECTION_HIDES,
  SECTION_ICONS,
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
import { REPEAT_MARKS, clockChange, dayBounds, homeCalendar, repeatMark, zoneOffset } from "./time.js";
import { STYLE } from "./styles.js";
import { TibberPricesCardBase, inCardWindow, loadEditors, validateWindowCards } from "./base.js";

function periodBadge(kind, title = "", style = "") {
  return `<span class="period-badge ${kind}"${title ? ` title="${title}"` : ""}${style ? ` style="${style}"` : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${PERIOD_PATHS[kind]}"${
    PERIOD_NUDGE[kind] ? ` transform="${PERIOD_NUDGE[kind]}"` : ""
  }></path></svg></span>`;
}

// Order of the legend: first how to read the graph (its shapes, the cut-off variant of a span,
// what their color means, the line across it), then the marks around it from top to bottom of
// a column (chip above the graph, low and high under the price, period line at the bottom)
const LEGEND_ORDER = [
  "bar",
  "span",
  "partial",
  "times",
  "level",
  "reference",
  "cut",
  "cheapest",
  "low",
  "high",
  "best",
  "peak",
  "best_now",
  "peak_now",
  "day_pointer",
  "day_now",
];
// Marks that belong to one section only; with both sections shown, the legend groups by section
// so the bar (hours) and the span (times of day) aren't mistaken for one another
const LEGEND_SECTION = {
  bar: "hours",
  span: "day_parts",
  partial: "day_parts",
  times: "day_parts",
  day_pointer: "days",
};
// Shared marks that start a row in the two-column legend, so pairs share a row: low beside
// high, best beside peak
const LEGEND_ROW_START = ["level", "low", "best", "best_now", "znow"];
// A detail card's legend: only what its chart shows, in this order
const DETAIL_LEGEND_ORDER = [
  "zbar",
  "level",
  "reference",
  "zref_off",
  "low",
  "high",
  "best",
  "peak",
  "best_now",
  "peak_now",
  "znow",
  "zpast",
  "zmissing",
  "times",
];

// Forecast cards attached to the page. HA attaches only the cards of the view on screen, so
// these are the cards of this dashboard tab: a legend explains what all of them show, since
// with one card per section usually only one of them shows the legend
const ATTACHED_CARDS = new Set();

// The part of a card's window that scrolls (below its header; see _showDialog)
const dialogScroll = (dialog) => dialog.querySelector(".dialog-scroll");

// The legend button of the section on screen (compact) or of the card
const OWN_LEGEND_BUTTON = ".panel:not(.inactive) .legend-button, ha-card:not(.is-compact) .legend-button";

// A day's low or high counts as passed half an hour after its quarter hour began: the quarter
// hour itself plus a little grace, so it doesn't fade the moment it's reached. The card redraws
// with each quarter-hour update, so it fades 30 to 45 minutes after the time shown
const EXTREME_PASSED_MS = 30 * 60 * 1000;

// At most this much height is given up to stay one grid row lower (half a row): spacing shrinks
// to at most half, graphs to at least 44 px. Beyond that the card takes the next row, so it
// never looks cramped
const MAX_SQUEEZE_PX = 32;

// A strip scrolled away from where it rests goes back there after this long without scrolling
// (not while a details window is open)
const STRIP_RETURN_MS = 10000;
// How long the mouse rests on an hour before the price steps to its neighbours show
const STEPS_DELAY_MS = 600;
// Half the width of such a step's percentage, for keeping it in sight
const STEPS_LABEL_HALF = 22;
// A price as the data has it: two decimals, as many more as it carries up to four (unrounded for
// all practical purposes). Used where small differences are the point and rounding would hide them
const EXACT_DECIMALS = [2, 4];

// A level as a dot in its color and its name, inside an element of `cls`
function levelTag(t, level, cls, tag = "span") {
  return `<${tag} class="${cls}"><span class="level-dot" style="background:${levelColor(level)}"></span>${
    t.levels[level] || level
  }</${tag}>`;
}

// The days' lows and highs falling into a stretch of time
function extremesIn(extremes, start, end) {
  return extremes.filter((x) => start <= x.at && x.at < end);
}

// "+12 %": how far a price lies from a base, in percent of the base, from the prices as shown
// ("" without a usable base)
function percentFrom(language, value, base, format, baseFormat = format) {
  const change = shownChange(value, base, format, baseFormat);
  return change === undefined ? "" : formatPercent(language, change, "always");
}

// A price difference with its sign, e.g. "+0,16 kr/kWh"
function signedPrice(format, unit, value) {
  return `${value > 0 ? "+" : value < 0 ? "\u2212" : "±"}${format(Math.abs(value))} ${unit}`;
}

// One day against another, as the words for it say: about the same within 1 %
function trendOf(change) {
  return Math.abs(change) < 0.01 ? "same" : change < 0 ? "cheaper" : "dearer";
}

// The day a block counts for: a night belongs to the day it ends on (22-06 is mostly the next
// day), so a day's parts run from its morning to its evening plus the night before
function dayOfBlock(dateOf, block) {
  return dateOf(block.part === "night" ? Date.parse(block.end) - 1 : Date.parse(block.start));
}

// Still to come, priced, and complete (a part cut off where the prices end doesn't compete)
function isAhead(block, now, key) {
  return Date.parse(block.end) > now && typeof block[key] === "number" && block.complete !== false;
}

function cheapestOf(blocks, key) {
  return blocks.reduce((best, b) => (!best || b[key] < best[key] ? b : best), undefined);
}

// How close (in % of the day's scale) the current price and the median of a day row count as one
// spot: their lines would overlap there (the parts of the day: NEAR_POINTERS_PX)
const NEAR_MEDIAN = 3;
// The least height a span of a part of the day is drawn at (px): a range of a few cents is still a
// span, not a dash
const SPAN_MIN_PX = 8;
// The graph's least height (px): 76 px less 12 px on a squeezed card
const GRAPH_MIN_PX = 64;
// The pointers of a span (current price, median) closer than this (px, taken at the graph's
// least height, so they never overlap there) count as one spot: their lines share the span's
// width, each on its own side
const NEAR_POINTERS_PX = 6;
// "25 min", "2.5 h", kept per language and unit
const DURATION_FORMATS = new Map();

function extremeLabel(t, format, unit, clock, kind, price, at) {
  return t.details.at
    .replace("{label}", t[`day_${kind}`])
    .replace("{price}", format(price))
    .replace("{unit}", unit)
    .replace("{time}", clock.format(new Date(at)));
}

// "Bestpreis-Zeitraum 13:30–15:00"
function periodLabel(t, clock, kind, start, end) {
  return `${t.details.period[kind]} ${timeRange(clock, start, end)}`;
}

// The marks as drawn in the strips, small, for the legend and details windows
const SWATCH = {
  bar: (color, cut = false) =>
    `<div class="graph"><div class="bar${cut ? " cut" : ""}" style="height:${cut ? 85 : 70}%;--c:${color}"></div></div>`,
  span: (color, partial = false) =>
    `<div class="graph${partial ? " partial" : ""}"><div class="span" style="bottom:15%;height:70%;--c:${color}"></div><div class="tick" style="bottom:45%"></div><div class="tick-line" style="bottom:45%"></div></div>`,
  ref: `<div class="graph"><div class="ref" style="bottom:50%"></div></div>`,
  chip: (text) => `<span class="chip">${text}</span>`,
  line: (kind) => `<span class="line" style="background:${MARK_COLORS[kind]}"></span>`,
  pointer: `<span class="mini-pointer"></span>`,
  now: `<span class="mini-now"></span>`,
  // A column of a detail card's chart: running now, past, or not known yet
  column: (kind) =>
    `<span class="mini-col ${kind}">${kind === "missing" ? "<span></span>" : `<span style="background:${LEVEL_COLORS.cheap}"></span>`}</span>`,
  extreme: (kind, passed = false) =>
    `<span class="extreme"><span class="${kind}${passed ? " passed" : ""}">${extremeIcon(kind)}</span></span>`,
};

// One line of the legend or details window: the mark, what it is, and what it means
function entryItem(swatch, title, text, extraClass = "") {
  return `<li class="entry${extraClass ? ` ${extraClass}` : ""}"><div class="swatch" aria-hidden="true">${swatch}</div><div><div class="entry-title">${title}</div>${
    text ? `<div class="entry-text">${text}</div>` : ""
  }</div></li>`;
}

/**
 * Where a strip's scale ends: at its highest price, unless a few blocks reach far above the
 * rest (a spike tomorrow). Then a quarter above the upper quartile of the blocks' tops, so the
 * others keep their shape; "far" means the highest reaches more than twice as high above the
 * bottom as that. Never below `floor` (the days' dashed lines stay on the scale)
 */
function scaleTop(tops, low, floor) {
  const sorted = tops.filter((v) => typeof v === "number").sort((a, b) => a - b);
  if (!sorted.length) return floor;
  const highest = sorted[sorted.length - 1];
  const quartile = sorted[Math.floor((sorted.length - 1) * 0.75)];
  const cap = Math.max(quartile + (quartile - low) * 0.25, floor);
  return highest - low > (cap - low) * 2 ? cap : Math.max(highest, floor);
}

// A line across a ring of `width` at `angle` (the gauge's average, the clock's hand)
function radialLine(center, radius, width, angle, attributes) {
  const [x0, y0] = polar(center, radius - width / 2 - 3, angle);
  const [x1, y1] = polar(center, radius + width / 2 + 3, angle);
  return `<line x1="${x0.toFixed(2)}" y1="${y0.toFixed(2)}" x2="${x1.toFixed(2)}" y2="${y1.toFixed(2)}" stroke-linecap="round" ${attributes}/>`;
}

// The best or peak price period running at `time`, and the next one after it ([start, end])
function periodAt(spans, time) {
  return spans.find(([start, end]) => start <= time && time < end);
}

function nextPeriod(spans, time) {
  return spans.filter(([start]) => start > time).sort((x, y) => x[0] - y[0])[0];
}

// The scale of "now": a 270° arc open at the bottom, so it reads as a scale (like HA's gauge
// card) and not as progress. It runs from the day's low to its high and is filled up to the
// current price, always a little, so the level's color shows even at the low. Shares are
// clamped to 0–1 by the caller
const GAUGE_FROM = -135;
const GAUGE_SPAN = 270;
const GAUGE_MIN_SHARE = 0.04;
function gaugeSvg({ share, mark, color, width = 8 }) {
  const end = GAUGE_FROM + GAUGE_SPAN * Math.max(GAUGE_MIN_SHARE, share);
  // The day's average across the arc: what makes the fill mean "below" or "above"
  const tick =
    typeof mark === "number"
      ? radialLine(
          50,
          40,
          width,
          GAUGE_FROM + GAUGE_SPAN * mark,
          'stroke="var(--primary-text-color, #212121)" stroke-opacity="0.55" stroke-width="1.6"'
        )
      : "";
  return `<svg viewBox="0 0 100 100" aria-hidden="true" focusable="false"><path d="${arcPath(50, 40, GAUGE_FROM, GAUGE_FROM + GAUGE_SPAN)}" fill="none" stroke="${TRACK_COLOR}" stroke-width="${width}" stroke-linecap="round"/><path d="${arcPath(50, 40, GAUGE_FROM, end)}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round"/>${tick}</svg>`;
}

export class TibberPricesForecastCard extends TibberPricesCardBase {
  // The chart card, from the icon top right
  static windowCards = [{ key: "chart", when: (config) => Boolean(config.chart_button) }];

  // Errors for config values the card can't use; setConfig and the visual editor check the same
  static assertConfig(config) {
    validateConfig(config);
    validateWindowCards(config);
  }

  setConfig(config) {
    TibberPricesCardBase.requireHome(config);
    TibberPricesForecastCard.assertConfig(config);
    this._config = { ...DEFAULTS, ...config };
    if (!Array.isArray(this._config.show) || !this._config.show.length) this._config.show = [...SECTIONS];
    // Each section's options, defaults filled in
    this._sections = Object.fromEntries(
      SECTIONS.map((section) => [section, { hide: [], ...SECTION_DEFAULTS[section], ...config[section] }])
    );
    // Compact layout: the section picked last, remembered per browser, home and set of sections,
    // so several compact cards of one home with different sections don't override each other
    this._storageKey = `tibber-prices-forecast:${config.device_id}:${[...this._config.show].sort().join(",")}`;
    this._view = storedValue(this._storageKey);
    this._configApplied();
  }

  // HA sets this in edit mode, where a card hidden until tomorrow's prices shows its placeholder
  set preview(value) {
    if (Boolean(value) === Boolean(this._preview)) return;
    this._preview = value;
    if (this._config && this._hass) this._scheduleRender();
  }

  get preview() {
    return this._preview;
  }

  getCardSize() {
    if (!this._config) return 3;
    const rows = this._config.layout === "compact" ? 1 : this._config.show.length;
    return 1 + rows * 2;
  }

  // Full width by default; never narrower than half a section (in precise mode as well), and
  // never lower than the compact or detailed content needs when a fixed height is set
  getGridOptions() {
    const compact = this._config && this._config.layout === "compact";
    return { columns: "full", min_columns: 6, min_rows: compact ? 4 : 6 };
  }

  // Visual editor: HA draws the form from this schema with its own selectors
  static getConfigForm() {
    const e = languageStrings(EDITOR_STRINGS);
    const t = languageStrings(STRINGS);
    // A section's own options, in its own panel (nested in YAML under the section's name)
    const section = (name, schema) => ({
      name,
      type: "expandable",
      icon: SECTION_ICONS[name],
      schema: [
        ...schema,
        EDITOR_FIELDS.nowDecimals(e),
        {
          name: "hide",
          selector: {
            select: {
              multiple: true,
              mode: "list",
              options: SECTION_HIDES[name].map((value) => ({ value, label: e.hide_option[value] })),
            },
          },
        },
        { name: "hide_details", selector: { boolean: {} } },
      ],
    });
    return {
      // Like HA's own cards: the home on top, everything else in panels
      schema: [
        EDITOR_FIELDS.device(),
        {
          name: "content",
          type: "expandable",
          flatten: true,
          iconPath: CONTENT_PATH,
          schema: [
            // A title inside the card, top left like HA's own cards (its standard one unless set)
            { name: "show_title", selector: { boolean: {} } },
            { name: "title", visible: { field: "show_title", value: true }, selector: { text: {} } },
            {
              name: "show",
              selector: {
                select: {
                  multiple: true,
                  reorder: true,
                  options: SECTIONS.map((value) => ({ value, label: t[value] })),
                },
              },
            },
            {
              name: "layout",
              required: true,
              selector: {
                select: {
                  mode: "box",
                  options: marked(e, ["detailed", "compact"], (value) => e[value], DEFAULTS.layout),
                },
              },
            },
            EDITOR_FIELDS.priceUnit(e),
            EDITOR_FIELDS.priceSource(e),
            EDITOR_FIELDS.average(e),
            EDITOR_FIELDS.appearance(e),
            {
              name: "scroll_buttons",
              selector: dropdown(
                marked(e, SCROLL_BUTTONS, (value) => e[`scroll_buttons_${value}`], DEFAULTS.scroll_buttons)
              ),
            },
            // Several cards for one home, each with its own sections: one legend and unit are enough
            {
              name: "",
              type: "grid",
              schema: [
                { name: "hide_legend", selector: { boolean: {} } },
                { name: "hide_unit", selector: { boolean: {} } },
              ],
            },
          ],
        },
        section("now", []),
        section("hours", []),
        section("day_parts", []),
        section("days", [
          {
            name: "shown",
            selector: dropdown(marked(e, DAYS_SHOWN, (value) => e[`shown_${value}`], SECTION_DEFAULTS.days.shown)),
          },
          {
            name: "tomorrow_pending",
            // Only tomorrow has to wait for its prices
            visible: { field: "shown", operator: "not_eq", value: "today" },
            selector: dropdown(
              marked(
                e,
                TOMORROW_PENDING,
                (value) => e[`tomorrow_pending_${value}`],
                SECTION_DEFAULTS.days.tomorrow_pending
              )
            ),
          },
        ]),
        {
          name: "interactions",
          type: "expandable",
          flatten: true,
          iconPath: GESTURE_TAP_PATH,
          schema: [
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
            ...EDITOR_FIELDS.chartButton(),
            { ...EDITOR_FIELDS.windowWidth(e), visible: { field: "chart_button", value: true } },
            ...EDITOR_FIELDS.gestures(),
          ],
        },
      ],
      // Section panels are named like the sections on the card
      computeLabel: (schema) => e[schema.name] || t[schema.name],
      computeHelper: (schema) => e[`${schema.name}_help`],
      assertConfig: (config) => TibberPricesForecastCard.assertConfig(config),
    };
  }

  /**
   * The icon top right opening the chart card in a window, where set (not on a card in another
   * card's window). On the now card's tile in the middle of its row
   */
  _updateChartButton(card) {
    const button = this.shadowRoot.querySelector(".chart-open");
    const shown = Boolean(this._config.chart_button) && this._opens("chart");
    button.hidden = !shown;
    card.classList.toggle("has-chart-button", shown);
    if (!shown) return;
    const label = stringsFor(this._hass).chart.open;
    button.setAttribute("aria-label", label);
    button.title = label;
    const icon = this._config.chart_icon || DEFAULTS.chart_icon;
    if (button.dataset.icon !== icon) {
      button.dataset.icon = icon;
      button.innerHTML = `<ha-icon icon="${escapeHtml(icon)}"></ha-icon>`;
    }
  }

  // Preselected in the card picker: the first home with a price outlook
  static getStubConfig(hass) {
    return { device_id: firstHomeDevice(hass), show: [...SECTIONS] };
  }

  // HA's form for the options, showing what applies where nothing is set (see the editor)
  static async getConfigElement() {
    await loadEditors();
    return document.createElement("tibber-prices-forecast-card-editor");
  }

  // What applies where the config sets nothing, as the editor shows it
  static configDefaults() {
    return {
      ...DEFAULTS,
      show: [...SECTIONS],
      ...Object.fromEntries(SECTIONS.map((section) => [section, { hide: [], ...SECTION_DEFAULTS[section] }])),
    };
  }

  _render() {
    if (!this._config || !this._hass) return;
    this._legendShows = undefined;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      // The legend dialog sits beside the card, not in it: re-rendering the card on a price
      // update leaves an open legend alone, and taps in it never reach the card's actions
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card></ha-card><button type="button" class="chart-open" hidden></button><dialog aria-labelledby="legend-title"></dialog>`;
      this._bindActions(this.shadowRoot.querySelector("ha-card"));
      // The chart card in a window: beside the card, so a redraw leaves it be, and its tap never
      // runs the card's action
      const chartButton = this.shadowRoot.querySelector(".chart-open");
      chartButton.addEventListener("click", () => this._openInWindow("chart", chartButton));
      this._bindLegend(this.shadowRoot.querySelector("dialog"));
      trackKeyboard(this);
    }
    const card = this.shadowRoot.querySelector("ha-card");
    this._updateInteractive(card);
    this._updateChartButton(card);
    card.classList.toggle("is-compact", this._config.layout === "compact");
    const buttons = this._config.scroll_buttons;
    card.classList.toggle("no-scroll-back", buttons === "forward" || buttons === "none");
    card.classList.toggle("no-scroll-forward", buttons === "back" || buttons === "none");
    card.classList.toggle(
      "column-details",
      this._config.show.some((section) => this._tapDetails(section))
    );
    const t = stringsFor(this._hass);
    const entities = this._entities || homeEntities(this._hass, this._config);
    const stateObj = priceState(this._hass, entities.price && this._hass.states[entities.price], this._priceSource());
    if (!stateObj) {
      this._setHidden(false);
      card.innerHTML = `<div class="empty">${t.no_data}</div>`;
      return;
    }
    const { factor, unit } = priceUnit(stateObj, this._config.price_unit);
    const hours = scalePrices(stateObj.attributes.outlook_hours || [], factor);
    const allParts = scalePrices(stateObj.attributes.outlook_day_parts || [], factor);
    const days = scalePrices(stateObj.attributes.outlook_days || [], factor);
    if (!hours.length && !allParts.length && !days.length) {
      this._setHidden(false);
      card.innerHTML = `<div class="empty">${t.no_data}</div>`;
      return;
    }

    const periods = homePeriods(this._hass, entities, stateObj);
    const now = Date.now();
    const { zone, dateOf, weekday, clock, clockLong, hourName: hourNumber, hourTag } = homeCalendar(this._hass);
    const today = dateOf(now);
    const yesterday = dateOf(dayBounds(today, zone)[0] - 1);
    // The parts of the day reach back as far as the hours (scroll back to see them); four show at
    // a time, from the one before the running one, like the hours
    const parts = allParts;
    // "Tomorrow · Saturday" above the first block of the next day, in both strips, at a divider.
    // Either word can be left out (the section's hide); the divider stays. With `everyDay`, every
    // day the strip reaches is named, the first one too (without a divider before it): like a
    // calendar's headings, the name of the day in view stays at the strip's left edge
    // (see _stickDayNames). Otherwise only tomorrow is
    const naming = (name, nowLabel, section, everyDay = false) => {
      const hide = this._sections[section].hide;
      let tomorrowShown = false;
      let previous;
      return (block, current) => {
        let day = "";
        let dayHtml = "";
        let newDay = false;
        let divider = false;
        // The block running now is today's, even a night that began yesterday (as for its
        // dashed line); others belong to the day they begin on
        const at = current ? now : Date.parse(block.start);
        const date = dateOf(at);
        const changed = everyDay ? date !== previous : !tomorrowShown && date > today;
        divider = changed && (!everyDay || previous !== undefined);
        previous = date;
        if (changed) {
          // A day before yesterday (the night that began then) has no word of its own: its weekday
          // names it, also where the weekdays are left out
          const word = date > today ? t.tomorrow : date === today ? t.today : date === yesterday ? t.yesterday : "";
          const words = [
            !hide.includes("tomorrow") && word,
            (!hide.includes("weekday") || !word) && weekday.format(new Date(at)),
          ].filter(Boolean);
          day = words.join(" · ");
          // Drawn with each word in a span: a narrow card stacks them, centered
          dayHtml = words.map((part) => `<span>${part}</span>`).join('<span class="label-sep"> · </span>');
          newDay = true;
          if (date > today) tomorrowShown = true;
        }
        // A day label of today (or later) stays fully visible over a past block: the day it names
        // is still running
        return {
          day,
          dayHtml,
          newDay,
          divider,
          ongoing: newDay && date >= today,
          name: current && nowLabel ? t.now : name(block),
        };
      };
    };
    const averageKind = averageKindOf(this._config, days);
    const average = averageOf(t, averageKind);
    // Now: the price of the hour running now, until the price sensor's own value is read below
    const currentHour = hours.find((b) => Date.parse(b.start) <= now && now < Date.parse(b.end));
    let nowPrice = currentHour ? currentHour[average.key] : undefined;
    // The day's average of the same kind by date: drawn as a dashed line, so every hour and part
    // of the day reads as above or below its day
    const references = dayReferences(stateObj, factor, days, average.key);
    // When each day's lowest and highest price occur, marked under the hour / part they fall in
    const extremes = days
      .flatMap((d) => [
        d.price_min_at && { at: Date.parse(d.price_min_at), kind: "low", price: d.price_min },
        d.price_max_at && { at: Date.parse(d.price_max_at), kind: "high", price: d.price_max },
      ])
      .filter(Boolean);
    // Facts behind each column and day row, for their details windows (indexed by data-detail
    // and data-day), and what all of them share
    this._details = [];
    // Each column's details by kind and start, for opening them from elsewhere (an hour in a
    // part's chart, the way back)
    this._detailIndex = new Map();
    this._dayDetails = [];
    // The views a detail was opened from, for the way back (and Escape) to lead there: kept
    // over redraws (new prices while a detail is open), emptied when the window closes
    if (!this._detailBack) this._detailBack = [];
    // Every quarter hour from last night on, for zooming into a time in its details
    const quarters = quarterSeries(stateObj, factor);
    // The quarter hour running now: its own price, the next one's, and where it ranks among
    // today's quarter hours, for "now" in the details
    let currentQuarter;
    const quarterIndex = quarters ? Math.floor((now - quarters.start) / quarters.step) : -1;
    if (quarters && typeof quarters.prices[quarterIndex] === "number") {
      const price = quarters.prices[quarterIndex];
      const [dayStart, dayEnd] = dayBounds(today, zone);
      const todays = quarters.prices.filter((value, i) => {
        const at = quarters.start + i * quarters.step;
        return typeof value === "number" && dayStart <= at && at < dayEnd;
      });
      const next = quarters.prices[quarterIndex + 1];
      currentQuarter = {
        price,
        level: quarters.levels[quarterIndex],
        end: quarters.start + (quarterIndex + 1) * quarters.step,
        next: typeof next === "number" ? next : undefined,
        // Shares of today's quarter hours that cost less and more than now
        cheaper: todays.filter((value) => value < price).length / todays.length,
        dearer: todays.filter((value) => value > price).length / todays.length,
      };
    }
    const inUnit = (value) => (typeof value === "number" ? value * factor : undefined);
    // The current price exactly as the price sensor shows it: its own value, with the decimals
    // set for it in Home Assistant (the user's choice, else the integration's; in the other unit
    // than the sensor's, two places more or fewer), unless a section sets its own
    const sensorPrice = Number.parseFloat(stateObj.state);
    if (currentQuarter && Number.isFinite(sensorPrice)) currentQuarter.price = sensorPrice * factor;
    // The blue marks (on today's span, beside the part of the day running now) show this same
    // current price: the one "Now" leads with in its details
    if (Number.isFinite(sensorPrice)) nowPrice = sensorPrice * factor;
    const registryEntry = this._hass.entities && this._hass.entities[entities.price];
    const precision = registryEntry && registryEntry.display_precision;
    const entityPlaces =
      typeof precision === "number" ? Math.max(0, precision + (factor > 1 ? -2 : factor < 1 ? 2 : 0)) : undefined;
    // The current price as the section shows it (its own decimals), else `fallback`
    const formatNowFor = (section, fallback) => {
      const set = String(this._sections[section].now_decimals);
      const places = NOW_DECIMALS.includes(set) && set !== "entity" ? Number(set) : entityPlaces;
      return places === undefined ? fallback : fixedPriceFormat(this._hass, places);
    };
    this._renderInfo = {
      t,
      unit,
      clock: clockLong,
      zone,
      averageKind,
      average,
      now,
      nowPrice,
      periods,
      hours,
      parts,
      dateOf,
      days,
      today,
      extremes,
      quarters,
      hourName: hourNumber,
      hourTag,
      weekdayOf: (time) => weekday.format(new Date(time)),
      // A time, with its weekday when it isn't today ("Sunday 02:00")
      at: (time) => (dateOf(time) === today ? "" : `${weekday.format(new Date(time))} `) + clock.format(new Date(time)),
      currentQuarter,
      formatNowFor,
      // What the price now is made of (the price sensor's attributes)
      priceParts: { energy: inUnit(stateObj.attributes.energy_price), tax: inUnit(stateObj.attributes.tax) },
    };
    this._dayPartHours = stateObj.attributes.outlook_day_part_hours || {};
    // A best or peak price period running right now (best first, should both overlap)
    const running = ["best", "peak"]
      .map((kind) => ({ kind, span: periodAt(periods[kind], now) }))
      .find((entry) => entry.span);
    this._renderInfo.activePeriod = running && {
      kind: running.kind,
      title: periodLabel(t, clockLong, running.kind, running.span[0], running.span[1]),
    };
    const context = { t, periods, now, nowPrice, today, unit, references, average, dateOf, extremes, clock, clockLong };
    this._averageKind = averageKind;
    // What this card shows in its strips (all sections of a compact card), for the legends of
    // the other cards on the tab
    this._legendShows = { sections: [], marks: [] };
    const hourName = (block) => hourTag(Date.parse(block.start));
    // The hours' strip, built once: also where it isn't drawn, as "now" opens the details of the
    // hour running now
    let hoursHtml;
    const hoursStrip = () => {
      if (hoursHtml === undefined)
        hoursHtml = this._strip(hours, "hours", naming(hourName, true, "hours", true), context);
      return hoursHtml;
    };
    if (this._renderStandalone(card, hoursStrip)) return;

    // Built once, as it collects the rows' details: empty when none of the days set is shown
    const daysSection = this._config.show.includes("days") ? this._days(days, context) : "";
    const available = { now: currentQuarter, hours: hours.length, day_parts: parts.length, days: daysSection };
    // In the order set in show (the editor lets the sections be dragged), each once
    const show = [...new Set(this._config.show)].filter((row) => available[row]);
    // Nothing left to show (only tomorrow, hidden until its prices are in): like HA's own cards
    // with nothing to show, the card leaves the dashboard until there is
    this._setHidden(!show.length);
    if (!show.length) {
      card.innerHTML = "";
      return;
    }
    // "Now": the hours' details first, which it opens
    let nowHtml = "";
    if (show.includes("now")) {
      hoursStrip();
      nowHtml = this._nowHtml("header");
    }
    const stripOf = {
      hours: hoursStrip,
      day_parts: () =>
        this._strip(
          parts,
          "parts",
          naming((block) => t[block.part] || block.part, false, "day_parts", true),
          context
        ),
    };
    // The card's own action button (optional), at the top or the bottom of the card
    const actionHtml =
      this._config.action_button && this._hasAction()
        ? `<button class="action-button" data-card-action>${this._actionText(t)} ›</button>`
        : "";
    const actionPosition = this._config.action_button_position;
    let actionPlaced = false;
    // The footer follows the last strip: its legend explains the strips. The days, set apart by
    // a divider, take their place in the order; with the days alone, the footer closes
    const compose = (sections) => {
      const stripRows = sections.filter((row) => stripOf[row]);
      const lastStrip = stripRows[stripRows.length - 1];
      // Visual order in the narrow layout, where strips, footer and days are items of one column.
      // The footer follows the last strip (and "now" right after it, which belongs to the strips);
      // without strips it comes last
      const positions = [...sections];
      let footerAt = positions.length;
      if (lastStrip) {
        footerAt = positions.indexOf(lastStrip) + 1;
        if (positions[footerAt] === "now") footerAt += 1;
      }
      positions.splice(footerAt, 0, "footer");
      const order = Object.fromEntries(positions.map((row, i) => [row, i]));
      const stripItems = stripRows.map((row) => [
        order[row],
        stripOf[row]().replace('<div class="strip-wrap"', `<div class="strip-wrap" style="order:${order[row]}"`),
      ]);
      const strips = stripItems.map(([, html]) => html).join("");
      // The legend explains only what these strips actually show (a low can lie outside both)
      const marks = [];
      if (strips) marks.push("level");
      if (sections.includes("hours")) marks.push("bar");
      if (sections.includes("day_parts")) marks.push("span");
      if (strips.includes('class="ref"')) marks.push("reference");
      if (strips.includes('class="chip"')) marks.push("cheapest");
      marks.push(...["best", "peak"].filter((kind) => strips.includes(`data-${kind}`)));
      marks.push(
        ...["best", "peak"].filter((kind) => strips.includes(`period-badge ${kind}`)).map((kind) => `${kind}_now`)
      );
      if (strips.includes('class="low"')) marks.push("low");
      if (strips.includes('class="high"')) marks.push("high");
      if (strips.includes(" partial")) marks.push("partial");
      if (strips.includes(' cut"')) marks.push("cut");
      if (strips.includes('class="tick-now"')) marks.push("day_now");
      if (sections.includes("day_parts")) marks.push("times");
      const daysHtml = sections.includes("days") ? daysSection : "";
      // The days' marks, as far as drawn (not for tomorrow's placeholder alone): the median
      // pointer, and on today's span the hour running now
      const dayRows = daysHtml.includes('class="day-span"');
      if (dayRows) {
        if (!marks.includes("level")) marks.push("level");
        if (daysHtml.includes('class="day-tick"')) marks.push("day_pointer");
        if (daysHtml.includes('class="day-now"') && !marks.includes("day_now")) marks.push("day_now");
        for (const kind of ["best", "peak"]) {
          if (daysHtml.includes(`period-badge ${kind}`) && !marks.includes(`${kind}_now`)) marks.push(`${kind}_now`);
        }
      }
      const legendSections = dayRows ? [...stripRows, "days"] : stripRows;
      this._legendShows.sections.push(...legendSections);
      this._legendShows.marks.push(...marks);
      const button =
        marks.length && !this._config.hide_legend
          ? `<button class="legend-button" data-legend="${marks.join(" ")}" data-sections="${legendSections.join(" ")}" aria-haspopup="dialog"><ha-icon icon="mdi:information-outline"></ha-icon><span>${t.legend.title}</span></button>`
          : "";
      // Without legend button and unit (both can be hidden, e.g. when another card shows them),
      // there's no footer at all
      const unitHtml = this._config.hide_unit ? "" : `<span class="unit">${unit}</span>`;
      const daysIndex = sections.indexOf("days");
      // At the bottom, the button joins the footer while that is the last line (no days after the
      // strips); otherwise it gets a line of its own at the card's end
      const footerLast = daysIndex < 0 || !strips || daysIndex < sections.indexOf(lastStrip);
      const inFooter = actionPosition === "bottom" && footerLast && actionHtml;
      if (inFooter) actionPlaced = true;
      const footerAction = inFooter ? actionHtml : "";
      const footer =
        button || unitHtml || footerAction
          ? `<div class="footer"${strips ? ` style="order:${order.footer}"` : ""}>${button}${unitHtml}${footerAction}</div>`
          : "";
      // "Now" where it is in the order
      const nowIndex = sections.indexOf("now");
      const nowItem =
        nowIndex < 0 ? undefined : [order.now, `<div class="now-row" style="order:${order.now}">${nowHtml}</div>`];
      const inOrder = (items) =>
        items
          .filter(Boolean)
          .sort((a, b) => a[0] - b[0])
          .map(([, html]) => html)
          .join("");
      const footerItem = footer && (strips || daysHtml) ? [order.footer, footer] : undefined;
      if (strips && daysHtml) {
        const rows = sections.filter((row) => row !== "now");
        const index = rows.indexOf("days");
        const neighbours = `${index > 0 ? " after" : ""}${index < rows.length - 1 ? " before" : ""}`;
        // Between the sections it joins the strips' column; first or last it spans the card
        const inside = nowItem && nowIndex > 0 && nowIndex < sections.length - 1;
        const split = `<div class="split${index === 0 ? " days-first" : ""}"><div class="main">${inOrder([
          ...stripItems,
          footerItem,
          inside && nowItem,
        ])}</div><div class="side${neighbours}" style="--order:${order.days}">${daysHtml}</div></div>`;
        if (!nowItem || inside) return split;
        return nowIndex === 0 ? nowItem[1] + split : split + nowItem[1];
      }
      return inOrder([...stripItems, daysHtml && [order.days, daysHtml], footerItem, nowItem]);
    };

    // The card's own title, top left like HA's card headers: in the row of the compact switch or
    // of a top action button when there is one
    const titleHtml = this._config.show_title ? `<h1 class="card-title">${cardTitle(this._config, t)}</h1>` : "";
    // The compact layout's tabs: every section but "now", which stays in view above or below them
    const body = show.filter((row) => row !== "now");
    // The compact layout's switch row holds the title and a top action button
    const inSwitch = this._config.layout === "compact" && body.length > 1;
    let html;
    if (inSwitch) {
      // All sections are laid out in one grid cell and only the picked one is visible: the card
      // keeps the height of the tallest, so switching never moves the dashboard
      const view = body.includes(this._view) ? this._view : body[0];
      const head = actionPosition === "top" ? actionHtml : "";
      if (head) actionPlaced = true;
      // "Now" stays in view: above the tabs when it comes first, else below them
      const nowRow = nowHtml && `<div class="now-row">${nowHtml}</div>`;
      const [nowAbove, nowBelow] = show.indexOf("now") === 0 ? [nowRow, ""] : ["", nowRow];
      html = `<div class="switch">${titleHtml}${head}<div role="group">${body
        .map(
          (row) =>
            `<button data-view="${row}" class="${row === view ? "active" : ""}" aria-pressed="${row === view}" aria-label="${t[row]}"><ha-icon icon="${SECTION_ICONS[row]}"></ha-icon><span class="label">${t[row]}</span></button>`
        )
        .join("")}</div></div>${nowAbove}<div class="panels">${body
        .map((row) => `<div class="panel${row === view ? "" : " inactive"}">${compose([row])}</div>`)
        .join("")}</div>${nowBelow}`;
    } else {
      html = compose(show);
    }
    const headTitle = inSwitch ? "" : titleHtml;
    const headAction = actionHtml && !actionPlaced && actionPosition === "top" ? actionHtml : "";
    if (headTitle || headAction) html = `<div class="card-head">${headTitle}${headAction}</div>${html}`;
    if (actionHtml && !actionPlaced && actionPosition !== "top")
      html = `${html}<div class="card-foot">${actionHtml}</div>`;
    // Columns opening their details make the card's surface a mouse-only target for its action:
    // keyboard and screen reader users get it as a button that shows when focused
    if (this._focusActionNeeded()) {
      html = `<button class="action-button focus-only" data-card-action>${this._actionText(t)}</button>${html}`;
    }
    card.innerHTML = html;
    this._refreshDetail();
    card.querySelectorAll(".strip").forEach((strip) =>
      strip.addEventListener("scroll", () => {
        this._fade(strip);
        this._stripScrolled(strip);
      })
    );
    // (Not when left out in the hours' panel)
    if (this._stepsOnHover()) {
      card.querySelectorAll(".strip.hours").forEach((strip) => this._bindSteps(strip));
    }
    this._fadeAll();
  }

  // Whether price steps show on hovering. Left out in the hours' panel: nowhere, neither in the
  // strip nor in the details, where picking a quarter hour still shows its own
  _stepsOnHover() {
    return !this._sections.hours.hide.includes("steps");
  }

  /**
   * Hovering an hour (or focusing it by keyboard): arrows in the direction of time, from the top
   * of the bar before into its bar and from its bar to the one after, each with the price change
   * in percent of the earlier price (so an arrow reads the same from both its hours). Only then, so the strip itself stays calm; not on touch,
   * where a tap opens the details. The same in a detail card's chart (`column` and `bar` name
   * its elements; its columns carry their price as data-value too)
   */
  _bindSteps(strip, { column: columnSelector = ".col", bar: barSelector = ".bar", hover = true } = {}) {
    // The hour shown (or waiting to show), the timer of the wait, the last mouse position, and
    // the column whose arrows stay (a picked quarter hour)
    let hovered;
    let timer;
    let last;
    let pinned;
    // Fades the arrows out (and drops any still waiting to show)
    const hide = () => {
      clearTimeout(timer);
      hovered = undefined;
      strip.classList.remove("has-steps");
      for (const svg of strip.querySelectorAll(".steps:not(.is-leaving)")) {
        svg.classList.remove("is-shown");
        svg.classList.add("is-leaving");
        setTimeout(() => svg.remove(), 200);
      }
    };
    const show = (column) => {
      // (The card may have been redrawn meanwhile: this strip is gone)
      if (!strip.isConnected) return;
      const bar = column && column.querySelector(barSelector);
      const value = column && Number(column.dataset.value);
      if (!bar || !Number.isFinite(value)) return;
      const box = strip.getBoundingClientRect();
      const topOf = (element) => {
        const rect = element.getBoundingClientRect();
        return { x: rect.left + rect.width / 2 - box.left + strip.scrollLeft, y: rect.top - box.top + strip.scrollTop };
      };
      const from = topOf(bar);
      const language = this._hass.language;
      // What shows of the strip, in its own coordinates: clear of a scroll button, or of most
      // of the faded edge, where there's more beyond it
      const wrap = strip.parentElement;
      const fade = Math.min(Math.max(wrap.clientWidth * FADE.share, FADE.min), FADE.max) / 2;
      const edge = (side) => {
        const button = wrap.querySelector(`.scroll.${side === "left" ? "back" : "forward"}`);
        if (button && getComputedStyle(button).display !== "none") {
          const rect = button.getBoundingClientRect();
          return side === "left" ? rect.right - box.left + 6 : box.right - rect.left + 6;
        }
        return strip.classList.contains(side === "left" ? "has-more-left" : "has-more-right") ? fade : 0;
      };
      const shownFrom = strip.scrollLeft + edge("left");
      const shownTo = strip.scrollLeft + strip.clientWidth - edge("right");
      // In the direction of time: from the hour before into this one, and from this one into the
      // next; each the change in percent of the earlier price. A neighbour out of
      // sight: the arrow still points its way, cut off where the strip stops showing
      const arrows = [
        [column.previousElementSibling, false],
        [column.nextElementSibling, true],
      ]
        .map(([neighbour, forward]) => {
          const target = neighbour && neighbour.querySelector(barSelector);
          const other = neighbour && Number(neighbour.dataset.value);
          if (!target || !Number.isFinite(other)) return "";
          const there = topOf(target);
          const [tail, tip] = forward ? [from, there] : [there, from];
          // Lifted a little above the tops, shortened at both ends, the tip on a bar's top
          const [x0, y0, x1, y1] = [tail.x, tail.y - 4, tip.x, tip.y - 4];
          const length = Math.hypot(x1 - x0, y1 - y0) || 1;
          const [ux, uy] = [(x1 - x0) / length, (y1 - y0) / length];
          let start = [x0 + ux * 6, y0 + uy * 6];
          let end = [x1 - ux * 6, y1 - uy * 6];
          const at = (x) => [x, y0 + ((x - x0) / (x1 - x0 || 1)) * (y1 - y0)];
          if (start[0] < shownFrom) start = at(shownFrom);
          if (end[0] > shownTo) end = at(shownTo);
          // No room for a readable arrow (the hovered hour itself at the edge): left out rather
          // than a stub lying on the other arrow
          if (end[0] - start[0] < 16) return "";
          // The change from the earlier price to the later one, in percent of the earlier (the
          // arrow's tail): one number per arrow, whichever of its two hours is hovered
          const [earlier, later] = forward ? [value, other] : [other, value];
          const change = earlier > 0 ? later / earlier - 1 : undefined;
          const kind = change === undefined || Math.abs(change) < 0.005 ? "same" : change > 0 ? "up" : "down";
          const head = [
            [end[0] - ux * 6 - uy * 3.5, end[1] - uy * 6 + ux * 3.5],
            [end[0] - ux * 6 + uy * 3.5, end[1] - uy * 6 - ux * 3.5],
          ];
          return {
            kind,
            start,
            end,
            head,
            // (No change: "±0 %" rather than a sign it doesn't have)
            text:
              change === undefined
                ? ""
                : kind === "same"
                  ? `±${formatPercent(language, 0, "never")}`
                  : formatPercent(language, change, "always"),
            // Over the middle of what shows of the arrow, whole in sight
            x: Math.min(Math.max((start[0] + end[0]) / 2, shownFrom + STEPS_LABEL_HALF), shownTo - STEPS_LABEL_HALF),
            y: Math.min(start[1], end[1]) - 6,
          };
        })
        .filter(Boolean);
      // Both numbers pushed to one edge: side by side, in the order of the arrows; with no room
      // for that, the later one above
      const [before, after] = arrows.length === 2 ? arrows : [];
      if (before && after && after.x - before.x < 2 * STEPS_LABEL_HALF + 4) {
        const middle = Math.min(
          Math.max((before.x + after.x) / 2, shownFrom + 2 * STEPS_LABEL_HALF + 2),
          shownTo - 2 * STEPS_LABEL_HALF - 2
        );
        before.x = middle - STEPS_LABEL_HALF - 2;
        after.x = middle + STEPS_LABEL_HALF + 2;
        if (shownTo - shownFrom < 4 * STEPS_LABEL_HALF + 4) {
          after.x = before.x = (shownFrom + shownTo) / 2;
          after.y = Math.min(before.y, after.y) - 15;
        }
      }
      const svgArrows = arrows
        .map(
          (a) =>
            `<g class="${a.kind}"><line x1="${a.start[0]}" y1="${a.start[1]}" x2="${a.end[0]}" y2="${a.end[1]}"></line><path d="M${a.end[0]} ${a.end[1]}L${a.head[0][0]} ${a.head[0][1]}L${a.head[1][0]} ${a.head[1][1]}Z"></path>${
              a.text ? `<text x="${a.x}" y="${a.y}">${a.text}</text>` : ""
            }</g>`
        )
        .join("");
      if (!svgArrows) return;
      strip.insertAdjacentHTML(
        "beforeend",
        `<svg class="steps" aria-hidden="true" width="${strip.scrollWidth}" height="${strip.scrollHeight}">${svgArrows}</svg>`
      );
      // Faded in (the class on the next frame, so the transition runs)
      const svg = strip.lastElementChild;
      strip.classList.add("has-steps");
      requestAnimationFrame(() => svg.classList.add("is-shown"));
    };
    // Only once the mouse rests on an hour, like a tooltip: passing over the strip stays calm
    const later = (column, delay) => {
      // (Arrows pinned to a picked column stay, whatever else the mouse passes; with the steps
      // left out on hovering, only a pick shows them)
      if (!hover || pinned || column === hovered) return;
      hide();
      hovered = column;
      timer = setTimeout(() => show(column), delay);
    };
    strip.addEventListener("pointerover", (event) => {
      if (event.pointerType !== "mouse") return;
      // Not when the strip moved under a resting mouse (gliding back home): only a moving mouse
      // picks another hour
      if (last && event.clientX === last.x && event.clientY === last.y) return;
      last = { x: event.clientX, y: event.clientY };
      later(event.target.closest(columnSelector), STEPS_DELAY_MS);
    });
    const leave = () => {
      if (!pinned) hide();
    };
    strip.addEventListener("pointerleave", leave);
    // By keyboard only: after a tap, the focus coming back from a closed window leaves them off
    strip.addEventListener("focusin", (event) => {
      if (keyboardInput) later(event.target.closest(columnSelector), 0);
    });
    strip.addEventListener("focusout", leave);
    return {
      // Keeps a column's arrows shown (undefined: back to showing them on hovering)
      pin: (column) => {
        pinned = column;
        hide();
        if (column) {
          hovered = column;
          show(column);
        }
      },
    };
  }

  // Hidden the way HA's own cards hide themselves: the grid closes the gap, and HA keeps a
  // hidden card visible in edit mode
  _setHidden(hidden) {
    if (hidden === this.hasAttribute("hidden")) return;
    this.style.display = hidden ? "none" : "";
    this.toggleAttribute("hidden", hidden);
    this.dispatchEvent(
      new CustomEvent("card-visibility-changed", { bubbles: true, composed: true, detail: { value: !hidden } })
    );
  }

  // Fade only an edge with more content behind it; recomputed on resize and scroll
  _fadeAll() {
    if (!this._resizeObserver && window.ResizeObserver) {
      // Only a new width matters: the height changes with the rounding below, which would
      // otherwise call this again
      this._resizeObserver = new ResizeObserver((entries) => {
        const width = entries[entries.length - 1].contentRect.width;
        if (width === this._observedWidth) return;
        this._observedWidth = width;
        this._fadeAll();
      });
      this._resizeObserver.observe(this);
    }
    this._homeStrips();
    this.shadowRoot.querySelectorAll(".strip").forEach((strip) => this._fade(strip));
    this._markWrapped();
    this._snapToGrid();
  }

  /**
   * In a sections view with automatic height, round the card's height up to whole grid rows
   * (56 px rows with 8 px gaps by default), so it ends where the cards beside it do. HA sets
   * --row-size only for a fixed number of rows: then HA sizes the card and it fills that. In a
   * masonry or panel view there is no grid to snap to.
   */
  _snapToGrid() {
    const card = this.shadowRoot && this.shadowRoot.querySelector("ha-card");
    if (!card) return;
    const style = getComputedStyle(this);
    const row = parseFloat(style.getPropertyValue("--row-height"));
    const gap = parseFloat(style.getPropertyValue("--row-gap")) || 0;
    card.style.minHeight = "";
    card.style.removeProperty("--squeeze");
    card.classList.remove("is-scrollable");
    if (style.getPropertyValue("--row-size").trim()) {
      this._fitFixedHeight(card);
      return;
    }
    if (!(row > 0)) return;
    // Measured without the previous rounding; the result is the same size again, so the
    // ResizeObserver isn't triggered in a loop
    const height = () => card.getBoundingClientRect().height;
    const natural = height();
    const rows = Math.max(1, Math.ceil((natural + gap - 0.5) / (row + gap)));
    const fit = (count) => count * (row + gap) - gap;
    let target = fit(rows);
    // Just over a row boundary: tighten the spacing inside the card a little (never its padding)
    // rather than add an almost empty row. Spacing shrinks linearly with --squeeze (0 to 1)
    const over = natural - fit(rows - 1);
    if (rows > 1 && over <= MAX_SQUEEZE_PX && this._squeeze(card, over, height)) {
      if (height() <= fit(rows - 1) + 0.5) target = fit(rows - 1);
      else card.style.removeProperty("--squeeze");
    }
    card.style.minHeight = `${target}px`;
  }

  /**
   * Tightens the card's inner spacing (--squeeze, 0 to 1) just enough to save `need` px of what
   * `measure` reads, if full tightening saves that much; false (and untouched) otherwise
   */
  _squeeze(card, need, measure) {
    const before = measure();
    card.style.setProperty("--squeeze", "1");
    const capacity = before - measure();
    if (capacity < need) {
      card.style.removeProperty("--squeeze");
      return false;
    }
    card.style.setProperty("--squeeze", String(Math.min(1, need / capacity + 0.01)));
    return true;
  }

  // Day info lines whose low and high wrapped onto a line of their own (by width, which CSS can't
  // tell): their dot between goes
  _markWrapped() {
    // All reset first, then all measured, then all marked: one layout, not one per line
    const lines = [...this.shadowRoot.querySelectorAll(".day-info")].map((info) => {
      info.classList.remove("is-wrapped");
      return [info, info.querySelector(".day-main"), info.querySelector(".extremes")];
    });
    const wrapped = lines.map(([, main, extremes]) =>
      Boolean(main && extremes && extremes.offsetTop > main.offsetTop + 2)
    );
    lines.forEach(([info], i) => info.classList.toggle("is-wrapped", wrapped[i]));
  }

  /**
   * A fixed height (rows set in the dashboard) too small for what the card shows: first its
   * spacing tightens as when rounding to grid rows; what still doesn't fit scrolls inside the
   * card, with a faded edge where there's more. Never over the card's edge, and never leaving
   * out a section one chose to show
   */
  _fitFixedHeight(card) {
    const over = () => card.scrollHeight - card.clientHeight;
    const natural = over();
    if (natural <= 0.5 || this._squeeze(card, natural, over)) return;
    // Scrolling anyway: as tight as it goes, so there's least to scroll
    card.style.setProperty("--squeeze", "1");
    card.classList.add("is-scrollable");
    this._fadeY(card);
    if (!card._scrollBound) {
      card._scrollBound = true;
      card.addEventListener("scroll", () => this._fadeY(card));
    }
  }

  // A card scrolling inside: its bottom faded while there's more below
  _fadeY(card) {
    const below = card.scrollHeight - card.clientHeight - card.scrollTop;
    card.classList.toggle("has-more-below", card.classList.contains("is-scrollable") && below > 1);
  }

  // Fade an edge with more behind it, and show its scroll button. Not on the left while the
  // strip rests where it belongs: the hour before now sits there, fully visible and tappable;
  // that one can scroll back is implied, and shows as soon as one has scrolled
  _fade(strip) {
    const max = strip.scrollWidth - strip.clientWidth;
    const rest = max - strip.scrollLeft;
    const atHome = Math.abs(strip.scrollLeft - Math.min(this._stripHome(strip), max)) < 2;
    for (const element of [strip, strip.parentElement]) {
      element.classList.toggle("has-more-right", rest > 1);
      element.classList.toggle("has-more-left", strip.scrollLeft > 1 && !atHome);
    }
    this._stickDayNames(strip);
  }

  /**
   * Day names stay in view like a calendar's headings: a name sits at its day's divider, and
   * once that has scrolled out on the left, it waits at the strip's left edge until the next
   * day's name pushes it out. Where its day has too little room left for the whole name, only
   * its first word stays ("Today"), so it isn't cut off. All measured first, then all moved: one
   * layout per scroll event
   */
  _stickDayNames(strip) {
    const left = strip.getBoundingClientRect().left;
    // Past the faded left edge (while there's more on the left), so it reads in full
    const edge = strip.classList.contains("has-more-left")
      ? Math.min(FADE.max, Math.max(FADE.min, FADE.share * strip.clientWidth)) - 6
      : 0;
    const labels = [...strip.querySelectorAll(":scope > .day.start")];
    // The column under each name (the columns come first among the strip's children)
    // (Its widths whole and as the first word, measured once while it's whole and laid out: a
    // label is new with each render, and has no width yet while the card isn't shown)
    for (const label of labels) {
      if (label._width) continue;
      const first = label.firstElementChild;
      label._width = label.scrollWidth;
      label._shortWidth = first ? first.offsetLeft + first.offsetWidth : label._width;
    }
    const places = labels.map((label) => ({
      start: strip.children[Number(label.dataset.col)].getBoundingClientRect().left - left,
    }));
    labels.forEach((label, i) => {
      const { start } = places[i];
      const next = i + 1 < places.length ? places[i + 1].start : Infinity;
      const at = Math.max(start, edge);
      const short = next - at - 8 < label._width && label._shortWidth < label._width;
      label.classList.toggle("is-short", short);
      // Up to the left edge (where its day has scrolled out), but always a little before the
      // next day's divider: pushed out over the edge by it, it fades instead of being cut off
      const width = short ? label._shortWidth : label._width;
      const shift = Math.min(Math.max(edge - start, 0), next - start - width - 8);
      const over = edge - start - shift;
      label.style.transform = shift ? `translateX(${shift}px)` : "";
      // (Gone within a few pixels: a name half out of view reads as cut off, faded or not)
      if (over > 0) label.style.setProperty("--pushed-out", String(Math.max(0, 1 - over / 16)));
      else label.style.removeProperty("--pushed-out");
    });
  }

  connectedCallback() {
    // A card in another card's window stands alone: no other card counts it, it counts none
    if (!inCardWindow(this)) ATTACHED_CARDS.add(this);
    if (this.shadowRoot) this._fadeAll();
    this._redrawDaysElsewhere();
  }

  // The other cards on the tab, which this one is drawn together with (shared day scale,
  // legend); none for a card in another card's window
  _peers() {
    return inCardWindow(this) ? [] : [...ATTACHED_CARDS].filter((card) => card !== this);
  }

  // Whether this card shows the row of "today" or "tomorrow" (its days section, not limited
  // to the other day)
  _showsDayRow(which) {
    if (!this._config || !this._config.show.includes("days")) return false;
    const { shown } = this._sections.days;
    return shown === "both" || shown === which;
  }

  // Whether another card on this tab shows that day's row of the same home. A tab behaves as
  // if its cards were one: the days share one scale, and tomorrow's row reads its percentage
  // against today's wherever that is
  _dayShownElsewhere(which) {
    return this._peers().some(
      (card) => card._config && card._config.device_id === this._config.device_id && card._showsDayRow(which)
    );
  }

  // Cards coming and going change how the other cards draw their days
  _redrawDaysElsewhere() {
    if (!this._showsDayRow("today") && !this._showsDayRow("tomorrow")) return;
    for (const card of this._peers()) {
      const sameHome = card._hass && card._config && card._config.device_id === this._config.device_id;
      if (sameHome && card._config.show.includes("days")) card._scheduleRender();
    }
  }

  // Which strip, the same across redraws
  _stripKey(strip) {
    return strip.classList.contains("hours") ? "hours" : "parts";
  }

  // Where a strip rests: its home column at the left edge (the hour before now, so now comes
  // second; for the parts of the day see the render). The strips reach back into yesterday
  _stripHome(strip) {
    const first = strip.querySelector(".col.home");
    if (!first) return 0;
    return strip.scrollLeft + first.getBoundingClientRect().left - strip.getBoundingClientRect().left;
  }

  // Each strip where it rests, or where the reader left it a moment ago: a redraw (new prices,
  // a new width) mustn't pull it away mid-scroll
  _homeStrips() {
    this._away = this._away || {};
    for (const strip of this.shadowRoot.querySelectorAll(".strip")) {
      const away = this._away[this._stripKey(strip)];
      this._settle(strip, away ? away.left : this._stripHome(strip), "auto");
    }
  }

  // Scrolls a strip by the card itself: its scroll events aren't the reader's
  _settle(strip, left, behavior) {
    strip._settling = Date.now() + (behavior === "smooth" ? 1000 : 150);
    strip.scrollTo({ left, behavior });
  }

  // The reader scrolled: remember where to, and go back after a while without scrolling
  _stripScrolled(strip) {
    if (strip._settling && Date.now() < strip._settling) return;
    const key = this._stripKey(strip);
    this._away = this._away || {};
    if (Math.abs(strip.scrollLeft - this._stripHome(strip)) < 2) {
      delete this._away[key];
      return;
    }
    this._away[key] = { left: strip.scrollLeft };
    this._scheduleReturn(key);
  }

  _scheduleReturn(key) {
    this._returnTimers = this._returnTimers || {};
    clearTimeout(this._returnTimers[key]);
    this._returnTimers[key] = setTimeout(() => {
      // Not under an open details window: wait until it's been closed a while
      const dialog = this.shadowRoot && this.shadowRoot.querySelector("dialog");
      const strip = this.shadowRoot && this.shadowRoot.querySelector(`.strip.${key}`);
      // Nor under the mouse: the reader is still looking at it
      if ((dialog && dialog.open) || (strip && strip.matches(":hover"))) {
        this._scheduleReturn(key);
        return;
      }
      delete this._away[key];
      if (strip) this._settle(strip, this._stripHome(strip), "smooth");
    }, STRIP_RETURN_MS);
  }

  disconnectedCallback() {
    ATTACHED_CARDS.delete(this);
    this._redrawDaysElsewhere();
    for (const timer of Object.values(this._returnTimers || {})) clearTimeout(timer);
    this._returnTimers = {};
    this._away = {};
    if (this._resizeObserver) this._resizeObserver.disconnect();
    this._resizeObserver = undefined;
  }

  /**
   * One strip of columns. Hours show the average as a bar; parts of the day show their spread
   * like the low/high of a weather forecast day: a span from lowest to highest price with a
   * dot at the average, each day on a scale of its own. The cheapest block from now on gets
   * a chip with how much cheaper it is than the block running now.
   */
  _strip(
    blocks,
    kind,
    naming,
    { t, periods, now, today, unit, references, average, dateOf, extremes, clock, clockLong }
  ) {
    const { key } = average;
    const ranged = kind === "parts";
    // A block's day for the dashed line: the day it begins on, but the block running now belongs
    // to today (a night is the old day's until midnight, then the new day's)
    // (The night at the very start began the day before yesterday, whose average isn't passed
    // on: it takes the day it leads into, where most of its hours lie)
    const referenceOf = (block) => {
      const start = Date.parse(block.start);
      const end = Date.parse(block.end);
      return references[dateOf(start <= now && now < end ? now : start)] ?? references[dateOf(end - 1)];
    };
    const valuesOf = (list) =>
      list.flatMap((b) => (ranged ? [b.price_min, b.price_max] : [b[key]]).concat(referenceOf(b)));
    const numbers = valuesOf(blocks).filter((v) => typeof v === "number");
    const format = priceFormatter(this._hass, numbers);
    // One scale per day, not one for the strip: a day's own span fills the height of its columns
    // instead of being squashed by a dearer day beside it (columns of different days aren't
    // comparable by height, the numbers say how they differ). A night counts for the day it
    // ends on, as everywhere (see dayOfBlock)
    const dayBlocks = new Map();
    for (const block of blocks) {
      const day = dayOfBlock(dateOf, block);
      if (!dayBlocks.has(day)) dayBlocks.set(day, []);
      dayBlocks.get(day).push(block);
    }
    const scales = new Map(
      [...dayBlocks].map(([day, list]) => {
        const dayNumbers = valuesOf(list).filter((v) => typeof v === "number");
        // Spans use the day's own range, bars start a little below its lowest price: both like
        // temperatures in a weather forecast
        const low = ranged ? Math.min(...dayNumbers) : barBaseline(dayNumbers);
        // A few prices far above the rest (a spike in the evening) would squash everything else
        // flat: the scale then ends a little above most prices, and what reaches beyond is cut
        // off at the top with a break mark (its number below says how high)
        const top = scaleTop(
          list.map((b) => (ranged ? b.price_max : b[key])),
          low,
          Math.max(...list.map(referenceOf).filter((v) => typeof v === "number"), low)
        );
        return [day, { low, top, span: top - low || 1 }];
      })
    );
    const scaleOf = (block) => scales.get(dayOfBlock(dateOf, block));
    const scale = (block, value) => {
      const { low, span } = scaleOf(block);
      return Math.min(((value - low) / span) * 100, 100);
    };
    // Bars and spans at the prices as shown: the same number, the same height (the day's line
    // keeps its exact place)
    const place = (block, value) => scale(block, shownPrice(format, value));
    const cut = (block, value) => shownPrice(format, value) > scaleOf(block).top;
    const language = this._hass.language;
    const section = ranged ? "day_parts" : "hours";
    const tappable = this._tapDetails(section);
    // Details left out in this section: not drawn (the details window still has them all)
    const hide = new Set(this._sections[section].hide);

    // A part's usual hours on hovering its name (e.g. "Morning 06–09")
    const hoursOf = (b) => {
      const hours = ranged && this._dayPartHours[b.part];
      return hours ? `${t[b.part]} ${hours.map((h) => String(h).padStart(2, "0")).join("–")}` : "";
    };
    const isCurrent = (b) => Date.parse(b.start) <= now && now < Date.parse(b.end);
    const current = blocks.find(isCurrent);
    // Shared by the details of all columns of this strip
    const strip = { format, current };
    // The cheapest block per day, each compared with now: the rest of today keeps its own chip
    // once tomorrow's prices are in. Always by the mean, whatever average is shown: what using
    // power across a block costs follows its mean (the median leaves out how high the dear
    // quarter hours are)
    const upcoming = blocks.filter((b) => isAhead(b, now, "price_mean"));
    const chips = new Map();
    for (const day of new Set(upcoming.map((b) => dayOfBlock(dateOf, b)))) {
      const cheapest = cheapestOf(
        upcoming.filter((b) => dayOfBlock(dateOf, b) === day),
        "price_mean"
      );
      if (!cheapest || !current || cheapest === current || !(current.price_mean > 0)) continue;
      const change = shownChange(cheapest.price_mean, current.price_mean, format);
      if (change === undefined || change > -0.01) continue;
      chips.set(cheapest, {
        chip: formatPercent(language, change, "always"),
        // The whole statement, for the tooltip and screen readers
        text: t.cheapest_tip[ranged ? "parts" : "hours"][day === today ? "today" : "tomorrow"]
          .replace("{percent}", formatPercent(language, -change, "never"))
          .replace("{price}", format(cheapest.price_mean))
          .replace("{now}", format(current.price_mean))
          .replace("{unit}", unit),
      });
    }

    // Where the strip rests: the block before the one running now (or that one, if first)
    const currentIndex = blocks.findIndex(isCurrent);
    const homeIndex = Math.max(0, currentIndex - 1);
    const dayNames = [];
    const columns = blocks.map((block, index) => {
      const start = Date.parse(block.start);
      const end = Date.parse(block.end);
      const isNow = isCurrent(block);
      const named = naming(block, isNow);
      const { name } = named;
      // Cut off where the known prices end: say how far it goes, and draw it as unfinished
      const partial = block.complete === false;
      const until = partial ? endTime(clock, block.end) : "";
      const day = partial ? t.until.replace("{time}", until) : named.day;
      const dayHtml = partial ? day : named.dayHtml;
      // The day's name (or how far it's known) goes into the strip's day row, over this column
      // (both grid lines: for an absolutely placed item, a missing end line is the strip's edge)
      if (dayHtml) {
        const nameKinds = [named.newDay && "start", partial && "partial", end <= now && !named.ongoing && "past"];
        dayNames.push(
          `<span class="${["day", ...nameKinds.filter(Boolean)].join(" ")}" style="grid-column:${index + 1} / ${index + 2}" data-col="${index}" aria-hidden="true">${dayHtml}</span>`
        );
      }
      const color = levelColor(block.level);
      let graph = "";
      // The current price beside the median (running part only), see below
      let nearMedian = false;
      // Where the chip floats: above the bar or span (a CSS length)
      let chipAt = `${Math.max(place(block, block[key] ?? 0), 7)}%`;
      if (ranged && typeof block.price_min === "number") {
        const bottom = place(block, block.price_min);
        const spanHeight = place(block, block.price_max) - bottom;
        // A narrow span is drawn at least SPAN_MIN_PX high (growing upward): the pointers sit at
        // their share of the span as drawn, so one at its lower end stays at the span's lower
        // edge and a price near the middle shows near the middle, whatever the span's height
        const drawn = `max(${spanHeight}%, ${SPAN_MIN_PX}px)`;
        const share = (at) => (spanHeight > 0 ? Math.min(1, Math.max(0, (at - bottom) / spanHeight)) : 0.5);
        // Kept two pixels inside the span, pointer and line alike: the line (the current price's is
        // 4 px with its halo) never hangs over an end of the span, and the pointer stays centered
        // on it
        const along = (at) => `calc(${bottom}% + clamp(2px, ${share(at)} * ${drawn}, ${drawn} - 2px))`;
        chipAt = `calc(${bottom}% + ${drawn})`;
        graph = `
          <div class="span${cut(block, block.price_max) ? " cut" : ""}" style="bottom:${bottom}%;height:${drawn};--c:${color}"></div>`;
        // The current price on the running part's span: a blue pointer on the left, facing the
        // median's on the right, kept on the span if the price lies just outside its range
        const nowPrice = this._renderInfo.nowPrice;
        const showNow = isNow && typeof nowPrice === "number" && !hide.has("now");
        const nowAt = showNow
          ? scale(block, Math.min(block.price_max, Math.max(block.price_min, nowPrice)))
          : undefined;
        const medianAt = place(block, block.price_median);
        // Where the pointers lie that close, they stand at one height, in the middle between them,
        // their lines halved and meeting there (see .meets)
        const drawnPx = Math.max((spanHeight / 100) * GRAPH_MIN_PX, SPAN_MIN_PX);
        nearMedian = showNow && Math.abs(share(nowAt) - share(medianAt)) * drawnPx < NEAR_POINTERS_PX;
        const meets = nearMedian && !hide.has("pointer") ? " meets" : "";
        const meetAt = along((nowAt + medianAt) / 2);
        const medianPos = nearMedian ? meetAt : along(medianAt);
        const nowPos = nearMedian ? meetAt : along(nowAt);
        if (!hide.has("pointer")) {
          graph += `<div class="tick" style="bottom:${medianPos}"></div>
          <div class="tick-line${meets}" style="bottom:${medianPos}"></div>`;
        }
        if (showNow) {
          graph += `<div class="tick-now-line${meets}" style="bottom:${nowPos}"></div><div class="tick-now" style="bottom:${nowPos}"></div>`;
        }
      } else if (typeof block[key] === "number") {
        graph = `<div class="bar${cut(block, block[key]) ? " cut" : ""}" style="height:${Math.max(place(block, block[key]), 7)}%;--c:${color}"></div>`;
      }
      // A period running now: its mark stuck to the top right corner of the highlighted column
      // of now, taking no room (left out with `badge`)
      const active = isNow && !hide.has("badge") && this._renderInfo.activePeriod;
      const reference = referenceOf(block);
      if (typeof reference === "number" && !hide.has("reference")) {
        graph += `<div class="ref" style="bottom:${scale(block, reference)}%"></div>`;
      }
      // The periods touching this block; the line under it is a small timeline of the block,
      // colored only where a period lies
      const touching = periodsTouching(periods, start, end);
      const drawn = hide.has("periods") ? [] : touching;
      const segments = drawn.map(({ k, a, b }) => ({
        k,
        left: ((Math.max(a, start) - start) / (end - start)) * 100,
        width: ((Math.min(b, end) - Math.max(a, start)) / (end - start)) * 100,
      }));
      const kinds = [...new Set(touching.map((p) => p.k))];
      const chip = chips.get(block);
      const shownChip = hide.has("cheapest") ? undefined : chip;
      // The chip floats in the graph just above the bar or span: the cheapest block's bar is
      // low, so there's room; a span reaching the top gets its upper end covered (its numbers
      // are below). It takes no row of its own, so the bars get that height
      const chipHtml = shownChip
        ? `<span class="chip" title="${chip.text}" style="bottom:min(calc(${chipAt} + 4px), calc(100% - 16px))">${chip.chip}</span>`
        : "";
      const range = ranged ? `${format(block.price_min)}–${format(block.price_max)}` : "";
      const here = extremesIn(extremes, start, end);
      const extremeText = (x) => extremeLabel(t, format, unit, clock, x.kind, x.price, x.at);
      // Hover hint on the graph: what it is, with its values (like an alt text)
      const time = timeRange(clock, start, end);
      const graphHint = [
        ranged ? `${t[block.part] || ""} ${time}` : time,
        t.levels[block.level],
        ranged
          ? `${format(block.price_min)}–${format(block.price_max)}, ${average.label} ${format(block[key])} ${unit}`
          : `${average.label} ${format(block[key])} ${unit}`,
        // Running now: the current price too, as the details lead with it
        isNow &&
          typeof this._renderInfo.nowPrice === "number" &&
          `${t.detail.now.now_price} ${this._renderInfo.formatNowFor(section, format)(this._renderInfo.nowPrice)} ${unit}${
            nearMedian ? `, ${t.detail.now.near_median}` : ""
          }`,
      ]
        .filter(Boolean)
        .join(" · ");
      const detail = this._details.length;
      this._details.push({ kind, block, isNow, partial, until, time, chip, here, touching, reference, strip });
      this._detailIndex.set(`${kind}|${start}`, detail);
      // Both in one block (e.g. a long day part): arrows only, the times in the tooltip
      const extremeHtml = here
        .filter((x) => !hide.has(x.kind))
        .map(
          (x) =>
            `<span class="${x.kind}" title="${extremeText(x)}">${extremeIcon(x.kind)}${
              here.length > 1 ? "" : ` ${clock.format(new Date(x.at))}`
            }</span>`
        )
        .join("");
      const label = [
        day,
        name,
        isNow && t.now,
        partial && t.partial_note.replace("{time}", until),
        t.levels[block.level],
        `${format(block[key])} ${unit}`,
        range && `${range} ${unit}`,
        chip && chip.text,
        ...here.map((x) => `${t[`day_${x.kind}`]} ${clock.format(new Date(x.at))}`),
        ...kinds.map((k) => t[k]),
      ]
        .filter(Boolean)
        .join(", ");
      // A column that opens its details is a button of its own (the strip then a group of them)
      return `<div class="col${isNow ? " current" : ""}${index === homeIndex ? " home" : ""}${end <= now ? " past" : ""}${partial ? " partial" : ""}${named.divider ? " new-day" : ""}" aria-label="${label}"${
        !ranged && typeof block[key] === "number" ? ` data-value="${shownPrice(format, block[key])}"` : ""
      }${tappable ? ` role="button" tabindex="0" aria-haspopup="dialog" data-detail="${detail}"` : ' role="listitem"'}>
        ${active ? periodBadge(active.kind, active.title) : ""}
        <div class="name" aria-hidden="true"${hoursOf(block) ? ` title="${hoursOf(block)}"` : ""}>${name}</div>
        <div class="graph" aria-hidden="true" title="${graphHint}${
          partial ? ` · ${t.partial_note.replace("{time}", until)}` : ""
        }">${graph}${chipHtml}</div>
        <div class="value" aria-hidden="true">${format(block[key])}</div>
        <div class="range" aria-hidden="true">${hide.has("range") ? "" : range}</div>
        <div class="extreme" aria-hidden="true">${extremeHtml}</div>
        <div class="mark${segments.length ? " has" : ""}" ${[...new Set(drawn.map((p) => p.k))]
          .map((k) => `data-${k}`)
          .join(" ")} aria-hidden="true"${
          drawn.length ? ` title="${drawn.map((p) => periodLabel(t, clockLong, p.k, p.a, p.b)).join(" · ")}"` : ""
        }>${segments
          .map((sg) => `<span style="left:${sg.left}%;width:${sg.width}%;background:${MARK_COLORS[sg.k]}"></span>`)
          .join("")}</div>
      </div>`;
    });
    const button = (direction, label, path) =>
      `<button class="scroll ${direction}" data-scroll="${direction}" aria-label="${label}">${svgIcon(path)}</button>`;
    // Rows of details left out entirely collapse (by setting only, never by data, so the height
    // never changes on its own). The parts' day row stays: it also says how far a part is known
    const collapsed = [
      !ranged && hide.has("tomorrow") && hide.has("weekday") && "--row-day:0px;--day-gap:0px",
      hide.has("range") && "--row-range:0px",
      hide.has("low") && hide.has("high") && "--row-extreme:0px",
      hide.has("periods") && "--row-mark:0px",
    ].filter(Boolean);
    // Day names in two parts (word and weekday): a narrow card stacks them in a taller row
    const twoPartDays = !hide.has("tomorrow") && !hide.has("weekday");
    return `<div class="strip-wrap">${button("back", t.earlier, CHEVRON_LEFT)}<div class="strip ${kind}${
      twoPartDays ? " two-part-days" : ""
    }"${collapsed.length ? ` style="${collapsed.join(";")}"` : ""} role="${tappable ? "group" : "list"}" aria-label="${
      t[kind === "parts" ? "day_parts" : "hours"]
    }">${columns.join("")}${dayNames.join("")}</div>${button("forward", t.later, CHEVRON_RIGHT)}</div>`;
  }

  /**
   * Today and tomorrow as rows, like the daily list of a weather forecast: lowest and highest
   * price at the ends of a span on one scale for the days shown, a pointer under it at the day's median,
   * the average shown on the right, on today's a triangle above the span where the price is now
   * (in the color of the "now" column), and below the day's level and volatility. Until
   * tomorrow's prices exist, its row says when they come, or is left out (tomorrow_pending:
   * hide; not in edit mode, so the card stays reachable there). Empty without any row.
   */
  _days(allDays, { t, unit, clock, now, nowPrice, today, average }) {
    const { shown, tomorrow_pending: pendingMode } = this._sections.days;
    // Details left out (the details window still has them all)
    const hide = new Set(this._sections.days.hide);
    // A best or peak price period running now: its sign beside today's name (left out with `badge`)
    const active = !hide.has("badge") && this._renderInfo.activePeriod;
    const days = allDays.filter((d) => shown === "both" || (shown === "today") === (d.date === today));
    // Tomorrow is pending only once today is known (no days at all: no section, as before)
    const pending =
      shown !== "today" &&
      allDays.length > 0 &&
      !allDays.some((d) => d.date > today) &&
      (pendingMode !== "hide" || this.preview);
    if (!days.length && !pending) return "";
    const { key } = average;
    const isMedian = key === "price_median";
    // One scale (and one number format) for the days shown on this tab, as if in one card: the
    // other day may be in another card of the same home
    // Days shown by another card of this home on the tab (once per render)
    const elsewhere = new Set(["today", "tomorrow"].filter((which) => this._dayShownElsewhere(which)));
    const onTab = allDays.filter((d) => days.includes(d) || elsewhere.has(d.date === today ? "today" : "tomorrow"));
    const todayDay = allDays.find((d) => d.date === today);
    const besideToday = days.some((d) => d.date === today) || elsewhere.has("today");
    const numbers = onTab.flatMap((d) => [d.price_min, d.price_max]).filter((v) => typeof v === "number");
    const low = Math.min(...numbers);
    const span = Math.max(...numbers) - low || 1;
    const scale = (value) => ((value - low) / span) * 100;
    const format = priceFormatter(this._hass, numbers);
    // Spans at the prices as shown: the same number, the same place (the price now keeps its
    // exact place)
    const place = (value) => scale(shownPrice(format, value));
    const tappable = this._tapDetails("days");
    const rows = days.map((day) => {
      const name = day.date === today ? t.today : t.tomorrow;
      // Today's low or high once it's behind us: still the day's value, but no longer to come
      const passed = (at) => Boolean(at) && now - Date.parse(at) >= EXTREME_PASSED_MS;
      const lowPassed = passed(day.price_min_at);
      const highPassed = passed(day.price_max_at);
      const when = (label, at, isPassed) =>
        at && `${label} ${clock.format(new Date(at))}${isPassed ? ` (${t.passed})` : ""}`;
      const color = levelColor(day.level);
      const level = t.levels[day.level] || day.level;
      const volatility = t.volatility[day.volatility] || "";
      // Tomorrow against today on the same average, once both days' prices are in: with today's
      // row right above, as a percentage under its average (the row above says against what);
      // tomorrow alone, in words in its info line
      const ratio =
        day.date > today && todayDay && todayDay[key] > 0 ? shownChange(day[key], todayDay[key], format) : undefined;
      // (Mid-line: "about as expensive as today")
      const comparison =
        ratio === undefined
          ? ""
          : lowerFirst(
              fill(t.detail.vs_today[trendOf(ratio)], {
                percent: formatPercent(this._hass.language, Math.abs(ratio), "never"),
              })
            );
      const left = place(day.price_min);
      const right = place(day.price_max);
      const medianAt = place(day.price_median);
      const isToday = day.date === today && typeof nowPrice === "number" && !hide.has("now");
      // Kept on the span if the price now lies just outside the day's (rounded) range
      const nowAt = isToday ? Math.min(100, Math.max(0, scale(nowPrice))) : undefined;
      // On top of each other, each pointer keeps half of the line (as at the parts of the day)
      const nearMedian = isToday && Math.abs(nowAt - medianAt) < NEAR_MEDIAN;
      const meets = nearMedian && !hide.has("pointer") ? " meets" : "";
      const nowText = isToday
        ? `${t.detail.now.now_price} ${this._renderInfo.formatNowFor("days", format)(nowPrice)} ${unit}${
            nearMedian ? `, ${t.detail.now.near_median}` : ""
          }`
        : "";
      const spoken = [
        name,
        level,
        `${format(day.price_min)}–${format(day.price_max)} ${unit}`,
        `${t.day_reference[isMedian ? "median" : "mean"]} ${format(day[key])} ${unit}`,
        !isMedian && `${t.day_reference.median} ${format(day.price_median)} ${unit}`,
        nowText,
        comparison,
        volatility,
        when(t.day_low, day.price_min_at, lowPassed),
        when(t.day_high, day.price_max_at, highPassed),
      ]
        .filter(Boolean)
        .join(", ");
      // The line below the span: level, volatility, low and high, as far as not left out
      const vsHtml =
        comparison && besideToday && !hide.has("compare")
          ? `<div class="day-vs ${trendOf(ratio)}" aria-hidden="true" title="${comparison}">${formatPercent(
              this._hass.language,
              ratio,
              "always"
            )}</div>`
          : "";
      const main = [
        !hide.has("level") && level,
        !besideToday && !hide.has("compare") && comparison,
        !hide.has("volatility") && volatility,
      ].filter(Boolean);
      const extremes = this._dayExtremes(day, t, clock, { low: lowPassed, high: highPassed }, hide);
      // Level and volatility, then low and high as one piece: where they wrap onto a line of
      // their own, the dot between goes (see _markWrapped)
      const info = [
        main.length && `<span class="day-main">${main.join(" · ")}</span>`,
        main.length && extremes && '<span class="day-sep">·</span>',
        extremes,
      ].filter(Boolean);
      const detail = this._dayDetails.length;
      this._dayDetails.push({ day, name, isToday: day.date === today, lowPassed, highPassed, format });
      return `<div class="day-row${vsHtml ? " has-vs" : ""}" aria-label="${spoken}"${
        tappable ? ` role="button" tabindex="0" aria-haspopup="dialog" data-day="${detail}"` : ' role="listitem"'
      }>
        <div class="day-name" aria-hidden="true">${name}${
          active && day.date === today ? periodBadge(active.kind, active.title) : ""
        }</div>
        <div class="day-track" aria-hidden="true" title="${level} · ${format(day.price_min)}–${format(day.price_max)} ${unit} · ${
          t.day_reference.median
        } ${format(day.price_median)}${nowText ? ` · ${nowText}` : ""}">
          <div class="day-span" style="left:${left}%;width:${right - left}%;background:${color}"></div>
          <span class="day-min${lowPassed ? " passed" : ""}" style="right:calc(${100 - left}% + 6px)">${format(day.price_min)}</span>
          <span class="day-max${highPassed ? " passed" : ""}" style="left:calc(${right}% + 6px)">${format(day.price_max)}</span>
          ${
            hide.has("pointer")
              ? ""
              : `<div class="day-tick" style="left:${medianAt}%"></div>
          <div class="day-tick-line${meets}" style="left:${medianAt}%"></div>`
          }${
            isToday
              ? `<div class="day-now-line${meets}" style="left:${nowAt}%"></div><div class="day-now" style="left:${nowAt}%"></div>`
              : ""
          }
        </div>
        <div class="day-mean" aria-hidden="true"><span class="ref-kind">${average.label}</span> ${format(day[key])}</div>${vsHtml}
        ${
          info.length
            ? `<div class="day-info" aria-hidden="true">${
                hide.has("level") ? "" : `<span class="level-dot" style="background:${color}"></span>`
              }${info.join("")}</div>`
            : ""
        }
      </div>`;
    });
    if (pending) {
      // Opens like a day: tomorrow without prices yet, filled in once they arrive
      const { zone, dateOf } = this._renderInfo;
      const detail = this._dayDetails.length;
      this._dayDetails.push({ day: { date: dateOf(dayBounds(today, zone)[1]) }, name: t.tomorrow, pending: true });
      rows.push(`<div class="day-row pending"${
        tappable
          ? ` role="button" tabindex="0" aria-haspopup="dialog" aria-label="${t.tomorrow}, ${t.tomorrow_pending}" data-day="${detail}"`
          : ' role="listitem"'
      }>
        <div class="day-name">${t.tomorrow}</div>
        <div class="day-info">${t.tomorrow_pending}</div>
      </div>`);
    }
    return `<div class="days" role="${tappable ? "group" : "list"}" aria-label="${t.days}">${rows.join("")}</div>`;
  }

  // When the day's low and high occur, with the same arrow-to-line marks as in the strips (the
  // words in their tooltip), always visible here: the strips only show them when they fall into
  // one of their blocks (not for a low at 23:45 tomorrow, or one already past)
  _dayExtremes(day, t, clock, passed, hide) {
    const entry = (kind, at, isPassed) =>
      at &&
      !hide.has(kind) &&
      `<span class="${kind}${isPassed ? " passed" : ""}" title="${t[`day_${kind}`]}${
        isPassed ? ` (${t.passed})` : ""
      }">${extremeIcon(kind)} ${clock.format(new Date(at))}</span>`;
    const parts = [entry("low", day.price_min_at, passed.low), entry("high", day.price_max_at, passed.high)].filter(
      Boolean
    );
    return parts.length ? `<span class="extremes">${parts.join(" · ")}</span>` : "";
  }

  _selectView(view) {
    this._view = view;
    // (Private mode or blocked storage: the switch still works for this page)
    storeValue(this._storageKey, view);
    this._render();
  }

  /**
   * The card's own controls (switch, page and legend buttons), the details of hours, parts of
   * the day and days, and its gestures (see _bindGestures). Without configuration a gesture does
   * nothing.
   */
  _bindActions(card) {
    const control = (event) =>
      event.target.closest("button[data-view], button[data-scroll], button[data-legend], button[data-card-action]");
    // An hour, part of the day or day opening its details (unless turned off for that section);
    // in the action zone a tap action set wins over the details of now
    const details = (event) => {
      const zoneTap = this._actionZone() && this._configured("tap") && !this._config.action_button;
      return (
        event.target.closest(".col[data-detail], .day-row[data-day]") ||
        (!zoneTap && event.target.closest(".now-block[data-detail]"))
      );
    };
    // Where the card's gestures run: its surface, or with a now section shown that section only
    // (its action zone, as the chart card's head); nowhere with its own button
    const zone = (event) => {
      if (control(event) || this._config.action_button) return null;
      if (this._actionZone() && !event.target.closest(".now-block")) return null;
      return details(event) || card;
    };
    card.addEventListener("click", (event) => {
      const button = control(event);
      if (button && button.dataset.legend) {
        this._openLegend(button);
      } else if (button && button.dataset.cardAction !== undefined) {
        this._action("tap");
      } else if (button && button.dataset.scroll) {
        const strip = button.parentElement.querySelector(".strip");
        const page = strip.clientWidth * 0.8 * (button.dataset.scroll === "forward" ? 1 : -1);
        strip.scrollBy({ left: page, behavior: "smooth" });
      } else if (button) {
        this._selectView(button.dataset.view);
      } else if (!zone(event)) {
        // Outside the gestures' zone a tap only opens details
        const column = details(event);
        if (column) this._openDetailsOf(column);
      }
    });
    this._bindGestures(card, zone, (target) => (target === card ? this._action("tap") : this._openDetailsOf(target)));
    card.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && !control(event)) {
        event.preventDefault();
        // The action zone (the now section) runs the tap action where one is set
        if (event.target.closest(".now-block[data-zone]") && this._configured("tap") && !this._config.action_button) {
          this._action("tap");
          return;
        }
        const column = event.target.closest(".col[data-detail], .day-row[data-day], .now-block[data-detail]");
        if (column) {
          this._openDetailsOf(column);
          return;
        }
        // Only the card itself, while it's the button, runs the action by keyboard
        if (event.target === card && card.getAttribute("role") === "button") this._action("tap");
      }
    });
  }

  _bindLegend(dialog) {
    // A tap on the backdrop lands on the dialog itself; inside, it lands on its content
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog || event.target.closest(".close")) {
        this._back(dialog);
        return;
      }
      // From a detail card to the whole legend, in the same window (and back again)
      if (event.target.closest("[data-open-legend]")) {
        this._pushBack(dialog, "[data-open-legend]");
        this._openLegend({ dataset: { legend: this._detailLegend.join(" ") } }, this._legendOpener, { only: true });
        dialog.querySelector(".close").focus();
        return;
      }
      if (event.target.closest("[data-open-values]")) {
        this._pushBack(dialog, "[data-open-values]");
        this._openValues();
        dialog.querySelector(".close").focus();
        return;
      }
      const drill = event.target.closest("[data-drill]");
      if (drill) {
        this._drill(dialog, Number(drill.dataset.drill));
        return;
      }
      const pick = event.target.closest("[data-pick]");
      if (pick) {
        this._pick(dialog, Number(pick.dataset.pick));
        return;
      }
      const step = event.target.closest("[data-nav]");
      if (step) this._navigate(Number(step.dataset.nav));
      if (event.target.closest("[data-nav-now]")) this._navigateTo(this._nowTarget(), "[data-nav-now]");
    });
    // In a detail card, the arrow keys and a horizontal swipe step to the time before or after
    // Back first, if the view was opened from another: by Escape, the button and back gestures
    const backFirst = (event) => {
      if (!this._detailBack.length) return false;
      event.preventDefault();
      this._back(dialog);
      return true;
    };
    dialog.addEventListener("keydown", (event) => {
      // Escape goes back here already: the browser lets a page hold off its closing only once
      // without a click in between, so a second Escape in a row would close the window
      if (event.key === "Escape" && backFirst(event)) return;
      // Hours, parts and quarter hours in a chart are buttons made of divs: Enter and Space click
      // them, and the click does the rest
      const button = (event.key === "Enter" || event.key === " ") && event.target.closest("[data-drill], [data-pick]");
      if (button) {
        event.preventDefault();
        button.click();
        return;
      }
      if (!this._detailNav || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) return;
      event.preventDefault();
      this._navigate(event.key === "ArrowLeft" ? -1 : 1);
    });
    let swipe;
    dialog.addEventListener("pointerdown", (event) => {
      swipe = event.pointerType === "mouse" ? undefined : { x: event.clientX, y: event.clientY };
    });
    dialog.addEventListener("pointerup", (event) => {
      if (!swipe || !this._detailNav) return;
      const dx = event.clientX - swipe.x;
      const dy = event.clientY - swipe.y;
      swipe = undefined;
      if (Math.abs(dx) > 60 && Math.abs(dx) > 2 * Math.abs(dy)) this._navigate(dx < 0 ? 1 : -1);
    });
    // Any other way to close (a back gesture), like the button: back first
    dialog.addEventListener("cancel", backFirst);
    dialog.addEventListener("close", () => {
      this._detailNav = undefined;
      this._detailBack = [];
      // A picked quarter hour goes with the window
      this._picked = undefined;
      // The card may have been redrawn meanwhile (price update): back to the button in its place
      const opener =
        this._legendOpener && this._legendOpener.isConnected
          ? this._legendOpener
          : this.shadowRoot.querySelector(OWN_LEGEND_BUTTON);
      if (opener) opener.focus();
    });
  }

  /**
   * The legend for the strips the button belongs to: each mark they show, drawn as in the
   * strips, with a sentence on what it means.
   */
  _openLegend(button, opener = button, { only = false } = {}) {
    this._detailNav = undefined;
    const t = stringsFor(this._hass);
    const l = t.legend;
    const levelNames = Object.entries(LEVEL_COLORS)
      .map(
        ([level, color]) => `<span><span class="level-dot" style="background:${color}"></span>${t.levels[level]}</span>`
      )
      .join("");
    const entries = {
      level: [
        `<span class="levels">${Object.values(LEVEL_COLORS)
          .map((color) => `<span style="background:${color}"></span>`)
          .join("")}</span>`,
        l.level[0],
        `${l.level[1]}<span class="level-names">${levelNames}</span>`,
      ],
      bar: [SWATCH.bar(LEVEL_COLORS.cheap), l.bar[0], l.bar[1][this._averageKind]],
      day_pointer: [SWATCH.pointer, ...l.day_pointer],
      day_now: [SWATCH.now, ...l.day_now],
      span: [SWATCH.span(LEVEL_COLORS.normal), ...l.span],
      reference: [SWATCH.ref, t.day_reference[this._averageKind], l.reference],
      cheapest: [SWATCH.chip(formatPercent(this._hass.language, -0.2, "always")), ...l.cheapest],
      best: [SWATCH.line("best"), t.best, l.best],
      peak: [SWATCH.line("peak"), t.peak, l.peak],
      best_now: [periodBadge("best"), ...l.best_now],
      peak_now: [periodBadge("peak"), ...l.peak_now],
      low: [SWATCH.extreme("low"), t.day_low, l.low],
      high: [SWATCH.extreme("high"), t.day_high, l.high],
      partial: [SWATCH.span(LEVEL_COLORS.normal, true), ...l.partial],
      cut: [SWATCH.bar(LEVEL_COLORS.very_expensive, true), ...l.cut],
      zbar: [SWATCH.bar(LEVEL_COLORS.cheap), ...l.zbar],
      zref_off: [`<span class="zref-off swatch-ref-off">${REF_OFF_ICONS.up}</span>`, ...l.zref_off],
      znow: [SWATCH.column("now"), ...l.znow],
      zpast: [SWATCH.column("past"), ...l.zpast],
      zmissing: [SWATCH.column("missing"), ...l.zmissing],
    };
    const partHours = Object.entries(this._dayPartHours || {});
    if (partHours.length) {
      const pad = (hour) => String(hour).padStart(2, "0");
      entries.times = [
        `<span class="timeline">${partHours
          .map(([, [from, to]]) => `<span style="flex:${(to - from + 24) % 24}"></span>`)
          .join("")}</span>`,
        l.times,
        partHours
          .map(([part, [from, to]]) => `<span class="nowrap">${t[part]} ${pad(from)}–${pad(to)}</span>`)
          .join(" · "),
      ];
    }
    // This card's strips first, then whatever the other cards on the tab add
    // (From a detail card: only what it shows)
    const others = only ? [] : this._peers().filter((card) => card._legendShows);
    const shown = [...button.dataset.legend.split(" "), ...others.flatMap((card) => card._legendShows.marks)];
    const kinds = LEGEND_ORDER.filter((kind) => shown.includes(kind) && entries[kind]);
    // Shared marks go in a grid that's two columns on wide screens, read row by row, with pairs
    // in one row; everything else is one column
    const list = (group, pairs = false) =>
      `<ul class="entries${pairs ? " pairs" : ""}">${group
        .map((kind) => entryItem(...entries[kind], pairs && LEGEND_ROW_START.includes(kind) ? "row-start" : ""))
        .join("")}</ul>`;
    // One section: a plain list. Hours and times of day together: what belongs to one of them
    // under its name (in the order of this card, then of the others), then what both have in common
    const sections = [
      ...new Set([
        ...(button.dataset.sections || "").split(" ").filter(Boolean),
        ...others.flatMap((card) => card._legendShows.sections),
      ]),
    ];
    const shared = kinds.filter((k) => !LEGEND_SECTION[k]);
    const stripSections = sections.filter((section) => section !== "days");
    // With one strip, what the strips have in common belongs to that strip's group
    const sharedWith = stripSections.length === 1 ? stripSections[0] : undefined;
    const group = (section) => {
      const own = kinds.filter((k) => LEGEND_SECTION[k] === section);
      const items = [...own, ...(section === sharedWith ? shared : [])];
      return items.length ? `<section class="group"><h3>${t[section]}</h3>${list(items)}</section>` : "";
    };
    let body;
    if (only) {
      body = list(
        DETAIL_LEGEND_ORDER.filter((kind) => shown.includes(kind) && entries[kind]),
        true
      );
    } else if (sections.length > 1) {
      // The sections side by side on wide screens (each one column); with two strips, what they
      // share below, named in the same order as the sections above it
      body = `<div class="groups">${sections.map(group).join("")}</div>${
        stripSections.length > 1 && shared.length
          ? `<section class="group shared"><h3>${l.both[stripSections[0]]}</h3>${list(shared, true)}</section>`
          : ""
      }`;
    } else {
      // Days alone: what they share with the strips (the level colors) first, then their marks
      const own = list(kinds.filter((k) => LEGEND_SECTION[k]));
      body = sections[0] === "days" ? `${list(shared, true)}${own}` : `${own}${list(shared, true)}`;
    }
    this._showDialog(l.title, `<div class="dialog-body">${body}</div>`, opener);
  }

  // What the whole legend explains: this card's legend button, or (when hidden) what it shows
  _legendSource() {
    const button = this.shadowRoot.querySelector(OWN_LEGEND_BUTTON);
    if (button) return button;
    const shows = this._legendShows || { marks: [], sections: [] };
    return { dataset: { legend: shows.marks.join(" "), sections: [...new Set(shows.sections)].join(" ") } };
  }

  // Fills the dialog (title with HA's close button, buttons at its end, then the body, which
  // scrolls on its own and starts at the top) and opens it
  _showDialog(title, body, opener, headEnd = "", subtitle = "") {
    const dialog = this.shadowRoot.querySelector("dialog");
    const t = stringsFor(this._hass);
    // Opened from another view in the window, or from a card's window beneath this one: the way
    // back to it instead of closing, as in HA's more-info dialog (closing this dialog is that way
    // back to the window)
    const back = this._detailBack.length > 0 || inCardWindow(this);
    const close = back ? t.back : t.legend.close;
    const head = dialogHead({ id: "legend-title", title, label: close, back, subtitle, end: headEnd });
    dialog.innerHTML = `${head}<div class="dialog-scroll">${body}</div>`;
    this._legendOpener = opener;
    if (!dialog.open) dialog.showModal();
  }

  /**
   * The detail card of an hour, a part of the day or a day, built like HA's more-info dialog:
   * on top the price and its level and how it relates to the day, then a chart zoomed into the
   * time, a few sentences on what that means, the facts, and quietly at the end the way to the
   * legend (the only one when the card's own is hidden). ‹ › in the header, swiping and the
   * arrow keys step to the time before or after.
   */
  _showDetailCard({ title, opener, nav, shown, hero, sub, tiles = [], status = [], chart, prose, facts }) {
    const t = stringsFor(this._hass);
    const color = levelColor(hero.level);
    const chip = hero.level
      ? `<span class="level-chip" style="--level:${color}"><span class="level-dot" style="background:${color}"></span>${
          t.levels[hero.level] || hero.level
        }</span>`
      : "";
    const body = `<div class="dialog-body detail">
      <div class="hero-tags">${(hero.tags || [])
        .filter((tag) => tag.text)
        .map(
          (tag) =>
            `<span class="badge${tag.now ? " now" : ""}${tag.live ? " live" : ""}">${
              tag.live ? '<span class="live-dot" aria-hidden="true"></span>' : ""
            }${tag.text}</span>`
        )
        .join("")}${chip}</div>
      ${hero.caption ? `<div class="hero-caption">${hero.caption}</div>` : ""}
      ${
        hero.message
          ? `<div class="hero"><span class="hero-message">${hero.message}</span></div>`
          : `<div class="hero">${hero.label ? `<span class="hero-kind">${hero.label}</span>` : ""}<span class="hero-price">${
              hero.price
            }</span><span class="hero-unit">${hero.unit}</span></div>`
      }
      ${sub ? `<p class="hero-sub">${sub}</p>` : ""}
      ${
        tiles.length
          ? `<div class="tiles">${tiles
              .map(
                (tile) =>
                  `<div class="tile${tile.placeholder ? " placeholder" : ""}"><div class="tile-label">${tile.label}</div><div class="tile-value">${tile.value}</div>${
                    tile.level ? levelTag(t, tile.level, "tile-level", "div") : ""
                  }${tile.note ? `<div class="tile-note">${tile.note}</div>` : ""}</div>`
              )
              .join("")}</div>`
          : ""
      }
      ${
        status.length
          ? `<div class="status">${status
              .map(
                (line) => `<div class="status-line ${line.kind}${line.upcoming ? " upcoming" : ""}">${line.text}</div>`
              )
              .join("")}</div>`
          : ""
      }
      ${chart.html}
      ${prose.length ? `<p class="prose">${prose.join(" ")}</p>` : ""}
      ${
        Object.values(facts).some((group) => group.length)
          ? `<button class="values-link" data-open-values><span>${t.detail.all_values}</span>${svgIcon(CHEVRON_RIGHT)}</button>`
          : ""
      }
      <button class="legend-link" data-open-legend><ha-icon icon="mdi:information-outline"></ha-icon><span>${t.detail.legend_link}</span></button>
    </div>`;
    this._detailNav = nav;
    this._detailShown = shown;
    this._detailValues = { title, facts };
    // What its chart shows, for its legend
    this._detailLegend = chart.marks;
    const step = (direction, label, path) =>
      `<button class="nav" data-nav="${direction}" aria-label="${label}" title="${label}"${
        this._navTarget(direction) === undefined ? " disabled" : ""
      }>${svgIcon(path)}</button>`;
    // Straight back to the time running now (today, for days), like a calendar's "Today". Not
    // shown while there; it keeps its room, so the title and arrows don't shift when stepping
    const nowTarget = this._nowTarget();
    const atNow = nowTarget === nav.index;
    const toNow =
      nowTarget === undefined
        ? ""
        : `<button class="nav-now${atNow ? " here" : ""}" data-nav-now${atNow ? ' tabindex="-1" aria-hidden="true"' : ""}>${
            nav.type === "day" ? t.today : t.now
          }</button>`;
    this._showDialog(title, body, opener, toNow + step(-1, t.earlier, CHEVRON_LEFT) + step(1, t.later, CHEVRON_RIGHT));
    // The price steps between its hours or quarter hours, as in the hour strip (a whole day
    // shows each hour's price on hovering instead)
    const zoom = this.shadowRoot.querySelector("dialog .zoom:not(.dense)");
    // (Left out in the hours' panel, they show on picking a quarter hour only)
    this._zoomSteps = zoom
      ? this._bindSteps(zoom, { column: ".zcol", bar: ".zbar", hover: this._stepsOnHover() })
      : undefined;
    // A picked quarter hour keeps its arrows (also when the card is drawn again)
    const picked = zoom && zoom.querySelector(".zcol.picked");
    if (picked) this._zoomSteps.pin(picked);
    const day = this.shadowRoot.querySelector("dialog .zoom.dense");
    if (day) this._bindScrub(day);
  }

  /**
   * A whole day's chart on touch: what the mouse gets by hovering an hour (its price on top of
   * its bar), a finger gets by resting on the chart for a moment and then moving over the hours
   * (the page and the swipe to the next day wait meanwhile). A tap or a swipe before that is
   * what it was: opening the hour, stepping to the day before or after.
   */
  _bindScrub(zoom) {
    let shown;
    const show = (column, haptic = false) => {
      if (column === shown) return;
      if (shown) shown.classList.remove("is-scrubbed");
      shown = column;
      if (column) column.classList.add("is-scrubbed");
      if (column && haptic) this._haptic("selection");
    };
    const columnAt = (x, y) => {
      const element = this.shadowRoot.elementFromPoint(x, y);
      const column = element && element.closest(".zcol");
      return column && zoom.contains(column) ? column : undefined;
    };
    this._bindHold(zoom, {
      grab: (x, y) => show(columnAt(x, y)),
      move: (x, y) => {
        // (Between two columns: the last one stays)
        const column = columnAt(x, y);
        if (column) show(column, true);
      },
      end: (event, held, cancelled) => {
        if (held && !cancelled) {
          // Neither the swipe to another day nor the tap on an hour: this was reading
          event.stopPropagation();
          const swallow = (click) => click.stopPropagation();
          zoom.addEventListener("click", swallow, { capture: true, once: true });
          setTimeout(() => zoom.removeEventListener("click", swallow, true), 400);
        }
        show(undefined);
      },
    });
  }

  /**
   * What only "now" has: how long the price of this quarter hour applies and what follows, the
   * block's average and the day's in tiles of their own, and whether a best or peak price period
   * runs now (or when the next best price period begins).
   */
  /**
   * "Now" at a glance: the current price on the day's scale and what to make of it. A best or
   * peak price period running leads; otherwise the level, how long it stays cheap or when it
   * gets cheap, the next best price period and a peak price period within three hours.
   * Undefined without the current quarter hour.
   */
  _nowState() {
    const { t, unit, now, periods, currentQuarter: live, quarters, days, today, average, clock, at } = this._renderInfo;
    if (!live) return undefined;
    const n = t.now_block;
    const day = days.find((d) => d.date === today) || {};
    const low = day.price_min;
    const high = day.price_max;
    const reference = day[average.key];
    const format = priceFormatter(
      this._hass,
      [low, high, live.price].filter((value) => typeof value === "number")
    );
    const formatNow = this._renderInfo.formatNowFor("now", format);
    const duration = (time) => this._duration(time - now);
    // "best price from 21:30 · in 4.5 h"
    const soon = (text, time) =>
      `${fill(text, { time: at(time) })} · ${fill(t.detail.now.wait, { duration: duration(time) })}`;
    // Cheap stretches from the quarter hours' levels: until when it stays cheap (not where the
    // known prices merely end), or when it next gets cheap, within a day
    const cheap = (level) => level === "cheap" || level === "very_cheap";
    let cheapUntil;
    let cheapFrom;
    if (quarters) {
      const { start, step, prices, levels } = quarters;
      const known = (i) => typeof prices[i] === "number";
      const index = Math.floor((now - start) / step);
      if (cheap(live.level)) {
        let i = index;
        while (known(i + 1) && cheap(levels[i + 1])) i += 1;
        if (known(i + 1)) cheapUntil = start + (i + 1) * step;
      } else {
        for (let i = index + 1; known(i) && start + i * step < now + 24 * HOUR_MS; i += 1) {
          if (cheap(levels[i])) {
            cheapFrom = start + i * step;
            break;
          }
        }
      }
    }
    const best = periodAt(periods.best, now);
    const peak = periodAt(periods.peak, now);
    const nextBest = nextPeriod(periods.best, now);
    const nextPeak = nextPeriod(periods.peak, now);
    const peakSoon = nextPeak && nextPeak[0] - now < 3 * HOUR_MS;
    let kind;
    let headline = "";
    let short = "";
    const lines = [];
    if (best) {
      kind = "best";
      headline = n.best;
      lines.push(`${fill(n.ends, { time: at(best[1]) })} · ${fill(n.left, { duration: duration(best[1]) })}`);
      if (cheapUntil > best[1]) lines.push(fill(n.still_cheap, { time: at(cheapUntil) }));
      short = fill(n.short.best, { duration: duration(best[1]) });
    } else if (peak) {
      kind = "peak";
      headline = n.peak;
      lines.push(fill(t.until, { time: at(peak[1]) }));
      if (nextBest) lines.push(soon(n.next_best, nextBest[0]));
      short = fill(n.short.peak, { time: at(peak[1]) });
    } else {
      // (cheapUntil is only set while it's cheap now)
      if (cheapUntil) {
        lines.push(fill(n.cheap_until, { time: at(cheapUntil) }));
      } else if (cheapFrom && (!nextBest || cheapFrom < nextBest[0])) {
        lines.push(soon(n.cheap_from, cheapFrom));
      }
      if (nextBest) lines.push(soon(n.next_best, nextBest[0]));
      if (peakSoon) {
        lines.push(soon(n.next_peak, nextPeak[0]));
        short = fill(n.short.peak_soon, { duration: duration(nextPeak[0]) });
      } else if (cheapUntil) short = fill(n.short.cheap_until, { time: at(cheapUntil) });
      else if (nextBest) short = fill(n.short.next_best, { duration: duration(nextBest[0]) });
    }
    const ranged = typeof low === "number" && typeof high === "number";
    const spread = ranged ? high - low : 0;
    // Where a price lies on the day's scale, 0 (low) to 1 (high)
    const shareOf = (value) => (spread > 0 ? Math.max(0, Math.min(1, (value - low) / spread)) : 0.5);
    const word = t.levels[live.level] || "";
    // The trend as its sensor shows it: its icon, its state in the user's language
    const trendObj = this._entities && this._entities.trend && this._hass.states[this._entities.trend];
    const trend =
      trendObj && trendObj.attributes.icon && !["unknown", "unavailable"].includes(trendObj.state)
        ? {
            // The sensor sets its icon by the trend itself
            icon: trendObj.attributes.icon,
            text: `${t.trend}: ${this._hass.formatEntityState ? this._hass.formatEntityState(trendObj) : trendObj.state}`,
          }
        : undefined;
    return {
      trend,
      price: live.price,
      color: levelColor(live.level),
      word,
      until: fill(t.until, { time: clock.format(new Date(live.end)) }),
      low,
      high,
      reference,
      ranged,
      share: shareOf(live.price),
      mark: ranged && typeof reference === "number" ? shareOf(reference) : undefined,
      format,
      formatNow,
      kind,
      headline,
      lines,
      short,
      label: fill(n.label, {
        price: formatNow(live.price),
        unit,
        level: word,
        low: format(low),
        high: format(high),
        average: t.day_reference[this._renderInfo.averageKind],
        reference: format(reference),
      }),
    };
  }

  /**
   * "Now" drawn as `header` (the line on top of the forecast card), `tile` (one row like HA's
   * tile card), `gauge` (the scale on its own) or `clock` (the coming twelve hours around a dial)
   */
  _nowHtml(style) {
    const state = this._nowState();
    if (!state) return "";
    const { unit, average } = this._renderInfo;
    const hide = new Set(this._sections.now.hide);
    // A tap opens the details of the hour running now, unless the card's own action is wanted
    const index = this._details.findIndex((d) => d.kind === "hours" && d.isNow);
    const opens = index >= 0 && this._tapDetails("now");
    // The card's action zone: a button for its actions too
    const zone = this._nowTakesActions();
    const trend = state.trend && !hide.has("trend") ? state.trend : undefined;
    const label = escapeHtml(trend ? `${state.label} ${trend.text}.` : state.label);
    // Subtle, top right: the direction prices move in now
    const trendHtml = trend
      ? `<span class="now-trend" title="${escapeHtml(trend.text)}" aria-hidden="true"><ha-icon icon="${trend.icon}"></ha-icon></span>`
      : "";
    const attributes =
      (zone ? " data-zone" : "") +
      (opens
        ? ` data-detail="${index}" role="button" tabindex="0" aria-label="${label}"`
        : zone
          ? ` role="button" tabindex="0" aria-label="${label}"`
          : ` role="group" aria-label="${label}"`);
    const price = state.formatNow(state.price);
    const verdict = [state.headline && `<b>${state.headline}</b>`, ...state.lines].filter(Boolean);
    if (style === "tile") {
      const sub = [state.word, !hide.has("verdict") && state.short].filter(Boolean).join(" · ");
      return `<div class="now-block now-tile"${attributes}><span class="now-mini">${gaugeSvg({ share: state.share, color: state.color, width: 12 })}</span><span class="now-text"><span class="now-value">${price} <span class="now-unit">${unit}</span></span><span class="now-sub">${sub}</span></span>${trendHtml}</div>`;
    }
    if (style === "header") {
      const levelChip = state.word ? `<span class="now-level" style="--c:${state.color}">${state.word}</span>` : "";
      const gauge = hide.has("gauge")
        ? ""
        : `<span class="now-mini">${gaugeSvg({ share: state.share, color: state.color, width: 11 })}</span>`;
      const line = hide.has("verdict") || !verdict.length ? "" : `<span class="now-line">${verdict.join(" · ")}</span>`;
      const position = (share) => `${(share * 100).toFixed(1)}%`;
      const span =
        state.ranged && !hide.has("day_span")
          ? `<span class="now-span" aria-hidden="true"><span class="now-span-bar">${
              typeof state.mark === "number"
                ? `<span class="now-span-ref" style="left:${position(state.mark)}"></span>`
                : ""
            }<span class="now-span-dot" style="left:${position(state.share)};--c:${state.color}"></span></span><span class="now-span-labels"><span>${state.format(state.low)}</span><span>${average.label} ${state.format(state.reference)}</span><span>${state.format(state.high)}</span></span></span>`
          : "";
      return `<div class="now-block now-head${trend ? " has-trend" : ""}"${attributes}>${trendHtml}${gauge}<span class="now-main"><span class="now-price"><span class="now-value">${price}</span> <span class="now-unit">${unit}</span>${levelChip}</span>${line}</span>${span}</div>`;
    }
    const verdictHtml =
      verdict.length && !hide.has("verdict")
        ? `<div class="now-verdict${state.kind ? ` ${state.kind}` : ""}"><span>${verdict.join("<br>")}</span></div>`
        : "";
    const center = `<div class="dial-center"><span class="dial-price">${price}<small>${unit}</small></span>${
      state.word ? `<span class="dial-level" style="--c:${state.color}">${state.word}</span>` : ""
    }<span class="dial-sub">${state.until}</span></div>`;
    if (style === "clock") {
      return `<div class="now-block now-clock"${attributes}>${trendHtml}<div class="dial-box"><div class="dial">${this._clockSvg(state)}${center}</div></div>${verdictHtml}</div>`;
    }
    const ends = state.ranged
      ? `<span class="dial-end low">${state.format(state.low)}</span>${
          typeof state.reference === "number"
            ? `<span class="dial-end mid">${average.label} ${state.format(state.reference)}</span>`
            : ""
        }<span class="dial-end high">${state.format(state.high)}</span>`
      : "";
    return `<div class="now-block now-gauge"${attributes}>${trendHtml}<div class="dial-box"><div class="dial">${gaugeSvg(
      {
        share: state.share,
        mark: state.mark,
        color: state.color,
      }
    )}${center}${ends}</div></div>${verdictHtml}</div>`;
  }

  /**
   * The coming twelve hours around a dial, each quarter hour in its level's color at its time
   * on the clock face, the hand at now. Behind the hand the dial goes on with the time twelve
   * hours later. Best and peak price periods as thin arcs outside; the numbers say which hour
   * each quarter of the dial stands for
   */
  _clockSvg(state) {
    const { now, zone, quarters, periods } = this._renderInfo;
    const C = 60;
    const R = 45;
    const W = 10;
    const HALF_DAY = 12 * HOUR_MS;
    const offset = zoneOffset(now, zone);
    const angleOf = (time) => (((((time + offset) % HALF_DAY) + HALF_DAY) % HALF_DAY) / HALF_DAY) * 360;
    const parts = [];
    if (quarters) {
      const { start, step, prices, levels } = quarters;
      const sweep = (step / HALF_DAY) * 360;
      const first = Math.floor((now - start) / step);
      const count = Math.round(HALF_DAY / step);
      for (let k = 0; k < count; k += 1) {
        const i = first + k;
        const angle = angleOf(start + i * step);
        const known = typeof prices[i] === "number";
        const color = known ? levelColor(levels[i]) : TRACK_COLOR;
        // The last one, right behind the hand, is furthest away: drawn faint, so the seam shows
        const faint = k === count - 1 && known ? ' stroke-opacity="0.35"' : "";
        parts.push(
          `<path d="${arcPath(C, R, angle + 0.35, angle + sweep - 0.35)}" fill="none" stroke="${color}" stroke-width="${W}"${faint}/>`
        );
      }
    } else {
      parts.push(`<circle cx="${C}" cy="${C}" r="${R}" fill="none" stroke="${TRACK_COLOR}" stroke-width="${W}"/>`);
    }
    for (const kind of ["best", "peak"]) {
      for (const [a, b] of periods[kind]) {
        const from = Math.max(a, now);
        const to = Math.min(b, now + HALF_DAY);
        if (to <= from) continue;
        const angle = angleOf(from);
        parts.push(
          `<path d="${arcPath(C, R + 9, angle, angle + ((to - from) / HALF_DAY) * 360)}" fill="none" stroke="${MARK_COLORS[kind]}" stroke-width="2.6" stroke-linecap="round"/>`
        );
      }
    }
    // Which hour each quarter of the dial stands for in the coming twelve hours
    const localHour = ((((now + offset) % (24 * HOUR_MS)) + 24 * HOUR_MS) % (24 * HOUR_MS)) / HOUR_MS;
    for (const position of [0, 3, 6, 9]) {
      let hour = Math.ceil(localHour);
      while (hour % 12 !== position) hour += 1;
      const [x, y] = polar(C, R - 13.5, position * 30);
      parts.push(
        `<text x="${x.toFixed(1)}" y="${(y + 2.4).toFixed(1)}" text-anchor="middle" font-size="7" fill="var(--secondary-text-color, #727272)">${hour % 24}</text>`
      );
    }
    const hand = angleOf(now);
    const [dx, dy] = polar(C, R + W / 2 + 4.5, hand);
    parts.push(
      `${radialLine(C, R, W, hand, 'stroke="var(--primary-text-color, #212121)" stroke-width="2.2"')}<circle cx="${dx.toFixed(2)}" cy="${dy.toFixed(2)}" r="2" fill="var(--primary-text-color, #212121)"/>`
    );
    return `<svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">${parts.join("")}</svg>`;
  }

  _nowView(
    live,
    { format, block, ranged, reference, sub, section = ranged ? "day_parts" : "hours", formatNow: givenFormatNow }
  ) {
    const { t, unit, clock, now, periods, average, averageKind, today, days, at } = this._renderInfo;
    // Each level beside the price it belongs to: the chip on top is this quarter hour's, the
    // tiles name the hour's (or part's) and the day's
    const day = days.find((d) => d.date === today);
    const language = this._hass.language;
    const n = t.detail.now;
    // (An hour's details pass theirs: the quarter hours there are shown unrounded)
    const formatNow = givenFormatNow || this._renderInfo.formatNowFor(section, format);
    const parts = [fill(n.valid_until, { time: clock.format(new Date(live.end)) })];
    // The next quarter hour, with the change in percent (meaningless around a price of zero)
    if (typeof live.next === "number" && live.price > 0) {
      parts.push(
        fill(n.then, {
          price: formatNow(live.next),
          change: percentFrom(language, live.next, live.price, formatNow),
        })
      );
    }
    const tiles = [];
    if (block && typeof block[average.key] === "number") {
      tiles.push({
        label: ranged ? n.this_part : n.this_hour,
        value: `${average.label} ${format(block[average.key])} ${unit}`,
        level: block.level,
        note: sub,
      });
    }
    if (typeof reference === "number") {
      tiles.push({
        label: t.day_reference[averageKind],
        value: `${format(reference)} ${unit}`,
        level: day && day.level,
        note: reference ? `${t.now} ${percentFrom(language, live.price, reference, formatNow, format)}` : "",
      });
    }
    const status = [];
    for (const kind of ["best", "peak"]) {
      const running = periodAt(periods[kind], now);
      if (running) status.push({ kind, text: fill(n.in_period[kind], { time: at(running[1]) }) });
    }
    if (!status.some((line) => line.kind === "best")) {
      const next = nextPeriod(periods.best, now);
      if (next) {
        status.push({
          kind: "best",
          upcoming: true,
          text: fill(n.next_best, {
            time: at(next[0]),
            wait: fill(n.wait, { duration: this._duration(next[0] - now) }),
          }),
        });
      }
    }
    return { sub: parts.join(" · "), tiles, status };
  }

  // "25 min", "2.5 h": how long until something begins
  _duration(ms) {
    const minutes = Math.max(1, Math.round(ms / 60000));
    const [value, unit] = minutes < 60 ? [minutes, "minute"] : [Math.round(minutes / 30) / 2, "hour"];
    const key = `${this._hass.language}|${unit}`;
    if (!DURATION_FORMATS.has(key)) {
      DURATION_FORMATS.set(
        key,
        new Intl.NumberFormat(this._hass.language, {
          style: "unit",
          unit,
          unitDisplay: "short",
          maximumFractionDigits: 1,
        })
      );
    }
    return DURATION_FORMATS.get(key).format(value);
  }

  // An open detail card follows the data (a new quarter hour, new prices): the same time again,
  // where the reader left it
  _refreshDetail() {
    const dialog = this.shadowRoot.querySelector("dialog");
    const shown = this._detailShown;
    if (!dialog || !dialog.open || !this._detailNav || !shown) return;
    const scroll = dialogScroll(dialog).scrollTop;
    const focused = dialog.contains(this.shadowRoot.activeElement);
    if (!this._reopen(shown, this._legendOpener)) return;
    dialogScroll(dialog).scrollTop = scroll;
    if (focused) dialog.querySelector(".close").focus();
  }

  // Opens a detail card again by what it shows (its index moves when the data does); false if
  // that time is gone
  _reopen(shown, opener) {
    const index =
      shown.type === "day"
        ? this._dayDetails.findIndex((d) => d.day.date === shown.key)
        : (this._detailIndex.get(`${shown.kind}|${Date.parse(shown.key)}`) ?? -1);
    if (index < 0) return false;
    if (shown.type === "day") this._openDayDetails(index, opener);
    else this._openDetails(index, opener);
    return true;
  }

  // Remembers the detail card shown now, to come back to it (with the focus on `focus`, the
  // control that left it)
  _pushBack(dialog, focus) {
    if (!this._detailNav || !this._detailShown) return;
    this._detailBack.push({
      shown: this._detailShown,
      opener: this._legendOpener,
      scroll: dialogScroll(dialog).scrollTop,
      focus,
    });
  }

  /**
   * All values of the detail card shown, in a view of their own like HA's "Details" of an
   * entity: the card's name above, in sections (prices, times, periods, comparison), each a
   * framed list
   */
  _openValues() {
    const { title, facts } = this._detailValues;
    const v = stringsFor(this._hass).detail.values;
    const sections = ["prices", "times", "periods", "compare"]
      .filter((group) => facts[group] && facts[group].length)
      .map(
        (group) =>
          `<section><h3>${v[group]}</h3><dl class="facts">${facts[group]
            .map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`)
            .join("")}</dl></section>`
      )
      .join("");
    this._detailNav = undefined;
    this._showDialog(v.title, `<div class="dialog-body values">${sections}</div>`, this._legendOpener, "", title);
  }

  // Picks a quarter hour in an hour's chart (again: unpicks it), in place: the same card with
  // its line below the chart, where the reader was
  _pick(dialog, start) {
    const context = this._pickContext;
    if (!context) return;
    const again = this._picked && this._picked.start === start;
    this._picked = again ? undefined : { key: `${this._detailShown.kind}|${context.block.start}`, start };
    for (const column of dialog.querySelectorAll("[data-pick]")) {
      const on = !again && Number(column.dataset.pick) === start;
      column.classList.toggle("is-picked", on);
      column.setAttribute("aria-pressed", String(on));
    }
    const slot = again ? undefined : context.slots.find((s) => s.start === start);
    dialog.querySelector(".zpick").innerHTML = this._pickLine(slot);
    // Its price steps stay with it while it's picked
    if (this._zoomSteps) this._zoomSteps.pin(again ? undefined : dialog.querySelector(`[data-pick="${start}"]`));
  }

  // Below an hour's chart: the picked quarter hour's line, or how to pick one
  _pickLine(slot) {
    return slot
      ? this._quarterLine(slot, this._pickContext)
      : `<span class="zpick-hint">${stringsFor(this._hass).detail.pick.hint}</span>`;
  }

  // From an hour in the chart of a part of the day or a day to that hour's details
  _drill(dialog, index) {
    this._pushBack(dialog);
    this._openDetails(index, this._legendOpener);
    dialog.querySelector(".close").focus();
  }

  /**
   * Back to the view this one was opened from, where the reader left it, with the focus on the
   * hour last shown if it's in its chart; with nothing to go back to (or that time gone by
   * now), the window closes
   */
  _back(dialog) {
    const from = this._detailShown;
    const entry = this._detailBack.pop();
    if (!entry || !this._reopen(entry.shown, entry.opener)) {
      dialog.close();
      return;
    }
    dialogScroll(dialog).scrollTop = entry.scroll;
    const control = entry.focus && dialog.querySelector(entry.focus);
    if (control) {
      control.focus({ preventScroll: true });
      return;
    }
    const index =
      from && from.type === "col" ? this._detailIndex.get(`${from.kind}|${Date.parse(from.key)}`) : undefined;
    const hour = index === undefined ? null : dialog.querySelector(`[data-drill="${index}"]`);
    (hour || dialog.querySelector(".close")).focus({ preventScroll: true });
  }

  // The time before or after the one shown (same strip, or the other day); undefined at the end
  _navTarget(direction) {
    const nav = this._detailNav;
    if (!nav) return undefined;
    if (nav.type === "day") return this._dayDetails[nav.index + direction] ? nav.index + direction : undefined;
    const { kind } = this._details[nav.index] || {};
    for (let i = nav.index + direction; i >= 0 && i < this._details.length; i += direction) {
      if (this._details[i].kind === kind) return i;
    }
    return undefined;
  }

  // The index of the time running now in the same strip (today, for days); undefined if none
  _nowTarget() {
    const nav = this._detailNav;
    if (!nav) return undefined;
    if (nav.type === "day") {
      const index = this._dayDetails.findIndex((d) => d.isToday);
      return index < 0 ? undefined : index;
    }
    const { kind } = this._details[nav.index] || {};
    const index = this._details.findIndex((d) => d.kind === kind && d.isNow);
    return index < 0 ? undefined : index;
  }

  _navigate(direction) {
    this._navigateTo(this._navTarget(direction), `[data-nav="${direction}"]`);
  }

  // Opens the details of another time in the same window; focus stays on the control used
  _navigateTo(target, control) {
    if (target === undefined || !this._detailNav || target === this._detailNav.index) return;
    const day = this._detailNav.type === "day";
    // Focus goes back to that time's column when the card is closed, if it's on the card
    const opener =
      this.shadowRoot.querySelector(`ha-card ${day ? `[data-day="${target}"]` : `[data-detail="${target}"]`}`) ||
      this._legendOpener;
    if (day) this._openDayDetails(target, opener);
    else this._openDetails(target, opener);
    // The content was replaced: keep the focus in the window, on the same control if it goes on
    const dialog = this.shadowRoot.querySelector("dialog");
    (dialog.querySelector(`${control}:not(:disabled):not(.here)`) || dialog.querySelector(".close")).focus();
  }

  /**
   * Prices in steps of `size` (a quarter hour or an hour) from start to end, each with its
   * level: from the quarter hours, aggregated like the strips (mean or median). Where they
   * don't reach (or from an older integration), hours come from the hour strip.
   */
  _slots(start, end, size, kind = this._renderInfo.averageKind) {
    const { quarters, hours } = this._renderInfo;
    const key = averageOf({}, kind).key;
    return quarterSlots(quarters, start, end, size, kind).map((slot) => {
      if (slot.price !== null || size < HOUR_MS) return slot;
      // Before the quarter hours (an hour further back than they reach): the hour strip's value
      const hour = hours.find((block) => Date.parse(block.start) === slot.start);
      return hour && typeof hour[key] === "number"
        ? { ...slot, price: hour[key], level: levelOfMany([hour.level]) }
        : slot;
    });
  }

  /**
   * The zoom chart: one bar per slot in its level color, from zero like the hour strip, the
   * day's average as the dashed line (the same line as in the strips), the slot running now
   * highlighted and past ones faded, the day's low and high as arrows, periods as lines
   * underneath. Dense (a whole day): no values, a label every third hour, and below the parts
   * of the day.
   */
  _zoomChart(slots, { format, reference, label, dense = false, bands = "", drill, empty = false, pick }) {
    const { t, unit, clock, now, periods, extremes } = this._renderInfo;
    // From the prices as shown (rounded): bars, baseline and span all follow the same numbers, so
    // a bar can't end up taller than the chart because its rounded price lies beyond the raw span
    const values = slots
      .map((s) => s.price)
      .filter((v) => typeof v === "number")
      .map((v) => shownPrice(format, v));
    // The marks drawn, for the detail card's legend (returned with the chart)
    const marks = new Set();
    // Without any price only as empty slots, where asked for (a day still to come)
    if (!values.length && !empty) return { html: "", marks: [] };
    if (values.length) marks.add("zbar").add("level");
    if (bands) marks.add("times");
    // Scaled to the bars alone, so the quarter hours of an hour show their differences; the
    // day's line only where it falls inside (the hero and tiles say how far off it is)
    const low = values.length ? barBaseline(values) : 0;
    const span = values.length ? Math.max(...values) - low || 1 : 1;
    const showReference = typeof reference === "number" && reference >= low && reference <= low + span;
    if (showReference) marks.add("reference");
    // Too far off to draw: a dash with an arrow at the right edge says which way it lies
    const offDirection =
      typeof reference === "number" && values.length && !showReference ? (reference > low ? "up" : "down") : "";
    if (offDirection) marks.add("zref_off");
    const offReference = offDirection
      ? `<span class="zref-off ${offDirection}" title="${t.day_reference[this._renderInfo.averageKind]} ${format(
          reference
        )} ${unit}">${REF_OFF_ICONS[offDirection]}</span>`
      : "";
    const scale = (value) => Math.min(100, Math.max(0, ((value - low) / span) * 100));
    const spoken = [];
    const columns = slots.map((slot, index) => {
      const known = typeof slot.price === "number";
      const isNow = slot.start <= now && now < slot.end;
      const time = timeRange(clock, slot.start, slot.end);
      const value = known ? `${t.levels[slot.level] || ""} · ${format(slot.price)} ${unit}` : t.detail.unknown;
      spoken.push(`${time}: ${value}`);
      const here = extremesIn(extremes, slot.start, slot.end);
      const touching = periodsTouching(periods, slot.start, slot.end);
      const length = slot.end - slot.start;
      const segments = touching
        .map(({ k, a, b }) => {
          const left = ((Math.max(a, slot.start) - slot.start) / length) * 100;
          const width = ((Math.min(b, slot.end) - Math.max(a, slot.start)) / length) * 100;
          return `<span style="left:${left}%;width:${width}%;background:${MARK_COLORS[k]}"></span>`;
        })
        .join("");
      // A period running now: its mark under the slot of now, beside the low and high marks
      // (above the bar it would cover the price)
      const active = isNow && known && this._renderInfo.activePeriod;
      if (isNow) marks.add("znow");
      if (slot.end <= now && known) marks.add("zpast");
      if (!known) marks.add("zmissing");
      if (active) marks.add(`${active.kind}_now`);
      for (const x of here) marks.add(x.kind);
      for (const { k } of touching) marks.add(k);
      // A whole day shows no numbers: hovering an hour shows its price on top of its bar
      // (Near the top, the price goes inside the bar: above it, it would leave the chart)
      // From the price as shown: the same number, the same height
      const shown = known ? shownPrice(format, slot.price) : undefined;
      const height = known ? Math.max(scale(shown), 3) : 0;
      const graph = known
        ? `<div class="zbar${dense && height > 75 ? " tall" : ""}" style="height:${height}%;--c:${levelColor(slot.level)}"${
            dense ? ` data-label="${format(slot.price)}"` : ""
          }></div>`
        : "";
      const ref = showReference ? `<div class="ref" style="bottom:${scale(reference)}%"></div>` : "";
      // A slot with details of its own (an hour) opens them
      const target = drill && drill(slot);
      // Or can be picked (a quarter hour of an hour): its line below the chart
      const picked = pick && slot.start === pick.selected;
      // (A button says what it is: the chart around it isn't one image then)
      const open =
        target !== undefined
          ? ` data-drill="${target}" role="button" tabindex="0" aria-label="${time}: ${value}"`
          : pick && known
            ? ` data-pick="${slot.start}" role="button" tabindex="0" aria-pressed="${picked}" aria-label="${time}: ${value}"`
            : "";
      return `<div class="zcol${isNow ? " current" : ""}${slot.end <= now ? " past" : ""}${known ? "" : " missing"}${
        target !== undefined ? " drill" : ""
      }${picked ? " is-picked" : ""}" title="${time} · ${value}"${open}${known && !dense ? ` data-value="${shown}"` : ""}>
        ${active ? periodBadge(active.kind, active.title) : ""}${
          dense ? "" : `<span class="zvalue">${known ? format(slot.price) : "?"}</span>`
        }
        <div class="zgraph">${graph}${ref}${index === slots.length - 1 ? offReference : ""}</div>
        <span class="zmark">${here.map((x) => `<span class="${x.kind}">${extremeIcon(x.kind)}</span>`).join("")}</span>
        <span class="zlabel">${label(slot, index, isNow)}</span>
        <div class="mark${segments ? " has" : ""}">${segments}</div>
      </div>`;
    });
    // One image for screen readers, unless it holds buttons (hours or parts to open, quarter
    // hours to pick): those would be hidden inside an image
    const interactive = Boolean(drill || pick) || bands.includes("data-drill");
    const image = interactive ? "" : ` role="img" aria-label="${spoken.join("; ")}"`;
    const html = `<figure class="zoom${dense ? " dense" : ""}${offDirection ? " ref-off" : ""}"${image}><div class="zplot">${columns.join(
      ""
    )}</div>${bands}</figure>`;
    return { html, marks: [...marks] };
  }

  // The details of the hour starting then, as far as the hour strip has it: an hour in the
  // chart of a part of the day or a day opens them
  _hourDetail(start) {
    return this._detailIndex.get(`hours|${start}`);
  }

  // The parts of the day under a day's chart, as wide as their hours
  _partBands(slots) {
    const { t, hourName } = this._renderInfo;
    const partOf = (time) => {
      const hour = Number(hourName(time));
      const found = Object.entries(this._dayPartHours || {}).find(([, [from, to]]) =>
        from < to ? from <= hour && hour < to : hour >= from || hour < to
      );
      return found && found[0];
    };
    const runs = [];
    for (const slot of slots) {
      const part = partOf(slot.start);
      if (runs.length && runs[runs.length - 1].part === part) runs[runs.length - 1].count += 1;
      else runs.push({ part, count: 1, start: slot.start });
    }
    if (!runs.some((run) => run.part)) return "";
    // Each opens its part of the day, as far as the strip of the parts has it (a night begun
    // the evening before, too)
    const detailOf = (run) =>
      this._details.findIndex(
        (d) => d.kind === "parts" && Date.parse(d.block.start) <= run.start && run.start < Date.parse(d.block.end)
      );
    return `<div class="zbands">${runs
      .map((run) => {
        const index = run.part ? detailOf(run) : -1;
        const label = run.count >= 3 && run.part ? t[run.part] : "";
        return index < 0
          ? `<span style="flex:${run.count} 1 0" aria-hidden="true">${label}</span>`
          : `<span style="flex:${run.count} 1 0" data-drill="${index}" role="button" tabindex="0" aria-label="${this._partName(
              this._details[index].block
            )}">${label}</span>`;
      })
      .join("")}</div>`;
  }

  /**
   * A part of the day on its day, as the language says it: "Saturday evening". A night goes by
   * the day it leads into where the language would be ambiguous otherwise ("Nacht zum
   * Samstag": "Freitagnacht" reads as either night to many); `inSentence` for the form inside
   * a sentence ("in der Nacht zum Samstag")
   */
  _partName(block, inSentence = false) {
    const { t, weekdayOf } = this._renderInfo;
    const start = Date.parse(block.start);
    const template = (inSentence && t.part_in_sentence[block.part]) || t.part_on_day[block.part];
    if (!template) return t[block.part] || block.part;
    return fill(template, { weekday: weekdayOf(start), next: weekdayOf(start + 12 * HOUR_MS) });
  }

  // "Saturday from 03:00", "this evening": when a later hour or part of the day begins
  _whenText(block, ranged) {
    const { t, clock, dateOf, today, weekdayOf } = this._renderInfo;
    const start = Date.parse(block.start);
    const isToday = dateOf(start) === today;
    if (ranged) {
      return isToday ? t.part_today[block.part] : this._partName(block, true);
    }
    return fill(t.detail.when_hour[isToday ? "today" : "other"], {
      time: clock.format(new Date(start)),
      weekday: weekdayOf(start),
    });
  }

  // "+0,12 kr/kWh (+8 %)": how far `value` lies from `base`, as shown (from the rounded prices)
  _difference(format, value, base) {
    const { unit } = this._renderInfo;
    const diff = shownPrice(format, value) - shownPrice(format, base);
    return `${signedPrice(format, unit, diff)} (${percentFrom(this._hass.language, value, base, format)})`;
  }

  _openDetailsOf(element) {
    if (element.dataset.day !== undefined) this._openDayDetails(Number(element.dataset.day), element);
    else this._openDetails(Number(element.dataset.detail), element);
  }

  /**
   * One day in detail: its whole course hour by hour with the parts of the day below, where
   * it's cheapest and dearest, what's still to come today or how tomorrow compares with today,
   * and the facts: range, median and average, volatility, low and high, cheapest hour and part
   * of the day, periods.
   */
  _openDayDetails(index, opener) {
    const info = this._dayDetails && this._dayDetails[index];
    if (!info) return;
    const { t, unit, clock, now, nowPrice, periods, hours, parts, dateOf, days, average, currentQuarter } =
      this._renderInfo;
    if (info.pending) {
      this._openPendingDay(index, opener, info);
      return;
    }
    const { day, format } = info;
    const formatNow = this._renderInfo.formatNowFor("days", format);
    const language = this._hass.language;
    const x = t.detail;
    const p = x.prose;
    const dd = t.day_details;
    const head = this._dayHead(day.date);
    const slots = this._slots(head.start, head.end, HOUR_MS);
    const chart = this._zoomChart(slots, {
      format,
      reference: day[average.key],
      dense: true,
      label: head.label,
      bands: this._partBands(slots),
      drill: (slot) => this._hourDetail(slot.start),
    });
    const other = days.find((d) => d !== day);
    // Tomorrow against today by the average shown (the big number and the tiles), so the
    // percentages match the prices next to them
    const { key } = average;
    // Against the other day (tomorrow against today, and once tomorrow's prices are in, today
    // against tomorrow)
    const vsOther = other && other[key] > 0 ? shownChange(day[key], other[key], format) : undefined;
    const vsKey = vsOther === undefined ? "" : trendOf(vsOther);
    const vsPercent = vsOther === undefined ? "" : formatPercent(language, Math.abs(vsOther), "never");
    // Under the big number what it is like itself; comparisons go in the tiles
    const sub = capitalize(t.volatility[day.volatility] || "");

    const prose = [];
    if (vsOther !== undefined) {
      prose.push(
        info.isToday
          ? fill(p.today_vs_tomorrow, { comparison: fill(x.vs_tomorrow[vsKey], { percent: vsPercent }) })
          : `${fill(x.vs_today[vsKey], { percent: vsPercent })}.`
      );
    }
    if (day.price_min_at && day.price_max_at) {
      prose.push(
        fill(p.day_extremes, {
          low: clock.format(new Date(day.price_min_at)),
          lowPrice: format(day.price_min),
          high: clock.format(new Date(day.price_max_at)),
          highPrice: format(day.price_max),
          unit,
        })
      );
    }
    // Cheapest hour and part of the day of this day; for today only what's still to come. By
    // the mean, like the chips: what using power across an hour or part of the day costs
    const onDay = (b) => isAhead(b, now, "price_mean") && dayOfBlock(dateOf, b) === day.date;
    const hour = cheapestOf(hours.filter(onDay), "price_mean");
    const part = cheapestOf(parts.filter(onDay), "price_mean");
    // (Leading with now, a tile says it)
    if (info.isToday && hour && !currentQuarter) {
      prose.push(fill(p.day_ahead, { time: clock.format(new Date(hour.start)), price: format(hour.price_mean), unit }));
    }

    const when = info.isToday ? "today" : "other";
    const passed = (isPassed) => (isPassed ? ` (${dd.passed})` : "");
    const facts = {
      prices: [
        [x.facts.range, `${format(day.price_min)}–${format(day.price_max)} ${unit}`],
        [x.facts.median, `${format(day.price_median)} ${unit}`],
        [x.facts.mean, `${format(day.price_mean)} ${unit}`],
      ],
      times: [],
      periods: [],
      compare: [],
    };
    if (x.volatility[day.volatility]) facts.prices.push([x.facts.volatility, x.volatility[day.volatility]]);
    // Today leads with the price of this very quarter hour, like the hour running now: the day's
    // average moves to a tile, beside the running hour's
    const live = info.isToday && currentQuarter ? currentQuarter : undefined;
    // Now (without the quarter hours: the running hour's), with the days' decimals
    if (info.isToday && !live && typeof nowPrice === "number") {
      facts.prices.push([x.facts.now, `${formatNow(nowPrice)} ${unit}`]);
    }
    if (day.price_min_at) {
      facts.times.push([
        t.day_low,
        `${clock.format(new Date(day.price_min_at))} · ${format(day.price_min)}${passed(info.lowPassed)}`,
      ]);
    }
    if (day.price_max_at) {
      facts.times.push([
        t.day_high,
        `${clock.format(new Date(day.price_max_at))} · ${format(day.price_max)}${passed(info.highPassed)}`,
      ]);
    }
    if (hour)
      facts.times.push([
        dd.cheapest_hour[when],
        `${timeRange(clock, hour.start, hour.end)} · ⌀ ${format(hour.price_mean)}`,
      ]);
    // The part named with its average, and where inside it it's cheapest (still to come, for
    // today): its whole span would read as cheap from its first hour on, which may be the
    // day's high
    if (part) {
      const inside = this._slots(
        Math.max(Date.parse(part.start), info.isToday ? now - (now % HOUR_MS) : 0),
        Date.parse(part.end),
        HOUR_MS,
        "mean"
      ).filter((slot) => typeof slot.price === "number" && slot.end > now);
      const best = cheapestOf(inside, "price");
      const name = `${t[part.part] || part.part} · ⌀ ${format(part.price_mean)}`;
      facts.times.push([
        dd.cheapest_part[when],
        best ? `${name} · ${fill(x.cheapest_in, { time: timeRange(clock, best.start, best.end) })}` : name,
      ]);
    }
    for (const k of ["best", "peak"]) {
      for (const [a, b] of periods[k].filter((period) => dateOf(period[0]) === day.date)) {
        facts.periods.push([t.details.period[k], timeRange(clock, a, b)]);
      }
    }
    if (vsOther !== undefined) {
      facts.compare.push([
        info.isToday ? x.facts.vs_tomorrow : x.facts.vs_today,
        this._difference(format, day[key], other[key]),
      ]);
    }

    // The day's average in a tile beside it, and the cheapest hour still to come today
    let nowView = {};
    if (!live && !info.isToday && vsOther !== undefined) {
      // Tomorrow, mirroring today: today's average beside it, and its own cheapest hour
      nowView.tiles = [
        {
          label: `${t.today} · ${t.day_reference[this._renderInfo.averageKind]}`,
          value: `${format(other[key])} ${unit}`,
          level: other.level,
          note: `${info.name} ${formatPercent(language, vsOther, "always")}`,
        },
      ];
      if (hour) {
        nowView.tiles.push({
          label: dd.cheapest_hour.other,
          value: timeRange(clock, hour.start, hour.end),
          level: hour.level,
          note: `⌀ ${format(hour.price_mean)} ${unit}`,
        });
      }
    }
    if (live) {
      nowView = this._nowView(live, { format, reference: day[average.key], section: "days" });
      if (hour) {
        nowView.tiles.push({
          label: dd.cheapest_hour.today,
          value: timeRange(clock, hour.start, hour.end),
          level: hour.level,
          note: `⌀ ${format(hour.price_mean)} ${unit}${
            live.price > 0 ? ` · ${percentFrom(language, hour.price_mean, live.price, format, formatNow)}` : ""
          }`,
        });
      }
    }

    this._showDetailCard({
      // "Today" or "Tomorrow" as the badge on the price line, so the title stays one line
      title: head.title,
      opener,
      nav: { type: "day", index },
      shown: { type: "day", key: day.date },
      hero: live
        ? {
            caption: x.now.now_price,
            price: formatNow(live.price),
            unit,
            level: live.level || day.level,
            tags: [{ text: info.name, now: true, live: true }, { text: head.weekday }],
          }
        : {
            label: average.label,
            price: format(day[average.key]),
            unit,
            level: day.level,
            tags: [{ text: info.name, now: info.isToday }, { text: head.weekday }],
          },
      sub: live ? nowView.sub : sub,
      tiles: nowView.tiles,
      status: nowView.status,
      chart,
      prose,
      facts,
    });
  }

  /**
   * What a day's card is headed with: the date as the title and its weekday as a badge (one
   * line next to "Today" and ‹ ›), its bounds, and the hour labels of its chart (every third)
   */
  _dayHead(date) {
    const { zone, hourName, hourTag } = this._renderInfo;
    const calendar = homeCalendar(this._hass);
    const noon = new Date(`${date}T12:00:00Z`);
    const [start, end] = dayBounds(date, zone);
    return {
      title: capitalize(calendar.dayMonth.format(noon)),
      weekday: capitalize(calendar.weekday.format(noon)),
      start,
      end,
      label: (slot) => {
        const tag = hourTag(slot.start);
        // Every third hour, and both passes of a repeated one
        return Number(hourName(slot.start)) % 3 === 0 || tag !== hourName(slot.start) ? tag : "";
      },
    };
  }

  /**
   * Tomorrow before its prices are in, opened like a day: when they usually come, and its tiles
   * and hours as empty placeholders. Once the prices arrive, the window shows the day itself
   */
  _openPendingDay(index, opener, info) {
    const { t, averageKind } = this._renderInfo;
    const head = this._dayHead(info.day.date);
    // Its hours as empty slots: no price is known for any of them yet
    const slots = [];
    for (let at = head.start; at < head.end; at += HOUR_MS) {
      slots.push({ start: at, end: Math.min(at + HOUR_MS, head.end), price: null, level: undefined });
    }
    const todayInfo = this._dayDetails.find((d) => d.isToday);
    const format = (todayInfo && todayInfo.format) || priceFormatter(this._hass, []);
    // Tomorrow's own tiles, as placeholders: the same as once its prices are in, still empty
    const tiles = [t.day_reference[averageKind], t.day_details.cheapest_hour.other].map((label) => ({
      label,
      value: "–",
      note: t.detail.unknown,
      placeholder: true,
    }));
    this._showDetailCard({
      title: head.title,
      opener,
      nav: { type: "day", index },
      shown: { type: "day", key: info.day.date },
      hero: {
        message: t.detail.pending.title,
        level: undefined,
        tags: [{ text: info.name }, { text: head.weekday }],
      },
      tiles,
      chart: this._zoomChart(slots, {
        format,
        dense: true,
        empty: true,
        label: head.label,
        bands: this._partBands(slots),
      }),
      prose: [t.detail.pending.prose],
      facts: {},
    });
  }

  /**
   * One hour or part of the day in detail: zoomed in (the quarter hours of an hour, the hours
   * of a part of the day; what isn't known yet as gaps), how the price moves within it and
   * whether waiting pays, and the facts: average and median, range, against the day and now,
   * the day's low or high and periods in it.
   */
  _openDetails(index, opener) {
    const info = this._details && this._details[index];
    if (!info) return;
    const {
      t,
      unit,
      clock,
      zone,
      averageKind,
      average,
      now,
      hours,
      parts,
      days,
      hourName,
      hourTag,
      nowPrice,
      currentQuarter,
      formatNowFor,
    } = this._renderInfo;
    const { key } = average;
    const { block, strip } = info;
    // The time running now leads with the price of this very quarter hour; the block's average
    // moves to a tile below, so the two can't be mistaken for each other
    const live = info.isNow && currentQuarter ? currentQuarter : undefined;
    const { format, current } = strip;
    const ranged = info.kind === "parts";
    // An hour's quarter hours (and the price of the one running) are shown as they are, not
    // rounded: their small differences are what the chart and the percentages are about. The
    // hour's own figures (average, range, day) keep the section's rounding
    const quarterFormat = fixedPriceFormat(this._hass, ...EXACT_DECIMALS);
    // The format of what is a quarter hour there: exact, in an hour's details
    const slotFormat = ranged ? format : quarterFormat;
    // The current price as this section shows it (its own decimals)
    const formatNow = ranged ? formatNowFor("day_parts", format) : slotFormat;
    const language = this._hass.language;
    const d = t.details;
    const x = t.detail;
    const p = x.prose;
    const start = Date.parse(block.start);
    const end = Date.parse(block.end);
    const calendar = homeCalendar(this._hass);
    const dayName = calendar.weekday.format(new Date(start));
    const when = ranged ? this._partName(block) : dayName;
    // A short title that fits one line next to ‹ ›: an hour's time, a part's name. The rest
    // (now, the weekday or the part's hours) goes in badges on top
    const title = ranged ? capitalize(when) : info.time;

    // Zoomed in: quarter hours of an hour; hours of a part of the day, a partly known one up
    // to its usual end (the unknown rest as gaps)
    let slots;
    if (ranged) {
      const usual = this._dayPartHours[block.part];
      const length = usual ? ((usual[1] - usual[0] + 24) % 24 || 24) * HOUR_MS : end - start;
      slots = this._slots(start, info.partial ? start + length : end, HOUR_MS);
    } else {
      slots = this._slots(start, end, QUARTER_MS);
    }
    const known = slots.filter((s) => typeof s.price === "number");
    // A quarter hour picked belongs to its hour: another time shown drops it
    const pickKey = `${info.kind}|${block.start}`;
    if (this._picked && this._picked.key !== pickKey) this._picked = undefined;
    const picked = this._picked && this._picked.start;
    const shortClock = calendar.clock;
    const chart = this._zoomChart(slots, {
      format: slotFormat,
      reference: info.reference,
      label: (slot, i, isNow) =>
        ranged ? hourTag(slot.start) : isNow ? t.now : shortClock.format(new Date(slot.start)),
      drill: ranged ? (slot) => this._hourDetail(slot.start) : undefined,
      // A quarter hour of an hour can be picked: what it costs against the hour, the day and now
      pick: ranged ? undefined : { selected: picked },
    });
    // The pick changes only the chart's columns and this line, in place (see _pick)
    this._pickContext = ranged
      ? undefined
      : { slots, format: slotFormat, baseFormat: format, block, reference: info.reference, current };
    const pickedSlot = slots.find((slot) => slot.start === picked && typeof slot.price === "number");
    if (!ranged) chart.html += `<div class="zpick" aria-live="polite">${this._pickLine(pickedSlot)}</div>`;

    const reference = info.reference;
    const hasReference = typeof reference === "number" && reference !== 0 && typeof block[key] === "number";
    // Under the big number what it is like itself (its range; "now": how long it applies)
    let sub = "";

    const prose = [];
    const isPast = end <= now;
    // Still to come of a running hour or part: what the advice can be about
    const ahead = known.filter((s) => s.end > now);
    if (isPast) prose.push(ranged ? p.past_part : p.past_hour);
    // The clocks change in it: an hour that occurs twice or is skipped
    const change = clockChange(start, end, calendar.zone, !ranged);
    if (change) {
      // Summer time first, then standard time, each with its abbreviation: "summer time (CEST)".
      // A repeated hour is one of the two passes, the other is an hour away
      const second = !ranged && repeatMark(start, calendar.zone) === REPEAT_MARKS.second;
      const before = ranged ? start : second ? start - HOUR_MS : start;
      const after = ranged ? end - 1 : second ? start : start + HOUR_MS;
      const names = {
        first: `${t.summer_time} (${calendar.zoneName(before)})`,
        second: `${t.standard_time} (${calendar.zoneName(after)})`,
      };
      prose.push(
        fill(p[`clocks_${change}_${ranged ? "part" : "hour"}`], { ...names, time: clock.format(new Date(end)) })
      );
    }
    if (live) {
      // More expensive than the share of today's quarter hours that cost less, or cheaper than
      // those that cost more: whichever says more
      const dearer = live.cheaper >= live.dearer;
      const share = formatPercent(language, dearer ? live.cheaper : live.dearer, "never");
      prose.push(fill(x.now.rank[dearer ? "dearer" : "cheaper"], { percent: share }));
    }
    if (!ranged && known.length >= 2) {
      const first = known[0].price;
      const last = known[known.length - 1].price;
      const mean = aggregate(
        known.map((s) => s.price),
        "mean"
      );
      const change = mean ? (last - first) / Math.abs(mean) : 0;
      const values = { first: quarterFormat(first), last: quarterFormat(last), unit };
      prose.push(change > 0.03 ? fill(p.rises, values) : change < -0.03 ? fill(p.falls, values) : p.steady);
      const cheapest = cheapestOf(ahead, "price");
      // Not when the cheapest is the one running now: that's what the price on top says
      const spread = Math.max(...ahead.map((s) => s.price)) - (cheapest ? cheapest.price : 0);
      if (cheapest && cheapest.start > now && ahead.length > 1 && spread > 0.005) {
        prose.push(fill(p.cheapest_quarter, { time: clock.format(new Date(cheapest.start)) }));
      }
    }
    if (ranged && known.length >= 2) {
      const pool = ahead.length > 1 ? ahead : known;
      const cheap = cheapestOf(pool, "price");
      const dear = pool.reduce((top, s) => (s.price > top.price ? s : top));
      prose.push(
        fill(p.part_spread, {
          cheap: clock.format(new Date(cheap.start)),
          cheapPrice: format(cheap.price),
          dear: clock.format(new Date(dear.start)),
          dearPrice: format(dear.price),
          unit,
        })
      );
    }
    if (info.partial) prose.push(fill(p.partial, { time: info.until }));
    if (info.chip) prose.push(`${info.chip.text}.`);
    // Whether waiting pays: the cheapest later hour or part of the day, by the mean like the chips
    if (!isPast && block.price_mean > 0) {
      const later = cheapestOf(
        (ranged ? parts : hours).filter((b) => Date.parse(b.start) >= end && typeof b.price_mean === "number"),
        "price_mean"
      );
      const change = later ? (shownChange(later.price_mean, block.price_mean, format) ?? 0) : 0;
      if (later && change <= -0.05) {
        prose.push(
          fill(p.later, { when: this._whenText(later, ranged), percent: formatPercent(language, -change, "never") })
        );
      } else if (later && !info.chip) {
        prose.push(p.nothing_cheaper[ranged ? "part" : "hour"]);
      }
    }

    const facts = { times: [], prices: [], periods: [], compare: [] };
    if (ranged) {
      facts.times.push([
        x.facts.time,
        `${info.time}${info.partial ? ` (${t.partial_note.replace("{time}", info.until)})` : ""}`,
      ]);
    }
    facts.prices.push(
      [x.facts.mean, `${format(block.price_mean)} ${unit}`],
      [x.facts.median, `${format(block.price_median)} ${unit}`]
    );
    if (typeof block.price_min === "number") {
      facts.prices.push([
        ranged ? x.facts.range : x.facts.quarters,
        `${format(block.price_min)}–${format(block.price_max)} ${unit}`,
      ]);
    }
    if (ranged && known.length) {
      const cheap = cheapestOf(known, "price");
      facts.times.push([x.facts.cheapest_hour, `${timeRange(clock, cheap.start, cheap.end)} · ${format(cheap.price)}`]);
    }
    // (Running now, the tile above says it)
    if (hasReference && !live) {
      facts.compare.push([x.facts.vs_day[averageKind], this._difference(format, block[key], reference)]);
    }
    if (!info.isNow && current && typeof block[key] === "number" && current[key] > 0) {
      facts.compare.push([x.facts.vs_now, this._difference(format, block[key], current[key])]);
    }
    for (const e of info.here) {
      facts.times.push([t[`day_${e.kind}`], `${clock.format(new Date(e.at))} · ${format(e.price)} ${unit}`]);
    }
    for (const period of info.touching) facts.periods.push([d.period[period.k], timeRange(clock, period.a, period.b)]);
    if (live) {
      const { energy, tax } = this._renderInfo.priceParts;
      // Parts of the current price: with its decimals
      if (typeof energy === "number") facts.prices.push([x.now.energy, `${formatNow(energy)} ${unit}`]);
      if (typeof tax === "number") facts.prices.push([x.now.tax, `${formatNow(tax)} ${unit}`]);
    }
    // Each tile's note says how the big number lies from the tile's value: here the price now
    // from the hour's (or part's) average
    const nowNote =
      live && typeof block[key] === "number" && block[key] !== 0
        ? `${t.now} ${percentFrom(language, live.price, block[key], formatNow, format)}`
        : "";
    const nowView = live
      ? this._nowView(live, {
          format,
          block,
          ranged,
          reference,
          sub: nowNote,
          formatNow,
        })
      : {};
    if (!live) {
      // Like "now": what the big number is compared with in tiles of their own (the day's
      // average, the price now), each saying how far this hour or part lies from it; under the
      // big number its own range
      const n = x.now;
      const self = ranged ? n.this_part : n.this_hour;
      const share = (base, baseFormat = format) => percentFrom(language, block[key], base, format, baseFormat);
      nowView.tiles = [];
      if (hasReference) {
        // The level of the day this line is (none for yesterday's)
        const day = days.find((candidate) => candidate[key] === reference);
        nowView.tiles.push({
          label: t.day_reference[averageKind],
          value: `${format(reference)} ${unit}`,
          level: day && day.level,
          note: `${self} ${share(reference)}`,
        });
      }
      if (!info.isNow && typeof nowPrice === "number" && nowPrice !== 0 && typeof block[key] === "number") {
        nowView.tiles.push({
          label: t.now,
          value: `${formatNow(nowPrice)} ${unit}`,
          level: currentQuarter ? currentQuarter.level : current && current.level,
          note: `${self} ${share(nowPrice, formatNow)}`,
        });
      }
      if (typeof block.price_min === "number") {
        sub = `${ranged ? x.facts.range : x.facts.quarters} ${format(block.price_min)}–${format(block.price_max)} ${unit}`;
      }
    }

    this._showDetailCard({
      title,
      opener,
      nav: { type: "col", index },
      shown: { type: "col", kind: info.kind, key: block.start },
      hero: {
        label: live ? "" : average.label,
        caption: live && x.now.now_price,
        price: live ? formatNow(live.price) : format(block[key]),
        unit,
        level: live ? live.level || block.level : block.level,
        tags: [
          { text: info.isNow && t.now, now: true, live: true },
          { text: ranged ? info.time : capitalize(dayName) },
        ],
      },
      sub: live ? nowView.sub : sub,
      tiles: nowView.tiles,
      status: nowView.status,
      chart,
      prose,
      facts,
    });
  }

  /**
   * The line of a quarter hour picked in an hour's chart: its time, price and level, then how
   * it compares with the hour, the day and now, its rank in the day, and the day's low or high
   * or a period it falls in
   */
  _quarterLine(slot, { format, baseFormat, block, reference, current }) {
    const { t, unit, clock, now, average, averageKind, periods, extremes, quarters, dateOf, zone, nowPrice } =
      this._renderInfo;
    const language = this._hass.language;
    const pk = t.detail.pick;
    const vs = (template, base, againstFormat = baseFormat) => {
      const percent = percentFrom(language, slot.price, base, format, againstFormat);
      return percent ? fill(template, { percent }) : "";
    };
    // Its rank among the day's quarter hours, whichever way says more
    let rank = "";
    if (quarters) {
      // The day's quarter hours by position in the series (no date formatting per quarter)
      const [dayStart, dayEnd] = dayBounds(dateOf(slot.start), zone);
      const first = Math.max(0, Math.ceil((dayStart - quarters.start) / quarters.step));
      const stop = Math.min(quarters.prices.length, Math.ceil((dayEnd - quarters.start) / quarters.step));
      const prices = quarters.prices.slice(first, stop).filter((price) => typeof price === "number");
      if (prices.length > 1) {
        const cheaper = prices.filter((price) => price < slot.price).length / prices.length;
        const dearer = prices.filter((price) => price > slot.price).length / prices.length;
        rank =
          cheaper >= dearer
            ? fill(pk.rank.dearer, { percent: formatPercent(language, cheaper, "never") })
            : fill(pk.rank.cheaper, { percent: formatPercent(language, dearer, "never") });
      }
    }
    const isNow = slot.start <= now && now < slot.end;
    const notes = [
      vs(pk.vs_hour, block[average.key]),
      vs(pk.vs_day[averageKind], reference),
      !isNow &&
        (typeof nowPrice === "number"
          ? vs(pk.vs_now, nowPrice, format)
          : vs(pk.vs_now, current && current[average.key])),
      rank,
      ...extremesIn(extremes, slot.start, slot.end).map((e) => t[`day_${e.kind}`]),
      ...[...new Set(periodsTouching(periods, slot.start, slot.end).map((p) => p.k))].map((k) => t.details.period[k]),
    ].filter(Boolean);
    return `<div class="zpick-head"><span>${timeRange(clock, slot.start, slot.end)}</span><span class="zpick-price">${format(
      slot.price
    )} ${unit}</span>${
      slot.level ? levelTag(t, slot.level, "zpick-level") : ""
    }</div>${notes.length ? `<div class="zpick-notes">${notes.join(" · ")}</div>` : ""}`;
  }

  // A card drawing something else from the same data (the now card) does so here and says true
  _renderStandalone() {
    return false;
  }

  // Whether tapping this section opens details (on unless its hide_details is set)
  _tapDetails(section) {
    return !this._sections[section].hide_details;
  }

  // A button can't contain buttons: with columns or days opening details, the card isn't one,
  // so keyboard and screen reader users get its action as a button of its own
  _focusActionNeeded() {
    return (
      !this._config.action_button && this._hasAction() && this._config.show.some((section) => this._tapDetails(section))
    );
  }

  // Whether the card's actions run in the now section only (its action zone, as the chart card's
  // head): a now section beside others (not the now card, which is all now)
  _actionZone() {
    const { show } = this._config;
    return show.includes("now") && show.length > 1;
  }

  // Whether the now section takes the card's actions (it's then a button, even without details)
  _nowTakesActions() {
    return this._actionZone() && !this._config.action_button && this._hasAction();
  }

  // The card's surface reacts (pointer, hover) while it runs an action and has no button for it;
  // it's a button for screen readers only when nothing inside opens details. With a now section
  // that section is the button instead (see _actionZone)
  _updateInteractive(card) {
    const interactive = !this._config.action_button && this._hasAction() && !this._nowTakesActions();
    card.classList.toggle("is-interactive", interactive);
    if (interactive && !this._focusActionNeeded()) {
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
    } else {
      card.removeAttribute("role");
      card.removeAttribute("tabindex");
    }
  }
}
