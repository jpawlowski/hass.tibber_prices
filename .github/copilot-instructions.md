# Copilot Instructions

This repository contains a **custom component for Home Assistant**, intended to be distributed via the **HACS (Home Assistant Community Store)**.

## Development Guidelines

-   Follow the **latest development practices** from both Home Assistant and HACS.
-   This component must be compatible with the **latest Home Assistant release**.
-   When working with dates or time references, always use the **current real-world date** and assume it is fetched from the internet — never use outdated or static values from training data.
-   Use **async functions**, **non-blocking I/O**, and **config flows** where applicable.
-   Structure the component with the expected files: `__init__.py`, `manifest.json`, `config_flow.py` (if needed), and versioning compatible with HACS.

## Coding Style

-   Follow **PEP8** and the official **Home Assistant coding conventions**.
-   Use **type hints** for all function signatures.
-   Include **docstrings** for all public classes and methods.
-   Prefer **f-strings** over `%` or `.format()` for string formatting.
-   Avoid placeholder or mock data unless explicitly required.
-   Never assume hardcoded paths or local setups — use **relative paths** and **configurable options**.
-   YAML examples must be valid and formatted correctly for use in Home Assistant.

## Code Structure and Ordering

To ensure readability and consistency, follow this recommended structure within each Python module:

1. **Imports**

    - Standard library imports
    - Third-party libraries (e.g., `homeassistant.*`)
    - Local module imports (`from . import xyz`)
    - Use `isort` to enforce this automatically

2. **Module-level constants and globals**

    - e.g., `DOMAIN`, `_LOGGER`, `CONF_*`

3. **Top-level functions**

    - Use only if necessary and not part of a class

4. **Main classes**

    - Core classes come first (e.g., entity platforms, config flows, coordinators)
    - Within each class:
        - Public methods first, ordered by importance or typical usage
        - Then private methods (prefix with `_`)
        - Special methods (`__init__`, `__str__`, etc.) at the top of the class

5. **Helper classes**
    - Place below main classes or move to a separate module if large

-   Use `async def` for all I/O-bound functions and Home Assistant callbacks
-   Split large modules into separate files for clarity

> ✅ Tip for Copilot: Public before private. Group logically. Favor readability over cleverness.

## Linting and Code Quality

-   Code must be clean and compliant with **Ruff**, which runs:
    -   Locally in the **devcontainer** (VS Code or Cursor)
    -   Remotely via **GitHub Actions**
-   Follow these key Ruff rules:
    -   `F401`, `F841` – No unused imports or variables
    -   `E402`, `E501` – Imports at top, lines ≤88 chars
    -   `C901`, `PLR0912`, `PLR0915` – Keep functions small and simple
    -   `PLR0911`, `RET504` – Avoid redundant returns and `else` after `return`
    -   `B008` – No mutable default arguments
    -   `T201` – Use `_LOGGER`, not `print()`
    -   `SIM102` – Use direct conditions (`if x`, not `if x == True`)
-   Prefer a **single return statement** at the end of a function
    (prepare the return value first, then return it once)
-   Avoid returning early unless it clearly improves readability
-   Use **Black** for code formatting and **isort** for import sorting
-   See `.ruff.toml` for detailed settings

## Additional Notes

-   Avoid generating placeholder or mock data unless explicitly required.
-   Don’t assume hardcoded paths or specific local setups – use **relative paths** and **configurable options**.
-   YAML examples should be valid and properly formatted for use in Home Assistant configs.

> ✅ Tip for Copilot: Generate clean, modular, and lint-compliant code from the start to minimize review and CI errors.

## Tests

This project does **not currently include automated tests**. Simplicity and fast iteration are prioritized over test coverage at this stage.

> ⚠️ If you generate tests, keep them minimal and **do not introduce testing frameworks or infrastructure** that are not already present in the project.
