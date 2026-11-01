/**
 * tibber-prices-energy-card: the chart card with the solar forecast and production, the home
 * battery and the grid of the Energy dashboard on top of the prices, to see where cheap and sunny
 * hours meet. All of it comes from what the Energy dashboard knows (its solar sources and the
 * forecast integrations it has picked), so there is nothing to set up.
 * With more than one curve there is no area below the prices (they would hide each other), and the
 * solar curves have an axis of their own at the right.
 */

import {
  HOUR_MS,
  QUARTER_MS,
  fill,
  formatPercent,
  lowerFirst,
  numberLocale,
  storeValue,
  storedValue,
  timeRange,
} from "./util.js";
import { STRINGS, languageStrings } from "./strings.js";
import { dayBounds } from "./time.js";
import { loadEditors } from "./base.js";
import {
  CHART_DEFAULT_VIEWS,
  CHART_SINGLE_DAY_VIEWS,
  CHART_VIEW_DEFAULTS,
  TibberPricesChartCard,
  chartViews,
  hashText,
  localFloor,
} from "./chart-card.js";

const SOLAR_MODES = ["power", "energy"];
const SOLAR_REFRESH_MS = 5 * 60000;
const SOLAR_RETRY_MS = 60000;
// The right axis: its numbers, then its title (the unit), read from the top down
const SOLAR_AXIS_NUMBERS = 34;
const SOLAR_AXIS_ROOM = SOLAR_AXIS_NUMBERS + 22;
const SOLAR_SUN_ROOM = 18;
// Sunrise and sunset, a horizon with half a sun and an arrow up or down, drawn on a 16 px grid
const SOLAR_SUN_ICONS = {
  rise: "M1.5 12.5h13M4.5 12.5a3.5 3.5 0 0 1 7 0M2.5 8.5l1 1M13.5 8.5l-1 1M8 6.5V1.5M6 3.5l2-2 2 2",
  set: "M1.5 12.5h13M4.5 12.5a3.5 3.5 0 0 1 7 0M2.5 8.5l1 1M13.5 8.5l-1 1M8 1.5V6.5M6 4.5l2 2 2-2",
};
const SOLAR_SUN_COLORS = ["#f9a825", "#ffca28"];
// [light, dark]: the price is one neutral color, so the forecast (violet, dashed) and the
// production (orange, as the Energy dashboard draws solar) stand apart from it and from each other;
// never green or red, which are the best and peak price periods' under the chart
const SOLAR_COLORS = {
  forecast: ["#8e24aa", "#ce93d8"],
  actual: ["#e65100", "#ffa726"],
  // The home battery: into it indigo, out of it cyan
  charge: ["#3949ab", "#9fa8da"],
  discharge: ["#00acc1", "#4dd0e1"],
  // The grid: what is bought brown, what is fed in magenta
  grid_import: ["#6d4c41", "#bcaaa4"],
  grid_export: ["#c2185b", "#f48fb1"],
};
// What the sun decides (shown between sunrise and sunset only) and what was measured (never later
// than now); the battery is measured, and runs at night too
const SOLAR_SUN_KINDS = ["forecast", "actual"];
const SOLAR_MEASURED = ["actual", "charge", "discharge", "grid_import", "grid_export"];
// The curves there can be data for, in the order of the legend
const SOLAR_KINDS = ["forecast", ...SOLAR_MEASURED];
// The price as the backdrop of the solar curves: the text color, muted
const SOLAR_PRICE_COLOR = "color-mix(in srgb, var(--primary-text-color, #212121) 55%, transparent)";
// The production's area in the power mode, at its top (it fades out towards the bottom)
const SOLAR_FILL_OPACITY = 0.25;
const SOLAR_CURVES = ["price", ...SOLAR_KINDS];
// The legend's sections: a tap on one's name switches all its curves
const SOLAR_SECTIONS = [
  { key: "solar", kinds: ["forecast", "actual"] },
  { key: "battery", kinds: ["charge", "discharge"] },
  { key: "grid", kinds: ["grid_import", "grid_export"] },
];
// What is shown at first: the prices, the sun and what is bought (the battery and the export wait
// in the legend). Until tomorrow's prices are in, yesterday takes the place of tomorrow
const SOLAR_DEFAULTS = {
  energy_curves: ["price", "forecast", "actual", "grid_import"],
  energy_mode: "power",
  energy_mode_switch: true,
  tomorrow_pending: "yesterday",
};

// What fades while other curves are brought to the front (each carries its curve's name as a class)
const SOLAR_FADES =
  ".energy-line, .energy-casing, .energy-area, .energy-end, .energy-dot, .balloon:not(.merged), .balloon-line";
const SOLAR_BAR_STYLE = `
  .plot text.balloon-text { font-size: 12px; }
  .plot .balloon-line { stroke-width: 1.5; stroke-dasharray: 2 3; stroke-linecap: round; }
  .plot.has-solar path.line { stroke-width: 1.75; }
  .plot .energy-end rect { fill: var(--ha-card-background, var(--card-background-color, #fff)); fill-opacity: 0.9; stroke-width: 1.25; }
  .plot .energy-end text { font-size: 11px; font-weight: var(--ha-font-weight-medium, 500); fill: var(--primary-text-color); }
  .plot .energy-end { transition: opacity 0.12s; }
  .plot.is-reading .energy-end { opacity: 0.25; }
  .plot.no-price path.line, .plot.no-price .reference, .plot.no-price .reference-label,
  .plot.no-price .extreme-dot, .plot.no-price .extreme-label, .plot.no-price .cursor-halo,
  .plot.no-price .cursor-band:not(.energy-band), .plot.no-price .cursor-dot:not(.energy-dot) { display: none; }
  .plot.has-solar .cursor-line { display: none; }
  .readout.is-energy { min-height: 0; container-type: inline-size; }
  .readout.is-energy .main { display: flex; flex-direction: column; gap: 8px; }
  .energy-head button { border: 0; background: none; color: inherit; font: inherit; cursor: pointer; }
  .energy-hero { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 16px; font-size: 13px;
    color: var(--secondary-text-color); }
  .energy-hero b { color: var(--primary-text-color); font-size: 18px; font-weight: var(--ha-font-weight-bold, 600); }
  .energy-hero .energy-kpi.when b { font-size: 15px; }
  .energy-hero .spacer { flex: 1; }
  .energy-hero .better { color: var(--success-color, #43a047); }
  .energy-hero .worse { color: var(--warning-color, #ef6c00); }
  .energy-head button[data-curve] { display: inline-flex; align-items: center; gap: 6px; padding: 2px 4px; border-radius: 6px; }
  .energy-head button[data-curve][aria-pressed="false"] { opacity: 0.45; text-decoration: line-through; }
  .energy-head i { display: inline-block; flex: none; width: 16px; height: 0; border-top: 2px solid var(--swatch); }
  .energy-head i.forecast { border-top-style: dashed; }
  .energy-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
  .energy-tile { display: flex; flex-direction: column; gap: 2px; padding: 6px 10px 6px; border-radius: 10px;
    background: color-mix(in srgb, var(--tile) 9%, transparent); border-left: 3px solid var(--tile);
    font-size: 12px; color: var(--secondary-text-color); transition: background-color 0.15s; }
  .energy-tile:hover { background: color-mix(in srgb, var(--tile) 16%, transparent); }
  .energy-tile.is-off { background: rgba(127, 127, 127, 0.06); border-left-color: rgba(127, 127, 127, 0.35); }
  .energy-tile.is-off .tile-value { color: var(--secondary-text-color); }
  .energy-tile button.section { align-self: flex-start; padding: 0; font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color); }
  .energy-tile .tile-value { color: var(--primary-text-color); font-size: 17px; font-weight: var(--ha-font-weight-bold, 600);
    font-variant-numeric: tabular-nums; }
  .energy-tile .tile-value small { font-size: 12px; font-weight: normal; color: var(--secondary-text-color); }
  .energy-tile .tile-curves { display: flex; flex-wrap: wrap; gap: 0 8px; margin: 2px -4px 0; }
  /* Narrow (a phone): the tiles in one row, each its sum and its word, the curves as swatches */
  @container (max-width: 560px) {
    .energy-tiles { grid-template-columns: none; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 6px; }
    .energy-tile { padding: 4px 8px; }
    .energy-tile .tile-sub, .energy-tile .curve-name { display: none; }
    .energy-tile .tile-value { font-size: 15px; }
    .energy-tile .tile-value small { display: block; font-size: 11px; }
    .energy-tile .tile-curves { gap: 0; }
    .energy-tile .tile-curves i { width: 14px; border-top-width: 3px; }
    .energy-hero { font-size: 12px; gap: 2px 10px; }
    .energy-hero b { font-size: 15px; }
  }
  .plot .time-mark rect { fill: var(--primary-text-color); }
  .plot .time-mark text { fill: var(--ha-card-background, var(--card-background-color, #fff)); font-size: 11px;
    font-weight: var(--ha-font-weight-medium, 500); }
  .plot :is(${SOLAR_FADES}), .plot path.line { transition: opacity 0.15s; }
  .plot.has-emphasis :is(${SOLAR_FADES}), .plot.has-emphasis:not(.emph-price) path.line { opacity: 0.15; }
  ${SOLAR_CURVES.map((kind) => `.plot.emph-${kind} :is(${SOLAR_FADES}).${kind}`).join(", ")} { opacity: 1; }
  .energy-modes { display: flex; padding: 2px; border-radius: 13px; background: rgba(127, 127, 127, 0.15); }
  .energy-modes button { height: 22px; padding: 0 9px; border: 0; border-radius: 11px; background: none; color: inherit;
    font: inherit; cursor: pointer; }
  .energy-modes button[aria-pressed="true"] { background: var(--ha-card-background, var(--card-background-color, #fff));
    color: var(--primary-text-color); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }
`;

