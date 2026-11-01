/**
 * Dashboard cards shipped with the Tibber Prices integration: the entry module, which registers
 * the cards and the tile feature (the editors register themselves when the first one is asked
 * for, see loadEditors in base.js).
 *
 * Loaded into every frontend by the integration itself (frontend/__init__.py), so there is
 * nothing to install. Plain web components without dependencies or a build step: the only
 * interface to Home Assistant is the `hass` object, which keeps the cards independent of
 * frontend internals. The modules import each other by relative path; the integration serves
 * them under a URL with its version, so an update never mixes old and new modules.
 *
 * Each module imports only from those before it: util → time → data → ui → config → strings,
 * styles → base → the cards (forecast → now, chart → energy) → this entry; the tile feature
 * (outlook-feature) needs only util to config and strings. The editors (editors.js) come after
 * the cards and are loaded on demand only, by import() from base.js.
 */

import { FEATURE_NAMES, languageStrings } from "./strings.js";
import { TibberPricesCardWindow } from "./base.js";
import { TibberPricesForecastCard } from "./forecast-card.js";
import { TibberPricesNowCard } from "./now-card.js";
import { TibberPricesChartCard } from "./chart-card.js";
import { TibberPricesEnergyCard } from "./energy-card.js";
import { TibberPricesOutlookFeature } from "./outlook-feature.js";

// Named so the browser fetches every module right after this one, not one level deeper at a time
import "./util.js";
import "./time.js";
import "./data.js";
import "./ui.js";
import "./config.js";
import "./styles.js";

/**
 * Registering the elements. This script is loaded by the integration while Home Assistant's
 * frontend starts, and the frontend swaps window.customElements for a scoped registry early on.
 * A definition made before the swap stays in the old registry, which HA no longer asks: the card
 * would show as an error until the page is loaded again. So register now, and again until the
 * registry in use also holds HA's own ha-card: then it's the final one, and ours are in it.
 */
function registerElements() {
  if (!customElements.get("tibber-prices-forecast-card")) {
    customElements.define("tibber-prices-forecast-card", TibberPricesForecastCard);
  }
  if (!customElements.get("tibber-prices-now-card")) {
    customElements.define("tibber-prices-now-card", TibberPricesNowCard);
  }
  if (!customElements.get("tibber-prices-chart-card")) {
    customElements.define("tibber-prices-chart-card", TibberPricesChartCard);
  }
  if (!customElements.get("tibber-prices-energy-card")) {
    customElements.define("tibber-prices-energy-card", TibberPricesEnergyCard);
  }
  if (!customElements.get("tibber-prices-card-window")) {
    customElements.define("tibber-prices-card-window", TibberPricesCardWindow);
  }
  if (!customElements.get("tibber-prices-outlook-feature")) {
    customElements.define("tibber-prices-outlook-feature", TibberPricesOutlookFeature);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "tibber-prices-forecast-card")) {
    window.customCards.push({
      type: "tibber-prices-forecast-card",
      name: "Tibber Prices Forecast",
      description: "The coming hours and parts of the day with price level and average price, like a weather forecast.",
      preview: true,
      documentationURL: "https://jpawlowski.github.io/hass.tibber_prices/user/dashboard-cards#forecast-card",
    });
  }
  if (!window.customCards.some((card) => card.type === "tibber-prices-now-card")) {
    window.customCards.push({
      type: "tibber-prices-now-card",
      name: "Tibber Prices Now",
      description:
        "The current price on the day's scale and what to make of it: as a tile, a gauge or a clock of the coming twelve hours.",
      preview: true,
      documentationURL: "https://jpawlowski.github.io/hass.tibber_prices/user/dashboard-cards#now-card",
    });
  }
  if (!window.customCards.some((card) => card.type === "tibber-prices-chart-card")) {
    window.customCards.push({
      type: "tibber-prices-chart-card",
      name: "Tibber Prices Chart",
      description:
        "The price curve of the outlook, today, tomorrow or both days, in quarter hours or hours: drag across it to read every price.",
      preview: true,
      documentationURL: "https://jpawlowski.github.io/hass.tibber_prices/user/dashboard-cards#chart-card",
    });
  }
  if (!window.customCards.some((card) => card.type === "tibber-prices-energy-card")) {
    window.customCards.push({
      type: "tibber-prices-energy-card",
      name: "Tibber Prices Energy",
      description:
        "The price curve with the solar forecast and production, the home battery and more of your Energy dashboard on top, to see where cheap hours and your energy meet.",
      preview: true,
      documentationURL: "https://jpawlowski.github.io/hass.tibber_prices/user/dashboard-cards#energy-card",
    });
  }
  window.customCardFeatures = window.customCardFeatures || [];
  if (!window.customCardFeatures.some((feature) => feature.type === "tibber-prices-outlook-feature")) {
    window.customCardFeatures.push({
      type: "tibber-prices-outlook-feature",
      name: languageStrings(FEATURE_NAMES),
      // Offered only for sensors that carry the outlook: the Current Electricity Price sensor
      isSupported: (hass, context) => {
        const stateObj = context && context.entity_id && hass.states[context.entity_id];
        return Boolean(stateObj && stateObj.attributes.outlook_hours);
      },
      configurable: false,
    });
  }
}

// Checks stop after a minute, for pages that never load HA's cards (e.g. a cast receiver)
const REGISTER_UNTIL = Date.now() + 60000;
(function registerWhenReady() {
  registerElements();
  if (!customElements.get("ha-card") && Date.now() < REGISTER_UNTIL) setTimeout(registerWhenReady, 50);
})();
