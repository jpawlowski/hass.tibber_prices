/**
 * Pieces of the cards' markup: icons and their paths, mark colors, arcs, dialog heads, and which
 * input the user is on (keyboard or pointer).
 */

import { escapeHtml } from "./util.js";

export const MARK_COLORS = { best: "var(--success-color, #43a047)", peak: "var(--error-color, #db4437)" };

// A period running right now, marked at the bar of now: a piggy bank for best price (a good
// time to save), a warning sign for peak price (better later). mdi:piggy-bank and mdi:alert,
// like HA's own icons
export const PERIOD_PATHS = {
  best: "M19.83 7.5L17.56 5.23C17.63 4.81 17.74 4.42 17.88 4.08C17.96 3.9 18 3.71 18 3.5C18 2.67 17.33 2 16.5 2C14.86 2 13.41 2.79 12.5 4H7.5C4.46 4 2 6.46 2 9.5S4.5 21 4.5 21H10V19H12V21H17.5L19.18 15.41L22 14.47V7.5H19.83M13 9H8V7H13V9M16 11C15.45 11 15 10.55 15 10S15.45 9 16 9C16.55 9 17 9.45 17 10S16.55 11 16 11Z",
  peak: "M13 14H11V9H13M13 18H11V16H13M1 21H23L12 2L1 21Z",
};
// Optically centered in the circle: a triangle's weight sits low, so it goes up a little (half
// way between its box's center and its center of mass)
export const PERIOD_NUDGE = { best: "", peak: "translate(0 -1.5)" };

// mdi:chevron-left / mdi:chevron-right
export const CHEVRON_LEFT = "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z";
export const CHEVRON_RIGHT = "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z";
export const CHEVRON_UP = "M7.41,15.41L12,10.83L16.59,15.41L18,14L12,8L6,14L7.41,15.41Z";
export const CHEVRON_DOWN = "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z";
// mdi:menu-down
export const MENU_DOWN = "M7,10L12,15L17,10H7Z";
// The day's line beyond a detail chart's range: a dash at the edge with an arrow its way
export const REF_OFF_ICONS = {
  up: '<svg viewBox="0 0 12 12" aria-hidden="true"><path class="arrow" d="M6 0L10 5H2Z"></path><path class="dash" d="M0 10H12"></path></svg>',
  down: '<svg viewBox="0 0 12 12" aria-hidden="true"><path class="dash" d="M0 2H12"></path><path class="arrow" d="M6 12L10 7H2Z"></path></svg>',
};

// Whether the last input was the keyboard rather than a tap or a click. The cards move the focus
// themselves (into a window, to its close button, back to what opened it), and Safari and Chrome
// show the focus ring on focus set from a script even after a tap: the cards show it only to
// keyboard users (see `data-keyboard` in the style)
export let keyboardInput = false;
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

// mdi:close
// mdi:arrow-left, the way back from a detail opened inside another
export const BACK_PATH = "M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z";
export const CLOSE_PATH =
  "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";
// The faded edge of a strip with more beyond it: a share of its width, within bounds (in the
// styles, and where the price steps keep clear of it)
export const FADE = { share: 0.08, min: 32, max: 72 };

// Same timings as HA's own action handler
export const HOLD_DOUBLE_TAP = { holdMs: 500, doubleTapMs: 250 };

// mdi:text-short, the icon of the "Content" panel in HA's own card editors
export const CONTENT_PATH = "M4,9H20V11H4V9M4,13H14V15H4V13Z";

// mdi:gesture-tap, for the "Interactions" section of the editor (labels as in HA's own editors)
export const GESTURE_TAP_PATH =
  "M10,9A1,1 0 0,1 11,8A1,1 0 0,1 12,9V13.47L13.21,13.6L18.15,15.79C18.68,16.03 19,16.56 19,17.14V21.5C18.97,22.32 18.32,22.97 17.5,23H11C10.62,23 10.26,22.85 10,22.57L5.1,18.37L5.84,17.6C6.03,17.39 6.3,17.28 6.58,17.28H6.8L10,19V9M11,5A4,4 0 0,1 15,9C15,10.5 14.2,11.77 13,12.46V11.24C13.61,10.69 14,9.89 14,9A3,3 0 0,0 11,6A3,3 0 0,0 8,9C8,9.89 8.39,10.69 9,11.24V12.46C7.8,11.77 7,10.5 7,9A4,4 0 0,1 11,5Z";

// "Tagestief 0,22 kr/kWh um 03:15"
/**
 * The mark of the day's low or high: an arrow onto a line, so it reads as the bottom or top
 * reached, not as "going down" or "going up". Drawn in the text's color and size
 */
export const EXTREME_PATHS = {
  low: "M6 1.5V8.5M3.2 5.8L6 8.6L8.8 5.8M2 10.6H10",
  high: "M6 10.5V3.5M3.2 6.2L6 3.4L8.8 6.2M2 1.4H10",
};
export function extremeIcon(kind) {
  return `<svg class="extreme-icon" viewBox="0 0 12 12" aria-hidden="true"><path d="${EXTREME_PATHS[kind]}"></path></svg>`;
}

// Points and arcs of the round displays: angles in degrees, clockwise from 12 o'clock
export function polar(center, radius, angle) {
  const rad = (angle * Math.PI) / 180;
  return [center + radius * Math.sin(rad), center - radius * Math.cos(rad)];
}

export function arcPath(center, radius, from, to) {
  const [x0, y0] = polar(center, radius, from);
  const [x1, y1] = polar(center, radius, to);
  const large = to - from > 180 ? 1 : 0;
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${radius} ${radius} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

export const TRACK_COLOR = "color-mix(in srgb, var(--primary-text-color, #212121) 12%, transparent)";

// A card's title as set, else its standard one ("Electricity prices"), ready for HTML
export function cardTitle(config, t) {
  return escapeHtml(String(config.title || "").trim() || t.card_title);
}

// An icon of Material Design's 24 px grid, for a button
export function svgIcon(path) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"></path></svg>`;
}

// The head of a window, like HA's dialogs: the close (or back) button left of the title (a
// smaller line above it where given), buttons at its end
export function dialogHead({ id, title, label, back = false, subtitle = "", end = "" }) {
  return `<div class="dialog-head"><button class="close${back ? " back" : ""}" aria-label="${label}" title="${label}">${svgIcon(
    back ? BACK_PATH : CLOSE_PATH
  )}</button><div class="dialog-titles">${
    subtitle ? `<div class="dialog-subtitle">${subtitle}</div>` : ""
  }<h2 id="${id}">${title}</h2></div>${end}</div>`;
}

// Focus rings only for the keyboard (see BASE_STYLE): each focus in the element's shadow root
// decides, by the input that led to it
export function trackKeyboard(host) {
  host.shadowRoot.addEventListener("focusin", () => host.toggleAttribute("data-keyboard", keyboardInput));
}
