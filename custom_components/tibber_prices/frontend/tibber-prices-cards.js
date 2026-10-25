/**
 * Dashboard cards shipped with the Tibber Prices integration.
 *
 * Loaded into every frontend by the integration itself (frontend/__init__.py), so there is
 * nothing to install. Plain web components without dependencies or a build step: the only
 * interface to Home Assistant is the `hass` object, which keeps the cards independent of
 * frontend internals.
 *
 * tibber-prices-forecast-card: the coming hours and parts of the day, shaped like a weather
 * forecast. Reads the `outlook_hours` / `outlook_day_parts` attributes of the Current
 * Electricity Price sensor; best/peak price periods come from the period binary sensors.
 *
 * tibber-prices-now-card: the current price as a tile, gauge or clock.
 * tibber-prices-chart-card: the price curve with a cursor to read it (see its class).
 */

// Same colors as the charts from get_apexcharts_yaml (level_type: level), so a column and the
// chart area at that time look alike
const LEVEL_COLORS = {
  very_cheap: "#2ecc71",
  cheap: "#27ae60",
  normal: "#f1c40f",
  expensive: "#e67e22",
  very_expensive: "#e74c3c",
};

const MARK_COLORS = { best: "var(--success-color, #43a047)", peak: "var(--error-color, #db4437)" };

// A period running right now, marked at the bar of now: a piggy bank for best price (a good
// time to save), a warning sign for peak price (better later). mdi:piggy-bank and mdi:alert,
// like HA's own icons
const PERIOD_PATHS = {
  best: "M19.83 7.5L17.56 5.23C17.63 4.81 17.74 4.42 17.88 4.08C17.96 3.9 18 3.71 18 3.5C18 2.67 17.33 2 16.5 2C14.86 2 13.41 2.79 12.5 4H7.5C4.46 4 2 6.46 2 9.5S4.5 21 4.5 21H10V19H12V21H17.5L19.18 15.41L22 14.47V7.5H19.83M13 9H8V7H13V9M16 11C15.45 11 15 10.55 15 10S15.45 9 16 9C16.55 9 17 9.45 17 10S16.55 11 16 11Z",
  peak: "M13 14H11V9H13M13 18H11V16H13M1 21H23L12 2L1 21Z",
};
// Optically centered in the circle: a triangle's weight sits low, so it goes up a little (half
// way between its box's center and its center of mass)
const PERIOD_NUDGE = { best: "", peak: "translate(0 -1.5)" };
function periodBadge(kind, title = "", style = "") {
  return `<span class="period-badge ${kind}"${title ? ` title="${title}"` : ""}${style ? ` style="${style}"` : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${PERIOD_PATHS[kind]}"${
    PERIOD_NUDGE[kind] ? ` transform="${PERIOD_NUDGE[kind]}"` : ""
  }></path></svg></span>`;
}

const FEATURE_NAMES = {
  en: "Price outlook",
  de: "Preisvorschau",
  nb: "Prisutsikt",
  nl: "Prijsvooruitblik",
  sv: "Prisutsikt",
};

// mdi:chevron-left / mdi:chevron-right
const CHEVRON_LEFT = "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z";
const CHEVRON_RIGHT = "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z";
const CHEVRON_UP = "M7.41,15.41L12,10.83L16.59,15.41L18,14L12,8L6,14L7.41,15.41Z";
const CHEVRON_DOWN = "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z";
// mdi:menu-down
const MENU_DOWN = "M7,10L12,15L17,10H7Z";

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
// The day's line beyond a detail chart's range: a dash at the edge with an arrow its way
const REF_OFF_ICONS = {
  up: '<svg viewBox="0 0 12 12" aria-hidden="true"><path class="arrow" d="M6 0L10 5H2Z"></path><path class="dash" d="M0 10H12"></path></svg>',
  down: '<svg viewBox="0 0 12 12" aria-hidden="true"><path class="dash" d="M0 2H12"></path><path class="arrow" d="M6 12L10 7H2Z"></path></svg>',
};
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

// Whether the last input was the keyboard rather than a tap or a click. The cards move the focus
// themselves (into a window, to its close button, back to what opened it), and Safari and Chrome
// show the focus ring on focus set from a script even after a tap: the cards show it only to
// keyboard users (see `data-keyboard` in the style)
let keyboardInput = false;
const MODIFIER_KEYS = new Set(["Shift", "Control", "Alt", "Meta"]);
window.addEventListener(
  "keydown",
  (event) => {
    // Not a lone modifier, nor a shortcut with one (Cmd+Tab, Ctrl+C): those don't move the focus
    if (!MODIFIER_KEYS.has(event.key) && !event.metaKey && !event.ctrlKey && !event.altKey) keyboardInput = true;
  },
  true
);
window.addEventListener("pointerdown", () => (keyboardInput = false), true);

// The legend button of the section on screen (compact) or of the card
const OWN_LEGEND_BUTTON = ".panel:not(.inactive) .legend-button, ha-card:not(.is-compact) .legend-button";

// mdi:close
// mdi:arrow-left, the way back from a detail opened inside another
const BACK_PATH = "M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z";
const CLOSE_PATH =
  "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";

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
// The faded edge of a strip with more beyond it: a share of its width, within bounds (in the
// styles, and where the price steps keep clear of it)
const FADE = { share: 0.08, min: 32, max: 72 };

// Which scroll buttons the strips show: both sides, only forward (into the future), only back,
// or none (swiping and scrolling work anyway)
const SCROLL_BUTTONS = ["both", "forward", "back", "none"];

// Same timings as HA's own action handler
const HOLD_DOUBLE_TAP = { holdMs: 500, doubleTapMs: 250 };

// mdi:text-short, the icon of the "Content" panel in HA's own card editors
const CONTENT_PATH = "M4,9H20V11H4V9M4,13H14V15H4V13Z";

// mdi:gesture-tap, for the "Interactions" section of the editor (labels as in HA's own editors)
const GESTURE_TAP_PATH =
  "M10,9A1,1 0 0,1 11,8A1,1 0 0,1 12,9V13.47L13.21,13.6L18.15,15.79C18.68,16.03 19,16.56 19,17.14V21.5C18.97,22.32 18.32,22.97 17.5,23H11C10.62,23 10.26,22.85 10,22.57L5.1,18.37L5.84,17.6C6.03,17.39 6.3,17.28 6.58,17.28H6.8L10,19V9M11,5A4,4 0 0,1 15,9C15,10.5 14.2,11.77 13,12.46V11.24C13.61,10.69 14,9.89 14,9A3,3 0 0,0 11,6A3,3 0 0,0 8,9C8,9.89 8.39,10.69 9,11.24V12.46C7.8,11.77 7,10.5 7,9A4,4 0 0,1 11,5Z";

