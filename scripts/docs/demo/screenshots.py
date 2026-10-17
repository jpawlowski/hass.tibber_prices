#!/usr/bin/env python3
"""Take documentation screenshots of the demo dashboard (Light + Dark).

Needs Playwright (not a project dependency):
    uv venv /tmp/pw && uv pip install --python /tmp/pw/bin/python playwright
    /tmp/pw/bin/python -m playwright install chromium

Token: HA_TOKEN env var or config/.ha_token (git-ignored). Usage:
    /tmp/pw/bin/python scripts/docs/demo/screenshots.py OUT_DIR [shot_name ...]
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any, NamedTuple

from playwright.sync_api import Page, WebSocketRoute, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
BASE = os.environ.get("HA_URL", "http://localhost:8123")
DASHBOARD = "tibber-demo"
CARDS = "tibber-cards"  # The integration's own cards (cards.yaml), for the Dashboard Cards page


class Shot(NamedTuple):
    """One screenshot: where to look, how wide, what to capture."""

    view: str  # view path in the dashboard
    width: int  # viewport width in CSS pixels
    # "content" = all sections of the view, "chart" = the visible ApexCharts card, "element" =
    # the first element matching `selector` (after clicking `click`, e.g. a dialog it opens)
    target: str
    tab: tuple[int, str] | None = None  # (nth tabdeck-card in the view, tab name) to click first
    dashboard: str = DASHBOARD
    selector: str = ""
    click: str = ""


SHOTS: dict[str, Shot] = {
    "overview": Shot("tibber-prices", 1400, "content"),
    "overview-mobile": Shot("tibber-prices", 400, "content"),
    # Chart tabs on the overview (its tabdeck-card), at desktop width
    "chart-outlook": Shot("tibber-prices", 1400, "chart", (0, "Outlook")),
    "chart-today": Shot("tibber-prices", 1400, "chart", (0, "Today")),
    "chart-tomorrow": Shot("tibber-prices", 1400, "chart", (0, "Tomorrow")),
    "chart-two-days": Shot("tibber-prices", 1400, "chart", (0, "2 days")),
    # Dashboard Cards page
    "card-forecast": Shot("forecast", 1400, "element", dashboard=CARDS, selector="tibber-prices-forecast-card"),
    "card-forecast-mobile": Shot("forecast", 400, "element", dashboard=CARDS, selector="tibber-prices-forecast-card"),
    "card-forecast-details": Shot(
        "forecast",
        1400,
        "element",
        dashboard=CARDS,
        selector="tibber-prices-forecast-card dialog",
        click="tibber-prices-forecast-card .strip.hours .col.current",
    ),
    "card-now": Shot("now", 1400, "content", dashboard=CARDS),
    "card-now-window": Shot(
        "window",
        1400,
        "element",
        dashboard=CARDS,
        selector="tibber-prices-now-card dialog",
        click="tibber-prices-now-card .now-block",
    ),
    "card-feature": Shot("feature", 1000, "content", dashboard=CARDS),
}


def token() -> str:
    """Return the HA access token from HA_TOKEN or config/.ha_token."""
    return os.environ.get("HA_TOKEN") or (ROOT / "config" / ".ha_token").read_text().strip()


def english(page: Page) -> None:
    """
    Show the frontend in English, whatever the token user's profile says.

    The docs are English; the cards follow the profile language, which HA keeps in the user's
    frontend data. Only this browser sees it changed (the profile itself is left alone).
    """
    asked: set[int] = set()

    def as_english(value: Any) -> dict[str, Any]:
        return {**(value or {}), "language": "en", "number_format": "language"}

    def items(data: Any) -> list[dict[str, Any]]:
        """The messages in a frame (HA may send several as one list)."""
        return data if isinstance(data, list) else [data]

    def handle(ws: WebSocketRoute) -> None:
        server = ws.connect_to_server()

        def from_page(message: str | bytes) -> None:
            # Only the few frames that ask for it are read; the rest pass untouched
            if isinstance(message, str) and '"language"' in message:
                for item in items(json.loads(message)):
                    if item.get("key") == "language" and str(item.get("type", "")).startswith("frontend/"):
                        asked.add(item["id"])
            server.send(message)

        def from_server(message: str | bytes) -> None:
            if isinstance(message, str) and asked and '"value"' in message:
                data = json.loads(message)
                changed = False
                for item in items(data):
                    if item.get("id") not in asked:
                        continue
                    if item.get("type") == "result" and isinstance(item.get("result"), dict):
                        item["result"]["value"] = as_english(item["result"].get("value"))
                        changed = True
                    elif item.get("type") == "event" and isinstance(item.get("event"), dict):
                        item["event"]["value"] = as_english(item["event"].get("value"))
                        changed = True
                if changed:
                    message = json.dumps(data)
            ws.send(message)

        ws.on_message(from_page)
        server.on_message(from_server)

    page.route_web_socket(re.compile(r"/api/websocket$"), handle)


def capture(page: Page, shot: Shot, path: str) -> None:
    """Select the tab (if any) and save the screenshot of the chart or of all sections."""
    deck = page.locator("tabdeck-card").nth(shot.tab[0]) if shot.tab else None
    if deck and shot.tab:
        tab = deck.get_by_text(shot.tab[1], exact=True)
        if not tab.count():
            sys.stderr.write(f"Skipped {path}: tab {shot.tab[1]!r} not shown (e.g. no data for tomorrow yet)\n")
            return
        tab.click()
        page.wait_for_timeout(4000)
    if shot.target == "element":
        if shot.click:
            page.locator(shot.click).first.click()
            page.wait_for_timeout(1500)
        page.locator(shot.selector).first.screenshot(path=path)
        return
    if shot.target == "chart" and deck:
        charts = deck.locator("config-template-card:visible, apexcharts-card:visible")
        if not charts.count():
            sys.stderr.write(f"Skipped {path}: no chart visible (e.g. no data for tomorrow yet)\n")
            return
        charts.first.screenshot(path=path)
        return
    boxes = [box for section in page.locator("hui-section").all() if (box := section.bounding_box())]
    x0 = min(b["x"] for b in boxes) - 16
    y0 = min(b["y"] for b in boxes) - 16
    x1 = max(b["x"] + b["width"] for b in boxes) + 16
    y1 = max(b["y"] + b["height"] for b in boxes) + 16
    page.screenshot(path=path, full_page=True, clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})


def main() -> None:
    """Take all requested shots in light and dark mode."""
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[2:] or list(SHOTS)
    auth = json.dumps(
        {
            "access_token": token(),
            "token_type": "Bearer",
            "expires_in": 31536000,
            "expires": 4102444800000,
            "hassUrl": BASE,
            "clientId": f"{BASE}/",
            "refresh_token": "",
        }
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name in wanted:
            shot = SHOTS[name]
            for scheme in ("light", "dark"):
                ctx = browser.new_context(
                    viewport={"width": shot.width, "height": 1200},
                    color_scheme=scheme,
                    locale="en-GB",
                    device_scale_factor=2,
                    timezone_id="Europe/Berlin",
                )
                ctx.add_init_script(f"localStorage.setItem('hassTokens', {json.dumps(auth)});")
                page = ctx.new_page()
                english(page)
                page.goto(f"{BASE}/{shot.dashboard}/{shot.view}")
                page.wait_for_selector("hui-sections-view", timeout=30000)
                page.wait_for_timeout(6000)  # let ApexCharts render
                capture(page, shot, str(out / f"{name}-{scheme}.png"))
                ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
