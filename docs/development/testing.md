# Testing

> **Note:** This guide is under construction.

## Integration Validation

Before running tests or committing changes, validate the integration structure:

```bash
# Run local validation (JSON syntax, Python syntax, required files)
./scripts/hassfest
```

This lightweight script checks:

-   ✓ `config_flow.py` exists
-   ✓ `manifest.json` is valid JSON with required fields
-   ✓ Translation files have valid JSON syntax
-   ✓ All Python files compile without syntax errors

**Note:** Full hassfest validation runs in GitHub Actions on push.

## Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_coordinator.py

# Run with coverage
pytest --cov=custom_components.tibber_prices tests/
```

## Manual Testing

```bash
# Start development environment
./scripts/develop
```

Then test in Home Assistant UI:

-   Configuration flow
-   Sensor states and attributes
-   Services
-   Translation strings

## Test Guidelines

Coming soon...