const STRINGS = {
  en: {
    // A part of the day on a weekday, as the language says it; a night by the day it leads into
    // where its weekday name would be ambiguous ("Freitagnacht": Thursday's or Friday's?)
    part_on_day: {
      morning: "{weekday} morning",
      day: "{weekday} daytime",
      evening: "{weekday} evening",
      night: "{weekday} night",
    },
    // Inside a sentence, where it differs ("in der Nacht zum Samstag")
    part_in_sentence: {},
    action_button: { "more-info": "More info", open: "Open", run: "Run" },
    day_details: {
      cheapest_hour: { today: "Cheapest hour still to come today", other: "Cheapest hour" },
      cheapest_part: { today: "Cheapest part of the day still to come today", other: "Cheapest part of the day" },
      passed: "already passed",
    },
    detail: {
      // Where inside a part of the day it's cheapest
      cheapest_in: "cheapest {time}",
      now: {
        near_median: "about at the median",
        now_price: "Current price",
        valid_until: "until {time}",
        then: "then {price} ({change})",
        this_hour: "This hour",
        this_part: "This part of the day",
        in_period: { best: "Best price period until {time}", peak: "Peak price period until {time}" },
        next_best: "Next best price period from {time} ({wait})",
        wait: "in {duration}",
        rank: {
          dearer: "More expensive than {percent} of today's quarter hours.",
          cheaper: "Cheaper than {percent} of today's quarter hours.",
        },
        energy: "Energy price",
        tax: "Taxes and fees",
      },
      volatility: { low: "Low", moderate: "Moderate", high: "High", very_high: "Very high" },
      legend_link: "What do the marks mean?",
      // Tomorrow before its prices are in
      pending: {
        title: "No prices yet",
        prose:
          "Tomorrow's prices usually arrive in the early afternoon. Once they're in, they show up here by themselves.",
      },
      all_values: "All values",
      // The values behind a detail card, in a view of their own like HA's "Details"
      values: { title: "Details", prices: "Prices", times: "Times", periods: "Periods", compare: "Comparison" },
      unknown: "not known yet",
      // One quarter hour picked in an hour's chart
      pick: {
        hint: "Tap a quarter hour for its details",
        vs_hour: "{percent} vs. the hour",
        vs_day: { mean: "{percent} vs. the day's average", median: "{percent} vs. the day's median" },
        vs_now: "{percent} vs. now",
        rank: { dearer: "dearer than {percent} of the day", cheaper: "cheaper than {percent} of the day" },
      },
      facts: {
        time: "Time",
        mean: "Average",
        median: "Median",
        quarters: "Quarter hours",
        range: "Lowest–highest",
        vs_day: { median: "Compared with the daily median", mean: "Compared with the daily average" },
        vs_now: "Compared with now",
        vs_today: "Compared with today",
        vs_tomorrow: "Compared with tomorrow",
        volatility: "Volatility",
        now: "Now",
        cheapest_hour: "Cheapest hour",
        cheapest_part: "Cheapest part of the day",
      },
      // Today against tomorrow, once its prices are in (inside a sentence)
      vs_tomorrow: {
        cheaper: "{percent} cheaper than tomorrow",
        dearer: "{percent} more expensive than tomorrow",
        same: "about as expensive as tomorrow",
      },
      vs_today: {
        cheaper: "{percent} cheaper than today",
        dearer: "{percent} more expensive than today",
        same: "About as expensive as today",
      },
      when_hour: { today: "today from {time}", other: "{weekday} from {time}" },
      prose: {
        today_vs_tomorrow: "On average, today is {comparison}.",
        past_hour: "This hour is over.",
        past_part: "This part of the day is over.",
        rises: "Within the hour, the price rises from {first} to {last} {unit}.",
        falls: "Within the hour, the price falls from {first} to {last} {unit}.",
        steady: "The price stays about the same throughout the hour.",
        cheapest_quarter: "The cheapest quarter hour starts at {time}.",
        part_spread:
          "The cheapest hour starts at {cheap} ({cheapPrice} {unit}), the most expensive at {dear} ({dearPrice} {unit}).",
        partial: "Prices are known only until {time} so far.",
        later: "Waiting pays: {when}, it's {percent} cheaper.",
        nothing_cheaper: {
          hour: "No hour still to come is clearly cheaper.",
          part: "No part of the day still to come is clearly cheaper.",
        },
        day_extremes: "Cheapest at {low} ({lowPrice} {unit}), most expensive at {high} ({highPrice} {unit}).",
        day_ahead: "Still to come today, the cheapest hour starts at {time} ({price} {unit}).",
      },
    },
    part_today: { morning: "this morning", day: "today during the day", evening: "this evening", night: "tonight" },
    details: {
      above: { median: "above the daily median", mean: "above the daily average" },
      below: { median: "below the daily median", mean: "below the daily average" },
      same: { median: "at the daily median", mean: "at the daily average" },
      at: "{label} {price} {unit} at {time}",
      period: { best: "Best price period", peak: "Peak price period" },
    },
    until: "until {time}",
    partial_note: "known only until {time}",
    earlier: "Earlier",
    later: "Later",
    back: "Back",
    day_low: "Day low",
    day_high: "Day high",
    passed: "passed",
    legend: {
      best_now: [
        "Best price now",
        "The piggy bank at the bar of now: a best price period is running, a good time to run appliances",
      ],
      peak_now: [
        "Peak price now",
        "The warning sign at the bar of now: a peak price period is running, better run appliances later",
      ],
      title: "Legend",
      // The marks of a detail card's chart
      zbar: ["Bar", "Its height is the price of that quarter hour or hour"],
      zref_off: ["Off the chart", "Arrow with a dash at the edge: the day's dashed line lies above or below the bars"],
      znow: ["Now", "The highlighted column is running now"],
      zpast: ["Faded", "Already past"],
      zmissing: ["Empty slot", "Its price isn't known yet"],
      times: "Times",
      day_pointer: ["Pointer: daily median", "Under a day's span: half of its quarter hours cost less"],
      day_now: [
        "Current price",
        "Blue triangle: where the current price lies, above today's span and beside the part of the day running now",
      ],
      both: { hours: "Hours and times of day", day_parts: "Times of day and hours" },
      close: "Close",
      level: ["Price level", "The color shows the price level:"],
      bar: ["Bar", { mean: "Its height is the hour's average price", median: "Its height is the hour's median price" }],
      span: ["Span", "Lowest to highest price of the part of the day; the pointer marks its median"],
      reference: "Anything below the dashed line is cheaper than the day as a whole",
      cheapest: [
        "Cheapest of the day",
        "Per day, how much cheaper than now its cheapest hour or part of the day is: today's from now on, tomorrow's once its prices are in. A night counts towards the day it ends on",
      ],
      best: "Colored line under a column: a best price period falls in this time",
      peak: "Colored line under a column: a peak price period falls in this time",
      low: "When the day's lowest price applies",
      high: "When the day's highest price applies",
      cut: ["Cut off", "Slanted gap at the top: the price reaches far above the rest, the number below says how high"],
      partial: ["Partly known", "Dashed: prices for this part of the day are known only up to the time shown above it"],
    },
    cheapest_tip: {
      hours: {
        today: "Cheapest hour still to come today: {percent} cheaper than now (⌀ {price} instead of {now} {unit})",
        tomorrow: "Cheapest hour tomorrow: {percent} cheaper than now (⌀ {price} instead of {now} {unit})",
      },
      parts: {
        today:
          "Cheapest part of the day still to come today: {percent} cheaper than now (⌀ {price} instead of {now} {unit})",
        tomorrow:
          "Cheapest part of the day tomorrow, the night before included: {percent} cheaper than now (⌀ {price} instead of {now} {unit})",
      },
    },
    median: "Median",
    day_reference: { median: "Daily median", mean: "Daily average" },
    today: "Today",
    yesterday: "Yesterday",
    days: "Days",
    tomorrow_pending: "Prices usually arrive in the early afternoon",
    volatility: {
      low: "low volatility",
      moderate: "moderate volatility",
      high: "high volatility",
      very_high: "very high volatility",
    },
    levels: {
      very_cheap: "Very Cheap",
      cheap: "Cheap",
      normal: "Normal",
      expensive: "Expensive",
      very_expensive: "Very Expensive",
    },
    hours: "Hours",
    day_parts: "Times of day",
    now: "Now",
    // "Now" at a glance (the line on top of the card, the now card)
    now_block: {
      best: "Best price period running",
      peak: "Peak price period running",
      ends: "ends {time}",
      left: "{duration} left",
      still_cheap: "still cheap until {time}",
      cheap_until: "cheap until {time}",
      cheap_from: "cheap from {time}",
      next_best: "best price from {time}",
      next_peak: "peak price from {time}",
      // One line in the tile, after the level
      short: {
        best: "best price for {duration}",
        peak: "peak price until {time}",
        peak_soon: "peak price in {duration}",
        cheap_until: "cheap until {time}",
        next_best: "best price in {duration}",
      },
      label: "Price now {price} {unit}, {level}. Today {low} to {high}, {average} {reference}.",
    },
    tomorrow: "Tomorrow",
    morning: "Morning",
    day: "Day",
    evening: "Evening",
    night: "Night",
    best: "Best price",
    trend: "Trend",
    peak: "Peak price",
    no_data: "No price outlook yet.",
    // The card's title, unless one of its own is set
    card_title: "Electricity prices",
    // The chart card: its views, its resolution switch and its curve
    chart: {
      open: "Price chart",
      outlook: "Outlook",
      two_days: "2 days",
      quarter_hour: "15 min",
      hour: "60 min",
      resolution: "Resolution",
      views: "Views",
      label: "Price curve: drag across it or use the arrow keys to read the prices",
      back_to_now: "Back to now",
      axis_time: "Time",
      axis_price: "Price",
      styles: "Style",
      // Against the average of what the view shows (its dashed line), where that's more than a day
      vs_view: {
        outlook: { mean: "{percent} vs. the outlook's average", median: "{percent} vs. the outlook's median" },
        two_days: { mean: "{percent} vs. the 2 days' average", median: "{percent} vs. the 2 days' median" },
      },
    },
  },
  de: {
    // A part of the day on a weekday, as the language says it; a night by the day it leads into
    // where its weekday name would be ambiguous ("Freitagnacht": Thursday's or Friday's?)
    part_on_day: {
      morning: "{weekday} früh",
      day: "{weekday} tagsüber",
      evening: "{weekday}abend",
      night: "Nacht zum {next}",
    },
    // Inside a sentence, where it differs ("in der Nacht zum Samstag")
    part_in_sentence: { night: "in der Nacht zum {next}" },
    action_button: { "more-info": "Mehr Infos", open: "Öffnen", run: "Ausführen" },
    day_details: {
      cheapest_hour: { today: "Günstigste Stunde heute noch", other: "Günstigste Stunde" },
      cheapest_part: { today: "Günstigste Tageszeit heute noch", other: "Günstigste Tageszeit" },
      passed: "schon vorbei",
    },
    detail: {
      // Where inside a part of the day it's cheapest
      cheapest_in: "am günstigsten {time}",
      now: {
        near_median: "etwa beim Median",
        now_price: "Aktueller Preis",
        valid_until: "gilt bis {time}",
        then: "danach {price} ({change})",
        this_hour: "Diese Stunde",
        this_part: "Diese Tageszeit",
        in_period: { best: "Bestpreis-Zeitraum bis {time}", peak: "Spitzenpreis-Zeitraum bis {time}" },
        next_best: "Nächster Bestpreis-Zeitraum ab {time} ({wait})",
        wait: "in {duration}",
        rank: {
          dearer: "Teurer als {percent} der Viertelstunden heute.",
          cheaper: "Günstiger als {percent} der Viertelstunden heute.",
        },
        energy: "Energiepreis",
        tax: "Steuern und Abgaben",
      },
      volatility: { low: "Gering", moderate: "Mäßig", high: "Stark", very_high: "Sehr stark" },
      legend_link: "Was bedeuten die Zeichen?",
      // Tomorrow before its prices are in
      pending: {
        title: "Noch keine Preise",
        prose:
          "Die Preise für morgen kommen meist am frühen Nachmittag. Sobald sie da sind, erscheinen sie hier von selbst.",
      },
      all_values: "Alle Werte",
      // The values behind a detail card, in a view of their own like HA's "Details"
      values: { title: "Details", prices: "Preise", times: "Zeitpunkte", periods: "Zeiträume", compare: "Vergleich" },
      unknown: "noch nicht bekannt",
      // One quarter hour picked in an hour's chart
      pick: {
        hint: "Viertelstunde antippen für Details",
        vs_hour: "{percent} zur Stunde",
        vs_day: { mean: "{percent} zum Tagesdurchschnitt", median: "{percent} zum Tagesmedian" },
        vs_now: "{percent} zu jetzt",
        rank: { dearer: "teurer als {percent} des Tages", cheaper: "günstiger als {percent} des Tages" },
      },
      facts: {
        time: "Zeit",
        mean: "Durchschnitt",
        median: "Median",
        quarters: "Viertelstunden",
        range: "Niedrigster–höchster",
        vs_day: { median: "Gegenüber Tagesmedian", mean: "Gegenüber Tagesdurchschnitt" },
        vs_now: "Gegenüber jetzt",
        vs_today: "Gegenüber heute",
        vs_tomorrow: "Gegenüber morgen",
        volatility: "Schwankung",
        now: "Jetzt",
        cheapest_hour: "Günstigste Stunde",
        cheapest_part: "Günstigste Tageszeit",
      },
      // Today against tomorrow, once its prices are in (inside a sentence)
      vs_tomorrow: {
        cheaper: "{percent} günstiger als morgen",
        dearer: "{percent} teurer als morgen",
        same: "etwa so teuer wie morgen",
      },
      vs_today: {
        cheaper: "{percent} günstiger als heute",
        dearer: "{percent} teurer als heute",
        same: "Etwa so teuer wie heute",
      },
      when_hour: { today: "heute ab {time}", other: "{weekday} ab {time}" },
      prose: {
        today_vs_tomorrow: "Heute ist es im Schnitt {comparison}.",
        past_hour: "Diese Stunde ist vorbei.",
        past_part: "Diese Tageszeit ist vorbei.",
        rises: "Im Lauf der Stunde steigt der Preis von {first} auf {last} {unit}.",
        falls: "Im Lauf der Stunde fällt der Preis von {first} auf {last} {unit}.",
        steady: "Der Preis bleibt die ganze Stunde über etwa gleich.",
        cheapest_quarter: "Die günstigste Viertelstunde beginnt um {time}.",
        part_spread:
          "Die günstigste Stunde beginnt um {cheap} ({cheapPrice} {unit}), die teuerste um {dear} ({dearPrice} {unit}).",
        partial: "Die Preise sind bisher nur bis {time} bekannt.",
        later: "Warten lohnt sich: {when} ist es {percent} günstiger.",
        nothing_cheaper: {
          hour: "Keine der kommenden Stunden ist deutlich günstiger.",
          part: "Keine der kommenden Tageszeiten ist deutlich günstiger.",
        },
        day_extremes: "Am günstigsten um {low} ({lowPrice} {unit}), am teuersten um {high} ({highPrice} {unit}).",
        day_ahead: "Von jetzt an beginnt die günstigste Stunde heute um {time} ({price} {unit}).",
      },
    },
    part_today: { morning: "heute früh", day: "heute tagsüber", evening: "heute Abend", night: "heute Nacht" },
    details: {
      above: { median: "über dem Tagesmedian", mean: "über dem Tagesdurchschnitt" },
      below: { median: "unter dem Tagesmedian", mean: "unter dem Tagesdurchschnitt" },
      same: { median: "auf dem Tagesmedian", mean: "auf dem Tagesdurchschnitt" },
      at: "{label} {price} {unit} um {time}",
      period: { best: "Bestpreis-Zeitraum", peak: "Spitzenpreis-Zeitraum" },
    },
    until: "bis {time}",
    partial_note: "nur bis {time} bekannt",
    earlier: "Früher",
    later: "Später",
    back: "Zurück",
    day_low: "Tagestief",
    day_high: "Tageshoch",
    passed: "vorbei",
    legend: {
      best_now: [
        "Bestpreis jetzt",
        "Das Sparschwein am Balken von jetzt: Gerade läuft ein Bestpreis-Zeitraum, ein guter Moment für Verbraucher",
      ],
      peak_now: [
        "Spitzenpreis jetzt",
        "Das Warndreieck am Balken von jetzt: Gerade läuft ein Spitzenpreis-Zeitraum, Verbraucher besser später einschalten",
      ],
      title: "Legende",
      // The marks of a detail card's chart
      zbar: ["Balken", "Seine Höhe ist der Preis dieser Viertelstunde oder Stunde"],
      zref_off: [
        "Außerhalb des Diagramms",
        "Pfeil mit Strich am Rand: die gestrichelte Linie des Tages liegt über oder unter den Balken",
      ],
      znow: ["Jetzt", "Die hervorgehobene Spalte läuft gerade"],
      zpast: ["Blass", "Schon vorbei"],
      zmissing: ["Leerer Platz", "Sein Preis ist noch nicht bekannt"],
      times: "Uhrzeiten",
      day_pointer: [
        "Zeiger: Tagesmedian",
        "Unter der Spanne eines Tages: Die Hälfte seiner Viertelstunden kostet weniger",
      ],
      day_now: [
        "Aktueller Preis",
        "Blaues Dreieck: wo der aktuelle Preis liegt, über der Spanne von heute und neben der laufenden Tageszeit",
      ],
      both: { hours: "Stunden und Tageszeiten", day_parts: "Tageszeiten und Stunden" },
      close: "Schließen",
      level: ["Preisniveau", "Die Farbe zeigt das Preisniveau:"],
      bar: [
        "Balken",
        { mean: "Seine Höhe ist der Durchschnittspreis der Stunde", median: "Seine Höhe ist der Median der Stunde" },
      ],
      span: ["Spanne", "Niedrigster bis höchster Preis der Tageszeit, der Zeiger markiert ihren Median"],
      reference: "Was unter der gestrichelten Linie liegt, ist günstiger als der Tag insgesamt",
      cheapest: [
        "Günstigste des Tages",
        "Je Tag, um wie viel die günstigste Stunde oder Tageszeit billiger ist als jetzt: heute ab jetzt, morgen, sobald die Preise da sind. Eine Nacht zählt zum Tag, an dem sie endet",
      ],
      best: "Farbige Linie unter einer Spalte: In diese Zeit fällt ein Bestpreis-Zeitraum",
      peak: "Farbige Linie unter einer Spalte: In diese Zeit fällt ein Spitzenpreis-Zeitraum",
      low: "Wann am Tag der niedrigste Preis gilt",
      high: "Wann am Tag der höchste Preis gilt",
      cut: ["Abgeschnitten", "Schräger Spalt oben: Der Preis liegt weit über dem Rest, die Zahl darunter nennt ihn"],
      partial: [
        "Teilweise bekannt",
        "Gestrichelt: Für diese Tageszeit sind Preise erst bis zur Uhrzeit darüber bekannt",
      ],
    },
    cheapest_tip: {
      hours: {
        today: "Günstigste Stunde heute noch: {percent} günstiger als jetzt (⌀ {price} statt {now} {unit})",
        tomorrow: "Günstigste Stunde morgen: {percent} günstiger als jetzt (⌀ {price} statt {now} {unit})",
      },
      parts: {
        today: "Günstigste Tageszeit heute noch: {percent} günstiger als jetzt (⌀ {price} statt {now} {unit})",
        tomorrow:
          "Günstigste Tageszeit morgen, die Nacht davor eingeschlossen: {percent} günstiger als jetzt (⌀ {price} statt {now} {unit})",
      },
    },
    median: "Median",
    day_reference: { median: "Tagesmedian", mean: "Tagesdurchschnitt" },
    today: "Heute",
    yesterday: "Gestern",
    days: "Tage",
    tomorrow_pending: "Preise kommen meist am frühen Nachmittag",
    volatility: {
      low: "geringe Schwankung",
      moderate: "mäßige Schwankung",
      high: "starke Schwankung",
      very_high: "sehr starke Schwankung",
    },
    levels: {
      very_cheap: "Sehr günstig",
      cheap: "Günstig",
      normal: "Normal",
      expensive: "Teuer",
      very_expensive: "Sehr teuer",
    },
    hours: "Stunden",
    day_parts: "Tageszeiten",
    now: "Jetzt",
    now_block: {
      best: "Bestpreis-Zeitraum läuft",
      peak: "Spitzenpreis-Zeitraum läuft",
      ends: "endet {time}",
      left: "noch {duration}",
      still_cheap: "danach noch günstig bis {time}",
      cheap_until: "günstig bis {time}",
      cheap_from: "günstig ab {time}",
      next_best: "Bestpreis ab {time}",
      next_peak: "Spitzenpreis ab {time}",
      short: {
        best: "Bestpreis noch {duration}",
        peak: "Spitzenpreis bis {time}",
        peak_soon: "Spitzenpreis in {duration}",
        cheap_until: "günstig bis {time}",
        next_best: "Bestpreis in {duration}",
      },
      label: "Preis jetzt {price} {unit}, {level}. Heute {low} bis {high}, {average} {reference}.",
    },
    tomorrow: "Morgen",
    morning: "Früh",
    day: "Tag",
    evening: "Abend",
    night: "Nacht",
    best: "Bestpreis",
    trend: "Trend",
    peak: "Spitzenpreis",
    no_data: "Noch keine Preisvorschau.",
    // The card's title, unless one of its own is set
    card_title: "Strompreise",
    // The chart card: its views, its resolution switch and its curve
    chart: {
      open: "Preisverlauf",
      outlook: "Ausblick",
      two_days: "2 Tage",
      quarter_hour: "15 min",
      hour: "60 min",
      resolution: "Auflösung",
      views: "Ansichten",
      label: "Preisverlauf: darüber ziehen oder die Pfeiltasten nutzen, um die Preise abzulesen",
      back_to_now: "Zurück zu jetzt",
      axis_time: "Uhrzeit",
      axis_price: "Preis",
      styles: "Darstellung",
      // Against the average of what the view shows (its dashed line), where that's more than a day
      vs_view: {
        outlook: { mean: "{percent} zum Durchschnitt im Ausblick", median: "{percent} zum Median im Ausblick" },
        two_days: { mean: "{percent} zum Durchschnitt der 2 Tage", median: "{percent} zum Median der 2 Tage" },
      },
    },
  },
  nb: {
    // A part of the day on a weekday, as the language says it; a night by the day it leads into
    // where its weekday name would be ambiguous ("Freitagnacht": Thursday's or Friday's?)
    part_on_day: {
      morning: "{weekday} morgen",
      day: "{weekday} på dagtid",
      evening: "{weekday} kveld",
      night: "natt til {next}",
    },
    // Inside a sentence, where it differs ("in der Nacht zum Samstag")
    part_in_sentence: {},
    action_button: { "more-info": "Mer info", open: "Åpne", run: "Kjør" },
    day_details: {
      cheapest_hour: { today: "Billigste time resten av i dag", other: "Billigste time" },
      cheapest_part: { today: "Billigste tid på døgnet resten av i dag", other: "Billigste tid på døgnet" },
      passed: "allerede passert",
    },
    detail: {
      // Where inside a part of the day it's cheapest
      cheapest_in: "billigst {time}",
      now: {
        near_median: "omtrent ved medianen",
        now_price: "Nåværende pris",
        valid_until: "gjelder til {time}",
        then: "deretter {price} ({change})",
        this_hour: "Denne timen",
        this_part: "Denne delen av dagen",
        in_period: { best: "Periode med beste pris til {time}", peak: "Periode med topppris til {time}" },
        next_best: "Neste periode med beste pris fra {time} ({wait})",
        wait: "om {duration}",
        rank: {
          dearer: "Dyrere enn {percent} av dagens kvarter.",
          cheaper: "Billigere enn {percent} av dagens kvarter.",
        },
        energy: "Energipris",
        tax: "Skatter og avgifter",
      },
      volatility: { low: "Lav", moderate: "Moderat", high: "Høy", very_high: "Svært høy" },
      legend_link: "Hva betyr tegnene?",
      // Tomorrow before its prices are in
      pending: {
        title: "Ingen priser ennå",
        prose:
          "Prisene for i morgen kommer vanligvis tidlig på ettermiddagen. Når de er klare, dukker de opp her av seg selv.",
      },
      all_values: "Alle verdier",
      // The values behind a detail card, in a view of their own like HA's "Details"
      values: {
        title: "Detaljer",
        prices: "Priser",
        times: "Tidspunkter",
        periods: "Perioder",
        compare: "Sammenligning",
      },
      unknown: "ikke kjent ennå",
      // One quarter hour picked in an hour's chart
      pick: {
        hint: "Trykk på et kvarter for detaljer",
        vs_hour: "{percent} mot timen",
        vs_day: { mean: "{percent} mot dagens snitt", median: "{percent} mot dagens median" },
        vs_now: "{percent} mot nå",
        rank: { dearer: "dyrere enn {percent} av dagen", cheaper: "billigere enn {percent} av dagen" },
      },
      facts: {
        time: "Tid",
        mean: "Gjennomsnitt",
        median: "Median",
        quarters: "Kvarter",
        range: "Laveste–høyeste",
        vs_day: { median: "Mot dagens median", mean: "Mot dagens gjennomsnitt" },
        vs_now: "Mot nå",
        vs_today: "Mot i dag",
        vs_tomorrow: "Mot i morgen",
        volatility: "Svingning",
        now: "Nå",
        cheapest_hour: "Billigste time",
        cheapest_part: "Billigste del av dagen",
      },
      // Today against tomorrow, once its prices are in (inside a sentence)
      vs_tomorrow: {
        cheaper: "{percent} billigere enn i morgen",
        dearer: "{percent} dyrere enn i morgen",
        same: "omtrent like dyrt som i morgen",
      },
      vs_today: {
        cheaper: "{percent} billigere enn i dag",
        dearer: "{percent} dyrere enn i dag",
        same: "Omtrent like dyrt som i dag",
      },
      when_hour: { today: "i dag fra {time}", other: "{weekday} fra {time}" },
      prose: {
        today_vs_tomorrow: "I snitt er i dag {comparison}.",
        past_hour: "Denne timen er over.",
        past_part: "Denne delen av dagen er over.",
        rises: "I løpet av timen stiger prisen fra {first} til {last} {unit}.",
        falls: "I løpet av timen faller prisen fra {first} til {last} {unit}.",
        steady: "Prisen holder seg omtrent lik hele timen.",
        cheapest_quarter: "Det billigste kvarteret begynner kl. {time}.",
        part_spread:
          "Den billigste timen begynner kl. {cheap} ({cheapPrice} {unit}), den dyreste kl. {dear} ({dearPrice} {unit}).",
        partial: "Prisene er foreløpig bare kjent til {time}.",
        later: "Det lønner seg å vente: {when} er det {percent} billigere.",
        nothing_cheaper: {
          hour: "Ingen av de kommende timene er tydelig billigere.",
          part: "Ingen av de kommende delene av dagen er tydelig billigere.",
        },
        day_extremes: "Billigst kl. {low} ({lowPrice} {unit}), dyrest kl. {high} ({highPrice} {unit}).",
        day_ahead: "Fra nå av begynner dagens billigste time kl. {time} ({price} {unit}).",
      },
    },
    part_today: { morning: "i dag tidlig", day: "i dag på dagtid", evening: "i kveld", night: "i natt" },
    details: {
      above: { median: "over dagsmedianen", mean: "over dagsgjennomsnittet" },
      below: { median: "under dagsmedianen", mean: "under dagsgjennomsnittet" },
      same: { median: "på dagsmedianen", mean: "på dagsgjennomsnittet" },
      at: "{label} {price} {unit} kl. {time}",
      period: { best: "Periode med beste pris", peak: "Periode med topppris" },
    },
    until: "til {time}",
    partial_note: "kjent bare til {time}",
    earlier: "Tidligere",
    later: "Senere",
    back: "Tilbake",
    day_low: "Dagens laveste",
    day_high: "Dagens høyeste",
    passed: "passert",
    legend: {
      best_now: [
        "Beste pris nå",
        "Sparegrisen ved stolpen for nå: en periode med beste pris pågår, et godt tidspunkt for apparater",
      ],
      peak_now: [
        "Topppris nå",
        "Varseltrekanten ved stolpen for nå: en periode med topppris pågår, slå heller på apparater senere",
      ],
      title: "Tegnforklaring",
      // The marks of a detail card's chart
      zbar: ["Stolpe", "Høyden er prisen for det kvarteret eller den timen"],
      zref_off: [
        "Utenfor diagrammet",
        "Pil med strek i kanten: dagens stiplede linje ligger over eller under stolpene",
      ],
      znow: ["Nå", "Den uthevede kolonnen pågår nå"],
      zpast: ["Blek", "Allerede forbi"],
      zmissing: ["Tom plass", "Prisen er ikke kjent ennå"],
      times: "Klokkeslett",
      day_pointer: ["Peker: dagsmedian", "Under dagens spenn: halvparten av kvarterene koster mindre"],
      day_now: [
        "Nåværende pris",
        "Blå trekant: hvor den nåværende prisen ligger, over dagens spenn og ved delen av dagen som pågår",
      ],
      both: { hours: "Timer og tider på døgnet", day_parts: "Tider på døgnet og timer" },
      close: "Lukk",
      level: ["Prisnivå", "Fargen viser prisnivået:"],
      bar: ["Stolpe", { mean: "Høyden er timens gjennomsnittspris", median: "Høyden er timens medianpris" }],
      span: ["Spenn", "Laveste til høyeste pris i tiden på døgnet, pekeren markerer medianen"],
      reference: "Det som ligger under den stiplede linjen, er billigere enn døgnet totalt",
      cheapest: [
        "Billigst per dag",
        "Per dag, hvor mye billigere enn nå den billigste timen eller tiden på døgnet er: i dag fra nå, i morgen når prisene er kommet. En natt teller for dagen den slutter",
      ],
      best: "Farget linje under en kolonne: en periode med beste pris faller i denne tiden",
      peak: "Farget linje under en kolonne: en periode med topppris faller i denne tiden",
      low: "Når dagens laveste pris gjelder",
      high: "Når dagens høyeste pris gjelder",
      cut: ["Avkuttet", "Skrå glipe øverst: prisen ligger langt over resten, tallet under viser hvor høyt"],
      partial: ["Delvis kjent", "Stiplet: prisene for denne tiden på døgnet er bare kjent frem til klokkeslettet over"],
    },
    cheapest_tip: {
      hours: {
        today: "Billigste time resten av i dag: {percent} billigere enn nå (⌀ {price} i stedet for {now} {unit})",
        tomorrow: "Billigste time i morgen: {percent} billigere enn nå (⌀ {price} i stedet for {now} {unit})",
      },
      parts: {
        today:
          "Billigste tid på døgnet resten av i dag: {percent} billigere enn nå (⌀ {price} i stedet for {now} {unit})",
        tomorrow:
          "Billigste tid på døgnet i morgen, natten før medregnet: {percent} billigere enn nå (⌀ {price} i stedet for {now} {unit})",
      },
    },
    median: "Median",
    day_reference: { median: "Dagsmedian", mean: "Dagsgjennomsnitt" },
    today: "I dag",
    yesterday: "I går",
    days: "Dager",
    tomorrow_pending: "Prisene kommer vanligvis tidlig på ettermiddagen",
    volatility: {
      low: "lav variasjon",
      moderate: "moderat variasjon",
      high: "høy variasjon",
      very_high: "svært høy variasjon",
    },
    levels: {
      very_cheap: "Veldig billig",
      cheap: "Billig",
      normal: "Normal",
      expensive: "Dyr",
      very_expensive: "Veldig dyr",
    },
    hours: "Timer",
    day_parts: "Tider på døgnet",
    now: "Nå",
    now_block: {
      best: "Periode med beste pris pågår",
      peak: "Periode med topppris pågår",
      ends: "slutter {time}",
      left: "{duration} igjen",
      still_cheap: "fortsatt billig til {time}",
      cheap_until: "billig til {time}",
      cheap_from: "billig fra {time}",
      next_best: "beste pris fra {time}",
      next_peak: "topppris fra {time}",
      short: {
        best: "beste pris, {duration} igjen",
        peak: "topppris til {time}",
        peak_soon: "topppris om {duration}",
        cheap_until: "billig til {time}",
        next_best: "beste pris om {duration}",
      },
      label: "Pris nå {price} {unit}, {level}. I dag {low} til {high}, {average} {reference}.",
    },
    tomorrow: "I morgen",
    morning: "Morgen",
    day: "Dag",
    evening: "Kveld",
    night: "Natt",
    best: "Beste pris",
    trend: "Trend",
    peak: "Topppris",
    no_data: "Ingen prisoversikt ennå.",
    // The card's title, unless one of its own is set
    card_title: "Strømpriser",
    // The chart card: its views, its resolution switch and its curve
    chart: {
      open: "Prisforløp",
      outlook: "Fremover",
      two_days: "2 dager",
      quarter_hour: "15 min",
      hour: "60 min",
      resolution: "Oppløsning",
      views: "Visninger",
      label: "Priskurve: dra over den eller bruk piltastene for å lese av prisene",
      back_to_now: "Tilbake til nå",
      axis_time: "Tid",
      axis_price: "Pris",
      styles: "Stil",
      // Against the average of what the view shows (its dashed line), where that's more than a day
      vs_view: {
        outlook: { mean: "{percent} mot snittet fremover", median: "{percent} mot medianen fremover" },
        two_days: { mean: "{percent} mot snittet for de 2 dagene", median: "{percent} mot medianen for de 2 dagene" },
      },
    },
  },
  nl: {
    // A part of the day on a weekday, as the language says it; a night by the day it leads into
    // where its weekday name would be ambiguous ("Freitagnacht": Thursday's or Friday's?)
    part_on_day: {
      morning: "{weekday}ochtend",
      day: "{weekday} overdag",
      evening: "{weekday}avond",
      night: "nacht naar {next}",
    },
    // Inside a sentence, where it differs ("in der Nacht zum Samstag")
    part_in_sentence: { night: "in de nacht naar {next}" },
    action_button: { "more-info": "Meer info", open: "Openen", run: "Uitvoeren" },
    day_details: {
      cheapest_hour: { today: "Goedkoopste uur nog vandaag", other: "Goedkoopste uur" },
      cheapest_part: { today: "Goedkoopste dagdeel nog vandaag", other: "Goedkoopste dagdeel" },
      passed: "al voorbij",
    },
    detail: {
      // Where inside a part of the day it's cheapest
      cheapest_in: "het goedkoopst {time}",
      now: {
        near_median: "ongeveer op de mediaan",
        now_price: "Huidige prijs",
        valid_until: "geldt tot {time}",
        then: "daarna {price} ({change})",
        this_hour: "Dit uur",
        this_part: "Dit dagdeel",
        in_period: { best: "Periode met beste prijs tot {time}", peak: "Periode met piekprijs tot {time}" },
        next_best: "Volgende periode met beste prijs vanaf {time} ({wait})",
        wait: "over {duration}",
        rank: {
          dearer: "Duurder dan {percent} van de kwartieren van vandaag.",
          cheaper: "Goedkoper dan {percent} van de kwartieren van vandaag.",
        },
        energy: "Energieprijs",
        tax: "Belastingen en heffingen",
      },
      volatility: { low: "Laag", moderate: "Gemiddeld", high: "Hoog", very_high: "Zeer hoog" },
      legend_link: "Wat betekenen de tekens?",
      // Tomorrow before its prices are in
      pending: {
        title: "Nog geen prijzen",
        prose:
          "De prijzen voor morgen komen meestal in de vroege middag. Zodra ze er zijn, verschijnen ze hier vanzelf.",
      },
      all_values: "Alle waarden",
      // The values behind a detail card, in a view of their own like HA's "Details"
      values: {
        title: "Details",
        prices: "Prijzen",
        times: "Tijdstippen",
        periods: "Periodes",
        compare: "Vergelijking",
      },
      unknown: "nog niet bekend",
      // One quarter hour picked in an hour's chart
      pick: {
        hint: "Tik op een kwartier voor details",
        vs_hour: "{percent} t.o.v. het uur",
        vs_day: { mean: "{percent} t.o.v. het daggemiddelde", median: "{percent} t.o.v. de dagmediaan" },
        vs_now: "{percent} t.o.v. nu",
        rank: { dearer: "duurder dan {percent} van de dag", cheaper: "goedkoper dan {percent} van de dag" },
      },
      facts: {
        time: "Tijd",
        mean: "Gemiddelde",
        median: "Mediaan",
        quarters: "Kwartieren",
        range: "Laagste–hoogste",
        vs_day: { median: "Ten opzichte van de dagmediaan", mean: "Ten opzichte van het daggemiddelde" },
        vs_now: "Ten opzichte van nu",
        vs_today: "Ten opzichte van vandaag",
        vs_tomorrow: "Ten opzichte van morgen",
        volatility: "Schommeling",
        now: "Nu",
        cheapest_hour: "Goedkoopste uur",
        cheapest_part: "Goedkoopste dagdeel",
      },
      // Today against tomorrow, once its prices are in (inside a sentence)
      vs_tomorrow: {
        cheaper: "{percent} goedkoper dan morgen",
        dearer: "{percent} duurder dan morgen",
        same: "ongeveer even duur als morgen",
      },
      vs_today: {
        cheaper: "{percent} goedkoper dan vandaag",
        dearer: "{percent} duurder dan vandaag",
        same: "Ongeveer even duur als vandaag",
      },
      when_hour: { today: "vandaag vanaf {time}", other: "{weekday} vanaf {time}" },
      prose: {
        today_vs_tomorrow: "Gemiddeld is vandaag {comparison}.",
        past_hour: "Dit uur is voorbij.",
        past_part: "Dit dagdeel is voorbij.",
        rises: "In de loop van het uur stijgt de prijs van {first} naar {last} {unit}.",
        falls: "In de loop van het uur daalt de prijs van {first} naar {last} {unit}.",
        steady: "De prijs blijft het hele uur ongeveer gelijk.",
        cheapest_quarter: "Het goedkoopste kwartier begint om {time}.",
        part_spread:
          "Het goedkoopste uur begint om {cheap} ({cheapPrice} {unit}), het duurste om {dear} ({dearPrice} {unit}).",
        partial: "De prijzen zijn tot nu toe alleen bekend tot {time}.",
        later: "Wachten loont: {when} is het {percent} goedkoper.",
        nothing_cheaper: {
          hour: "Geen van de komende uren is duidelijk goedkoper.",
          part: "Geen van de komende dagdelen is duidelijk goedkoper.",
        },
        day_extremes: "Het goedkoopst om {low} ({lowPrice} {unit}), het duurst om {high} ({highPrice} {unit}).",
        day_ahead: "Vanaf nu begint het goedkoopste uur van vandaag om {time} ({price} {unit}).",
      },
    },
    part_today: { morning: "vanochtend", day: "vandaag overdag", evening: "vanavond", night: "vannacht" },
    details: {
      above: { median: "boven de dagmediaan", mean: "boven het daggemiddelde" },
      below: { median: "onder de dagmediaan", mean: "onder het daggemiddelde" },
      same: { median: "op de dagmediaan", mean: "op het daggemiddelde" },
      at: "{label} {price} {unit} om {time}",
      period: { best: "Periode met beste prijs", peak: "Periode met piekprijs" },
    },
    until: "tot {time}",
    partial_note: "alleen bekend tot {time}",
    earlier: "Eerder",
    later: "Later",
    back: "Terug",
    day_low: "Dagdieptepunt",
    day_high: "Daghoogtepunt",
    passed: "voorbij",
    legend: {
      best_now: [
        "Beste prijs nu",
        "Het spaarvarken bij de balk van nu: er loopt een periode met beste prijs, een goed moment voor apparaten",
      ],
      peak_now: [
        "Piekprijs nu",
        "De gevarendriehoek bij de balk van nu: er loopt een periode met piekprijs, zet apparaten liever later aan",
      ],
      title: "Legenda",
      // The marks of a detail card's chart
      zbar: ["Staaf", "De hoogte is de prijs van dat kwartier of uur"],
      zref_off: [
        "Buiten de grafiek",
        "Pijl met streepje aan de rand: de stippellijn van de dag ligt boven of onder de staven",
      ],
      znow: ["Nu", "De gemarkeerde kolom loopt nu"],
      zpast: ["Vervaagd", "Al voorbij"],
      zmissing: ["Lege plek", "De prijs is nog niet bekend"],
      times: "Tijden",
      day_pointer: ["Wijzer: dagmediaan", "Onder de spanne van een dag: de helft van de kwartieren kost minder"],
      day_now: [
        "Huidige prijs",
        "Blauwe driehoek: waar de huidige prijs ligt, boven de spanne van vandaag en naast het lopende dagdeel",
      ],
      both: { hours: "Uren en dagdelen", day_parts: "Dagdelen en uren" },
      close: "Sluiten",
      level: ["Prijsniveau", "De kleur toont het prijsniveau:"],
      bar: [
        "Staaf",
        { mean: "De hoogte is de gemiddelde prijs van het uur", median: "De hoogte is de mediaanprijs van het uur" },
      ],
      span: ["Bereik", "Laagste tot hoogste prijs van het dagdeel; de wijzer markeert de mediaan"],
      reference: "Wat onder de stippellijn ligt, is goedkoper dan de dag als geheel",
      cheapest: [
        "Goedkoopst per dag",
        "Per dag hoeveel goedkoper dan nu het goedkoopste uur of dagdeel is: vandaag vanaf nu, morgen zodra de prijzen er zijn. Een nacht telt mee voor de dag waarop hij eindigt",
      ],
      best: "Gekleurde lijn onder een kolom: in deze tijd valt een periode met de beste prijs",
      peak: "Gekleurde lijn onder een kolom: in deze tijd valt een periode met piekprijs",
      low: "Wanneer de laagste prijs van de dag geldt",
      high: "Wanneer de hoogste prijs van de dag geldt",
      cut: ["Afgekapt", "Schuine opening bovenaan: de prijs ligt ver boven de rest, het getal eronder zegt hoe hoog"],
      partial: ["Deels bekend", "Gestippeld: prijzen voor dit dagdeel zijn alleen bekend tot het tijdstip erboven"],
    },
    cheapest_tip: {
      hours: {
        today: "Goedkoopste uur nog vandaag: {percent} goedkoper dan nu (⌀ {price} in plaats van {now} {unit})",
        tomorrow: "Goedkoopste uur morgen: {percent} goedkoper dan nu (⌀ {price} in plaats van {now} {unit})",
      },
      parts: {
        today: "Goedkoopste dagdeel nog vandaag: {percent} goedkoper dan nu (⌀ {price} in plaats van {now} {unit})",
        tomorrow:
          "Goedkoopste dagdeel morgen, de nacht ervoor inbegrepen: {percent} goedkoper dan nu (⌀ {price} in plaats van {now} {unit})",
      },
    },
    median: "Mediaan",
    day_reference: { median: "Dagmediaan", mean: "Daggemiddelde" },
    today: "Vandaag",
    yesterday: "Gisteren",
    days: "Dagen",
    tomorrow_pending: "Prijzen komen meestal in de vroege middag",
    volatility: {
      low: "weinig schommeling",
      moderate: "matige schommeling",
      high: "sterke schommeling",
      very_high: "zeer sterke schommeling",
    },
    levels: {
      very_cheap: "Zeer Goedkoop",
      cheap: "Goedkoop",
      normal: "Normaal",
      expensive: "Duur",
      very_expensive: "Zeer Duur",
    },
    hours: "Uren",
    day_parts: "Dagdelen",
    now: "Nu",
    now_block: {
      best: "Periode met beste prijs loopt",
      peak: "Periode met piekprijs loopt",
      ends: "eindigt {time}",
      left: "nog {duration}",
      still_cheap: "daarna nog goedkoop tot {time}",
      cheap_until: "goedkoop tot {time}",
      cheap_from: "goedkoop vanaf {time}",
      next_best: "beste prijs vanaf {time}",
      next_peak: "piekprijs vanaf {time}",
      short: {
        best: "beste prijs nog {duration}",
        peak: "piekprijs tot {time}",
        peak_soon: "piekprijs over {duration}",
        cheap_until: "goedkoop tot {time}",
        next_best: "beste prijs over {duration}",
      },
      label: "Prijs nu {price} {unit}, {level}. Vandaag {low} tot {high}, {average} {reference}.",
    },
    tomorrow: "Morgen",
    morning: "Ochtend",
    day: "Dag",
    evening: "Avond",
    night: "Nacht",
    best: "Beste prijs",
    trend: "Trend",
    peak: "Piekprijs",
    no_data: "Nog geen prijsvooruitblik.",
    // The card's title, unless one of its own is set
    card_title: "Stroomprijzen",
    // The chart card: its views, its resolution switch and its curve
    chart: {
      open: "Prijsverloop",
      outlook: "Vooruitblik",
      two_days: "2 dagen",
      quarter_hour: "15 min",
      hour: "60 min",
      resolution: "Resolutie",
      views: "Weergaven",
      label: "Prijsverloop: sleep eroverheen of gebruik de pijltjestoetsen om de prijzen af te lezen",
      back_to_now: "Terug naar nu",
      axis_time: "Tijd",
      axis_price: "Prijs",
      styles: "Stijl",
      // Against the average of what the view shows (its dashed line), where that's more than a day
      vs_view: {
        outlook: {
          mean: "{percent} t.o.v. het gemiddelde in de vooruitblik",
          median: "{percent} t.o.v. de mediaan in de vooruitblik",
        },
        two_days: {
          mean: "{percent} t.o.v. het gemiddelde van de 2 dagen",
          median: "{percent} t.o.v. de mediaan van de 2 dagen",
        },
      },
    },
  },
  sv: {
    // A part of the day on a weekday, as the language says it; a night by the day it leads into
    // where its weekday name would be ambiguous ("Freitagnacht": Thursday's or Friday's?)
    part_on_day: {
      morning: "{weekday} morgon",
      day: "{weekday} dagtid",
      evening: "{weekday} kväll",
      night: "natten till {next}",
    },
    // Inside a sentence, where it differs ("in der Nacht zum Samstag")
    part_in_sentence: {},
    action_button: { "more-info": "Mer info", open: "Öppna", run: "Kör" },
    day_details: {
      cheapest_hour: { today: "Billigaste timmen under resten av i dag", other: "Billigaste timmen" },
      cheapest_part: { today: "Billigaste tiden på dygnet under resten av i dag", other: "Billigaste tiden på dygnet" },
      passed: "redan passerat",
    },
    detail: {
      // Where inside a part of the day it's cheapest
      cheapest_in: "billigast {time}",
      now: {
        near_median: "ungefär vid medianen",
        now_price: "Aktuellt pris",
        valid_until: "gäller till {time}",
        then: "sedan {price} ({change})",
        this_hour: "Den här timmen",
        this_part: "Den här tiden på dagen",
        in_period: { best: "Period med bästa pris till {time}", peak: "Period med topppris till {time}" },
        next_best: "Nästa period med bästa pris från {time} ({wait})",
        wait: "om {duration}",
        rank: {
          dearer: "Dyrare än {percent} av dagens kvartar.",
          cheaper: "Billigare än {percent} av dagens kvartar.",
        },
        energy: "Energipris",
        tax: "Skatter och avgifter",
      },
      volatility: { low: "Låg", moderate: "Måttlig", high: "Hög", very_high: "Mycket hög" },
      legend_link: "Vad betyder tecknen?",
      // Tomorrow before its prices are in
      pending: {
        title: "Inga priser än",
        prose: "Priserna för i morgon kommer oftast tidigt på eftermiddagen. När de finns visas de här av sig själva.",
      },
      all_values: "Alla värden",
      // The values behind a detail card, in a view of their own like HA's "Details"
      values: { title: "Detaljer", prices: "Priser", times: "Tidpunkter", periods: "Perioder", compare: "Jämförelse" },
      unknown: "inte känt ännu",
      // One quarter hour picked in an hour's chart
      pick: {
        hint: "Tryck på en kvart för detaljer",
        vs_hour: "{percent} mot timmen",
        vs_day: { mean: "{percent} mot dagens snitt", median: "{percent} mot dagens median" },
        vs_now: "{percent} mot nu",
        rank: { dearer: "dyrare än {percent} av dagen", cheaper: "billigare än {percent} av dagen" },
      },
      facts: {
        time: "Tid",
        mean: "Medelvärde",
        median: "Median",
        quarters: "Kvartar",
        range: "Lägsta–högsta",
        vs_day: { median: "Jämfört med dagens median", mean: "Jämfört med dagens medelvärde" },
        vs_now: "Jämfört med nu",
        vs_today: "Jämfört med i dag",
        vs_tomorrow: "Jämfört med i morgon",
        volatility: "Svängning",
        now: "Nu",
        cheapest_hour: "Billigaste timme",
        cheapest_part: "Billigaste tid på dagen",
      },
      // Today against tomorrow, once its prices are in (inside a sentence)
      vs_tomorrow: {
        cheaper: "{percent} billigare än i morgon",
        dearer: "{percent} dyrare än i morgon",
        same: "ungefär lika dyrt som i morgon",
      },
      vs_today: {
        cheaper: "{percent} billigare än i dag",
        dearer: "{percent} dyrare än i dag",
        same: "Ungefär lika dyrt som i dag",
      },
      when_hour: { today: "i dag från {time}", other: "{weekday} från {time}" },
      prose: {
        today_vs_tomorrow: "I snitt är i dag {comparison}.",
        past_hour: "Den här timmen är över.",
        past_part: "Den här tiden på dagen är över.",
        rises: "Under timmen stiger priset från {first} till {last} {unit}.",
        falls: "Under timmen sjunker priset från {first} till {last} {unit}.",
        steady: "Priset ligger ungefär lika hela timmen.",
        cheapest_quarter: "Den billigaste kvarten börjar {time}.",
        part_spread:
          "Den billigaste timmen börjar {cheap} ({cheapPrice} {unit}), den dyraste {dear} ({dearPrice} {unit}).",
        partial: "Priserna är hittills bara kända till {time}.",
        later: "Det lönar sig att vänta: {when} är det {percent} billigare.",
        nothing_cheaper: {
          hour: "Ingen av de kommande timmarna är tydligt billigare.",
          part: "Ingen av de kommande tiderna på dagen är tydligt billigare.",
        },
        day_extremes: "Billigast {low} ({lowPrice} {unit}), dyrast {high} ({highPrice} {unit}).",
        day_ahead: "Från och med nu börjar dagens billigaste timme {time} ({price} {unit}).",
      },
    },
    part_today: { morning: "i dag på morgonen", day: "i dag på dagen", evening: "i kväll", night: "i natt" },
    details: {
      above: { median: "över dagsmedianen", mean: "över dagsgenomsnittet" },
      below: { median: "under dagsmedianen", mean: "under dagsgenomsnittet" },
      same: { median: "på dagsmedianen", mean: "på dagsgenomsnittet" },
      at: "{label} {price} {unit} kl. {time}",
      period: { best: "Period med bästa pris", peak: "Period med topppris" },
    },
    until: "till {time}",
    partial_note: "känt bara till {time}",
    earlier: "Tidigare",
    later: "Senare",
    back: "Tillbaka",
    day_low: "Dagens lägsta",
    day_high: "Dagens högsta",
    passed: "passerat",
    legend: {
      best_now: [
        "Bästa pris nu",
        "Spargrisen vid stapeln för nu: en period med bästa pris pågår, ett bra tillfälle för apparater",
      ],
      peak_now: [
        "Topppris nu",
        "Varningstriangeln vid stapeln för nu: en period med topppris pågår, slå hellre på apparater senare",
      ],
      title: "Teckenförklaring",
      // The marks of a detail card's chart
      zbar: ["Stapel", "Höjden är priset för den kvarten eller timmen"],
      zref_off: [
        "Utanför diagrammet",
        "Pil med streck i kanten: dagens streckade linje ligger över eller under staplarna",
      ],
      znow: ["Nu", "Den markerade kolumnen pågår nu"],
      zpast: ["Blek", "Redan förbi"],
      zmissing: ["Tom plats", "Priset är inte känt än"],
      times: "Klockslag",
      day_pointer: ["Pekare: dagsmedian", "Under dagens spann: hälften av kvartarna kostar mindre"],
      day_now: [
        "Aktuellt pris",
        "Blå triangel: var det aktuella priset ligger, över dagens spann och bredvid den pågående tiden på dagen",
      ],
      both: { hours: "Timmar och tider på dygnet", day_parts: "Tider på dygnet och timmar" },
      close: "Stäng",
      level: ["Prisnivå", "Färgen visar prisnivån:"],
      bar: ["Stapel", { mean: "Höjden är timmens genomsnittspris", median: "Höjden är timmens medianpris" }],
      span: ["Spann", "Lägsta till högsta pris under tiden på dygnet, pekaren markerar medianen"],
      reference: "Det som ligger under den streckade linjen är billigare än dygnet som helhet",
      cheapest: [
        "Billigast per dag",
        "Per dag, hur mycket billigare än nu den billigaste timmen eller tiden på dygnet är: i dag från nu, imorgon när priserna har kommit. En natt räknas till dagen den slutar",
      ],
      best: "Färgad linje under en kolumn: en period med bästa pris infaller under den här tiden",
      peak: "Färgad linje under en kolumn: en period med topppris infaller under den här tiden",
      low: "När dagens lägsta pris gäller",
      high: "När dagens högsta pris gäller",
      cut: ["Avkapad", "Snett glapp upptill: priset ligger långt över resten, talet under visar hur högt"],
      partial: ["Delvis känt", "Streckat: priserna för den här tiden på dygnet är bara kända fram till tiden ovanför"],
    },
    cheapest_tip: {
      hours: {
        today:
          "Billigaste timmen under resten av i dag: {percent} billigare än nu (⌀ {price} i stället för {now} {unit})",
        tomorrow: "Billigaste timmen imorgon: {percent} billigare än nu (⌀ {price} i stället för {now} {unit})",
      },
      parts: {
        today:
          "Billigaste tiden på dygnet under resten av i dag: {percent} billigare än nu (⌀ {price} i stället för {now} {unit})",
        tomorrow:
          "Billigaste tiden på dygnet imorgon, natten före inräknad: {percent} billigare än nu (⌀ {price} i stället för {now} {unit})",
      },
    },
    median: "Median",
    day_reference: { median: "Dagsmedian", mean: "Dagsgenomsnitt" },
    today: "Idag",
    yesterday: "Igår",
    days: "Dagar",
    tomorrow_pending: "Priserna kommer oftast tidigt på eftermiddagen",
    volatility: {
      low: "låg variation",
      moderate: "måttlig variation",
      high: "hög variation",
      very_high: "mycket hög variation",
    },
    levels: {
      very_cheap: "Mycket billigt",
      cheap: "Billigt",
      normal: "Normalt",
      expensive: "Dyrt",
      very_expensive: "Mycket dyrt",
    },
    hours: "Timmar",
    day_parts: "Tider på dygnet",
    now: "Nu",
    now_block: {
      best: "Period med bästa pris pågår",
      peak: "Period med topppris pågår",
      ends: "slutar {time}",
      left: "{duration} kvar",
      still_cheap: "fortfarande billigt till {time}",
      cheap_until: "billigt till {time}",
      cheap_from: "billigt från {time}",
      next_best: "bästa pris från {time}",
      next_peak: "topppris från {time}",
      short: {
        best: "bästa pris, {duration} kvar",
        peak: "topppris till {time}",
        peak_soon: "topppris om {duration}",
        cheap_until: "billigt till {time}",
        next_best: "bästa pris om {duration}",
      },
      label: "Pris nu {price} {unit}, {level}. I dag {low} till {high}, {average} {reference}.",
    },
    tomorrow: "Imorgon",
    morning: "Morgon",
    day: "Dag",
    evening: "Kväll",
    night: "Natt",
    best: "Bästa pris",
    trend: "Trend",
    peak: "Topppris",
    no_data: "Ingen prisöversikt än.",
    // The card's title, unless one of its own is set
    card_title: "Elpriser",
    // The chart card: its views, its resolution switch and its curve
    chart: {
      open: "Prisförlopp",
      outlook: "Framåt",
      two_days: "2 dagar",
      quarter_hour: "15 min",
      hour: "60 min",
      resolution: "Upplösning",
      views: "Vyer",
      label: "Priskurva: dra över den eller använd piltangenterna för att läsa av priserna",
      back_to_now: "Tillbaka till nu",
      axis_time: "Tid",
      axis_price: "Pris",
      styles: "Stil",
      // Against the average of what the view shows (its dashed line), where that's more than a day
      vs_view: {
        outlook: { mean: "{percent} mot snittet framåt", median: "{percent} mot medianen framåt" },
        two_days: { mean: "{percent} mot snittet för de 2 dagarna", median: "{percent} mot medianen för de 2 dagarna" },
      },
    },
  },
};

