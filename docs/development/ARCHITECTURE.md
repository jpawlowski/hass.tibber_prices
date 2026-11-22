# Architecture Overview

This document describes the technical architecture of the Tibber Prices & Planning custom component for Home Assistant.

## Directory Structure

```text
custom_components/tibber_prices/
├── __init__.py              # Integration setup and unload
├── config_flow.py           # Config flow entry point
├── const.py                 # Constants and configuration keys
├── coordinator/             # Data update coordinator package
│   ├── __init__.py          # Exports TibberPricesDataUpdateCoordinator
│   └── base.py              # Main coordinator class
├── data.py                  # Data classes and type definitions
├── diagnostics.py           # Diagnostic data for troubleshooting
├── entity/                  # Base entity package
│   ├── __init__.py          # Exports TibberPricesEntity
│   └── base.py              # Base entity class implementation
├── icons.json               # Entity and service action icons
├── manifest.json            # Integration metadata
├── repairs.py               # Repair flows for fixing issues
├── services.yaml            # Service action definitions (legacy filename)
├── api/                     # External API communication
│   ├── __init__.py
│   └── client.py            # API client implementation
├── config_flow_handler/     # Config flow implementation
│   ├── __init__.py          # Package exports
│   ├── config_flow.py       # Main config flow (user, reauth, reconfigure)
│   ├── options_flow.py      # Options flow
│   ├── schemas/             # probatio schemas
│   │   ├── __init__.py      # Schema exports
│   │   ├── config.py        # Config flow schemas
│   │   └── options.py       # Options flow schemas
│   └── validators/          # Input validation
│       ├── __init__.py      # Validator exports
│       └── credentials.py   # Credential validation
├── service_actions/         # Service action implementations
│   ├── __init__.py          # Registration in async_setup()
│   └── refresh_data.py      # The refresh_data handler
├── translations/            # Localization files
│   └── en.json              # English translations
└── <platform>/              # Platform-specific implementations
    ├── __init__.py          # Platform setup and PARALLEL_UPDATES
    └── <entity>.py          # Entity descriptions and entity class
```

`entity_utils/` and `utils/` are part of the permitted package set in
[`AGENTS.md`](../../AGENTS.md) but do not exist until something needs them — an entity helper
used by three or more entity classes, or an integration-wide utility.

## Core Components

### Data Update Coordinator

**Directory:** `coordinator/`

The coordinator fetches the device state once per interval and hands the same payload to every
entity, so no entity ever calls the API itself.

**Core functionality:**

- A fixed one-hour update interval (`UPDATE_INTERVAL`), chosen by the developer rather than the user
- Translation of API client exceptions into `ConfigEntryAuthFailed` and `UpdateFailed`
- Raising and clearing the repair issue for the deprecated API version

**Key class:** `TibberPricesDataUpdateCoordinator` (exported from `coordinator/__init__.py`)

Retries and backoff are **not** implemented here. Home Assistant already retries `UpdateFailed`
with exponential backoff, and failures are logged by Home Assistant, not by the coordinator.

**Design rationale:**

The coordinator is a package rather than a single file so that transform helpers, a cache or a
push listener can be added as separate modules once they are needed — each staying under the
200–400 line guideline and testable on its own.

### API Client

**Directory:** `api/`

Handles all communication with external APIs or devices. Implements:

- Async HTTP requests using `aiohttp`
- Connection management and timeouts
- Authentication handling
- Error translation to custom exceptions

**Key class:** `TibberPricesApiClient`

### Config Flow

**Directory:** `config_flow_handler/`

Implements the configuration UI for adding and configuring the integration. The package
is organized modularly to support complex flows without becoming monolithic.

**Structure:**

- `config_flow.py`: Main flow (user setup, reauth, reconfigure)
- `options_flow.py`: Options flow for post-setup configuration
- `schemas/`: probatio schemas for all forms
- `validators/`: Validation logic separated from flow logic

**Supported flows:**

- Initial user setup with validation
- Options flow for the filter replacement threshold
- Reauthentication flow for expired credentials
- Reconfiguration of the stored credentials

A subentry flow goes in `config_flow_handler/subentry_flow.py` when the integration grows to
need one; see [`ha-config-flow`](../../.agents/skills/ha-config-flow/SKILL.md).