// The most of a value range as a few lines at round steps (1, 2, 2.5, 5 times a power of ten), from 0
function solarAxis(max, count) {
  if (!(max > 0)) return { high: 1, ticks: [0, 1] };
  const raw = max / count;
  const base = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * base).find((s) => s >= raw);
  const ticks = [];
  for (let value = 0; value < max + step * 0.999; value += step) ticks.push(Math.round(value * 1000) / 1000);
  return { high: ticks[ticks.length - 1], ticks };
}

// Sunrise and sunset of a day at a place (ms; undefined where the sun doesn't rise or set), by the
// sunrise equation: solar noon from the mean anomaly and the equation of the center, then the hour
// angle of the sun's upper edge at the horizon (-0.833°, with refraction). Good to a minute or two
function sunTimes(dayStart, dayEnd, latitude, longitude) {
  const rad = Math.PI / 180;
  const julian = (time) => time / 86400000 + 2440587.5;
  // (From the middle of the local day, which on the days the clocks change is not 12 hours in)
  const middle = (dayStart + dayEnd) / 2;
  const n = Math.round(julian(middle) - 2451545 + 0.0008);
  const mean = (357.5291 + 0.98560028 * (n - longitude / 360)) % 360;
  const center = 1.9148 * Math.sin(mean * rad) + 0.02 * Math.sin(2 * mean * rad) + 0.0003 * Math.sin(3 * mean * rad);
  const lambda = (mean + center + 180 + 102.9372) % 360;
  const noon = 2451545 + (n - longitude / 360) + 0.0053 * Math.sin(mean * rad) - 0.0069 * Math.sin(2 * lambda * rad);
  const declination = Math.asin(Math.sin(lambda * rad) * Math.sin(23.4397 * rad));
  const cosine =
    (Math.sin(-0.833 * rad) - Math.sin(latitude * rad) * Math.sin(declination)) /
    (Math.cos(latitude * rad) * Math.cos(declination));
  if (cosine > 1 || cosine < -1) return undefined;
  const angle = Math.acos(cosine) / rad / 360;
  const at = (j) => (j - 2440587.5) * 86400000;
  // The day it falls on, whatever day the equation picked: within half a day of the day's middle
  const inDay = (time) => time - Math.round((time - middle) / 86400000) * 86400000;
  return { rise: inDay(at(noon - angle)), set: inDay(at(noon + angle)) };
}

// The part of a line (points [time, value] joined by straight lines) between two moments, with the
// values at the cut found along the line
function clipLine(points, from, to) {
  const out = [];
  for (let i = 1; i < points.length; i++) {
    const [t0, v0] = points[i - 1];
    const [t1, v1] = points[i];
    const a = Math.max(t0, from);
    const b = Math.min(t1, to);
    if (!(a < b) || t1 === t0) continue;
    const at = (t) => v0 + (v1 - v0) * ((t - t0) / (t1 - t0));
    if (!out.length || out[out.length - 1][0] !== a) out.push([a, at(a)]);
    out.push([b, at(b)]);
  }
  return out;
}

// The unit a range of values is shown in, as the Energy dashboard picks it: W below 1 kW, MW from
// 1000 kW, else kW (energy: Wh, kWh, MWh); `factor` takes a value in kW(h) there
function solarScale(peak, energy) {
  const suffix = energy ? "Wh" : "W";
  if (peak > 0 && peak < 1) return { factor: 1000, unit: suffix };
  if (peak >= 1000) return { factor: 0.001, unit: `M${suffix}` };
  return { factor: 1, unit: `k${suffix}` };
}

// Decimals the lines of an axis need: as few as show every one of them as it is (2.5 needs one)
function solarDecimals(ticks) {
  return [0, 1, 2, 3].find((n) => ticks.every((tick) => Math.abs(Number(tick.toFixed(n)) - tick) < 1e-9)) ?? 3;
}

// A value in kW(h) with the unit that suits its size, e.g. "420 W", "1.8 kW"
const SOLAR_NUMBER_FORMATS = new Map();
function solarFormat(locale, value, { energy = false } = {}) {
  const { factor, unit } = solarScale(Math.abs(value), energy);
  const shown = value * factor;
  const digits = factor === 1000 || Math.abs(shown) >= 100 ? 0 : 2;
  // (Building an Intl format is the costly part: one per locale and digits)
  const key = `${locale}|${digits}`;
  if (!SOLAR_NUMBER_FORMATS.has(key)) {
    SOLAR_NUMBER_FORMATS.set(key, new Intl.NumberFormat(locale, { maximumFractionDigits: digits }));
  }
  return `${SOLAR_NUMBER_FORMATS.get(key).format(shown)} ${unit}`;
}

// Energy per clock hour (kWh, keyed by the hour's start) from the Energy dashboard's forecast:
// `wh_hours` has Wh per period at the timestamp where the period ENDS (Forecast.Solar: 607 Wh at
// 15:00 is the hour before it, the sun sets at 15:03), so a value belongs to the hour before its
// timestamp, and one at 15:03 to the hour of 15:00
function solarForecastHours(forecasts, zone) {
  const hours = new Map();
  for (const forecast of Object.values(forecasts || {})) {
    for (const [stamp, wh] of Object.entries((forecast && forecast.wh_hours) || {})) {
      const time = Date.parse(stamp);
      const energy = wh === null ? NaN : Number(wh);
      if (Number.isNaN(time) || !Number.isFinite(energy)) continue;
      const hour = localFloor(time - 1, HOUR_MS, zone);
      hours.set(hour, (hours.get(hour) || 0) + energy / 1000);
    }
  }
  return hours;
}

// Energy per hour produced (kWh) from the long-term statistics of the solar sources: their change
// per hour, which counts a meter that resets at midnight and one that runs on alike
function solarActualHours(statistics, ids, zone) {
  const hours = new Map();
  for (const id of ids) {
    for (const row of (statistics || {})[id] || []) {
      const time = typeof row.start === "number" ? row.start : Date.parse(row.start);
      // (A negative change is a meter that was replaced or a glitch: no value, so a gap, not a zero)
      if (Number.isNaN(time) || typeof row.change !== "number" || row.change < 0) continue;
      const hour = localFloor(time, HOUR_MS, zone);
      hours.set(hour, (hours.get(hour) || 0) + row.change);
    }
  }
  return hours;
}

// The Energy dashboard's data from `from` to `to` (ms): the solar forecast, and per measured curve
// its hours. Throws where it can't be had (no energy setup)
async function fetchSolar(hass, zone, from, to) {
  // Without an energy setup the call fails: no solar curves then, the card stays a price chart
  const prefs = await hass.callWS({ type: "energy/get_prefs" });
  const all = prefs.energy_sources || [];
  const sources = all.filter((source) => source.type === "solar");
  const batteries = all.filter((source) => source.type === "battery");
  const grids = all.filter((source) => source.type === "grid");
  const ids = {
    actual: sources.map((source) => source.stat_energy_from).filter(Boolean),
    // Into the battery is `stat_energy_to`, out of it `stat_energy_from`
    charge: batteries.map((source) => source.stat_energy_to).filter(Boolean),
    discharge: batteries.map((source) => source.stat_energy_from).filter(Boolean),
    // The grid: one connection each with its import and export meter (older Home Assistant
    // versions list them as `flow_from` / `flow_to` of one source)
    grid_import: grids
      .flatMap((source) => [source.stat_energy_from, ...(source.flow_from || []).map((f) => f.stat_energy_from)])
      .filter(Boolean),
    grid_export: grids
      .flatMap((source) => [source.stat_energy_to, ...(source.flow_to || []).map((f) => f.stat_energy_to)])
      .filter(Boolean),
  };
  const statisticIds = [...new Set(Object.values(ids).flat())];
  const hasForecast = sources.some((source) => (source.config_entry_solar_forecast || []).length);
  const [forecasts, statistics] = await Promise.all([
    hasForecast ? hass.callWS({ type: "energy/solar_forecast" }) : {},
    statisticIds.length
      ? hass.callWS({
          type: "recorder/statistics_during_period",
          start_time: new Date(from).toISOString(),
          end_time: new Date(to).toISOString(),
          statistic_ids: statisticIds,
          period: "hour",
          types: ["change"],
          units: { energy: "kWh" },
        })
      : {},
  ]);
  const solar = { forecast: solarForecastHours(forecasts, zone) };
  for (const kind of SOLAR_MEASURED) solar[kind] = solarActualHours(statistics, ids[kind], zone);
  return solar;
}

// The energy data, shared by every energy card of the page: the Energy dashboard is set up once per
// Home Assistant, so a second card, or the same card again after a change of dashboard, needn't ask
// anew. By time zone and stretch of days; an answer counts as long as a card's own one did (a
// failure for a shorter while), and cards asking at the same time share one request. Gives
// { at, solar }: when it was asked, and the data (undefined where it failed: a card keeps what it
// had). The data is shared, so cards only read it
const SOLAR_CACHE = new Map();

