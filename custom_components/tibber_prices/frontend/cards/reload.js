/**
 * The notice that the cards on this page are outdated, with a button to reload.
 *
 * After an update the integration serves the cards under a new URL (frontend/__init__.py), but a
 * page that stays open keeps running the modules it loaded; the companion app may do so for days.
 * The editors, loaded on demand, would come from the old URL, which is no longer served. Home
 * Assistant restarts after every update of an integration, so the page's connection comes back
 * then: once the integration is set up again (listed in hass.config.components, which Home
 * Assistant keeps current), the page asks it where the cards are served now. When that isn't
 * where these came from, it shows Home Assistant's own notice (the `hass-notification` event its
 * frontend uses itself) with a button to reload. Only the check is ours, as with other custom
 * cards that do this. It never reloads without asking: the user may be in the middle of something.
 */

import { STRINGS, languageStrings } from "./strings.js";

// Where these modules came from, as the integration names it (without the trailing slash)
const LOADED_FROM = new URL(".", import.meta.url).pathname.replace(/\/$/, "");

let connection;
// Whether the connection (re)started since the last answer, and whether a question is on its way
let pending = false;
let asking = false;
let offered = false;
// The list of components a question failed with: right after a reconnect the page may still hold
// the one from before the restart, naming the integration before it is set up again. Asked again
// once Home Assistant sends a new list (it replaces it on every change)
let failedWith;
let lastComponents;

// Called with every new hass object, from every card and tile feature: watches the connection
// once, and asks as soon as the integration is set up after a (re)connect
export function watchForUpdate(hass) {
  if (hass.connection && hass.connection !== connection) {
    connection = hass.connection;
    connection.addEventListener("ready", () => {
      pending = true;
      failedWith = undefined;
    });
    pending = true;
  }
  const components = (lastComponents = hass.config?.components);
  if (pending && !asking && !offered && components !== failedWith && components?.includes("tibber_prices")) {
    ask(components);
  }
}

// Called where loading a module failed (loadEditors in base.js): most likely it came from a URL an
// update left behind, but a fault in the module fails the same way, so the integration decides
export function checkForUpdate() {
  pending = true;
  failedWith = undefined;
  if (connection && !asking && !offered) ask(lastComponents);
}

async function ask(components) {
  asking = true;
  try {
    const { url } = await connection.sendMessagePromise({ type: "tibber_prices/frontend" });
    pending = false;
    if (url !== LOADED_FROM) offerReload();
  } catch {
    failedWith = components; // asked again with the next list of components or reconnect
  } finally {
    asking = false;
  }
}

function offerReload() {
  if (offered) return;
  offered = true;
  const t = languageStrings(STRINGS).update;
  (document.querySelector("home-assistant") ?? document.body).dispatchEvent(
    new CustomEvent("hass-notification", {
      bubbles: true,
      composed: true,
      // With an id, Home Assistant replaces a notice of the same id instead of stacking another
      detail: {
        id: "tibber_prices-reload",
        message: t.message,
        duration: -1,
        dismissable: true,
        action: { text: t.reload, action: () => location.reload() },
      },
    })
  );
}
