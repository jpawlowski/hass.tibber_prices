/**
 * What every card builds on: TibberPricesCardBase, and the window a card shows another card in.
 */

import { homeEntities, isPlainObject } from "./util.js";
import { HOLD_DOUBLE_TAP, cardTitle, dialogHead, trackKeyboard } from "./ui.js";
import { stringsFor } from "./strings.js";
import { DEFAULTS, modeVariables } from "./config.js";
import { CARD_WINDOW_STYLE } from "./styles.js";

// The cards a card can show in a window, its options for it under their key: the element, its
// editor (a level down in the outer card's editor) and the icon of its row there
const WINDOW_CARDS = {
  forecast: {
    element: "tibber-prices-forecast-card",
    editor: "tibber-prices-forecast-card-editor",
    icon: "mdi:calendar-clock",
    holds: "the forecast card's options, e.g. `show: [hours, days]`",
  },
  // (The chart card has no title of its own: its window says what it is)
  chart: {
    element: "tibber-prices-chart-card",
    editor: "tibber-prices-chart-card-editor",
    icon: "mdi:chart-line",
    title: (t) => t.chart.open,
    holds: "the chart card's options, e.g. `views: [today, tomorrow]`",
  },
};

// The options of the cards a card opens in a window, checked as on their own: by the card's own
// class, found by its element name (a card never imports another)
export function validateWindowCards(config) {
  for (const [key, card] of Object.entries(WINDOW_CARDS)) {
    const options = config[key];
    if (options === undefined) continue;
    if (!isPlainObject(options)) throw new Error(`\`${key}\` holds ${card.holds}`);
    customElements.get(card.element)?.assertConfig(options);
  }
}

// How long a finger rests before it holds the pointer (then it may move in any direction), and
// how far it may wander meanwhile
const HOLD_MS = 350;
const HOLD_SLOP_PX = 8;

// The editors, loaded with the first one asked for (getConfigElement may answer with a promise):
// a page that only shows cards never loads them
let editorsLoaded;
export function loadEditors() {
  editorsLoaded ??= import("./editors.js").then((editors) => editors.registerEditors());
  return editorsLoaded;
}

// Whether a card is the one in another card's window (it then stands alone: no other card on the
// tab counts it, it counts none)
export function inCardWindow(element) {
  const root = element.getRootNode();
  return root instanceof ShadowRoot && root.host instanceof TibberPricesCardWindow;
}

/**
 * What the cards share: drawn once per frame when one of the home's entities changes, a forced
 * light or dark mode, the configured actions (tap, hold, double tap, like any HA card: the card
 * only reports which gesture happened, HA performs the action) and the other cards they show
 * in a window (see WINDOW_CARDS)
 */
export class TibberPricesCardBase extends HTMLElement {
  // The cards this one shows in a window, `when` its config asks for it
  static windowCards = [];

  // The price shown (see priceState): the total or the energy price alone, as set
  _priceSource() {
    return this._config.price_source;
  }

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
      // The price shown outside, unless the card's own options set one
      config: {
        price_source: this._priceSource(),
        ...options,
        device_id: this._config.device_id,
        show_title: false,
      },
      title: title && !String(options.title || "").trim() ? title(t) : cardTitle(options, t),
      width: this._config.window_width || DEFAULTS.window_width,
      hass: this._hass,
      opener,
    });
  }

  /**
   * A finger resting on `element` for a moment grabs the pointer (a short buzz): from then on its
   * moves are the element's, in any direction, and the page doesn't scroll. Moving away first is
   * a swipe or a scroll as usual, unless `early(dx, dy)` grabs at once on that move. `start(event)`
   * may turn a touch down; `grab(x, y)` and `move(x, y)` follow the held finger; `end(event, held,
   * cancelled)` comes when it lets go. Only touch and pen: the mouse is the card's own
   */
  _bindHold(element, { start, grab, move, end, early }) {
    let touch;
    const take = () => {
      touch.held = true;
      try {
        element.setPointerCapture(touch.id);
      } catch (err) {
        // Pointer already gone
      }
      this._haptic("light");
      grab(touch.x, touch.y);
    };
    element.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse" || event.button > 0 || (start && start(event) === false)) return;
      const current = (touch = {
        id: event.pointerId,
        originX: event.clientX,
        originY: event.clientY,
        x: event.clientX,
        y: event.clientY,
        held: false,
      });
      current.timer = setTimeout(() => touch === current && !current.held && take(), HOLD_MS);
    });
    // Once held, the finger's moves are the element's, not the page's: stopped before the page
    // scrolls (only possible before it began, which a finger held still hasn't)
    element.addEventListener(
      "touchmove",
      (event) => {
        if (touch && touch.held && event.cancelable) event.preventDefault();
      },
      { passive: false }
    );
    // A long press would open the context menu or the text selection
    element.addEventListener("contextmenu", (event) => event.preventDefault());
    element.addEventListener("pointermove", (event) => {
      if (!touch || touch.id !== event.pointerId) return;
      touch.x = event.clientX;
      touch.y = event.clientY;
      if (touch.held) {
        move(touch.x, touch.y);
        return;
      }
      const dx = Math.abs(touch.x - touch.originX);
      const dy = Math.abs(touch.y - touch.originY);
      if (early && early(dx, dy)) {
        clearTimeout(touch.timer);
        take();
      } else if (Math.hypot(dx, dy) > HOLD_SLOP_PX) {
        // Moved before the hold: no hold any more, a swipe or a scroll
        clearTimeout(touch.timer);
      }
    });
    const finish = (event, cancelled) => {
      if (!touch || touch.id !== event.pointerId) return;
      const { held, timer } = touch;
      clearTimeout(timer);
      touch = undefined;
      end(event, held, cancelled);
    };
    element.addEventListener("pointerup", (event) => finish(event, false));
    element.addEventListener("pointercancel", (event) => finish(event, true));
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
export class TibberPricesCardWindow extends HTMLElement {
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