// The answer for that stretch still counting, at once (none while a request is under way)
function solarCached(zone, from, to) {
  const entry = SOLAR_CACHE.get(`${zone}|${from}|${to}`);
  const fresh = entry && !entry.pending && Date.now() - entry.at < (entry.solar ? SOLAR_REFRESH_MS : SOLAR_RETRY_MS);
  return fresh ? entry : undefined;
}

function solarData(hass, zone, from, to) {
  const key = `${zone}|${from}|${to}`;
  const entry = SOLAR_CACHE.get(key);
  if (entry && entry.pending) return entry.pending;
  const cached = solarCached(zone, from, to);
  if (cached) return Promise.resolve(cached);
  const keep = (solar) => {
    const answer = { at: Date.now(), solar };
    SOLAR_CACHE.set(key, answer);
    return answer;
  };
  const pending = fetchSolar(hass, zone, from, to).then(keep, () => keep(undefined));
  SOLAR_CACHE.delete(key);
  SOLAR_CACHE.set(key, { pending });
  // Only the last few stretches (a new day is a new one)
  while (SOLAR_CACHE.size > 4) SOLAR_CACHE.delete(SOLAR_CACHE.keys().next().value);
  return pending;
}

export class TibberPricesEnergyCard extends TibberPricesChartCard {
  setConfig(config) {
    // The defaults where a key is unset (an explicit undefined or null is unset too)
    const merged = { ...config };
    for (const [key, value] of Object.entries(SOLAR_DEFAULTS)) merged[key] ??= value;
    if (!SOLAR_MODES.includes(merged.energy_mode)) {
      throw new Error("`energy_mode` is `power` (kW per hour) or `energy` (kWh summed up over the day)");
    }
    const curves = merged.energy_curves;
    if (!(Array.isArray(curves) && curves.every((c) => SOLAR_CURVES.includes(c)))) {
      throw new Error(`\`energy_curves\` lists the curves shown at first: ${SOLAR_CURVES.join(", ")}`);
    }
    super.setConfig(merged);
    const key = `tibber-prices-energy:${hashText(JSON.stringify(config))}`;
    this._modeKey = `${key}:mode`;
    this._curvesKey = `${key}:curves`;
    this._storedMode = storedValue(this._modeKey);
    let stored;
    try {
      stored = JSON.parse(storedValue(this._curvesKey));
    } catch {
      stored = undefined;
    }
    // What the legend switched on and off last, else what the card is set to show at first
    this._visible = new Set(
      Array.isArray(stored) ? stored.filter((c) => SOLAR_CURVES.includes(c)) : this._config.energy_curves
    );
    this._emphasis = undefined;
    // Data still on its way for the old config is dropped, and a new load may start
    this._solar = undefined;
    this._solarAt = undefined;
    this._solarLoading = false;
    this._loadToken = undefined;
  }

  // Hours: the forecast and the production are hourly, so are the prices next to them (15 minutes
  // can be set per view again)
  static get viewDefaults() {
    return { ...CHART_VIEW_DEFAULTS, resolution: "hour" };
  }

  // The curves there is data for
  _dataKinds() {
    const solar = this._solar;
    return solar ? SOLAR_KINDS.filter((kind) => solar[kind].size) : [];
  }

  // The curves there is data for, all of them in the legend
  _availableSeries() {
    return this._dataKinds();
  }

  // Whether the forecast has hours of tomorrow: the sun's forecast comes long before tomorrow's
  // prices (around 13:00), and planning the day begins in the morning
  _forecastTomorrow() {
    const d = this._data;
    const solar = this._solar;
    if (!solar) return false;
    for (const hour of solar.forecast.keys()) if (hour >= d.tomorrowStart && hour < d.dayAfter) return true;
    return false;
  }

  // Tomorrow is shown once the forecast reaches it, its prices or not
  _tomorrowShown() {
    return super._tomorrowShown() || this._forecastTomorrow();
  }

  // A stretch without prices still has the forecast to show
  _drawsWithoutPrices() {
    return this._dataKinds().length > 0;
  }

  // The outlook reaches to the end of tomorrow where the forecast does (the price line ends with
  // the prices)
  _span(view, resolution, now) {
    const span = super._span(view, resolution, now);
    if (view !== "outlook" || !this._forecastTomorrow()) return span;
    return [span[0], Math.max(span[1], this._data.dayAfter)];
  }

  // Those of the curves with data the legend has on
  _shownSeries() {
    const on = this._visible;
    return this._availableSeries().filter((kind) => on.has(kind));
  }

  get _mode() {
    // The one picked last (a mode stored by an older version may be gone), else the card's setting
    return [this._storedMode, this._config.energy_mode].find((m) => SOLAR_MODES.includes(m));
  }

  _darkIndex() {
    return this._dark() ? 1 : 0;
  }

  // The legend's swatch of a curve: the price's line is the muted one it is drawn in
  _legendColor(kind) {
    return kind === "price" ? SOLAR_PRICE_COLOR : this._solarColor(kind);
  }

  _solarColor(kind) {
    return SOLAR_COLORS[kind][this._darkIndex()];
  }

  _rightRoom() {
    return this._availableSeries().length ? SOLAR_AXIS_ROOM : 0;
  }

  // A row under the hours for sunrise and sunset: why the curves stop and begin
  _footRoom() {
    return this._availableSeries().some((kind) => SOLAR_SUN_KINDS.includes(kind)) ? SOLAR_SUN_ROOM : 0;
  }

  // The price is the backdrop of the solar curves: one muted line, thinner than theirs
  _colors() {
    const colors = super._colors();
    if (!this._availableSeries().length) return colors;
    return { ...colors, line: { ...colors.line, single: SOLAR_PRICE_COLOR } };
  }

  // More than one curve: no area below the prices, and the prices in one color (their level is in
  // the line above and the tag, the colors are the solar curves')
  _fills() {
    return !this._availableSeries().length;
  }

  _style(view) {
    const style = super._style(view);
    return this._availableSeries().length ? { ...style, line: "single" } : style;
  }

  _styleSwitch() {
    return !this._availableSeries().length && super._styleSwitch();
  }

  // With two axes both say what they count: the price axis always names its unit
  _unitShown(place, short = false) {
    if (place === "axis" && this._availableSeries().length && this._data) return this._data.unit;
    return super._unitShown(place, short);
  }

  async _loadSolar() {
    const hass = this._hass;
    const d = this._data;
    if (!hass || !d || this._solarLoading) return;
    // Mostly the answer this card already has: nothing to wait for (this runs at every redraw)
    const cached = solarCached(d.zone, d.yesterdayStart, d.dayAfter);
    if (cached && cached.at === this._solarAt) return;
    this._solarLoading = true;
    const token = {};
    this._loadToken = token;
    // Shared with the other energy cards, which decides when to ask anew: mostly the answer this
    // card already has, then there's nothing to redraw
    const { at, solar } = await solarData(hass, d.zone, d.yesterdayStart, d.dayAfter);
    // A new config came in meanwhile: this answer is for the old one
    if (this._loadToken !== token) return;
    this._solarLoading = false;
    if (at === this._solarAt) return;
    this._solarAt = at;
    // A failed refresh keeps what was loaded before
    const views = this._views;
    if (solar) this._solar = solar;
    // The forecast may bring tomorrow's tab (before its prices): the tabs anew, else the chart
    if (views && chartViews(this._config, { tomorrowKnown: this._tomorrowShown() }).join() !== views.join()) {
      this._render();
    } else {
      this._refreshSolar();
    }
  }

  // The chart and the head after a change of the data, the curves or the mode
  _refreshSolar() {
    if (this._data) this._draw();
    this._renderHead();
  }

  // Sunrise and sunset (ms) of the day a moment falls in, from the home's location: the curves have
  // nothing to say outside them (no production, nothing expected); undefined where it can't be told
  // (no location, or a sun that doesn't rise or set), then the whole day counts. Kept per day
  _sunWindow(time) {
    const { latitude, longitude } = this._hass.config || {};
    if (typeof latitude !== "number" || typeof longitude !== "number") return undefined;
    const d = this._data;
    const date = d.dateOf(time);
    const key = `${latitude}|${longitude}|${date}`;
    const cache = (this._sunWindows ||= new Map());
    if (!cache.has(key)) {
      const [dayStart, dayEnd] = dayBounds(date, d.zone);
      const sun = sunTimes(dayStart, dayEnd, latitude, longitude);
      cache.set(key, sun ? [sun.rise, sun.set] : undefined);
    }
    return cache.get(key);
  }

  // Whether an hour lies wholly in the night (the hours sunrise or sunset falls in count as day)
  _nightHour(hour) {
    const sun = this._sunWindow(hour);
    return Boolean(sun) && (hour + HOUR_MS <= sun[0] || hour >= sun[1]);
  }

  // Where the forecast begins to show: after the production we have. The hours before have the
  // production or nothing (a gap in the recording stays a gap, the forecast isn't put in its place);
  // without any production data at all the whole forecast shows
  _forecastFrom() {
    const d = this._data;
    const { actual } = this._solar;
    if (!actual.size) return -Infinity;
    const hour = localFloor(Date.now(), HOUR_MS, d.zone);
    return actual.has(hour) ? hour + HOUR_MS : hour;
  }

