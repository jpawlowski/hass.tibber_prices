# Copilot Instructions

This repository contains a **custom component for Home Assistant**, intended to be distributed via the **HACS (Home Assistant Community Store)**.

## Development Guidelines

- Follow the **latest development practices** from both Home Assistant and HACS.
- This component is actively maintained and must be compatible with the **latest Home Assistant release**.
- When working with dates or time references, always use the **current real-world date** and assume it is fetched from the internet — never use outdated or static values from training data.
- Use **async functions**, **non-blocking I/O**, and **config flows** where applicable.
- Ensure the component is structured with proper files: `__init__.py`, `manifest.json`, `config_flow.py` (if needed), and versioning compatible with HACS.

## Coding Style

- Follow **PEP8** and Home Assistant's coding conventions.
- Use **type hints** and include **docstrings** for all public classes and methods.
- Prefer **f-strings** for string formatting over `%` or `.format()`.

## Linting and Code Quality

- Code must be clean and compliant with **Ruff**, which runs:
  - **Locally** in the **devcontainer** (VS Code or Cursor)
  - **Remotely** via **GitHub Actions**
- Follow these key Ruff rules:
  - `F401`, `F841` – No unused imports or variables
  - `E402`, `E501` – Imports at top, lines ≤88 chars
  - `C901`, `PLR0912`, `PLR0915` – Keep functions small and simple
  - `PLR0911`, `RET504` – Avoid redundant returns and `else` after `return`
  - `B008` – No mutable default arguments
  - `T201` – Use `_LOGGER`, not `print()`
  - `SIM102` – Use direct conditions (`if x`, not `if x == True`)
- Prefer a **single return statement** at the end of a function for clarity
  (prepare the return value first, then return it once)
- Avoid returning early unless it clearly improves readability
- Use **Black** for formatting and **isort** for import sorting
- See `.ruff.toml` for detailed settings

## Additional Notes

- Avoid generating placeholder or mock data unless explicitly required.
- Don’t assume hardcoded paths or specific local setups – use **relative paths** and **configurable options**.
- YAML examples should be valid and properly formatted for use in Home Assistant configs.

> ✅ Tip for Copilot: Generate clean, modular, and lint-compliant code from the start to minimize review and CI errors.

## Tests

This project does **not currently include automated tests**. Simplicity and fast iteration are prioritized over test coverage at this stage.

> ⚠️ If you generate tests, keep them minimal and **do not introduce testing frameworks or infrastructure** that are not already present in the project.
