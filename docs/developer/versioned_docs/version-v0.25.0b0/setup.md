# Development Setup

> **Note:** This guide is under construction. For now, please refer to [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.25.0b0/AGENTS.md) for detailed setup information.

## Prerequisites

-   VS Code with Dev Container support
-   Docker installed and running
-   GitHub account (for Tibber API token)

## Quick Setup

```bash
# Clone the repository
git clone https://github.com/jpawlowski/hass.tibber_prices.git
cd hass.tibber_prices

# Open in VS Code
code .

# Reopen in DevContainer (VS Code will prompt)
# Or manually: Ctrl+Shift+P → "Dev Containers: Reopen in Container"
```

## Development Environment

The DevContainer includes:

-   Python 3.13 with `.venv` at `/home/vscode/.venv/`
-   `uv` package manager (fast, modern Python tooling)
-   Home Assistant development dependencies
-   Ruff linter/formatter
-   Git, GitHub CLI, Node.js, Rust toolchain

## Running the Integration

```bash
# Start Home Assistant in debug mode
./scripts/develop
```

Visit http://localhost:8123

## Making Changes

```bash
# Lint and format code
./scripts/lint

# Check-only (CI mode)
./scripts/lint-check

# Validate integration structure
./scripts/release/hassfest
```

See [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.25.0b0/AGENTS.md) for detailed patterns and conventions.