  // The energy of a curve (kWh) between two moments, hours without data counting as nothing; the
  // hour `until` falls in counts as far as it has come
  _energyBetween(kind, from, until) {
    const hours = this._solar[kind];
    const hour = localFloor(until, HOUR_MS, this._data.zone);
    let total = 0;
    for (let at = from; at < hour; at += HOUR_MS) total += hours.get(at) || 0;
    return total + ((until - hour) / HOUR_MS) * (hours.get(hour) || 0);
  }

  // The value of a curve at a moment, in the mode (kW or kWh); undefined where
  // there is none. Power: the hour's kWh is its average kW, as a step like the prices. Energy: the
  // day's kWh summed up from midnight, in between the hours along the line; the forecast goes on from
  // what was produced where it begins
  _solarValue(kind, time) {
    const d = this._data;
    const hour = localFloor(time, HOUR_MS, d.zone);
    const hours = this._solar[kind];
    if (!hours || !hours.has(hour)) return undefined;
    if (SOLAR_MEASURED.includes(kind) && hour > Date.now()) return undefined;
    const from = kind === "forecast" ? this._forecastFrom() : -Infinity;
    if (hour < from) return undefined;
    const bySun = SOLAR_SUN_KINDS.includes(kind);
    if (this._mode === "power") return bySun && this._nightHour(hour) ? undefined : hours.get(hour);
    // The sun's curves only between sunrise and sunset
    const dayStart = dayBounds(d.dateOf(hour), d.zone)[0];
    const sun = bySun ? this._sunWindow(hour) : undefined;
    if (sun && (time < sun[0] || time > sun[1])) return undefined;
    const fraction = ((time - hour) / HOUR_MS) * hours.get(hour);
    if (kind !== "forecast") return this._energyBetween(kind, dayStart, hour) + fraction;
    // The forecast from where it begins (in this day) on top of what was produced up to there
    const begin = Math.max(from, dayStart);
    const produced = begin > dayStart ? this._energyBetween("actual", dayStart, begin) : 0;
    return produced + this._energyBetween("forecast", begin, hour) + fraction;
  }

  // The points of a series in the shown stretch: [time, value] each (power) or lines of them
  // (energy, one per stretch without a gap)
  _solarPoints(kind, from, to, now) {
    const d = this._data;
    const hours = this._solar[kind];
    const start = kind === "forecast" ? this._forecastFrom() : -Infinity;
    if (this._mode === "power") {
      const points = [];
      for (let hour = localFloor(from, HOUR_MS, d.zone); hour < to; hour += HOUR_MS) {
        if (SOLAR_MEASURED.includes(kind) && hour > now) break;
        if (hour < start || !hours.has(hour)) continue;
        if (!SOLAR_SUN_KINDS.includes(kind) || !this._nightHour(hour)) points.push([hour, hours.get(hour)]);
      }
      return { steps: true, points };
    }
    const lines = [];
    for (let at = from; at < to;) {
      const [dayStart, dayEnd] = dayBounds(d.dateOf(at), d.zone);
      at = dayEnd;
      // The sun's curves only between sunrise and sunset: before it nothing is produced, after it
      // nothing is expected
      const sun = SOLAR_SUN_KINDS.includes(kind) ? this._sunWindow(dayStart) : undefined;
      const clipped = (day) => day.map((line) => (sun ? clipLine(line, sun[0], sun[1]) : line));
      if (kind === "forecast") {
        // From where it begins, continuing the production of that day; days before it have none
        if (dayEnd <= start) continue;
        const begin = Math.max(start, dayStart);
        let total = begin > dayStart ? this._energyBetween("actual", dayStart, begin) : 0;
        const line = [[begin, total]];
        for (let hour = begin; hour < dayEnd; hour += HOUR_MS) {
          total += hours.get(hour) || 0;
          line.push([Math.min(hour + HOUR_MS, dayEnd), total]);
        }
        lines.push(...clipped([line]));
        continue;
      }
      // What was measured: a stretch of hours with data is one line, a gap ends it
      let total = 0;
      let line;
      const stretches = [];
      for (let hour = dayStart; hour < dayEnd && hour <= now; hour += HOUR_MS) {
        if (!hours.has(hour)) {
          line = undefined;
          continue;
        }
        if (!line) {
          line = [[hour, total]];
          stretches.push(line);
        }
        total += hours.get(hour);
        line.push([Math.min(hour + HOUR_MS, dayEnd), total]);
      }
      lines.push(...clipped(stretches));
    }
    return { steps: false, lines: lines.filter((line) => line.length > 1) };
  }

  // Sunrise and sunset of the days in view, in the row under the hours: a sunrise's time to the left
  // of its icon, a sunset's to the right (away from midday, so the two don't meet)
  _sunParts({ x, from, to, left, right, footY }) {
    if (!this._footRoom()) return [];
    const d = this._data;
    const color = SOLAR_SUN_COLORS[this._darkIndex()];
    const parts = [];
    for (let start = from; start < to;) {
      start = dayBounds(d.dateOf(start), d.zone)[1];
      const sun = this._sunWindow(start - 1);
      if (!sun) continue;
      for (const [kind, time] of [
        ["rise", sun[0]],
        ["set", sun[1]],
      ]) {
        if (time < from || time >= to) continue;
        const cx = x(time);
        const label = d.clock.format(new Date(time));
        const room = label.length * 6.4 + 4;
        let side = kind === "rise" ? -1 : 1;
        if (side < 0 && cx - 10 - room < left) side = 1;
        if (side > 0 && cx + 10 + room > right) side = -1;
        parts.push(
          `<g class="sun ${kind}"><title>${label}</title><path d="${SOLAR_SUN_ICONS[kind]}" transform="translate(${cx - 8} ${footY - 8})" style="fill:none;stroke:${color};stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round"></path><text x="${cx + side * 10}" y="${footY}" text-anchor="${side < 0 ? "end" : "start"}" dominant-baseline="central">${label}</text></g>`
        );
      }
    }
    return parts;
  }

  _extraParts({ x, from, to, left, right, top, bottom, now, defs, footY }) {
    this._loadSolar();
    this._frame = undefined;
    const sun = this._sunParts({ x, from, to, left, right, footY });
    const available = this._availableSeries();
    const plot = this._els.plot;
    plot.classList.toggle("has-solar", available.length > 0);
    plot.classList.toggle("no-price", available.length > 0 && !this._visible.has("price"));
    const series = this._shownSeries();
    const mode = this._mode;
    if (!available.length || !series.length) return { under: [], over: sun };
    const parts = [];
    const under = [];
    const wanted = Math.max(2, Math.floor((bottom - top) / 50));
    let y;
    let ticks;
    let high;
    let scale;
    const pointsOf = (kind) => ({ kind, ...this._solarPoints(kind, from, to, now) });
    const data = series.map(pointsOf);
    // The axis fits the highest value the view could show, of every curve there is data for,
    // whichever the legend has on: switching a curve on or off never moves the scale
    const values = available
      .map((kind) => (series.includes(kind) ? data.find((s) => s.kind === kind) : pointsOf(kind)))
      .flatMap((s) => (s.steps ? s.points.map((p) => p[1]) : s.lines.flatMap((l) => l.map((p) => p[1]))));
    const peak = Math.max(0, ...values);
    scale = solarScale(peak, mode === "energy");
    const axis = solarAxis(peak * scale.factor, wanted);
    high = axis.high;
    ticks = axis.ticks;
    y = (value) => bottom - ((value * scale.factor) / high) * (bottom - top);
    // The power mode fills the production below its steps, fading out towards the bottom (the
    // forecast has no area: it is what is still to come, and a line says it)
    if (mode === "power" && series.includes("actual")) {
      const color = this._solarColor("actual");
      defs.push(
        `<linearGradient id="solar-fill-actual" gradientUnits="userSpaceOnUse" x1="0" y1="${top}" x2="0" y2="${bottom}"><stop offset="0" style="stop-color:${color};stop-opacity:${SOLAR_FILL_OPACITY}"></stop><stop offset="1" style="stop-color:${color};stop-opacity:0"></stop></linearGradient>`
      );
    }
    for (const s of data) {
      const stroke = `fill:none;stroke:${this._solarColor(s.kind)};stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round`;
      // A casing in the card's color under each line: where curves cross, the one on top stays clear
      const casing =
        "fill:none;stroke:var(--ha-card-background, var(--card-background-color, #fff));stroke-width:5.5;stroke-opacity:0.85;stroke-linejoin:round;stroke-linecap:round";
      const dash = s.kind === "forecast" ? ";stroke-dasharray:6 4" : "";
      for (const points of s.steps ? [s.points] : s.lines) {
        if (!points.length) continue;
        let line = "";
        let area = "";
        if (s.steps) {
          // A run of hours is one step line and one area below it, down to the plot's bottom
          let runStart;
          points.forEach(([time, value], i) => {
            const end = x(Math.min(time + HOUR_MS, to));
            if (i && points[i - 1][0] + HOUR_MS === time) {
              line += `V${y(value)}H${end}`;
              area += `V${y(value)}H${end}`;
              return;
            }
            if (area) area += `V${bottom}H${runStart}Z`;
            runStart = x(Math.max(time, from));
            line += `M${runStart},${y(value)}H${end}`;
            area += `M${runStart},${bottom}V${y(value)}H${end}`;
          });
          if (area) area += `V${bottom}H${runStart}Z`;
        } else {
          line = points.map(([time, value], i) => `${i ? "L" : "M"}${x(time)},${y(value)}`).join("");
        }
        if (area && s.kind === "actual") {
          under.push(`<path class="energy-area actual" d="${area}" style="fill:url(#solar-fill-actual)"></path>`);
        }
        parts.push(`<path class="energy-casing ${s.kind}" d="${line}" style="${casing}"></path>`);
        parts.push(`<path class="energy-line ${s.kind}" d="${line}" style="${stroke}${dash}"></path>`);
      }
    }
    const digits = solarDecimals(ticks);
    for (const tick of ticks) {
      const label = tick.toFixed(digits);
      parts.push(`<text x="${right + 6}" y="${y(tick / scale.factor)}" dominant-baseline="middle">${label}</text>`);
    }
    // The axis says what it counts, like the price axis at the left: its unit, read from the top down
    parts.push(
      `<text class="axis-title" transform="translate(${right + SOLAR_AXIS_NUMBERS + 12} ${(top + bottom) / 2}) rotate(90)" text-anchor="middle" dominant-baseline="central">${scale.unit}</text>`
    );
    if (mode === "energy") parts.push(...this._endLabels({ data, x, y, left, right, top, bottom, now }));
    this._frame = { y };
    return { under, over: [...parts, ...sun] };
  }

