/**
 * Time in the home's time zone: offsets, clock changes, the bounds of a day, and the calendar of
 * the home (its zone and today's and tomorrow's dates).
 */

import { HOUR_MS, timeZone } from "./util.js";

// How far a time zone is ahead of UTC at a moment (ms); undefined: the browser's
// Kept per zone: building an Intl format is the costly part
const ZONE_FORMATS = new Map();
export function zoneOffset(time, zone) {
  const key = zone || "";
  if (!ZONE_FORMATS.has(key)) {
    ZONE_FORMATS.set(
      key,
      new Intl.DateTimeFormat("en-US", {
        timeZone: zone,
        hourCycle: "h23",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    );
  }
  const parts = ZONE_FORMATS.get(key).formatToParts(new Date(time));
  const v = Object.fromEntries(parts.map((part) => [part.type, Number(part.value)]));
  return Date.UTC(v.year, v.month - 1, v.day, v.hour, v.minute, v.second) - (time - (time % 1000));
}

// The mark of a wall-clock hour that occurs twice (the clocks go back): "ᴬ" the first time, "ᴮ"
// the second; "" at any other moment. The end of the first pass (the same moment as the start of
// the second) is "ᴮ" too, so a range reads "02:00ᴬ–02:00ᴮ" rather than "02:00–02:00"
export const REPEAT_MARKS = { first: "\u1D2C", second: "\u1D2E" };
export function repeatMark(time, zone) {
  const offset = zoneOffset(time, zone);
  if (zoneOffset(time + HOUR_MS, zone) < offset) return REPEAT_MARKS.first;
  if (zoneOffset(time - HOUR_MS, zone) > offset) return REPEAT_MARKS.second;
  return "";
}

// The zone's abbreviation at a moment ("CEST", "CET"), as the language writes it. Some languages
// (English) only know an offset ("GMT+2") for zones outside their region: then British English is
// tried, and failing that the offset stays
function zoneAbbreviation(date, language, zone) {
  let name = "";
  for (const locale of [language, "en-GB"]) {
    const part = new Intl.DateTimeFormat(locale, { timeZone: zone, timeZoneName: "short" })
      .formatToParts(date)
      .find((p) => p.type === "timeZoneName");
    name = part ? part.value : "";
    if (name && !/^(GMT|UTC)[+\u2212-]/.test(name)) break;
  }
  return name.replace(/^GMT/, "UTC");
}

// Whether the clocks change within a block of hours: "back" (one of its hours occurs twice),
// "forward" (an hour is skipped) or "". An hour that starts a repeated one is "back" itself, the
// hour before a skipped one "forward" (it ends at the change)
export function clockChange(start, end, zone, isHour) {
  if (isHour) {
    if (repeatMark(start, zone)) return "back";
    return zoneOffset(end, zone) > zoneOffset(start, zone) ? "forward" : "";
  }
  const delta = zoneOffset(end - 1, zone) - zoneOffset(start, zone);
  return delta < 0 ? "back" : delta > 0 ? "forward" : "";
}

// Midnight starting a calendar date (YYYY-MM-DD) in the home's time zone, and the next one
export function dayBounds(date, zone) {
  const [year, month, day] = date.split("-").map(Number);
  const midnight = (d) => {
    const utc = Date.UTC(year, month - 1, d);
    return utc - zoneOffset(utc - zoneOffset(utc, zone), zone);
  };
  return [midnight(day), midnight(day + 1)];
}

// A home's calendar: its time zone, the date of a moment there and the formats of its days and
// times in the HA language. Kept per language and zone: building an Intl format is the costly part
const CALENDARS = new Map();
export function homeCalendar(hass) {
  const zone = timeZone(hass);
  const key = `${hass.language}|${zone}`;
  if (!CALENDARS.has(key)) {
    const day = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: zone });
    const clockFormat = new Intl.DateTimeFormat(hass.language, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone: zone,
    });
    const hourFormat = new Intl.DateTimeFormat(hass.language, { hour: "2-digit", hourCycle: "h23", timeZone: zone });
    const hourName = (time) => hourFormat.format(new Date(time)).replace(/\D+$/, "");
    CALENDARS.set(key, {
      zone,
      // Calendar date (YYYY-MM-DD) of a moment, in the home's time zone
      dateOf: (time) => day.format(new Date(time)),
      weekday: new Intl.DateTimeFormat(hass.language, { weekday: "long", timeZone: zone }),
      dayMonth: new Intl.DateTimeFormat(hass.language, { day: "numeric", month: "long", timeZone: zone }),
      weekdayShort: new Intl.DateTimeFormat(hass.language, { weekday: "short", timeZone: zone }),
      // A time of day, marked where the clocks go back and it occurs twice (see repeatMark)
      clock: {
        format: (date) => clockFormat.format(date) + repeatMark(date.getTime(), zone),
      },
      // The same with the zone's own abbreviation, for tooltips, the chart's cursor tag and dialogs:
      // "02:15 (CEST)", "02:15 (CET)"
      clockLong: {
        format: (date) => {
          const mark = repeatMark(date.getTime(), zone);
          return clockFormat.format(date) + (mark ? ` (${zoneAbbreviation(date, hass.language, zone)})` : "");
        },
      },
      // The number of an hour ("02"), and its label, marked like the clock
      zoneName: (time) => zoneAbbreviation(new Date(time), hass.language, zone),
      hourName,
      hourTag: (time) => hourName(time) + repeatMark(time, zone),
    });
  }
  return CALENDARS.get(key);
}