// Labels of the visual editor (the card's own texts are in STRINGS)
const EDITOR_STRINGS = {
  en: {
    chart_button: "Icon for the chart card",
    chart_button_help: "Top right; opens the price chart in a window",
    chart_icon: "Icon",
    tap_opens_chart: "Chart card in a window",
    nested_chart: "Chart card in a window",
    nested_forecast: "Forecast card in a window",
    nested_help: "Its own settings",
    nested_back: "Back",
    day_shade_strength: "Day line: shade",
    day_shade_strength_help: "At the line, towards the other day; one value for light and dark themes. 0: none",
    day_shade_width: "Day line: shade reach",
    day_shade_width_help: "Hours of the view",
    day_line_width: "Day line: thickness",
    day_line_width_help: "Default 1 px; 0: none",
    day_line_strength: "Day line: strength",
    day_line_strength_help: "Share of the text color. Empty: as the price lines",
    grid_line_width: "Price lines: thickness",
    grid_line_width_help: "Default 0.75 px; 0: none",
    grid_line_strength: "Price lines: strength",
    grid_line_strength_help:
      "Share of the text color, so it suits light and dark themes alike. Empty: the theme's divider color",
    header_details: "Level and gap in the top line",
    header_level: "Price level",
    header_delta: "Gap from the average",
    chip_show_always: "Always",
    chip_show_reading: "Only while reading prices",
    chip_show_never: "Never",
    header_level_at: "Only at these levels",
    header_level_at_help: "None ticked: at every level",
    header_delta_from: "Only from a gap of",
    header_delta_from_help:
      "0: at any gap; else only where the price lies at least this far above or below the average",
    axis_decimals: "Decimals of the price axis",
    axis_decimals_auto: "By the unit (€, kr: one; ct, øre: none)",
    axis_title_x: "Title of the time axis",
    axis_title_y: "Title of the price axis",
    units: "Units",
    unit_place_header: "In the top line",
    unit_place_tag: "On the cursor's tag",
    unit_place_axis: "At the price axis",
    unit_display_full: "Unit rate (e.g. ct/kWh)",
    unit_display_currency: "Currency only (e.g. ct)",
    unit_display_none: "None",
    unit_display_help:
      "The unit rate is the price per kWh; a small ring shows the currency only. Screen readers always read the whole unit",
    day_colors: "Day colors",
    day_colors_help: "The pills of yesterday, today and tomorrow above the curve (now's is in the color of now)",
    header: "Top line",
    header_chips: "A line with chips",
    header_dial: "Ring",
    header_none: "Hide",
    header_help:
      "Without it, the tag above the curve still shows the time and price; actions run from the card's own button only",
    style_number: "Style {n}",
    style_label: "Name",
    chart_tap_action_help: "On the card's top (price and time); a tap on the curve moves the cursor",
    default_mark: "default",
    view_inherit_option: "As for all views ({value})",
    device_id: "Home",
    device_id_help: "Your Tibber home, or one of its time-travel views",
    price_unit: "Price unit",
    unit_auto: "As set in the integration",
    unit_base: "Base currency (e.g. €/kWh)",
    unit_subunit: "Subunit (e.g. ct/kWh)",
    interactions: "Interactions",
    average: "Average shown",
    average_help:
      "The prices shown and the dashed line in hours and parts of the day; the pointers and the line in the day rows always show the median",
    average_mean: "Arithmetic mean",
    average_median: "Median",
    hide_details: "Turn off details on tap",
    hide_details_help: "A tap then runs the card's action; hover hints stay",
    action_button: "Card action via its own button",
    action_button_help: "Only this button in the footer runs the card's actions; tapping the card no longer does",
    action_button_text: "Button text",
    action_button_text_help: "Empty: fits the action, e.g. “More info”",
    action_button_position: "Button position",
    action_button_position_top: "Top",
    action_button_position_bottom: "Bottom",
    tap_action: "Tap behavior",
    hold_action: "Hold behavior",
    double_tap_action: "Double tap behavior",
    entity: "Entity for More info",
    entity_help: "Opened by a “More info” action; empty: the home's price sensor",
    show_title: "Show title",
    title: "Title",
    title_help: "Empty: “Electricity prices”",
    layout: "Layout",
    detailed: "Detailed",
    compact: "Compact",
    layout_help: "Detailed: all sections, one below the other. Compact: one section at a time, with a switch",
    show: "Sections",
    now_decimals: "Decimals of the current price",
    now_decimals_help: "In Now and its details; by default as set for the Current Electricity Price entity",
    now_decimals_entity: "As the price entity",
    scroll_buttons: "Scroll buttons",
    scroll_buttons_help:
      "The left one shows only once the strip has been scrolled away from where it rests; swiping works either way",
    scroll_buttons_both: "Both sides",
    scroll_buttons_forward: "Right only (into the future)",
    scroll_buttons_back: "Left only",
    scroll_buttons_none: "None",
    hide_legend: "Hide legend",
    hide_unit: "Hide price unit",
    content: "Content",
    hide: "Leave out",
    hide_help: "The section itself always stays",
    hide_option: {
      header_average: "Average in the top line (where the chart has no dashed line)",
      day_word: "Today, Tomorrow or Yesterday above each day (in views of more than one day)",
      day_weekday: "Weekday above each day",
      day_shade: "Soft shade off the day line (towards the other day)",
      gauge: "Scale beside the price",
      verdict: "What to make of it (best price, cheap until …)",
      trend: "Trend (icon top right)",
      day_span: "Today's span as a line (wide cards)",
      compare: "Comparison with today (on tomorrow's row)",
      steps: "Price steps on hovering an hour (arrows with percentages)",
      reference: "Dashed line (the day's average)",
      reference_label: "Price on the dashed line",
      now_line_quarter_hour: "Line of now at 15 min",
      now_line_hour: "Line of now at 60 min",
      tomorrow: "Day name where a new day begins (Today, Tomorrow)",
      weekday: "Weekday where the next day begins",
      cheapest: "Cheapest of the day (green chips)",
      periods: "Best and peak price periods (line underneath)",
      badge: "Piggy bank or warning sign while a best or peak price period runs",
      low: "Day's low",
      high: "Day's high",
      pointer: "Pointer at the median",
      range: "Lowest–highest price (numbers)",
      now: "Price now (blue marker)",
      level: "Price level",
      volatility: "Volatility",
    },
    shown: "Days shown",
    shown_both: "Today and tomorrow",
    shown_today: "Today only",
    shown_tomorrow: "Tomorrow only",
    tomorrow_pending: "Until tomorrow's prices are in",
    tomorrow_pending_help:
      "With only tomorrow and no other section, the whole card stays hidden until then (in edit mode it stays visible)",
    tomorrow_pending_placeholder: "Say when they usually come",
    tomorrow_pending_hide: "Hide tomorrow",
    tomorrow_pending_yesterday: "Show yesterday instead",
    appearance: "Light or dark",
    appearance_help:
      "Always light or always dark keeps the card so on any dashboard, in your theme's colors where it has both modes",
    appearance_auto: "As Home Assistant",
    appearance_light: "Light",
    appearance_dark: "Dark",
    style: "Style",
    style_tile: "Tile",
    style_gauge: "Gauge",
    style_clock: "Clock",
    style_help:
      "Tile: one row, like Home Assistant's tile card. Gauge: the price on today's scale. Clock: the coming 12 hours around a dial",
    now_tap_action_help: "Nothing: a tap opens what “Tap opens” says. Set e.g. Navigate to open a dashboard instead",
    tap_opens: "Tap opens",
    tap_opens_details: "Details of now",
    tap_opens_nothing: "Nothing",
    tap_opens_help: "Where no tap action is set below",
    tap_opens_forecast: "Forecast card in a window",
    window_width: "Window width",
    window_width_narrow: "Narrow (like More info)",
    window_width_medium: "Medium",
    window_width_wide: "Wide",
    window_width_full: "Full screen width",
    forecast: "Forecast card",
    styles: "Styles",
    style_switch: "Switchable in the card",
    style_switch_help: "A small switch at the top right changes between the styles picked",
    style_name: "Line {line} · area {fill}",
    all_views: "All views",
    all_views_help: "What every view shows, unless its own panel says otherwise",
    view_inherit_help: "Empty: as for all views",
    style_line: "Line",
    style_fill: "Area",
    style_reference: "Dashed line (each day's average)",
    style_add: "Add style",
    style_remove: "Remove",
    style_up: "Move up",
    style_down: "Move down",
    styles_inherited: "As for all views:",
    styles_customize: "Own styles for this view",
    styles_inherit: "As for all views again",
    style_fill_average_shown: "below/above ⌀ of the view",
    style_fill_average_day: "below/above each day's ⌀",
    style_name_reference: " · ⌀ line",
    style_line_level: "price level",
    style_line_average: "as the area",
    style_line_single: "one color",
    style_fill_level: "price level",
    line_colors: "Line colors",
    fill_colors: "Area colors",
    color_now: "Now (line and label)",
    color_single: "One color",
    color_below: "Below average",
    color_above: "Above average",
    mode_light: "light",
    mode_dark: "dark",
    line_colors_help:
      "Unset colors come from your theme (one color: text color; below: teal; above: warning color) or are the price level's usual ones.",
    fill_colors_help: "Unset colors are the line's.",
    color_reset: "Back to the standard color",
    color_reset_all: "Reset all to standard",
    views: "Views",
    views_help: "Which ones, in this order; the first one opens first",
    resolution: "Resolution",
    resolution_switch: "Switchable, starts at 15 min",
    resolution_switch_hour: "Switchable, starts at 60 min",
    resolution_quarter_hour: "Only 15 min",
    resolution_hour: "Only 60 min",
    chart_average_help: "The 60-minute prices and the dashed line: the arithmetic mean by default",
    chart_hide_help: "The curve itself always stays",
    chart_tomorrow_pending_help:
      "Until then, Tomorrow says when they usually come, isn't offered, or makes way for Yesterday",
  },
  de: {
    chart_button: "Symbol für die Chart-Karte",
    chart_button_help: "Oben rechts; öffnet den Preisverlauf in einem Fenster",
    chart_icon: "Symbol",
    tap_opens_chart: "Chart-Karte im Fenster",
    nested_chart: "Chart-Karte im Fenster",
    nested_forecast: "Forecast-Karte im Fenster",
    nested_help: "Ihre eigenen Einstellungen",
    nested_back: "Zurück",
    day_shade_strength: "Tageslinie: Schatten",
    day_shade_strength_help: "An der Linie, zum anderen Tag hin; ein Wert für helle und dunkle Themes. 0: keiner",
    day_shade_width: "Tageslinie: Schattenbreite",
    day_shade_width_help: "Stunden der Ansicht",
    day_line_width: "Tageslinie: Stärke",
    day_line_width_help: "Standard 1 px; 0: keine",
    day_line_strength: "Tageslinie: Deutlichkeit",
    day_line_strength_help: "Anteil der Textfarbe. Leer: wie die Preislinien",
    grid_line_width: "Preislinien: Stärke",
    grid_line_width_help: "Standard 0,75 px; 0: keine",
    grid_line_strength: "Preislinien: Deutlichkeit",
    grid_line_strength_help:
      "Anteil der Textfarbe, passt so zu hellen und dunklen Themes. Leer: Trennlinienfarbe des Themes",
    header_details: "Niveau und Abweichung in der Kopfzeile",
    header_level: "Preisniveau",
    header_delta: "Abweichung vom Durchschnitt",
    chip_show_always: "Immer",
    chip_show_reading: "Nur beim Ablesen der Preise",
    chip_show_never: "Nie",
    header_level_at: "Nur bei diesen Niveaus",
    header_level_at_help: "Keins angehakt: bei jedem Niveau",
    header_delta_from: "Erst ab einer Abweichung von",
    header_delta_from_help:
      "0: bei jeder Abweichung; sonst nur, wenn der Preis mindestens so weit über oder unter dem Durchschnitt liegt",
    axis_decimals: "Nachkommastellen der Preisachse",
    axis_decimals_auto: "Nach Einheit (€, kr: eine; ct, øre: keine)",
    axis_title_x: "Titel der Zeitachse",
    axis_title_y: "Titel der Preisachse",
    units: "Einheiten",
    unit_place_header: "In der Kopfzeile",
    unit_place_tag: "An der Preismarke über der Kurve",
    unit_place_axis: "An der Preisachse",
    unit_display_full: "Arbeitspreis (z. B. ct/kWh)",
    unit_display_currency: "Nur Währung (z. B. ct)",
    unit_display_none: "Keine",
    unit_display_help:
      "Der Arbeitspreis ist der Preis pro kWh; ein kleiner Kreis zeigt nur die Währung. Screenreader lesen immer die ganze Einheit vor",
    day_colors: "Farben der Tage",
    day_colors_help: "Die Pillen für gestern, heute und morgen über der Kurve (die für jetzt hat die Jetzt-Farbe)",
    header: "Kopfzeile",
    header_chips: "Zeile mit Chips",
    header_dial: "Kreis",
    header_none: "Ausblenden",
    header_help:
      "Ohne sie zeigt die Marke über der Kurve weiter Zeit und Preis; Aktionen laufen dann nur über den eigenen Knopf der Karte",
    style_number: "Darstellung {n}",
    style_label: "Name",
    chart_tap_action_help: "Auf dem Kopf der Karte (Preis und Zeit); ein Tippen auf die Kurve setzt den Cursor",
    default_mark: "Standard",
    view_inherit_option: "Wie bei allen Ansichten ({value})",
    device_id: "Zuhause",
    device_id_help: "Dein Tibber-Zuhause oder eine seiner Zeitreise-Ansichten",
    price_unit: "Preiseinheit",
    unit_auto: "Wie in der Integration eingestellt",
    unit_base: "Hauptwährung (z. B. €/kWh)",
    unit_subunit: "Untereinheit (z. B. ct/kWh)",
    interactions: "Interaktionen",
    average: "Angezeigter Durchschnitt",
    average_help:
      "Die angezeigten Preise und die gestrichelte Linie in Stunden und Tageszeiten; die Zeiger und die Linie bei Heute und Morgen zeigen immer den Median",
    average_mean: "Arithmetischer Mittelwert",
    average_median: "Median",
    hide_details: "Details beim Antippen ausschalten",
    hide_details_help: "Antippen löst dann die Kartenaktion aus, die Hinweise beim Überfahren bleiben",
    action_button: "Kartenaktion über eigenen Knopf",
    action_button_help:
      "Nur dieser Knopf in der Fußzeile löst die Aktionen der Karte aus, Antippen der Karte nicht mehr",
    action_button_text: "Knopftext",
    action_button_text_help: "Leer: passend zur Aktion, z. B. „Mehr Infos“",
    action_button_position: "Position des Knopfs",
    action_button_position_top: "Oben",
    action_button_position_bottom: "Unten",
    tap_action: "Verhalten bei Antippen",
    hold_action: "Verhalten bei Festhalten",
    double_tap_action: "Verhalten bei Doppeltippen",
    entity: "Entität für die Detailansicht",
    entity_help: "Öffnet sich bei der Aktion „Mehr Infos“; leer: der Preissensor des Zuhauses",
    show_title: "Titel anzeigen",
    title: "Titel",
    title_help: "Leer: „Strompreise“",
    layout: "Layout",
    detailed: "Detailliert",
    compact: "Kompakt",
    layout_help: "Detailliert: alle Bereiche untereinander. Kompakt: ein Bereich, umschaltbar",
    show: "Bereiche",
    now_decimals: "Nachkommastellen des aktuellen Preises",
    now_decimals_help:
      "Bei Jetzt und in seinen Details; standardmäßig wie bei der Entität „Aktueller Strompreis“ eingestellt",
    now_decimals_entity: "Wie die Preis-Entität",
    scroll_buttons: "Scroll-Knöpfe",
    scroll_buttons_help:
      "Der linke erscheint erst, wenn der Streifen aus seiner Grundstellung gescrollt wurde; Wischen geht immer",
    scroll_buttons_both: "Beide Seiten",
    scroll_buttons_forward: "Nur rechts (in die Zukunft)",
    scroll_buttons_back: "Nur links",
    scroll_buttons_none: "Keine",
    hide_legend: "Legende ausblenden",
    hide_unit: "Preiseinheit ausblenden",
    content: "Inhalt",
    hide: "Ausblenden",
    hide_help: "Der Bereich selbst bleibt immer",
    hide_option: {
      header_average: "Durchschnitt in der Kopfzeile (wo das Chart keine gestrichelte Linie hat)",
      day_word: "Heute, Morgen oder Gestern über jedem Tag (in Ansichten mit mehr als einem Tag)",
      day_weekday: "Wochentag über jedem Tag",
      day_shade: "Sanfter Schatten an der Tageslinie (zum anderen Tag hin)",
      gauge: "Skala neben dem Preis",
      verdict: "Einordnung (Bestpreis, günstig bis …)",
      trend: "Trend (Symbol oben rechts)",
      day_span: "Spanne des Tages als Linie (breite Karten)",
      compare: "Vergleich mit heute (bei Morgen)",
      steps: "Preissprünge beim Darüberfahren (Pfeile mit Prozent)",
      reference: "Gestrichelte Linie (Tagesdurchschnitt)",
      reference_label: "Preis an der gestrichelten Linie",
      now_line_quarter_hour: "Linie für jetzt bei 15 min",
      now_line_hour: "Linie für jetzt bei 60 min",
      tomorrow: "Tagesname am Tageswechsel (Heute, Morgen)",
      weekday: "Wochentag am Tageswechsel",
      cheapest: "Günstigste des Tages (grüne Chips)",
      periods: "Bestpreis- und Spitzenpreis-Zeiträume (Linie darunter)",
      badge: "Sparschwein bzw. Warndreieck, solange ein Bestpreis- oder Spitzenpreis-Zeitraum läuft",
      low: "Tagestief",
      high: "Tageshoch",
      pointer: "Zeiger auf den Median",
      range: "Niedrigster–höchster Preis (Zahlen)",
      now: "Aktueller Preis (blaue Marke)",
      level: "Preisniveau",
      volatility: "Schwankung",
    },
    shown: "Angezeigte Tage",
    shown_both: "Heute und morgen",
    shown_today: "Nur heute",
    shown_tomorrow: "Nur morgen",
    tomorrow_pending: "Bis die Preise für morgen da sind",
    tomorrow_pending_help:
      "Mit nur morgen und keinem anderen Bereich bleibt die ganze Karte bis dahin ausgeblendet (im Bearbeitungsmodus bleibt sie sichtbar)",
    tomorrow_pending_placeholder: "Anzeigen, wann sie meist kommen",
    tomorrow_pending_hide: "Morgen ausblenden",
    tomorrow_pending_yesterday: "Stattdessen gestern zeigen",
    appearance: "Hell oder dunkel",
    appearance_help:
      "Immer hell oder immer dunkel zeigt die Karte auf jedem Dashboard so, in den Farben deines Themes, wenn es beide Modi hat",
    appearance_auto: "Wie Home Assistant",
    appearance_light: "Hell",
    appearance_dark: "Dunkel",
    style: "Darstellung",
    style_tile: "Kachel",
    style_gauge: "Skala",
    style_clock: "Uhr",
    style_help:
      "Kachel: eine Zeile, wie die Kachel-Karte von Home Assistant. Skala: der Preis auf der Skala des Tages. Uhr: die nächsten 12 Stunden rund um ein Zifferblatt",
    now_tap_action_help:
      "Nichts: Antippen öffnet, was bei „Antippen öffnet“ steht. Wähle z. B. Navigieren, um stattdessen ein Dashboard zu öffnen",
    tap_opens: "Antippen öffnet",
    tap_opens_details: "Details von Jetzt",
    tap_opens_nothing: "Nichts",
    tap_opens_help: "Sofern unten keine Aktion fürs Antippen gesetzt ist",
    tap_opens_forecast: "Forecast-Karte im Fenster",
    window_width: "Fensterbreite",
    window_width_narrow: "Schmal (wie „Mehr Infos“)",
    window_width_medium: "Mittel",
    window_width_wide: "Breit",
    window_width_full: "Ganze Bildschirmbreite",
    forecast: "Forecast-Karte",
    styles: "Darstellungen",
    style_switch: "In der Karte umschaltbar",
    style_switch_help: "Ein kleiner Umschalter oben rechts wechselt zwischen den gewählten Darstellungen",
    style_name: "Linie {line} · Fläche {fill}",
    all_views: "Alle Ansichten",
    all_views_help: "Was jede Ansicht zeigt, solange ihr eigener Bereich nichts anderes sagt",
    view_inherit_help: "Leer: wie bei allen Ansichten",
    style_line: "Linie",
    style_fill: "Fläche",
    style_reference: "Gestrichelte Linie (Durchschnitt jedes Tages)",
    style_add: "Darstellung hinzufügen",
    style_remove: "Entfernen",
    style_up: "Nach oben",
    style_down: "Nach unten",
    styles_inherited: "Wie bei allen Ansichten:",
    styles_customize: "Eigene Darstellungen für diese Ansicht",
    styles_inherit: "Wieder wie bei allen Ansichten",
    style_fill_average_shown: "unter/über ⌀ der Ansicht",
    style_fill_average_day: "unter/über ⌀ jedes Tages",
    style_name_reference: " · ⌀-Linie",
    style_line_level: "Preisniveau",
    style_line_average: "wie die Fläche",
    style_line_single: "eine Farbe",
    style_fill_level: "Preisniveau",
    line_colors: "Linienfarben",
    fill_colors: "Flächenfarben",
    color_now: "Jetzt (Linie und Hinweis)",
    color_single: "Eine Farbe",
    color_below: "Unter dem Durchschnitt",
    color_above: "Über dem Durchschnitt",
    mode_light: "hell",
    mode_dark: "dunkel",
    line_colors_help:
      "Farben ohne eigene Wahl kommen aus deinem Theme (eine Farbe: Textfarbe; darunter: Petrol; darüber: Warnfarbe) oder sind die üblichen des Preisniveaus.",
    fill_colors_help: "Farben ohne eigene Wahl sind die der Linie.",
    color_reset: "Zurück zur Standardfarbe",
    color_reset_all: "Alle auf Standard zurücksetzen",
    views: "Ansichten",
    views_help: "Welche, in dieser Reihenfolge; die erste öffnet zuerst",
    resolution: "Auflösung",
    resolution_switch: "Umschaltbar, startet bei 15 min",
    resolution_switch_hour: "Umschaltbar, startet bei 60 min",
    resolution_quarter_hour: "Nur 15 min",
    resolution_hour: "Nur 60 min",
    chart_average_help: "Die 60-Minuten-Preise und die gestrichelte Linie: standardmäßig das arithmetische Mittel",
    chart_hide_help: "Die Kurve selbst bleibt immer",
    chart_tomorrow_pending_help:
      "Bis dahin sagt „Morgen“, wann sie meist kommen, fehlt ganz oder macht Platz für „Gestern“",
  },
  nb: {
    chart_button: "Symbol for diagramkortet",
    chart_button_help: "Øverst til høyre; åpner prisforløpet i et vindu",
    chart_icon: "Symbol",
    tap_opens_chart: "Diagramkort i et vindu",
    nested_chart: "Diagramkort i et vindu",
    nested_forecast: "Prognosekort i et vindu",
    nested_help: "Egne innstillinger",
    nested_back: "Tilbake",
    day_shade_strength: "Daglinje: skygge",
    day_shade_strength_help: "Ved linjen, mot den andre dagen; én verdi for lyse og mørke temaer. 0: ingen",
    day_shade_width: "Daglinje: skyggebredde",
    day_shade_width_help: "Timer i visningen",
    day_line_width: "Daglinje: tykkelse",
    day_line_width_help: "Standard 1 px; 0: ingen",
    day_line_strength: "Daglinje: tydelighet",
    day_line_strength_help: "Andel av tekstfargen. Tomt: som prislinjene",
    grid_line_width: "Prislinjer: tykkelse",
    grid_line_width_help: "Standard 0,75 px; 0: ingen",
    grid_line_strength: "Prislinjer: tydelighet",
    grid_line_strength_help:
      "Andel av tekstfargen, passer slik til lyse og mørke temaer. Tomt: temaets skillelinjefarge",
    header_details: "Nivå og avvik i topplinjen",
    header_level: "Prisnivå",
    header_delta: "Avvik fra gjennomsnittet",
    chip_show_always: "Alltid",
    chip_show_reading: "Bare når du leser av prisene",
    chip_show_never: "Aldri",
    header_level_at: "Bare ved disse nivåene",
    header_level_at_help: "Ingen krysset av: ved alle nivåer",
    header_delta_from: "Først fra et avvik på",
    header_delta_from_help:
      "0: ved ethvert avvik; ellers bare når prisen ligger minst så langt over eller under gjennomsnittet",
    axis_decimals: "Desimaler på prisaksen",
    axis_decimals_auto: "Etter enhet (kr: én; øre: ingen)",
    axis_title_x: "Tittel på tidsaksen",
    axis_title_y: "Tittel på prisaksen",
    units: "Enheter",
    unit_place_header: "I toppraden",
    unit_place_tag: "På merket over kurven",
    unit_place_axis: "Ved prisaksen",
    unit_display_full: "Energipris (f.eks. øre/kWh)",
    unit_display_currency: "Bare valuta (f.eks. øre)",
    unit_display_none: "Ingen",
    unit_display_help:
      "Energiprisen er prisen per kWh; en liten ring viser bare valutaen. Skjermlesere leser alltid hele enheten",
    day_colors: "Dagfarger",
    day_colors_help: "Pillene for i går, i dag og i morgen over kurven (den for nå har nåfargen)",
    header: "Topprad",
    header_chips: "Rad med brikker",
    header_dial: "Ring",
    header_none: "Skjul",
    header_help:
      "Uten den viser merket over kurven fortsatt tid og pris; handlinger kjøres da bare fra kortets egen knapp",
    style_number: "Stil {n}",
    style_label: "Navn",
    chart_tap_action_help: "På toppen av kortet (pris og tid); et trykk på kurven flytter markøren",
    default_mark: "standard",
    view_inherit_option: "Som for alle visninger ({value})",
    device_id: "Hjem",
    device_id_help: "Tibber-hjemmet ditt, eller en av tidsreisevisningene",
    price_unit: "Prisenhet",
    unit_auto: "Som innstilt i integrasjonen",
    unit_base: "Hovedvaluta (f.eks. kr/kWh)",
    unit_subunit: "Underenhet (f.eks. øre/kWh)",
    interactions: "Interaksjoner",
    average: "Gjennomsnitt som vises",
    average_help:
      "Prisene som vises og den stiplede linjen i timer og tider på døgnet; pekerne og linjen ved i dag og i morgen viser alltid medianen",
    average_mean: "Aritmetisk gjennomsnitt",
    average_median: "Median",
    hide_details: "Slå av detaljer ved trykk",
    hide_details_help: "Et trykk kjører da kortets handling; hint ved peking blir",
    action_button: "Korthandling via egen knapp",
    action_button_help: "Bare denne knappen nederst utfører kortets handlinger, trykk på kortet gjør det ikke lenger",
    action_button_text: "Knappetekst",
    action_button_text_help: "Tom: passer til handlingen, f.eks. «Mer info»",
    action_button_position: "Knappens plassering",
    action_button_position_top: "Øverst",
    action_button_position_bottom: "Nederst",
    tap_action: "Atferd ved trykk",
    hold_action: "Atferd ved hold",
    double_tap_action: "Atferd ved dobbelttrykk",
    entity: "Entitet for Mer info",
    entity_help: "Åpnes av handlingen «Mer info»; tom: hjemmets prissensor",
    show_title: "Vis tittel",
    title: "Tittel",
    title_help: "Tom: «Strømpriser»",
    layout: "Visning",
    detailed: "Detaljert",
    compact: "Kompakt",
    layout_help: "Detaljert: alle deler under hverandre. Kompakt: én del om gangen, med bryter",
    show: "Deler",
    now_decimals: "Desimaler for nåværende pris",
    now_decimals_help: "I Nå og detaljene; som standard som innstilt for enheten «Nåværende strømpris»",
    now_decimals_entity: "Som prisenheten",
    scroll_buttons: "Rulleknapper",
    scroll_buttons_help:
      "Den venstre vises først når stripen er rullet bort fra utgangsstillingen; sveiping fungerer uansett",
    scroll_buttons_both: "Begge sider",
    scroll_buttons_forward: "Bare høyre (fremover i tid)",
    scroll_buttons_back: "Bare venstre",
    scroll_buttons_none: "Ingen",
    hide_legend: "Skjul tegnforklaring",
    hide_unit: "Skjul prisenhet",
    content: "Innhold",
    hide: "Skjul",
    hide_help: "Selve delen blir alltid stående",
    hide_option: {
      header_average: "Snitt i toppraden (der diagrammet ikke har stiplet linje)",
      day_word: "I dag, I morgen eller I går over hver dag (i visninger med mer enn én dag)",
      day_weekday: "Ukedag over hver dag",
      day_shade: "Myk skygge ved daglinjen (mot den andre dagen)",
      gauge: "Skala ved siden av prisen",
      verdict: "Vurdering (beste pris, billig til …)",
      trend: "Trend (symbol øverst til høyre)",
      day_span: "Dagens spenn som linje (brede kort)",
      compare: "Sammenligning med i dag (ved i morgen)",
      steps: "Prishopp når du holder musen over en time (piler med prosent)",
      reference: "Stiplet linje (dagens gjennomsnitt)",
      reference_label: "Pris på den stiplede linjen",
      now_line_quarter_hour: "Linjen for nå ved 15 min",
      now_line_hour: "Linjen for nå ved 60 min",
      tomorrow: "Dagsnavn ved dagsskiftet (I dag, I morgen)",
      weekday: "Ukedag ved dagsskiftet",
      cheapest: "Dagens billigste (grønne merker)",
      periods: "Perioder med beste pris og topppris (linje under)",
      badge: "Sparegris eller varseltrekant mens en periode med beste pris eller topppris pågår",
      low: "Dagens laveste",
      high: "Dagens høyeste",
      pointer: "Peker på medianen",
      range: "Laveste–høyeste pris (tall)",
      now: "Pris nå (blått merke)",
      level: "Prisnivå",
      volatility: "Svingning",
    },
    shown: "Dager som vises",
    shown_both: "I dag og i morgen",
    shown_today: "Bare i dag",
    shown_tomorrow: "Bare i morgen",
    tomorrow_pending: "Til prisene for i morgen er klare",
    tomorrow_pending_help:
      "Med bare i morgen og ingen andre deler er hele kortet skjult til da (i redigeringsmodus forblir det synlig)",
    tomorrow_pending_placeholder: "Vis når de vanligvis kommer",
    tomorrow_pending_hide: "Skjul i morgen",
    tomorrow_pending_yesterday: "Vis i går i stedet",
    appearance: "Lys eller mørk",
    appearance_help:
      "Alltid lys eller alltid mørk viser kortet slik på alle dashbord, i temaets farger når det har begge moduser",
    appearance_auto: "Som Home Assistant",
    appearance_light: "Lys",
    appearance_dark: "Mørk",
    style: "Visning",
    style_tile: "Flis",
    style_gauge: "Måler",
    style_clock: "Klokke",
    style_help:
      "Flis: én rad, som flis-kortet i Home Assistant. Måler: prisen på dagens skala. Klokke: de neste 12 timene rundt en urskive",
    now_tap_action_help:
      "Ingenting: et trykk åpner det som står under «Trykk åpner». Velg f.eks. Naviger for å åpne et dashbord i stedet",
    tap_opens: "Trykk åpner",
    tap_opens_details: "Detaljer for nå",
    tap_opens_nothing: "Ingenting",
    tap_opens_help: "Så lenge ingen trykkhandling er satt nedenfor",
    tap_opens_forecast: "Prognosekort i et vindu",
    window_width: "Vindusbredde",
    window_width_narrow: "Smal (som «Mer info»)",
    window_width_medium: "Middels",
    window_width_wide: "Bred",
    window_width_full: "Hele skjermbredden",
    forecast: "Prognosekort",
    styles: "Stiler",
    style_switch: "Kan byttes i kortet",
    style_switch_help: "En liten bryter øverst til høyre bytter mellom de valgte stilene",
    style_name: "Linje {line} · flate {fill}",
    all_views: "Alle visninger",
    all_views_help: "Det hver visning viser, så lenge dens eget område ikke sier noe annet",
    view_inherit_help: "Tom: som for alle visninger",
    style_line: "Linje",
    style_fill: "Flate",
    style_reference: "Stiplet linje (hver dags snitt)",
    style_add: "Legg til stil",
    style_remove: "Fjern",
    style_up: "Flytt opp",
    style_down: "Flytt ned",
    styles_inherited: "Som for alle visninger:",
    styles_customize: "Egne stiler for denne visningen",
    styles_inherit: "Som for alle visninger igjen",
    style_fill_average_shown: "under/over ⌀ i visningen",
    style_fill_average_day: "under/over hver dags ⌀",
    style_name_reference: " · ⌀-linje",
    style_line_level: "prisnivå",
    style_line_average: "som flaten",
    style_line_single: "én farge",
    style_fill_level: "prisnivå",
    line_colors: "Linjefarger",
    fill_colors: "Flatefarger",
    color_now: "Nå (linje og merke)",
    color_single: "Én farge",
    color_below: "Under snittet",
    color_above: "Over snittet",
    mode_light: "lys",
    mode_dark: "mørk",
    line_colors_help:
      "Farger uten eget valg kommer fra temaet ditt (én farge: tekstfarge; under: blågrønn; over: varselfarge) eller er prisnivåets vanlige.",
    fill_colors_help: "Farger uten eget valg er linjens.",
    color_reset: "Tilbake til standardfargen",
    color_reset_all: "Tilbakestill alle til standard",
    views: "Visninger",
    views_help: "Hvilke, i denne rekkefølgen; den første åpnes først",
    resolution: "Oppløsning",
    resolution_switch: "Kan byttes, starter på 15 min",
    resolution_switch_hour: "Kan byttes, starter på 60 min",
    resolution_quarter_hour: "Bare 15 min",
    resolution_hour: "Bare 60 min",
    chart_average_help: "60-minuttersprisene og den stiplede linjen: som standard det aritmetiske gjennomsnittet",
    chart_hide_help: "Selve kurven blir alltid",
    chart_tomorrow_pending_help:
      "Til da sier «I morgen» når de vanligvis kommer, vises ikke eller gir plass til «I går»",
  },
  nl: {
    chart_button: "Pictogram voor de grafiekkaart",
    chart_button_help: "Rechtsboven; opent het prijsverloop in een venster",
    chart_icon: "Pictogram",
    tap_opens_chart: "Grafiekkaart in een venster",
    nested_chart: "Grafiekkaart in een venster",
    nested_forecast: "Prognosekaart in een venster",
    nested_help: "Eigen instellingen",
    nested_back: "Terug",
    day_shade_strength: "Daglijn: schaduw",
    day_shade_strength_help: "Bij de lijn, naar de andere dag toe; één waarde voor lichte en donkere thema's. 0: geen",
    day_shade_width: "Daglijn: schaduwbreedte",
    day_shade_width_help: "Uren van de weergave",
    day_line_width: "Daglijn: dikte",
    day_line_width_help: "Standaard 1 px; 0: geen",
    day_line_strength: "Daglijn: sterkte",
    day_line_strength_help: "Aandeel van de tekstkleur. Leeg: als de prijslijnen",
    grid_line_width: "Prijslijnen: dikte",
    grid_line_width_help: "Standaard 0,75 px; 0: geen",
    grid_line_strength: "Prijslijnen: sterkte",
    grid_line_strength_help:
      "Aandeel van de tekstkleur, past zo bij lichte en donkere thema's. Leeg: de scheidingslijnkleur van het thema",
    header_details: "Niveau en afwijking in de bovenste regel",
    header_level: "Prijsniveau",
    header_delta: "Afwijking van het gemiddelde",
    chip_show_always: "Altijd",
    chip_show_reading: "Alleen bij het aflezen van prijzen",
    chip_show_never: "Nooit",
    header_level_at: "Alleen bij deze niveaus",
    header_level_at_help: "Niets aangevinkt: bij elk niveau",
    header_delta_from: "Pas vanaf een afwijking van",
    header_delta_from_help:
      "0: bij elke afwijking; anders alleen als de prijs minstens zo ver boven of onder het gemiddelde ligt",
    axis_decimals: "Decimalen van de prijsas",
    axis_decimals_auto: "Naar eenheid (€: één; ct: geen)",
    axis_title_x: "Titel van de tijdas",
    axis_title_y: "Titel van de prijsas",
    units: "Eenheden",
    unit_place_header: "In de bovenste regel",
    unit_place_tag: "Op het label boven de curve",
    unit_place_axis: "Bij de prijsas",
    unit_display_full: "Prijs per kWh (bijv. ct/kWh)",
    unit_display_currency: "Alleen valuta (bijv. ct)",
    unit_display_none: "Geen",
    unit_display_help:
      "De prijs per kWh; een kleine ring toont alleen de valuta. Schermlezers lezen altijd de hele eenheid voor",
    day_colors: "Kleuren van de dagen",
    day_colors_help: "De pillen voor gisteren, vandaag en morgen boven de curve (die van nu heeft de kleur van nu)",
    header: "Bovenste regel",
    header_chips: "Regel met chips",
    header_dial: "Ring",
    header_none: "Verbergen",
    header_help:
      "Zonder toont het label boven de curve nog tijd en prijs; acties lopen dan alleen via de eigen knop van de kaart",
    style_number: "Stijl {n}",
    style_label: "Naam",
    chart_tap_action_help: "Op de bovenkant van de kaart (prijs en tijd); een tik op de curve verplaatst de cursor",
    default_mark: "standaard",
    view_inherit_option: "Zoals bij alle weergaven ({value})",
    device_id: "Woning",
    device_id_help: "Je Tibber-woning, of een van de tijdreisweergaven",
    price_unit: "Prijseenheid",
    unit_auto: "Zoals ingesteld in de integratie",
    unit_base: "Hoofdvaluta (bijv. €/kWh)",
    unit_subunit: "Subeenheid (bijv. ct/kWh)",
    interactions: "Interacties",
    average: "Getoond gemiddelde",
    average_help:
      "De getoonde prijzen en de stippellijn in uren en dagdelen; de wijzers en de lijn bij vandaag en morgen tonen altijd de mediaan",
    average_mean: "Rekenkundig gemiddelde",
    average_median: "Median",
    hide_details: "Details bij tikken uitschakelen",
    hide_details_help: "Tikken voert dan de actie van de kaart uit; hints bij aanwijzen blijven",
    action_button: "Kaartactie via eigen knop",
    action_button_help: "Alleen deze knop onderaan voert de acties van de kaart uit, tikken op de kaart niet meer",
    action_button_text: "Knoptekst",
    action_button_text_help: "Leeg: passend bij de actie, bijv. „Meer info”",
    action_button_position: "Positie van de knop",
    action_button_position_top: "Boven",
    action_button_position_bottom: "Onder",
    tap_action: "Tik gedrag",
    hold_action: "Gedrag vasthouden",
    double_tap_action: "Gedrag bij dubbeltikken",
    entity: "Entiteit voor Meer info",
    entity_help: "Geopend door de actie „Meer info”; leeg: de prijssensor van de woning",
    show_title: "Titel tonen",
    title: "Titel",
    title_help: "Leeg: „Stroomprijzen”",
    layout: "Weergave",
    detailed: "Gedetailleerd",
    compact: "Compact",
    layout_help: "Gedetailleerd: alle onderdelen onder elkaar. Compact: één onderdeel tegelijk, met schakelaar",
    show: "Onderdelen",
    now_decimals: "Decimalen van de huidige prijs",
    now_decimals_help:
      "Bij Nu en in de details; standaard zoals ingesteld voor de entiteit „Huidige Elektriciteitsprijs”",
    now_decimals_entity: "Zoals de prijsentiteit",
    scroll_buttons: "Scrollknoppen",
    scroll_buttons_help: "De linker verschijnt pas als de strook uit haar beginstand is gescrold; vegen werkt altijd",
    scroll_buttons_both: "Beide kanten",
    scroll_buttons_forward: "Alleen rechts (de toekomst in)",
    scroll_buttons_back: "Alleen links",
    scroll_buttons_none: "Geen",
    hide_legend: "Legenda verbergen",
    hide_unit: "Prijseenheid verbergen",
    content: "Inhoud",
    hide: "Verbergen",
    hide_help: "Het onderdeel zelf blijft altijd",
    hide_option: {
      header_average: "Gemiddelde in de bovenste regel (waar de grafiek geen stippellijn heeft)",
      day_word: "Vandaag, Morgen of Gisteren boven elke dag (in weergaven met meer dan één dag)",
      day_weekday: "Weekdag boven elke dag",
      day_shade: "Zachte schaduw bij de daglijn (naar de andere dag toe)",
      gauge: "Schaal naast de prijs",
      verdict: "Duiding (beste prijs, goedkoop tot …)",
      trend: "Trend (pictogram rechtsboven)",
      day_span: "Bereik van de dag als lijn (brede kaarten)",
      compare: "Vergelijking met vandaag (bij morgen)",
      steps: "Prijssprongen bij aanwijzen van een uur (pijlen met procenten)",
      reference: "Stippellijn (daggemiddelde)",
      reference_label: "Prijs bij de stippellijn",
      now_line_quarter_hour: "Lijn van nu bij 15 min",
      now_line_hour: "Lijn van nu bij 60 min",
      tomorrow: "Dagnaam bij de dagwissel (Vandaag, Morgen)",
      weekday: "Weekdag bij de dagwissel",
      cheapest: "Goedkoopste van de dag (groene labels)",
      periods: "Periodes met beste prijs en piekprijs (lijn eronder)",
      badge: "Spaarvarken of waarschuwingsdriehoek zolang een periode met beste prijs of piekprijs loopt",
      low: "Laagste van de dag",
      high: "Hoogste van de dag",
      pointer: "Wijzer op de mediaan",
      range: "Laagste–hoogste prijs (getallen)",
      now: "Prijs nu (blauwe markering)",
      level: "Prijsniveau",
      volatility: "Schommeling",
    },
    shown: "Getoonde dagen",
    shown_both: "Vandaag en morgen",
    shown_today: "Alleen vandaag",
    shown_tomorrow: "Alleen morgen",
    tomorrow_pending: "Tot de prijzen voor morgen er zijn",
    tomorrow_pending_help:
      "Met alleen morgen en geen ander onderdeel blijft de hele kaart tot dan verborgen (in de bewerkmodus blijft ze zichtbaar)",
    tomorrow_pending_placeholder: "Tonen wanneer ze meestal komen",
    tomorrow_pending_hide: "Morgen verbergen",
    tomorrow_pending_yesterday: "Gisteren in plaats daarvan tonen",
    appearance: "Licht of donker",
    appearance_help:
      "Altijd licht of altijd donker toont de kaart zo op elk dashboard, in de kleuren van je thema als het beide modi heeft",
    appearance_auto: "Zoals Home Assistant",
    appearance_light: "Licht",
    appearance_dark: "Donker",
    style: "Weergave",
    style_tile: "Tegel",
    style_gauge: "Meter",
    style_clock: "Klok",
    style_help:
      "Tegel: één rij, zoals de tegelkaart van Home Assistant. Meter: de prijs op de schaal van vandaag. Klok: de komende 12 uur rond een wijzerplaat",
    now_tap_action_help:
      "Niets: tikken opent wat bij „Tikken opent” staat. Kies bijv. Navigeren om in plaats daarvan een dashboard te openen",
    tap_opens: "Tikken opent",
    tap_opens_details: "Details van nu",
    tap_opens_nothing: "Niets",
    tap_opens_help: "Zolang hieronder geen tikactie is ingesteld",
    tap_opens_forecast: "Prognosekaart in een venster",
    window_width: "Vensterbreedte",
    window_width_narrow: "Smal (zoals „Meer info”)",
    window_width_medium: "Middel",
    window_width_wide: "Breed",
    window_width_full: "Volledige schermbreedte",
    forecast: "Prognosekaart",
    styles: "Stijlen",
    style_switch: "Wisselbaar in de kaart",
    style_switch_help: "Een kleine schakelaar rechtsboven wisselt tussen de gekozen stijlen",
    style_name: "Lijn {line} · vlak {fill}",
    all_views: "Alle weergaven",
    all_views_help: "Wat elke weergave toont, zolang haar eigen gedeelte niets anders zegt",
    view_inherit_help: "Leeg: zoals bij alle weergaven",
    style_line: "Lijn",
    style_fill: "Vlak",
    style_reference: "Stippellijn (gemiddelde van elke dag)",
    style_add: "Stijl toevoegen",
    style_remove: "Verwijderen",
    style_up: "Omhoog",
    style_down: "Omlaag",
    styles_inherited: "Zoals bij alle weergaven:",
    styles_customize: "Eigen stijlen voor deze weergave",
    styles_inherit: "Weer zoals bij alle weergaven",
    style_fill_average_shown: "onder/boven ⌀ van de weergave",
    style_fill_average_day: "onder/boven ⌀ van elke dag",
    style_name_reference: " · ⌀-lijn",
    style_line_level: "prijsniveau",
    style_line_average: "zoals het vlak",
    style_line_single: "één kleur",
    style_fill_level: "prijsniveau",
    line_colors: "Lijnkleuren",
    fill_colors: "Vlakkleuren",
    color_now: "Nu (lijn en label)",
    color_single: "Eén kleur",
    color_below: "Onder het gemiddelde",
    color_above: "Boven het gemiddelde",
    mode_light: "licht",
    mode_dark: "donker",
    line_colors_help:
      "Kleuren zonder eigen keuze komen uit je thema (één kleur: tekstkleur; onder: blauwgroen; boven: waarschuwingskleur) of zijn de gebruikelijke van het prijsniveau.",
    fill_colors_help: "Kleuren zonder eigen keuze zijn die van de lijn.",
    color_reset: "Terug naar de standaardkleur",
    color_reset_all: "Alles terugzetten naar standaard",
    views: "Weergaven",
    views_help: "Welke, in deze volgorde; de eerste opent eerst",
    resolution: "Resolutie",
    resolution_switch: "Wisselbaar, begint bij 15 min",
    resolution_switch_hour: "Wisselbaar, begint bij 60 min",
    resolution_quarter_hour: "Alleen 15 min",
    resolution_hour: "Alleen 60 min",
    chart_average_help: "De prijzen per 60 minuten en de stippellijn: standaard het rekenkundig gemiddelde",
    chart_hide_help: "De curve zelf blijft altijd",
    chart_tomorrow_pending_help:
      "Tot dan zegt „Morgen” wanneer ze meestal komen, ontbreekt of maakt plaats voor „Gisteren”",
  },
  sv: {
    chart_button: "Symbol för diagramkortet",
    chart_button_help: "Uppe till höger; öppnar prisförloppet i ett fönster",
    chart_icon: "Symbol",
    tap_opens_chart: "Diagramkort i ett fönster",
    nested_chart: "Diagramkort i ett fönster",
    nested_forecast: "Prognoskort i ett fönster",
    nested_help: "Egna inställningar",
    nested_back: "Tillbaka",
    day_shade_strength: "Daglinje: skugga",
    day_shade_strength_help: "Vid linjen, mot den andra dagen; ett värde för ljusa och mörka teman. 0: ingen",
    day_shade_width: "Daglinje: skuggbredd",
    day_shade_width_help: "Timmar i vyn",
    day_line_width: "Daglinje: tjocklek",
    day_line_width_help: "Standard 1 px; 0: ingen",
    day_line_strength: "Daglinje: tydlighet",
    day_line_strength_help: "Andel av textfärgen. Tomt: som prislinjerna",
    grid_line_width: "Prislinjer: tjocklek",
    grid_line_width_help: "Standard 0,75 px; 0: inga",
    grid_line_strength: "Prislinjer: tydlighet",
    grid_line_strength_help: "Andel av textfärgen, passar så till ljusa och mörka teman. Tomt: temats avdelarfärg",
    header_details: "Nivå och avvikelse i översta raden",
    header_level: "Prisnivå",
    header_delta: "Avvikelse från genomsnittet",
    chip_show_always: "Alltid",
    chip_show_reading: "Bara när du läser av priserna",
    chip_show_never: "Aldrig",
    header_level_at: "Bara vid dessa nivåer",
    header_level_at_help: "Inget markerat: vid alla nivåer",
    header_delta_from: "Först från en avvikelse på",
    header_delta_from_help:
      "0: vid varje avvikelse; annars bara när priset ligger minst så långt över eller under genomsnittet",
    axis_decimals: "Decimaler på prisaxeln",
    axis_decimals_auto: "Efter enhet (kr: en; öre: inga)",
    axis_title_x: "Titel på tidsaxeln",
    axis_title_y: "Titel på prisaxeln",
    units: "Enheter",
    unit_place_header: "I översta raden",
    unit_place_tag: "På etiketten ovanför kurvan",
    unit_place_axis: "Vid prisaxeln",
    unit_display_full: "Energipris (t.ex. öre/kWh)",
    unit_display_currency: "Endast valuta (t.ex. öre)",
    unit_display_none: "Ingen",
    unit_display_help:
      "Energipriset är priset per kWh; en liten ring visar bara valutan. Skärmläsare läser alltid hela enheten",
    day_colors: "Dagarnas färger",
    day_colors_help: "Pillren för i går, i dag och i morgon ovanför kurvan (den för nu har nu-färgen)",
    header: "Översta raden",
    header_chips: "Rad med etiketter",
    header_dial: "Ring",
    header_none: "Dölj",
    header_help:
      "Utan den visar etiketten ovanför kurvan fortfarande tid och pris; åtgärder körs då bara från kortets egen knapp",
    style_number: "Stil {n}",
    style_label: "Namn",
    chart_tap_action_help: "På kortets överdel (pris och tid); ett tryck på kurvan flyttar markören",
    default_mark: "standard",
    view_inherit_option: "Som för alla vyer ({value})",
    device_id: "Hem",
    device_id_help: "Ditt Tibber-hem, eller en av dess tidsresevyer",
    price_unit: "Prisenhet",
    unit_auto: "Som inställt i integrationen",
    unit_base: "Huvudvaluta (t.ex. kr/kWh)",
    unit_subunit: "Underenhet (t.ex. öre/kWh)",
    interactions: "Interaktioner",
    average: "Visat medelvärde",
    average_help:
      "Priserna som visas och den streckade linjen i timmar och tider på dygnet; pekarna och linjen vid idag och imorgon visar alltid medianen",
    average_mean: "Aritmetiskt medelvärde",
    average_median: "Median",
    hide_details: "Stäng av detaljer vid tryck",
    hide_details_help: "Ett tryck kör då kortets åtgärd; tips vid hovring finns kvar",
    action_button: "Korthandling via egen knapp",
    action_button_help: "Bara den här knappen längst ned utför kortets åtgärder, tryck på kortet gör det inte längre",
    action_button_text: "Knapptext",
    action_button_text_help: "Tomt: passar till åtgärden, t.ex. ”Mer info”",
    action_button_position: "Knappens placering",
    action_button_position_top: "Överst",
    action_button_position_bottom: "Nederst",
    tap_action: "Beteende vid tryck",
    hold_action: "Beteende vid långtryck",
    double_tap_action: "Beteende vid dubbeltryck",
    entity: "Entitet för Mer info",
    entity_help: "Öppnas av åtgärden ”Mer info”; tom: hemmets prissensor",
    show_title: "Visa titel",
    title: "Titel",
    title_help: "Tom: ”Elpriser”",
    layout: "Visning",
    detailed: "Detaljerad",
    compact: "Kompakt",
    layout_help: "Detaljerad: alla delar under varandra. Kompakt: en del i taget, med växel",
    show: "Delar",
    now_decimals: "Decimaler för aktuellt pris",
    now_decimals_help: "I Nu och detaljerna; som standard som inställt för entiteten ”Aktuellt elpris”",
    now_decimals_entity: "Som prisentiteten",
    scroll_buttons: "Rullningsknappar",
    scroll_buttons_help:
      "Den vänstra visas först när remsan har rullats bort från sitt utgångsläge; svepa fungerar ändå",
    scroll_buttons_both: "Båda sidor",
    scroll_buttons_forward: "Bara höger (framåt i tiden)",
    scroll_buttons_back: "Bara vänster",
    scroll_buttons_none: "Inga",
    hide_legend: "Dölj teckenförklaring",
    hide_unit: "Dölj prisenhet",
    content: "Innehåll",
    hide: "Dölj",
    hide_help: "Själva avsnittet finns alltid kvar",
    hide_option: {
      header_average: "Snitt i översta raden (där diagrammet saknar streckad linje)",
      day_word: "I dag, I morgon eller I går över varje dag (i vyer med mer än en dag)",
      day_weekday: "Veckodag över varje dag",
      day_shade: "Mjuk skugga vid daglinjen (mot den andra dagen)",
      gauge: "Skala bredvid priset",
      verdict: "Bedömning (bästa pris, billigt till …)",
      trend: "Trend (ikon uppe till höger)",
      day_span: "Dagens spann som linje (breda kort)",
      compare: "Jämförelse med i dag (vid i morgon)",
      steps: "Prissteg när du håller muspekaren över en timme (pilar med procent)",
      reference: "Streckad linje (dagens medelvärde)",
      reference_label: "Pris vid den streckade linjen",
      now_line_quarter_hour: "Linjen för nu vid 15 min",
      now_line_hour: "Linjen för nu vid 60 min",
      tomorrow: "Dagsnamn vid dagsskiftet (Idag, Imorgon)",
      weekday: "Veckodag vid dagsskiftet",
      cheapest: "Dagens billigaste (gröna märken)",
      periods: "Perioder med bästa pris och topppris (linje under)",
      badge: "Spargris eller varningstriangel medan en period med bästa pris eller topppris pågår",
      low: "Dagens lägsta",
      high: "Dagens högsta",
      pointer: "Visare på medianen",
      range: "Lägsta–högsta pris (siffror)",
      now: "Pris nu (blå markering)",
      level: "Prisnivå",
      volatility: "Svängning",
    },
    shown: "Dagar som visas",
    shown_both: "I dag och i morgon",
    shown_today: "Bara i dag",
    shown_tomorrow: "Bara i morgon",
    tomorrow_pending: "Tills priserna för i morgon finns",
    tomorrow_pending_help:
      "Med bara i morgon och inget annat avsnitt är hela kortet dolt tills dess (i redigeringsläget syns det)",
    tomorrow_pending_placeholder: "Visa när de brukar komma",
    tomorrow_pending_hide: "Dölj i morgon",
    tomorrow_pending_yesterday: "Visa i går i stället",
    appearance: "Ljust eller mörkt",
    appearance_help:
      "Alltid ljust eller alltid mörkt visar kortet så på alla instrumentpaneler, i temats färger när det har båda lägena",
    appearance_auto: "Som Home Assistant",
    appearance_light: "Ljust",
    appearance_dark: "Mörkt",
    style: "Visning",
    style_tile: "Ruta",
    style_gauge: "Mätare",
    style_clock: "Klocka",
    style_help:
      "Ruta: en rad, som rutkortet i Home Assistant. Mätare: priset på dagens skala. Klocka: de kommande 12 timmarna runt en urtavla",
    now_tap_action_help:
      "Inget: ett tryck öppnar det som står under ”Tryck öppnar”. Välj t.ex. Navigera för att öppna en instrumentpanel i stället",
    tap_opens: "Tryck öppnar",
    tap_opens_details: "Detaljer för nu",
    tap_opens_nothing: "Ingenting",
    tap_opens_help: "Så länge ingen tryckåtgärd är satt nedan",
    tap_opens_forecast: "Prognoskort i ett fönster",
    window_width: "Fönsterbredd",
    window_width_narrow: "Smal (som ”Mer info”)",
    window_width_medium: "Mellan",
    window_width_wide: "Bred",
    window_width_full: "Hela skärmbredden",
    forecast: "Prognoskort",
    styles: "Stilar",
    style_switch: "Växlingsbar i kortet",
    style_switch_help: "En liten växel uppe till höger byter mellan de valda stilarna",
    style_name: "Linje {line} · yta {fill}",
    all_views: "Alla vyer",
    all_views_help: "Det varje vy visar, så länge dess eget avsnitt inte säger något annat",
    view_inherit_help: "Tom: som för alla vyer",
    style_line: "Linje",
    style_fill: "Yta",
    style_reference: "Streckad linje (varje dags snitt)",
    style_add: "Lägg till stil",
    style_remove: "Ta bort",
    style_up: "Flytta upp",
    style_down: "Flytta ned",
    styles_inherited: "Som för alla vyer:",
    styles_customize: "Egna stilar för den här vyn",
    styles_inherit: "Som för alla vyer igen",
    style_fill_average_shown: "under/över vyns ⌀",
    style_fill_average_day: "under/över varje dags ⌀",
    style_name_reference: " · ⌀-linje",
    style_line_level: "prisnivå",
    style_line_average: "som ytan",
    style_line_single: "en färg",
    style_fill_level: "prisnivå",
    line_colors: "Linjefärger",
    fill_colors: "Ytfärger",
    color_now: "Nu (linje och etikett)",
    color_single: "En färg",
    color_below: "Under snittet",
    color_above: "Över snittet",
    mode_light: "ljus",
    mode_dark: "mörk",
    line_colors_help:
      "Färger utan eget val kommer från ditt tema (en färg: textfärg; under: blågrön; över: varningsfärg) eller är prisnivåns vanliga.",
    fill_colors_help: "Färger utan eget val är linjens.",
    color_reset: "Tillbaka till standardfärgen",
    color_reset_all: "Återställ alla till standard",
    views: "Vyer",
    views_help: "Vilka, i den här ordningen; den första öppnas först",
    resolution: "Upplösning",
    resolution_switch: "Växlingsbar, börjar på 15 min",
    resolution_switch_hour: "Växlingsbar, börjar på 60 min",
    resolution_quarter_hour: "Endast 15 min",
    resolution_hour: "Endast 60 min",
    chart_average_help: "60-minuterspriserna och den streckade linjen: som standard det aritmetiska medelvärdet",
    chart_hide_help: "Själva kurvan finns alltid kvar",
    chart_tomorrow_pending_help:
      "Tills dess säger ”I morgon” när de brukar komma, visas inte eller ger plats åt ”I går”",
  },
};

