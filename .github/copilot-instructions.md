# Copilot Instructions

This repository contains a **custom component for Home Assistant**, intended to be distributed via the **HACS (Home Assistant Community Store)**.

## Development Guidelines

-   Follow the **official Home Assistant development guidelines** at [developers.home-assistant.io](https://developers.home-assistant.io).
-   Ensure compatibility with the **latest Home Assistant release**.
-   Use **async functions**, **non-blocking I/O**, and **config flows** where applicable.
-   Structure the component using these standard files:

    -   `__init__.py` – setup and teardown
    -   `manifest.json` – metadata and dependencies
    -   `config_flow.py` – if the integration supports UI configuration
    -   `sensor.py`, `switch.py`, etc. – for platforms
    -   `const.py` – constants (`DOMAIN`, `CONF_*`, etc.)

-   Use Home Assistant's built-in helpers and utility modules:

    -   `homeassistant.helpers.entity`, `device_registry`, `config_validation`
    -   `homeassistant.util.dt` (`dt_util`) for time/date handling

-   Do not wrap built-in functions (e.g., don’t wrap `dt_util.parse_datetime`)
-   Avoid third-party or custom libraries unless absolutely necessary
-   Never assume static local file paths — use config options and relative paths

## Coding Style

-   Follow **PEP8**, enforced by **Black**, **isort**, and **Ruff**
-   Use **type hints** on all function and method signatures
-   Add **docstrings** for all public classes and methods
-   Use **f-strings** for string formatting
-   Do not use `print()` — use `_LOGGER` for logging
-   YAML examples must be **valid**, **minimal**, and **Home Assistant compliant**

## Code Structure and Ordering

Use the following order inside Python modules:

1. **Imports**

    - Python standard library imports first
    - Third-party imports (e.g., `homeassistant.*`)
    - Local imports within this component (`from . import xyz`)
    - Enforced automatically by `isort`

2. **Module-level constants and globals**

    - Define constants and globals at module-level (e.g., `DOMAIN`, `_LOGGER`, `CONF_*`, `DEFAULT_*`)

3. **Top-level functions**

    - Use only for stateless, reusable logic
    - Prefix with `_` if internal only (e.g., `_parse_price()`)
    - Do not place Home Assistant lifecycle logic here

4. **Main classes**

    - Define main classes (Home Assistant Entity classes, DataUpdateCoordinators, and ConfigFlow handlers)
    - Order inside class:

        - Special methods (`__init__`, `__repr__`)
        - Public methods (no `_`)
        - Private methods (`_prefix`)

    - All I/O or lifecycle methods must be `async def`

5. **Helper classes**

    - If helper classes become complex, move them to separate modules (e.g., `helpers.py`, `models.py`)

> ✅ Copilot tip: Use top-level functions for pure helpers only. Prefer structured classes where Home Assistant expects them.

## Data Structures

Use `@dataclass` for plain data containers where appropriate:

```python
from dataclasses import dataclass

@dataclass
class PriceSlot:
    start: datetime
    end: datetime
    price: float
```

## Visual File Layout

Split component logic into multiple Python modules for improved clarity and maintainability:

```
/custom_components/your_component/
├── __init__.py
├── manifest.json
├── const.py
├── sensor.py
├── config_flow.py
├── models.py       # dataclasses
├── helpers.py      # pure utility functions
```

Use `#region` / `#endregion` optionally to improve readability in large files.

## Optional Files (Custom Integration via HACS)

Only create these files if explicitly required by your integration features. Not all files used in Core integrations apply to Custom Integrations:

-   `services.yaml` – Define custom Home Assistant services
-   `translations/*.json` (e.g., `en.json`, `de.json`) – Provide translations for UI elements
-   Additional platform files (e.g., `binary_sensor.py`, `switch.py`, `number.py`, `button.py`, `select.py`) – Support for additional entity types
-   `websocket_api.py` – Define custom WebSocket API endpoints
-   `diagnostics.py` – Provide diagnostic data to users and maintainers
-   `repair.py` – Offer built-in repair hints or troubleshooting guidance
-   `issue_registry.py` – Communicate integration-specific issues or important changes to users clearly

> ⚠️ **Copilot tip**: Avoid Core-only files (`device_action.py`, `device_trigger.py`, `device_condition.py`, `strings.json`) for Custom Integrations. These are typically not supported or rarely used.

## Linting and Code Quality

-   Enforced by **Ruff**, which runs:

    -   Locally via VS Code devcontainer
    -   Remotely via GitHub Actions

Key Ruff linter rules that must be followed:

-   `F401`, `F841` – No unused imports or variables
-   `E402`, `E501` – Imports at top, lines ≤88 chars
-   `C901`, `PLR0912`, `PLR0915` – Functions must be small and simple
-   `PLR0911`, `RET504` – No redundant `else` after `return`
-   `B008` – No mutable default arguments
-   `T201` – Do not use `print()`
-   `SIM102` – Prefer `if x` over `if x == True`

Also:

-   Use **Black** for formatting
-   Use **isort** for import sorting
-   See `.ruff.toml` for custom settings
-   Prefer **one return statement per function** unless early returns improve clarity

## Tests

This integration does **not include automated tests** by default.

> ⚠️ If Copilot generates tests, keep them minimal and **do not introduce new test frameworks** not already present.
