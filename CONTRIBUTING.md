# Contributing to Tibber Prices Integration

Thank you for your interest in contributing! This document provides guidelines for contributing to this Home Assistant custom integration.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [Coding Standards](#coding-standards)
- [Submitting Changes](#submitting-changes)
- [Documentation](#documentation)

For detailed developer documentation, see [docs/development/](docs/development/).

> **Note:** This project is developed with extensive AI assistance (GitHub Copilot, Claude). If you're also using AI tools, check [`AGENTS.md`](/AGENTS.md) for patterns and conventions that ensure consistency.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/hass.tibber_prices.git
   cd hass.tibber_prices
   ```
3. **Open in DevContainer** (recommended):
   - Open in VS Code
   - Click "Reopen in Container" when prompted
   - Or manually: `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"

See [Development Setup](docs/development/setup.md) for detailed instructions.

## Development Process

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Changes

- Follow the [Coding Guidelines](docs/development/coding-guidelines.md)
- Keep changes focused and atomic
- Update documentation if needed

### 3. Test Your Changes

```bash
# Lint and format
./scripts/lint

# Start development environment
./scripts/develop

# Run tests (if available)
pytest tests/
```

### 4. Commit Your Changes

We use **Conventional Commits** format:

```
<type>(<scope>): <short summary>

<detailed description>

Impact: <user-visible effects>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `chore`, `test`

**Example:**
```bash
git commit -m "feat(sensors): add daily average price sensor

Added new sensor that calculates average price for the entire day.

Impact: Users can now track daily average prices for cost analysis."
```

See [`AGENTS.md`](AGENTS.md) section "Git Workflow Guidance" for detailed guidelines.

## Submitting Changes

### Pull Request Process

1. **Push your branch** to your fork
2. **Create a Pull Request** on GitHub with:
   - Clear title describing the change
   - Detailed description with context
   - Reference related issues (`Fixes #123`)
3. **Wait for review** and address feedback

### PR Requirements

- ✅ Code passes `./scripts/lint-check`
- ✅ No breaking changes (or clearly documented)
- ✅ Translations updated for all languages
- ✅ Commit messages follow Conventional Commits
- ✅ Changes tested in Home Assistant

## Coding Standards

### Code Style

- **Formatter/Linter**: Ruff (enforced automatically)
- **Max line length**: 120 characters
- **Python version**: 3.13+

Always run before committing:
```bash
./scripts/lint
```

### Key Patterns

- Use `dt_util` from `homeassistant.util` for all datetime operations
- Load translations asynchronously at integration setup
- Enrich price data before exposing to entities
- Follow Home Assistant entity naming conventions

See [Coding Guidelines](docs/development/coding-guidelines.md) for complete details.

## Documentation

- **User guides**: Place in `docs/user/` (installation, configuration, usage)
- **Developer guides**: Place in `docs/development/` (architecture, patterns)
- **Update translations**: When changing `translations/en.json`, update ALL language files

## Reporting Bugs

Report bugs via [GitHub Issues](../../issues/new/choose).

**Great bug reports include:**
- Quick summary and background
- Steps to reproduce (be specific!)
- Expected vs. actual behavior
- Sample code/logs if applicable

## Questions?

- Check [Developer Documentation](docs/development/)
- Read [Copilot Instructions](AGENTS.md) for patterns
- Search [existing issues](https://github.com/jpawlowski/hass.tibber_prices/issues)
- Open a [new issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new)

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
