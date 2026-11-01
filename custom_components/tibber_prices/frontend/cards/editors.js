/**
 * The cards' editors: Home Assistant's form for their options, showing the value that applies where
 * the config sets nothing (HA's own cards do, an empty field there means "none"), and saving only
 * what's changed: a value shown but never touched stays out of the config, so a better default
 * later reaches the card too. (HA's form hands back all values it shows, so the change is worked
 * out against what it showed.)
 */

import { capitalize, escapeHtml, fill, isPlainObject } from "./util.js";
import { BACK_PATH, CHEVRON_DOWN, CHEVRON_RIGHT, CHEVRON_UP, CLOSE_PATH, svgIcon, trackKeyboard } from "./ui.js";
import { EDITOR_STRINGS, STRINGS, languageStrings } from "./strings.js";
import { BASE_STYLE } from "./styles.js";
import { TibberPricesForecastCard } from "./forecast-card.js";
import { TibberPricesNowCard } from "./now-card.js";
import {
  CHART_COLOR_STATES,
  CHART_DAY_COLORS,
  CHART_FILLS,
  CHART_INHERIT,
  CHART_LINES,
  CHART_MODES,
  CHART_THEME_COLORS,
  CHART_VIEW_FIELDS,
  CHART_VIEW_ICONS,
  STYLE_ICON_STYLE,
  TibberPricesChartCard,
  chartColors,
  chartStyle,
  chartStyleIcon,
  chartStyleId,
  chartStyleLabel,
  chartStyleName,
  chartViewName,
  chartViewOptions,
  chartViews,
  cssColor,
  isSet,
} from "./chart-card.js";
import { TibberPricesEnergyCard } from "./energy-card.js";

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

// Options a card in another card's window takes from the outer card (see _openInWindow), so its
// editor a level down leaves them out
const NESTED_FROM_OUTER = ["device_id", "price_source"];

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
  // a level down, without the home and the price shown: the card in the window takes them from
  // the outer card
  _formSchema() {
    const schema = this._card.getConfigForm().schema;
    if (!this._nested) return schema;
    const outer = (fields) =>
      fields
        .filter((field) => !NESTED_FROM_OUTER.includes(field.name))
        .map((field) => (field.schema ? { ...field, schema: outer(field.schema) } : field));
    return outer(schema);
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
          TibberPricesChartCard.viewSchema(target, this._inherited(), this._card.viewDefaults),
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
        if (schemaChanged) form.schema = TibberPricesChartCard.viewSchema(target, inherited, this._card.viewDefaults);
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
      const standard = target === "all_views" && JSON.stringify(item) === JSON.stringify(this._card.viewDefaults[key]);
      if (!isSet(item) || item === CHART_INHERIT || standard) delete own[key];
      else own[key] = item;
    }
    this._changed(withKey(config, target, own));
  }

  // ---- Styles: a row each (preview, line, area, dashed line; the first is the default)

  // What applies to a view without options of its own: those for all views, else the defaults
  _inherited() {
    return chartViewOptions(this._config, "all_views", this._card.viewDefaults);
  }

  _renderStyles(target) {
    const e = languageStrings(EDITOR_STRINGS);
    const block = this.shadowRoot.querySelector(`.styles-block[data-target="${target}"]`);
    if (!block) return;
    const own = this._config[target] || {};
    const ownStyles = Array.isArray(own.styles) && own.styles.length;
    const applying = chartViewOptions(this._config, target, this._card.viewDefaults);
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
    own.styles = change(chartViewOptions(this._config, target, this._card.viewDefaults).styles, own).map(chartStyle);
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

class TibberPricesEnergyCardEditor extends TibberPricesChartCardEditor {
  get _card() {
    return TibberPricesEnergyCard;
  }
}

// Defined once the first editor is asked for (loadEditors in base.js): most pages never show one,
// and by then the frontend's registry is the final one
export function registerEditors() {
  for (const [name, element] of [
    ["tibber-prices-forecast-card-editor", TibberPricesForecastCardEditor],
    ["tibber-prices-now-card-editor", TibberPricesNowCardEditor],
    ["tibber-prices-chart-card-editor", TibberPricesChartCardEditor],
    ["tibber-prices-energy-card-editor", TibberPricesEnergyCardEditor],
  ]) {
    if (!customElements.get(name)) customElements.define(name, element);
  }
}