  // The solar curves' points at the cursor's moment (the middle of its slot): where, what and in
  // which color. Kept for the slot until the next draw: the dots, the balloons and the chips ask
  _cursorPoints(slot) {
    if (!this._frame) return [];
    const memo = this._pointsMemo;
    if (memo && memo.frame === this._frame && memo.start === slot.start) return memo.points;
    const time = (slot.start + slot.end) / 2;
    const energy = this._mode === "energy";
    const locale = numberLocale(this._hass);
    // Ink on the balloon: light on the darker colors of light themes, dark on the lighter of dark ones
    const ink = this._dark() ? "#1b1b1b" : "#fff";
    const points = this._shownSeries().flatMap((kind) => {
      const value = this._solarValue(kind, time);
      if (value === undefined) return [];
      let text = solarFormat(locale, value, { energy });
      // What is bought costs: the hour's, or the day's so far
      const cost = kind === "grid_import" ? this._importCost(time) : undefined;
      if (cost) text += ` · ${this._costText(cost)}`;
      return [{ kind, color: this._solarColor(kind), ink, text, y: this._frame.y(value) }];
    });
    this._pointsMemo = { frame: this._frame, start: slot.start, points };
    return points;
  }

  // The mean price of an hour (its quarter hours that are known), null where none is: of the
  // prices shown, or of `prices` (the totals, d.totals)
  _hourPrice(hour, prices = this._data.prices) {
    const d = this._data;
    let sum = 0;
    let count = 0;
    for (let at = hour; at < hour + HOUR_MS; at += d.step) {
      const price = this._quarterPrice(at, prices);
      if (price === null) continue;
      sum += price;
      count += 1;
    }
    return count ? sum / count : null;
  }

  // What the energy bought from the grid cost, in the prices' unit (ct, €): in the power mode the
  // hour's, in the energy mode the day's up to the moment (the hour it is in as far as it has come).
  // Undefined without a price for the hour. The import only: what is fed in earns a different price.
  // Always at the total price, taxes and fees included, also while the energy price alone is shown:
  // that is what it cost
  _importCost(time) {
    const d = this._data;
    const hours = this._solar.grid_import;
    const hour = localFloor(time, HOUR_MS, d.zone);
    const price = this._hourPrice(hour, this._data.totals);
    if (price === null || !hours.has(hour)) return undefined;
    if (this._mode === "power") return hours.get(hour) * price;
    let total = ((time - hour) / HOUR_MS) * hours.get(hour) * price;
    for (let at = dayBounds(d.dateOf(hour), d.zone)[0]; at < hour; at += HOUR_MS) {
      const before = this._hourPrice(at, this._data.totals);
      if (before !== null && hours.has(at)) total += hours.get(at) * before;
    }
    return total;
  }

