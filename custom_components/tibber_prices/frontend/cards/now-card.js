/**
 * tibber-prices-now-card: "now" on its own, for a main dashboard. The same engine as the
 * forecast card (its data, details windows, actions, light and dark), drawn in one of three
 * styles: `tile` (one row like HA's tile card), `gauge` (the price on the day's scale) or
 * `clock` (the coming twelve hours around a dial). A tap opens the details of now; set a tap
 * action (e.g. navigate to a dashboard with more) and a tap runs that instead.
 */

import { firstHomeDevice } from "./util.js";
import { CONTENT_PATH, GESTURE_TAP_PATH } from "./ui.js";
import { EDITOR_STRINGS, STRINGS, languageStrings, stringsFor } from "./strings.js";
import { DEFAULTS, EDITOR_FIELDS, NOW_DECIMALS, SECTION_HIDES, marked, validateConfig } from "./config.js";
import { TibberPricesCardBase, loadEditors, validateWindowCards } from "./base.js";
import { TibberPricesForecastCard } from "./forecast-card.js";

const NOW_STYLES = ["tile", "gauge", "clock"];
// What a tap opens (without a tap action): the details of now, or the forecast card or the chart
// card in a window, set up under `forecast` or `chart` like the card on its own (its home is the
// now card's)
const NOW_TAP_OPENS = ["details", "forecast", "chart"];
// What the now card can leave out (its scale and price are what it is)
const NOW_CARD_HIDES = SECTION_HIDES.now.filter((value) => value === "verdict" || value === "trend");
const NOW_CARD_DEFAULTS = {
  style: "tile",
  price_unit: "auto",
  price_source: "total",
  average: "mean",
  appearance: "auto",
  tap_opens: "details",
  now_decimals: "entity",
};
// Rows in a sections view: the tile is one row like HA's; the round ones need a square
const NOW_ROWS = { tile: 1, gauge: 4, clock: 5 };

// Errors for config values the now card can't use; setConfig and the visual editor check the same
function validateNowConfig(config) {
  if (config.style && !NOW_STYLES.includes(config.style)) {
    throw new Error("`style` is `tile`, `gauge` or `clock`");
  }
  if (config.now_decimals !== undefined && !NOW_DECIMALS.includes(String(config.now_decimals))) {
    throw new Error("`now_decimals` is `entity` (as the price entity shows it) or 0 to 4");
  }
  if (config.hide && !(Array.isArray(config.hide) && config.hide.every((x) => NOW_CARD_HIDES.includes(x)))) {
    throw new Error(`\`hide\` lists details to leave out: ${NOW_CARD_HIDES.join(", ")}`);
  }
  if (config.tap_opens && !NOW_TAP_OPENS.includes(config.tap_opens)) {
    throw new Error("`tap_opens` is `details` (of now), `forecast` or `chart` (that card in a window)");
  }
  validateConfig(config);
}

export class TibberPricesNowCard extends TibberPricesForecastCard {
  // What a tap opens (tap_opens), and the chart card from the icon top right
  static windowCards = [
    { key: "forecast", when: (config) => config.tap_opens === "forecast" },
    { key: "chart", when: (config) => config.tap_opens === "chart" || Boolean(config.chart_button) },
  ];

  static assertConfig(config) {
    validateNowConfig(config);
    validateWindowCards(config);
  }

  setConfig(config) {
    TibberPricesCardBase.requireHome(config);
    TibberPricesNowCard.assertConfig(config);
    const options = { ...NOW_CARD_DEFAULTS, ...config };
    // The forecast card's engine with "now" as its only section
    super.setConfig({
      ...options,
      show: ["now"],
      layout: "detailed",
      now: { now_decimals: String(options.now_decimals), hide: options.hide || [] },
    });
  }

  getCardSize() {
    return NOW_ROWS[(this._config && this._config.style) || "tile"];
  }

  getGridOptions() {
    const style = (this._config && this._config.style) || "tile";
    if (style === "tile") return { columns: 6, rows: 1, min_columns: 4, min_rows: 1, max_rows: 1 };
    return { columns: 6, rows: NOW_ROWS[style], min_columns: 4, min_rows: NOW_ROWS[style] - 1 };
  }

  _renderStandalone(card, hoursStrip) {
    hoursStrip();
    card.classList.add("is-now-card");
    const html = this._nowHtml(this._config.style);
    this._setHidden(false);
    card.innerHTML = html || `<div class="empty">${stringsFor(this._hass).no_data}</div>`;
    this._refreshDetail();
    this._fadeAll();
    return true;
  }

  // A tap opens the details of now (or the forecast card), unless a tap action is set: then it
  // runs that
  _tapDetails() {
    return !this._configured("tap");
  }

  _openDetailsOf(element) {
    if (this._opens(this._config.tap_opens)) this._openInWindow(this._config.tap_opens, element);
    else super._openDetailsOf(element);
  }

  // A fixed height (rows set in a sections view) is filled, the dial as large as it fits;
  // otherwise the card takes the height its width gives
  _snapToGrid() {
    const card = this.shadowRoot && this.shadowRoot.querySelector("ha-card");
    if (!card) return;
    card.classList.toggle("is-fixed", Boolean(getComputedStyle(this).getPropertyValue("--row-size").trim()));
    if (this._config.style !== "tile" && !card.classList.contains("is-fixed")) super._snapToGrid();
  }

  static getConfigForm() {
    const e = languageStrings(EDITOR_STRINGS);
    const t = languageStrings(STRINGS);
    return {
      schema: [
        EDITOR_FIELDS.device(),
        {
          name: "style",
          required: true,
          selector: {
            select: {
              mode: "box",
              options: marked(e, NOW_STYLES, (value) => e[`style_${value}`], NOW_CARD_DEFAULTS.style),
            },
          },
        },
        {
          name: "content",
          type: "expandable",
          flatten: true,
          iconPath: CONTENT_PATH,
          schema: [
            EDITOR_FIELDS.priceUnit(e),
            EDITOR_FIELDS.priceSource(e),
            EDITOR_FIELDS.average(e),
            EDITOR_FIELDS.nowDecimals(e),
            EDITOR_FIELDS.appearance(e),
            {
              name: "hide",
              selector: {
                select: {
                  multiple: true,
                  mode: "list",
                  options: NOW_CARD_HIDES.map((value) => ({ value, label: e.hide_option[value] })),
                },
              },
            },
          ],
        },
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
                  options: marked(e, NOW_TAP_OPENS, (value) => e[`tap_opens_${value}`], NOW_CARD_DEFAULTS.tap_opens),
                },
              },
            },
            ...EDITOR_FIELDS.chartButton(),
            EDITOR_FIELDS.windowWidth(e),
            ...EDITOR_FIELDS.gestures("now_tap_action_help"),
          ],
        },
      ],
      computeLabel: (schema) => e[schema.name] || t[schema.name],
      computeHelper: (schema) => e[schema.helper || `${schema.name}_help`],
      assertConfig: (config) => TibberPricesNowCard.assertConfig(config),
    };
  }

  static getStubConfig(hass) {
    return { device_id: firstHomeDevice(hass), style: NOW_CARD_DEFAULTS.style };
  }

  static async getConfigElement() {
    await loadEditors();
    return document.createElement("tibber-prices-now-card-editor");
  }

  static configDefaults() {
    return {
      ...NOW_CARD_DEFAULTS,
      hide: [],
      chart_button: false,
      chart_icon: DEFAULTS.chart_icon,
      window_width: DEFAULTS.window_width,
    };
  }
}
