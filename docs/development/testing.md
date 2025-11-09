# Testing

> **Note:** This guide is under construction.

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
- Configuration flow
- Sensor states and attributes
- Services
- Translation strings

## Test Guidelines

Coming soon...
