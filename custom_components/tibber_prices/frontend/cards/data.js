/**
 * What the cards read from the price sensor: the unit, the quarter-hour series, the state for the
 * price source (total or energy price), the days' references and the home's periods.
 */

import { aggregate, levelOfMany } from "./util.js";
import { dayBounds, homeCalendar } from "./time.js";

/**
 * Prices in the unit the card is set to: as the integration shows them ("auto"), or always in
 * base currency (€, kr) or subunit (ct, øre). Returns the factor to apply and the unit label.
 */
export function priceUnit(stateObj, setting) {
  const units = stateObj.attributes.outlook_units;
  if (!units) return { factor: 1, unit: stateObj.attributes.unit_of_measurement || "" };
  const target = setting === "base" || setting === "subunit" ? setting : units.display;
  const factor = target === units.display ? 1 : target === "subunit" ? 100 : 0.01;
  return { factor, unit: units[target] };
}

// Every price_* field of an outlook entry, scaled
export function scalePrices(entries, factor) {
  if (factor === 1) return entries;
  return entries.map((entry) =>
    Object.fromEntries(
      Object.entries(entry).map(([key, value]) => [
        key,
        key.startsWith("price_") && typeof value === "number" ? value * factor : value,
      ])
    )
  );
}

// Every quarter hour of the price sensor's outlook (from last night on), in the unit shown, with
// the total prices beside them (the same list unless the energy price alone is shown, see
// priceState); undefined from an integration without them
export function quarterSeries(stateObj, factor) {
  const series = stateObj.attributes.outlook_quarters;
  if (!series || !Array.isArray(series.prices)) return undefined;
  const scale = (list) => list.map((price) => (typeof price === "number" ? price * factor : null));
  const prices = scale(series.prices);
  return {
    start: Date.parse(series.start),
    step: (series.minutes || 15) * 60000,
    prices,
    totals: series.totals ? scale(series.totals) : prices,
    levels: series.levels || [],
  };
}

// Which price a card shows: the total, taxes and fees included (default, as Tibber bills it), or
// the energy price alone
export const PRICE_SOURCES = ["total", "energy"];

/**
 * The price sensor as a card showing `source` reads it: as it is for the total price; for the
 * energy price alone, every price of its outlook (hours, parts of the day, days, yesterday, the
 * quarter hours) and its state taken from the energy prices of the quarter hours. Levels,
 * volatility and the periods stay those of the total price, as the integration decides on them,
 * so the colors and marks never disagree with its sensors. As it is from an integration that
 * sends no energy prices. One object per state, so redraws of the same state compare equal
 */
