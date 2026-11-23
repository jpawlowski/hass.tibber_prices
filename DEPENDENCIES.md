# Dependencies Overview

This custom integration uses multiple requirements files to separate different types of dependencies:

## 📁 Files

### `requirements.txt` - Runtime Dependencies

**Purpose:** Python packages needed by the integration at runtime
**Installed by:** Home Assistant when loading the integration
**Also defined in:** `custom_components/tibber_prices/manifest.json`

**Note:** This file is typically empty if this integration has no additional runtime dependencies beyond Home Assistant core.

**Example:**

```txt
aiohttp>=3.8.0
async-timeout>=4.0.0
```

### `package.json` - Node.js Development Tools

**Purpose:** JavaScript/Node.js tools used for Markdown formatting and linting
**Installed by:** `script/setup/bootstrap` via `npm install`
**Used by:** Developers, IDEs, pre-commit hooks

**Includes:**

- `prettier` - Markdown formatter (also used by `esbenp.prettier-vscode` VS Code extension)
- `markdownlint-cli2` - Markdown linter (also used by `davidanson.vscode-markdownlint` VS Code extension)

**Note:** These tools are the CLI counterparts of the VS Code extensions already installed in the devcontainer. Having both ensures IDE and CI/pre-commit behaviour is identical.

### `requirements_dev.txt` - Development Tools

**Purpose:** Additional development tools beyond what Home Assistant core provides
**Installed by:** `script/setup/bootstrap`
**Used by:** Developers, IDEs

**Includes:**

- `pyright` - Type checker (we prefer pyright over HA's mypy for better IDE integration)
- `colorlog` - Colored logging for development scripts
- Performance tools (`zlib_ng`, `isal`) - Optional optimization packages

**Note:** Most development tools (ruff, pre-commit, codespell, pylint) are already provided by Home Assistant core's `requirements_test.txt` and `requirements_test_pre_commit.txt`, which are installed automatically via `script/setup/bootstrap`.

### `requirements_test.txt` - Testing Framework

**Purpose:** Additional testing tools beyond what Home Assistant core provides
**Installed by:** `script/setup/bootstrap`
**Used by:** Test runners, CI/CD

**Includes:**

- `pytest-homeassistant` - Test fixtures from Home Assistant Core, one release per Home Assistant version

**Note:** Core testing tools (pytest, pytest-asyncio, pytest-aiohttp, pytest-cov, pytest-timeout, pytest-xdist, coverage, freezegun, requests-mock, respx) are already provided by Home Assistant core's `requirements_test.txt`, which is installed automatically via `script/setup/bootstrap`.

## 🔄 Relationship with manifest.json

### manifest.json `requirements` field

```json
{
  "requirements": ["aiohttp>=3.8.0"]
}
```

- ✅ Runtime dependencies for end users
- ✅ Automatically installed by Home Assistant
- ✅ Should match `requirements.txt` content
- ℹ️ **Optional:** If this integration doesn't need additional packages beyond Home Assistant core, you can omit this field

### When to add dependencies

| Add to                               | When                                                         |
| ------------------------------------ | ------------------------------------------------------------ |
| `manifest.json` + `requirements.txt` | Runtime dependency (end users need it)                       |
| `requirements_dev.txt`               | Python development tool (linting, formatting, type checking) |
| `requirements_test.txt`              | Testing tool (pytest plugins, test utilities)                |
| `package.json`                       | Node.js development tool (Markdown formatting/linting)       |

## 📝 Maintenance

When you add a runtime dependency:

1. ✅ Add to `manifest.json` `requirements` field
2. ✅ Add to `requirements.txt` (same version constraint)
3. ❌ Don't add to `requirements_dev.txt` or `requirements_test.txt`

**Example:**

```json
// manifest.json
{
  "requirements": ["aiohttp>=3.8.0"]
}
```

```txt
# requirements.txt
aiohttp>=3.8.0
```

## 🚀 Bootstrap Script

The `script/setup/bootstrap` automatically installs dependencies from multiple sources:

### From Home Assistant Core

**Version:** Configured via `HA_VERSION` in `.devcontainer/devcontainer.json` (currently `2025.12.3`)

1. **Runtime dependencies** (`requirements_all.txt`)
   - All packages that Home Assistant integrations might need
   - Includes aiohttp, async-timeout, and hundreds of other packages

2. **Test dependencies** (`requirements_test.txt`)
   - pytest and all pytest plugins (pytest-asyncio, pytest-aiohttp, pytest-cov, pytest-timeout, pytest-xdist)
   - Testing utilities (coverage, freezegun, requests-mock, respx)
   - mypy-dev for type checking (we use pyright instead)

3. **Pre-commit dependencies** (`requirements_test_pre_commit.txt`)
   - ruff (linting and formatting)
   - codespell (spell checking)
   - pre-commit (hook framework)
   - pylint (linting)

4. **Home Assistant core** (`homeassistant==$HA_VERSION`)
   - The full Home Assistant installation

### From This Project

- `requirements_dev.txt` - Additional development tools this project uses (pyright, colorlog, performance packages)
- `requirements_test.txt` - Custom component testing utilities
- `requirements.txt` - This integration's runtime dependencies (if any)
- `package.json` - Node.js tools for Markdown linting/formatting (prettier, markdownlint-cli2)

This approach means this project only needs to maintain a minimal set of dependencies that are specific to this integration, while leveraging the comprehensive dependency management from Home Assistant core.

## 🔍 hacs.json vs manifest.json

### hacs.json

```json
{
  "name": "Integration Name",
  "homeassistant": "2025.11.0",
  "hacs": "2.0.5"
}
```

- ❌ **No Python dependencies** - only metadata
- ✅ Minimum Home Assistant version, read by the Marketplace (Home Assistant 2026.11+) and by HACS
- ✅ Minimum HACS version, only compared by HACS before 2026.11 — keep it while `homeassistant` is older than that

### manifest.json

```json
{
  "requirements": ["package>=1.0.0"]
}
```

- ✅ **Python package dependencies**
- ✅ Installed by Home Assistant

**No duplication needed!** `hacs.json` only contains version constraints for Home Assistant and HACS, not Python packages.
