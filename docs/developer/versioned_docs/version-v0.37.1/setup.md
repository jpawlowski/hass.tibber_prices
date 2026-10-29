# Development Setup

> **Note:** This guide is under construction. For now, please refer to [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.37.1/AGENTS.md) for detailed setup information.

## Prerequisites

- VS Code with Dev Container support
- Docker installed and running
- GitHub account (for Tibber API token)

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

- Python (the version Home Assistant is built on, see `.python-version`) with `.venv` at `/home/vscode/.venv/`
- `uv` package manager (fast, modern Python tooling)
- Home Assistant development dependencies
- Ruff linter/formatter
- Git, GitHub CLI, Node.js, pyright, git-cliff, shellcheck, shfmt, yq

### Tool Versions (mise)

The development tools are managed by [mise](https://mise.jdx.dev): their versions are pinned in `mise.toml` in the project root, and the same file is used in the DevContainer, in CI and locally. The Python version is the exception: it lives in `.python-version`, which `./scripts/setup/update-ha-version` keeps at the version the configured Home Assistant release is built on.

- **Update a tool**: change its version in `mise.toml`, then run `mise install`
- **Outside the DevContainer**: [install mise](https://mise.jdx.dev/getting-started.html), then run `mise install` in the project root
- Python packages (Home Assistant and its dependencies) are not managed by mise but by `uv` in `./scripts/setup/bootstrap`

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

See [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.37.1/AGENTS.md) for detailed patterns and conventions.
