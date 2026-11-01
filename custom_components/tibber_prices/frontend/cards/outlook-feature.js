/**
 * tibber-prices-outlook-feature: the coming hours as a tile card feature. Add it to a tile of
 * the Current Electricity Price sensor ("Add feature" in the tile editor): a row of small bars
 * in the level colors, from the hour running now to six hours ahead. Works below the tile and
 * inline next to its name; time labels drop out when the row gets too narrow for them.
 */

import { averageOf, barBaseline, levelColor, priceFormatter } from "./util.js";
import { stringsFor } from "./strings.js";
import { validatePriceSource } from "./config.js";
import { priceState } from "./data.js";
import { homeCalendar } from "./time.js";

const FEATURE_STYLE = `
  :host { display: block; height: var(--feature-height, 42px); container-type: inline-size; }
  .row { display: flex; gap: 4px; height: 100%; }
  .col { flex: 1 1 0; min-width: 0; display: grid; grid-template-rows: 1fr 12px; row-gap: 2px; justify-items: center; }
  .graph { position: relative; width: 100%; max-width: 20px; }
  .bar { position: absolute; bottom: 0; left: 0; right: 0; min-height: 3px; border-radius: 3px;
         box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  .label { font-size: var(--ha-font-size-xs, 10px); line-height: 12px; color: var(--secondary-text-color);
           white-space: nowrap; font-variant-numeric: tabular-nums; }
  .now .label { color: var(--primary-text-color); font-weight: var(--ha-font-weight-bold, 600); }
  .empty { display: flex; align-items: center; height: 100%; font-size: var(--ha-font-size-s, 12px);
           color: var(--secondary-text-color); }
  /* Too narrow for labels (e.g. inline next to the tile name): an outline marks the hour now */
  @container (max-width: 180px) {
    .col { grid-template-rows: 1fr; }
    .label { display: none; }
    .now .bar { outline: 1.5px solid var(--secondary-text-color); outline-offset: 1px; }
  }
`;

const FEATURE_HOURS = 7;

export class TibberPricesOutlookFeature extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:tibber-prices-outlook-feature" };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    validatePriceSource(config);
    this._config = config;
    // Drawn again with the new options, also for the same state
    this._drawn = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  set stateObj(stateObj) {
    if (stateObj === this._stateObj) return;
    this._stateObj = stateObj;
    this._render();
  }

  _render() {
    if (!this._hass || !this._stateObj || !this._config) return;
    // Redraw only for a new state (state objects are replaced on change) or another language
    if (this.shadowRoot && this._drawn && this._drawn[0] === this._stateObj && this._drawn[1] === this._hass.language) {
      return;
    }
    this._drawn = [this._stateObj, this._hass.language];
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const t = stringsFor(this._hass);
    const now = Date.now();
    // The mean, like the forecast card by default (the tile feature has no settings of its own)
    const { key } = averageOf(t, "mean");
    // Now and six hours ahead: a tile has room for that, with readable labels (`price_source`
    // in YAML, like the cards: the energy price alone)
    const stateObj = priceState(this._hass, this._stateObj, this._config.price_source);
    const hours = (stateObj.attributes.outlook_hours || [])
      .filter((h) => Date.parse(h.end) > now && typeof h[key] === "number")
      .slice(0, FEATURE_HOURS);
    if (!hours.length) {
      this.shadowRoot.innerHTML = `<style>${FEATURE_STYLE}</style><div class="empty">${t.no_data}</div>`;
      return;
    }
    const prices = hours.map((h) => h[key]);
    // Like the forecast card: from a little below the lowest price (always below the highest)
    const low = barBaseline(prices);
    const high = Math.max(...prices);
    const format = priceFormatter(this._hass, prices);
    const { hourTag } = homeCalendar(this._hass);
    const unit = this._stateObj.attributes.unit_of_measurement || "";
    const columns = hours.map((h) => {
      const current = Date.parse(h.start) <= now;
      const label = current ? t.now : hourTag(Date.parse(h.start));
      const height = Math.max(((h[key] - low) / (high - low)) * 100, 6);
      const color = levelColor(h.level);
      const spoken = `${label}, ${t.levels[h.level] || h.level}, ${format(h[key])} ${unit}`;
      return `<div class="col${current ? " now" : ""}" role="listitem" aria-label="${spoken}">
        <div class="graph" aria-hidden="true"><div class="bar" style="height:${height}%;background:${color}"></div></div>
        <div class="label" aria-hidden="true">${label}</div>
      </div>`;
    });
    this.shadowRoot.innerHTML = `<style>${FEATURE_STYLE}</style><div class="row" role="list" aria-label="${t.hours}">${columns.join("")}</div>`;
  }
}
