# Architecture

> **Note:** This guide is under construction. For now, please refer to `.github/copilot-instructions.md` for detailed architecture information.

## Core Components

### Data Flow
1. `TibberPricesApiClient` - GraphQL API client
2. `TibberPricesDataUpdateCoordinator` - Update orchestration & caching
3. Price enrichment functions - Statistical calculations
4. Entity platforms - Sensors and binary sensors
5. Custom services - API endpoints

### Key Patterns

- **Dual translation system**: `/translations/` (HA schema) + `/custom_translations/` (extended)
- **Price enrichment**: 24h trailing/leading averages, ratings, differences
- **Quarter-hour precision**: Entity updates on 00/15/30/45 boundaries
- **Intelligent caching**: User data (24h), price data (calendar day validation)

See `.github/copilot-instructions.md` "Architecture Overview" section for complete details.
