# Copilot Instructions

This repository contains a **custom component for Home Assistant**, intended to be distributed via the **HACS (Home Assistant Community Store)**.

## Development Guidelines

-   Follow the **latest official practices** from Home Assistant and HACS.
-   Ensure compatibility with the **latest Home Assistant release**.
-   Always use the **current real-world date** when working with times or schedules — do not use hardcoded or outdated values.
-   Use **async functions**, **non-blocking I/O**, and **config flows** when applicable.
-   Structure the component using standard files: `__init__.py`, `manifest.json`, `config_flow.py` (if needed), and proper versioning.
-   Use **Home Assistant built-in libraries and helpers** whenever possible:
    -   For dates: use `homeassistant.util.dt` (`dt_util`)
    -   For configs: use `homeassistant.helpers.config_validation`
    -   For state handling: use `homeassistant.helpers.entity`
-   **Avoid wrapping built-in utilities** (e.g., do not wrap `dt_util.parse_datetime`)
-   **Avoid using custom libraries** unless absolutely necessary and justified

## Coding Style

-   Follow **PEP8** and Home Assistant's coding conventions
-   Use **type hints** for all function and method signatures
-   Add **docstrings** to all public classes and public methods
-   Use **f-strings** for formatting, not `%` or `.format()`
-   Use **relative paths** and **configurable options**, not hardcoded values
-   Provide valid and clean YAML examples when needed (e.g., for `configuration.yaml`)

## Code Structure and Ordering

Follow this standard order within Python modules:

1. **Imports**

    - Python standard library imports
    - Third-party libraries (`homeassistant.*`)
    - Local imports (`from . import xyz`)
    - Use `isort` to enforce order

2. **Module-level constants and globals**

    - Example: `DOMAIN`, `_LOGGER`, `CONF_*`, `DEFAULT_*`

3. **Top-level functions**

    - Only define if they are not part of a class

4. **Main classes**

    - Core classes first: entity classes, coordinators, config flows
    - Method order within each class:
        - Special methods (`__init__`, `__str__`) first
        - Public methods (no `_` prefix), in logical order of usage
        - Private methods (prefix `_`), grouped below public ones

5. **Helper classes**
    - Place after main classes, or move to separate modules if complex

-   Use `async def` for I/O or Home Assistant lifecycle methods
-   Split large files into multiple modules if needed

> ✅ Copilot tip: Use public methods first, private methods after. Avoid mixing. Keep file structure consistent.

### Optional: Code Folding Regions

You may use `#region` and `#endregion` comments to group related logic. Only apply in large files and where folding improves clarity.

## Linting and Code Quality

-   Use **Ruff**, which runs:

    -   Locally in the devcontainer (VS Code or Cursor)
    -   Remotely via GitHub Actions

-   Required Ruff rules:

    -   `F401`, `F841` – No unused imports or variables
    -   `E402`, `E501` – Imports at top, lines ≤88 characters
    -   `C901`, `PLR0912`, `PLR0915` – Keep functions small and simple
    -   `PLR0911`, `RET504` – Avoid unnecessary `else` after `return`
    -   `B008` – No mutable default arguments
    -   `T201` – Use `_LOGGER`, not `print()`
    -   `SIM102` – Use `if x`, not `if x == True`

-   Prefer a **single return statement** at the end of functions
-   Avoid early returns unless they improve clarity
-   Use **Black** for formatting and **isort** for sorting imports
-   Refer to `.ruff.toml` for configuration details

> ✅ Copilot tip: Generate clean, single-pass functions with clear returns. Don’t leave unused code.

## Tests

This project does **not include automated tests**.

> ⚠️ If generating tests, keep them minimal and avoid introducing test frameworks not already present.
