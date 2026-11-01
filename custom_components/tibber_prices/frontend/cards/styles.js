/**
 * The styles the cards share. Pieces (BASE_STYLE, WINDOW_STYLE, ...) are interpolated into each
 * card's own, not copied.
 */

import { FADE, TRACK_COLOR } from "./ui.js";

// What every shadow root of the cards and editors starts with: focus rings only for the keyboard
// (the shadow root's focusin sets data-keyboard), and the hidden attribute hiding an element
// whatever display its class gives it
export const BASE_STYLE = `
  :host { --focus-ring: none; }
  :host([data-keyboard]) { --focus-ring: 2px solid var(--primary-color, #03a9f4); }
  :host(:not([data-keyboard])) :focus-visible { outline: none; }
  [hidden] { display: none !important; }
`;

// The pulsing dot of what's live (now): a ring slowly pulsing out of it, like a live broadcast's
// (in the "now" blue, not red: red means expensive here). Still for those who reduce motion. Its
// size and color: --live-dot-size, --live-dot-color
export const LIVE_DOT_STYLE = `
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
export const ACTION_BUTTON_STYLE = `
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
export const CARD_WINDOW_STYLE = `
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
export const STYLE = `
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
                    --bar-w: 20px; --span-w: 16px; --day-h: 12px; --day-gap: 6px; --name-h: 16px; --value-h: 20px; --label-h: 14px; }
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
  /* Current price and median at one spot: each pointer's line runs from its side to the middle,
     one line in two colors */
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
    .strip { --bar-w: 24px; --span-w: 18px; --day-h: 20px; --name-h: 20px; --label-h: 16px; }
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
    .strip { --bar-w: 28px; --span-w: 20px; --name-h: 22px; --label-h: 18px; }
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