  // A sum of money in the prices' currency (38 ct), from 100 of a subunit on in the base one (1.24 €)
  _costText(cost) {
    const d = this._data;
    const locale = numberLocale(this._hass);
    let value = cost;
    let unit = d.unit;
    if (d.subunit && d.baseUnit && Math.abs(cost) >= 100) {
      value = cost / 100;
      unit = d.baseUnit;
    }
    const base = !(d.subunit && unit === d.unit);
    const digits = base ? 2 : Math.abs(value) < 10 ? 1 : 0;
    const text = new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: base ? 2 : 0 });
    return `${text.format(value)} ${unit.split("/")[0]}`;
  }

  // A dot on each solar curve at the cursor's moment. Where the prices are off, the shade of the
  // slot (otherwise from the bottom up to the price line) goes to the first curve that is left, in
  // the order of the legend: it has to end at a curve to say what it measures
  _extraCursor(slot, cx) {
    const points = this._cursorPoints(slot);
    const g = this._geo;
    let marks = "";
    if (!this._visible.has("price") && points.length && g) {
      const a = g.x(slot.start);
      const b = g.x(slot.end);
      const under = Math.min(points[0].y + 1.5, g.bottom);
      marks += `<rect class="cursor-band energy-band" x="${a}" y="${under}" width="${Math.max(b - a, 1)}" height="${g.bottom - under}"></rect>`;
    }
    return (
      marks +
      points
        .map(
          (p) =>
            `<circle class="cursor-dot energy-dot ${p.kind}" cx="${cx}" cy="${p.y}" r="4.5" style="fill:${p.color}"></circle>`
        )
        .join("")
    );
  }

  /**
   * A balloon at every point the cursor is on, the price's and the solar curves': in the color of its
   * curve and joined to its dot by a dashed line of that color, so which belongs to which is never
   * in doubt. The highest point's balloon goes above its dot, the lowest point's below it, one in
   * between to the side (where there is more room), each as near as the others allow: balloons
   * never cover each other or a dot, and no line crosses another line or a balloon, so a balloon
   * may move sideways and its line run at a slant. (The price's tag of the chart card sits in a row
   * at the top; with several curves each value stays with its curve.) The time is in the line above
   * the chart
   */
  _drawCursorTag(layer, slot, cx, inPeriod) {
    // Without solar data this is the chart card, with its tag in the top row
    if (!this._availableSeries().length) return super._drawCursorTag(layer, slot, cx, inPeriod);
    const g = this._geo;
    this._yieldSwitch(false);
    this._tagShown = undefined;
    this._drawTimeMark(layer, slot, cx);
    // (A copy: the solar points are kept for the slot, see _cursorPoints)
    const points = [...this._cursorPoints(slot)];
    if (slot.price !== null && this._visible.has("price")) {
      const unit = this._unitShown("tag");
      points.push({
        kind: "price",
        color: "var(--primary-text-color, #212121)",
        ink: "var(--ha-card-background, var(--card-background-color, #fff))",
        text: `${g.format(slot.price)}${unit ? ` ${unit}` : ""}`,
        y: g.y(slot.price),
      });
    }
    if (!points.length) return;
    points.sort((a, b) => a.y - b.y);
    // Three or more: a balloon each would be a crowd, one balloon lists them
    if (points.length > 2) {
      this._drawMergedBalloon(layer, points, cx);
      return;
    }
    const height = 22;
    const gap = 10;
    const dotRoom = 8;
    const bounds = [g.top - 2, g.bottom + 2];
    const ns = "http://www.w3.org/2000/svg";
    const lines = document.createElementNS(ns, "g");
    layer.append(lines);
    const balloons = points.map((point) => {
      const el = document.createElementNS(ns, "g");
      el.setAttribute("class", `cursor-tag balloon ${point.kind}`);
      el.innerHTML = `<rect class="cursor-pill" rx="11" height="${height}" style="fill:${point.color}"></rect><text class="cursor-price balloon-text" style="fill:${point.ink}">${point.text}</text>`;
      layer.append(el);
      return { point, el, text: el.querySelector("text") };
    });
    // Measured once all are in place: one layout, not one per balloon
    for (const b of balloons) b.width = (b.text.getComputedTextLength() || b.point.text.length * 7) + 22;
    const n = balloons.length;
    // Where a balloon of this width may go: [x, y] of its top left corner. Above and below its dot
    // (centered, then slanting to either side), beside it (centered on the dot's height, or lower
    // and higher), each further and further away
    const slots = (b, role) => {
      const { y } = b.point;
      const w = b.width;
      const off = Math.round(w * 0.55);
      const free = cx - g.left >= g.right - cx ? [-1, 1] : [1, -1];
      const side = (dir, dy) => [dir < 0 ? cx - 16 - w : cx + 16, y - height / 2 + dy];
      const above = (dx, extra) => [cx - w / 2 + dx, y - gap - height - extra];
      const below = (dx, extra) => [cx - w / 2 + dx, y + gap + extra];
      const out = [];
      const near = { above, below };
      const sides = (k) => free.flatMap((dir) => [side(dir, 0), side(dir, k), side(dir, -k)].slice(0, k ? 3 : 1));
      const order = {
        above: ["above", "side", "below"],
        below: ["below", "side", "above"],
        side: ["side", "above", "below"],
      }[role];
      // The way it is meant first (nearer, then further off, then slanting), the others after it
      for (const kind of order) {
        for (const extra of [0, 8, 16, 28, 44]) {
          if (kind === "side") out.push(...sides(extra));
          else for (const dx of [0, -off, off]) out.push(near[kind](dx, extra));
        }
      }
      return out;
    };
    // The line from the dot to the nearest point of the balloon, starting at the dot's edge
    const leader = (rect, dot) => {
      const tx = Math.min(Math.max(dot.x, rect.x), rect.x + rect.w);
      const ty = Math.min(Math.max(dot.y, rect.y), rect.y + height);
      const length = Math.hypot(tx - dot.x, ty - dot.y) || 1;
      const reach = Math.min(6, length);
      return [dot.x + ((tx - dot.x) / length) * reach, dot.y + ((ty - dot.y) / length) * reach, tx, ty];
    };
    const crosses = (a, b) => {
      const turn = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
      const [a1, a2, b1, b2] = [
        [a[0], a[1]],
        [a[2], a[3]],
        [b[0], b[1]],
        [b[2], b[3]],
      ];
      return turn(a1, a2, b1) !== turn(a1, a2, b2) && turn(b1, b2, a1) !== turn(b1, b2, a2);
    };
    const hitsRect = (line, rect) => {
      for (let t = 0.1; t < 1; t += 0.1) {
        const x = line[0] + (line[2] - line[0]) * t;
        const y = line[1] + (line[3] - line[1]) * t;
        if (x > rect.x - 1 && x < rect.x + rect.w + 1 && y > rect.y - 1 && y < rect.y + height + 1) return true;
      }
      return false;
    };
    const placed = [];
    // Whether a balloon's rectangle meets a box, with some air around
    const meets = (rect, x, y, w, h, air = 0) =>
      rect.x < x + w + air && x < rect.x + rect.w + air && rect.y < y + h + air && y < rect.y + height + air;
    const valid = (rect, line) =>
      rect.y >= bounds[0] &&
      rect.y + height <= bounds[1] &&
      rect.x >= g.left &&
      rect.x + rect.w <= g.right &&
      placed.every(
        (o) =>
          !meets(rect, o.rect.x, o.rect.y, o.rect.w, height, 3) &&
          !crosses(line, o.line) &&
          !hitsRect(line, o.rect) &&
          !hitsRect(o.line, rect)
      ) &&
      points.every((p) => !meets(rect, cx - dotRoom, p.y - dotRoom, dotRoom * 2, dotRoom * 2));
    balloons.forEach((b, index) => {
      // Highest above, lowest below, those in between beside their dot
      const role = index === 0 ? "above" : index === n - 1 ? "below" : "side";
      const candidates = slots(b, role).map(([x, y]) => {
        const rect = { x: Math.min(Math.max(x, g.left), g.right - b.width), y, w: b.width };
        return { rect, line: leader(rect, { x: cx, y: b.point.y }) };
      });
      const choice = candidates.find((c) => valid(c.rect, c.line)) || candidates[0];
      placed.push(choice);
      const { rect, line } = choice;
      const pill = b.el.querySelector("rect");
      pill.setAttribute("x", rect.x);
      pill.setAttribute("y", rect.y);
      pill.setAttribute("width", rect.w);
      b.text.setAttribute("x", rect.x + rect.w / 2);
      b.text.setAttribute("y", rect.y + height / 2 + 4.5);
      b.text.setAttribute("text-anchor", "middle");
      const stroke = b.point.kind === "price" ? "var(--secondary-text-color)" : b.point.color;
      lines.insertAdjacentHTML(
        "beforeend",
        `<line class="balloon-line ${b.point.kind}" x1="${line[0]}" y1="${line[1]}" x2="${line[2]}" y2="${line[3]}" style="stroke:${stroke}"></line>`
      );
    });
  }

  // The cursor's time as a mark on the time axis (the head holds the balance, not the moment); the
  // day before it where the view spans more than one
  _drawTimeMark(layer, slot, cx) {
    const g = this._geo;
    const d = this._data;
    const range = timeRange(d.clock, slot.start, slot.end);
    const text = CHART_SINGLE_DAY_VIEWS.includes(this._view)
      ? range
      : `${this._dayWord(d.dateOf(slot.start), slot.start)} ${range}`;
    const el = document.createElementNS("http://www.w3.org/2000/svg", "g");
    el.setAttribute("class", "time-mark");
    el.innerHTML = `<rect rx="9" height="18"></rect><text text-anchor="middle">${text}</text>`;
    layer.append(el);
    const label = el.querySelector("text");
    const width = (label.getComputedTextLength() || text.length * 6.2) + 16;
    const x = Math.min(Math.max(cx - width / 2, g.left - 20), g.right + 20 - width);
    const y = g.bottom + 4;
    const rect = el.querySelector("rect");
    rect.setAttribute("x", x);
    rect.setAttribute("y", y);
    rect.setAttribute("width", width);
    label.setAttribute("x", x + width / 2);
    label.setAttribute("y", y + 12.5);
  }

  /**
   * One balloon for all the points at the cursor, from the highest curve down (so the rows follow the
   * curves): a swatch in the curve's color, its name and its value. Beside the cursor, on the side
   * with more room, at the height of the points' middle, kept inside the plot
   */
  _drawMergedBalloon(layer, points, cx) {
    const g = this._geo;
    const s = this._t.energy;
    const ns = "http://www.w3.org/2000/svg";
    const row = 18;
    const pad = 8;
    const inner = 14;
    const el = document.createElementNS(ns, "g");
    el.setAttribute("class", "cursor-tag balloon merged");
    const card = "var(--ha-card-background, var(--card-background-color, #fff))";
    el.innerHTML =
      `<rect class="balloon-box" rx="10" style="fill:${card};fill-opacity:0.96;stroke:var(--secondary-text-color);stroke-opacity:0.45"></rect>` +
      points
        .map((p) => {
          // The curves in front stand out in the list too, the others step back
          const front = this._emphasis && this._emphasis.has(p.kind);
          const back = this._emphasis && !front ? ";opacity:0.4" : "";
          const label = front
            ? "fill:var(--primary-text-color);font-weight:var(--ha-font-weight-bold, 600)"
            : "fill:var(--secondary-text-color)";
          return `<circle r="4.5" style="fill:${p.color}${back}"></circle><text class="balloon-text label" style="${label}${back}">${s[p.kind]}</text><text class="balloon-text value" text-anchor="end" style="fill:var(--primary-text-color);font-weight:var(--ha-font-weight-${front ? "bold, 600" : "medium, 500"})${back}">${p.text}</text>`;
        })
        .join("");
    layer.append(el);
    const widest = (selector) =>
      Math.max(
        ...[...el.querySelectorAll(selector)].map((t) => t.getComputedTextLength() || t.textContent.length * 6.5)
      );
    const labelWidth = widest("text.label");
    const valueWidth = widest("text.value");
    const width = pad * 2 + inner + labelWidth + 12 + valueWidth;
    const height = pad * 2 + row * points.length;
    const bounds = [g.top - 2, g.bottom + 2];
    const left = cx - g.left >= g.right - cx;
    const x = Math.min(Math.max(left ? cx - 16 - width : cx + 16, g.left), g.right - width);
    const middle = points.reduce((sum, p) => sum + p.y, 0) / points.length;
    const y = Math.max(bounds[0], Math.min(middle - height / 2, bounds[1] - height));
    const box = el.querySelector("rect");
    box.setAttribute("x", x);
    box.setAttribute("y", y);
    box.setAttribute("width", width);
    box.setAttribute("height", height);
    const circles = el.querySelectorAll("circle");
    const labels = el.querySelectorAll("text.label");
    const values = el.querySelectorAll("text.value");
    points.forEach((_, i) => {
      const cy = y + pad + row * i + row / 2;
      circles[i].setAttribute("cx", x + pad + 4.5);
      circles[i].setAttribute("cy", cy);
      labels[i].setAttribute("x", x + pad + inner);
      labels[i].setAttribute("y", cy + 4.5);
      values[i].setAttribute("x", x + width - pad);
      values[i].setAttribute("y", cy + 4.5);
    });
  }

  /**
   * At the end of the energy curves, what the day comes to, kept in view like the averages' numbers
   * of the price: where the forecast ends (at sunset) the energy expected for the day ("≈ 12 kWh"),
   * where the production ends (now, or at sunset of a day that's over) what was produced against what
   * was forecast up to there, with the gap in percent. Above and left of its end, where the curve
   * isn't; one that would meet another moves up
   */
  _endLabels({ data, x, y, left, right, top, bottom, now }) {
    const d = this._data;
    const language = this._hass.language;
    const anchors = {};
    for (const series of data) {
      for (const line of series.lines) {
        const [time, value] = line[line.length - 1];
        // (A line ending where a day does belongs to that day)
        (anchors[d.dateOf(time - 1)] ||= {})[series.kind] = [time, value];
      }
    }
    const shown = (kind) => data.some((series) => series.kind === kind);
    const format = (value) => solarFormat(numberLocale(this._hass), value, { energy: true });
    const labels = [];
    for (const [date, end] of Object.entries(anchors)) {
      const [dayStart, dayEnd] = dayBounds(date, d.zone);
      const sun = this._sunWindow(dayStart);
      const over = dayEnd <= now || Boolean(sun && now >= sun[1]);
      if (end.actual) {
        let text = format(end.actual[1]);
        const planned = this._energyBetween("forecast", dayStart, over ? dayEnd : now);
        if (shown("forecast") && planned > 0) {
          const gap = formatPercent(language, (end.actual[1] - planned) / planned, "always");
          text += ` / ${format(planned)} (${gap})`;
        }
        labels.push({ at: end.actual, text, kind: "actual" });
      }
      if (end.forecast) labels.push({ at: end.forecast, text: `≈ ${format(end.forecast[1])}`, kind: "forecast" });
      for (const kind of ["charge", "discharge", "grid_import", "grid_export"]) {
        if (end[kind]) labels.push({ at: end[kind], text: format(end[kind][1]), kind });
      }
    }
    const height = 16;
    const placed = [];
    const parts = [];
    // Where the cursor rests when nobody reads: in the middle of the hour (quarter hour) of now,
    // a dot on each curve there
    const step = this._resolution() === "hour" ? HOUR_MS : d.step;
    const slotStart = localFloor(now, step, d.zone);
    const dotX = x(slotStart + step / 2);
    const dotRoom = 10;
    for (const label of labels.sort((a, b) => a.at[0] - b.at[0])) {
      const width = label.text.length * 6.1 + 14;
      let px = Math.min(Math.max(x(label.at[0]) - width + 2, left), right - width);
      // Clear of the cursor's dots where it rests (at now): to its left, else to its right
      if (px < dotX + dotRoom && dotX - dotRoom < px + width) {
        px = dotX - dotRoom - width >= left ? dotX - dotRoom - width : Math.min(dotX + dotRoom, right - width);
      }
      const ay = y(label.at[1]);
      let py = ay - 7 - height;
      if (py < top - 2) py = ay + 7;
      for (let tries = 0; tries < 3; tries++) {
        const hit = placed.find(
          (o) => px < o.x + o.w + 2 && o.x < px + width + 2 && py < o.y + height + 2 && o.y < py + height + 2
        );
        if (!hit) break;
        py = hit.y - height - 3;
      }
      py = Math.min(Math.max(py, top - 2), bottom - height);
      placed.push({ x: px, y: py, w: width });
      const color = this._solarColor(label.kind);
      parts.push(
        `<g class="energy-end ${label.kind}"><rect x="${px}" y="${py}" width="${width}" height="${height}" rx="8" style="stroke:${color}"></rect><text x="${px + width / 2}" y="${py + 11.5}" text-anchor="middle">${label.text}</text></g>`
      );
    }
    return parts;
  }

  _render() {
    super._render();
    if (!this.shadowRoot.querySelector("style.energy")) {
      this.shadowRoot
        .querySelector("ha-card")
        .insertAdjacentHTML("beforebegin", `<style class="energy">${SOLAR_BAR_STYLE}</style>`);
    }
    this._renderHead();
  }

  // With energy data the head is the energy's, whatever the cursor reads (its values are in the
  // balloons); without it the chart card's
  _setReadout(...args) {
    if (this._availableSeries().length) {
      this._renderHead();
      return;
    }
    this._els.readout.classList.remove("is-energy");
    super._setReadout(...args);
  }

  // The kWh of a curve in a stretch, and whether it has any hour there
  _sumBetween(kind, from, to) {
    let value = 0;
    let any = false;
    for (const [hour, kwh] of this._solar[kind]) {
      if (hour < from || hour >= to) continue;
      value += kwh;
      any = true;
    }
    return { value, any };
  }

  /**
   * What the view's stretch comes to: per curve its kWh, what was bought cost and paid on average
   * against the mean price of the same hours (buying evenly), how much of the home's use the home
   * covered itself (all that isn't bought: production and battery, less what went into the battery
   * or the grid), and the mean price of the stretch. Cost and paid at the total price whichever is
   * shown (what was bought cost that), the mean in the price shown
   */
  _balance(from, to) {
    const sums = Object.fromEntries(SOLAR_KINDS.map((kind) => [kind, this._sumBetween(kind, from, to)]));
    let cost = 0;
    let bought = 0;
    let even = 0;
    let hours = 0;
    for (const [hour, kwh] of this._solar.grid_import) {
      if (hour < from || hour >= to) continue;
      const price = this._hourPrice(hour, this._data.totals);
      if (price === null) continue;
      cost += kwh * price;
      bought += kwh;
      even += price;
      hours += 1;
    }
    const paid = bought > 0 ? cost / bought : undefined;
    const reference = hours ? even / hours : undefined;
    const used =
      ["actual", "grid_import", "discharge"].reduce((sum, kind) => sum + sums[kind].value, 0) -
      sums.charge.value -
      sums.grid_export.value;
    const own =
      sums.actual.any && sums.grid_import.any && used > 0
        ? Math.min(Math.max(1 - sums.grid_import.value / used, 0), 1)
        : undefined;
    const d = this._data;
    const prices = [];
    for (let at = from; at < to; at += d.step) {
      const price = this._quarterPrice(at);
      if (price !== null) prices.push(price);
    }
    const mean = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : undefined;
    return { sums, cost: hours ? cost : undefined, paid, reference, own, mean };
  }

  /**
   * The head: the balance of the view in view. Above, the price's switch with the stretch's mean
   * price, what was paid for the energy bought against that and the share the home covered itself,
   * and the power / energy switch; below, a tile per section of the curves (solar, battery, grid)
   * with its sums, whose name switches all its curves and whose curves switch one by one. The
   * tiles are the legend: pointing at one brings its curves to the front
   */
  _renderHead() {
    const els = this._els;
    if (!els || !this._data || !this._geo || !this._availableSeries().length) return;
    const readout = els.readout;
    readout.classList.add("is-energy");
    readout.classList.remove("has-dial");
    const main = els.main;
    if (!this._headBound) {
      this._headBound = true;
      main.addEventListener("click", (ev) => {
        const curve = ev.target.closest("button[data-curve]");
        const section = ev.target.closest("button[data-section]");
        const mode = ev.target.closest("button[data-mode]");
        if (!curve && !section && !mode) return;
        // Not the card's tap action on the head
        ev.stopPropagation();
        if (mode) {
          if (mode.dataset.mode === this._mode) return;
          this._storedMode = mode.dataset.mode;
          storeValue(this._modeKey, this._storedMode);
          this._refreshSolar();
          return;
        }
        const kinds = curve ? [curve.dataset.curve] : this._sectionKinds(section.dataset.section);
        // A section: all of its curves off where one is on, else all on
        const on = !kinds.some((kind) => this._visible.has(kind));
        for (const kind of kinds) {
          if (on) this._visible.add(kind);
          else this._visible.delete(kind);
        }
        storeValue(this._curvesKey, JSON.stringify([...this._visible]));
        this._emphasize(on ? kinds : []);
        this._refreshSolar();
      });
      // Pointing at a tile or a curve's name (or tabbing to it) brings its curves to the front
      const point = (ev) => {
        const curve = ev.target.closest("[data-curve]");
        const section = ev.target.closest("[data-section]");
        const kinds = curve ? [curve.dataset.curve] : section ? this._sectionKinds(section.dataset.section) : [];
        this._emphasize(kinds.filter((kind) => this._visible.has(kind)));
      };
      main.addEventListener("pointerover", point);
      main.addEventListener("focusin", point);
      main.addEventListener("pointerleave", () => this._emphasize([]));
      main.addEventListener("focusout", () => this._emphasize([]));
    }
    const s = this._t.energy;
    const d = this._data;
    const g = this._geo;
    const locale = numberLocale(this._hass);
    const kwh = (value) => solarFormat(locale, value, { energy: true });
    const priceText = (value) => `${g.format(value)} ${d.unit}`;
    // The outlook and tomorrow look ahead (from the hour running): when the sun and the low prices
    // come, not what was; the other views are the balance of their stretch
    const ahead = ["outlook", "tomorrow"].includes(this._view)
      ? Math.max(g.from, localFloor(Date.now(), HOUR_MS, d.zone))
      : undefined;
    const b = this._balance(ahead ?? g.from, g.to);
    if (ahead !== undefined) {
      // Nothing is measured ahead yet: the tiles say what is expected
      for (const kind of SOLAR_MEASURED) b.sums[kind] = { value: 0, any: false };
      b.cost = undefined;
    }
    const on = this._visible;
    // (The name in a span of its own: narrow tiles show the swatch alone, the name as its tooltip)
    const curve = (kind, label = s[kind]) =>
      `<button type="button" data-curve="${kind}" aria-pressed="${on.has(kind)}" title="${s[kind]}"><i class="${kind}" style="--swatch:${this._legendColor(kind)}"></i><span class="curve-name">${label}</span></button>`;
    const hero = [curve("price", b.mean !== undefined ? `${s.price} <b>⌀ ${priceText(b.mean)}</b>` : s.price)];
    if (ahead !== undefined) {
      hero.push(...this._aheadKpis(ahead, g.to));
    } else if (b.paid !== undefined) {
      // Paid is at the total price: said so beside the energy price alone, so the two aren't compared
      const paid = this._priceSource() === "energy" ? s.paid_total : s.paid;
      let text = fill(paid, { price: `<b>${priceText(b.paid)}</b>` });
      if (b.reference) {
        const gap = b.paid / b.reference - 1;
        const percent = formatPercent(this._hass.language, gap, "always");
        text += ` <span class="${gap <= 0 ? "better" : "worse"}">${fill(s.vs_average, { percent })}</span>`;
      }
      hero.push(`<span class="energy-kpi">${text}</span>`);
    }
    if (ahead === undefined && b.own !== undefined) {
      const percent = formatPercent(this._hass.language, b.own);
      hero.push(`<span class="energy-kpi">${fill(s.self_sufficient, { percent: `<b>${percent}</b>` })}</span>`);
    }
    const mode = this._mode;
    if (this._config.energy_mode_switch) {
      hero.push(
        `<span class="spacer"></span><div class="energy-modes" role="group" aria-label="${s.mode}">${SOLAR_MODES.map(
          (m) => `<button type="button" data-mode="${m}" aria-pressed="${m === mode}">${s[m]}</button>`
        ).join("")}</div>`
      );
    }
    const { sums } = b;
    const value = (sum, word) => (sum.any ? `${kwh(sum.value)}${word ? ` <small>${word}</small>` : ""}` : "–");
    const tiles = SOLAR_SECTIONS.map(({ key }) => {
      const kinds = this._sectionKinds(key);
      if (!kinds.length) return "";
      let main = "–";
      const sub = [];
      if (key === "solar") {
        const expected = sums.forecast.any && sums.forecast.value > 0 ? kwh(sums.forecast.value) : "";
        if (sums.actual.any) {
          main = value(sums.actual, s.produced);
          if (expected) sub.push(fill(s.expected, { value: expected }));
        } else if (expected) {
          main = `≈ ${expected}`;
          sub.push(s.forecast);
        }
      } else if (key === "battery") {
        if (kinds.includes("charge")) main = value(sums.charge, s.charged);
        if (kinds.includes("discharge")) {
          if (main === "–") main = value(sums.discharge, s.discharged);
          else if (sums.discharge.any) sub.push(`${kwh(sums.discharge.value)} ${s.discharged}`);
        }
      } else {
        if (kinds.includes("grid_import")) {
          main = value(sums.grid_import, s.bought);
          if (b.cost !== undefined) sub.push(this._costText(b.cost));
        }
        if (kinds.includes("grid_export") && sums.grid_export.any) {
          const fed = fill(s.fed_in, { value: kwh(sums.grid_export.value) });
          if (main === "–") main = value(sums.grid_export, "");
          else sub.push(fed);
        }
      }
      const label = s[`section_${key}`];
      const pressed = kinds.some((kind) => on.has(kind));
      return `<div class="energy-tile${pressed ? "" : " is-off"}" data-section="${key}" style="--tile:${this._solarColor(
        kinds[kinds.length > 1 && key === "solar" ? 1 : 0]
      )}"><button type="button" class="section" data-section="${key}" aria-pressed="${pressed}">${label}</button><div class="tile-value">${main}</div><div class="tile-sub">${
        sub.join(" · ") || "&nbsp;"
      }</div><div class="tile-curves">${kinds.map((kind) => curve(kind)).join("")}</div></div>`;
    }).join("");
    const html = `<div class="energy-head"><div class="energy-hero">${hero.join("")}</div><div class="energy-tiles">${tiles}</div></div>`;
    // Unchanged (the cursor moved): left alone, so a pointer on it stays where it is
    if (html === this._headHtml && main.querySelector(":scope > .energy-head")) return;
    this._headHtml = html;
    main.innerHTML = html;
  }

  /**
   * The head's line ahead: when the sun is strongest, when the prices are lowest, and where the two
   * meet, so "when do I run the dishwasher" is answered at a glance. It shows, it doesn't plan.
   * Where the prices of the stretch aren't in yet, it says when they come
   */
  _aheadKpis(from, to) {
    const d = this._data;
    const s = this._t.energy;
    const locale = numberLocale(this._hass);
    // "tomorrow 11:00–14:00" in the outlook, the time alone where the view is one day
    const when = (a, b) => {
      const day = CHART_SINGLE_DAY_VIEWS.includes(this._view) || d.dateOf(a) === d.today ? "" : d.dateOf(a);
      const prefix = day === d.tomorrow ? `${lowerFirst(this._t.tomorrow)} ` : day ? `${this._dayWord(day, a)} ` : "";
      return `${prefix}<b>${timeRange(d.clock, a, b)}</b>`;
    };
    const kpis = [];
    const sun = this._sunAhead(from, to);
    const cheap = this._cheapAhead(from, to);
    if (sun) {
      const energy = solarFormat(locale, sun[2], { energy: true });
      kpis.push(
        `<span class="energy-kpi when">${fill(s.sun_window, { time: when(sun[0], sun[1]) })} · ≈ ${energy}</span>`
      );
    }
    // Where they meet: the lowest prices inside the sun say so instead of being named twice
    const meet = sun && cheap ? [Math.max(sun[0], cheap[0]), Math.min(sun[1], cheap[1])] : undefined;
    const meets = meet && meet[1] - meet[0] >= QUARTER_MS;
    if (cheap && !(meets && meet[0] === cheap[0] && meet[1] === cheap[1])) {
      kpis.push(`<span class="energy-kpi when">${fill(s.cheap_window, { time: when(cheap[0], cheap[1]) })}</span>`);
    }
    if (meets)
      kpis.push(`<span class="energy-kpi when better">${fill(s.both_window, { time: when(meet[0], meet[1]) })}</span>`);
    if (to > d.end) kpis.push(`<span class="energy-kpi">${this._t.tomorrow_pending}</span>`);
    return kpis;
  }

  /**
   * The next stretch of strong sun ahead, as [start, end, kWh]: on the first day with strong sun
   * still to come (at least half the strongest hour ahead: the last weak hour before sunset doesn't
   * count), the hour the forecast peaks and the hours around it with at least half of that.
   * Undefined without a forecast ahead
   */
  _sunAhead(from, to) {
    const d = this._data;
    const hours = this._solar.forecast;
    const ahead = [...hours.keys()]
      .filter((hour) => hour >= from && hour < to && hours.get(hour) > 0)
      .sort((a, b) => a - b);
    if (!ahead.length) return undefined;
    const strongest = Math.max(...ahead.map((hour) => hours.get(hour)));
    const date = d.dateOf(ahead.find((hour) => hours.get(hour) >= strongest / 2));
    const inDay = ahead.filter((hour) => d.dateOf(hour) === date);
    const peak = inDay.reduce((a, b) => (hours.get(b) > hours.get(a) ? b : a));
    const enough = (hour) => inDay.includes(hour) && hours.get(hour) >= hours.get(peak) / 2;
    let start = peak;
    while (enough(start - HOUR_MS)) start -= HOUR_MS;
    let end = peak + HOUR_MS;
    while (enough(end)) end += HOUR_MS;
    let energy = 0;
    for (let hour = start; hour < end; hour += HOUR_MS) energy += hours.get(hour);
    return [start, end, energy];
  }

  /**
   * The lowest prices ahead, as [start, end]: the next best price period (the integration's own, as
   * the chart marks it below the hours), else the cheapest three hours in a row at the total price,
   * like the periods (what buying then costs, whichever price is shown). Undefined without prices
   * ahead
   */
  _cheapAhead(from, to) {
    const best = this._data.periods.best.find(([a, b]) => b > from && a < to);
    if (best) return [Math.max(best[0], from), Math.min(best[1], to)];
    const span = 3 * HOUR_MS;
    let pick;
    for (let hour = from; hour + span <= to; hour += HOUR_MS) {
      const prices = [0, 1, 2].map((i) => this._hourPrice(hour + i * HOUR_MS, this._data.totals));
      if (prices.includes(null)) continue;
      const mean = prices.reduce((a, b) => a + b, 0) / 3;
      if (!pick || mean < pick[2]) pick = [hour, hour + span, mean];
    }
    return pick && [pick[0], pick[1]];
  }

  // The curves of a section of the legend there is data for
  _sectionKinds(key) {
    const section = SOLAR_SECTIONS.find((s) => s.key === key);
    const available = this._availableSeries();
    return section ? section.kinds.filter((kind) => available.includes(kind)) : [];
  }

  // The curves in front (the others fade): a class on the plot per curve, so a redraw keeps it
  _emphasize(kinds) {
    const plot = this._els && this._els.plot;
    if (!plot) return;
    this._emphasis = kinds.length ? new Set(kinds) : undefined;
    for (const kind of SOLAR_CURVES) plot.classList.toggle(`emph-${kind}`, kinds.includes(kind));
    plot.classList.toggle("has-emphasis", kinds.length > 0);
  }

  static getConfigForm() {
    const form = super.getConfigForm();
    const t = languageStrings(STRINGS);
    const fields = [
      {
        name: "energy_curves",
        selector: {
          select: {
            multiple: true,
            options: SOLAR_CURVES.map((value) => ({ value, label: t.energy[value] })),
          },
        },
      },
      {
        name: "energy_mode",
        selector: {
          select: { mode: "dropdown", options: SOLAR_MODES.map((value) => ({ value, label: t.energy[value] })) },
        },
      },
      { name: "energy_mode_switch", selector: { boolean: {} } },
    ];
    // Right under the views
    const at = form.schema.findIndex((field) => field.name === "views") + 1;
    return { ...form, schema: [...form.schema.slice(0, at), ...fields, ...form.schema.slice(at)] };
  }

  static async getConfigElement() {
    await loadEditors();
    return document.createElement("tibber-prices-energy-card-editor");
  }

  static getStubConfig(hass) {
    return { ...TibberPricesChartCard.getStubConfig(hass), views: [...CHART_DEFAULT_VIEWS] };
  }

  static configDefaults() {
    return { ...super.configDefaults(), ...SOLAR_DEFAULTS };
  }
}
