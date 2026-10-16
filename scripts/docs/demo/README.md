# Demo dashboard and documentation screenshots

Everything needed to reproduce the screenshots in the docs and the README from the dev instance (`./scripts/develop`).
The dashboard is also the prototype for a context-aware user dashboard; design notes live in `planning/dashboard-ux-plan.md` (git-ignored, local).

## Tibber demo account

Tibber provides a public demo token with a fictional home ("Vitahuset", shown as "Winterfell Castle 1", Sweden, SEK):

```text
3A77EECF61BD445F47241A5A36202185C35AF3AF58609E19B53F3A8872AD7BE1-1
```

Add the integration in the dev instance with this token. Screenshots must only ever show this demo home, never a real one.

## Setup (once)

1. Install **ApexCharts Card**, **Config Template Card** and **TabDeck Card** from HACS in the dev instance.
2. `config/configuration.yaml` already registers the YAML dashboard `tibber-demo`.
3. Create a long-lived access token (profile → Security) and store it in `config/.ha_token` (git-ignored), or export it as `HA_TOKEN`.

## Render the dashboard

```bash
./scripts/docs/demo/render-dashboard            # writes config/dashboards/tibber-demo.yaml
./scripts/docs/demo/render-dashboard --lang de  # labels in another language
```

The template (`dashboard.template.yaml`) uses placeholders instead of entity IDs and names:

- `entity:<translation_key>` resolves against the entity registry of the demo entry, so it works whatever language HA runs in.
- `label:<key>` resolves from `labels/<lang>.json` (en, de, nb, nl, sv). Names are short because the heading already gives the context ("Lowest price" under "Today", not "Today's Lowest Price"). The labels live here, not in the integration, until a generated user dashboard needs them at runtime.
- `{"$chart": <name>}` inserts a card from `charts/<name>.yaml`.

Reload the dashboard in the browser after rendering; YAML dashboards need no restart.

## Regenerate the chart cards

The files in `charts/` are the output of `tibber_prices.get_apexcharts_yaml` for the demo entry with `level_type: level` (so the chart colors match the price level shown in the verdict) `highlight_best_price: true` and `highlight_peak_price: true` (peak price periods stay hidden until toggled in the legend):

| File | `day` | Tab |
|---|---|---|
| `outlook.yaml` | `rolling_window_autozoom` | Outlook (default) |
| `today.yaml` | `today` | Today |
| `tomorrow.yaml` | `tomorrow` | Tomorrow (only shown once tomorrow's prices exist) |
| `two_days.yaml` | `rolling_window` | 2 days |

Regenerate them after changes to the chart generator, then render again.

## Take screenshots

```bash
uv venv /tmp/pw && uv pip install --python /tmp/pw/bin/python playwright
/tmp/pw/bin/python -m playwright install chromium
/tmp/pw/bin/python scripts/docs/demo/screenshots.py /tmp/shots            # all shots, light + dark
/tmp/pw/bin/python scripts/docs/demo/screenshots.py /tmp/shots overview   # a single shot
```

The script clicks the tabs before each shot and crops to the dashboard content (no sidebar, no user name). Shots of the Tomorrow tab are skipped while tomorrow's prices are not available yet.
