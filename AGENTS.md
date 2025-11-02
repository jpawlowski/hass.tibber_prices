# AI Coding Agent Instructions

This document provides comprehensive instructions for AI coding agents (like ChatGPT Codex, Claude, etc.) to properly understand, set up, and work with this project.

## Project Overview

**Project**: Tibber Price Information & Ratings
**Type**: Home Assistant Custom Integration
**Distribution**: HACS (Home Assistant Community Store)
**Domain**: `tibber_prices`
**Language**: Python 3.13
**License**: MIT

### Purpose

This integration provides advanced price information and ratings from Tibber for Home Assistant users. It enables monitoring of electricity prices, price levels, and rating information to help optimize energy consumption and save money.

### Key Features

-   Current and next hour electricity prices (EUR and ct/kWh)
-   Price level indicators (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE)
-   Statistical sensors (lowest, highest, average prices)
-   Price ratings (quarterly-hour, daily, monthly)
-   Smart binary sensors (peak hour detection, best price hours)
-   Diagnostic sensors (data freshness, API connection status)

## Repository Structure

```
.
├── custom_components/tibber_prices/    # Main integration code
│   ├── __init__.py                     # Setup and teardown
│   ├── manifest.json                   # Integration metadata
│   ├── const.py                        # Constants (DOMAIN, CONF_*, etc.)
│   ├── config_flow.py                  # UI configuration flow
│   ├── coordinator.py                  # Data update coordinator
│   ├── data.py                         # Data models
│   ├── api.py                          # Tibber API client
│   ├── sensor.py                       # Sensor platform
│   ├── binary_sensor.py                # Binary sensor platform
│   ├── entity.py                       # Base entity classes
│   ├── services.py                     # Custom services
│   ├── services.yaml                   # Service definitions
│   ├── diagnostics.py                  # Diagnostic data provider
│   ├── translations/                   # Standard translations
│   │   ├── en.json                     # English translations
│   │   └── de.json                     # German translations
│   └── custom_translations/            # Supplemental translations
│       ├── en.json
│       └── de.json
├── config/                             # Development Home Assistant config
│   └── configuration.yaml
├── scripts/                            # Development scripts
│   ├── setup                           # Install dependencies
│   ├── develop                         # Run development Home Assistant
│   └── lint                            # Run code quality checks
├── tests/                              # Test files (minimal)
├── .devcontainer/                      # VS Code devcontainer config
├── .github/                            # GitHub configuration
│   └── copilot-instructions.md         # GitHub Copilot instructions
├── pyproject.toml                      # Black & isort configuration
├── .ruff.toml                          # Ruff linter configuration
├── requirements.txt                    # Development dependencies
├── hacs.json                           # HACS metadata
├── README.md                           # User documentation
├── CONTRIBUTING.md                     # Contribution guidelines
├── LICENSE                             # MIT License
└── AGENTS.md                           # This file
```

## Environment Setup

### Prerequisites

To work with this project, you need:

1. **Python 3.13** (required by Home Assistant)
2. **Git** for version control
3. **VS Code** (recommended for devcontainer support)
4. **Docker** (for devcontainer-based development)

### Quick Setup (Devcontainer - Recommended)

If working in VS Code with Docker installed:

1. Open the repository in VS Code
2. Accept the prompt to "Reopen in Container" (or use Command Palette → "Dev Containers: Reopen in Container")
3. The devcontainer will automatically:
    - Use Python 3.13 environment
    - Run `scripts/setup` to install dependencies
    - Configure the development environment
    - Set up Home Assistant instance on port 8123

### Manual Setup

If not using devcontainer:

```bash
# Navigate to project root
cd /path/to/hass.tibber_prices

# Install dependencies
pip3 install -r requirements.txt

# Alternatively, use the setup script
bash scripts/setup
```

### Running Development Home Assistant

```bash
# Run Home Assistant with the integration loaded
bash scripts/develop
```

This will:

-   Create a `config/` directory if not present
-   Set `PYTHONPATH` to include `custom_components/`
-   Start Home Assistant in debug mode on port 8123
-   Load the integration from `custom_components/tibber_prices/`

