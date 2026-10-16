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
import sys
from typing import NamedTuple

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
BASE = os.environ.get("HA_URL", "http://localhost:8123")
DASHBOARD = "tibber-demo"


class Shot(NamedTuple):
    """One screenshot: where to look, how wide, what to capture."""

    view: str  # view path in the demo dashboard
    width: int  # viewport width in CSS pixels
    target: str  # "content" = all sections of the view, "chart" = the visible ApexCharts card
    tab: tuple[int, str] | None = None  # (nth tabdeck-card in the view, tab name) to click first


SHOTS: dict[str, Shot] = {
    "overview": Shot("overview", 1400, "content", (0, "Now")),
    "overview-hour": Shot("overview", 1400, "content", (0, "Current hour")),
    "overview-next-hour": Shot("overview", 1400, "content", (0, "In 1 hour")),
    "overview-mobile": Shot("overview", 400, "content", (0, "Now")),
    "details": Shot("details", 1200, "content"),
    # Chart tabs on the overview (second tabdeck-card), at desktop width
    "chart-outlook": Shot("overview", 1400, "chart", (1, "Outlook")),
    "chart-today": Shot("overview", 1400, "chart", (1, "Today")),
    "chart-tomorrow": Shot("overview", 1400, "chart", (1, "Tomorrow")),
    "chart-two-days": Shot("overview", 1400, "chart", (1, "2 days")),
}


def token() -> str:
    """Return the HA access token from HA_TOKEN or config/.ha_token."""
    return os.environ.get("HA_TOKEN") or (ROOT / "config" / ".ha_token").read_text().strip()


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
                page.goto(f"{BASE}/{DASHBOARD}/{shot.view}")
                page.wait_for_selector("hui-sections-view", timeout=30000)
                page.wait_for_timeout(6000)  # let ApexCharts render
                capture(page, shot, str(out / f"{name}-{scheme}.png"))
                ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
