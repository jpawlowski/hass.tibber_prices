# Copilot Instructions

This repository contains a **Home Assistant custom integration** providing Tibber electricity price information and ratings, distributed via **HACS**.

## Repository Overview

-   **Type**: Home Assistant Custom Integration (~5,100 lines Python)
-   **Language**: Python 3.13, async/await
-   **Framework**: Home Assistant 2025.10.0+
-   **Main Components**: Sensors, Binary Sensors, Services, Config Flow, Data Coordinator
-   **Testing**: pytest with pytest-homeassistant-custom-component (7 test files)

## Build, Lint, and Test Commands

### Setup (ALWAYS Run First)

```bash
scripts/setup  # Installs dependencies
```

**Note**: `homeassistant>=2025.10.0` may not be in PyPI. Use devcontainer for full environment.

### Linting (ALWAYS Run Before Commit)

```bash
scripts/lint  # Runs: ruff format . && ruff check . --fix
```

-   CI enforces via `.github/workflows/lint.yml` (runs `ruff format --check` and `ruff check`)
-   **CI will fail if linting errors exist**
-   Key rules: F401, F841, E402, E501, C901, PLR0912/15/11, RET504, B008, T201, SIM102
-   Line length: 120 chars (see `.ruff.toml`)

### Testing

```bash
pytest tests/  # Run all tests
pytest tests/test_price_utils.py  # Run specific test
```

Tests in `tests/` directory cover price utilities, coordinator, midnight turnover, services.

### CI Validation

Two workflows run on push/PR:

1. **`validate.yml`**: hassfest (HA manifest validation) + HACS validation
2. **`lint.yml`**: Ruff format + lint checks

**Replicate CI locally**: Run `scripts/lint` – if it passes, CI will pass.

### Development Environment

Use VS Code devcontainer (`.devcontainer/devcontainer.json`):

-   Python 3.13, auto-runs `scripts/setup`
-   Home Assistant on port 8123
-   Start: `scripts/develop` (runs `hass --config ./config --debug`)

## Development Guidelines

-   Follow [developers.home-assistant.io](https://developers.home-assistant.io)
-   Use async functions, non-blocking I/O, config flows
-   Standard files: `__init__.py`, `manifest.json`, `config_flow.py`, `sensor.py`, `const.py`
-   Use HA helpers: `homeassistant.helpers.entity`, `device_registry`, `dt_util`
-   Don't wrap built-ins, avoid third-party libs, no static file paths

## Coding Style

-   **PEP8** via Black, isort, Ruff
-   Type hints + docstrings on all public methods
-   F-strings for formatting
-   Use `_LOGGER`, not `print()`

### Module Structure Order

1. Imports (stdlib → third-party → local)
2. Module constants/globals
3. Top-level functions (public → helpers → utilities)
4. Main classes (Entity, Coordinator, ConfigFlow)
5. Helper classes (or move to separate modules)

### Code Comments Policy

-   **No** comments for automated changes (reordering, renaming, compliance)
-   Comments **only** for logic/purpose/usage
-   Explanations go in PR/commit messages, not code

## Backwards Compatibility Policy

-   **Do not** add compatibility layers unless explicitly requested
-   Target latest stable HA version only

## Translations Policy

-   User-facing strings in `translations/en.json` and other `translations/*.json`
-   **All translation files must sync** – update all languages when adding/changing keys
-   `custom_translations/` for supplemental strings not in standard HA format
-   Never duplicate keys between `translations/` and `custom_translations/`
-   Standard translations take priority over custom

## Project Layout

```
/
├── .github/workflows/          # CI: lint.yml, validate.yml
├── .devcontainer/              # VS Code dev container
├── custom_components/tibber_prices/  # Main code (5,100 lines)
│   ├── __init__.py (115)       # Entry point
│   ├── const.py (473)          # Constants
│   ├── api.py (850)            # Tibber API client
│   ├── coordinator.py (536)    # Data coordinator
│   ├── sensor.py (859)         # Sensor platform
│   ├── binary_sensor.py (693)  # Binary sensors
│   ├── config_flow.py (494)    # UI config
│   ├── services.py (639)       # Custom services
│   ├── price_utils.py (291)    # Price calculations
│   ├── services.yaml           # Service definitions
│   ├── translations/           # Standard HA translations (en, de)
│   └── custom_translations/    # Supplemental translations
├── config/configuration.yaml   # Dev HA config
├── scripts/
│   ├── setup                   # Install deps
│   ├── lint                    # Ruff format & check
│   └── develop                 # Start HA
├── tests/                      # pytest suite (7 files)
├── .ruff.toml                  # Linting config
├── pyproject.toml              # Black/isort config
├── requirements.txt            # Dependencies
└── hacs.json                   # HACS metadata
```

### Configuration Files

-   **`.ruff.toml`**: Python 3.13, line length 120, ALL rules with selective ignores
-   **`pyproject.toml`**: Black/isort (line length 120)
-   **`.editorconfig`**: 4-space indent, LF, UTF-8
-   **`manifest.json`**: domain, version, requirements (`aiofiles>=23.2.1`), IoT class
-   **`hacs.json`**: HA 2025.10.0+, HACS 2.0.1+

### Architecture

-   **Data Flow**: API → Coordinator → Sensors/Binary Sensors
-   **Storage**: HA Storage API for caching
-   **Update**: Polling (cloud_polling)
-   **Services**: get_price, get_apexcharts_data, get_apexcharts_yaml, refresh_user_data

### Common Tasks

-   **Add sensor**: Edit `sensor.py`/`binary_sensor.py` + translation keys
-   **Modify API**: Edit `api.py` (GraphQL queries)
-   **Price calculations**: Edit `price_utils.py`
-   **Translations**: Sync all files in `translations/` and `custom_translations/`
-   **Add service**: Edit `services.py` + `services.yaml`

## Linting Rules (Ruff)

Key enforced rules:

-   F401, F841: No unused imports/variables
-   E402: Imports at top
-   E501: Lines ≤120 chars
-   C901, PLR0912, PLR0915: Simple functions
-   PLR0911, RET504: No redundant else after return
-   B008: No mutable defaults
-   T201: No print()
-   SIM102: Prefer `if x` over `if x == True`

## Optional Files

Only create if needed: `services.yaml`, `translations/*.json`, `binary_sensor.py`, `diagnostics.py`. **Avoid** Core-only files: `device_action.py`, `device_trigger.py`, `strings.json`.

## Important Notes

-   **Only dependency**: `aiofiles>=23.2.1`
-   **No pip install HA**: Use devcontainer
-   **Git ignore**: `__pycache__`, `.pytest*`, `.ruff_cache`, `config/*` (except `configuration.yaml`)
-   **Trust these instructions**: Only search if incomplete or incorrect