### Running Code Quality Checks

```bash
# Format code and run linter
bash scripts/lint
```

This runs:

-   **Ruff format** (code formatting)
-   **Ruff check --fix** (linting with auto-fixes)

## Development Guidelines

### Framework & Best Practices

This is a **Home Assistant Custom Integration**. Follow these principles:

1. **Official Guidelines**: Follow [developers.home-assistant.io](https://developers.home-assistant.io)
2. **Compatibility**: Target the latest Home Assistant release (2024.1.0+)
3. **Async Programming**: Use `async def` for I/O and lifecycle methods
4. **Config Flows**: Use UI-based configuration (no YAML config)
5. **Built-in Helpers**: Use Home Assistant's helper modules:
    - `homeassistant.helpers.entity`
    - `homeassistant.helpers.device_registry`
    - `homeassistant.helpers.config_validation`
    - `homeassistant.util.dt` (for datetime handling)
6. **No Wrapping**: Don't wrap built-in functions (e.g., `dt_util.parse_datetime`)
7. **Minimal Dependencies**: Avoid third-party libraries unless absolutely necessary
8. **No Static Paths**: Use config options and relative paths, never assume static file paths

### Coding Style

All code must follow these style requirements:

#### Formatting & Linting

-   **Black** for code formatting (line length: 120)
-   **isort** for import sorting
-   **Ruff** for comprehensive linting
-   Enforced locally and via GitHub Actions

#### Python Style

-   **PEP8 compliant**
-   **Type hints** on all function/method signatures
-   **Docstrings** for all public classes and methods
-   **f-strings** for string formatting
-   **NO** `print()` statements — use `_LOGGER` for logging
-   **NO** comments explaining automated changes (reordering, renaming, etc.)
-   Comments should only explain actual logic, purpose, or usage

#### Key Ruff Rules

| Rule                   | Description                        |
| ---------------------- | ---------------------------------- |
| F401, F841             | No unused imports or variables     |
| E402, E501             | Imports at top, lines ≤120 chars   |
| C901, PLR0912, PLR0915 | Functions must be small and simple |
| PLR0911, RET504        | No redundant `else` after `return` |
| B008                   | No mutable default arguments       |
| T201                   | No `print()` statements            |
| SIM102                 | Prefer `if x` over `if x == True`  |

#### Additional Style Rules

-   Prefer **one return statement per function** unless early returns improve clarity
-   Use `@dataclass` for plain data containers

### Code Structure & Organization

#### Python Module Order

Organize all Python files in this order:

1. **Imports**

    ```python
    # Standard library
    import asyncio
    from datetime import datetime

    # Third-party (Home Assistant)
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import Entity

    # Local
    from .const import DOMAIN
    from .data import PriceData
    ```

2. **Module-level constants**

    ```python
    _LOGGER = logging.getLogger(__name__)
    DOMAIN = "tibber_prices"
    CONF_API_TOKEN = "api_token"
    DEFAULT_SCAN_INTERVAL = 3600
    ```

3. **Top-level functions**

    - Public API/entry points first (e.g., `async_setup_entry`)
    - Direct helpers second (in call order)
    - Pure utility functions last
    - Internal functions prefixed with `_`
    - Order functions so callers appear before callees when possible
    - Group related functions logically

4. **Main classes**

    - Entity classes, DataUpdateCoordinators, ConfigFlow handlers
    - Order within class: `__init__`, `__repr__`, public methods, private methods
    - All I/O methods must be `async def`

5. **Helper classes**
    - Move complex helpers to separate modules (`helpers.py`, `models.py`)

#### Optional Folding Regions

Use `#region` / `#endregion` comments in large files for readability:

```python
#region Helper Functions

def _calculate_rating(price: float, avg: float) -> float:
    """Calculate price rating."""
    return (price / avg) * 100

#endregion
```

### File Structure Best Practices

Standard integration files:

| File                  | Purpose                                 | Required                                   |
| --------------------- | --------------------------------------- | ------------------------------------------ |
| `__init__.py`         | Setup and teardown                      | ✅ Yes                                     |
| `manifest.json`       | Metadata and dependencies               | ✅ Yes                                     |
| `const.py`            | Constants (DOMAIN, CONF*\*, DEFAULT*\*) | ✅ Yes                                     |
| `config_flow.py`      | UI configuration                        | ✅ Yes (this integration uses config flow) |
| `sensor.py`           | Sensor platform                         | ✅ Yes                                     |
| `binary_sensor.py`    | Binary sensor platform                  | ✅ Yes                                     |
| `coordinator.py`      | Data update coordinator                 | ✅ Yes                                     |
| `entity.py`           | Base entity classes                     | ⚠️ Optional                                |
| `data.py`             | Data models (@dataclass)                | ⚠️ Optional                                |
| `api.py`              | External API client                     | ⚠️ Optional                                |
| `services.py`         | Custom services                         | ⚠️ Optional                                |
| `services.yaml`       | Service definitions                     | ⚠️ Optional                                |
| `diagnostics.py`      | Diagnostic data                         | ⚠️ Optional                                |
| `translations/*.json` | UI translations                         | ⚠️ Optional                                |

**Do NOT create** (these are for Core integrations only):

-   `device_action.py`, `device_trigger.py`, `device_condition.py`
-   `strings.json` (use `translations/` instead)

### Backwards Compatibility Policy

**IMPORTANT**: Do **NOT** implement backward compatibility features unless explicitly requested.

-   Assume a clean, modern codebase
-   Target latest stable Home Assistant only
-   No deprecated function support
-   No compatibility workarounds or layers
-   **Ask first** if you think backward compatibility is needed

### Translations Management

This integration has two translation directories:

#### `/translations/` (Standard Home Assistant Translations)

-   For all standard Home Assistant UI strings (config flow, options, entity names, etc.)
-   **MUST** be kept in sync across all language files
-   All keys in `en.json` must exist in all other language files
-   Non-English files can use placeholder values if translation unavailable

#### `/custom_translations/` (Supplemental Translations)

-   For UI strings not supported by standard Home Assistant translation format
-   Only use if the string cannot be handled in `/translations/`
-   Never duplicate keys between `/translations/` and `/custom_translations/`
-   Standard translations always take priority

#### Translation Rules

1. When adding a translation key to `en.json`, update **ALL** language files
2. When removing/renaming a key, update **ALL** language files
3. Never duplicate keys between standard and custom translations
4. Keep both directories in sync with their respective English base files

### Data Structures

Use `@dataclass` for data containers:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PriceSlot:
    """Represents a single price time slot."""
    start: datetime
    end: datetime
    price: float
    level: str
```

### Testing

This integration **does not include comprehensive automated tests** by default.

-   If generating tests, keep them minimal
-   Do not introduce new test frameworks
-   Use existing test structure in `tests/` directory

## Dependencies

### Runtime Dependencies

Defined in `manifest.json`:

```json
{
    "homeassistant": "2024.1.0",
    "requirements": ["aiofiles>=23.2.1"]
}
```

### Development Dependencies

Defined in `requirements.txt`:

```
colorlog>=6.9.0,<7.0.0
homeassistant>=2025.11.0,<2025.12.0
pytest-homeassistant-custom-component>=0.13.0,<0.14.0
pip>=21.3.1
ruff>=0.11.6,<0.15.0
```

### Configuration Files

-   **pyproject.toml**: Black (line-length: 120, target: py313) and isort config
-   **.ruff.toml**: Comprehensive linting rules (based on Home Assistant Core)
-   **.devcontainer/**: VS Code devcontainer with Python 3.13

## Working with the Integration

### Understanding the Domain

-   **Domain**: `tibber_prices`
-   **API**: Tibber GraphQL API
-   **Authentication**: API access token (from developer.tibber.com)
-   **Update Method**: Cloud polling (`iot_class: cloud_polling`)

### Entity Types

The integration provides:

1. **Sensors** (`sensor.py`):

    - Price sensors (current, next hour)
    - Statistical sensors (min, max, average)
    - Rating sensors (quarterly-hour, daily, monthly)
    - Diagnostic sensors (last update, tomorrow's data status)

2. **Binary Sensors** (`binary_sensor.py`):
    - Peak hour detection
    - Best price hour detection
    - API connection status

### Data Flow

1. **Coordinator** (`coordinator.py`): Fetches data from Tibber API
2. **API Client** (`api.py`): Handles GraphQL requests
3. **Data Models** (`data.py`): Structures the data
4. **Entities** (sensors, binary sensors): Present data to Home Assistant

### Config Flow

The integration uses **UI-based configuration** (no YAML):

1. User enters Tibber API token
2. Config flow validates token
3. Integration creates entry
4. Coordinator starts fetching data

## Common Tasks

### Adding a New Sensor

1. Define constant in `const.py`
2. Add sensor class in `sensor.py` or `binary_sensor.py`
3. Update coordinator if new data needed
4. Add translation keys to `translations/en.json` (and other languages)
5. Test with `scripts/develop`
6. Run `scripts/lint` before committing

### Modifying API Calls

1. Update `api.py` with new GraphQL query
2. Update `data.py` if data structure changes
3. Update `coordinator.py` to handle new data
4. Update entities that consume the data

### Adding Translations

1. Add key to `translations/en.json`
2. Add same key to all other `translations/*.json` files
3. Use translation in code via translation key reference
4. Verify with Home Assistant UI

## Debugging

### Enable Debug Logging

In Home Assistant `configuration.yaml`:

```yaml
logger:
    default: info
    logs:
        custom_components.tibber_prices: debug
```

### Development Instance

The `scripts/develop` script starts Home Assistant with:

-   Debug mode enabled (`--debug`)
-   Custom component loaded from source
-   Configuration in `config/` directory
-   Logs visible in terminal

### Common Issues

1. **Import errors**: Check `PYTHONPATH` is set correctly
2. **API errors**: Verify Tibber token is valid
3. **Entity not appearing**: Check entity is enabled in Home Assistant
4. **Translation not showing**: Verify all language files have the key

## Git Workflow

1. Create feature branch from `main`
2. Make changes following guidelines above
3. Run `scripts/lint` to ensure code quality
4. Test with `scripts/develop`
5. Commit with descriptive message
6. Create pull request to `main`

### Commit Messages

Follow conventional commit style:

```
feat: add monthly price statistics sensor
fix: correct timezone handling for price data
docs: update README with new sensor information
refactor: simplify coordinator data parsing
test: add tests for price level calculation
```

## Resources

-   **Home Assistant Developer Docs**: https://developers.home-assistant.io
-   **Tibber API**: https://developer.tibber.com
-   **Repository**: https://github.com/jpawlowski/hass.tibber_prices
-   **Issues**: https://github.com/jpawlowski/hass.tibber_prices/issues
-   **HACS**: https://hacs.xyz

## Summary Checklist

Before committing any changes, ensure:

-   [ ] Code follows PEP8 and project style guidelines
-   [ ] All functions have type hints and docstrings
-   [ ] No `print()` statements (use `_LOGGER`)
-   [ ] Code runs without errors with `scripts/develop`
-   [ ] `scripts/lint` passes without errors
-   [ ] All translation files are in sync
-   [ ] No backward compatibility code added (unless requested)
-   [ ] Changes documented in code comments (logic only, not process)
-   [ ] Tested in development Home Assistant instance

## Notes for AI Agents

1. **Always read this file first** before making changes
2. **Check existing code patterns** before implementing new features
3. **Use semantic_search** to find similar implementations in the codebase
4. **Ask for clarification** if requirements are ambiguous
5. **Test changes** with development environment before finalizing
6. **Keep changes minimal** and focused on the specific task
7. **Follow the style guide strictly** - automated checks will enforce this
8. **Update translations** whenever user-facing strings change
9. **Document only logic** in code comments, not automated refactoring actions
10. **Assume modern codebase** - no legacy support unless explicitly requested

---

**Last Updated**: 2025-11-02
**Project Version**: 0.1.0
**Home Assistant Minimum Version**: 2024.1.0
**Python Version**: 3.13