**Key classes:**

- `TibberPricesConfigFlowHandler` (main flow)
- `TibberPricesOptionsFlow` (options)

### Base Entity

**Package:** `entity/`

Provides common functionality for all entities in the integration:

- Device information
- Unique ID generation
- Coordinator integration
- Availability tracking

**Key class:** `TibberPricesEntity` (in `entity/base.py`)

## Platform Organization

Each platform (sensor, binary_sensor, switch, etc.) follows this pattern:

```text
<platform>/
├── __init__.py              # Platform setup: async_setup_entry()
└── <entity_name>.py         # Individual entity implementation
```

Platform entities inherit from both:

1. Home Assistant platform base (e.g., `SensorEntity`)
2. `TibberPricesEntity` for common functionality

## Data Flow

```text
┌─────────────────┐
│  Config Entry   │ ← Created by config flow
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Coordinator   │ ← Fetches data from API every 5 min
└────────┬────────┘
         │
         ▼
    ┌────┴────┐
    │  Data   │ ← Stored in coordinator.data
    └────┬────┘
         │
    ┌────┴────────────────┐
    │                     │
    ▼                     ▼
┌─────────┐         ┌─────────┐
│ Sensor  │         │ Switch  │ ← Entities read from coordinator
└─────────┘         └─────────┘
```

## AI Agent Context

Agent-facing content is layered so each piece is loaded only when it is relevant:

| Layer                             | Loaded                      | Contains                                          |
| --------------------------------- | --------------------------- | ------------------------------------------------- |
| `AGENTS.md`                       | always                      | project identity, workflow rules, validation loop |
| `.agents/instructions/*.md`       | per touched file            | passive style rules for one file type             |
| `.agents/skills/*/SKILL.md`       | when a task matches         | active procedures for a specific kind of work     |
| `docs/development/`, `docs/user/` | when a human or agent reads | explanations, decisions, guides — this document   |

Style rules belong in `.agents/instructions/`, procedures belong in a skill, explanations belong in `docs/`.

One copy of each instruction file serves two agents: GitHub Copilot and VS Code match its `applyTo` glob string,
Claude Code matches the same patterns via `paths` (a YAML list, one pattern per item) and reaches the same files
through the `.claude/rules/instructions` symlink. Codex and OpenCode have no comparable file-triggered mechanism —
their nested `AGENTS.md` support keys off the working directory or the files read, not on file-type patterns — so
they rely on the root `AGENTS.md` plus the pointers each skill carries.

The skill catalogue, the symlink layout that makes one directory work for every agent vendor, and the rules for writing
a new skill are documented in [`.agents/skills/README.md`](../../.agents/skills/README.md).

For working with AI coding agents in this repository, see [`AI_AGENTS.md`](./AI_AGENTS.md).

## Key Design Decisions

Architectural and design decisions made during development are records in [decisions/](decisions/README.md).

## Extension Points

To add new functionality:

### Adding a New Platform

1. Create directory: `custom_components/tibber_prices/<platform>/`
2. Implement `__init__.py` with `async_setup_entry()`
3. Create entity classes inheriting from platform base + `TibberPricesEntity`
4. Add platform to `PLATFORMS` in `__init__.py`

### Adding a New Service Action

1. Create service action handler in `service_actions/<service_name>.py`
2. Define service action in `services.yaml` (legacy filename) with schema
3. Register service action in `__init__.py:async_setup()` (NOT `async_setup_entry`)

### Modifying Data Structure

1. Update coordinator data type in `coordinator.py`
2. Adjust API client response parsing in `api/client.py`
3. Update entity property implementations to match new structure

## Testing Strategy

- **Unit tests:** Test individual functions and classes in isolation
- **Integration tests:** Test coordinator with mocked API
- **Fixtures:** Shared test fixtures in `tests/conftest.py`

Tests mirror the source structure under `tests/`.

## Dependencies

Core dependencies (see `manifest.json`):

- `aiohttp` - Async HTTP client
- Home Assistant 2025.7.0+ - Platform requirements

Development dependencies (see `requirements_dev.txt`, `requirements_test.txt`).
