/**
 * The notice that the cards on this page are outdated, with a button to reload.
 *
 * After an update the integration serves the cards under a new URL (frontend/__init__.py), but a
 * page that stays open keeps running the modules it loaded; the companion app may do so for days.
 * Worse, the editors are loaded on demand from the old URL, which is no longer served. Home
 * Assistant restarts after every update of an integration, so the page's connection comes back
 * then: it asks the integration where the cards are served now, and when that isn't where these
 * came from, shows Home Assistant's own notice (the `hass-notification` event its frontend uses
 * itself) with a button to reload. Only the check is ours, as with other custom cards that do this.
 *
 * Once per page, whichever card or tile feature gets the hass object first. Never reloads without
 * asking: the user may be in the middle of something.
 */

import { stringsFor } from "./strings.js";

// Where these modules came from, as the integration names it (without the trailing slash)
const LOADED_FROM = new URL(".", import.meta.url).pathname.replace(/\/$/, "");

// Right after a restart the connection is back before the integration is set up, and its command
// unknown: asked again a few times, then given up until the next reconnect
const RETRY_MS = 15000;
const RETRIES = 8;

let connection;
let hass;
let offered = false;

// Called with every new hass object; starts watching the connection once
export function watchForUpdate(newHass) {
  hass = newHass;
  if (!hass.connection || connection === hass.connection) return;
  connection = hass.connection;
  connection.addEventListener("ready", () => check(0));
  check(0);
}

async function check(attempt) {
  if (offered) return;
  let answer;
  try {
    answer = await connection.sendMessagePromise({ type: "tibber_prices/frontend" });
  } catch (err) {
    if (err?.code === "unknown_command" && attempt < RETRIES) setTimeout(() => check(attempt + 1), RETRY_MS);
    return;
  }
  // Checked again: a reconnect may have started a second check meanwhile
  if (offered || answer?.url === LOADED_FROM) return;
  offered = true;
  const t = stringsFor(hass).update;
  (document.querySelector("home-assistant") ?? document.body).dispatchEvent(
    new CustomEvent("hass-notification", {
      bubbles: true,
      composed: true,
      detail: {
        message: t.message,
        duration: -1,
        dismissable: true,
        action: { text: t.reload, action: () => location.reload() },
      },
    })
  );
}
