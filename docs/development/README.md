# Developer Documentation

This section contains documentation for contributors and maintainers of the Tibber Prices integration.

## 📚 Developer Guides

-   **[Setup](setup.md)** - DevContainer, environment setup, and dependencies
-   **[Architecture](architecture.md)** - Code structure, patterns, and conventions
-   **[Timer Architecture](timer-architecture.md)** - Timer system, scheduling, coordination (3 independent timers)
-   **[Caching Strategy](caching-strategy.md)** - Cache layers, invalidation, debugging
-   **[Testing](testing.md)** - How to run tests and write new test cases
-   **[Release Management](release-management.md)** - Release workflow and versioning process
-   **[Coding Guidelines](coding-guidelines.md)** - Style guide, linting, and best practices
-   **[Refactoring Guide](refactoring-guide.md)** - How to plan and execute major refactorings

## 🤖 AI Documentation

The main AI/Copilot documentation is in [`AGENTS.md`](../../AGENTS.md). This file serves as long-term memory for AI assistants and contains:

-   Detailed architectural patterns
-   Code quality rules and conventions
-   Development workflow guidance
-   Common pitfalls and anti-patterns
-   Project-specific patterns and utilities

**Important:** When proposing changes to patterns or conventions, always update [`AGENTS.md`](../../AGENTS.md) to keep AI guidance consistent.

### AI-Assisted Development

This integration is developed with extensive AI assistance (GitHub Copilot, Claude, and other AI tools). The AI handles:

-   **Pattern Recognition**: Understanding and applying Home Assistant best practices
-   **Code Generation**: Implementing features with proper type hints, error handling, and documentation
-   **Refactoring**: Maintaining consistency across the codebase during structural changes
-   **Translation Management**: Keeping 5 language files synchronized
-   **Documentation**: Generating and maintaining comprehensive documentation

**Quality Assurance:**

-   Automated linting with Ruff (120-char line length, max complexity 25)
-   Home Assistant's type checking and validation
-   Real-world testing in development environment
-   Code review by maintainer before merging

**Benefits:**

-   Rapid feature development while maintaining quality
-   Consistent code patterns across all modules
-   Comprehensive documentation maintained alongside code
-   Quick bug fixes with proper understanding of context

**Limitations:**

-   AI may occasionally miss edge cases or subtle bugs
-   Some complex Home Assistant patterns may need human review
-   Translation quality depends on AI's understanding of target language
-   User feedback is crucial for discovering real-world issues

If you're working with AI tools on this project, the [`AGENTS.md`](../../AGENTS.md) file provides the context and patterns that ensure consistency.

## 🚀 Quick Start for Contributors

1. **Fork and clone** the repository
2. **Open in DevContainer** (VS Code: "Reopen in Container")
3. **Run setup**: `./scripts/setup` (happens automatically via `postCreateCommand`)
4. **Start development environment**: `./scripts/develop`
5. **Make your changes** following the [Coding Guidelines](coding-guidelines.md)
6. **Run linting**: `./scripts/lint`
7. **Validate integration**: `./scripts/hassfest`
8. **Test your changes** in the running Home Assistant instance
9. **Commit using Conventional Commits** format
10. **Open a Pull Request** with clear description

## 🛠️ Development Tools

The project includes several helper scripts in `./scripts/`:

-   `bootstrap` - Initial setup of dependencies
-   `develop` - Start Home Assistant in debug mode (auto-cleans .egg-info)
-   `clean` - Remove build artifacts and caches
-   `lint` - Auto-fix code issues with ruff
-   `lint-check` - Check code without modifications (CI mode)
-   `hassfest` - Validate integration structure (JSON, Python syntax, required files)
-   `setup` - Install development tools (git-cliff, @github/copilot)
-   `prepare-release` - Prepare a new release (bump version, create tag)
-   `generate-release-notes` - Generate release notes from commits

## 📦 Project Structure

```
custom_components/tibber_prices/
├── __init__.py           # Integration setup
├── coordinator.py        # Data update coordinator with caching
├── api.py               # Tibber GraphQL API client
├── price_utils.py       # Price enrichment functions
├── average_utils.py     # Average calculation utilities
├── sensor/              # Sensor platform (package)
│   ├── __init__.py      #   Platform setup
│   ├── core.py          #   TibberPricesSensor class
│   ├── definitions.py   #   Entity descriptions
│   ├── helpers.py       #   Pure helper functions
│   └── attributes.py    #   Attribute builders
├── binary_sensor.py     # Binary sensor platform
├── entity_utils/        # Shared entity helpers
│   ├── icons.py         #   Icon mapping logic
│   ├── colors.py        #   Color mapping logic
│   └── attributes.py    #   Common attribute builders
├── services.py          # Custom services
├── config_flow.py       # UI configuration flow
├── const.py             # Constants and helpers
├── translations/        # Standard HA translations
└── custom_translations/ # Extended translations (descriptions)
```

## 🔍 Key Concepts

**DataUpdateCoordinator Pattern:**

-   Centralized data fetching and caching
-   Automatic entity updates on data changes
-   Persistent storage via `Store`
-   Quarter-hour boundary refresh scheduling

**Price Data Enrichment:**

-   Raw API data is enriched with statistical analysis
-   Trailing/leading 24h averages calculated per interval
-   Price differences and ratings added
-   All via pure functions in `price_utils.py`

**Translation System:**

-   Dual system: `/translations/` (HA schema) + `/custom_translations/` (extended)
-   Both must stay in sync across all languages (de, en, nb, nl, sv)
-   Async loading at integration setup

## 🧪 Testing

```bash
# Validate integration structure
./scripts/hassfest

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_coordinator.py

# Run with coverage
pytest --cov=custom_components.tibber_prices tests/
```

## 📝 Documentation Standards

-   **User-facing docs** go in `docs/user/`
-   **Developer docs** go in `docs/development/`
-   **AI guidance** goes in `AGENTS.md`
-   Use clear examples and code snippets
-   Keep docs up-to-date with code changes

## 🤝 Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for detailed contribution guidelines, code of conduct, and pull request process.

## 📄 License

This project is licensed under [LICENSE](../../LICENSE).

---

**Note:** This documentation is for developers. End users should refer to the [User Documentation](../user/).