const ENERGY_STATES = new WeakMap();
export function priceState(hass, stateObj, source) {
  if (!stateObj || source !== "energy") return stateObj;
  const attributes = stateObj.attributes;
  const series = attributes.outlook_quarters;
  if (!series || !Array.isArray(series.energy)) return stateObj;
  const { zone } = homeCalendar(hass);
  const start = Date.parse(series.start);
  const step = (series.minutes || 15) * 60000;
  // The energy price now: the sensor's, else the running quarter hour's; never the total beside
  // energy prices (unknown then). Read again when the quarter hour has moved on
  const quarter = Math.floor((Date.now() - start) / step);
  const nowState = () => {
    const price = typeof attributes.energy_price === "number" ? attributes.energy_price : series.energy[quarter];
    return typeof price === "number" ? String(price) : "unknown";
  };
  const cached = ENERGY_STATES.get(stateObj);
  if (cached && cached.zone === zone) {
    if (cached.quarter !== quarter) {
      cached.quarter = quarter;
      cached.state = { ...cached.state, state: nowState() };
    }
    return cached.state;
  }
  if (!series.energy.some((p) => typeof p === "number")) return stateObj;
  // The energy prices from `from` to `to`: their spread, their averages and when the lowest and
  // highest come first; nulls where none is known
  const pricesOf = (from, to) => {
    const values = [];
    let low;
    let high;
    for (let i = Math.max(0, Math.ceil((from - start) / step)); i < series.energy.length; i += 1) {
      const at = start + i * step;
      if (at >= to) break;
      const price = series.energy[i];
      if (typeof price !== "number") continue;
      values.push(price);
      if (!low || price < low.price) low = { price, at };
      if (!high || price > high.price) high = { price, at };
    }
    if (!values.length) {
      return {
        price_mean: null,
        price_median: null,
        price_min: null,
        price_max: null,
        price_min_at: null,
        price_max_at: null,
      };
    }
    return {
      price_mean: aggregate(values, "mean"),
      price_median: aggregate(values, "median"),
      price_min: low.price,
      price_max: high.price,
      price_min_at: new Date(low.at).toISOString(),
      price_max_at: new Date(high.at).toISOString(),
    };
  };
  // A block's own prices; a day's reference and its extremes' times too, the rest as it was
  const block = ({ price_min_at, price_max_at, ...prices }, entry) => ({ ...entry, ...prices });
  const day = (prices, entry, reference) => ({
    ...entry,
    ...prices,
    price_reference: reference === "median" ? prices.price_median : prices.price_mean,
  });
  const span = (entry) => pricesOf(Date.parse(entry.start), Date.parse(entry.end));
  const days = (attributes.outlook_days || []).map((entry) => day(span(entry), entry, entry.reference));
  const yesterday = attributes.outlook_yesterday;
  const state = {
    ...stateObj,
    state: nowState(),
    attributes: {
      ...attributes,
      // What the price is made of means the total: the energy price alone has no parts
      energy_price: undefined,
      tax: undefined,
      outlook_hours: (attributes.outlook_hours || []).map((entry) => block(span(entry), entry)),
      outlook_day_parts: (attributes.outlook_day_parts || []).map((entry) => block(span(entry), entry)),
      outlook_days: days,
      outlook_yesterday: yesterday && day(pricesOf(...dayBounds(yesterday.date, zone)), yesterday, days[0]?.reference),
      // The total prices kept beside them, for what buying costs (see quarterSeries)
      outlook_quarters: { ...series, prices: series.energy, totals: series.prices },
    },
  };
  ENERGY_STATES.set(stateObj, { zone, quarter, state });
  return state;
}

// The average a card shows: the mean unless it says otherwise ("auto": as set for the
// integration's average sensors, which the days carry)
export function averageKindOf(config, days) {
  return config.average === "auto" ? (days[0] && days[0].reference) || "mean" : config.average;
}

// Each day's average of a kind by date, yesterday's too (after midnight its last hour is still
// shown)
export function dayReferences(stateObj, factor, days, key) {
  const yesterday = stateObj.attributes.outlook_yesterday;
  return Object.fromEntries(
    [...(yesterday ? scalePrices([yesterday], factor) : []), ...days].map((day) => [day.date, day[key]])
  );
}

// A period sensor's periods (today's and tomorrow's) as [start, end], after those that ended
// before today as far back as the outlook reaches (from the price sensor); none without the sensor
function periodSpans(hass, entity, past = []) {
  const stateObj = entity && hass.states[entity];
  if (!stateObj) return [];
  return [...past, ...(stateObj.attributes.periods || [])].map((p) => [Date.parse(p.start), Date.parse(p.end)]);
}

// The home's best and peak price periods (see periodSpans)
export function homePeriods(hass, entities, stateObj) {
  const past = stateObj.attributes.outlook_past_periods || {};
  return {
    best: periodSpans(hass, entities.best, past.best_price),
    peak: periodSpans(hass, entities.peak, past.peak_price),
  };
}

// Prices in steps of `size` (a quarter hour or an hour) from `from` to `to`, each with its level:
// the quarter hours in it, aggregated (mean or median); null where there are none
export function quarterSlots(quarters, from, to, size, kind) {
  const slots = [];
  for (let at = from; at < to; at += size) {
    const end = Math.min(at + size, to);
    const prices = [];
    const levels = [];
    for (let time = at; quarters && time < end; time += quarters.step) {
      const index = Math.round((time - quarters.start) / quarters.step);
      if (typeof quarters.prices[index] !== "number") continue;
      prices.push(quarters.prices[index]);
      levels.push(quarters.levels[index]);
    }
    slots.push({ start: at, end, price: prices.length ? aggregate(prices, kind) : null, level: levelOfMany(levels) });
  }
  return slots;
}