// Number format from the user's profile (decimal comma or point), like HA's own cards
function numberLocale(hass) {
  const format = hass.locale && hass.locale.number_format;
  const locales = { comma_decimal: "en-US", decimal_comma: "de-DE", space_comma: "fr-FR", system: undefined };
  return format in locales ? locales[format] : hass.language;
}

// The user's profile decides: the server's time zone or the browser's
function timeZone(hass) {
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
function firstHomeDevice(hass) {
  const entry = Object.values(hass.entities || {}).find(
    (e) => e.platform === "tibber_prices" && e.translation_key === HOME_ENTITIES.price && e.device_id
  );
  return entry ? entry.device_id : "";
}

function homeEntities(hass, config) {
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
const SECTIONS = ["now", "hours", "day_parts", "days"];

// Which days the day rows show, and what tomorrow's row does until its prices are published:
// say when they usually come, or stay away (a card left with nothing to show hides itself)
const DAYS_SHOWN = ["both", "today", "tomorrow"];
const TOMORROW_PENDING = ["placeholder", "hide"];

// Per section, the details that can be left out (`hide`); what makes the section stays: the
// hours with their bars and prices, the parts of the day with their spans, the days with theirs
const SECTION_HIDES = {
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
const SECTION_DEFAULTS = {
  now: { now_decimals: "entity" },
  hours: { now_decimals: "entity" },
  day_parts: { now_decimals: "entity" },
  days: { shown: "both", tomorrow_pending: "placeholder", now_decimals: "entity" },
};

// Decimals of the current price in a section's details: as set for the price entity in Home
// Assistant (default), or a fixed number
const NOW_DECIMALS = ["entity", "0", "1", "2", "3", "4"];

// Where the card's own action button sits: at the bottom (default) or the top of the card
const ACTION_BUTTON_POSITIONS = ["bottom", "top"];

// Values the card uses when an option isn't set. A card added from the card picker carries them
// (so the editor shows them selected, not empty), and so does the dashboard from get_dashboard_yaml
const DEFAULTS = {
  price_unit: "auto",
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
function modeVariables(themes, mode) {
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
const SECTION_ICONS = {
  now: "mdi:progress-clock",
  hours: "mdi:clock-outline",
  day_parts: "mdi:weather-sunset",
  days: "mdi:calendar-range",
};

/**
 * Prices in the unit the card is set to: as the integration shows them ("auto"), or always in
 * base currency (€, kr) or subunit (ct, øre). Returns the factor to apply and the unit label.
 */
function priceUnit(stateObj, setting) {
  const units = stateObj.attributes.outlook_units;
  if (!units) return { factor: 1, unit: stateObj.attributes.unit_of_measurement || "" };
  const target = setting === "base" || setting === "subunit" ? setting : units.display;
  const factor = target === units.display ? 1 : target === "subunit" ? 100 : 0.01;
  return { factor, unit: units[target] };
}

// Every price_* field of an outlook entry, scaled
function scalePrices(entries, factor) {
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

// Color of a price level (normal for an unknown one), as in the charts
function levelColor(level) {
  return LEVEL_COLORS[level] || LEVEL_COLORS.normal;
}

// Prices with two decimals, or whole numbers once they reach 10 (øre, ct); "–" for none
function priceFormatter(hass, numbers) {
  return fixedPriceFormat(hass, Math.max(...numbers.map(Math.abs)) >= 10 ? 0 : 2);
}

// Prices with a fixed number of decimals ("–" for none); the format carries its decimals, which
// percentages between shown prices are rounded to (see shownPrice). Kept per locale and decimals:
// building an Intl format is the costly part
const PRICE_FORMATS = new Map();
function fixedPriceFormat(hass, decimals) {
  const locale = numberLocale(hass);
  const key = `${locale}|${decimals}`;
  if (!PRICE_FORMATS.has(key)) {
    const number = new Intl.NumberFormat(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    const format = (value) => (typeof value === "number" ? number.format(value) : "–");
    format.decimals = decimals;
    PRICE_FORMATS.set(key, format);
  }
  return PRICE_FORMATS.get(key);
}

// A price as shown by `format` (rounded to its decimals): what percentages between shown prices
// are computed from, so they agree with the numbers next to them ("0,67 → 0,67" is ±0 %, not
// +1 % from digits that aren't shown)
function shownPrice(format, value) {
  return format && typeof format.decimals === "number" ? Number(value.toFixed(format.decimals)) : value;
}

// A whole percentage with a real minus sign; the formatters are kept per language and sign
const PERCENT_FORMATS = new Map();
function formatPercent(language, value, signDisplay) {
  const key = `${language}|${signDisplay}`;
  if (!PERCENT_FORMATS.has(key)) {
    PERCENT_FORMATS.set(
      key,
      new Intl.NumberFormat(language, { style: "percent", maximumFractionDigits: 0, signDisplay })
    );
  }
  return PERCENT_FORMATS.get(key).format(value).replace("-", "\u2212");
}

// A level as a dot in its color and its name, inside an element of `cls`
function levelTag(t, level, cls, tag = "span") {
  return `<${tag} class="${cls}"><span class="level-dot" style="background:${levelColor(level)}"></span>${
    t.levels[level] || level
  }</${tag}>`;
}

// The best and peak price periods overlapping a stretch of time, as { k, a, b }
function periodsTouching(periods, start, end) {
  return ["best", "peak"].flatMap((k) =>
    periods[k].filter(([a, b]) => a < end && start < b).map(([a, b]) => ({ k, a, b }))
  );
}

// The days' lows and highs falling into a stretch of time
function extremesIn(extremes, start, end) {
  return extremes.filter((x) => start <= x.at && x.at < end);
}

// How far a price lies from a base, as a share of the base, both as shown by their formats
// (undefined without a usable base): percentages agree with the prices next to them
function shownChange(value, base, format, baseFormat = format) {
  if (typeof value !== "number" || typeof base !== "number") return undefined;
  const shownBase = shownPrice(baseFormat, base);
  return shownBase === 0 ? undefined : (shownPrice(format, value) - shownBase) / Math.abs(shownBase);
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

// A time of day, with midnight at the end of a span as 24:00
function endTime(clock, time) {
  return clock.format(new Date(time)).replace(/^00:00$/, "24:00");
}

function timeRange(clock, start, end) {
  return `${clock.format(new Date(start))}–${endTime(clock, end)}`;
}

// One day against another, as the words for it say: about the same within 1 %
function trendOf(change) {
  return Math.abs(change) < 0.01 ? "same" : change < 0 ? "cheaper" : "dearer";
}

// "About as …" → "about as …": a sentence's start used inside a line
function lowerFirst(text) {
  return text.replace(/^\p{Lu}/u, (letter) => letter.toLowerCase());
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
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

const HOUR_MS = 3600000;
const QUARTER_MS = 900000;
const LEVEL_STEPS = ["very_cheap", "cheap", "normal", "expensive", "very_expensive"];
// How close (in % of a span's scale) the current price and the median count as one spot: their
// lines would overlap there
const NEAR_MEDIAN = 3;

// Text from the user (a card title) as HTML text: never markup
function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// A text with its {placeholders} filled in
function fill(text, values) {
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in values ? values[name] : match));
}

// Mean or median of some prices
function aggregate(values, kind) {
  if (kind !== "median") return values.reduce((sum, v) => sum + v, 0) / values.length;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

// The level of several quarter hours together: the rounded average of their steps
function levelOfMany(levels) {
  const steps = levels.map((level) => LEVEL_STEPS.indexOf(level)).filter((step) => step >= 0);
  if (!steps.length) return undefined;
  return LEVEL_STEPS[Math.round(steps.reduce((sum, step) => sum + step, 0) / steps.length)];
}

// How far a time zone is ahead of UTC at a moment (ms); undefined: the browser's
// Kept per zone: building an Intl format is the costly part
const ZONE_FORMATS = new Map();
// "25 min", "2.5 h", kept per language and unit
const DURATION_FORMATS = new Map();
function zoneOffset(time, zone) {
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

// Midnight starting a calendar date (YYYY-MM-DD) in the home's time zone, and the next one
function dayBounds(date, zone) {
  const [year, month, day] = date.split("-").map(Number);
  const midnight = (d) => {
    const utc = Date.UTC(year, month - 1, d);
    return utc - zoneOffset(utc - zoneOffset(utc, zone), zone);
  };
  return [midnight(day), midnight(day + 1)];
}

/**
 * Where bars start: a quarter of the spread below the lowest price, never below zero while
 * prices are positive. Like temperatures in a weather forecast, so small differences show
 * (from zero, prices of 0.80 to 1.10 would all be three quarters high or more); the numbers
 * under the bars carry the exact values. With all prices equal, from zero
 */
function barBaseline(values) {
  const lowest = Math.min(...values);
  const highest = Math.max(...values);
  if (highest === lowest) return Math.min(0, lowest - 1);
  const base = lowest - (highest - lowest) * 0.25;
  return lowest >= 0 ? Math.max(0, base) : base;
}

// The price key and its label for the average shown ("⌀" for the mean)
function averageOf(t, kind) {
  return kind === "median" ? { key: "price_median", label: t.median } : { key: "price_mean", label: "⌀" };
}

// A home's calendar: its time zone, the date of a moment there and the formats of its days and
// times in the HA language. Kept per language and zone: building an Intl format is the costly part
const CALENDARS = new Map();
function homeCalendar(hass) {
  const zone = timeZone(hass);
  const key = `${hass.language}|${zone}`;
  if (!CALENDARS.has(key)) {
    const day = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: zone });
    CALENDARS.set(key, {
      zone,
      // Calendar date (YYYY-MM-DD) of a moment, in the home's time zone
      dateOf: (time) => day.format(new Date(time)),
      weekday: new Intl.DateTimeFormat(hass.language, { weekday: "long", timeZone: zone }),
      dayMonth: new Intl.DateTimeFormat(hass.language, { day: "numeric", month: "long", timeZone: zone }),
      weekdayShort: new Intl.DateTimeFormat(hass.language, { weekday: "short", timeZone: zone }),
      clock: new Intl.DateTimeFormat(hass.language, {
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
        timeZone: zone,
      }),
      hourLabel: new Intl.DateTimeFormat(hass.language, { hour: "2-digit", hourCycle: "h23", timeZone: zone }),
    });
  }
  return CALENDARS.get(key);
}

// Every quarter hour of the price sensor's outlook (from last night on), in the unit shown;
// undefined from an integration without them
function quarterSeries(stateObj, factor) {
  const series = stateObj.attributes.outlook_quarters;
  if (!series || !Array.isArray(series.prices)) return undefined;
  return {
    start: Date.parse(series.start),
    step: (series.minutes || 15) * 60000,
    prices: series.prices.map((price) => (typeof price === "number" ? price * factor : null)),
    levels: series.levels || [],
  };
}

// The average a card shows: the mean unless it says otherwise ("auto": as set for the
// integration's average sensors, which the days carry)
function averageKindOf(config, days) {
  return config.average === "auto" ? (days[0] && days[0].reference) || "mean" : config.average;
}

// Each day's average of a kind by date, yesterday's too (after midnight its last hour is still
// shown)
function dayReferences(stateObj, factor, days, key) {
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
function homePeriods(hass, entities, stateObj) {
  const past = stateObj.attributes.outlook_past_periods || {};
  return {
    best: periodSpans(hass, entities.best, past.best_price),
    peak: periodSpans(hass, entities.peak, past.peak_price),
  };
}

// Prices in steps of `size` (a quarter hour or an hour) from `from` to `to`, each with its level:
// the quarter hours in it, aggregated (mean or median); null where there are none
function quarterSlots(quarters, from, to, size, kind) {
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

// "Tagestief 0,22 kr/kWh um 03:15"
/**
 * The mark of the day's low or high: an arrow onto a line, so it reads as the bottom or top
 * reached, not as "going down" or "going up". Drawn in the text's color and size
 */
const EXTREME_PATHS = {
  low: "M6 1.5V8.5M3.2 5.8L6 8.6L8.8 5.8M2 10.6H10",
  high: "M6 10.5V3.5M3.2 6.2L6 3.4L8.8 6.2M2 1.4H10",
};
function extremeIcon(kind) {
  return `<svg class="extreme-icon" viewBox="0 0 12 12" aria-hidden="true"><path d="${EXTREME_PATHS[kind]}"></path></svg>`;
}

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

// Points and arcs of the round displays: angles in degrees, clockwise from 12 o'clock
function polar(center, radius, angle) {
  const rad = (angle * Math.PI) / 180;
  return [center + radius * Math.sin(rad), center - radius * Math.cos(rad)];
}

function arcPath(center, radius, from, to) {
  const [x0, y0] = polar(center, radius, from);
  const [x1, y1] = polar(center, radius, to);
  const large = to - from > 180 ? 1 : 0;
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${radius} ${radius} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
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
const TRACK_COLOR = "color-mix(in srgb, var(--primary-text-color, #212121) 12%, transparent)";

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

// A card's title as set, else its standard one ("Electricity prices"), ready for HTML
function cardTitle(config, t) {
  return escapeHtml(String(config.title || "").trim() || t.card_title);
}

// Errors for config values the card can't use; setConfig and the visual editor check the same
function validateConfig(config) {
  if (config.price_unit && !PRICE_UNITS.includes(config.price_unit)) {
    throw new Error("`price_unit` is `auto`, `base` or `subunit`");
  }
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
  // The cards opened in a window (now and chart card), set up as on their own
  if (config.forecast !== undefined && !isPlainObject(config.forecast)) {
    throw new Error("`forecast` holds the forecast card's options, e.g. `show: [hours, days]`");
  }
  if (config.forecast) validateConfig(config.forecast);
  if (config.chart !== undefined && !isPlainObject(config.chart)) {
    throw new Error("`chart` holds the chart card's options, e.g. `views: [today, tomorrow]`");
  }
  if (config.chart) validateChartConfig(config.chart);
}

function stringsFor(hass) {
  return STRINGS[(hass.language || "en").split("-")[0]] || STRINGS.en;
}

// The frontend sets the user's language on <html>; the editor has no hass object at hand
function languageStrings(table) {
  return table[(document.documentElement.lang || "en").split("-")[0]] || table.en;
}

// An icon of Material Design's 24 px grid, for a button
function svgIcon(path) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"></path></svg>`;
}

// The head of a window, like HA's dialogs: the close (or back) button left of the title (a
// smaller line above it where given), buttons at its end
function dialogHead({ id, title, label, back = false, subtitle = "", end = "" }) {
  return `<div class="dialog-head"><button class="close${back ? " back" : ""}" aria-label="${label}" title="${label}">${svgIcon(
    back ? BACK_PATH : CLOSE_PATH
  )}</button><div class="dialog-titles">${
    subtitle ? `<div class="dialog-subtitle">${subtitle}</div>` : ""
  }<h2 id="${id}">${title}</h2></div>${end}</div>`;
}

// Focus rings only for the keyboard (see BASE_STYLE): each focus in the element's shadow root
// decides, by the input that led to it
function trackKeyboard(host) {
  host.shadowRoot.addEventListener("focusin", () => host.toggleAttribute("data-keyboard", keyboardInput));
}

// What every shadow root of the cards and editors starts with: focus rings only for the keyboard
// (the shadow root's focusin sets data-keyboard), and the hidden attribute hiding an element
// whatever display its class gives it
const BASE_STYLE = `
  :host { --focus-ring: none; }
  :host([data-keyboard]) { --focus-ring: 2px solid var(--primary-color, #03a9f4); }
  :host(:not([data-keyboard])) :focus-visible { outline: none; }
  [hidden] { display: none !important; }
`;

// The pulsing dot of what's live (now): a ring slowly pulsing out of it, like a live broadcast's
// (in the "now" blue, not red: red means expensive here). Still for those who reduce motion. Its
// size and color: --live-dot-size, --live-dot-color
const LIVE_DOT_STYLE = `
  .live-dot { position: relative; width: var(--live-dot-size, 8px); height: var(--live-dot-size, 8px); border-radius: 50%;
              background: var(--live-dot-color, var(--primary-color, #03a9f4)); }
  .live-dot::after { content: ""; position: absolute; inset: 0; border-radius: 50%; background: inherit;
                     animation: live-pulse 2s ease-out infinite; }
  @keyframes live-pulse {
    from { transform: scale(1); opacity: 0.7; }
    to { transform: scale(2.6); opacity: 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    .live-dot::after { animation: none; opacity: 0; }
  }
`;

// A card's own action button, a text button in the primary color like HA's; the invisible
// ::after reaches into the space around it (its touch target)
const ACTION_BUTTON_STYLE = `
  .action-button { position: relative; display: inline-flex; align-items: center; min-height: 28px; border: 0;
                   border-radius: 14px; background: none; cursor: pointer; font: inherit;
                   font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
                   color: var(--primary-color, #03a9f4); white-space: nowrap; touch-action: manipulation; }
  .action-button::after { content: ""; position: absolute; inset: -10px -4px; }
  .action-button:hover { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.08); }
  .action-button:focus-visible { outline: var(--focus-ring); outline-offset: 0; }
`;

// Class names in the styles: an element's kind is a word (`.chip`, `.col`). A state a script
// switches on a container is `is-…` (what it is now), `has-…` (what it holds) or `no-…` (what it
// leaves out): a bare word there would also match an element of that name inside it (a compact
// card and a compact chip, a cell shown as the default and the default mark). A single item's
// state stays a word beside its kind (`.col.passed`)

// The frame of a window (legend, details, a card in a window)
const WINDOW_STYLE = `
  /* Legend, details, a card in a window: a modal dialog in the top layer, so no card or section edge cuts it off.
     Built like HA's own dialogs: the close button (X) left of the title in a header that stays
     put while the content below it scrolls, full screen on phones, wider from 720 px on */
  dialog { width: min(440px, calc(100vw - 32px)); max-height: calc(100vh - 64px); box-sizing: border-box;
           padding: 0; border: 0; border-radius: var(--ha-card-border-radius, 12px); overflow: hidden;
           color: var(--primary-text-color); font-family: var(--ha-font-family-body, inherit);
           background: var(--ha-card-background, var(--card-background-color, #fff));
           box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); }
  dialog[open] { display: flex; flex-direction: column; }
  dialog::backdrop { background: rgba(0, 0, 0, 0.4); }
  .dialog-scroll { flex: 1 1 auto; min-height: 0; overflow: auto; }
  /* Full screen exactly when HA's own dialogs go full screen. There the window reaches under the
     status bar, the home indicator and the notch: padded off them like HA's own dialogs, with
     the safe area insets HA sets for its frontend and the companion app (else the browser's) */
  @media all and (max-width: 450px), all and (max-height: 500px) {
    :host dialog,
    :host dialog:has(.detail) { width: 100vw; max-width: none; height: 100dvh; max-height: none; margin: 0; border-radius: 0;
                                padding: var(--safe-area-inset-top, env(safe-area-inset-top, 0px))
                                         var(--safe-area-inset-right, env(safe-area-inset-right, 0px))
                                         var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px))
                                         var(--safe-area-inset-left, env(safe-area-inset-left, 0px)); }
  }
  @media (min-width: 720px) {
    dialog { width: min(880px, calc(100vw - 64px)); }
  }
  .dialog-head { flex: none; display: flex; align-items: center; min-height: 64px; box-sizing: border-box;
                 padding: 4px 24px 0 4px; }
  .dialog-head h2 { flex: 1; min-width: 0; margin: 0 0 0 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                    color: var(--ha-dialog-header-title-color, var(--primary-text-color));
                    font-size: var(--ha-dialog-header-title-font-size, var(--ha-font-size-2xl, 24px));
                    line-height: var(--ha-dialog-header-title-line-height, var(--ha-line-height-condensed, 1.2));
                    font-weight: var(--ha-dialog-header-title-font-weight, var(--ha-font-weight-normal, 400)); }
  .dialog-titles { flex: 1; min-width: 0; margin-left: 8px; }
  .dialog-titles h2 { margin: 0; }
  .close { width: 48px; height: 48px; padding: 0; border: 0; border-radius: 50%; background: none; cursor: pointer;
           display: inline-flex; align-items: center; justify-content: center; color: var(--primary-text-color);
           touch-action: manipulation; }
  .close svg { width: 24px; height: 24px; fill: currentColor; }
  .close:hover { background: rgba(127, 127, 127, 0.12); }
  .close:focus-visible { outline: var(--focus-ring); outline-offset: -4px; }
  .dialog-body { padding: 8px 24px 24px; }
`;

// The window of a card in another card: the frame, as wide as set (on phones full screen like the
// other windows), the card without its own frame. It doesn't take the dashboard's rows: its height
// is its own. The element itself takes no room
const CARD_WINDOW_STYLE = `
  ${BASE_STYLE}
  :host { position: absolute; width: 0; height: 0; overflow: hidden; }
  ${WINDOW_STYLE}
  @media (min-width: 451px) and (min-height: 501px) {
    dialog { width: min(880px, calc(100vw - 64px)); }
    dialog:has(.narrow) { width: min(560px, calc(100vw - 32px)); }
    dialog:has(.wide) { width: min(1280px, calc(100vw - 64px)); }
    dialog:has(.full) { width: calc(100vw - 64px); max-width: none; }
  }
  .window-body { padding: 0 8px 8px; --row-size: initial; --row-height: initial; --row-gap: initial; }
  .window-body > * { display: block; --ha-card-border-width: 0; --ha-card-box-shadow: none; }
`;

// Layout on an 8 px grid with HA's type scale. Every column has the same fixed rows (day,
// label, graph with the cheapest chip floating in it, value, range, mark), so labels, bars,
// prices and marks sit on one line across a strip, whatever a column contains
const STYLE = `
  :host { position: relative; display: block; height: 100%; }
  /* The icon top right opening the chart card in a window; the trend gives way to it */
  .chart-open { position: absolute; top: 6px; right: 6px; z-index: 2; display: inline-flex; align-items: center; justify-content: center;
                width: 36px; height: 36px; padding: 0; border: 0; border-radius: 50%; background: none; cursor: pointer;
                color: var(--secondary-text-color); --mdc-icon-size: 20px; }
  .chart-open::after { content: ""; position: absolute; inset: -4px; }
  .chart-open:hover { background: rgba(127, 127, 127, 0.12); color: var(--primary-text-color); }
  .chart-open:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  ha-card:has(> .now-tile) ~ .chart-open { top: 50%; transform: translateY(-50%); }
  ha-card.has-chart-button .now-trend { right: 44px; }
  ha-card.has-chart-button .now-gauge > .now-trend, ha-card.has-chart-button .now-clock > .now-trend { right: 48px; }
  ha-card.has-chart-button .now-head.has-trend { padding-right: 76px; }
  ha-card.has-chart-button .now-head:not(.has-trend) { padding-right: 44px; }
  ha-card.has-chart-button .now-tile { padding-right: 44px; }
  /* Focus rings for the keyboard only (see keyboardInput): after a tap or a click, focus the
     card set itself (the window's close button, the column a window was opened from) stays
     without one. The cards' rings draw --focus-ring; the browser's own ring goes too */
  ${BASE_STYLE}
  /* Lines drawn on the level colors: those colors don't change with the theme, and only a near
     black stands out on all five (contrast 4.5 to 10; white, light grey and the primary blue
     reach 1.1 to 3.8). The "now" line keeps its blue as a core between two such edges */
  ha-card { --on-level-color: #1c1c1c; }
  /* What past things in a chart are paled toward */
  ha-card, dialog { --fade-bg: var(--ha-card-background, var(--card-background-color, #fff));
                    /* Sizes the wide steps below raise: bar and span widths, the strips' row heights */
                    --bar-w: 20px; --span-w: 14px; --day-h: 12px; --day-gap: 6px; --name-h: 16px; --value-h: 20px; --label-h: 14px; }
  /* ha-card animates every change (transition: all 0.3s). This card renders as soon as it has
     data, often before Home Assistant has styled the page, and would visibly fade from a square
     card with a light border into its final look on every load. It doesn't animate */
  ha-card { padding: 16px; container: card / inline-size; height: 100%; box-sizing: border-box;
            display: flex; flex-direction: column; transition: none; }
  /* A fixed height too small for its content: it scrolls inside the card (see _fitFixedHeight),
     the bottom faded in the card's background while there's more below (not a mask, which
     would fade the card's border too; ::before is the card's hover layer) */
  ha-card.is-scrollable { overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; }
  ha-card.is-scrollable::after { content: ""; position: sticky; bottom: -16px; z-index: 3; flex: none; order: 99;
                            height: 32px; margin: -16px -16px -16px; pointer-events: none; opacity: 0;
                            transition: opacity 0.15s; background: linear-gradient(transparent, var(--fade-bg)); }
  ha-card.is-scrollable.has-more-below::after { opacity: 1; }
  /* Room left over when the card is taller than its content (rounded up to whole grid rows, or
     a fixed height): the days spread over it, otherwise the footer moves to the bottom. So the
     card ends where its neighbours do without a blank strip at the bottom */
  ha-card > .footer:last-child { margin-top: auto; padding-top: calc(12px - 6px * var(--squeeze, 0)); }
  ha-card > .days, .split .side > .days { flex: 1; align-content: space-evenly; }
  /* Strips and days together, in the order set in show. Narrow: one column, the main part's
     strips and footer joining the days as items ordered by the card (footer after the last
     strip); wide: the days in a column of their own, see the container query below */
  .split { flex: 1; display: flex; flex-direction: column; row-gap: calc(16px - 8px * var(--squeeze, 0)); }
  .split > .main { display: contents; }
  .split > .side { order: var(--order); flex: 1 0 auto; display: flex; flex-direction: column; }
  .split .strip-wrap + .strip-wrap, .split .main > .footer { margin-top: 0; }
  /* A divider on each side the days have neighbours */
  .split > .side.after > .days { padding-top: calc(16px - 6px * var(--squeeze, 0)); border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
  .split > .side.before > .days { padding-bottom: calc(16px - 6px * var(--squeeze, 0)); border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
  ha-card.is-interactive { cursor: pointer; position: relative; }
  /* Hover and press feedback like HA's own cards (button, entity): a faint layer in the state
     icon color, 4 % on hover and 12 % when pressed, as their ha-ripple does. Not over the
     card's own buttons, which don't run the card's action */
  ha-card.is-interactive::before { content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
                                background: var(--ha-ripple-color, var(--state-icon-color, #44739e)); opacity: 0;
                                transition: opacity 15ms linear; }
  @media (hover: hover) {
    ha-card.is-interactive:hover:not(:has(button:hover))::before {
      background: var(--ha-ripple-hover-color, var(--ha-ripple-color, var(--state-icon-color, #44739e)));
      opacity: var(--ha-ripple-hover-opacity, 0.04); }
  }
  /* Columns that open their details are buttons of their own: they light up, not the card */
  ha-card.column-details .col[data-detail], ha-card.column-details .day-row[data-day] { cursor: pointer; }
  /* Room around a day row for its hover and focus, without moving anything */
  .day-row[data-day] { margin: -4px -8px; padding: 4px 8px; border-radius: 12px; }
  @media (hover: hover) {
    ha-card.column-details .col[data-detail]:hover,
    ha-card.column-details .day-row[data-day]:hover { background: rgba(127, 127, 127, 0.08); }
    ha-card.column-details .col.current[data-detail]:hover { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.18); }
    ha-card.is-interactive.column-details:hover:has(.col[data-detail]:hover, .day-row[data-day]:hover)::before { opacity: 0; }
  }
  ha-card.column-details .col[data-detail]:focus-visible,
  ha-card.column-details .day-row[data-day]:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  ha-card.is-interactive:active:not(:has(button:active)):not(.column-details:has(.col:active, .day-row[data-day]:active))::before {
    background: var(--ha-ripple-pressed-color, var(--ha-ripple-color, var(--state-icon-color, #44739e)));
    opacity: var(--ha-ripple-pressed-opacity, 0.12); }
  ha-card:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  /* Scrolling sideways clips the top too: 9 px of room above the columns, given back by the
     margin, so a badge on a column's corner isn't cut off and nothing moves. Above that room,
     the day row: a band of the strip, not of its columns, where the day names run across the
     columns (see .day), clear of a column's tint, hover and focus ring */
  .strip { position: relative; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(var(--col-min), 1fr); gap: 4px;
           overflow-x: auto; scrollbar-width: none; padding-top: calc(9px + var(--row-day, var(--day-h)) + var(--day-gap) + 4px);
           margin-top: -9px; }
  .strip::-webkit-scrollbar { display: none; }
  /* Places to snap to: where the strip rests (letting go near it, it settles there, as in other
     apps), and both ends, so an end close to that place stays reachable rather than snapping
     back; in between, scrolling stays free */
  .strip { scroll-snap-type: x proximity; }
  /* The price steps to the neighbouring hours, while one is hovered */
  .zoom { position: relative; }
  .steps { position: absolute; top: 0; left: 0; z-index: 2; overflow: visible; pointer-events: none;
           opacity: 0; transition: opacity 0.2s ease-out; }
  .steps.is-shown { opacity: 1; }
  .steps.is-leaving { transition-duration: 0.15s; }
  .strip.hours .chip { transition: opacity 0.2s ease-out; }
  @media (prefers-reduced-motion: reduce) {
    .steps, .strip.hours .chip { transition: none; }
  }
  .steps line { stroke-width: 1.5; stroke: currentColor; }
  .steps path { fill: currentColor; }
  .steps text { fill: currentColor; text-anchor: middle; font-size: var(--ha-font-size-s, 12px);
                font-weight: var(--ha-font-weight-bold, 600); font-variant-numeric: tabular-nums;
                paint-order: stroke; stroke: var(--ha-card-background, var(--card-background-color, #fff));
                stroke-width: 4px; stroke-linejoin: round; }
  .steps .up { color: var(--error-color, #db4437); }
  .steps .down { color: var(--success-color, #43a047); }
  .steps .same { color: var(--secondary-text-color); }
  /* Meanwhile the chips step back, so the percentages don't collide with them */
  .strip.hours.has-steps .chip { opacity: 0.15; }
  .col.home, .col:first-of-type { scroll-snap-align: start; }
  .col:last-of-type { scroll-snap-align: end; }
  .strip.hours { --col-min: 40px; }
  /* Touch: hours a finger's width (44 px, Apple's minimum target; Material asks 48). Wider cards
     set wider columns below anyway */
  @media (any-pointer: coarse) {
    .strip.hours { --col-min: 44px; }
  }
  /* Four parts of the day at a time, a whole day's round: the one before now, now, and two to
     come; scrolling shows more */
  .strip.parts { --col-min: 60px; grid-auto-columns: max(var(--col-min), calc((100% - 12px) / 4)); }
  /* Strips take the card's spare height (rounded up to grid rows, or a fixed height) in their
     graph row: bars and spans grow from 76 px up to 140 px, everything else keeps its place.
     --fade is the faded edge where a strip scrolls on (set by the ResizeObserver): a hint on
     phones, clearly visible on wide cards */
  .strip-wrap { position: relative; --fade: clamp(${FADE.min}px, ${FADE.share * 100}%, ${FADE.max}px); --graph: minmax(calc(76px - 12px * var(--squeeze, 0)), 1fr); --pad: calc(8px - 4px * var(--squeeze, 0));
                --above: calc(36px + var(--pad)); --below: calc(49px + var(--pad));
                flex: 1 0 auto; display: flex; flex-direction: column; max-height: calc(44px + 140px + var(--below)); }
  .strip-wrap > .strip { flex: 1 0 auto; }
  /* Below the graph: value, (range,) extreme, mark, their gaps and the column padding */
  .strip-wrap:has(> .parts) { --below: calc(67px + var(--pad)); }
  .is-compact .strip-wrap:has(> .parts) { --below: calc(49px + var(--pad)); }
  .strip.has-more-right { mask-image: linear-gradient(to right, #000 calc(100% - var(--fade)), transparent); }
  .strip.has-more-left { mask-image: linear-gradient(to left, #000 calc(100% - var(--fade)), transparent); }
  .strip.has-more-left.has-more-right {
    mask-image: linear-gradient(to right, transparent, #000 var(--fade), #000 calc(100% - var(--fade)), transparent); }
  /* Page buttons where a strip goes on: for mouse and keyboard, and as a visible cue to swipe.
     Centered on the graph row: day row 12 + 4, padding 8, name 16 + gap 4 = 44 above it,
     --below under it */
  .scroll { position: absolute; top: calc(var(--above) + (100% - var(--above) - var(--below)) / 2); width: 32px; height: 32px; margin-top: -16px; padding: 0; border: 0;
            border-radius: 50%; display: none; align-items: center; justify-content: center; cursor: pointer;
            color: var(--primary-text-color); background: var(--ha-card-background, var(--card-background-color, #fff));
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25); z-index: 1; }
  .scroll svg { width: 20px; height: 20px; fill: currentColor; }
  /* Touch: a 44 px target around the 32 px button (a bigger button would hide a column) */
  @media (any-pointer: coarse) {
    .scroll::after { content: ""; position: absolute; inset: -6px; border-radius: 50%; }
  }
  .scroll.back { left: 0; }
  .scroll.forward { right: 0; }
  .strip-wrap.has-more-left .scroll.back, .strip-wrap.has-more-right .scroll.forward { display: inline-flex; }
  .no-scroll-back .scroll.back, .no-scroll-forward .scroll.forward { display: none !important; }
  .scroll:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  .strip-wrap + .strip-wrap { margin-top: calc(16px - 8px * var(--squeeze, 0)); }
  .col { position: relative; display: grid; row-gap: 4px;
         grid-template-rows: var(--name-h) var(--graph) var(--value-h) var(--row-range, var(--label-h))
                             var(--row-extreme, var(--label-h)) var(--row-mark, 3px);
         justify-items: center; padding: var(--pad) 0; border-radius: 12px; }
  .col.current { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  /* What's over (the hour before now): faded, like past bars in the details; the day's dashed
     line runs on unbroken */
  .col.past > :not(.graph) { opacity: 0.45; }
  /* What's past in a chart turns pale by mixing toward the background, not by transparency: the
     day's line behind the bars and spans stays hidden */
  .col.past, .zcol.past { --pale: 45%; --pale-marks: 45%; }
  .partial { --pale: 50%; --pale-marks: 60%; }
  .col.past .bar, .col.past .span, .zcol.past .zbar, .partial .span {
    background: color-mix(in srgb, var(--c) var(--pale), var(--fade-bg)); }
  .col.past .tick, .partial .tick { border-right-color: color-mix(in srgb, var(--primary-text-color) var(--pale-marks), var(--fade-bg)); }
  .col.past .tick-line, .partial .tick-line { background: color-mix(in srgb, var(--on-level-color) var(--pale-marks), var(--fade-bg)); }
  .col.past .bar, .col.past .span, .zcol.past .zbar { box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.05); }
  /* Where the next day begins: a line in the gap before its first column, and its name set
     like a calendar's month, from the line onwards across the columns. It also explains why
     the dashed reference line jumps there: from here on it's the next day's. The line fades out
     at both ends, so the lines of two strips one above the other don't meet hard */
  .col.new-day::before { content: ""; position: absolute; top: calc(-4px - var(--row-day, var(--day-h)) - var(--day-gap)); bottom: 0; left: -2.5px; width: 1px; opacity: 0.35;
                         color: var(--secondary-text-color);
                         background: linear-gradient(to bottom, transparent, currentColor 32px,
                                                     currentColor calc(100% - 32px), transparent); }
  .day, .name, .range { white-space: nowrap; color: var(--secondary-text-color); }
  /* A day's name (or how far a part of the day is known) in the strip's day row, over its column:
     placed in the column's grid area, it takes no room in the strip. Moved along while its
     divider is scrolled out on the left (see _stickDayNames), above the columns it passes */
  /* A day's name over the strip, apart from the columns below it (--day-gap) */
  .day { position: absolute; z-index: 2; grid-row: 1; top: calc(-1 * (var(--row-day, var(--day-h)) + var(--day-gap)));
         height: var(--day-h); line-height: var(--day-h); font-size: var(--ha-font-size-xs, 10px); pointer-events: none; }
  .day:not(.start) { left: 50%; translate: -50% 0; }
  /* (Faded as far as the next day's name pushes it out on the left, see _stickDayNames) */
  .day.start { opacity: var(--pushed-out, 1); }
  .day.past { opacity: calc(0.45 * var(--pushed-out, 1)); }
  .day.start { left: 0; padding-left: 6px; font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-bold, 600);
               color: var(--primary-text-color); }
  /* Too little room left in its day: the first word only */
  .day.start.is-short > :not(:first-child) { display: none; }
  .name { height: var(--name-h); line-height: var(--name-h); font-size: var(--ha-font-size-s, 12px); }
  .current .name { color: var(--primary-text-color); font-weight: var(--ha-font-weight-bold, 600); }
  .chip { font-size: var(--ha-font-size-xs, 10px); font-weight: var(--ha-font-weight-bold, 600); line-height: 16px;
          padding: 0 6px; border-radius: 8px; color: var(--success-color, #43a047);
          background: rgba(var(--rgb-success-color, 67, 160, 71), 0.15); font-variant-numeric: tabular-nums; }
  /* (Its own stacking context: the day's line goes behind the bars and spans, not behind the
     column's highlight) */
  .graph { position: relative; isolation: isolate; width: 100%; min-height: calc(76px - 12px * var(--squeeze, 0)); }
  /* In the graph above the bar or span: solid, ringed in the card's color, so it reads on top of
     a span reaching up there too */
  .graph > .chip { position: absolute; left: 50%; z-index: 1; transform: translateX(-50%); white-space: nowrap;
                   background: var(--ha-card-background, var(--card-background-color, #fff));
                   background-image: linear-gradient(rgba(var(--rgb-success-color, 67, 160, 71), 0.15),
                                                     rgba(var(--rgb-success-color, 67, 160, 71), 0.15));
                   box-shadow: 0 0 0 2px var(--ha-card-background, var(--card-background-color, #fff)); }
  /* (Colored by --c, its level's color: CSS can pale it, see .past) */
  .bar, .span, .zbar { background: var(--c); }
  /* Bar and span widths grow with the text on wide cards (--bar-w, --span-w); the pointers on a
     span follow its width. A span stays about two thirds of a bar: it floats and shows a range
     (low to high), and as wide as a bar it would read as one (a quantity from the baseline) */
  .bar { position: absolute; bottom: 0; left: 50%; width: var(--bar-w); margin-left: calc(var(--bar-w) / -2);
         border-radius: 4px;
         box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  /* Spans and average markers read as a chart, not as a control: no rail behind the span (a
     rail plus a handle is the look of a slider), and the median as a small pointer beside it */
  .span { position: absolute; left: 50%; width: var(--span-w); margin-left: calc(var(--span-w) / -2);
          min-height: 8px; border-radius: 3px;
          box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  /* The median's pointer on the right of the span, pointing left; the left, read first, is for
     the current price (like today's row: now above, the median below) */
  .tick { position: absolute; left: 50%; width: 0; height: 0; margin: 0 0 -5px calc(var(--span-w) / 2);
          border-top: 5px solid transparent; border-bottom: 5px solid transparent;
          border-right: 6px solid var(--primary-text-color); }
  /* The pointer touches the span, its line runs across the span only: the exact spot, still
     clearly not a handle. 2 px, centered on the tip (the pointer is 10 px high) */
  .tick-line { position: absolute; left: 50%; width: var(--span-w); height: 2px;
               margin: 0 0 -1px calc(var(--span-w) / -2);
               background: var(--on-level-color); }
  /* Day reference: dashed, reaching across the column gap so neighbouring columns join up */
  /* The day's line runs behind the bars and spans, like a chart's reference line: the eye carries
     it on across them, and pointers on a span stay clear of it */
  .ref { position: absolute; z-index: -1; left: -2px; right: -2px; height: 0; margin-bottom: -0.75px; pointer-events: none;
         border-top: 1.5px dashed var(--secondary-text-color); opacity: 0.8; }
  /* The outer columns stay inside the strip, or it would count as scrolling */
  .col:first-of-type .ref { left: 0; }
  .col:last-of-type .ref { right: 0; }
  .value { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); line-height: var(--value-h);
           color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  .range { height: var(--label-h); line-height: var(--label-h); font-size: 11px; font-variant-numeric: tabular-nums; }
  /* Hours, and parts of the day in the compact layout, have no min–max row (the span shows them;
     screen readers still get them), so both strips line up exactly */
  .hours .col, .is-compact .parts .col {
    grid-template-rows: var(--name-h) var(--graph) var(--value-h)
                        var(--row-extreme, var(--label-h)) var(--row-mark, 3px);
  }
  .hours .range, .is-compact .parts .range { display: none; }
  /* The day's low and high: when exactly (quarter hour), under the column it falls in */
  .extreme { height: var(--label-h); line-height: var(--label-h); font-size: var(--ha-font-size-xs, 10px); white-space: nowrap;
             font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; }
  .extreme .low, .day-info .low { color: var(--success-color, #43a047); }
  .extreme .high, .day-info .high { color: var(--error-color, #db4437); }
  .day-info .extremes { white-space: nowrap; font-variant-numeric: tabular-nums; }
  /* A low or high already behind us: greyed, the value stays readable */
  .day-info .passed, .day-min.passed, .day-max.passed { color: var(--secondary-text-color); opacity: 0.6; }
  .extreme span + span { margin-left: 4px; }
  /* A period running now: a small round badge on top of the bar or span of now, in the
     period's color (also beside "Today" and in the legend) */
  .period-badge { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px;
                  border-radius: 50%; box-sizing: border-box; color: #fff; background: var(--badge);
                  box-shadow: 0 0 0 2px var(--ha-card-background, var(--card-background-color, #fff)); }
  .period-badge svg { width: 12px; height: 12px; fill: currentColor; }
  .period-badge.best { --badge: var(--success-color, #43a047); }
  .period-badge.peak { --badge: var(--error-color, #db4437); }
  /* Centered on the top right corner of the highlighted column, like a badge on an app icon:
     out of the flow, it takes no room. In a strip, its top on the column's top instead (above it
     is the day row, where the day's name runs across the columns) and 3 px further out, so its
     ring stays clear of the hour's name ("Now") in a 40 px column */
  .col > .period-badge, .zcol > .period-badge { position: absolute; top: -9px; right: -9px; z-index: 1; }
  .col > .period-badge { top: 0; right: -12px; }
  .dense .zcol > .period-badge { top: -7px; right: -7px; width: 14px; height: 14px; }
  .dense .zcol > .period-badge svg { width: 10px; height: 10px; }
  /* Beside "Today", floating: the row keeps its height */
  .day-name { position: relative; }
  .day-name .period-badge { position: absolute; top: 1px; margin-left: 6px; }
  /* The low and high mark: as large as the text beside it, in its color */
  .extreme-icon { width: 1em; height: 1em; vertical-align: -0.125em; fill: none; stroke: currentColor;
                  stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  /* A day part known only until the prices end: same data, visibly unfinished */
  /* Cut off at the top of the scale (a price far above the rest): a slanted gap near its top,
     like a broken axis */
  .bar.cut::after, .span.cut::after { content: ""; position: absolute; left: -2px; right: -2px; top: 6px; height: 3px;
                                      background: var(--ha-card-background, var(--card-background-color, #fff));
                                      transform: skewY(-20deg); }
  /* Partly known: pale like what's past (mixed, not transparent, so the day's line stays hidden
     behind it) and outlined dashed */
  .partial .span { outline: 1.5px dashed var(--secondary-text-color); outline-offset: 1px; }
  /* The dashed outline lies 2.5 px around the span: the pointers touch it from outside, like
     the span itself otherwise */
  .partial .tick { margin-left: calc(var(--span-w) / 2 + 3px); }
  .partial .tick-now { margin-left: calc(var(--span-w) / -2 - 9px); }
  /* The current price on the running part's span: blue, on the left (read first), the tip
     touching the span, its line across the span like today's (2 px blue with a halo in the
     card's background) */
  .tick-now { position: absolute; left: 50%; z-index: 1; width: 0; height: 0;
              margin: 0 0 -5px calc(var(--span-w) / -2 - 6px);
              border-top: 5px solid transparent; border-bottom: 5px solid transparent;
              border-left: 6px solid var(--primary-color, #03a9f4); }
  /* Current price and median at one spot: each pointer's line runs from its side to the middle */
  .tick-now-line.meets { width: calc(var(--span-w) / 2); }
  .tick-line.meets { width: calc(var(--span-w) / 2); margin-left: 0; }
  .day-now-line.meets { bottom: 50%; }
  .day-tick-line.meets { top: 50%; }
  .tick-now-line { position: absolute; left: 50%; z-index: 1; width: var(--span-w); height: 4px;
                   margin: 0 0 -2px calc(var(--span-w) / -2);
                   box-sizing: border-box; background: var(--primary-color, #03a9f4);
                   border: solid var(--ha-card-background, var(--card-background-color, #fff)); border-width: 1px 0; }
  .day.partial { font-style: italic; }
  .mark { position: relative; width: 80%; height: 3px; border-radius: 2px; overflow: hidden; }
  .mark.has { background: rgba(127, 127, 127, 0.2); }
  .mark span { position: absolute; top: 0; bottom: 0; }
  /* Days: one row per day; name, min, span, max and average on one line, details below */
  .days { display: grid; row-gap: 12px; }
  /* (The lines 8 px apart: the median's pointer reaches 6 px under the span) */
  .day-row { display: grid; grid-template-columns: 72px 40px 1fr 40px minmax(64px, auto); column-gap: 8px; row-gap: 8px;
             grid-template-areas: "name track track track mean" "info info info info info"; align-items: center; }
  /* The day's name and its average on one baseline (the average's smaller sign would shift its
     line otherwise), the span centered beside them */
  .day-name { grid-area: name; align-self: baseline; }
  .day-track { grid-area: track; }
  .day-mean { grid-area: mean; align-self: baseline; }
  .day-info { grid-area: info; }
  /* Tomorrow against today, under its average (the row keeps its info line beside it) */
  .day-row.has-vs { grid-template-areas: "name track track track mean" "info info info info vs"; }
  .day-vs { grid-area: vs; justify-self: end; align-self: start; font-size: var(--ha-font-size-s, 12px); line-height: 16px;
            font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .day-vs.cheaper { color: var(--success-color, #43a047); }
  .day-vs.dearer { color: var(--error-color, #db4437); }
  .day-vs.same { color: var(--secondary-text-color); }
  /* The row's title, like a name in HA's own lists: medium, so it stands out without outweighing
     the day's price on the right */
  .day-name { font-size: var(--ha-font-size-m, 14px); line-height: 20px; color: var(--primary-text-color);
              font-weight: var(--ha-font-weight-medium, 500); }
  /* Lowest and highest price at the ends of the span, on its scale: the same price stands at the
     same place in both rows, so similar days line up. The track keeps room for them at its sides */
  .day-min, .day-max { position: absolute; top: 50%; transform: translateY(-50%); white-space: nowrap;
                       font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color);
                       font-variant-numeric: tabular-nums; }
  .day-track { position: relative; height: 10px; margin: 0 44px; }
  .day-span { position: absolute; top: 0; bottom: 0; min-width: 6px; border-radius: 3px;
              box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  /* The day's median: a pointer under the span like the one at the parts of the day (pointers
     always mark the median; dashed lines the average shown), with a 2 px line across the span,
     centered on the tip. Below, as a measure of the day; above is for "now" */
  .day-tick { position: absolute; top: 100%; width: 0; height: 0; margin-left: -5px;
              border-left: 5px solid transparent; border-right: 5px solid transparent;
              border-bottom: 6px solid var(--primary-text-color); }
  .day-tick-line { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px;
                   background: var(--on-level-color); }
  /* The price now (today only): a triangle above the span pointing at it, like a playhead or a
     "you are here" pin, in the color of the "now" column,
     with a line across the span like the median's: 2 px blue with a 1 px halo in the card's
     background, which sets it off from every level color in both themes; drawn above the median's */
  .day-now-line { position: absolute; top: 0; bottom: 0; width: 4px; margin-left: -2px; z-index: 1;
                  box-sizing: border-box; border: solid var(--ha-card-background, var(--card-background-color, #fff));
                  border-width: 0 1px;
                  background: var(--primary-color, #03a9f4); }
  .day-now { position: absolute; top: -6px; z-index: 1; width: 0; height: 0; margin-left: -5px;
             border-left: 5px solid transparent; border-right: 5px solid transparent;
             border-top: 6px solid var(--primary-color, #03a9f4); }
  .day-mean { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); line-height: 20px;
              text-align: right; color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  /* Dot and text side by side: a wrapped line starts under the text, not under the dot */
  .day-info { display: flex; flex-wrap: wrap; align-items: baseline; font-size: var(--ha-font-size-s, 12px); line-height: 16px;
              color: var(--secondary-text-color); }
  /* Low and high wrapped onto a line of their own: no dot at the end of the line above, and
     lined up with the text (after the level's dot) */
  .day-info.is-wrapped .day-sep { display: none; }
  /* (Spaced by margin: a flex item drops the spaces at its edges) */
  .day-sep { margin: 0 0.3em; }
  .day-info.is-wrapped > .level-dot ~ .extremes { margin-left: 14px; }
  .level-dot { display: inline-block; width: 8px; height: 8px; flex: none; margin-right: 6px; border-radius: 50%;
               vertical-align: 0; box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  /* Narrow (e.g. half a section): name and reference on top, the span over the full width,
     lowest and highest price at its ends below it */
  @container card (max-width: 319px) {
    .day-row { grid-template-columns: 1fr auto; row-gap: 4px;
               grid-template-areas: "name mean" "track track" "info info"; }
    /* No room under it here: right after the average, on its line */
    .day-row.has-vs { grid-template-columns: 1fr auto auto;
                      grid-template-areas: "name mean vs" "track track track" "info info info"; }
    .day-row.has-vs .day-vs { align-self: center; }
    /* Room for the median's pointer under the span before the line below */
    .day-track { margin-top: 8px; margin-bottom: 10px; }
    /* Centered, like the span above; low and high on a line of their own */
    .day-info { justify-content: center; text-align: center; }
    .day-info.is-wrapped > .level-dot ~ .extremes { margin-left: 0; }
    /* A day's name over the strips: centered over its column, word and weekday stacked */
    .strip.two-part-days { --row-day: 24px; }
    .day.start { left: 50%; translate: -50% 0; padding-left: 0; height: auto; display: flex;
                 flex-direction: column; align-items: center; text-align: center; }
    .day.start .label-sep { display: none; }
    .switch .label { display: none; }
  }
  /* The days alone in a card wide enough (say tomorrow's on a dashboard): a size up, as in a
     column of their own beside the strips (see below); the rows spread over the card's height */
  @container card (min-width: 420px) {
    ha-card > .days .day-name, ha-card > .days .day-mean { font-size: var(--ha-font-size-l, 16px); line-height: 24px; }
    ha-card > .days .ref-kind { font-size: var(--ha-font-size-s, 12px); }
    ha-card > .days .day-info, ha-card > .days .day-vs, ha-card > .days .day-min, ha-card > .days .day-max {
      font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
    ha-card > .days .day-track { height: 12px; margin: 0 52px; }
    ha-card > .days .day-row { row-gap: 10px; }
  }
  /* Wide (two sections or a big screen): the days move beside hours and parts of the day,
     like the daily list next to the hourly one in a weather app */
  @container card (min-width: 880px) {
    /* The side column is as tall as hours and parts of the day; the days spread evenly over it,
       like in the compact layout (aligning them to the strips would suggest a link that isn't
       there: both strips cover today and tomorrow) */
    /* The days' column grows with the card (a fixed 360 px squeezed their lines on wide ones) */
    .split { display: grid; grid-template-columns: minmax(0, 1fr) clamp(360px, 30%, 520px); column-gap: 24px;
             align-items: stretch; }
    .split.days-first { grid-template-columns: clamp(360px, 30%, 520px) minmax(0, 1fr); }
    .split > .main { display: flex; flex-direction: column; }
    .split > .main > .now-row { margin-block: calc(16px - 8px * var(--squeeze, 0)); }
    .split > .main > .now-row:first-child { margin-top: 0; }
    .split > .side { order: 1; }
    .split.days-first > .side { order: -1; }
    .split .strip-wrap + .strip-wrap { margin-top: calc(16px - 8px * var(--squeeze, 0)); }
    .split .main > .footer { margin-top: auto; padding-top: calc(12px - 6px * var(--squeeze, 0)); }
    .split > .side > .days { padding: 0 0 0 24px; border: 0; border-left: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
    .split > .side.after > .days, .split > .side.before > .days { padding-top: 0; padding-bottom: 0;
                                                                   border-top: 0; border-bottom: 0; }
    .split.days-first > .side > .days { padding: 0 24px 0 0; border-left: 0; border-right: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
    /* With the room of a column of their own, the days in a size up: HA's large (16) for name and
       price, medium (14) for the rest */
    .split > .side .day-name, .split > .side .day-mean { font-size: var(--ha-font-size-l, 16px); line-height: 24px; }
    .split > .side .ref-kind { font-size: var(--ha-font-size-s, 12px); }
    .split > .side .day-info, .split > .side .day-vs { font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
    .split > .side .day-min, .split > .side .day-max { font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
    .split > .side .day-track { height: 12px; margin: 0 52px; }
    .split > .side .day-row { row-gap: 10px; }
    /* With the days beside them, the strips' labels a size up too, like the days (HA's sizes);
       columns as wide as their widest text (e.g. "↑ 17:00"), bars and spans a little wider */
    .strip.hours { --col-min: 52px; }
    .strip { --bar-w: 24px; --span-w: 16px; --day-h: 20px; --name-h: 20px; --label-h: 16px; }
    .day { font-size: var(--ha-font-size-m, 14px); }
    .day.start { font-size: var(--ha-font-size-l, 16px); }
    .chip { font-size: var(--ha-font-size-s, 12px); line-height: 18px; }
    .name { font-size: var(--ha-font-size-m, 14px); }
    .range, .extreme { font-size: var(--ha-font-size-s, 12px); }
  }
  /* Very wide: room for the prices a size up too (narrower, 48 hours leave them none) */
  @container card (min-width: 1200px) {
    .strip { --value-h: 22px; }
    .value { font-size: var(--ha-font-size-l, 16px); }
  }
  /* Wider still: the labels one more size (still HA's). Not the prices: 48 hours side by side
     leave them no room for more (e.g. "29,12" in cents) */
  @container card (min-width: 1600px) {
    .strip.hours { --col-min: 60px; }
    .strip { --bar-w: 28px; --span-w: 18px; --name-h: 22px; --label-h: 18px; }
    .name { font-size: var(--ha-font-size-l, 16px); }
    .range, .extreme { font-size: var(--ha-font-size-m, 14px); }
  }
  /* One line: the legend button and the unit. The button looks no taller than the text, but
     its touch target is 48 px (Material) / 44 pt (Apple): it reaches into the space around */
  .footer { display: flex; align-items: center; justify-content: space-between; min-height: 16px; margin-top: calc(12px - 6px * var(--squeeze, 0));
            font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); }
  .footer .unit { margin-left: auto; white-space: nowrap; }
  /* The card's action as a button of its own: it looks like a small text button (28 px), but
     its touch target is 48 px high like the legend button's, the invisible ::after reaching
     into the space around it */
  ${ACTION_BUTTON_STYLE}
  .action-button { z-index: 1; margin: -6px -8px -6px 12px; padding: 0 8px; }
  .footer .legend-button + .action-button { margin-left: auto; }
  .card-head, .card-foot { display: flex; justify-content: flex-end; }
  /* The title, styled like HA's card header (its theme variables), on its row's left */
  .card-title { flex: 1 1 auto; min-width: 0; margin: 0 auto 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                color: var(--ha-card-header-color, var(--primary-text-color));
                font-family: var(--ha-card-header-font-family, inherit);
                font-size: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
                font-weight: var(--ha-font-weight-normal, 400); letter-spacing: -0.012em; line-height: 32px; }
  .card-head:has(.card-title) { align-items: center; margin: -4px 0 calc(12px - 4px * var(--squeeze, 0)); }
  .switch > .card-title { margin-right: 12px; }
  /* The button's own line reaches into the card's padding: the text keeps its distance from the
     edge, the line costs only about 20 px */
  .card-head { margin: -8px 0 0; }
  .card-foot { margin: 0 0 -8px; }
  /* Compact: in the switch's line, at its left */
  .switch > .action-button { margin: 0 auto 0 -8px; }
  /* Shown only while focused by keyboard, like a skip link */
  .action-button.focus-only { position: absolute; top: 8px; left: 8px; z-index: 2; margin: 0; min-height: 36px; padding: 0 12px;
                              background: var(--ha-card-background, var(--card-background-color, #fff));
                              box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25); clip-path: inset(50%); opacity: 0; }
  .action-button.focus-only:focus { clip-path: none; opacity: 1; }
  .legend-button { position: relative; z-index: 1; display: inline-flex; align-items: center; gap: 6px;
                   min-width: 48px; min-height: 48px; margin: -16px 0 -16px -12px; padding: 0 12px; border: 0;
                   border-radius: 24px; background: none; cursor: pointer; font: inherit; color: inherit;
                   touch-action: manipulation; -webkit-tap-highlight-color: transparent; -webkit-touch-callout: none; --mdc-icon-size: 18px; }
  .legend-button:hover { color: var(--primary-text-color); }
  .legend-button:focus-visible { outline: var(--focus-ring); outline-offset: -6px; }
  ${WINDOW_STYLE}
  /* From 720 px on, the legend uses two columns (see the entries below) */
  @media (min-width: 720px) {
    .groups { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); column-gap: 32px; }
    .groups > .group + .group { margin-top: 0; padding-top: 0; border-top: 0; }
    .entries.pairs { grid-template-columns: 1fr 1fr; column-gap: 32px; }
    .entries.pairs > .row-start { grid-column: 1; }
  }
  .entries { display: grid; row-gap: 16px; margin: 0; padding: 0; list-style: none; }
  .entries + .entries { margin-top: 16px; }
  /* Detail card: one column like HA's more-info dialog. Price and level on top, the zoomed-in
     chart, a few sentences, the facts as label and value, and quietly at the end the legend */
  dialog:has(.detail) { width: min(480px, calc(100vw - 32px)); }
  .detail { display: grid; row-gap: 16px; padding-top: 4px; }
  .hero { display: flex; flex-wrap: wrap; align-items: baseline; column-gap: 6px; row-gap: 8px; }
  /* "Now", "Today", "Tomorrow": a badge first on the price line (not in the title, which would
     wrap); what's running now in the tint of the "now" column */
  .badge { height: 24px; padding: 0 10px; border-radius: 12px; white-space: nowrap;
           font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-bold, 600); line-height: 24px;
           color: var(--primary-text-color); background: rgba(127, 127, 127, 0.15); }
  .badge.now { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.18); }
  /* "Now" is live: its badge with the pulsing dot */
  .badge.live { display: inline-flex; align-items: center; gap: 6px; }
  ${LIVE_DOT_STYLE}
  .hero-kind, .hero-unit { font-size: var(--ha-font-size-m, 14px); color: var(--secondary-text-color); }
  .hero-message { font-size: var(--ha-font-size-2xl, 24px); line-height: 32px; }
  .hero-price { font-size: 40px; line-height: 44px; font-weight: var(--ha-font-weight-normal, 400);
                font-variant-numeric: tabular-nums; letter-spacing: -0.5px; }
  /* Badges left and the level right above the price, so a narrow window never breaks the price line */
  .hero-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: -8px; }
  .level-chip { display: inline-flex; align-items: center; gap: 6px; margin-left: auto;
                height: 24px; padding: 0 10px; border-radius: 12px; white-space: nowrap;
                font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
                background: rgba(127, 127, 127, 0.15); background: color-mix(in srgb, var(--level) 20%, transparent); }
  .hero-sub { margin: -12px 0 0; font-size: var(--ha-font-size-m, 14px); line-height: 20px; color: var(--secondary-text-color); }
  /* "Now": what the big number is, said above it */
  .hero-caption { margin-bottom: -14px; font-size: var(--ha-font-size-s, 12px); line-height: 16px;
                  font-weight: var(--ha-font-weight-medium, 500); color: var(--secondary-text-color); }
  /* The block's average and the day's, each in a tile of its own: clearly not the price now */
  .tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .tile { padding: 10px 12px; border-radius: 12px; border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
  .tile-label { font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); }
  .tile-value { display: flex; align-items: center; gap: 6px; margin-top: 2px; font-size: var(--ha-font-size-l, 16px);
                line-height: 22px; font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums;
                white-space: nowrap; }
  .tile-level { display: flex; align-items: center; gap: 6px; margin-top: 2px; font-size: var(--ha-font-size-s, 12px);
                line-height: 16px; font-weight: var(--ha-font-weight-medium, 500); }
  .tile.placeholder { border-style: dashed; }
  .tile.placeholder .tile-value { color: var(--secondary-text-color); }
  .tile-note { margin-top: 2px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); }
  /* Whether a best or peak price period runs now, or when the next best one begins */
  .status { display: grid; gap: 6px; }
  .status-line { padding: 8px 12px; border-radius: 8px; border-left: 3px solid var(--line);
                 font-size: var(--ha-font-size-m, 14px); line-height: 20px;
                 background: rgba(127, 127, 127, 0.1); background: color-mix(in srgb, var(--line) 14%, transparent); }
  .status-line.best { --line: var(--success-color, #43a047); }
  .status-line.peak { --line: var(--error-color, #db4437); }
  .status-line.upcoming { background: none; border-left-width: 2px; color: var(--secondary-text-color); }
  .prose { margin: 0; font-size: var(--ha-font-size-m, 14px); line-height: 21px; }
  /* The way to all values: a row like HA's links to a view of their own */
  .values-link { display: flex; align-items: center; justify-content: space-between; gap: 16px; width: 100%;
                 min-height: 48px; margin: 0; padding: 0 4px 0 0; border: 0; border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2));
                 background: none; cursor: pointer; font: inherit; font-size: var(--ha-font-size-m, 14px);
                 font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color); text-align: left;
                 touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
  .values-link svg { width: 24px; height: 24px; flex: none; fill: var(--secondary-text-color); }
  .values-link:hover svg { fill: var(--primary-text-color); }
  .values-link:focus-visible { outline: var(--focus-ring); outline-offset: 2px; border-radius: 4px; }
  /* All values: like HA's "Details" of an entity, a heading per section over a framed list */
  .values { display: grid; row-gap: 24px; padding-top: 12px; }
  .values h3 { margin: 0 0 12px; font-size: var(--ha-font-size-l, 16px); line-height: 24px;
               font-weight: var(--ha-font-weight-bold, 600); }
  .values .facts { padding: 0 16px; border-radius: var(--ha-card-border-radius, 12px);
                   border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
  .values .facts > div:first-child { border-top: 0; }
  .dialog-subtitle { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--ha-font-size-m, 14px);
                     line-height: 20px; color: var(--secondary-text-color); }
  .facts { margin: 0; }
  .facts > div { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; padding: 10px 0;
                 border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2));
                 font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
  .facts dt { color: var(--secondary-text-color); }
  .facts dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
  /* The zoom: bars as in the hour strip, on a quiet panel */
  .zoom { margin: 0; padding: 8px 8px 10px; border-radius: 12px; background: rgba(127, 127, 127, 0.07); }
  .zplot { display: flex; gap: 6px; }
  .zcol { position: relative; flex: 1 1 0; min-width: 0; display: grid; justify-items: center; row-gap: 4px;
          grid-template-rows: 16px 112px 14px 14px 3px; padding: 6px 0; border-radius: 10px; }
  .zcol.current { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  /* An hour that opens its own details */
  .zcol.drill, .zcol[data-pick] { cursor: pointer; -webkit-tap-highlight-color: transparent; touch-action: manipulation; }
  .zcol.drill:hover, .zcol[data-pick]:hover { background: rgba(127, 127, 127, 0.12); }
  .zcol.drill.current:hover, .zcol[data-pick].current:hover { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.2); }
  .zcol.drill:focus-visible, .zcol[data-pick]:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  /* A picked quarter hour: ringed, its line below the chart */
  .zcol.is-picked { box-shadow: inset 0 0 0 2px var(--primary-text-color); }
  .zpick { margin-top: -8px; padding: 0 4px; min-height: 20px; font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
  .zpick-hint { font-size: var(--ha-font-size-s, 12px); color: var(--secondary-text-color); }
  .zpick-head { display: flex; flex-wrap: wrap; align-items: center; column-gap: 12px; }
  .zpick-price { font-weight: var(--ha-font-weight-medium, 500); font-variant-numeric: tabular-nums; }
  .zpick-level { display: inline-flex; align-items: center; gap: 6px; font-size: var(--ha-font-size-s, 12px); }
  .zpick-notes { margin-top: 2px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); }
  .zcol.past > :not(.zgraph) { opacity: 0.45; }
  .zvalue { font-size: var(--ha-font-size-s, 12px); line-height: 16px; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .zgraph { position: relative; isolation: isolate; width: 100%; }
  .zbar { position: absolute; bottom: 0; left: 50%; width: min(32px, 70%); transform: translateX(-50%); border-radius: 4px;
          box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  /* Not known yet: an empty, dashed slot */
  .zcol.missing .zgraph::after { content: ""; position: absolute; bottom: 0; left: 50%; width: min(32px, 70%); height: 40%;
                                 transform: translateX(-50%); box-sizing: border-box; border-radius: 4px; opacity: 0.6;
                                 border: 1.5px dashed var(--secondary-text-color); }
  .zcol.missing .zvalue { color: var(--secondary-text-color); }
  .zcol:first-child .ref { left: 0; }
  .zcol:last-child .ref { right: 0; }
  /* The day's line off the chart: quiet, at the right edge, at the top or the bottom */
  /* (Outside the last column, in room of its own, so a ring around a picked or focused column
     never covers it) */
  .zoom.ref-off .zplot, .zoom.ref-off .zbands { padding-right: 14px; }
  .zref-off { position: absolute; right: -17px; width: 12px; height: 12px; line-height: 0; opacity: 0.75; }
  .zref-off.up { top: -4px; }
  .zref-off.down { bottom: -4px; }
  .zref-off svg { width: 12px; height: 12px; overflow: visible; }
  .zref-off .arrow { fill: var(--secondary-text-color); }
  .zref-off .dash { stroke: var(--secondary-text-color); stroke-width: 1.5; stroke-dasharray: 3 2; fill: none; }
  .swatch .zref-off.swatch-ref-off { position: static; }
  .zmark { font-size: var(--ha-font-size-s, 12px); line-height: 14px; font-weight: var(--ha-font-weight-bold, 600); }
  .zmark .low { color: var(--success-color, #43a047); }
  .zmark .high { color: var(--error-color, #db4437); }
  .zlabel { font-size: var(--ha-font-size-s, 12px); line-height: 14px; white-space: nowrap; color: var(--secondary-text-color); }
  .zcol.current .zlabel { color: var(--primary-text-color); font-weight: var(--ha-font-weight-bold, 600); }
  /* A whole day: narrow bars, a label every third hour, the parts of the day below */
  .dense .zplot { gap: 2px; }
  .dense .zcol { grid-template-rows: 96px 12px 12px 3px; padding: 4px 0; border-radius: 4px; }
  .dense .zbar { width: 80%; border-radius: 2px; }
  /* A whole day: the hovered (or focused) hour's price on top of its bar, at once */
  .dense .zbar::after { content: attr(data-label); position: absolute; bottom: calc(100% + 4px); left: 50%;
                        transform: translateX(-50%); padding: 0 4px; border-radius: 4px; white-space: nowrap;
                        font-size: var(--ha-font-size-xs, 10px); line-height: 16px; font-weight: var(--ha-font-weight-bold, 600);
                        font-variant-numeric: tabular-nums; color: var(--primary-text-color); background: var(--fade-bg);
                        box-shadow: 0 0 0 1px var(--divider-color, rgba(127, 127, 127, 0.3)); pointer-events: none; visibility: hidden; }
  .dense .zbar.tall::after { bottom: auto; top: 4px; }
  .dense .zcol:hover .zbar::after, .dense .zcol:focus-visible .zbar::after, .dense .zcol.is-scrubbed .zbar::after { visibility: visible; }
  .dense .zcol:hover, .dense .zcol:focus-visible, .dense .zcol.is-scrubbed { z-index: 2; }
  .dense .zcol.is-scrubbed { background: rgba(127, 127, 127, 0.12); }
  /* A finger held on the chart reads it: no text selection, no callout */
  .zoom.dense { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
  .dense .zmark { font-size: var(--ha-font-size-xs, 10px); line-height: 12px; }
  .dense .zlabel { font-size: var(--ha-font-size-xs, 10px); line-height: 12px; overflow: visible; }
  .dense .mark { width: 100%; }
  .zbands { display: flex; gap: 2px; margin-top: 6px; }
  .zbands span { min-width: 0; height: 24px; border-radius: 4px; overflow: hidden; white-space: nowrap; text-align: center;
                 font-size: var(--ha-font-size-xs, 10px); line-height: 24px; color: var(--secondary-text-color);
                 background: rgba(127, 127, 127, 0.12); }
  .zbands span:nth-child(even) { background: rgba(127, 127, 127, 0.22); }
  /* A part of the day that opens its own details */
  .zbands span[data-drill] { cursor: pointer; -webkit-tap-highlight-color: transparent; touch-action: manipulation; }
  .zbands span[data-drill]:hover { color: var(--primary-text-color); background: rgba(127, 127, 127, 0.32); }
  .zbands span[data-drill]:focus-visible { outline: var(--focus-ring); outline-offset: 1px; }
  /* ‹ › in the header: to the time before or after */
  .dialog-head .nav { width: 48px; height: 48px; padding: 0; border: 0; border-radius: 50%; background: none; cursor: pointer;
                      display: inline-flex; align-items: center; justify-content: center; color: var(--primary-text-color);
                      touch-action: manipulation; }
  .dialog-head .nav svg { width: 24px; height: 24px; fill: currentColor; }
  .dialog-head .nav:hover:not(:disabled) { background: rgba(127, 127, 127, 0.12); }
  .dialog-head .nav:disabled { opacity: 0.3; cursor: default; }
  .dialog-head .nav:focus-visible { outline: var(--focus-ring); outline-offset: -4px; }
  /* "Now" / "Today": a small text button before ‹ ›, its touch target 48 px high */
  .dialog-head .nav-now { position: relative; height: 32px; margin-right: 4px; padding: 0 12px; border-radius: 16px; cursor: pointer;
                          border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.3)); background: none; font: inherit;
                          font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
                          color: var(--primary-text-color); white-space: nowrap; touch-action: manipulation; }
  .dialog-head .nav-now::after { content: ""; position: absolute; inset: -8px -2px; }
  .dialog-head .nav-now:hover:not(:disabled) { background: rgba(127, 127, 127, 0.12); }
  .dialog-head .nav-now.here { visibility: hidden; }
  .dialog-head .nav-now:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  .dialog-head:has(.nav) { padding-right: 8px; }
  /* A detail card's title may take two lines next to ‹ › rather than be cut off */
  .dialog-head:has(.nav) h2 { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; white-space: normal;
                              font-size: 20px; line-height: 24px; padding: 8px 0; }
  /* The way to the whole legend: quiet, still a full touch target */
  .legend-link { display: inline-flex; align-items: center; gap: 8px; justify-self: start; min-height: 48px;
                 margin: -8px 0 -16px -12px; padding: 0 12px; border: 0; border-radius: 24px; background: none;
                 cursor: pointer; font: inherit; font-size: var(--ha-font-size-s, 12px);
                 color: var(--secondary-text-color); touch-action: manipulation; --mdc-icon-size: 18px; }
  .legend-link:hover { color: var(--primary-text-color); background: rgba(127, 127, 127, 0.08); }
  .legend-link:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  .group + .group, .groups + .group { margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
  .group h3 { margin: 0 0 12px; font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
              line-height: 16px; color: var(--secondary-text-color); }
  .entry { display: grid; grid-template-columns: 48px 1fr; column-gap: 16px; align-items: start; }
  .swatch { position: relative; height: 32px; display: flex; align-items: center; justify-content: center; }
  .swatch .graph { width: 24px; height: 32px; min-height: 0; }
  .swatch .ref { left: 0; right: 0; }
  .swatch .line { width: 24px; height: 3px; border-radius: 2px; }
  .swatch .mini-track { position: relative; width: 44px; height: 8px; }
  .swatch .mini-track > span { position: absolute; top: 0; bottom: 0; border-radius: 3px; box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  /* Swatches of the day markers with their line, as on the span */
  .swatch .mini-pointer::after, .swatch .mini-now::after { content: ""; position: absolute; left: -1px; width: 2px; height: 10px; }
  .swatch .mini-pointer::after { bottom: 0; background: var(--primary-text-color); }
  .swatch .mini-now::after { top: 0; left: -2px; width: 4px; box-sizing: border-box; background: var(--primary-color, #03a9f4);
                             border: solid var(--ha-card-background, var(--card-background-color, #fff)); border-width: 0 1px; }
  .swatch .mini-pointer { position: relative; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent;
                          border-bottom: 6px solid var(--primary-text-color); }
  .swatch .mini-now { position: relative; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent;
                      border-top: 6px solid var(--primary-color, #03a9f4); }
  /* One day round from 06:00, split into its parts in alternating shades */
  .swatch .timeline { display: flex; width: 44px; height: 8px; border-radius: 4px; overflow: hidden; }
  .swatch .timeline span:nth-child(odd) { background: var(--secondary-text-color); opacity: 0.6; }
  .swatch .timeline span:nth-child(even) { background: var(--secondary-text-color); opacity: 0.25; }
  .nowrap { white-space: nowrap; }
  .swatch .levels { display: flex; gap: 2px; }
  .swatch .levels span { width: 8px; height: 20px; border-radius: 2px; box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  .swatch .mini-col { display: flex; align-items: flex-end; justify-content: center; width: 24px; height: 32px;
                      box-sizing: border-box; padding-bottom: 4px; border-radius: 6px; }
  .swatch .mini-col > span { width: 12px; height: 60%; border-radius: 3px; box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12); }
  .swatch .mini-col.now { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12); }
  .swatch .mini-col.past > span { opacity: 0.45; }
  .swatch .mini-col.missing > span { height: 40%; box-sizing: border-box; box-shadow: none; opacity: 0.6;
                                     border: 1.5px dashed var(--secondary-text-color); }
  .swatch .extreme { font-size: var(--ha-font-size-m, 14px); line-height: 20px; height: auto; }
  .entry-title { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); line-height: 20px; }
  .entry-text { font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); }
  .level-names { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 4px; }
  .level-names span { display: inline-flex; align-items: center; white-space: nowrap; }
  .ref-kind { font-size: var(--ha-font-size-xs, 10px); font-weight: var(--ha-font-weight-normal, 400);
              color: var(--secondary-text-color); }
  .empty { color: var(--secondary-text-color); }
  .panels { flex: 1; display: grid; }
  .panel { grid-area: 1 / 1; min-width: 0; display: flex; flex-direction: column; }
  /* The footer sits at the same spot in every section, whatever its height */
  .panel > .footer:last-child { margin-top: auto; padding-top: calc(12px - 6px * var(--squeeze, 0)); }
  /* Compact: every section fills the same area; the days spread evenly over that height
     instead of clinging to the top */
  .is-compact .panel > .days { flex: 1; align-content: space-evenly; row-gap: 12px; }
  .panel.inactive { visibility: hidden; }
  .switch { display: flex; align-items: center; justify-content: flex-end; margin-bottom: calc(8px - 4px * var(--squeeze, 0)); }
  .switch [role="group"] { display: inline-flex; padding: 2px; border-radius: 18px; background: rgba(127, 127, 127, 0.15); }
  .switch [role="group"] button { display: inline-flex; align-items: center; gap: 6px; min-height: 32px; padding: 0 14px;
                                  border: 0; border-radius: 16px; background: none; cursor: pointer; font: inherit;
                                  font-size: var(--ha-font-size-s, 12px); color: var(--secondary-text-color); --mdc-icon-size: 18px; }
  .switch [role="group"] button.active { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.2); color: var(--primary-text-color); }
  /* "Now": the current price and what to make of it. On top of the forecast card as a line of
     its own (now-head), and the now card's three styles */
  .now-block { position: relative; color: var(--primary-text-color); border-radius: 12px; }
  .now-block[data-detail], .now-block[data-zone] { cursor: pointer; }
  .now-block[data-zone]:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  .now-block[data-detail]:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  @media (hover: hover) {
    .now-block[data-detail]:hover, .now-block[data-zone]:hover { background: rgba(127, 127, 127, 0.08); }
  }
  .now-mini { flex: none; display: block; }
  /* The trend: an icon in the corner, quiet (its name on hover) */
  .now-trend { position: absolute; top: 8px; right: 8px; display: flex; color: var(--secondary-text-color);
               opacity: 0.8; --mdc-icon-size: 18px; pointer-events: auto; }
  .now-head.has-trend { padding-right: 32px; }
  .now-gauge > .now-trend, .now-clock > .now-trend { top: 12px; right: 12px; }
  .now-tile > .now-trend { position: static; align-self: flex-start; margin-left: auto; }
  .now-mini svg, .dial svg { display: block; width: 100%; height: 100%; overflow: visible; }
  .now-value { font-weight: 500; font-variant-numeric: tabular-nums; }
  .now-unit { color: var(--secondary-text-color); font-size: 14px; font-weight: 400; }
  /* The level beside the price: its color as a dot, the word in the text color (yellow text on
     white would be unreadable) */
  .now-level { display: inline-flex; align-items: center; gap: 6px; padding: 1px 8px; border-radius: 10px;
               font-size: 12px; font-weight: 500; line-height: 18px; white-space: nowrap;
               background: color-mix(in srgb, var(--c) 18%, transparent); }
  .now-level::before, .dial-level::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--c); flex: none; }
  .now-verdict b, .now-line b { color: var(--primary-text-color); font-weight: 500; }

  /* The line on top: scale, price with level and verdict; the day's span beside it where wide */
  .now-head { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; padding: 8px; margin: -8px; }
  /* Its distance to what's above and below; in the narrow split the column's gap gives it */
  .now-row { margin-block: calc(16px - 6px * var(--squeeze, 0)); }
  .now-row:first-child, .card-head + .now-row, .switch + .now-row { margin-top: 0; }
  .now-row:last-child { margin-bottom: 0; }
  .split .now-row { margin-block: 0; }
  .now-head .now-mini { width: 44px; height: 44px; }
  .now-main { flex: 1 1 220px; min-width: 0; display: grid; gap: 2px; }
  .now-price { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; }
  .now-head .now-value { font-size: 24px; line-height: 30px; }
  .now-line { font-size: 13px; line-height: 18px; color: var(--secondary-text-color); }
  .now-span { flex: 1 1 200px; min-width: 0; max-width: 360px; display: grid; gap: 6px; }
  .now-span-bar { position: relative; height: 6px; border-radius: 3px; background: ${TRACK_COLOR}; }
  .now-span-ref { position: absolute; top: -4px; width: 2px; height: 14px; margin-left: -1px; border-radius: 1px;
                  background: var(--secondary-text-color); }
  .now-span-dot { position: absolute; top: 50%; width: 14px; height: 14px; border-radius: 50%; box-sizing: border-box;
                  transform: translate(-50%, -50%); background: var(--c); border: 2px solid var(--fade-bg); }
  .now-span-labels { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; line-height: 16px;
                     color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  /* Narrow: no room for the span beside the text, and below it would only repeat the scale */
  @container card (max-width: 519px) {
    .now-span { display: none; }
  }

  /* The now card: no padding of its own, each style brings what it needs */
  ha-card.is-now-card { padding: 0; overflow: hidden; }
  /* One row like HA's tile card: the scale where the tile has its icon */
  .now-tile { display: flex; align-items: center; gap: 10px; padding: 10px; height: 100%; box-sizing: border-box; }
  ha-card:not(.is-fixed) .now-tile { min-height: 56px; }
  .now-tile .now-mini { width: 36px; height: 36px; }
  .now-text { min-width: 0; display: grid; }
  .now-tile .now-value, .now-tile .now-unit { font-size: 14px; line-height: 20px; }
  .now-tile .now-value, .now-sub { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .now-sub { font-size: 12px; line-height: 16px; color: var(--secondary-text-color); }

  /* The scale and the clock: a square dial, as large as the card allows, text sized to it */
  .now-gauge, .now-clock { display: flex; flex-direction: column; align-items: center; gap: 8px; height: 100%;
                           box-sizing: border-box; padding: 12px 16px 14px; }
  .dial-box { width: 100%; display: flex; justify-content: center; }
  .dial { position: relative; width: min(100%, 260px); aspect-ratio: 1; container-type: inline-size; }
  /* A fixed height (rows in a sections view): the dial fills what the verdict leaves */
  ha-card.is-fixed .dial-box { flex: 1 1 0; min-height: 0; container-type: size; }
  ha-card.is-fixed .dial { width: min(100cqw, 100cqh); }
  .dial-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
                 justify-content: center; gap: 1cqw; text-align: center; pointer-events: none; }
  .dial-price { font-size: 15cqw; font-weight: 500; line-height: 1.05; letter-spacing: -0.01em;
                font-variant-numeric: tabular-nums; white-space: nowrap; }
  .dial-price small { margin-left: 1.5cqw; font-size: 5.6cqw; font-weight: 400; color: var(--secondary-text-color); }
  .dial-level { display: inline-flex; align-items: center; gap: 1.6cqw; font-size: 5.6cqw; font-weight: 500; }
  .dial-level::before { width: 3cqw; height: 3cqw; }
  .dial-sub { font-size: 5.2cqw; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  /* Low and high at the arc's ends, the average between them in its gap */
  .dial-end { position: absolute; top: 85%; transform: translateX(-50%); font-size: 5cqw; white-space: nowrap;
              color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  .dial-end.low { left: 21.7%; }
  .dial-end.high { left: 78.3%; }
  .dial-end.mid { left: 50%; top: 90%; }
  /* The clock's center is smaller: the hour numbers sit around it */
  .now-clock .dial-price { font-size: 11cqw; }
  .now-clock .dial-price small { display: block; margin: 0.5cqw 0 0; font-size: 4.4cqw; }
  .now-clock .dial-level { font-size: 4.4cqw; }
  .now-clock .dial-sub { font-size: 4.2cqw; }
  .now-clock svg text { font-family: inherit; }
  .now-verdict { flex: none; width: 100%; box-sizing: border-box; padding: 6px 10px; border-radius: 10px;
                 font-size: 13px; line-height: 18px; text-align: center; color: var(--secondary-text-color);
                 background: rgba(127, 127, 127, 0.08); }
  /* A fixed height: at most three lines, so the dial keeps its room */
  ha-card.is-fixed .now-verdict > span { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
  .now-verdict.best { background: color-mix(in srgb, var(--success-color, #43a047) 14%, transparent); }
  .now-verdict.peak { background: color-mix(in srgb, var(--error-color, #db4437) 12%, transparent); }
`;

// Editor fields both cards share (HA draws the form with its own selectors)
const dropdown = (options) => ({ select: { mode: "dropdown", options } });
// Options with the one in effect when nothing is set marked "(default)": the editor shows the
// value that applies, and which of them is the default
function marked(e, values, label, fallback) {
  return values.map((value) => ({
    value,
    label: value === fallback ? `${label(value)} (${e.default_mark})` : label(value),
  }));
}
const EDITOR_FIELDS = {
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

// The cards a card can show in a window, its options for it under their key: the element, its
// editor (a level down in the outer card's editor) and the icon of its row there
const WINDOW_CARDS = {
  forecast: {
    element: "tibber-prices-forecast-card",
    editor: "tibber-prices-forecast-card-editor",
    icon: "mdi:calendar-clock",
  },
  // (The chart card has no title of its own: its window says what it is)
  chart: {
    element: "tibber-prices-chart-card",
    editor: "tibber-prices-chart-card-editor",
    icon: "mdi:chart-line",
    title: (t) => t.chart.open,
  },
};

// Whether a card is the one in another card's window (it then stands alone: no other card on the
// tab counts it, it counts none)
function inCardWindow(element) {
  const root = element.getRootNode();
  return root instanceof ShadowRoot && root.host instanceof TibberPricesCardWindow;
}

/**
 * What the cards share: drawn once per frame when one of the home's entities changes, a forced
 * light or dark mode, the configured actions (tap, hold, double tap, like any HA card: the card
 * only reports which gesture happened, HA performs the action) and the other cards they show
 * in a window (see WINDOW_CARDS)
 */
class TibberPricesCardBase extends HTMLElement {
  // The cards this one shows in a window, `when` its config asks for it
  static windowCards = [];

  // The cards this one holds the options of, edited a level down
  static nestedCards(config) {
    return this.windowCards.filter((card) => card.when(config)).map(({ key }) => ({ key, ...WINDOW_CARDS[key] }));
  }

  set hass(hass) {
    this._hass = hass;
    if (this._window) this._window.hass = hass;
    if (!this._config) return;
    this._applyAppearance();
    // Resolved once per config (and again if the registry changes)
    if (!this._entities || this._registry !== hass.entities) {
      this._registry = hass.entities;
      this._entities = homeEntities(hass, this._config);
    }
    // Re-render only when one of our entities changed (state objects are replaced on change)
    const signature = Object.values(this._entities)
      .map((id) => hass.states[id])
      .concat(hass.language);
    if (this._signature && signature.every((value, i) => value === this._signature[i])) return;
    this._signature = signature;
    this._scheduleRender();
  }

  // A forced light or dark mode: its colors as variables on the card itself, so everything in
  // it follows, its windows included. Only when the page is in the other mode; checked again
  // when the theme or mode changes (HA then replaces hass.themes)
  _applyAppearance() {
    const themes = this._hass.themes || {};
    if (this._themes === themes) return;
    this._themes = themes;
    const { appearance } = this._config;
    const forced = appearance === "light" || appearance === "dark";
    const vars =
      forced && appearance !== (themes.darkMode ? "dark" : "light") ? modeVariables(themes, appearance) : null;
    for (const key of this._modeKeys || []) this.style.removeProperty(`--${key}`);
    this._modeKeys = vars ? Object.keys(vars) : [];
    for (const key of this._modeKeys) this.style.setProperty(`--${key}`, String(vars[key]));
    this.style.colorScheme = vars ? appearance : "";
  }

  // Every card is set up for a home
  static requireHome(config) {
    if (!config || !config.device_id) throw new Error("Pick your home (`device_id`)");
  }

  // A new config is drawn at once (its entities, their states and the theme looked at anew)
  _configApplied() {
    this._entities = undefined;
    this._signature = undefined;
    this._themes = undefined;
    if (this._hass) {
      this._applyAppearance();
      this._render();
    }
  }

  // Whether this card opens that one in a window: as its config asks (windowCards), and not
  // itself in another card's window (such a card stands alone)
  _opens(key) {
    const card = this.constructor.windowCards.find((item) => item.key === key);
    return Boolean(card && card.when(this._config)) && !inCardWindow(this);
  }

  // One render per frame: a data update writes the price sensor and both period sensors in a row
  _scheduleRender() {
    if (this._renderPending) return;
    this._renderPending = true;
    requestAnimationFrame(() => {
      this._renderPending = false;
      // (Taken off the page meanwhile, e.g. leaving the view: drawn when it comes back)
      if (this.isConnected) this._render();
    });
  }

  // Runs only what's configured: without a tap_action, HA would fall back to more info, but
  // like hold and double tap, tapping does nothing unless set
  _action(gesture) {
    if (!this._configured(gesture)) return;
    // "More info" and the like act on the entity set for it, else the home's price sensor
    const config = { ...this._config, entity: this._config.entity || (this._entities || {}).price };
    this.dispatchEvent(
      new CustomEvent("hass-action", { bubbles: true, composed: true, detail: { config, action: gesture } })
    );
  }

  // Whether a gesture (tap, hold, double_tap) has an action other than "none"
  _configured(gesture) {
    const action = this._config[`${gesture}_action`];
    return Boolean(action) && action.action !== "none";
  }

  // Whether the card runs an action at all (tap, hold or double tap not set to "none")
  _hasAction() {
    return ["tap", "hold", "double_tap"].some((gesture) => this._configured(gesture));
  }

  // Label of the card's action button: set in the config, or one that fits the tap action
  _actionText(t) {
    if (this._config.action_button_text) return this._config.action_button_text;
    const action = (this._config.tap_action || { action: "none" }).action;
    if (action === "more-info") return t.action_button["more-info"];
    if (action === "navigate" || action === "url") return t.action_button.open;
    return t.action_button.run;
  }

  /**
   * Tap, double tap and hold where `zone(event)` gives the element they're on (null: not the
   * card's gestures there): `tap(element)` runs a tap, the other two their actions. With a
   * double tap set, a tap waits for a second one; a hold keeps the click after it from tapping
   * and the browser's context menu from opening
   */
  _bindGestures(card, zone, tap) {
    let holdTimer;
    let held = false;
    let tapTimer;
    card.addEventListener("click", (event) => {
      const target = zone(event);
      if (!target) return;
      if (held) {
        held = false;
        return;
      }
      if (!this._configured("double_tap")) {
        tap(target);
      } else if (tapTimer) {
        clearTimeout(tapTimer);
        tapTimer = undefined;
        this._action("double_tap");
      } else {
        tapTimer = setTimeout(() => {
          tapTimer = undefined;
          tap(target);
        }, HOLD_DOUBLE_TAP.doubleTapMs);
      }
    });
    card.addEventListener("pointerdown", (event) => {
      if (!this._configured("hold") || !zone(event)) return;
      held = false;
      holdTimer = setTimeout(() => {
        held = true;
        this._action("hold");
      }, HOLD_DOUBLE_TAP.holdMs);
    });
    for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
      card.addEventListener(type, () => clearTimeout(holdTimer));
    }
    card.addEventListener("contextmenu", (event) => {
      if (this._configured("hold") && zone(event)) event.preventDefault();
    });
  }

  /**
   * Another card in a window, set up as under its key (`forecast`, `chart`) and used like that
   * card on its own, with this card's home. It opens no window of its own (see _opens), and the
   * window has the title
   */
  _openInWindow(key, opener) {
    if (!this._window) {
      this._window = document.createElement("tibber-prices-card-window");
      this.shadowRoot.append(this._window);
    }
    const options = this._config[key] || {};
    const t = stringsFor(this._hass);
    const { element, title } = WINDOW_CARDS[key];
    this._window.open({
      element,
      config: { ...options, device_id: this._config.device_id, show_title: false },
      title: title && !String(options.title || "").trim() ? title(t) : cardTitle(options, t),
      width: this._config.window_width || DEFAULTS.window_width,
      hass: this._hass,
      opener,
    });
  }

  /**
   * A short buzz: in Home Assistant's apps through their haptics (they listen for this event,
   * the iPhone's Taptic Engine included), in a browser through the vibration API where there is
   * one (Android; Safari has none)
   */
  _haptic(kind) {
    const app =
      window.externalApp ||
      (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.externalBus);
    if (app) window.dispatchEvent(new CustomEvent("haptic", { detail: kind }));
    // As the profile says ("Vibrate on interaction"), which the apps' haptics follow by themselves
    else if (navigator.vibrate && this._hass.vibrate !== false) navigator.vibrate(kind === "selection" ? 6 : 12);
  }
}

/**
 * tibber-prices-card-window: the window of a card in another card, unseen itself: only its
 * window shows, in the top layer, built like HA's dialogs (the close button left of the title,
 * full screen on phones). Escape, the button and a tap beside it close it, the focus goes back
 * to where it was opened from. The card in it is gone with the window, so no card updates unseen
 */
class TibberPricesCardWindow extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${CARD_WINDOW_STYLE}</style><dialog aria-labelledby="window-title"></dialog>`;
    trackKeyboard(this);
    const dialog = this.shadowRoot.querySelector("dialog");
    // A tap on the backdrop lands on the dialog itself; inside, it lands on its content
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog || event.target.closest(".close")) dialog.close();
    });
    dialog.addEventListener("close", () => {
      if (this._card) this._card.remove();
      this._card = undefined;
      if (this._opener && this._opener.isConnected) this._opener.focus();
    });
  }

  set hass(hass) {
    if (this._card) this._card.hass = hass;
  }

  open({ element, config, title, width, hass, opener }) {
    const dialog = this.shadowRoot.querySelector("dialog");
    const head = dialogHead({ id: "window-title", title, label: stringsFor(hass).legend.close });
    dialog.innerHTML = `${head}<div class="dialog-scroll"><div class="dialog-body window-body ${width}"></div></div>`;
    const card = document.createElement(element);
    card.setConfig(config);
    card.hass = hass;
    this._card = card;
    this._opener = opener;
    dialog.querySelector(".window-body").append(card);
    if (!dialog.open) dialog.showModal();
  }

  disconnectedCallback() {
    const dialog = this.shadowRoot.querySelector("dialog");
    if (dialog.open) dialog.close();
  }
}

class TibberPricesForecastCard extends TibberPricesCardBase {
  // The chart card, from the icon top right
  static windowCards = [{ key: "chart", when: (config) => Boolean(config.chart_button) }];

  setConfig(config) {
    TibberPricesCardBase.requireHome(config);
    validateConfig(config);
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
      assertConfig: validateConfig,
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
  static getConfigElement() {
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
    const stateObj = entities.price && this._hass.states[entities.price];
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
    const { zone, dateOf, weekday, clock, hourLabel: hourFormat } = homeCalendar(this._hass);
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
      clock,
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
      hourName: (time) => hourFormat.format(new Date(time)).replace(/\D+$/, ""),
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
      title: periodLabel(t, clock, running.kind, running.span[0], running.span[1]),
    };
    const context = { t, periods, now, nowPrice, today, unit, references, average, dateOf, extremes, clock };
    this._averageKind = averageKind;
    // What this card shows in its strips (all sections of a compact card), for the legends of
    // the other cards on the tab
    this._legendShows = { sections: [], marks: [] };
    const hourName = (block) => hourFormat.format(new Date(block.start)).replace(/\D+$/, "");
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
   * dot at the average, on one scale for the whole strip. The cheapest block from now on gets
   * a chip with how much cheaper it is than the block running now.
   */
  _strip(blocks, kind, naming, { t, periods, now, today, unit, references, average, dateOf, extremes, clock }) {
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
    const values = blocks.flatMap((b) => (ranged ? [b.price_min, b.price_max] : [b[key]]).concat(referenceOf(b)));
    const numbers = values.filter((v) => typeof v === "number");
    // Spans use the strip's own range, bars start a little below the lowest price: both like
    // temperatures in a weather forecast
    const low = ranged ? Math.min(...numbers) : barBaseline(numbers);
    // A few prices far above the rest (a spike tomorrow) would squash everything else flat: the
    // scale then ends a little above most prices, and what reaches beyond is cut off at the top
    // with a break mark (its number below says how high)
    const top = scaleTop(
      blocks.map((b) => (ranged ? b.price_max : b[key])),
      low,
      Math.max(...blocks.map(referenceOf).filter((v) => typeof v === "number"), low)
    );
    const span = top - low || 1;
    const format = priceFormatter(this._hass, numbers);
    const scale = (value) => Math.min(((value - low) / span) * 100, 100);
    // Bars and spans at the prices as shown: the same number, the same height (the price now and
    // the day's line keep their exact place)
    const place = (value) => scale(shownPrice(format, value));
    const cut = (value) => shownPrice(format, value) > top;
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
      if (ranged && typeof block.price_min === "number") {
        const bottom = place(block.price_min);
        graph = `
          <div class="span${cut(block.price_max) ? " cut" : ""}" style="bottom:${bottom}%;height:${place(block.price_max) - bottom}%;--c:${color}"></div>`;
        // The current price on the running part's span: a blue pointer on the left, facing the
        // median's on the right, kept on the span if the price lies just outside its range
        const nowPrice = this._renderInfo.nowPrice;
        const showNow = isNow && typeof nowPrice === "number" && !hide.has("now");
        const nowAt = showNow ? scale(Math.min(block.price_max, Math.max(block.price_min, nowPrice))) : undefined;
        const medianAt = place(block.price_median);
        // Where both lines would lie on top of each other, each pointer keeps half of the line,
        // on its own side, so the median's doesn't vanish under the current price's
        nearMedian = showNow && Math.abs(nowAt - medianAt) < NEAR_MEDIAN;
        const meets = nearMedian && !hide.has("pointer") ? " meets" : "";
        if (!hide.has("pointer")) {
          graph += `<div class="tick" style="bottom:${medianAt}%"></div>
          <div class="tick-line${meets}" style="bottom:${medianAt}%"></div>`;
        }
        if (showNow) {
          graph += `<div class="tick-now-line${meets}" style="bottom:${nowAt}%"></div><div class="tick-now" style="bottom:${nowAt}%"></div>`;
        }
      } else if (typeof block[key] === "number") {
        graph = `<div class="bar${cut(block[key]) ? " cut" : ""}" style="height:${Math.max(place(block[key]), 7)}%;--c:${color}"></div>`;
      }
      // A period running now: its mark stuck to the top right corner of the highlighted column
      // of now, taking no room (left out with `badge`)
      const active = isNow && !hide.has("badge") && this._renderInfo.activePeriod;
      const reference = referenceOf(block);
      if (typeof reference === "number" && !hide.has("reference")) {
        graph += `<div class="ref" style="bottom:${scale(reference)}%"></div>`;
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
      const chipAt = ranged ? place(block.price_max) : Math.max(place(block[key]), 7);
      const chipHtml = shownChip
        ? `<span class="chip" title="${chip.text}" style="bottom:min(calc(${chipAt}% + 4px), calc(100% - 16px))">${chip.chip}</span>`
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
          drawn.length ? ` title="${drawn.map((p) => periodLabel(t, clock, p.k, p.a, p.b)).join(" · ")}"` : ""
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
    // Opened from another view in the window: the way back to it instead of closing, as in HA's
    // more-info dialog
    const back = this._detailBack.length > 0;
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
    let gesture;
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
    zoom.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse" || event.button > 0) return;
      const held = (gesture = {
        id: event.pointerId,
        originX: event.clientX,
        originY: event.clientY,
        x: event.clientX,
        y: event.clientY,
        grabbed: false,
      });
      held.timer = setTimeout(() => {
        if (gesture !== held) return;
        held.grabbed = true;
        try {
          zoom.setPointerCapture(held.id);
        } catch (err) {
          // Pointer already gone
        }
        this._haptic("light");
        show(columnAt(held.x, held.y));
      }, CHART_HOLD_MS);
    });
    // Once held, the finger's moves are the chart's, not the page's
    zoom.addEventListener(
      "touchmove",
      (event) => {
        if (gesture && gesture.grabbed && event.cancelable) event.preventDefault();
      },
      { passive: false }
    );
    // A long press would open the context menu or select text
    zoom.addEventListener("contextmenu", (event) => event.preventDefault());
    zoom.addEventListener("pointermove", (event) => {
      if (!gesture || gesture.id !== event.pointerId) return;
      gesture.x = event.clientX;
      gesture.y = event.clientY;
      if (gesture.grabbed) {
        // (Between two columns: the last one stays)
        const column = columnAt(event.clientX, event.clientY);
        if (column) show(column, true);
      } else if (Math.hypot(event.clientX - gesture.originX, event.clientY - gesture.originY) > CHART_HOLD_SLOP_PX) {
        // Moved before the hold: no hold any more, a swipe or a scroll
        clearTimeout(gesture.timer);
      }
    });
    const end = (event, cancelled) => {
      if (!gesture || gesture.id !== event.pointerId) return;
      if (gesture.grabbed && !cancelled) {
        // Neither the swipe to another day nor the tap on an hour: this was reading
        event.stopPropagation();
        const swallow = (click) => click.stopPropagation();
        zoom.addEventListener("click", swallow, { capture: true, once: true });
        setTimeout(() => zoom.removeEventListener("click", swallow, true), 400);
      }
      clearTimeout(gesture.timer);
      gesture = undefined;
      show(undefined);
    };
    zoom.addEventListener("pointerup", (event) => end(event, false));
    zoom.addEventListener("pointercancel", (event) => end(event, true));
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

  _nowView(live, { format, block, ranged, reference, sub, section = ranged ? "day_parts" : "hours" }) {
    const { t, unit, clock, now, periods, average, averageKind, today, days, at } = this._renderInfo;
    // Each level beside the price it belongs to: the chip on top is this quarter hour's, the
    // tiles name the hour's (or part's) and the day's
    const day = days.find((d) => d.date === today);
    const language = this._hass.language;
    const n = t.detail.now;
    const formatNow = this._renderInfo.formatNowFor(section, format);
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
    const values = slots.map((s) => s.price).filter((v) => typeof v === "number");
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
    const scale = (value) => ((value - low) / span) * 100;
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
    const { zone, hourName } = this._renderInfo;
    const calendar = homeCalendar(this._hass);
    const noon = new Date(`${date}T12:00:00Z`);
    const [start, end] = dayBounds(date, zone);
    return {
      title: capitalize(calendar.dayMonth.format(noon)),
      weekday: capitalize(calendar.weekday.format(noon)),
      start,
      end,
      label: (slot) => (Number(hourName(slot.start)) % 3 === 0 ? hourName(slot.start) : ""),
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
    // The current price as this section shows it (its own decimals)
    const formatNow = formatNowFor(info.kind === "parts" ? "day_parts" : "hours", format);
    const language = this._hass.language;
    const d = t.details;
    const x = t.detail;
    const p = x.prose;
    const ranged = info.kind === "parts";
    const start = Date.parse(block.start);
    const end = Date.parse(block.end);
    const dayName = homeCalendar(this._hass).weekday.format(new Date(start));
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
    const chart = this._zoomChart(slots, {
      format,
      reference: info.reference,
      label: (slot, i, isNow) => (ranged ? hourName(slot.start) : isNow ? t.now : clock.format(new Date(slot.start))),
      drill: ranged ? (slot) => this._hourDetail(slot.start) : undefined,
      // A quarter hour of an hour can be picked: what it costs against the hour, the day and now
      pick: ranged ? undefined : { selected: picked },
    });
    // The pick changes only the chart's columns and this line, in place (see _pick)
    this._pickContext = ranged ? undefined : { slots, format, block, reference: info.reference, current };
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
      const values = { first: format(first), last: format(last), unit };
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
    const nowView = live ? this._nowView(live, { format, block, ranged, reference, sub: nowNote }) : {};
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
  _quarterLine(slot, { format, block, reference, current }) {
    const { t, unit, clock, now, average, averageKind, periods, extremes, quarters, dateOf, zone, nowPrice } =
      this._renderInfo;
    const language = this._hass.language;
    const pk = t.detail.pick;
    const vs = (template, base, baseFormat = format) => {
      const percent = percentFrom(language, slot.price, base, format, baseFormat);
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
          ? vs(pk.vs_now, nowPrice, this._renderInfo.formatNowFor("hours", format))
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

/**
 * tibber-prices-now-card: "now" on its own, for a main dashboard. The same engine as the
 * forecast card (its data, details windows, actions, light and dark), drawn in one of three
 * styles: `tile` (one row like HA's tile card), `gauge` (the price on the day's scale) or
 * `clock` (the coming twelve hours around a dial). A tap opens the details of now; set a tap
 * action (e.g. navigate to a dashboard with more) and a tap runs that instead.
 */
const NOW_STYLES = ["tile", "gauge", "clock"];
// What a tap opens (without a tap action): the details of now, or the forecast card or the chart
// card in a window, set up under `forecast` or `chart` like the card on its own (its home is the
// now card's)
const NOW_TAP_OPENS = ["details", "forecast", "chart"];
// What the now card can leave out (its scale and price are what it is)
const NOW_CARD_HIDES = SECTION_HIDES.now.filter((value) => value === "verdict" || value === "trend");
// How wide that window is (on phones it's full screen anyway): about HA's more-info dialog, a
// medium width (default), wide, or the whole screen
const WINDOW_WIDTHS = ["narrow", "medium", "wide", "full"];
const NOW_CARD_DEFAULTS = {
  style: "tile",
  price_unit: "auto",
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

class TibberPricesNowCard extends TibberPricesForecastCard {
  // What a tap opens (tap_opens), and the chart card from the icon top right
  static windowCards = [
    { key: "forecast", when: (config) => config.tap_opens === "forecast" },
    { key: "chart", when: (config) => config.tap_opens === "chart" || Boolean(config.chart_button) },
  ];

  setConfig(config) {
    TibberPricesCardBase.requireHome(config);
    validateNowConfig(config);
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
      assertConfig: validateNowConfig,
    };
  }

  static getStubConfig(hass) {
    return { device_id: firstHomeDevice(hass), style: NOW_CARD_DEFAULTS.style };
  }

  static getConfigElement() {
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
// The views a card can offer; yesterday only where asked for (in `views`, or in tomorrow's place
// until its prices are in: `tomorrow_pending: yesterday`)
const CHART_VIEWS = ["outlook", "yesterday", "today", "tomorrow", "two_days"];
const CHART_DEFAULT_VIEWS = ["outlook", "today", "tomorrow", "two_days"];
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
const CHART_SINGLE_DAY_VIEWS = ["yesterday", "today", "tomorrow"];
// What's above the curve: a line with the price and chips, a ring with the price in it (where it
// lies between the view's lowest and highest, in the area's color), or nothing
const CHART_HEADERS = ["chips", "dial", "none"];
// The unit with the prices, per place (`units: { header, tag, axis }`): the unit rate's (currency
// per kWh, e.g. ct/kWh), the currency alone (ct), or none. In the top line and the cursor's tag
// by default, at the price axis (small, above its numbers) only where asked for
const CHART_UNIT_DISPLAYS = ["full", "currency", "none"];
const CHART_UNIT_PLACES = { header: "full", tag: "full", axis: "none" };
// The price lines: how thick (px; 0: none), and how strong (percent of the text color; unset:
// the theme's divider color)
const CHART_GRID_WIDTH = 0.75;
// What a tap on the card's head opens (without a tap action): nothing, or the forecast card in a
// window (set up under `forecast`, its home the chart card's), as on the now card
const CHART_TAP_OPENS = ["nothing", "forecast"];
// How long the line above the curve takes to change over: quick, but no hard cut
const CHART_TWEEN_MS = 180;
const REDUCED_MOTION = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : undefined;
// The line where a day begins: a little thicker than the price lines
const CHART_DAY_LINE_WIDTH = 1;
// The shade off a day's line: how strong at the line (percent of the text color on light
// themes; on dark ones a sixth more, where a light tint on a dark card shows less than a dark one
// on light), and how far it reaches (hours of the view, 24 px at least)
const CHART_DAY_SHADE = { strength: 6, width: 2.5, dark: 7 / 6 };
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
const CHART_LINES = ["level", "average", "single"];
const CHART_FILLS = ["level", "average_shown", "average_day"];
const CHART_DEFAULT_STYLE = { line: "level", fill: "level", reference: true };
// When the top line shows the price's level and how far it lies from the average: always, only
// while prices are being read (the cursor moved off now at rest), or never; the level only at the
// levels listed (none listed: at all), the gap only from so many percent on
const CHART_CHIP_SHOWS = ["always", "reading", "never"];
const CHART_VIEW_DEFAULTS = {
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
const CHART_INHERIT = "inherit";
// A view's options in its editor panel (styles have their own block)
const CHART_VIEW_FIELDS = [
  "resolution",
  "hide",
  "header_level",
  "header_level_at",
  "header_delta",
  "header_delta_from",
];
// The views' panels in the editor, with the icons of the dashboard's chart tabs
const CHART_VIEW_ICONS = {
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
const CHART_COLOR_STATES = {
  line_colors: ["now", "single", "below", "above", ...LEVEL_STEPS],
  fill_colors: ["below", "above", ...LEVEL_STEPS],
  day_colors: ["yesterday", "today", "tomorrow"],
};
// The pills of the days (the one of now is in the color of now): yesterday faded, today neutral,
// tomorrow a calm violet, apart from now's blue and the levels' and average's colors
const CHART_DAY_COLORS = {
  yesterday: "var(--disabled-text-color, #bdbdbd)",
  today: "var(--secondary-text-color, #727272)",
  tomorrow: "var(--purple-color, #926bc7)",
};
// From the theme, so a theme of one's own carries over. Not its primary color: that blue marks
// now, here and in the other cards. One color: the text color (neutral, right in light and dark);
// below the average a calm teal (apart from now's blue and the best price's green); above it the
// warning color (apart from the peak price's red). The levels keep their colors, as in all cards
const CHART_THEME_COLORS = {
  // Now: the line, the label and the way back, in the blue of now in the other cards
  now: "var(--primary-color, #03a9f4)",
  single: "var(--primary-text-color, #212121)",
  below: "var(--teal-color, #009688)",
  above: "var(--warning-color, #ffa600)",
};
const CHART_MODES = ["light", "dark"];
const CHART_DEFAULTS = {
  views: [...CHART_DEFAULT_VIEWS],
  price_unit: "auto",
  average: "mean",
  appearance: "auto",
  tomorrow_pending: "placeholder",
  show_title: false,
  header: "chips",
};
// The outlook starts this long before now: what just happened, for comparison
const CHART_BEFORE_NOW_MS = 2 * HOUR_MS;
// A cursor set by touch or keyboard goes back to now after this long without use: time to read
// and compare, not left standing for good
const CHART_RETURN_MS = 30000;
// How far a touch moves sideways before it's a drag of the cursor (not a tap or a scroll)
const CHART_DRAG_PX = 6;
// How long a finger rests before it holds the pointer (then it may move in any direction), and
// how far it may wander meanwhile
const CHART_HOLD_MS = 350;
const CHART_HOLD_SLOP_PX = 8;
// How near the mouse comes to the switches in the chart's corner before they take precedence over
// the cursor's tag
const CHART_SWITCH_ZONE_PX = 24;
// mdi:restore, on the button back to now
const RESTORE_PATH =
  "M13,3A9,9 0 0,0 4,12H1L4.89,15.89L4.96,16.03L9,12H6A7,7 0 0,1 13,5A7,7 0 0,1 20,12A7,7 0 0,1 13,19C11.07,19 9.32,18.21 8.06,16.94L6.64,18.36C8.27,20 10.5,21 13,21A9,9 0 0,0 22,12A9,9 0 0,0 13,3Z";

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
function chartStyle(style) {
  return { ...CHART_DEFAULT_STYLE, ...(style || {}) };
}

// Whether a view's option is set: a list left empty counts as not set
function isSet(value) {
  return value !== undefined && value !== null && value !== "" && !(Array.isArray(value) && !value.length);
}

/**
 * A view's options, for the card and its editor alike: its own, else those for all views, else
 * the defaults (`all_views`: what a view without its own gets). A list left empty counts as not
 * set; the styles and their switch go together (a view with styles of its own switches between
 * those as it says)
 */
function chartViewOptions(config, view) {
  const own = view === "all_views" ? {} : config[view] || {};
  const all = config.all_views || {};
  const pick = (key) => (isSet(own[key]) ? own[key] : isSet(all[key]) ? all[key] : CHART_VIEW_DEFAULTS[key]);
  const stylesFrom = isSet(own.styles) ? own : isSet(all.styles) ? all : CHART_VIEW_DEFAULTS;
  return {
    ...Object.fromEntries(CHART_VIEW_FIELDS.map((key) => [key, pick(key)])),
    styles: stylesFrom.styles.map(chartStyle),
    style_switch: Boolean(stylesFrom.style_switch),
  };
}

function chartStyleId(style) {
  return `${style.line}.${style.fill}.${style.reference ? 1 : 0}`;
}

/**
 * The colors of lines and areas in light or dark: own ones from the config, else the theme's (one
 * color, below and above the average) or the level's usual one; the area's, unset, as the line's
 */
function chartColors(config, dark) {
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
const STYLE_ICON_STYLE = `
  .icon-line path { fill: none; stroke-width: 1.6; stroke-linejoin: round; }
  .icon-reference { stroke: var(--secondary-text-color); stroke-width: 1; stroke-dasharray: 2 1.5; }
`;

// A style as a small curve: four steps, two of them above the average, in its colors
function chartStyleIcon(style, colors) {
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

// A color from the config: [r, g, b] from the color picker, or any CSS color written in YAML
function cssColor(value) {
  if (Array.isArray(value) && value.length === 3 && value.every((n) => Number.isFinite(Number(n)))) {
    return `rgb(${value.map(Number).join(" ")})`;
  }
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

// Browser storage that may be missing (private mode, blocked site data): never fails
function storedValue(key) {
  try {
    return window.localStorage.getItem(key) || undefined;
  } catch (err) {
    return undefined;
  }
}

function storeValue(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (err) {
    // Only a convenience: the choice is just not remembered
  }
}

// A short fingerprint of a text (a card's config), for keys in browser storage
function hashText(text) {
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 33 + text.charCodeAt(i)) | 0;
  return (hash >>> 0).toString(36);
}

// The start of the local hour (or quarter hour) a moment falls in, in the home's time zone
function localFloor(time, size, zone) {
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
  }
  @container chart (max-width: 360px) {
    .price { font-size: 24px; }
    .chip { padding: 0 7px; font-size: 12px; }
    .segments button { font-size: 12px; padding: 0 10px; }
  }
`;

// A view's name, as on its tab
function chartViewName(t, view) {
  return t[view] || t.chart[view];
}

/**
 * The views a card shows: those listed (else the default ones), tomorrow before its prices are
 * in as set: with a note on when they come, not at all, or with yesterday standing in (unless
 * yesterday has a tab of its own), in time's order: before today, else where tomorrow was. With
 * `all`, everything the card can show (tomorrow and its stand-in: the editor's panels)
 */
function chartViews(config, { tomorrowKnown = false, all = false }) {
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
function chartStyleName(e, style) {
  const name = fill(e.style_name, { line: e[`style_line_${style.line}`], fill: e[`style_fill_${style.fill}`] });
  return style.reference ? `${name}${e.style_name_reference}` : name;
}

// What a style is called in the chart: its own name, else "Style 2" by its place
function chartStyleLabel(e, style, index) {
  const own = typeof style.name === "string" ? style.name.trim() : "";
  return own ? escapeHtml(own) : fill(e.style_number, { n: index + 1 });
}

class TibberPricesChartCard extends TibberPricesCardBase {
  // The forecast card, from a tap (tap_opens)
  static windowCards = [{ key: "forecast", when: (config) => config.tap_opens === "forecast" }];

  setConfig(config) {
    TibberPricesCardBase.requireHome(config);
    validateChartConfig(config);
    this._config = { ...CHART_DEFAULTS, ...config };
    // The view and style picked last, remembered per browser and card (by its config): each chart
    // card on a dashboard switches on its own
    const key = `tibber-prices-chart:${hashText(JSON.stringify(config))}`;
    this._viewKey = `${key}:view`;
    this._styleKey = `${key}:style`;
    this._view = storedValue(this._viewKey);
    this._cursor = undefined;
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

  // A view's options (see chartViewOptions), built once per config
  _viewOptions(view = this._view) {
    if (!this._viewCache.has(view)) this._viewCache.set(view, chartViewOptions(this._config, view));
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
    const views = chartViews(this._config, { tomorrowKnown: this._data.tomorrowKnown });
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
    controls.innerHTML = viewButtons;
    controls.hidden = !viewButtons;
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
    const stateObj = entities.price && this._hass.states[entities.price];
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
      // The quarter hours (start, step, prices, levels) on the data itself
      ...quarters,
      unit,
      // Prices in the subunit (ct, øre), not the base currency (€, kr)
      subunit: units ? unit === units.subunit : false,
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
    if (view === "two_days") return d.tomorrowKnown ? [d.todayStart, d.dayAfter] : [d.yesterdayStart, d.tomorrowStart];
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
    if (view === "tomorrow" && !d.tomorrowKnown) {
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
    if (!known.length) {
      this._geo = undefined;
      plot.innerHTML = `<div class="placeholder">${t.no_data}</div>`;
      return;
    }
    const values = known.map((slot) => slot.price);
    // The scale of the quarter hours in both resolutions (an hour's average lies within its
    // quarter hours'), over the stretch either shows (the outlook starts at the hour in hours):
    // switching between them leaves the axis where it is
    const scaleFrom = Math.min(this._span(view, "quarter_hour", now)[0], this._span(view, "hour", now)[0]);
    const scaleValues = this._slots(scaleFrom, to, "quarter_hour")
      .filter((slot) => slot.price !== null)
      .map((slot) => slot.price);
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
    const bottomRoom = 18 + (periodsShown ? 6 : 0) + (xTitle ? 14 : 0);
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
    const tickLabels = scale.ticks.map((v) => axisFormat(v));
    // Up the price axis, left of its numbers and read from the bottom up: its title and unit,
    // "Price (ct/kWh)", or either alone (where asked for)
    const axisUnit = this._unitShown("axis");
    const yLabel = yTitle && axisUnit ? `${t.chart.axis_price} (${axisUnit})` : yTitle ? t.chart.axis_price : axisUnit;
    // (Its line 11 px high around x = 8, then 8 px to the numbers, as between them and the plot)
    const gutter = yLabel ? 22 : 0;
    const left = gutter + Math.max(...tickLabels.map((label) => label.length)) * 6.5 + 8;
    const right = width - 2;
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
    const shownAverage = aggregate(values, d.averageKind);
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
    const base = scale.low < 0 && scale.high > 0 ? y(0) : bottom;
    for (const r of runsOf(paintOf(fillMode))) {
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
        `<text${midnight ? ' class="midnight"' : ""} x="${tx}" y="${height - 3 - (xTitle ? 14 : 0)}" text-anchor="middle">${d.hourLabel.format(new Date(time)).replace(/\D+$/, "")}</text>`
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
          return timeRange(d.clock, at, at + QUARTER_MS);
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
    layer.innerHTML = marks;
    // A best or peak price period the slot is in (or part of it)
    const period = slotPeriod(d.periods, slot.start, slot.end);
    if (pinned) this._drawCursorTag(layer, slot, cx, period);
    else this._tagShown = undefined;
    this._readout(slot, index, { live: index === g.nowIndex && !pinned, reading: pinned, period });
  }

  // The price of the quarter hour a moment falls in (null: not known)
  _quarterPrice(time) {
    const d = this._data;
    const i = Math.floor((time - d.start) / d.step);
    return i >= 0 && i < d.prices.length ? d.prices[i] : null;
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
    const when = `${timeRange(d.clock, slot.start, slot.end)}<tspan class="cursor-day"> · ${this._dayWord(d.dateOf(slot.start), slot.start)}</tspan>`;
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
    const range = timeRange(d.clock, slot.start, slot.end);
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
      period && (period.partial ? `${t[period.k]} ${timeRange(d.clock, period.start, period.end)}` : t[period.k]);
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
      this._chip(period.partial ? timeRange(d.clock, period.start, period.end) : t[period.k], {
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
    const chips = [gapChip, averageChip, levelChip, periodChip];
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
   * scrolls the page as usual, a tap sets the cursor (either goes back to now by itself). Mouse: it follows the pointer and a click keeps it there. Keyboard:
   * arrows by one slot, Page Up/Down by an hour or six, Home/End, Escape for now
   */
  _bindPlot(plot) {
    let gesture;
    const grab = (clientX) => {
      gesture.dragging = true;
      try {
        plot.setPointerCapture(gesture.id);
      } catch (err) {
        // Pointer already gone
      }
      plot.classList.add("is-dragging");
      this._haptic("light");
      this._hoverAt(clientX, false);
    };
    plot.addEventListener("pointerdown", (ev) => {
      if (!this._geo || ev.button > 0) return;
      clearTimeout(this._returnTimer);
      gesture = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, touch: ev.pointerType !== "mouse", dragging: false };
      if (!gesture.touch) {
        gesture.dragging = true;
        this._setCursor(this._indexAt(ev.clientX));
        return;
      }
      const held = gesture;
      held.timer = setTimeout(() => gesture === held && !held.dragging && grab(held.lastX ?? held.x), CHART_HOLD_MS);
    });
    // Once held, the finger's moves are the pointer's, not the page's: stopped before the page
    // scrolls (only possible before it began, which a finger held still hasn't)
    plot.addEventListener(
      "touchmove",
      (ev) => {
        if (gesture && gesture.touch && gesture.dragging && ev.cancelable) ev.preventDefault();
      },
      { passive: false }
    );
    // A long press would open the context menu or the text selection
    plot.addEventListener("contextmenu", (ev) => ev.preventDefault());
    plot.addEventListener("pointermove", (ev) => {
      if (!this._geo) return;
      if (gesture && gesture.id === ev.pointerId) {
        if (!gesture.touch) {
          this._setCursor(this._indexAt(ev.clientX));
          return;
        }
        gesture.lastX = ev.clientX;
        const dx = Math.abs(ev.clientX - gesture.x);
        const dy = Math.abs(ev.clientY - gesture.y);
        if (!gesture.dragging) {
          // Moving before the hold: sideways grabs at once; anything else is no hold any more
          if (dx > CHART_DRAG_PX && dx > dy) {
            clearTimeout(gesture.timer);
            grab(ev.clientX);
          } else if (Math.hypot(dx, dy) > CHART_HOLD_SLOP_PX) {
            clearTimeout(gesture.timer);
          }
          return;
        }
        this._hoverAt(ev.clientX, true);
        return;
      }
      if (ev.pointerType === "mouse") {
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
      }
    });
    const end = (ev, cancelled) => {
      if (!gesture || gesture.id !== ev.pointerId) return;
      const { touch, dragging, timer } = gesture;
      clearTimeout(timer);
      gesture = undefined;
      plot.classList.remove("is-dragging");
      if (!touch) return; // A click keeps the cursor until the pointer leaves
      if (dragging) {
        // Let go: the cursor stays where the finger left it, like after a tap
        if (this._hover !== undefined) this._cursor = this._hover;
        this._hover = undefined;
        this._drawCursor();
      } else if (!cancelled) {
        // A tap sets the cursor until the timer runs out
        this._setCursor(this._indexAt(ev.clientX));
      }
      this._scheduleReturn();
    };
    plot.addEventListener("pointerup", (ev) => end(ev, false));
    plot.addEventListener("pointercancel", (ev) => end(ev, true));
    plot.addEventListener("pointerleave", (ev) => {
      if (ev.pointerType !== "mouse" || gesture) return;
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
      assertConfig: validateChartConfig,
    };
  }

  // The form of a view's panel (or the one for all views): its resolution and what it leaves
  // out; a view's fields left empty are as for all views
  static viewSchema(target, inherited = CHART_VIEW_DEFAULTS) {
    const e = languageStrings(EDITOR_STRINGS);
    const own = target !== "all_views";
    const label = (value) => e[`resolution_${value}`];
    // A view: "as for all views" first (what that is, in brackets); all views: the default marked
    const resolutions = own
      ? [
          { value: CHART_INHERIT, label: fill(e.view_inherit_option, { value: label(inherited.resolution) }) },
          ...CHART_RESOLUTIONS.map((value) => ({ value, label: label(value) })),
        ]
      : marked(e, CHART_RESOLUTIONS, label, CHART_VIEW_DEFAULTS.resolution);
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
        : marked(e, CHART_CHIP_SHOWS, (value) => e[`chip_show_${value}`], CHART_VIEW_DEFAULTS[name]);
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
  static getConfigElement() {
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

/**
 * The cards' editors: Home Assistant's form for their options, showing the value that applies where
 * the config sets nothing (HA's own cards do, an empty field there means "none"), and saving only
 * what's changed: a value shown but never touched stays out of the config, so a better default
 * later reaches the card too. (HA's form hands back all values it shows, so the change is worked
 * out against what it showed.)
 */
function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// The config with `value` under `key`, or without the key where `value` is empty
function withKey(config, key, value) {
  const result = { ...config };
  if (value && Object.keys(value).length) result[key] = value;
  else delete result[key];
  return result;
}

// The defaults with the config over them, objects merged key by key (lists as a whole)
function withDefaults(defaults, config) {
  const merged = { ...defaults };
  for (const [key, value] of Object.entries(config || {})) {
    merged[key] = isPlainObject(value) && isPlainObject(defaults[key]) ? withDefaults(defaults[key], value) : value;
  }
  return merged;
}

// The config with what the form changed (next against what it showed); cleared fields go
function withChanges(config, shown, next) {
  const result = { ...(config || {}) };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  for (const key of new Set([...Object.keys(shown || {}), ...Object.keys(next || {})])) {
    const before = (shown || {})[key];
    const after = (next || {})[key];
    if (same(before, after)) continue;
    if (isPlainObject(after) && isPlainObject(before)) {
      const nested = withChanges(result[key], before, after);
      if (Object.keys(nested).length) result[key] = nested;
      else delete result[key];
    } else if (after === undefined || after === null || after === "") {
      delete result[key];
    } else {
      result[key] = after;
    }
  }
  return result;
}

// The editors' way a level down, into a card this one holds (and back), as HA's own stack editors
const NESTED_EDITOR_STYLE = `
  .nested { display: flex; flex-direction: column; gap: 8px; margin-top: 24px; }
  .nested:empty { display: none; }
  .nested-row { display: flex; align-items: center; gap: 16px; width: 100%; min-height: 56px; padding: 8px 12px 8px 16px;
                box-sizing: border-box; border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.3));
                border-radius: var(--ha-border-radius-md, 6px); background: none; font: inherit; text-align: left;
                color: var(--primary-text-color); cursor: pointer; }
  .nested-row:hover { background: rgba(127, 127, 127, 0.06); }
  .nested-row:focus-visible { outline: var(--focus-ring); outline-offset: 2px; }
  .nested-row ha-icon { color: var(--secondary-text-color); }
  .nested-row span { flex: 1; min-width: 0; }
  .nested-row b { display: block; font-size: 14px; font-weight: var(--ha-font-weight-medium, 500); }
  .nested-row small { display: block; font-size: 12px; line-height: 16px; color: var(--secondary-text-color); }
  .nested-row svg, .sub-head svg { width: 24px; height: 24px; flex: none; fill: currentColor; }
  .nested-row > svg { color: var(--secondary-text-color); }
  .sub-head { display: flex; align-items: center; gap: 8px; margin: -4px 0 16px -8px; }
  .sub-head button { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; padding: 0;
                     border: 0; border-radius: 50%; background: none; cursor: pointer; color: var(--primary-text-color); }
  .sub-head button:hover { background: rgba(127, 127, 127, 0.12); }
  .sub-head button:focus-visible { outline: var(--focus-ring); outline-offset: -2px; }
  .sub-title { font-size: 16px; font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color); }
`;

class TibberPricesFormEditor extends HTMLElement {
  // The card this edits (getConfigForm, configDefaults); set by each editor
  get _card() {
    return TibberPricesForecastCard;
  }

  setConfig(config) {
    this._config = config;
    // A level down: the card held there follows a change made elsewhere (the code editor)
    if (this._sub) {
      const options = { ...(config[this._sub.key] || {}), device_id: config.device_id };
      const { device_id: _device, ...shown } = this._sub.editor._config || {};
      const { device_id: _home, ...wanted } = options;
      if (JSON.stringify(shown) !== JSON.stringify(wanted)) this._sub.editor.setConfig(options);
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._sub) this._sub.editor.hass = hass;
    if (!this._form) this._render();
    else this._hassChanged(hass);
  }

  _hassChanged(hass) {
    this._form.hass = hass;
  }

  async _ensureForm() {
    // HA loads its form with its own editors; the tile card's brings it along
    if (!customElements.get("ha-form")) {
      const tile = customElements.get("hui-tile-card");
      if (tile && tile.getConfigElement) await tile.getConfigElement();
      await customElements.whenDefined("ha-form");
    }
  }

  // A form set up before it's in the page: it draws at once, and without a schema it fails
  _newForm(schema, data, onChange) {
    const form = document.createElement("ha-form");
    // (Built once per editor: the whole translated schema, for two functions)
    if (!this._formBase) this._formBase = this._card.getConfigForm();
    const base = this._formBase;
    form.schema = schema;
    form.computeLabel = base.computeLabel;
    form.computeHelper = base.computeHelper;
    form.hass = this._hass;
    form.data = data;
    form.addEventListener("value-changed", (ev) => {
      ev.stopPropagation();
      onChange(ev.detail.value);
    });
    return form;
  }

  // What the form shows: the defaults with the config over them
  _shown() {
    return withDefaults(this._card.configDefaults(), this._config);
  }

  async _render() {
    if (!this._hass || !this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      trackKeyboard(this);
      this.shadowRoot.innerHTML = `<style>${BASE_STYLE}${this._style()}${NESTED_EDITOR_STYLE}</style><div class="editor-main">${this._skeleton()}<div class="nested"></div></div><div class="editor-sub" hidden></div>`;
      this._bindNested();
      await this._ensureForm();
      this._shownData = this._shown();
      this._form = this._newForm(this._formSchema(), this._shownData, (value) =>
        this._changed(withChanges(this._config, this._shownData, value))
      );
      const after = this.shadowRoot.querySelector(".after-form");
      after.parentNode.insertBefore(this._form, after);
      this._setUp();
    }
    // (A call while the form is still loading: the first one sets it up with the latest values)
    if (!this._form) return;
    this._form.hass = this._hass;
    this._shownData = this._shown();
    this._form.data = this._shownData;
    this._update();
    this._renderNested();
  }

  // The fields of the form on top (an editor with panels of its own may keep some for the end);
  // a level down, without the home: it's the outer card's
  _formSchema() {
    const schema = this._card.getConfigForm().schema;
    return this._nested ? schema.filter((field) => field.name !== "device_id") : schema;
  }

  // ---- A level down: the editor of a card this one holds, in place of this one's

  // The cards held (not a level further down), a row each that opens its editor
  _renderNested() {
    const box = this.shadowRoot.querySelector(".nested");
    const e = languageStrings(EDITOR_STRINGS);
    const cards = this._nested || !this._card.nestedCards ? [] : this._card.nestedCards(this._config);
    const key = cards.map((card) => card.key).join(",");
    if (box.dataset.key === key) return;
    box.dataset.key = key;
    box.innerHTML = cards
      .map(
        (card) =>
          `<button type="button" class="nested-row" data-nested="${card.key}"><ha-icon icon="${card.icon}"></ha-icon><span><b>${e[`nested_${card.key}`]}</b><small>${e.nested_help}</small></span>${svgIcon(CHEVRON_RIGHT)}</button>`
      )
      .join("");
  }

  _bindNested() {
    this.shadowRoot.querySelector(".nested").addEventListener("click", (event) => {
      const row = event.target.closest("[data-nested]");
      if (row) this._openNested(row.dataset.nested);
    });
    this.shadowRoot.querySelector(".editor-sub").addEventListener("click", (event) => {
      if (event.target.closest(".sub-back")) this._closeNested();
    });
  }

  _openNested(key) {
    const card = (this._card.nestedCards(this._config) || []).find((item) => item.key === key);
    if (!card) return;
    const e = languageStrings(EDITOR_STRINGS);
    const sub = this.shadowRoot.querySelector(".editor-sub");
    sub.innerHTML = `<div class="sub-head"><button type="button" class="sub-back" aria-label="${e.nested_back}" title="${e.nested_back}">${svgIcon(BACK_PATH)}</button><span class="sub-title">${e[`nested_${key}`]}</span></div>`;
    const editor = document.createElement(card.editor);
    editor._nested = true;
    editor.addEventListener("config-changed", (event) => {
      // Its options go under its key, without the home (that's this card's)
      event.stopPropagation();
      const { device_id: _device, type: _type, ...options } = event.detail.config;
      this._changed(withKey(this._config, key, options), false);
    });
    editor.hass = this._hass;
    editor.setConfig({ ...(this._config[key] || {}), device_id: this._config.device_id });
    sub.append(editor);
    this._sub = { key, editor };
    this.shadowRoot.querySelector(".editor-main").hidden = true;
    sub.hidden = false;
    sub.querySelector(".sub-back").focus();
  }

  _closeNested() {
    const key = this._sub && this._sub.key;
    this._sub = undefined;
    const sub = this.shadowRoot.querySelector(".editor-sub");
    sub.hidden = true;
    sub.innerHTML = "";
    this.shadowRoot.querySelector(".editor-main").hidden = false;
    this._render();
    const row = key && this.shadowRoot.querySelector(`[data-nested="${key}"]`);
    if (row) row.focus();
  }

  _style() {
    return ":host { display: block; }";
  }

  _skeleton() {
    return '<div class="after-form"></div>';
  }

  // Hooks of an editor with more than the form
  _setUp() {}

  _update() {}

  _changed(config, redraw = true) {
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
    if (redraw) this._render();
  }
}

class TibberPricesForecastCardEditor extends TibberPricesFormEditor {}

class TibberPricesNowCardEditor extends TibberPricesFormEditor {
  get _card() {
    return TibberPricesNowCard;
  }
}

/**
 * The chart card's editor: Home Assistant's form for its options (the schema of getConfigForm),
 * then the own colors as a table, a row per state with a swatch for light and one for dark. A
 * swatch without an own color shows the one that applies, dashed; a click opens the system's
 * color picker, ✕ goes back to that color. Colors are written as hex (`#00b4d8`).
 */
const CHART_EDITOR_STYLE = `
  :host { display: block; }
  /* As HA's own panels of the form above (ha-form-expandable): 24 px apart, icon and padding alike */
  .views-panels, .colors { display: flex; flex-direction: column; gap: 24px; margin-top: 24px; }
  .end-form { display: block; margin-top: 24px; }
  ha-expansion-panel { display: block; --expansion-panel-content-padding: 0; border-radius: var(--ha-border-radius-md, 6px);
                       --ha-card-border-radius: var(--ha-border-radius-md, 6px); }
  ha-icon { color: var(--secondary-text-color); }
  .content { padding: 12px; }
  .help { margin: 0 0 12px; font-size: 13px; line-height: 18px; color: var(--secondary-text-color); }
  .text-button, .reset-all { display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px; border: 0; border-radius: 16px;
                             background: none; font: inherit; font-size: 14px; font-weight: var(--ha-font-weight-medium, 500);
                             cursor: pointer; color: var(--primary-color, #03a9f4); }
  .text-button:hover, .reset-all:hover { background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.08); }
  .reset-all { display: block; margin: 12px 0 0 auto; }
  /* The styles of a view: a row each, as the views' own form looks */
  .styles-block { container-type: inline-size; margin-top: 24px; }
  .styles-head { margin-bottom: 4px; font-size: 14px; font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color); }
  .inherited { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
  .chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px 4px 6px; border-radius: 14px; font-size: 13px;
          background: rgba(127, 127, 127, 0.12); color: var(--primary-text-color); }
  .chip svg, .preview svg { width: 33px; height: 21px; border-radius: 3px; overflow: hidden; flex: none; }
  ${STYLE_ICON_STYLE}
  .style-row { display: grid; grid-template-columns: auto 1fr 1fr auto; grid-template-areas: "preview line fill actions" ". name ref ref";
               gap: 8px 12px; align-items: end; padding: 12px 0; border-bottom: 1px solid var(--divider-color, rgba(127, 127, 127, 0.2)); }
  .style-row .preview { grid-area: preview; align-self: center; display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .style-row .default { font-size: 11px; color: var(--secondary-text-color); }
  .style-row .line { grid-area: line; }
  .style-row .fill { grid-area: fill; }
  .style-row .ref { grid-area: ref; align-self: center; }
  .style-row .style-name { grid-area: name; }
  .style-row .actions { grid-area: actions; display: flex; align-self: center; }
  .field { display: flex; flex-direction: column; gap: 4px; min-width: 0; font-size: 12px; color: var(--secondary-text-color); }
  .field input[type="text"] { box-sizing: border-box; width: 100%; height: 40px; padding: 0 10px; border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.3));
                               border-radius: 8px; font: inherit; font-size: 14px; color: var(--primary-text-color);
                               background: var(--card-background-color, #fff); }
  .field select { width: 100%; height: 40px; padding: 0 8px; border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.3));
                  border-radius: 8px; font: inherit; font-size: 14px; color: var(--primary-text-color);
                  background: var(--card-background-color, #fff); }
  .check { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--primary-text-color); cursor: pointer; }
  .check input, .switch-row input { width: 18px; height: 18px; margin: 0; accent-color: var(--primary-color, #03a9f4); }
  .icon-button { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; padding: 0; border: 0;
                 border-radius: 50%; background: none; cursor: pointer; color: var(--secondary-text-color); }
  .icon-button:hover:not(:disabled) { background: rgba(127, 127, 127, 0.12); }
  .icon-button:disabled { opacity: 0.3; cursor: default; }
  .icon-button svg { width: 20px; height: 20px; fill: currentColor; }
  .styles-foot { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-top: 8px; }
  .switch-row { display: flex; align-items: flex-start; gap: 10px; margin-top: 12px; cursor: pointer; }
  .switch-row b { display: block; font-size: 14px; font-weight: var(--ha-font-weight-normal, 400); color: var(--primary-text-color); }
  .switch-row small { display: block; font-size: 12px; line-height: 16px; color: var(--secondary-text-color); }
  .switch-row input { margin-top: 2px; }
  /* Narrower (the editor's dialog): line and area one below the other beside the preview; a phone:
     every field a row of its own */
  @container (max-width: 600px) {
    .style-row { grid-template-columns: auto 1fr auto; grid-template-areas: "preview line actions" ". fill ." ". name ." ". ref ."; }
  }
  @container (max-width: 380px) {
    .style-row { grid-template-areas: "preview . actions" "line line line" "fill fill fill" "name name name" "ref ref ref"; }
  }
  /* The colors: a table, a row per state */
  .table { display: grid; grid-template-columns: 1fr repeat(2, 56px); align-items: center; gap: 6px 12px; }
  .head { font-size: 12px; color: var(--secondary-text-color); text-align: center; }
  .name { font-size: 14px; color: var(--primary-text-color); }
  .cell { position: relative; justify-self: center; width: 40px; height: 28px; }
  .cell label { display: block; width: 100%; height: 100%; border-radius: 8px; cursor: pointer; box-sizing: border-box;
                border: 2px solid var(--divider-color, rgba(127, 127, 127, 0.3)); }
  .cell.is-default label { border-style: dashed; opacity: 0.75; }
  .cell input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; border: 0; padding: 0; }
  .cell label:has(input:focus-visible) { outline: var(--focus-ring); outline-offset: 2px; }
  .cell button { position: absolute; top: -8px; right: -10px; width: 20px; height: 20px; padding: 0; border: 0; border-radius: 50%;
                 font-size: 12px; line-height: 20px; cursor: pointer; color: var(--text-primary-color, #fff);
                 background: var(--secondary-text-color, #727272); box-shadow: 0 0 0 2px var(--card-background-color, #fff); }
  .cell button::after { content: ""; position: absolute; inset: -6px; }
  .cell.is-default button { display: none; }
  /* Fingers: larger targets (44 px with the gap), 16 px text in selects (iOS doesn't zoom in) */
  @media (any-pointer: coarse) {
    .table { grid-template-columns: 1fr repeat(2, 64px); gap: 10px 8px; }
    .cell { width: 52px; height: 40px; }
    .cell button { top: -9px; right: -9px; width: 22px; height: 22px; line-height: 22px; }
    .reset-all, .text-button { padding: 10px 14px; }
    .icon-button { width: 44px; height: 44px; }
    .field select, .field input[type="text"] { height: 44px; font-size: 16px; }
    .check input, .switch-row input { width: 22px; height: 22px; }
  }
`;

// A CSS color (a theme variable too) as #rrggbb, as the element shows it: what a color input takes
function hexColor(element, color) {
  const probe = document.createElement("span");
  probe.style.color = color;
  probe.style.display = "none";
  element.append(probe);
  const rgb = getComputedStyle(probe).color.match(/\d+(\.\d+)?/g) || ["0", "0", "0"];
  probe.remove();
  return `#${rgb
    .slice(0, 3)
    .map((n) => Math.round(Number(n)).toString(16).padStart(2, "0"))
    .join("")}`;
}

class TibberPricesChartCardEditor extends TibberPricesFormEditor {
  get _card() {
    return TibberPricesChartCard;
  }

  _style() {
    return CHART_EDITOR_STYLE;
  }

  _skeleton() {
    return '<div class="after-form views-panels"></div><div class="colors"></div><div class="end-form"></div>';
  }

  // Interactions at the end, as in HA's own card editors: after the views and the colors
  _formSchema() {
    return super._formSchema().filter((field) => field.name !== "interactions");
  }

  _endSchema() {
    return this._card.getConfigForm().schema.filter((field) => field.name === "interactions");
  }

  _hassChanged(hass) {
    super._hassChanged(hass);
    for (const form of this._viewForms.values()) form.hass = hass;
    if (this._endForm) this._endForm.hass = hass;
  }

  _setUp() {
    this._viewForms = new Map();
    this._bindStyles(this.shadowRoot.querySelector(".views-panels"));
    this._bindColors(this.shadowRoot.querySelector(".colors"));
  }

  _update() {
    this._renderViews();
    this._renderColors();
    if (!this._endForm) {
      this._endForm = this._newForm(this._endSchema(), this._shownData, (value) =>
        this._changed(withChanges(this._config, this._shownData, value))
      );
      this.shadowRoot.querySelector(".end-form").append(this._endForm);
    }
    this._endForm.hass = this._hass;
    this._endForm.data = this._shownData;
  }

  // ---- Views: a panel for all views, then one per view the card offers

  _renderViews() {
    const e = languageStrings(EDITOR_STRINGS);
    const t = languageStrings(STRINGS);
    const root = this.shadowRoot.querySelector(".views-panels");
    const targets = ["all_views", ...chartViews(this._config, { all: true })];
    const key = targets.join(",");
    if (root.dataset.key !== key) {
      // Panels for another set of views; those open stay open
      const open = new Set(
        [...root.querySelectorAll("ha-expansion-panel")].filter((p) => p.expanded).map((p) => p.dataset.target)
      );
      root.innerHTML = "";
      this._viewForms = new Map();
      for (const target of targets) {
        const panel = document.createElement("ha-expansion-panel");
        panel.setAttribute("outlined", "");
        panel.dataset.target = target;
        const title = target === "all_views" ? e.all_views : chartViewName(t, target);
        panel.innerHTML = `<ha-icon slot="leading-icon" icon="${CHART_VIEW_ICONS[target]}"></ha-icon><div slot="header" role="heading" aria-level="3">${title}</div><div class="content">${
          target === "all_views" ? `<p class="help">${e.all_views_help}</p>` : ""
        }<div class="form-slot"></div><div class="styles-block" data-target="${target}"></div></div>`;
        const form = this._newForm(
          TibberPricesChartCard.viewSchema(target, this._inherited()),
          this._viewData(target),
          (value) => this._setView(target, value)
        );
        panel.querySelector(".form-slot").append(form);
        root.append(panel);
        panel.expanded = open.has(target);
        this._viewForms.set(target, form);
      }
      root.dataset.key = key;
    } else {
      // A new schema redraws every field: only where what the views inherit has changed
      const inherited = this._inherited();
      const inheritedKey = JSON.stringify(inherited);
      const schemaChanged = root.dataset.inherited !== inheritedKey;
      for (const [target, form] of this._viewForms) {
        if (schemaChanged) form.schema = TibberPricesChartCard.viewSchema(target, inherited);
        form.data = this._viewData(target);
      }
    }
    root.dataset.inherited = JSON.stringify(this._inherited());
    for (const target of targets) this._renderStyles(target);
  }

  // A panel's form values: for all views as they apply, for a view its own (empty: as for all)
  _viewData(target) {
    const own = this._config[target] || {};
    if (target === "all_views") {
      const options = this._inherited();
      return Object.fromEntries(CHART_VIEW_FIELDS.map((key) => [key, options[key]]));
    }
    const data = {
      resolution: own.resolution || CHART_INHERIT,
      hide: own.hide || [],
      header_level: own.header_level || CHART_INHERIT,
      header_level_at: own.header_level_at || [],
      header_delta: own.header_delta || CHART_INHERIT,
      header_delta_from: own.header_delta_from,
    };
    return data;
  }

  _setView(target, value) {
    const config = { ...this._config };
    const own = { ...(config[target] || {}) };
    for (const key of CHART_VIEW_FIELDS) {
      const item = value[key];
      // For all views a value as the default isn't saved either: a better default reaches it
      const standard = target === "all_views" && JSON.stringify(item) === JSON.stringify(CHART_VIEW_DEFAULTS[key]);
      if (!isSet(item) || item === CHART_INHERIT || standard) delete own[key];
      else own[key] = item;
    }
    this._changed(withKey(config, target, own));
  }

  // ---- Styles: a row each (preview, line, area, dashed line; the first is the default)

  // What applies to a view without options of its own: those for all views, else the defaults
  _inherited() {
    return chartViewOptions(this._config, "all_views");
  }

  _renderStyles(target) {
    const e = languageStrings(EDITOR_STRINGS);
    const block = this.shadowRoot.querySelector(`.styles-block[data-target="${target}"]`);
    if (!block) return;
    const own = this._config[target] || {};
    const ownStyles = Array.isArray(own.styles) && own.styles.length;
    const applying = chartViewOptions(this._config, target);
    const colors = chartColors(this._config, Boolean(this._hass.themes && this._hass.themes.darkMode));
    let html = `<div class="styles-head">${e.styles}</div>`;
    if (target !== "all_views" && !ownStyles) {
      const inherited = applying.styles;
      html += `<p class="help">${e.styles_inherited}</p><div class="inherited">${inherited
        .map(
          (style, i) =>
            `<span class="chip" title="${chartStyleName(e, style)}">${chartStyleIcon(style, colors)}<span>${chartStyleLabel(e, style, i)}</span></span>`
        )
        .join("")}</div><button type="button" class="text-button" data-act="customize">${e.styles_customize}</button>`;
    } else {
      const { styles } = applying;
      const options = (values, prefix, current) =>
        values
          .map(
            (value) =>
              `<option value="${value}"${value === current ? " selected" : ""}>${capitalize(e[`${prefix}${value}`])}</option>`
          )
          .join("");
      const rows = styles
        .map((style, i) => {
          const name = chartStyleName(e, style);
          return `<div class="style-row" data-i="${i}" role="group" aria-label="${name}">
            <span class="preview" title="${name}">${chartStyleIcon(style, colors)}${i ? "" : `<span class="default">${e.default_mark}</span>`}</span>
            <label class="field line"><span>${e.style_line}</span><select data-field="line">${options(CHART_LINES, "style_line_", style.line)}</select></label>
            <label class="field fill"><span>${e.style_fill}</span><select data-field="fill">${options(CHART_FILLS, "style_fill_", style.fill)}</select></label>
            <label class="field style-name"><span>${e.style_label}</span><input type="text" data-field="name" value="${escapeHtml(style.name || "")}" placeholder="${fill(e.style_number, { n: i + 1 })}"></label>
            <label class="check ref"><input type="checkbox" data-field="reference"${style.reference ? " checked" : ""}>${e.style_reference}</label>
            <span class="actions">
              <button type="button" class="icon-button" data-act="up" title="${e.style_up}" aria-label="${e.style_up}"${i ? "" : " disabled"}>${svgIcon(CHEVRON_UP)}</button>
              <button type="button" class="icon-button" data-act="down" title="${e.style_down}" aria-label="${e.style_down}"${i < styles.length - 1 ? "" : " disabled"}>${svgIcon(CHEVRON_DOWN)}</button>
              <button type="button" class="icon-button" data-act="remove" title="${e.style_remove}" aria-label="${e.style_remove}"${styles.length > 1 ? "" : " disabled"}>${svgIcon(CLOSE_PATH)}</button>
            </span>
          </div>`;
        })
        .join("");
      const switchOn = applying.style_switch;
      html += `<div class="style-rows">${rows}</div>`;
      if (styles.length > 1) {
        html += `<label class="switch-row"><input type="checkbox" data-act="switch"${switchOn ? " checked" : ""}><span><b>${e.style_switch}</b><small>${e.style_switch_help}</small></span></label>`;
      }
      html += `<div class="styles-foot"><button type="button" class="text-button" data-act="add">+ ${e.style_add}</button>${
        target === "all_views"
          ? ""
          : `<button type="button" class="text-button" data-act="inherit">${e.styles_inherit}</button>`
      }</div>`;
    }
    if (block.dataset.html === html) return;
    block.dataset.html = html;
    block.innerHTML = html;
  }

  _bindStyles(root) {
    root.addEventListener("change", (ev) => {
      const block = ev.target.closest(".styles-block");
      if (!block) return;
      const { target } = block.dataset;
      if (ev.target.dataset.act === "switch") {
        this._editStyles(target, (styles, own) => {
          own.style_switch = ev.target.checked;
          return styles;
        });
        return;
      }
      const field = ev.target.dataset.field;
      const row = ev.target.closest(".style-row");
      if (!field || !row) return;
      const value = field === "reference" ? ev.target.checked : ev.target.value;
      this._editStyles(target, (styles) =>
        styles.map((style, i) => {
          if (i !== Number(row.dataset.i)) return style;
          const changed = { ...style, [field]: value };
          // An empty name: called by its place again
          if (field === "name" && !String(value).trim()) delete changed.name;
          return changed;
        })
      );
    });
    root.addEventListener("click", (ev) => {
      const button = ev.target.closest("button[data-act]");
      const block = button && button.closest(".styles-block");
      if (!block) return;
      const { target } = block.dataset;
      const row = button.closest(".style-row");
      const i = row ? Number(row.dataset.i) : -1;
      const act = button.dataset.act;
      if (act === "inherit") {
        const own = { ...(this._config[target] || {}) };
        delete own.styles;
        delete own.style_switch;
        this._changed(withKey(this._config, target, own));
        return;
      }
      this._editStyles(target, (styles, own) => {
        if (act === "customize") {
          own.style_switch = this._inherited().style_switch;
          return styles;
        }
        if (act === "add") {
          // The most useful combination not offered yet: the simple style first, as in Tibber's app
          const ids = new Set(styles.map(chartStyleId));
          const next = [
            { line: "average", fill: "average_shown" },
            { line: "level", fill: "average_shown" },
            { line: "single", fill: "average_shown", reference: false },
            { line: "level", fill: "level" },
            { line: "single", fill: "level" },
            { line: "average", fill: "average_day", reference: false },
          ]
            .map(chartStyle)
            .find((style) => !ids.has(chartStyleId(style)));
          return [...styles, next || chartStyle({ line: "average", fill: "average_shown" })];
        }
        if (act === "remove") return styles.filter((_, k) => k !== i);
        const to = act === "up" ? i - 1 : i + 1;
        if (to < 0 || to >= styles.length) return styles;
        const moved = styles.slice();
        [moved[i], moved[to]] = [moved[to], moved[i]];
        return moved;
      });
    });
  }

  // Changes a panel's styles (a view without its own starts from those it inherits)
  _editStyles(target, change) {
    const config = { ...this._config };
    const own = { ...(config[target] || {}) };
    own.styles = change(chartViewOptions(this._config, target).styles, own).map(chartStyle);
    if (own.styles.length < 2) delete own.style_switch;
    config[target] = own;
    this._changed(config);
  }

  // ---- Colors

  _bindColors(colors) {
    // While the picker is open only its swatch follows (redrawing would close the picker);
    // the table follows when it closes (the area's colors follow the line's)
    colors.addEventListener("input", (ev) => {
      const input = ev.target.closest("input[type=color]");
      if (!input) return;
      input.parentElement.style.background = input.value;
      input.closest(".cell").classList.remove("is-default");
      this._setColor(input.dataset.group, input.dataset.key, input.value, false);
    });
    colors.addEventListener("change", (ev) => {
      if (ev.target.closest("input[type=color]")) this._changed(this._config);
    });
    colors.addEventListener("click", (ev) => {
      const button = ev.target.closest("button[data-key]");
      if (button) this._setColor(button.dataset.group, button.dataset.key, undefined);
      // All of a panel's own colors at once: the standard ones apply again
      const all = ev.target.closest("button[data-reset]");
      if (all) {
        const config = { ...this._config };
        delete config[all.dataset.reset];
        this._changed(config);
      }
    });
  }

  _setColor(group, key, value, redraw = true) {
    const colors = { ...(this._config[group] || {}) };
    if (value === undefined) delete colors[key];
    else colors[key] = value;
    this._changed(withKey(this._config, group, colors), redraw);
  }

  // The table of colors; kept while a picker is open (redrawn only where values differ)
  _renderColors() {
    const e = languageStrings(EDITOR_STRINGS);
    const t = languageStrings(STRINGS);
    const root = this.shadowRoot.querySelector(".colors");
    // Unchanged colors and theme: nothing to do (each swatch reads its color from the page)
    const themes = (this._hass && this._hass.themes) || {};
    const key = JSON.stringify([
      this._config.line_colors,
      this._config.fill_colors,
      this._config.day_colors,
      themes.theme,
      themes.darkMode,
      document.documentElement.lang,
    ]);
    if (root.dataset.key === key) return;
    root.dataset.key = key;
    const name = (state) =>
      CHART_DAY_COLORS[state] ? t[state] : CHART_THEME_COLORS[state] ? e[`color_${state}`] : t.levels[state];
    // What applies, as the card works it out (an own color, else the theme's or the level's for
    // the line, the line's for the area), in the mode of that column
    const applying = { light: chartColors(this._config, false), dark: chartColors(this._config, true) };
    const part = { line_colors: "line", fill_colors: "fill", day_colors: "days" };
    const applies = (group, state, mode) => applying[mode][part[group]][state];
    const html = Object.entries(CHART_COLOR_STATES)
      .map(([group, states]) => {
        const rows = states
          .map((state) => {
            const cells = CHART_MODES.map((mode) => {
              const key = `${state}_${mode}`;
              const own = cssColor((this._config[group] || {})[key]);
              const color = hexColor(root, applies(group, state, mode));
              const title = `${name(state)} (${e[`mode_${mode}`]})`;
              return `<div class="cell${own ? "" : " is-default"}"><label style="background:${color}" title="${title}"><input type="color" value="${color}" data-group="${group}" data-key="${key}" aria-label="${title}"></label><button type="button" data-group="${group}" data-key="${key}" title="${e.color_reset}" aria-label="${e.color_reset}: ${title}">✕</button></div>`;
            }).join("");
            return `<span class="name">${name(state)}</span>${cells}`;
          })
          .join("");
        const own = Object.keys(this._config[group] || {}).length > 0;
        const icon =
          { line_colors: "mdi:chart-line-variant", fill_colors: "mdi:texture-box" }[group] || "mdi:calendar-blank";
        return `<ha-expansion-panel outlined data-group="${group}"><ha-icon slot="leading-icon" icon="${icon}"></ha-icon><div slot="header" role="heading" aria-level="3">${e[group]}</div><div class="content"><p class="help">${e[`${group}_help`]}</p><div class="table"><span></span><span class="head">${e.mode_light}</span><span class="head">${e.mode_dark}</span>${rows}</div><button type="button" class="reset-all" data-reset="${group}"${own ? "" : " hidden"}>${e.color_reset_all}</button></div></ha-expansion-panel>`;
      })
      .join("");
    if (root.dataset.html === html) return;
    // Keep panels open across redraws
    const open = new Set(
      [...root.querySelectorAll("ha-expansion-panel")].filter((p) => p.expanded).map((p) => p.dataset.group)
    );
    root.dataset.html = html;
    root.innerHTML = html;
    for (const panel of root.querySelectorAll("ha-expansion-panel")) panel.expanded = open.has(panel.dataset.group);
  }
}

/**
 * tibber-prices-outlook-feature: the coming hours as a tile card feature. Add it to a tile of
 * the Current Electricity Price sensor ("Add feature" in the tile editor): a row of small bars
 * in the level colors, from the hour running now to six hours ahead. Works below the tile and
 * inline next to its name; time labels drop out when the row gets too narrow for them.
 */
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

class TibberPricesOutlookFeature extends HTMLElement {
  static getStubConfig() {
    return { type: "custom:tibber-prices-outlook-feature" };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
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
    if (!this._hass || !this._stateObj) return;
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
    // Now and six hours ahead: a tile has room for that, with readable labels
    const hours = (this._stateObj.attributes.outlook_hours || [])
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
    const hourFormat = homeCalendar(this._hass).hourLabel;
    const unit = this._stateObj.attributes.unit_of_measurement || "";
    const columns = hours.map((h) => {
      const current = Date.parse(h.start) <= now;
      const label = current ? t.now : hourFormat.format(new Date(h.start)).replace(/\D+$/, "");
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
  if (!customElements.get("tibber-prices-card-window")) {
    customElements.define("tibber-prices-card-window", TibberPricesCardWindow);
  }
  for (const [name, element] of [
    ["tibber-prices-forecast-card-editor", TibberPricesForecastCardEditor],
    ["tibber-prices-now-card-editor", TibberPricesNowCardEditor],
  ]) {
    if (!customElements.get(name)) customElements.define(name, element);
  }
  if (!customElements.get("tibber-prices-chart-card-editor")) {
    customElements.define("tibber-prices-chart-card-editor", TibberPricesChartCardEditor);
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
