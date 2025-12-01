# Copilot Instructions

This is a **Home Assistant custom component** for Tibber electricity price data, distributed via **HACS**. It fetches, caches, and enriches **quarter-hourly** electricity prices with statistical analysis, price levels, and ratings.

## Documentation Metadata

-   **Last Major Update**: 2025-01-21
-   **Last Architecture Review**: 2025-01-21 (Phase 1: Added TypedDict documentation system, improved BaseCalculator with 8 helper methods. Phase 2: Documented Import Architecture - Hybrid Pattern (Trend/Volatility build own attributes), verified no circular dependencies, confirmed optimal TYPE_CHECKING usage across all 8 calculators.)
-   **Last Code Example Cleanup**: 2025-11-18 (Removed redundant implementation details from AGENTS.md, added guidelines for when to include code examples)
-   **Documentation Status**: ✅ Current (verified against codebase)

_Note: When proposing significant updates to this file, update the metadata above with the new date and brief description of changes._

## Maintaining This Documentation

**CRITICAL: This file is the AI's long-term memory across sessions.**

When working with the codebase, Copilot MUST actively maintain consistency between this documentation and the actual code:

**Scope:** "This documentation" and "this file" refer specifically to `AGENTS.md` in the repository root. This does NOT include user-facing documentation like `README.md`, `/docs/user/`, or comments in code. Those serve different purposes and are maintained separately.

**Documentation Organization:**

-   **This file** (`AGENTS.md`): AI/Developer long-term memory, patterns, conventions
-   **`docs/user/`**: End-user guides (installation, configuration, usage examples)
-   **`docs/development/`**: Contributor guides (setup, architecture, release management)
-   **`README.md`**: Project overview with links to detailed documentation

**Automatic Inconsistency Detection:**

-   When code changes affect documented patterns, examples, file paths, function names, or architectural decisions **in this file**, IMMEDIATELY flag the inconsistency
-   If a documented function is renamed, moved, or deleted → suggest documentation update
-   If file structure changes (files moved/renamed/deleted) → suggest path updates
-   If implementation patterns change (e.g., new translation structure, different caching approach) → suggest pattern documentation update
-   If new learnings emerge during debugging or development → suggest adding to documentation

**Documentation Update Process:**

1. **Detect** inconsistency or valuable new learning during work
2. **ALWAYS ask first** before modifying this file - propose what should be changed/added and explain WHY
3. **Wait for approval** from user
4. **Apply changes** only after confirmation
5. Keep proposals concise but specific (rough outline acceptable, not full text required)

**When to discuss in chat vs. direct file changes:**

-   **Make direct changes when:**

    -   Clear, straightforward task (fix bug, add function, update config)
    -   Single approach is obvious
    -   User request is specific ("add X", "change Y to Z")
    -   Quick iteration is needed (user can review diff and iterate)

-   **Discuss/show in chat first when:**
    -   Multiple valid approaches exist (architectural decision)
    -   Significant refactoring affecting many files
    -   Unclear requirements need clarification
    -   Trade-offs need discussion (performance vs. readability, etc.)
    -   User asks open-ended question ("how should we...", "what's the best way...")

**Goal:** Save time. File edits with VS Code tracking are fast for simple changes. Chat discussion is better for decisions requiring input before committing to an approach.

**Code Examples in AGENTS.md - When and How:**

**CRITICAL:** Code examples in this file are **conceptual illustrations**, NOT implementation references. They demonstrate patterns and architectural decisions, but may not match actual code exactly.

**When to include code examples:**

✅ **DO include examples for:**

-   **Architectural patterns** - Show WHY a design decision was made (e.g., "direct method pattern vs Callable pattern")
-   **Non-obvious patterns** - Illustrate unusual HA-specific patterns not documented elsewhere (e.g., selector translation structure)
-   **Decision rationale** - Demonstrate trade-offs between approaches (e.g., performance comparison with metrics)
-   **Configuration patterns** - Show structure of config files when format is critical (e.g., git-cliff.toml template)
-   **Best practices vs anti-patterns** - Side-by-side comparison of ✅ correct vs ❌ wrong approaches

❌ **DON'T include examples for:**

-   **Implementation details** - Code that duplicates what's in actual source files (e.g., full function implementations)
-   **API usage** - Standard library or HA API calls that are documented elsewhere (just reference the actual files)
-   **Entity definitions** - Complete SensorEntityDescription examples (just describe the pattern)
-   **Translation JSON** - Full translation file examples (just show the key structure pattern)
-   **Service schemas** - Complete schema definitions (reference services.py instead)

**Style for code examples:**

When code examples ARE justified:

1. **Keep them minimal** - Show only the concept, not full implementation
2. **Use comments liberally** - Explain WHY, not WHAT (code shows WHAT)
3. **Mark as conceptual** - Add comment like `# Conceptual - see actual_file.py for implementation`
4. **Prefer pseudo-code** - When illustrating logic flow, simplified pseudo-code > real code
5. **Reference actual files** - Always point to where the real implementation lives

**Example comparison:**

```python
# ❌ TOO DETAILED - duplicates actual code
def build_extra_state_attributes(
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    config_entry: TibberPricesConfigEntry,
    coordinator_data: dict,
    sensor_attrs: dict | None = None,
) -> dict[str, Any] | None:
    """Build extra state attributes for sensors."""
    timestamp = round_to_nearest_quarter_hour(dt_util.now())
    attributes = {"timestamp": timestamp.isoformat()}
    # ... 20 more lines ...

# ✅ GOOD - shows pattern, references implementation
# Pattern: Default timestamp → merge sensor_attrs → preserve ordering
# See sensor/attributes.py build_extra_state_attributes() for implementation
def build_extra_state_attributes(...) -> dict[str, Any] | None:
    # 1. Generate default timestamp (rounded quarter)
    # 2. Merge sensor-specific attributes (may override timestamp)
    # 3. Preserve timestamp ordering (always FIRST)
    # 4. Add description attributes inline (always LAST)
```

**Maintenance principle:**

If you notice yourself copying function signatures or implementation details from actual source files into AGENTS.md, STOP. Instead:

1. Describe the pattern/concept in words
2. Reference the actual file path
3. Only add minimal pseudo-code if the pattern is truly non-obvious

This prevents AGENTS.md from becoming outdated when code evolves, while still preserving the architectural knowledge and decision rationale that makes this file valuable.

**When to Propose Updates (with Confidence Levels):**

🔴 **HIGH Confidence** - Factual inconsistencies (flag immediately):

-   ✅ Documented function/class renamed, moved, or deleted
-   ✅ File paths changed (files moved/renamed/deleted)
-   ✅ Example code references non-existent code
-   ✅ Breaking changes to documented APIs or patterns

🟡 **MEDIUM Confidence** - Possible changes (ask for clarification):

-   ✅ Implementation pattern changed (might be intentional refactor)
-   ✅ New approach observed alongside documented old approach (unclear which is preferred)
-   ✅ Documented pattern still works but seems outdated

🟢 **LOW Confidence** - Suggestions for additions (propose when valuable):

-   ✅ New architectural pattern discovered during debugging (like the selector translation structure fix)
-   ✅ Important learnings that would help future sessions
-   ✅ User expressed wish for documentation
-   ✅ HA best practice learned that applies to this project

**Do NOT Propose Updates For:**

-   ❌ Temporary debugging code or experimental changes
-   ❌ Minor implementation details that don't affect understanding
-   ❌ Private helper function internals (unless part of documented pattern)
-   ❌ TODO comments (unless they represent architectural decisions)
-   ❌ Variable names or internal state (unless part of public API)

**Update Proposal Format:**
Include confidence level and impact in proposals:

> **[🔴 HIGH]** I noticed the translation pattern in AGENTS.md references `enrich_price_info_with_differences()` in `price_utils.py`, but this function was renamed to `enrich_prices()`.
>
> **Impact:** Future sessions will look for wrong function name.
>
> **Proposed change:** Update function name in "Price Data Enrichment" section.
>
> Should I update the documentation?

**Batch Updates:**
If you detect 3+ related minor changes (e.g., multiple constant renames during refactoring), propose them as one batch update instead of asking separately for each.

This ensures the documentation stays accurate and useful as the codebase evolves, while maintaining user control over what gets documented.

## Planning Major Refactorings

**Purpose**: Large-scale architectural changes require careful planning before implementation.

**Planning Directory**: `/planning/` (git-ignored, safe for iteration)

**When to Create a Planning Document:**

Create a detailed plan when:

-   🔴 **Major refactoring** (>5 files, >500 lines changed)
-   🔴 **Architectural changes** (new packages, module restructuring)
-   🔴 **Breaking changes** (API changes, config format migrations)
-   🟡 **Complex features** (multiple moving parts, unclear best approach)

Skip planning for:

-   🟢 Bug fixes (straightforward, <100 lines)
-   🟢 Small features (<3 files, clear approach)
-   🟢 Documentation updates
-   🟢 Cosmetic changes (formatting, renaming)

**Planning Document Lifecycle:**

1. **Planning Phase** (WIP in `/planning/`)

    - Create `planning/<feature>-refactoring-plan.md`
    - Iterate freely (git-ignored, no commit pressure)
    - AI can help refine without polluting git history
    - Multiple revisions until plan is solid

2. **Implementation Phase** (Active work)

    - Use plan as reference during coding
    - Update plan if issues discovered
    - Track progress through phases
    - Test after each phase

3. **Completion Phase** (After implementation)

    - **Option A**: Move to `docs/development/` if lasting value

        - Example: `planning/module-splitting-plan.md` → `docs/development/module-splitting-plan.md`
        - Update status to "✅ COMPLETED"
        - Commit as historical reference

    - **Option B**: Delete if superseded

        - Plan served its purpose
        - Code and AGENTS.md are source of truth

    - **Option C**: Archive in `planning/archive/`
        - Keep locally for "why we didn't do X" reference
        - Don't commit (git-ignored)

**Required Planning Document Sections:**

```markdown
# <Feature> Refactoring Plan

**Status**: 🔄 PLANNING | 🚧 IN PROGRESS | ✅ COMPLETED | ❌ CANCELLED
**Created**: YYYY-MM-DD
**Last Updated**: YYYY-MM-DD

## Problem Statement

-   What's the issue?
-   Why does it need fixing?
-   Current pain points

## Proposed Solution

-   High-level approach
-   File structure (before/after)
-   Module responsibilities

## Migration Strategy

-   Phase-by-phase breakdown
-   File lifecycle (CREATE/MODIFY/DELETE/RENAME)
-   Dependencies between phases
-   Testing checkpoints

## Risks & Mitigation

-   What could go wrong?
-   How to prevent it?
-   Rollback strategy

## Success Criteria

-   Measurable improvements
-   Testing requirements
-   Verification steps
```

**Example**: See `docs/development/module-splitting-plan.md` for a completed plan (moved from `planning/` after successful implementation).

**Integration with AGENTS.md:**

After successful refactoring:

1. Update AGENTS.md with new patterns/conventions
2. Move plan to `docs/development/` if valuable for future reference
3. Planning doc is temporary scaffolding; AGENTS.md is permanent guide

**Best Practices:**

✅ **DO:**

-   Iterate freely in `/planning/` (git-ignored)
-   Break complex changes into clear phases
-   Document file lifecycle explicitly
-   Include code examples and patterns
-   Plan testing after each phase

❌ **DON'T:**

-   Start coding before plan is solid
-   Skip the "Why?" section
-   Commit `/planning/` files (they're ignored!)
-   Over-plan trivial changes

## File Organization and Structure Policy

**CRITICAL: Keep integration root clean - only platform modules belong there.**

**Root Directory (`custom_components/tibber_prices/`):**

**✅ ALLOWED in root:**
-   Platform modules: `__init__.py`, `sensor.py` (deprecated, now `sensor/`), `binary_sensor.py` (deprecated, now `binary_sensor/`), future platforms
-   Core integration files: `const.py`, `manifest.json`, `services.yaml`, `diagnostics.py`, `data.py`
-   Translation directories: `translations/`, `custom_translations/`

**❌ PROHIBITED in root:**
-   Utility modules (use `/utils/` package instead)
-   Helper functions (use `/utils/` or appropriate package)
-   Data transformation logic (use `/utils/` or `/coordinator/`)
-   Any `*_utils.py` or `*_helpers.py` files

**Organized Packages:**

1. **`/utils/`** - Pure data transformation functions (stateless)
   -   `average.py` - Average and time-window calculations
   -   `price.py` - Price enrichment, volatility, rating calculations
   -   **Pattern**: Import as `from ..utils.average import function_name`

2. **`/entity_utils/`** - Entity-specific utilities
   -   `icons.py` - Dynamic icon selection logic
   -   `colors.py` - Icon color mapping
   -   `attributes.py` - Common attribute builders
   -   **Pattern**: Import as `from ..entity_utils import function_name`

3. **`/coordinator/`** - DataUpdateCoordinator and related logic
   -   `core.py` - Main coordinator class
   -   `cache.py` - Persistent storage handling
   -   `data_transformation.py` - Raw data → enriched data
   -   `period_handlers/` - Period calculation sub-package
   -   **Pattern**: Coordinator-specific implementations

4. **`/sensor/`** - Sensor platform package
   -   `core.py` - Entity class (1,268 lines - manages 80+ sensor types)
   -   `definitions.py` - Entity descriptions
   -   `helpers.py` - Sensor-specific helpers
   -   `calculators/` - Value calculation package (8 specialized calculators, 1,838 lines)
   -   `attributes/` - Attribute builders package (8 specialized modules, 1,209 lines)
   -   **Pattern**: Calculator Pattern (business logic separated from presentation)
   -   **Architecture**: Two-tier (Calculators handle computation → Attributes handle state presentation)

5. **`/binary_sensor/`** - Binary sensor platform package
   -   Same structure as `/sensor/`

6. **`/config_flow_handlers/`** - Configuration flow package
   -   `user_flow.py` - Initial setup flow
   -   `subentry_flow.py` - Add additional homes
   -   `options_flow.py` - Reconfiguration
   -   `schemas.py` - Form schemas
   -   `validators.py` - Input validation

7. **`/api/`** - External API communication
   -   `client.py` - GraphQL client
   -   `queries.py` - Query definitions
   -   `exceptions.py` - API-specific exceptions

**When Adding New Files:**

**Before creating a new file in root, ask:**
1. Is this a new HA platform? → OK in root (e.g., `switch.py`, `number.py`)
2. Is this a utility/helper? → Goes in `/utils/` or `/entity_utils/`
3. Is this coordinator-related? → Goes in `/coordinator/`
4. Is this entity-related? → Goes in `/sensor/` or `/binary_sensor/`
5. Is this config flow related? → Goes in `/config_flow_handlers/`

**Goal**: Maintain clean architecture where integration root only contains platform entry points and core integration files. All logic organized in purpose-specific packages.

## Architecture Overview

**Core Data Flow:**

1. `TibberPricesApiClient` (`api.py`) queries Tibber's GraphQL API with `resolution:QUARTER_HOURLY` for user data and prices (day before yesterday/yesterday/today/tomorrow - 384 intervals total, ensuring trailing 24h averages are accurate for all intervals)
2. `TibberPricesDataUpdateCoordinator` (`coordinator.py`) orchestrates updates every 15 minutes, manages persistent storage via `Store`, and schedules quarter-hour entity refreshes
3. Price enrichment functions (`utils/price.py`, `utils/average.py`) calculate trailing/leading 24h averages, price differences, and rating levels for each 15-minute interval
4. Entity platforms (`sensor/` package, `binary_sensor/` package) expose enriched data as Home Assistant entities
5. Custom services (`services/` package) provide API endpoints for chart data export, ApexCharts YAML generation, and user data refresh

**Key Patterns:**

-   **Dual translation system**: Standard HA translations in `/translations/` (config flow, UI strings per HA schema), supplemental in `/custom_translations/` (entity descriptions not supported by HA schema). Both must stay in sync. Use `async_load_translations()` and `async_load_standard_translations()` from `const.py`. When to use which: `/translations/` is bound to official HA schema requirements; anything else goes in `/custom_translations/` (requires manual translation loading). **Schema reference**: `/schemas/json/translation_schema.json` provides the structure for `/translations/*.json` files based on [HA's translation documentation](https://developers.home-assistant.io/docs/internationalization/core).

    -   **Select selector translations**: Use `selector.{translation_key}.options.{value}` structure (NOT `selector.select.{translation_key}`). Translation keys map to JSON in `/translations/*.json` following the HA schema structure.

        **CRITICAL Rules:**
        - When using `translation_key`, pass options as **plain string list**, NOT `SelectOptionDict`
        - Selector option keys MUST be lowercase: `[a-z0-9-_]+` pattern (Hassfest validation)
        - Label parameter overrides translations (avoid when using translation_key)
        - Use `SelectOptionDict` ONLY for dynamic/non-translatable options (no translation_key)

        See `config_flow/schemas.py` for implementation examples.

-   **Price data enrichment**: All quarter-hourly price intervals get augmented with `trailing_avg_24h`, `difference`, and `rating_level` fields via `enrich_price_info_with_differences()` in `utils/price.py`. This adds statistical analysis (24h trailing average, percentage difference from average, rating classification) to each 15-minute interval. See `utils/price.py` for enrichment logic.
-   **Sensor organization (refactored Nov 2025)**: The `sensor/` package uses **Calculator Pattern** for separation of concerns:
    -   **Calculator Package** (`sensor/calculators/`): 8 specialized calculators handle business logic (1,838 lines total)
        -   `base.py` - Abstract BaseCalculator with coordinator access
        -   `interval.py` - Single interval calculations (current/next/previous)
        -   `rolling_hour.py` - 5-interval rolling windows
        -   `daily_stat.py` - Calendar day min/max/avg statistics
        -   `window_24h.py` - Trailing/leading 24h windows
        -   `volatility.py` - Price volatility analysis
        -   `trend.py` - Complex trend analysis with caching (640 lines)
        -   `timing.py` - Best/peak price period timing
        -   `metadata.py` - Home/metering metadata
    -   **Attributes Package** (`sensor/attributes/`): 8 specialized modules handle state presentation (1,209 lines total)
        -   Modules match calculator types: `interval.py`, `daily_stat.py`, `window_24h.py`, `volatility.py`, `trend.py`, `timing.py`, `future.py`, `metadata.py`
        -   `__init__.py` - Routing logic + unified builders (`build_sensor_attributes`, `build_extra_state_attributes`)
    -   **Core Entity** (`sensor/core.py`): 1,268 lines managing 80+ sensor types
        -   Instantiates all calculators in `__init__`
        -   Delegates value calculations to appropriate calculator
        -   Uses unified handler methods: `_get_interval_value()`, `_get_rolling_hour_value()`, `_get_daily_stat_value()`, `_get_24h_window_value()`
        -   Handler mapping dictionary routes entity keys to value getters
    -   **Architecture Benefits**: 42% line reduction in core.py (2,170 → 1,268 lines), clear separation of concerns, improved testability, reusable components
    -   **See "Common Tasks" section** for detailed patterns and examples
-   **Quarter-hour precision**: Entities update on 00/15/30/45-minute boundaries via `schedule_quarter_hour_refresh()` in `coordinator/listeners.py`, not just on data fetch intervals. Uses `async_track_utc_time_change(minute=[0, 15, 30, 45], second=0)` for absolute-time scheduling. Smart boundary tolerance (±2 seconds) in `sensor/helpers.py` → `round_to_nearest_quarter_hour()` handles HA scheduling jitter: if HA triggers at 14:59:58 → rounds to 15:00:00 (next interval), if HA restarts at 14:59:30 → stays at 14:45:00 (current interval). This ensures current price sensors update without waiting for the next API poll, while preventing premature data display during normal operation.
-   **Currency handling**: Multi-currency support with major/minor units (e.g., EUR/ct, NOK/øre) via `get_currency_info()` and `format_price_unit_*()` in `const.py`.
-   **Intelligent caching strategy**: Minimizes API calls while ensuring data freshness:
    -   User data cached for 24h (rarely changes)
    -   Price data validated against calendar day - cleared on midnight turnover to force fresh fetch
    -   Cache survives HA restarts via `Store` persistence
    -   API polling intensifies only when tomorrow's data expected (afternoons)
    -   Stale cache detection via `_is_cache_valid()` prevents using yesterday's data as today's

**Multi-Layer Caching (Performance Optimization)**:

The integration uses **4 distinct caching layers** with automatic invalidation:

1. **Persistent API Cache** (`coordinator/cache.py` → HA Storage):
    - **What**: Raw price/user data from Tibber API (~50KB)
    - **Lifetime**: Until midnight (price) or 24h (user)
    - **Invalidation**: Automatic at 00:00 local, cache validation on load
    - **Why**: Reduce API calls from every 15min to once per day, survive HA restarts

2. **Translation Cache** (`const.py` → in-memory dicts):
    - **What**: UI strings, entity descriptions (~5KB)
    - **Lifetime**: Forever (until HA restart)
    - **Invalidation**: Never (read-only after startup load)
    - **Why**: Avoid file I/O on every entity attribute access (15+ times/hour)

3. **Config Dictionary Cache** (`coordinator/` modules):
    - **What**: Parsed options dict (~1KB per module)
    - **Lifetime**: Until `config_entry.options` change
    - **Invalidation**: Explicit via `invalidate_config_cache()` on options update
    - **Why**: Avoid ~30-40 `options.get()` calls per coordinator update (98% time saving)

4. **Period Calculation Cache** (`coordinator/periods.py`):
    - **What**: Calculated best/peak price periods (~10KB)
    - **Lifetime**: Until price data or config changes
    - **Invalidation**: Automatic via hash comparison of inputs (timestamps + rating_levels + config)
    - **Why**: Avoid expensive calculation (~100-500ms) when data unchanged (70% CPU saving)

**Cache Invalidation Coordination**:
- Options change → Explicit `invalidate_config_cache()` on both DataTransformer and PeriodCalculator
- Midnight turnover → Clear persistent + transformation cache, period cache auto-invalidates via hash
- Tomorrow data arrival → Hash mismatch triggers period recalculation only
- No cascading invalidations - each cache is independent

**See** `docs/development/caching-strategy.md` for detailed lifetime, invalidation logic, and debugging guide.

**Component Structure:**

```
custom_components/tibber_prices/
├── __init__.py           # Entry setup, platform registration
├── coordinator.py        # DataUpdateCoordinator with caching/scheduling
├── api.py                # GraphQL client with retry/error handling
├── utils/                # Pure data transformation utilities
│   ├── __init__.py       #   Package exports
│   ├── average.py        #   Trailing/leading average utilities
│   └── price.py          #   Price enrichment, level/rating calculations
├── services/             # Custom services package
│   ├── __init__.py       #   Service registration
│   ├── chartdata.py      #   Chart data export service
│   ├── apexcharts.py     #   ApexCharts YAML generator
│   ├── refresh_user_data.py # User data refresh
│   ├── formatters.py     #   Data transformation utilities
│   └── helpers.py        #   Common service helpers
├── sensor/               # Sensor platform (package)
│   ├── __init__.py       #   Platform setup (async_setup_entry)
│   ├── core.py           #   TibberPricesSensor class (1,268 lines)
│   ├── definitions.py    #   ENTITY_DESCRIPTIONS
│   ├── helpers.py        #   Pure helper functions (incl. smart boundary tolerance)
│   ├── calculators/      #   Value calculation package (1,838 lines)
│   │   ├── __init__.py   #     Package exports
│   │   ├── base.py       #     Abstract BaseCalculator (57 lines)
│   │   ├── interval.py   #     Single interval calculations (206 lines)
│   │   ├── rolling_hour.py #   5-interval rolling windows (123 lines)
│   │   ├── daily_stat.py #     Daily min/max/avg (211 lines)
│   │   ├── window_24h.py #     Trailing/leading 24h (53 lines)
│   │   ├── volatility.py #     Price volatility (113 lines)
│   │   ├── trend.py      #     Trend analysis with caching (640 lines)
│   │   ├── timing.py     #     Best/peak price timing (246 lines)
│   │   └── metadata.py   #     Home/metering metadata (123 lines)
│   └── attributes/       #   Attribute builders package (1,209 lines)
│       ├── __init__.py   #     Routing + unified builders (267 lines)
│       ├── interval.py   #     Interval attributes (228 lines)
│       ├── daily_stat.py #     Statistics attributes (124 lines)
│       ├── window_24h.py #     24h window attributes (106 lines)
│       ├── timing.py     #     Period timing attributes (64 lines)
│       ├── volatility.py #     Volatility attributes (128 lines)
│       ├── trend.py      #     Trend attribute routing (34 lines)
│       ├── future.py     #     Forecast attributes (223 lines)
│       └── metadata.py   #     Current interval helper (35 lines)
├── binary_sensor/        # Binary sensor platform (package)
│   ├── __init__.py       #   Platform setup (async_setup_entry)
│   ├── core.py           #   TibberPricesBinarySensor class
│   ├── definitions.py    #   ENTITY_DESCRIPTIONS, constants
│   └── attributes.py     #   Attribute builders
├── entity.py             # Base TibberPricesEntity class
├── entity_utils/         # Shared entity helpers (both platforms)
│   ├── __init__.py       #   Package exports
│   ├── icons.py          #   Icon mapping logic
│   ├── colors.py         #   Color mapping logic
│   └── attributes.py     #   Common attribute builders
├── data.py               # @dataclass TibberPricesData
├── const.py              # Constants, translation loaders, currency helpers
├── config_flow/          # UI configuration flow (package)
│   ├── __init__.py       #   Package exports
│   ├── user_flow.py      #   Main config flow (setup + reauth)
│   ├── subentry_flow.py  #   Subentry flow (add homes)
│   ├── options_flow.py   #   Options flow (settings)
│   ├── schemas.py        #   vol.Schema definitions
│   └── validators.py     #   Validation functions
└── services.yaml         # Service definitions
```

## Import Architecture and Dependency Management

**CRITICAL: Import architecture follows strict layering to prevent circular dependencies.**

### Dependency Flow (Calculator Pattern)

**Clean Separation:**
```
sensor/calculators/  → sensor/attributes/  (Volatility only - Hybrid Pattern)
sensor/calculators/  → sensor/helpers/     (DailyStat, RollingHour - Pure functions)
sensor/calculators/  → entity_utils/       (Pure utility functions)
sensor/calculators/  → const.py            (Constants only)

sensor/attributes/   ✗  (NO imports from calculators/)
sensor/helpers/      ✗  (NO imports from calculators/)
```

**Why this works:**
- **One-way dependencies**: Calculators can import from attributes/helpers, but NOT vice versa
- **No circular imports**: Reverse direction is empty (verified Jan 2025)
- **Clean testing**: Each layer can be tested independently

### Hybrid Pattern (Trend/Volatility Calculators)

**Background:** During Nov 2025 refactoring, Trend and Volatility calculators retained attribute-building logic to avoid duplicating complex calculations. This creates a **backwards dependency** (calculator → attributes) but is INTENTIONAL.

**Pattern:**
1. **Calculator** computes value AND builds attribute dict
2. **Core** stores attributes in `cached_data` dict
3. **Attributes package** retrieves cached attributes via:
   - `_add_cached_trend_attributes()` for trend sensors
   - `_add_timing_or_volatility_attributes()` for volatility sensors

**Example (Volatility):**
```python
# sensor/calculators/volatility.py
from custom_components.tibber_prices.sensor.attributes import (
    add_volatility_type_attributes,  # ← Backwards dependency (calculator → attributes)
    get_prices_for_volatility,
)

def get_volatility_value(self, *, volatility_type: str) -> str | None:
    # Calculate volatility level
    volatility = calculate_volatility_level(prices, ...)

    # Build attribute dict (stored for later)
    self._last_volatility_attributes = {"volatility": volatility, ...}
    add_volatility_type_attributes(self._last_volatility_attributes, ...)

    return volatility

def get_volatility_attributes(self) -> dict | None:
    return self._last_volatility_attributes  # ← Retrieved by attributes package
```

**Trade-offs:**
- ✅ **Pro**: Complex logic stays in ONE place (no duplication)
- ✅ **Pro**: Calculator has full context for attribute decisions
- ❌ **Con**: Violates strict separation (calculator builds attributes)
- ❌ **Con**: Creates backwards dependency (testability impact)

**Decision:** Pattern is **acceptable** for complex calculators (Trend, Volatility) where attribute logic is tightly coupled to calculation. Simple calculators (Interval, DailyStat, etc.) DO NOT follow this pattern.

### TYPE_CHECKING Best Practices

All calculator modules use `TYPE_CHECKING` correctly:

**Pattern:**
```python
# Runtime imports (used in function bodies)
from custom_components.tibber_prices.const import CONF_PRICE_RATING_THRESHOLD_HIGH
from custom_components.tibber_prices.entity_utils import get_price_value

from .base import TibberPricesBaseCalculator

# Type-only imports (only for type hints)
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any
```

**Rules:**
- ✅ **Runtime imports**: Functions, classes, constants used in code → OUTSIDE TYPE_CHECKING
- ✅ **Type-only imports**: Only used in type hints → INSIDE TYPE_CHECKING
- ✅ **Coordinator import**: Always in base.py, inherited by all calculators

**Verified Status (Jan 2025):**
- All 8 calculators (base, interval, rolling_hour, daily_stat, window_24h, volatility, trend, timing, metadata) use TYPE_CHECKING correctly
- No optimization needed - imports are already categorized optimally

### Import Anti-Patterns to Avoid

❌ **DON'T:**
- Import from higher layers (attributes/helpers importing from calculators)
- Use runtime imports for type-only dependencies
- Create circular dependencies between packages
- Import entire modules when only needing one function

✅ **DO:**
- Follow one-way dependency flow (calculators → attributes/helpers)
- Use TYPE_CHECKING for type-only imports
- Import specific items: `from .helpers import aggregate_price_data`
- Document intentional backwards dependencies (Hybrid Pattern)

## Period Calculation System (Best/Peak Price Periods)

**CRITICAL:** Period calculation uses multi-criteria filtering that can create **mathematical conflicts** at high flexibility values. Understanding these interactions is essential for reliable period detection.

**Core Challenge:**

The period calculation applies **three independent filters** that ALL must pass:
1. **Flex filter**: `price ≤ daily_min × (1 + flex)`
2. **Min_Distance filter**: `price ≤ daily_avg × (1 - min_distance/100)`
3. **Level filter**: `rating_level IN [allowed_levels]`

**Mathematical Conflict Condition:**

When `daily_min × (1 + flex) > daily_avg × (1 - min_distance/100)`, the flex filter permits intervals that the min_distance filter blocks, causing zero periods despite high flexibility.

Example: daily_min=10 ct, daily_avg=20 ct, flex=50%, min_distance=5%
- Flex allows: ≤15 ct
- Distance allows: ≤19 ct
- But combined: Only intervals ≤15 ct AND ≤19 ct AND matching level → Distance becomes dominant constraint

**Solutions Implemented (Nov 2025):**

1. **Hard Caps on Flex** (`coordinator/period_handlers/core.py`):
   - `MAX_SAFE_FLEX = 0.50` (50% overall maximum)
   - `MAX_OUTLIER_FLEX = 0.25` (25% for price spike detection)
   - Warns users when base flex exceeds thresholds (INFO at 25%, WARNING at 30%)

2. **Relaxation Increment Cap** (`coordinator/period_handlers/relaxation.py`):
   - Maximum 3% increment per relaxation step (prevents explosion from high base flex)
   - Example: Base flex 40% → increments as 43%, 46%, 49% (capped at 50%)
   - Without cap: 40% × 1.25 = 50% step → reaches 100% in 6 steps

3. **Dynamic Min_Distance Scaling** (`coordinator/period_handlers/level_filtering.py`):
   - Reduces min_distance proportionally as flex increases above 20%
   - Formula: `scale_factor = max(0.25, 1.0 - ((flex - 0.20) × 2.5))`
   - Example: flex=30% → scale=0.75 → min_distance reduced by 25%
   - Minimum scaling: 25% of original (prevents complete removal)

4. **Enhanced Debug Logging** (`coordinator/period_handlers/period_building.py`):
   - Tracks exact counts of intervals filtered by flex, min_distance, and level
   - Shows which filter blocked the most candidates
   - Enables diagnosis of configuration issues

**Configuration Guidance:**

**Recommended Flex Ranges:**
- **With relaxation enabled**: 10-20% base flex (relaxation will escalate as needed)
- **Without relaxation**: 20-35% direct flex (no automatic escalation)
- **Anti-pattern**: Base flex >30% with relaxation enabled → causes rapid escalation and filter conflicts

**Key Constants** (defined in `coordinator/period_handlers/core.py`):
```python
MAX_SAFE_FLEX = 0.50                      # 50% absolute maximum
MAX_OUTLIER_FLEX = 0.25                   # 25% for stable outlier detection
FLEX_WARNING_THRESHOLD_RELAXATION = 0.25  # INFO warning at 25% base flex
FLEX_HIGH_THRESHOLD_RELAXATION = 0.30     # WARNING at 30% base flex
```

**Relaxation Strategy** (`coordinator/period_handlers/relaxation.py`):
- Per-day independent loops (each day escalates separately based on its needs)
- Hard cap: 3% absolute maximum increment per step (prevents explosion from high base flex)
- Default configuration: 11 flex levels (15% base → 18% → 21% → ... → 48% max)
- Filter combinations: original level → level="any" (tries both price and volatility levels)
- Each flex level tries all filter combinations before increasing flex further

**Period Boundary Behavior** (`coordinator/period_handlers/period_building.py`):
- Periods can **cross midnight** (day boundaries) naturally
- Reference price locked to **period start day** for consistency across the entire period
- Pattern: "Uses reference price from start day of the period for consistency" (same as period statistics)
- Example: Period starting 23:45 on Day 1 continues into Day 2 using Day 1's daily_min as reference
- This prevents artificial splits at midnight when prices remain favorable across the boundary

**Default Configuration Values** (`const.py`):
```python
DEFAULT_BEST_PRICE_FLEX = 15              # 15% base - optimal for relaxation mode
DEFAULT_PEAK_PRICE_FLEX = -20             # 20% base (negative for peak detection)
DEFAULT_RELAXATION_ATTEMPTS_BEST = 11     # 11 steps: 15% → 48% (3% increment per step)
DEFAULT_RELAXATION_ATTEMPTS_PEAK = 11     # 11 steps: 20% → 50% (3% increment per step)
```

The relaxation increment is **hard-coded at 3% per step** in `relaxation.py` for reliability and predictability. This prevents configuration issues with high base flex values while still allowing sufficient escalation to the 50% hard maximum.

**Dynamic Scaling Table** (min_distance adjustment):
```
Flex    Scale   Example (min_distance=5%)
-------------------------------------------
≤20%    100%    5.00% (no reduction)
25%     87.5%   4.38%
30%     75%     3.75%
35%     62.5%   3.13%
40%     50%     2.50%
45%     37.5%   1.88%
≥50%    25%     1.25% (minimum)
```

**Testing Scenarios:**

When debugging period calculation issues:
1. Check flex value: Is base flex >30%? Reduce to 15-20% if using relaxation
2. Check logs for "scaled min_distance": Is it reducing too much? May need lower base flex
3. Check filter statistics: Which filter blocks most intervals? (flex, distance, or level)
4. Check relaxation warnings: INFO at 25%, WARNING at 30% indicate suboptimal config

**See:**
- **Theory documentation**: `docs/development/period-calculation-theory.md` (comprehensive mathematical analysis, conflict conditions, configuration pitfalls)
- **Implementation**: `coordinator/period_handlers/` package (core.py, relaxation.py, level_filtering.py, period_building.py)
- **User guide**: `docs/user/period-calculation.md` (simplified user-facing explanations)

## Development Environment Setup

**Python Virtual Environment:**

-   Project uses `.venv` located at `/home/vscode/.venv/` (outside workspace)
-   Symlinked into workspace root as `.venv` → `/home/vscode/.venv/`
-   **Why outside workspace?** Project folder is bind-mounted from host, which doesn't support hardlinks required by `uv`

**Package Manager:**

-   Uses `uv` (modern, fast Python package manager)
-   **Always use `uv` commands**, not `pip` directly:

    ```bash
    # ✅ Correct
    uv pip install <package>
    uv run pytest

    # ❌ Wrong - uses system Python
    pip install <package>
    python -m pytest
    ```

**Development Scripts:**

-   All scripts in `./scripts/` automatically use the correct `.venv`
-   No need to manually activate venv or specify Python path
-   Examples: `./scripts/lint`, `./scripts/develop`, `./scripts/lint-check`
-   Release management: `./scripts/release/prepare`, `./scripts/release/generate-notes`

**Release Note Backends (auto-installed in DevContainer):**

-   **Rust toolchain**: Minimal Rust installation via DevContainer feature
-   **git-cliff**: Template-based release notes (fast, reliable, installed via cargo in `scripts/setup/setup`)
-   Manual grep/awk parsing as fallback (always available)

**When generating shell commands:**

1. **Prefer development scripts** (they handle .venv automatically)
2. **If using Python directly**, use `.venv/bin/python` explicitly:
    ```bash
    .venv/bin/python -m pytest tests/
    .venv/bin/python -c "import homeassistant; print('OK')"
    ```
3. **For package management**, always use `uv`:
    ```bash
    uv pip list
    uv pip install --upgrade homeassistant
    ```

**Debugging Environment Issues:**

-   If `import homeassistant` fails: Check if `.venv` symlink exists and points to correct location
-   If packages missing: Run `uv sync` to install dependencies from `pyproject.toml`
-   If wrong Python version: Verify `.venv/bin/python --version` (should be 3.13+)

## Development Workflow

**IMPORTANT: This project is designed for DevContainer development.**

If you notice commands failing or missing dependencies:

1. **Check if running in DevContainer**: Ask user to run `ls /.dockerenv && echo "In container" || echo "NOT in container"`
2. **If NOT in container**: Suggest opening project in DevContainer (VS Code: "Reopen in Container")
3. **Why it matters**:
    - `.venv` is located outside workspace (hardlink issues on bind-mounts)
    - Development scripts expect container environment
    - VS Code Python settings are container-specific

**If user insists on local development without container**, warn that:

-   You'll need to adapt commands for their local setup
-   Some features (like `.venv` symlink) won't work as documented
-   Support will be limited (not the intended workflow)

**Start dev environment:**

```bash
./scripts/develop  # Starts HA in debug mode with config/ dir, sets PYTHONPATH
                   # Automatically runs minimal cleanup (.egg-info only)
```

**Clean up artifacts:**

```bash
./scripts/clean           # Remove build artifacts, caches (pytest, ruff, coverage)
./scripts/clean --deep    # Also remove __pycache__ (normally not needed)
./scripts/clean --minimal # Only critical issues (.egg-info) - used by develop
```

**Type checking and linting:**

```bash
./scripts/type-check  # Run Pyright type checking
./scripts/lint-check  # Run Ruff linting (check-only, CI mode)
./scripts/lint        # Run Ruff linting with auto-fix
./scripts/check       # Run both type-check + lint-check (recommended before commits)
```

**Local validation:**

```bash
./scripts/release/hassfest  # Lightweight local integration validation
```

Note: The local `hassfest` script performs basic validation checks (JSON syntax, required files, Python syntax). Full hassfest validation runs in GitHub Actions.

**Testing:**

```bash
./scripts/test     # Run all tests (pytest with project configuration)
./scripts/test -v  # Verbose output
./scripts/test -k test_midnight  # Run specific test by name
./scripts/test tests/test_midnight_periods.py  # Run specific file
```

Test framework: pytest with Home Assistant custom component support. Tests live in `/tests/` directory. Use `@pytest.mark.unit` for fast tests, `@pytest.mark.integration` for tests that use real coordinator/time services.

## Testing Changes

**IMPORTANT: Never start `./scripts/develop` automatically.**

When changes are complete and ready for testing:

1. **Ask user to test**, don't execute `./scripts/develop` yourself
2. **Provide specific test guidance** based on what changed in this session:

    - Which UI screens to check (e.g., "Open config flow, step 3")
    - What behavior to verify (e.g., "Dropdown should show translated values")
    - What errors to watch for (e.g., "Check logs for JSON parsing errors")
    - What NOT to test (if change is isolated, no need to test everything)

3. **Keep test guidance concise** - 3-5 bullet points max
4. **Focus on session changes only** - Don't suggest testing unrelated features

**Example:**

> ✅ Changes complete! Please test:
>
> 1. Rebuild DevContainer (VS Code: "Reopen and Rebuild")
> 2. Open a Python file - Pylance should now resolve `homeassistant.*` imports without errors
> 3. Check that autocomplete works for HA APIs
>
> No need to test the integration itself - these are environment-only changes.

**What NOT to do:**

-   ❌ Don't execute `./scripts/develop` automatically
-   ❌ Don't suggest exhaustive testing of unrelated features
-   ❌ Don't check `git status` to determine what changed (trust session memory)
-   ❌ Don't assume user needs reminding to commit (they manage their own workflow)

## Git Workflow Guidance

**Purpose:** Maintain clean, atomic commits that enable future release note generation while preserving technical accuracy.

**Why This Matters:**

-   Commits stay **technical** (for developers, describe what changed and why)
-   Commits are **structured** (Conventional Commits format with "Impact:" sections)
-   Release notes are **user-friendly** (AI translates commits into user language later)
-   Clean history enables automatic release note generation from commit messages

**Critical Principles:**

1. **AI suggests commits, NEVER executes them** - User maintains full control of git operations
2. **Commits are for developers** - Technical language, implementation details, code changes
3. **Release notes are for users** - AI will translate commit history into user-friendly format later
4. **Suggest conservatively** - Only at clear feature boundaries, not after every change
5. **Trust session memory** - Don't check `git status`, recall what was accomplished this session

### When to Suggest Commits

**Suggest commits at clear feature boundaries:**

| Scenario                                      | Suggest? | Example                                                                                              |
| --------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| Feature complete and tested                   | ✅ YES   | "Optional: Before we start the next feature, you might want to commit the translation system fixes?" |
| Bug fixed with verification                   | ✅ YES   | "Optional: This bug fix is complete and verified. Ready to commit before moving on?"                 |
| Multiple related files changed (logical unit) | ✅ YES   | "Optional: All 5 translation files updated. This forms a logical commit."                            |
| About to start unrelated work                 | ✅ YES   | "Optional: Before we start refactoring the API client, commit the current sensor changes?"           |
| User explicitly asks what's uncommitted       | ✅ YES   | Provide summary of changes and suggest commit message                                                |
| Iterating on same feature                     | ❌ NO    | Don't suggest between attempts/refinements                                                           |
| Debugging in progress                         | ❌ NO    | Wait until root cause found and fixed                                                                |
| User declined previous commit suggestion      | ❌ NO    | Respect their workflow preference                                                                    |

**Suggestion Language:**

-   Use "Optional:" prefix to make it clear this is not required
-   Ask, don't assume: "Want to commit?" not "You should commit"
-   Accept graceful decline: If user says no or ignores, don't mention again for that boundary
-   Provide commit message: Include full Conventional Commit format with "Impact:" section
-   **Specify files to stage**: When suggesting commits, list exact files for `git add`
-   **Split when logical**: If session has multiple unrelated changes, suggest separate commits with specific file lists

**Commit Splitting Guidelines:**

Split into multiple commits when:

-   Different areas affected (config flow + docs + environment)
-   Different change types (fix + feat + docs)
-   Different impact scope (user-facing vs. developer-only)
-   Changes can work independently

Combine into single commit when:

-   Tightly coupled changes (translations + code using them)
-   Single feature across files (sensor + translations + service)
-   Dependency chain (A requires B to function)
-   Small scope (2-3 related files telling one story)

**Example - Single Commit:**

> Optional: Ruff configuration migration complete. Ready to commit?
>
> **Stage these files:**
>
> ```bash
> git add pyproject.toml AGENTS.md
> ```
>
> **Commit message:**
>
> ```
> refactor: migrate ruff config from .ruff.toml to pyproject.toml
>
> Consolidated ruff configuration into pyproject.toml following modern Python
> conventions and integration_blueprint pattern.
>
> Updated all references in AGENTS.md from .ruff.toml to
> pyproject.toml under [tool.ruff] section.
>
> Impact: Aligns with modern Python tooling standards. No user-visible changes.
> ```

**Example - Multiple Commits:**

> Optional: Two separate improvements ready. Suggest splitting:
>
> **Commit 1: Translation Fix**
>
> ```bash
> git add custom_components/tibber_prices/config_flow/
> git add custom_components/tibber_prices/translations/*.json
> ```
>
> ```
> fix(config_flow): use flat selector structure for translation_key
>
> SelectOptionDict with label parameter was overriding translation_key,
> causing config flow to fail at step 4.
>
> Changed to plain string lists with translation_key parameter,
> following HA pattern: selector.{translation_key}.options.{value}
>
> Updated all 5 language files (de, en, nb, nl, sv).
>
> Impact: Config flow works through all 6 steps with translated options.
> ```
>
> **Commit 2: Documentation**
>
> ```bash
> git add AGENTS.md
> ```
>
> ```
> docs(patterns): document selector translation structure
>
> Added correct translation pattern for SelectSelector based on
> official HA documentation and debugging session.
>
> Documents flat selector.{translation_key}.options.{value} structure
> and common pitfall of SelectOptionDict overriding translations.
>
> Impact: Future sessions generate correct selector translations.
> ```
>
> Want to commit separately or combine?

### Conventional Commits Format

**Reference:** Follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) specification.

**Structure:**

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Required Elements:**

-   **type**: Lowercase, communicates intent (feat, fix, docs, etc.)
-   **description**: Short summary (max 50-72 chars), imperative mood ("add" not "added"), lowercase start, no period

**Optional Elements:**

-   **scope**: Parentheses after type, e.g., `feat(sensors):` - lowercase, specific area of change
-   **body**: Detailed explanation, wrap at 72 chars, explain WHAT and WHY (not HOW - code shows that)
-   **footer**: Breaking changes, issue references, or custom fields

**Breaking Changes:**

Use `BREAKING CHANGE:` footer or `!` after type/scope:
```
feat(api)!: drop support for legacy endpoint

BREAKING CHANGE: The /v1/prices endpoint has been removed. Use /v2/prices instead.
```

**Types (Conventional Commits standard):**

-   `feat`: New feature (appears in release notes as "New Features")
-   `fix`: Bug fix (appears in release notes as "Bug Fixes")
-   `docs`: Documentation only (appears in release notes as "Documentation")
-   `style`: Code style/formatting (no behavior change, omitted from release notes)
-   `refactor`: Code restructure without behavior change (may or may not appear in release notes)
-   `perf`: Performance improvement (appears in release notes)
-   `test`: Test changes only (omitted from release notes)
-   `build`: Build system/dependencies (omitted from release notes)
-   `ci`: CI configuration (omitted from release notes)
-   `chore`: Maintenance tasks (usually omitted from release notes)

**Scope (project-specific, optional but recommended):**

-   `translations`: Translation system changes
-   `config_flow`: Configuration flow changes
-   `sensors`: Sensor implementation
-   `binary_sensors`: Binary sensor implementation
-   `api`: API client changes
-   `coordinator`: Data coordinator changes
-   `services`: Service implementations
-   `docs`: Documentation files

**Custom Footer - Impact Section:**

Add `Impact:` footer for release note generation context (project-specific addition):

```
feat(services): add rolling window support

Implement dynamic 48h window that adapts to data availability.

Impact: Users can create auto-adapting price charts without manual
day selection. Requires config-template-card for ApexCharts mode.
```

**Best Practices:**

-   **Subject line**: Max 50 chars (hard limit 72), lowercase, imperative mood
-   **Body**: Wrap at 72 chars, optional but useful for complex changes
-   **Blank line**: Required between subject and body
-   **Impact footer**: Optional but recommended for user-facing changes

### Technical Commit Message Examples

**Example 1: Bug Fix**

```
fix(config_flow): use flat selector structure for translation_key

SelectOptionDict with label parameter was overriding translation_key,
causing config flow to fail at step 4 with "Unknown error occurred".

Changed to use plain string lists with translation_key parameter,
following official HA pattern: selector.{translation_key}.options.{value}

Updated all 5 language files (de, en, nb, nl, sv) with correct
structure.

Impact: Config flow now works through all 6 steps with properly
translated dropdown options. Users can complete setup without
encountering errors.
```

**Example 2: Documentation**

```
docs(workflow): add git commit guidance for release notes

Added comprehensive "Git Workflow Guidance" section to AGENTS.md
documenting when AI should suggest commits, Conventional Commits format, and
how to structure technical messages that enable future release note generation.

Key additions:
- Commit boundary detection decision table
- When NOT to suggest commits (during iteration/debugging)
- Conventional Commits format with types and scopes
- Technical commit message examples with "Impact:" sections
- Release note generation guidelines for future use

Impact: AI can now help maintain clean, atomic commits structured for
automatic release note generation while preserving technical accuracy.
```

**Example 3: Feature**

```
feat(environment): add VS Code Python environment configuration

Added .vscode/settings.json with universal Python/Ruff settings and updated
.devcontainer/devcontainer.json to use workspace .venv interpreter.

Changes:
- .devcontainer/devcontainer.json: Set python.defaultInterpreterPath to .venv
- .devcontainer/devcontainer.json: Added python.analysis.extraPaths
- .vscode/settings.json: Created with Pylance and Ruff configuration
- Removed deprecated ruff.lint.args and ruff.format.args

Impact: Pylance now resolves homeassistant.* imports correctly and provides
full autocomplete for Home Assistant APIs. Developers get proper IDE support
without manual interpreter selection.
```

**Example 4: Refactor**

```
refactor: migrate ruff config from .ruff.toml to pyproject.toml

Consolidated ruff configuration into pyproject.toml following modern Python
conventions and integration_blueprint pattern.

Updated all references in AGENTS.md from .ruff.toml to
pyproject.toml under [tool.ruff] section.

Impact: Aligns with modern Python tooling standards. No user-visible changes.
```

### "Impact:" Section Guidelines

The "Impact:" section bridges technical commits and future release notes:

**What to Include:**

-   **User-visible effects**: What changes for end users of the integration
-   **Developer benefits**: What improves for contributors/maintainers
-   **Context for translation**: Information that helps future AI translate this into user-friendly release note
-   **Omit "Impact:" if**: Internal refactor with zero user/dev impact (e.g., rename private variable)

**Examples:**

✅ **Good Impact Sections:**

-   "Config flow now works through all 6 steps without errors"
-   "Pylance provides full autocomplete for Home Assistant APIs"
-   "AI maintains clean commit history for release note generation"
-   "Aligns with HA 2025.x translation schema requirements"
-   "Reduces API calls by 70% through intelligent caching"

❌ **Poor Impact Sections:**

-   "Code is better now" (vague, not actionable)
-   "Fixed the bug" (redundant with commit type)
-   "Updated file X" (describes action, not impact)
-   "This should work" (uncertain, commits should be verified)

### Release Note Generation (Future Use)

**When generating release notes from commits:**

1. **Filter by type**:
    - Include: `feat`, `fix`, `docs` (if significant)
    - Maybe include: `refactor` (if user-visible)
    - Exclude: `chore`, `test`, `style`
2. **Group by type**:
    - "New Features" (feat)
    - "Bug Fixes" (fix)
    - "Documentation" (docs)
    - "Improvements" (refactor with user impact)
3. **Translate to user language**:
    - Technical: "fix(config_flow): use flat selector structure" → User: "Fixed configuration wizard failing at step 4"
    - Technical: "feat(environment): add VS Code configuration" → User: "Improved developer experience with better IDE support"
4. **Use "Impact:" as source**:
    - Extract user-visible effects from Impact sections
    - Preserve context (why it matters)
    - Rewrite in present tense, active voice
5. **Add examples if helpful**:
    - Show before/after for UI changes
    - Demonstrate new capabilities with code snippets
    - Link to documentation for complex features

**Example Release Note (Generated from Commits):**

> **Tibber Prices 2.0.1**
>
> **Bug Fixes**
>
> -   Fixed configuration wizard failing at step 4 when selecting price thresholds. Dropdown options now appear correctly with proper translations.
>
> **Improvements**
>
> -   Improved developer environment setup with automatic Python path detection and full Home Assistant API autocomplete in VS Code

### Philosophy

**User Controls Workflow:**

-   User decides when to commit
-   User writes final commit message (AI provides suggestion)
-   User manages branches, PRs, and releases
-   AI is an assistant, not a driver

**AI Suggests at Boundaries:**

-   Suggests when logical unit complete
-   Provides structured commit message
-   Accepts decline without repeating
-   Trusts session memory over `git status`

**Commits Enable Release Notes:**

-   Technical accuracy preserved (for developers)
-   Structure enables automation (Conventional Commits)
-   Impact sections provide user context (for release notes)
-   Future AI translates into user-friendly format

### Release Notes Generation

**Multiple Options Available:**

1. **Helper Script** (recommended, foolproof)

    - Script: `./scripts/release/prepare VERSION`
    - Bumps manifest.json version → commits → creates tag locally
    - You review and push when ready
    - Example: `./scripts/release/prepare 0.3.0`

2. **Auto-Tag Workflow** (safety net)

    - Workflow: `.github/workflows/auto-tag.yml`
    - Triggers on manifest.json changes
    - Automatically creates tag if it doesn't exist
    - Prevents "forgot to tag" mistakes

3. **Local Script** (testing, preview, and updating releases)

    - Script: `./scripts/release/generate-notes [FROM_TAG] [TO_TAG]`
    - Parses Conventional Commits between tags
    - Supports multiple backends (auto-detected):
        - **AI-powered**: GitHub Copilot CLI (best, context-aware)
        - **Template-based**: git-cliff (fast, reliable)
        - **Manual**: grep/awk fallback (always works)
    - **Auto-update feature**: If a GitHub release exists for TO_TAG, automatically offers to update release notes (interactive prompt)

    **Usage examples:**

    ```bash
    # Generate and preview notes
    ./scripts/release/generate-notes v0.2.0 v0.3.0

    # If release exists, you'll see:
    # → Generated release notes
    # → Detection: "A GitHub release exists for v0.3.0"
    # → Prompt: "Do you want to update the release notes on GitHub? [y/N]"
    # → Answer 'y' to auto-update, 'n' to skip

    # Force specific backend
    RELEASE_NOTES_BACKEND=copilot ./scripts/release/generate-notes v0.2.0 v0.3.0
    ```

4. **GitHub UI Button** (manual, PR-based)

    - Uses `.github/release.yml` configuration
    - Click "Generate release notes" when creating release
    - Works best with PRs that have labels
    - Direct commits appear in "Other Changes" category

5. **CI/CD Automation** (automatic on tag push)
    - Workflow: `.github/workflows/release.yml`
    - Triggers on version tags (v1.0.0, v2.1.3, etc.)
    - Uses git-cliff backend (AI disabled in CI)
    - Filters out version bump commits automatically
    - Creates GitHub release automatically

**Recommended Release Workflow:**

```bash
# Step 1: Get version suggestion (analyzes commits since last release)
./scripts/release/suggest-version

# Output shows:
# - Commit analysis (features, fixes, breaking changes)
# - Suggested version based on Semantic Versioning
# - Alternative versions (MAJOR/MINOR/PATCH)
# - Preview and release commands

# Step 2: Preview release notes (with AI if available)
./scripts/release/generate-notes v0.2.0 HEAD

# Step 3: Prepare release (bumps manifest.json + creates tag)
./scripts/release/prepare 0.3.0
# Or without argument to show suggestion first:
./scripts/release/prepare

# Step 4: Review changes
git log -1 --stat
git show v0.3.0

# Step 5: Push when ready
git push origin main v0.3.0

# Done! CI/CD creates release automatically with git-cliff notes
```

**Alternative: Improve existing release with AI:**

If you want better release notes after the automated release:

```bash
# Generate AI-powered notes and update existing release
./scripts/release/generate-notes v0.2.0 v0.3.0

# Script will:
# 1. Generate notes (uses AI if available locally)
# 2. Detect existing GitHub release
# 3. Ask: "Do you want to update the release notes on GitHub? [y/N]"
# 4. Update release automatically if you confirm

# This allows:
# - Fast automated releases (CI uses git-cliff)
# - Manual AI improvement when desired (uses Copilot quota only on request)
```

**Semantic Versioning Rules:**

-   **Pre-1.0 (0.x.y)**:
    -   Breaking changes → bump MINOR (0.x.0)
    -   New features → bump MINOR (0.x.0)
    -   Bug fixes → bump PATCH (0.0.x)
-   **Post-1.0 (x.y.z)**:
    -   Breaking changes → bump MAJOR (x.0.0)
    -   New features → bump MINOR (0.x.0)
    -   Bug fixes → bump PATCH (0.0.x)

**Alternative: Manual Bump (with Auto-Tag Safety Net):**

```bash
# 1. Bump manifest.json manually
vim custom_components/tibber_prices/manifest.json  # "version": "0.3.0"
git commit -am "chore(release): bump version to 0.3.0"
git push

# 2. Auto-Tag workflow detects manifest.json change → creates tag
# 3. Release workflow creates GitHub release
```

**Using the Local Script:**

```bash
# Generate from latest tag to HEAD
./scripts/release/generate-notes

# Generate between specific tags
./scripts/release/generate-notes v1.0.0 v1.1.0

# Force specific backend
RELEASE_NOTES_BACKEND=manual ./scripts/release/generate-notes

# Disable AI (use in CI/CD)
USE_AI=false ./scripts/release/generate-notes
```

**Backend Selection Logic:**

1. If `$RELEASE_NOTES_BACKEND` set → use that backend
2. Else if in CI/CD (`$CI` or `$GITHUB_ACTIONS`) → skip AI, use git-cliff or manual
3. Else if `USE_AI=false` → skip AI, use git-cliff or manual
4. Else if GitHub Copilot CLI available (`copilot` command) → use AI (best quality, smart grouping)
5. Else if git-cliff available → use template-based (fast, reliable, 1:1 commit mapping)
6. Else → use manual grep/awk parsing (always works)

**Backend Comparison:**

-   **GitHub Copilot CLI** (`copilot`):

    -   ✅ AI-powered semantic understanding
    -   ✅ Smart grouping of related commits into single release notes
    -   ✅ Interprets "Impact:" sections for user-friendly descriptions
    -   ✅ Multiple commits can be combined with all links: ([hash1](url1), [hash2](url2))
    -   ⚠️ Uses premium request quota
    -   ⚠️ Output may vary between runs

-   **git-cliff** (template-based):

    -   ✅ Fast and consistent
    -   ✅ 1:1 commit to release note line mapping
    -   ✅ Highly configurable via `cliff.toml`
    -   ❌ No semantic understanding
    -   ❌ Cannot intelligently group related commits

-   **manual** (grep/awk):
    -   ✅ Always available (no dependencies)
    -   ✅ Basic commit categorization
    -   ❌ No commit grouping
    -   ❌ Basic formatting only

**Output Format:**

All backends produce GitHub-flavored Markdown with consistent structure:

```markdown
## 🎉 New Features

-   **scope**: Description ([commit_hash](link))
    User-visible impact from "Impact:" section

-   **scope**: Combined description ([hash1](link1), [hash2](link2)) # AI backend only
    Multiple related commits grouped together
```

## 🐛 Bug Fixes

-   **scope**: Description ([commit_hash](link))
    User-visible impact

## 📚 Documentation

...

````

**Installing Optional Backends:**

```bash
# git-cliff (fast, reliable, used in CI/CD)
# Auto-installed in DevContainer via scripts/setup/setup
# See: https://git-cliff.org/docs/installation
cargo install git-cliff  # or download binary from releases
````

**When to Use Which:**

-   **GitHub Button**: When working with PRs, quick manual releases
-   **Local Script**: Before committing to test release notes, manual review needed
-   **CI/CD**: Automatic releases on tag push (production workflow)

**Format Requirements:**

-   **HACS**: No specific format required, uses GitHub releases as-is
-   **Home Assistant**: No specific format required for custom integrations
-   **Markdown**: Standard GitHub-flavored Markdown supported
-   **HTML**: Can include `<ha-alert>` tags for special notices (HA update entities only)

**Validate integration:**

```bash
# Run local validation (checks JSON syntax, Python syntax, required files)
./scripts/release/hassfest

# Or validate JSON files manually if needed:
python -m json.tool custom_components/tibber_prices/translations/de.json > /dev/null
```

**Why:** The `./scripts/release/hassfest` script validates JSON syntax (translations, manifest), Python syntax, and required files. This catches common errors before pushing to GitHub Actions. For quick JSON-only checks, you can still use `python -m json.tool` directly.

## Linting Best Practices

**CRITICAL: Always check BOTH type checking (Pyright) AND linting (Ruff) before completing work.**

### Quick Reference: Available Scripts

```bash
# Type checking only (Pyright/Pylance)
./scripts/type-check

# Linting only (Ruff)
./scripts/lint-check  # Check-only (CI mode)
./scripts/lint        # Auto-fix mode

# Both together (recommended workflow)
./scripts/check       # Runs type-check + lint-check
```

### Two-Tool Strategy: Pyright vs Ruff

This project uses **two complementary tools** with different responsibilities:

**Pyright (Type Checker)** - Catches type safety issues:
- ✅ Type mismatches (`str` passed where `int` expected)
- ✅ None-safety violations (`Optional[T]` used as `T`)
- ✅ Missing/wrong type annotations
- ✅ Attribute access on wrong types
- ✅ Function signature mismatches
- ⚠️ **Cannot auto-fix** - requires manual code changes
- 🔍 **Always run first** - catches design issues early

**Ruff (Linter + Formatter)** - Enforces code style and patterns:
- ✅ Code formatting (line length, indentation, quotes)
- ✅ Import ordering (stdlib → third-party → local)
- ✅ Unused imports/variables
- ✅ Complexity checks (McCabe)
- ✅ Best practice violations (mutable defaults, etc.)
- 🔧 **Can auto-fix** most issues with `./scripts/lint`
- 📋 **Run after Pyright** - cleans up after manual fixes

### Recommended Workflow

**When making changes:**

1. **Write/modify code** with type hints
2. **Run `./scripts/type-check`** - fix type errors manually
3. **Run `./scripts/lint`** - auto-format and fix style issues
4. **Run `./scripts/check`** - final verification (both tools)

**When debugging errors:**

If you see errors from one tool, understand which tool should fix them:

```bash
# Pyright errors → Manual fixes needed
./scripts/type-check

# Example Pyright errors:
# - "Type X is not assignable to type Y"
# - "Cannot access attribute 'foo' for class 'Bar'"
# - "Argument of type 'str | None' cannot be assigned..."
```

```bash
# Ruff errors → Usually auto-fixable
./scripts/lint       # Try auto-fix first
./scripts/lint-check # Verify remaining issues

# Example Ruff errors:
# - "Line too long (121 > 120 characters)"
# - "Unused import 'datetime'"
# - "Missing type annotation"
```

### Common Type Checking Patterns

**Pattern 1: Optional Types - Always Be Explicit**

```python
# ❌ BAD - Pylance sees this as potentially None
def process_data(time: TimeService | None) -> None:
    result = time.now()  # Error: 'None' has no attribute 'now'

# ✅ GOOD - Guard against None
def process_data(time: TimeService | None) -> None:
    if time is None:
        return
    result = time.now()  # OK - type narrowed to TimeService

# ✅ BETTER - Make it required if always provided
def process_data(time: TimeService) -> None:
    result = time.now()  # OK - never None
```

**Pattern 2: Custom Type Aliases for Clarity**

```python
# ✅ Define custom types in TYPE_CHECKING block
if TYPE_CHECKING:
    from collections.abc import Callable
    from .time_service import TimeService

    # Custom callback type that accepts TimeService
    TimeServiceCallback = Callable[[TimeService], None]

# Use in class definition
class ListenerManager:
    def __init__(self) -> None:
        self._listeners: list[TimeServiceCallback] = []

    def add_listener(self, callback: TimeServiceCallback) -> None:
        self._listeners.append(callback)  # Type-safe!
```

**Pattern 3: Runtime Checks for Dynamic Attributes**

```python
# ❌ BAD - Pyright doesn't understand hasattr
if hasattr(tz, "localize"):
    result = tz.localize(dt)  # Error: attribute not known

# ✅ GOOD - Use type: ignore with explanation
if hasattr(tz, "localize"):
    # Type checker doesn't understand hasattr, but this is safe
    result = tz.localize(dt)  # type: ignore[attr-defined]
```

**Pattern 4: Walrus Operator for None-Checks**

```python
# ❌ BAD - Two calls, potential race condition
if time.get_interval_time(price) is not None:
    dt = time.get_interval_time(price).date()  # Called twice!

# ✅ GOOD - Walrus operator with type narrowing
if (interval_time := time.get_interval_time(price)) is not None:
    dt = interval_time.date()  # Type-safe, single call
```

**Pattern 5: Return Type Consistency**

```python
# ❌ BAD - Function signature says str, returns datetime
def get_timestamp() -> str:
    return datetime.now()  # Error: incompatible return type

# ✅ GOOD - Match return type to actual return value
def get_timestamp() -> datetime:
    return datetime.now()  # OK

# ✅ ALSO GOOD - Convert if signature requires string
def get_timestamp() -> str:
    return datetime.now().isoformat()  # OK - returns str
```

### Pyright Configuration

Project uses `typeCheckingMode = "basic"` in `pyproject.toml`:
- Balanced between strictness and pragmatism
- Catches real bugs without excessive noise
- Compatible with Home Assistant's typing style

**Key settings:**
```toml
[tool.pyright]
include = ["custom_components/tibber_prices"]
venvPath = "."
venv = ".venv"
typeCheckingMode = "basic"
```

**CRITICAL: When generating code, always aim for Pyright `basic` mode compliance:**

✅ **DO:**
- Add type hints to all function signatures (parameters + return types)
- Use proper type annotations: `dict[str, Any]`, `list[dict]`, `str | None`
- Handle Optional types explicitly (None-checks before use)
- Use TYPE_CHECKING imports for type-only dependencies
- Prefer explicit returns over implicit `None`

❌ **DON'T:**
- Leave functions without return type hints
- Ignore potential `None` values in Optional types
- Use `Any` as escape hatch (only when truly needed)
- Create functions that could return different types based on runtime logic

**Goal:** Generated code should pass `./scripts/type-check` on first try, minimizing post-generation fixes.

**See also:** "Ruff Code Style Guidelines" section below for complementary code style rules that ensure `./scripts/lint` compliance.

### When Type Errors Are Acceptable

**Use `type: ignore` comments sparingly and ONLY when:**

1. **Runtime checks guarantee safety** (hasattr, isinstance)
2. **Third-party library has wrong/missing type stubs**
3. **Home Assistant API has incomplete typing**

**ALWAYS include explanation:**
```python
# ✅ GOOD - Explains why ignore is needed
result = tz.localize(dt)  # type: ignore[attr-defined]  # pytz-specific method

# ❌ BAD - No explanation
result = tz.localize(dt)  # type: ignore
```

### Integration with VS Code

Pylance (VS Code's Python language server) uses the same Pyright engine:
- **Red squiggles** = Type errors (must fix)
- **Yellow squiggles** = Warnings (should fix)
- Hover for details, Cmd/Ctrl+Click for definitions
- Problems panel shows all issues at once

The `./scripts/type-check` script runs the same checks in terminal, ensuring CI/CD consistency.

### Linting Details

**Always use the provided scripts:**

```bash
./scripts/lint        # Auto-fix mode
./scripts/lint-check  # Check-only (CI mode)
```

**Why not call `ruff` directly?**

Calling `ruff` or `uv run ruff` directly can cause unintended side effects:

-   May install the integration as a Python package (creates `.egg-info`, etc.)
-   HA will then load the **installed** version instead of the **development** version from `custom_components/`
-   Causes confusing behavior where code changes don't take effect

**About `__pycache__` directories:**

-   **Normal and expected** when Home Assistant runs - this is Python's bytecode cache for faster loading
-   **Not a problem** in development - speeds up HA startup
-   **Already in `.gitignore`** - won't be committed
-   **Only problematic** if the package gets installed in `.venv` (then HA loads installed version, not dev version)
-   `./scripts/develop`, `./scripts/lint`, and `./scripts/lint-check` automatically clean up accidental installations

**Exception:** If you need to run `ruff` with custom flags not supported by our scripts:

1. Run your custom `ruff` command
2. **Immediately after**, clean up any installation artifacts:

    ```bash
    # Use our cleanup script (uses both pip and uv pip for compatibility)
    ./scripts/clean --minimal

    # Or manually:
    pip uninstall -y tibber_prices 2>/dev/null || true
    uv pip uninstall tibber_prices 2>/dev/null || true
    ```

3. Ask user to restart HA: `./scripts/develop`

**When in doubt:** Stick to `./scripts/lint` - it's tested and safe.

**Note on pip vs. uv pip:**

-   `scripts/clean` uses **both** `pip` and `uv pip` for maximum compatibility
-   Regular `pip uninstall` has cleaner output (no "Using Python X.Y..." messages)
-   `uv pip uninstall` is used as fallback for robustness
-   Both are needed because different commands may install via different methods

**Ruff Configuration:**

-   Max line length: **120** chars (not 88 from Ruff's default)
-   Max complexity: **25** (McCabe)
-   Target: Python 3.13
-   No unused imports/variables (`F401`, `F841`)
-   No mutable default args (`B008`)
-   Use `_LOGGER` not `print()` (`T201`)
-   `pyproject.toml` (under `[tool.ruff]`) has full configuration

## Critical Project-Specific Patterns

**1. Translation Loading (Async-First)**
Load translations at integration setup via `async_load_translations()` and `async_load_standard_translations()` in `__init__.py`. Access cached translations synchronously later via `get_translation(path, language)` from `const.py`.

**2. Price Data Enrichment**
Never use raw API price data directly. Always enrich via `enrich_price_info_with_differences()` from `utils/price.py` to add `trailing_avg_24h`, `difference`, and `rating_level` fields.

**3. Time Handling**
Always use `dt_util` from `homeassistant.util` instead of Python's `datetime` module for timezone-aware operations. **Critical:** Use `dt_util.as_local()` when comparing API timestamps to local time. Import datetime types only for type hints: `from datetime import date, datetime, timedelta`.

**4. Coordinator Data Structure**
Coordinator data follows structure: `coordinator.data = {"user_data": {...}, "priceInfo": [...], "currency": "EUR"}`. The `priceInfo` is a flat list containing all enriched interval dicts (yesterday + today + tomorrow). Currency is stored at top level for easy access. See `coordinator/core.py` for data management.

**5. Service Response Pattern**
Services returning data must declare `supports_response=SupportsResponse.ONLY` in registration. See `services.py` for implementation patterns.

## Common Pitfalls (HA-Specific)

**1. Entity State Class Compatibility:**
MONETARY device_class requires TOTAL state_class (or None for snapshots), NOT MEASUREMENT. TIMESTAMP device_class requires None state_class. Check [HA sensor docs](https://developers.home-assistant.io/docs/core/entity/sensor) for valid combinations. See `sensor/definitions.py` for correct implementations.

**2. Config Flow Input Validation:**
ALWAYS validate input before `async_create_entry()`. Test API connection, validate data format. Use specific error keys for proper translation. See `config_flow/user_flow.py` for validation patterns.

**3. Don't Override async_update() with DataUpdateCoordinator:**
When using `DataUpdateCoordinator`, entities get updates automatically. Only implement properties (`native_value`, `extra_state_attributes`), not `async_update()`. See `sensor/core.py` and `binary_sensor/core.py` for correct patterns.

**4. Service Response Declaration:**
Services returning data MUST declare `supports_response` parameter. Use `SupportsResponse.ONLY` for data-only services, `OPTIONAL` for dual-purpose, `NONE` for action-only. See `services.py` for examples.

## Code Quality Rules

**CRITICAL: See "Linting Best Practices" section for comprehensive type checking (Pyright) and linting (Ruff) guidelines.**

### Home Assistant Class Naming Conventions

**All public classes in an integration MUST use the integration name as prefix.**

This is a Home Assistant standard to avoid naming conflicts between integrations and ensure clear ownership of classes.

**Naming Pattern:**
```python
# ✅ CORRECT - Integration prefix + semantic purpose
class TibberPricesApiClient:              # Integration + semantic role
class TibberPricesDataUpdateCoordinator:  # Integration + semantic role
class TibberPricesDataFetcher:            # Integration + semantic role
class TibberPricesSensor:                 # Integration + entity type
class TibberPricesEntity:                 # Integration + entity type

# ❌ INCORRECT - Missing integration prefix
class DataFetcher:         # Should be: TibberPricesDataFetcher
class TimeService:         # Should be: TibberPricesTimeService
class PeriodCalculator:    # Should be: TibberPricesPeriodCalculator

# ❌ INCORRECT - Including package hierarchy (unnecessary)
class TibberPricesCoordinatorDataFetcher:  # Too verbose, package path is namespace
class TibberPricesSensorCalculatorTrend:   # Too verbose, import path shows location
```

**IMPORTANT:** Do NOT include package hierarchy in class names. Python's import system provides the namespace:
```python
# The import path IS the full namespace:
from custom_components.tibber_prices.coordinator.data_fetching import TibberPricesDataFetcher
from custom_components.tibber_prices.sensor.calculators.trend import TibberPricesTrendCalculator

# Adding package names to class would be redundant:
# TibberPricesCoordinatorDataFetcher  ❌ NO - unnecessarily verbose
# TibberPricesSensorCalculatorsTrendCalculator  ❌ NO - ridiculously long
```

**Home Assistant Core follows this pattern:**
- `TibberDataCoordinator` (not `TibberCoordinatorDataCoordinator`)
- `MetWeatherData` (not `MetCoordinatorWeatherData`)
- `MetDataUpdateCoordinator` (not `MetCoordinatorDataUpdateCoordinator`)

Use semantic prefixes that describe the PURPOSE, not the package location.

**When prefix is required:**
- ✅ All public classes (used across multiple modules)
- ✅ All exception classes
- ✅ All coordinator classes
- ✅ All entity classes (Sensor, BinarySensor, etc.)
- ✅ All service/helper classes exposed to other modules
- ✅ All data classes (dataclasses, NamedTuples) used as public APIs

**When prefix can be omitted:**
- 🟡 Private helper classes used only within a single module (prefix class name with `_` underscore)
- 🟡 Type aliases and callbacks (e.g., `TimeServiceCallback` is acceptable)
- 🟡 Small NamedTuples used only for internal function returns (e.g., within calculators)
- 🟡 Enums that are clearly namespaced (e.g., `QueryType` in `api.queries`)
- 🟡 **TypedDict classes**: Documentation-only constructs (never instantiated), used solely for IDE autocomplete - shorter names improve readability (e.g., `IntervalPriceAttributes`, `PeriodAttributes`)

**Private Classes (Module-Internal):**

If you create a helper class that is ONLY used within a single module file:
```python
# ✅ CORRECT - Private class with underscore prefix
class _InternalHelper:
    """Helper class used only within this module."""
    pass

# Usage: Only in the same file, never imported elsewhere
result = _InternalHelper().process()
```

**When to use private classes:**
- ❌ **DON'T** use for code organization alone - if it deserves a class, it's usually public
- ✅ **DO** use for internal implementation details (e.g., state machines, internal builders)
- ✅ **DO** use for temporary refactoring helpers (mark as `# TODO: Make public` if it grows)

**Example of genuine private class use case:**
```python
# In coordinator/data_fetching.py
class _ApiRetryStateMachine:
    """Internal state machine for retry logic. Never used outside this file."""
    def __init__(self, max_retries: int) -> None:
        self._attempts = 0
        self._max_retries = max_retries

    # Only used by DataFetcher methods in this file
```

In practice, most "helper" logic should be **functions**, not classes. Reserve classes for stateful components.

### Ruff Code Style Guidelines

**Ruff config (`pyproject.toml` under `[tool.ruff]`):**

We use **Ruff** (which replaces Black, Flake8, isort, and more) as our linter and formatter:

-   Max line length: **120** chars (not 88 from Ruff's default)
-   Max complexity: **25** (McCabe)
-   Target: Python 3.13
-   No unused imports/variables (`F401`, `F841`)
-   No mutable default args (`B008`)
-   Use `_LOGGER` not `print()` (`T201`)

**Pyright config (`pyproject.toml` under `[tool.pyright]`):**

We use **Pyright** for static type checking:

-   Type checking mode: **basic** (balanced strictness)
-   Target: Python 3.13
-   Validates type annotations, None-safety, attribute access
-   Integrated with VS Code via Pylance extension

**Import order (enforced by isort):**

1. Python stdlib (only specific types needed, e.g., `from datetime import date, datetime, timedelta`)
2. Third-party (`homeassistant.*`, `aiohttp`, etc.)
3. Local (`.api`, `.const`, etc.)

**Import best practices:**

-   Prefer Home Assistant utilities over stdlib equivalents: `from homeassistant.util import dt as dt_util` instead of `import datetime`
-   Import only specific stdlib types when needed for type hints: `from datetime import date, datetime, timedelta`
-   Use `dt_util` for all datetime operations (parsing, timezone conversion, current time)
-   Avoid aliasing stdlib modules with same names as HA utilities (e.g., `import datetime as dt` conflicts with `dt_util`)

**Error handling best practices:**

-   Keep try blocks minimal - only wrap code that can throw exceptions
-   Process data **after** the try/except block, not inside
-   Catch specific exceptions, avoid bare `except Exception:` (allowed only in config flows and background tasks)
-   Use `ConfigEntryNotReady` for temporary failures (device offline)
-   Use `ConfigEntryAuthFailed` for auth issues
-   Use `ServiceValidationError` for user input errors in services

**Logging guidelines:**

**Critical principle:** Logs must enable logic tracing without reading code. Each log message should make the current state and decision-making process crystal clear.

**Why good logging matters beyond debugging:**

-   Clear logs become the foundation for good documentation (see "Documentation Writing Strategy")
-   If you spend hours making logs explain the logic, that clarity transfers directly to user docs
-   Logs show state transitions and decisions that users need to understand
-   Pattern: Good hierarchical logs → Easy to extract examples and explanations for documentation

**Log Level Strategy:**

-   **INFO Level** - User-facing results and high-level progress:

    -   Compact 1-line summaries (no multi-line blocks)
    -   Important results only (success/failure outcomes)
    -   No indentation (scannability)
    -   Example: `"Calculating BEST PRICE periods: relaxation=ON, target=2/day, flex=15.0%"`
    -   Example: `"Day 2025-11-11: Success after 1 relaxation phase (2 periods)"`

-   **DEBUG Level** - Detailed execution trace:

    -   Full context headers with all relevant configuration
    -   Step-by-step progression through logic
    -   Hierarchical indentation to show call depth/logic structure
    -   Intermediate results and calculations
    -   Example: `"  Day 2025-11-11: Found 1 baseline period (need 2)"`
    -   Example: `"    Phase 1: flex 20.25% + original filters"`

-   **WARNING Level** - Problems and unexpected states:
    -   Top-level important messages (no indentation)
    -   Clear indication of what went wrong
    -   Example: `"Day 2025-11-11: All relaxation phases exhausted, still only 1 period found"`

**Hierarchical Indentation Pattern:**

Use consistent indentation to show logical structure (DEBUG level only):

```python
# Define indentation constants at module level
INDENT_L0 = ""          # Top-level (0 spaces)
INDENT_L1 = "  "        # Level 1 (2 spaces)
INDENT_L2 = "    "      # Level 2 (4 spaces)
INDENT_L3 = "      "    # Level 3 (6 spaces)
INDENT_L4 = "        "  # Level 4 (8 spaces)
INDENT_L5 = "          "# Level 5 (10 spaces)

# Usage example showing logic hierarchy
_LOGGER.debug("%sCalculating periods for day %s", INDENT_L0, day_date)
_LOGGER.debug("%sBaseline: Found %d periods", INDENT_L1, baseline_count)
_LOGGER.debug("%sStarting relaxation...", INDENT_L1)
_LOGGER.debug("%sPhase 1: flex 20.25%%", INDENT_L2)
_LOGGER.debug("%sCandidate period: %s", INDENT_L3, period_str)
_LOGGER.debug("%sMerging with baseline...", INDENT_L3)
_LOGGER.debug("%sExtended baseline period from %s to %s", INDENT_L4, old_end, new_end)
```

**Why indentation?**

-   Makes call stack and decision tree visible at a glance
-   Enables quick problem localization (which phase/step failed?)
-   Shows parent-child relationships between operations
-   Distinguishes between sequential steps vs nested logic

**Configuration Context:**

When starting complex calculations, log the full decision context upfront (DEBUG level):

```python
_LOGGER.debug(
    "%sConfiguration:\n"
    "%s  Relaxation: %s\n"
    "%s  Target: %d periods per day\n"
    "%s  Base flex: %.1f%%\n"
    "%s  Strategy: 4 flex levels × 4 filter combinations",
    INDENT_L0,
    INDENT_L0, "ENABLED" if enable_relaxation else "DISABLED",
    INDENT_L0, min_periods,
    INDENT_L0, base_flex,
    INDENT_L0,
)
```

**Per-Day Processing:**

Complex logic that operates per-day should clearly show which day is being processed (DEBUG level):

```python
for day_date, day_intervals in intervals_by_day.items():
    _LOGGER.debug("%sProcessing day %s", INDENT_L1, day_date)
    # ... processing ...
    _LOGGER.debug("%sDay %s: Found %d periods", INDENT_L1, day_date, count)
```

**General Rules:**

-   Use lazy logging: `_LOGGER.debug("Message with %s", variable)` (never f-strings in log calls - Ruff G004)
-   No periods at end of log messages
-   No integration name in messages (added automatically by HA)
-   Always include relevant identifiers (day, phase, period) for context
-   Log BEFORE and AFTER state changes to show transitions
-   Use consistent terminology (e.g., "baseline" vs "relaxed", "extended" vs "replaced")

**Function organization:**
Public entry points → direct helpers (call order) → pure utilities. Prefix private helpers with `_`.

**Legacy/Backwards compatibility:**

-   **Do NOT add legacy migration code** unless the change was already released in a version tag
-   **Check if released**: Use `./scripts/release/check-if-released <commit-hash>` to verify if code is in any `v*.*.*` tag
-   **Example**: If introducing breaking config change in commit `abc123`, run `./scripts/release/check-if-released abc123`:
    -   ✓ NOT RELEASED → No migration needed, just use new code
    -   ✗ ALREADY RELEASED → Migration may be needed for users upgrading from that version
-   **Rule**: Only add backwards compatibility for changes that shipped to users via HACS/GitHub releases
-   **Prefer breaking changes over complexity**: If migration code would be complex or clutter the codebase, prefer documenting the breaking change in release notes (Home Assistant style). Only add simple migrations (e.g., `.lower()` call, key rename) when trivial.

**Translation sync:** When updating `/translations/en.json`, update ALL language files (`de.json`, etc.) with same keys (placeholder values OK).

**Documentation language:**

-   **CRITICAL**: All user-facing documentation (`README.md`, `/docs/user/`, `/docs/development/`) MUST be written in **English**
-   **Code comments**: Always use English for code comments and docstrings
-   **UI translations**: Multi-language support exists in `/translations/` and `/custom_translations/` (de, en, nb, nl, sv) for UI strings only
-   **Why English-only docs**: Ensures maintainability, accessibility to global community, and consistency with Home Assistant ecosystem
-   **Entity names in documentation**: Use **translated display names** from `/translations/en.json` (what users see), not internal entity IDs. Example: "Best Price Period" not "sensor.tibber_home_best_price_period" (add entity ID as comment if needed for clarity).

**Examples and use cases:**

-   **Regional context**: Tibber operates primarily in European markets (Norway, Sweden, Germany, Netherlands). Examples should reflect European context:
    -   ✅ Use cases: Heat pump, dishwasher, washing machine, electric vehicle charging, water heater
    -   ✅ Appliances: Common in European homes (heat pumps for heating/cooling, instantaneous water heaters)
    -   ✅ Energy patterns: European pricing structures (often lower overnight rates, higher daytime rates)
    -   ✅ Optimization strategies: ECO programs with long run times, heat pump defrost cycles, smart water heating
    -   ❌ Avoid: US-centric examples (central air conditioning as primary cooling, 240V dryers, different voltage standards)
    -   ❌ Avoid: US appliance behavior assumptions (e.g., dishwashers requiring hot water connection due to 120V limitations)
-   **Technical differences**: European appliances operate differently due to 230V power supply:
    -   Dishwashers: Built-in heaters, ECO programs (long duration, low energy), cold water connection standard
    -   Washing machines: Fast heating cycles, higher temperature options (60°C, 90°C programs common)
    -   Heat pumps: Primary heating source (not just cooling), complex defrost cycles, weather-dependent operation
-   **Units and formats**: Use European conventions where appropriate:
    -   Prices: ct/kWh or øre/kWh (as provided by Tibber API)
    -   Time: 24-hour format (00:00-23:59)
    -   Dates: ISO 8601 format (YYYY-MM-DD)

**Language style and tone:**

-   **Informal address**: Always use informal "you" forms (German: "du" not "Sie", Dutch: "je/jouw" not "u/uw"). This applies to all translations.
-   **Gender-neutral language**: Use gender-neutral formulations where possible, but keep them natural - avoid forced or artificial constructions.
-   **Documentation tone**: English documentation should use a friendly, approachable tone. Avoid overly formal constructions like "It is recommended that you..." - prefer "We recommend..." or "You can...".
-   **Imperative mood**: Use direct imperatives for instructions: "Configure the integration" not "You should configure the integration".
-   **Language-specific notes**:
    -   German: Use "du" (informal) and gender-neutral imperatives (e.g., "Konfiguriere" instead of "Konfigurieren Sie")
    -   Dutch: Use "je/jouw" (informal) instead of "u/uw" (formal)
    -   Swedish/Norwegian: Already use informal address by default (no formal "Ni"/"De" in modern usage)
    -   English: Already gender-neutral and appropriately informal

**User Documentation Quality:**

When writing or updating user-facing documentation (`docs/user/`), follow these principles learned from real user feedback:

-   **Clarity over completeness**: Users want to understand concepts, not read technical specifications
    -   ✅ Good: "Relaxation automatically loosens filters until enough periods are found"
    -   ❌ Bad: "The relaxation algorithm implements a 4×4 matrix strategy with multiplicative flex increments"
-   **Visual examples**: Use timeline diagrams, code blocks with comments, before/after comparisons
    -   ✅ Show what a "period" looks like on a 24-hour timeline
    -   ✅ Include automation examples with real entity names
-   **Use-case driven**: Start with "what can I do with this?" not "how does it work internally"
    -   ✅ Structure: Quick Start → Common Scenarios → Configuration Guide → Advanced Topics
    -   ❌ Avoid: Starting with mathematical formulas or algorithm descriptions
-   **Practical troubleshooting**: Address real problems users encounter
    -   ✅ "No periods found → Try: increase flex from 15% to 20%"
    -   ❌ Avoid: Generic "check your configuration" without specific guidance
-   **Progressive disclosure**: Basic concepts first, advanced details later
    -   ✅ Main doc covers 80% use cases in simple terms
    -   ✅ Link to advanced/technical docs for edge cases
    -   ❌ Don't mix basic explanations with deep technical details
-   **When code changed significantly**: Verify documentation still matches
    -   If relaxation strategy changed from 3 phases to 4×4 matrix → documentation MUST reflect this
    -   If metadata format changed → update all examples showing attributes
    -   If per-day independence was added → explain why some days relax differently

**Documentation Writing Strategy:**

Understanding **how** good documentation emerges is as important as knowing what makes it good:

-   **Live Understanding vs. Code Analysis**

    -   ✅ **DO:** Write docs during/after active development
        -   When implementing complex logic, document it while the "why" is fresh
        -   Use real examples from debugging sessions (actual logs, real data)
        -   Document decisions as they're made, not after the fact
    -   ❌ **DON'T:** Write docs from cold code analysis
        -   Reading code shows "what", not "why"
        -   Missing context: Which alternatives were considered?
        -   No user perspective: What's actually confusing?

-   **User Feedback Loop**

    -   Key insight: Documentation improves when users question it
    -   Pattern:
        1. User asks: "Does this still match the code?"
        2. AI realizes: "Oh, the 3-phase model is outdated"
        3. Together we trace through real behavior
        4. Documentation gets rewritten with correct mental model
    -   Why it works: User questions force critical thinking, real confusion points get addressed

-   **Log-Driven Documentation**

    -   Observation: When logs explain logic clearly, documentation becomes easier
    -   Why: Logs show state transitions ("Baseline insufficient → Starting relaxation"), decisions ("Replaced period X with larger Y"), and are already written for humans
    -   Pattern: If you spent hours making logs clear → use that clarity in documentation too

-   **Concrete Examples > Abstract Descriptions**

    -   ✅ **Good:** "Day 2025-11-11 found 2 periods at flex=12.0% +volatility_any (stopped early, no need to try higher flex)"
    -   ❌ **Bad:** "The relaxation algorithm uses a configurable threshold multiplier with filter combination strategies"
    -   Use real data from debug sessions, show actual attribute values, demonstrate with timeline diagrams

-   **Context Accumulation in Long Sessions**

    -   Advantage: AI builds mental model incrementally, sees evolution of logic (not just final state), understands trade-offs
    -   Disadvantage of short sessions: Cold start every time, missing "why" context, documentation becomes spec-writing
    -   Lesson: Complex documentation benefits from focused, uninterrupted work with accumulated context

-   **Document the "Why", Not Just the "What"**
    -   Every complex pattern should answer:
        1. **What** does it do? (quick summary)
        2. **Why** was it designed this way? (alternatives considered)
        3. **How** does a user benefit? (practical impact)
        4. **When** does it fail? (known limitations)
    -   Example: "Replacement Logic: Larger periods replace smaller overlapping ones because users want ONE long cheap period, not multiple short overlapping ones."

## Ruff Code Style Guidelines

These rules ensure generated code passes `./scripts/lint` on first try. Ruff enforces these automatically.

**See also:** "Linting Best Practices" section above for Pyright type checking guidelines that ensure `./scripts/type-check` compliance.

**String Formatting:**

```python
# ✅ Use f-strings for simple formatting
message = f"Found {count} items"
url = f"{base_url}/api/{endpoint}"

# ✅ Use lazy logging (no f-strings in logger calls)
_LOGGER.debug("Processing %s items", count)

# ❌ Avoid .format() and % formatting
message = "Found {} items".format(count)  # Ruff will suggest f-string
```

**String Quotes:**

```python
# ✅ Use double quotes (Ruff's default)
name = "tibber_prices"
message = "Hello world"

# ✅ Use single quotes to avoid escaping
html = '<div class="container">content</div>'

# ❌ Inconsistent quote usage
name = 'tibber_prices'  # Ruff will change to double quotes
```

**Trailing Commas:**

```python
# ✅ Always use trailing commas in multi-line structures
SENSOR_TYPES = [
    "current_interval_price",
    "min_price",
    "max_price",  # ← Trailing comma
]

# ✅ Also for function arguments
def calculate_average(
    prices: list[dict],
    start_time: datetime,
    end_time: datetime,  # ← Trailing comma
) -> float:
    pass

# ❌ Missing trailing comma
SENSOR_TYPES = [
    "current_interval_price",
    "min_price",
    "max_price"  # Ruff will add trailing comma
]
```

**Docstrings:**

```python
# ✅ Use triple double-quotes, single-line for simple cases
def get_price() -> float:
    """Return current electricity price."""
    return 0.25

# ✅ Multi-line docstrings: summary line, blank, details
def calculate_average(prices: list[dict]) -> float:
    """Calculate average price from interval list.

    Args:
        prices: List of price dictionaries with 'total' key.

    Returns:
        Average price as float.
    """
    return sum(p["total"] for p in prices) / len(prices)

# ❌ Single quotes or missing docstrings on public functions
def get_price() -> float:
    '''Return price'''  # Ruff will change to double quotes
```

**Line Breaking:**

```python
# ✅ Break long lines at logical points
result = some_function(
    argument1=value1,
    argument2=value2,
    argument3=value3,
)

# ✅ Break long conditions
if (
    price > threshold
    and time_of_day == "peak"
    and day_of_week in ["Monday", "Friday"]
):
    do_something()

# ✅ Chain methods with line breaks
df = (
    data_frame
    .filter(lambda x: x > 0)
    .sort_values()
    .reset_index()
)
```

**Type Annotations:**

```python
# ✅ Annotate function signatures (public functions)
def get_current_interval_price(coordinator: DataUpdateCoordinator) -> float:
    """Get current price from coordinator."""
    return coordinator.data["priceInfo"][0]["total"]

# ✅ Use modern type syntax (Python 3.13)
def process_prices(prices: list[dict[str, Any]]) -> dict[str, float]:
    pass

# ❌ Avoid old-style typing (List, Dict from typing module)
from typing import List, Dict
def process_prices(prices: List[Dict[str, Any]]) -> Dict[str, float]:  # Use list, dict instead
    pass

# ✅ Optional parameters
def fetch_data(home_id: str, max_retries: int = 3) -> dict | None:
    pass
```

**Import Grouping:**

```python
# ✅ Correct order with blank lines between groups
from datetime import date, datetime, timedelta  # Stdlib

from homeassistant.core import HomeAssistant  # Third-party
from homeassistant.util import dt as dt_util

from .const import DOMAIN  # Local
from .coordinator import TibberPricesDataUpdateCoordinator

# ❌ Mixed order or missing blank lines
from .const import DOMAIN
from datetime import datetime
from homeassistant.core import HomeAssistant  # Ruff will reorder
```

**List/Dict Comprehensions:**

```python
# ✅ Use comprehensions for simple transformations
prices = [interval["total"] for interval in data]
price_map = {interval["startsAt"]: interval["total"] for interval in data}

# ✅ Break long comprehensions
prices = [
    interval["total"]
    for interval in data
    if interval["total"] is not None
]

# ❌ Don't use comprehensions for complex logic
result = [  # Use regular loop instead
    calculate_something_complex(x, y, z)
    for x in items
    for y in x.nested
    if some_complex_condition(y)
    for z in y.more_nested
]
```

**Common Ruff Auto-fixes:**

-   Unused imports → removed automatically
-   Unused variables → prefixed with `_` if intentional: `_unused = value`
-   Mutable default args → use `None` with `if x is None: x = []`
-   `== True` / `== False` → simplified to `if x:` / `if not x:`
-   Long lines → Ruff suggests breaks but may need manual adjustment

## Attribute Naming Conventions

Entity attributes exposed to users must be **self-explanatory and descriptive**. Follow these rules to ensure clarity in automations and dashboards:

### General Principles

1. **Be Explicit About Context**: Attribute names should indicate what the value represents AND how/where it was calculated
2. **Avoid Ambiguity**: Generic terms like "status", "value", "data" need qualifiers
3. **Show Relationships**: When comparing/calculating, name must show what is compared to what
4. **Consistency First**: Follow established patterns in the codebase

### Attribute Ordering

Attributes should follow a **logical priority order** to make the most important information easily accessible in automations and UI:

**Standard Order Pattern:**

```python
attributes = {
    # 1. Time information (when does this apply?)
    "timestamp": ...,          # ALWAYS FIRST: Reference time for state/attributes validity
    "start": ...,
    "end": ...,
    "duration_minutes": ...,

    # 2. Core decision attributes (what should I do?)
    "level": ...,              # Price level (VERY_CHEAP, CHEAP, NORMAL, etc.)
    "rating_level": ...,       # Price rating (LOW, NORMAL, HIGH)

    # 3. Price statistics (how much does it cost?)
    "price_avg": ...,
    "price_min": ...,
    "price_max": ...,

    # 4. Price differences (optional - how does it compare?)
    "price_diff_from_daily_min": ...,
    "price_diff_from_daily_min_%": ...,

    # 5. Detail information (additional context)
    "hour": ...,
    "minute": ...,
    "time": ...,
    "period_position": ...,
    "interval_count": ...,

    # 6. Meta information (technical details)
    "pricePeriods": [...],          # Nested structures last
    "priceInfo": [...],

    # 7. Extended descriptions (always last)
    "description": "...",      # Short description from custom_translations (always shown)
    "long_description": "...", # Detailed explanation from custom_translations (shown when CONF_EXTENDED_DESCRIPTIONS enabled)
    "usage_tips": "...",       # Usage examples from custom_translations (shown when CONF_EXTENDED_DESCRIPTIONS enabled)
}
```

**Critical: The `timestamp` Attribute**

The `timestamp` attribute **MUST always be first** in every sensor's attributes. It serves as the reference time indicating when the state and attributes are valid.

**Automatic Default Behavior:**

All sensors (both `sensor` and `binary_sensor` platforms) automatically receive a default `timestamp` attribute set to the **current time rounded to the nearest quarter hour** (00, 15, 30, or 45 minutes). This is handled using unified attribute builder functions:

-   **Sensor platform**: `sensor/attributes.py` → `build_extra_state_attributes()` (called from `sensor/core.py` → `extra_state_attributes` property)
-   **Binary sensor platform**: `binary_sensor/attributes.py` → `build_async_extra_state_attributes()` and `build_sync_extra_state_attributes()` (called from `binary_sensor/core.py` properties)

Both platforms use the same pattern: a `build_*_extra_state_attributes()` function that generates the default timestamp, merges sensor-specific attributes, and ensures timestamp ordering.

The rounding uses `round_to_nearest_quarter_hour()` from `average_utils.py`, which intelligently handles HA scheduling jitter (±2 seconds tolerance).

**When Sensors Override the Default:**

Individual sensors can override the default timestamp to reflect different time contexts:

-   **Current interval sensors**: Use default (rounded quarter) - represents when calculation was made
-   **Next interval sensors**: Override with next interval's `startsAt` - shows when that interval starts
-   **Previous interval sensors**: Override with previous interval's `startsAt` - shows when that interval started
-   **Statistical sensors (min/max)**: Override with extreme interval's `startsAt` - shows when the extreme price occurs
-   **Daily average sensors**: Override with midnight (00:00) of that day - shows the value applies to the whole day
-   **Daily aggregated sensors**: Override with midnight (00:00) of that day - shows the value applies to the whole day
-   **Daily volatility sensors**: Override with day start (00:00 of yesterday/today/tomorrow) - shows which day's data is analyzed
-   **Next 24h volatility sensor**: Override with current time (not rounded) - shows the exact start of the 24h window
-   **Future forecast sensors**: Override with first interval's `startsAt` - shows when the forecast window begins
-   **Timing sensors** (`best_price_end_time`, etc.): Override with minute-precise or quarter-rounded time - shows current calculation time with appropriate precision
-   **Period sensors**: Use default (rounded quarter) - represents when period state was determined (via binary_sensor attribute functions)
-   **Chart data export**: Overrides with service call timestamp (when data was requested)
-   **Data timestamp sensor**: Overrides with API's data timestamp (when data was fetched from Tibber)

**Key Principles:** The timestamp represents one of these concepts:

1. **WHEN the calculation was made** (current/forecast sensors) - uses default rounded quarter
2. **WHEN the referenced interval occurs** (next/previous/extreme interval sensors) - uses interval's `startsAt`
3. **WHICH day the data applies to** (daily average/aggregated sensors) - uses midnight of that day
4. **WHICH day's data is analyzed** (volatility sensors) - uses day start (00:00 of that specific day)
5. **WHEN a time window starts** (next 24h, future N-hour forecasts) - uses exact current time or first interval start
6. **WHEN an action occurred** (service calls, API fetches) - uses action timestamp
7. **Current time with appropriate precision** (timing sensors) - uses minute-precise or quarter-rounded time depending on update frequency

The midnight timestamp (concept 3) indicates temporal scope rather than calculation time. Even though the value may be recalculated multiple times throughout the day (e.g., when tomorrow's data arrives), the timestamp stays at midnight to show "this value represents the entire day from 00:00 to 23:59".

Day start timestamps (concept 4) differ from midnight timestamps: they always point to 00:00 of the **specific day being analyzed** (yesterday = 00:00 yesterday, tomorrow = 00:00 tomorrow), not today's midnight.

This ensures users always understand temporal context - when the sensor updated, which specific interval the data refers to, which calendar day applies, or which time window is being analyzed.

**Implementation Pattern:**

Both platforms use **unified architecture with direct method pattern** for attribute collection:

**1. Direct Method Pattern (Standardized Nov 2025):**

Both `sensor/core.py` and `binary_sensor/core.py` implement `_get_sensor_attributes()`:

```python
# sensor/core.py
def _get_sensor_attributes(self) -> dict | None:
    """Get sensor-specific attributes."""
    # Direct implementation returns dict
    return build_sensor_attributes(...)

# binary_sensor/core.py
def _get_sensor_attributes(self) -> dict | None:
    """Get sensor-specific attributes."""
    # Direct implementation returns dict
    return get_price_intervals_attributes(...) if key == "best_price_period" else None
```

**Why direct method over Callable pattern?**
- **Simpler**: No lambda/Callable indirection, clearer stack traces
- **More HA-standard**: Most Core integrations use direct methods
- **Better performance**: ~2x faster (~0.1-0.5μs vs 0.2-0.8μs per call)
- **More maintainable**: Single implementation approach across both platforms
- **Future-proof**: Less moving parts, getter never changes at runtime

**2. Unified Attribute Builder Functions:**

Both platforms now use **identical signatures and patterns** (unified Nov 2025):

**Sensor Platform (`sensor/attributes.py`):**
```python
def build_extra_state_attributes(
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    config_entry: TibberPricesConfigEntry,
    coordinator_data: dict,
    sensor_attrs: dict | None = None,
) -> dict[str, Any] | None:
    """Build extra state attributes for sensors."""
    # 1. Generate default timestamp (rounded quarter)
    # 2. Merge sensor-specific attributes (may override timestamp)
    # 3. Preserve timestamp ordering (always FIRST)
    # 4. Add description attributes inline (always LAST)
```

**Binary Sensor Platform (`binary_sensor/attributes.py`):**
```python
async def build_async_extra_state_attributes(
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    config_entry: TibberPricesConfigEntry,
    sensor_attrs: dict | None = None,
    is_on: bool | None = None,  # Binary sensor specific
) -> dict | None:
    """Build async extra state attributes (with translation loading)."""
    # Same pattern: Default timestamp → merge sensor_attrs → descriptions inline

def build_sync_extra_state_attributes(...) -> dict | None:
    """Build sync extra state attributes (cached translations)."""
    # Same pattern: Default timestamp → merge sensor_attrs → descriptions inline
```

**Key Points:**
- **Architectural consistency**: Both platforms use direct method pattern (not Callable)
- **Naming consistency**: Both use `_get_sensor_attributes()` method name
- **Parameter consistency**: Both builders accept `sensor_attrs` parameter
- **Description logic unified**: Both build descriptions **inline** (no separate method in core.py)
- **Same logic flow**: Default timestamp → merge attributes → preserve ordering → add descriptions
- **Exception handling**: Both platforms have try/except in extra_state_attributes properties
- **Platform separation**: Logic stays separate per platform, but patterns are unified

**3. Timestamp Override Pattern:**

Sensors override the timestamp by setting it in their attribute builders (e.g., `sensor/attributes.py` helper functions). The platform ensures timestamp stays FIRST in the attribute dict even when overridden:

```python
# 1. Platform generates default timestamp (rounded quarter) - ALWAYS FIRST
default_timestamp = round_to_nearest_quarter_hour(now)
attributes = {"timestamp": default_timestamp.isoformat()}

# 2. Sensor-specific attributes added
sensor_attrs = self._get_sensor_attributes()  # May include timestamp override

# 3. If sensor overrides timestamp, it's extracted and kept FIRST
if "timestamp" in sensor_attrs:
    timestamp_override = sensor_attrs.pop("timestamp")
    # Rebuild dict with overridden timestamp FIRST
    attributes = {"timestamp": timestamp_override, **attributes}

# 4. All other sensor attributes merged (timestamp position preserved)
attributes.update(sensor_attrs)

# 5. Description attributes added last (never override timestamp)
attributes.update(description_attrs)
```

This ensures timestamp is always the first key in the attribute dict, regardless of whether it was overridden.

**Rationale:**

-   **Time first**: Users need to know when/for which interval the data applies before interpreting values
-   **Decisions next**: Core attributes for automation logic (is it cheap/expensive?)
-   **Prices after**: Actual values to display or use in calculations
-   **Differences optionally**: Contextual comparisons if relevant
-   **Details follow**: Supplementary information for deeper analysis
-   **Meta last**: Complex nested data and technical information
-   **Descriptions always last**: Human-readable help text from `custom_translations/` (must always be defined; `description` always shown, `long_description` and `usage_tips` shown only when user enables `CONF_EXTENDED_DESCRIPTIONS`)

**In Practice:**

```python
# ✅ Good: Follows priority order
{
    "timestamp": "2025-11-08T14:00:00+01:00",  # ALWAYS first
    "start": "2025-11-08T14:00:00+01:00",
    "end": "2025-11-08T15:00:00+01:00",
    "rating_level": "LOW",
    "price_avg": 18.5,
    "interval_count": 4,
    "intervals": [...]
}

# ❌ Bad: Random order makes it hard to scan
{
    "intervals": [...],
    "interval_count": 4,
    "rating_level": "LOW",
    "start": "2025-11-08T14:00:00+01:00",
    "price_avg": 18.5,
    "end": "2025-11-08T15:00:00+01:00"
}
```

### Naming Patterns

**Time-based Attributes:**

-   Use `next_*` for future calculations starting from the next interval (not "future\_\*")
-   Use `trailing_*` for backward-looking calculations
-   Use `leading_*` for forward-looking calculations
-   Always include the time span: `next_3h_avg`, `trailing_24h_max`
-   For multi-part periods, be specific: `second_half_6h_avg` (not "later_half")

**Counting Attributes:**

-   Use singular `_count` for counting items: `interval_count`, `period_count`
-   Exception: `intervals_available` is a status indicator (how many are available), not a count of items being processed
-   Prefer singular form: `interval_count` over `intervals_count` (the word "count" already implies plurality)

**Difference/Comparison Attributes:**

-   Use `_diff` suffix (not "difference")
-   Always specify what is being compared: `price_diff_from_daily_min`, `second_half_3h_diff_from_current`
-   For percentages, use `_diff_%` suffix with underscore: `price_diff_from_max_%`

**Duration Attributes:**

-   Be specific about scope: `remaining_minutes_in_period` (not "after_interval")
-   Pattern: `{remaining/elapsed}_{unit}_in_{scope}`

**Status/Boolean Attributes:**

-   Use descriptive suffixes: `data_available` (not just "available")
-   Qualify generic terms: `data_status` (not just "status")
-   Pattern: `{what}_{status_type}` like `tomorrow_data_status`

**Grouped/Nested Data:**

-   Describe the grouping: `intervals_by_hour` (not just "hours")
-   Pattern: `{items}_{grouping_method}`

**Price-Related Attributes:**

-   Period averages: `period_price_avg` (average across the period)
-   Reference comparisons: `period_price_diff_from_daily_min` (period avg vs daily min)
-   Interval-specific: `interval_price_diff_from_daily_max` (current interval vs daily max)

### Before Adding New Attributes

Ask yourself:

1. **Would a user understand this without reading documentation?**
2. **Is it clear what time period/scope this refers to?**
3. **If it's a calculation, is it obvious what's being compared/calculated?**
4. **Does it follow existing patterns in the codebase?**

If the answer to any is "no", make the name more explicit.

## Common Tasks

**Add a new sensor:**

After the sensor.py refactoring (completed Nov 2025), sensors are organized by **calculation method** rather than feature type. Follow these steps:

1. **Determine calculation pattern** - Choose which group your sensor belongs to:

    - **Interval-based**: Uses time offset from current interval (e.g., current/next/previous)
    - **Rolling hour**: Aggregates 5-interval window (2 before + center + 2 after)
    - **Daily statistics**: Min/max/avg within calendar day boundaries
    - **24h windows**: Trailing/leading from current interval
    - **Future forecast**: N-hour windows starting from next interval
    - **Volatility**: Statistical analysis of price variation
    - **Diagnostic**: System information and metadata

2. **Add entity description** to appropriate sensor group in `sensor/definitions.py`:

    - `INTERVAL_PRICE_SENSORS`, `INTERVAL_LEVEL_SENSORS`, or `INTERVAL_RATING_SENSORS`
    - `ROLLING_HOUR_PRICE_SENSORS`, `ROLLING_HOUR_LEVEL_SENSORS`, or `ROLLING_HOUR_RATING_SENSORS`
    - `DAILY_STAT_SENSORS`
    - `WINDOW_24H_SENSORS`
    - `FUTURE_AVG_SENSORS` or `FUTURE_TREND_SENSORS`
    - `VOLATILITY_SENSORS`
    - `DIAGNOSTIC_SENSORS`

3. **Add handler mapping** in `sensor/core.py` → `_get_value_getter()` method:

    - For interval-based: Use `_get_interval_value(interval_offset, value_type)`
    - For rolling hour: Use `_get_rolling_hour_value(hour_offset, value_type)`
    - For daily stats: Use `_get_daily_stat_value(day, stat_func)`
    - For 24h windows: Use `_get_24h_window_value(stat_func)`
    - For others: Implement specific handler if needed

4. **Add translation keys** to `/translations/en.json` and `/custom_translations/en.json`

5. **Sync all language files** (de, nb, nl, sv)

**See** `sensor/definitions.py` for sensor grouping examples and `sensor/core.py` for handler implementations.

**Unified Handler Methods (Post-Refactoring):**

The refactoring consolidated duplicate logic into unified methods in `sensor/core.py`:

-   **`_get_interval_value(interval_offset, value_type, in_euro=False)`**

    -   Replaces: `_get_interval_price_value()`, `_get_interval_level_value()`, `_get_interval_rating_value()`
    -   Handles: All interval-based sensors (current/next/previous)
    -   Returns: Price (float), level (str), or rating (str) based on value_type

-   **`_get_rolling_hour_value(hour_offset, value_type)`**

    -   Replaces: `_get_rolling_hour_average_value()`, `_get_rolling_hour_level_value()`, `_get_rolling_hour_rating_value()`
    -   Handles: All 5-interval rolling hour windows
    -   Returns: Aggregated value (average price, aggregated level/rating)

-   **`_get_daily_stat_value(day, stat_func)`**

    -   Replaces: `_get_statistics_value()` (calendar day portion)
    -   Handles: Min/max/avg for calendar days (today/tomorrow)
    -   Returns: Price in minor currency units (cents/øre)

-   **`_get_24h_window_value(stat_func)`**
    -   Replaces: `_get_average_value()`, `_get_minmax_value()`
    -   Handles: Trailing/leading 24h window statistics
    -   Returns: Price in minor currency units (cents/øre)

Legacy wrapper methods still exist for backward compatibility but will be removed in a future cleanup phase.

**Add a new binary sensor:**

After the binary_sensor.py refactoring (completed Nov 2025), follow these steps:

1. **Add entity description** to `binary_sensor/definitions.py` → `ENTITY_DESCRIPTIONS` tuple
2. **Implement state logic** in `binary_sensor/core.py` → Add state property returning bool, update `is_on` routing
3. **Add attribute builder** (if needed) in `binary_sensor/attributes.py` → Create builder function, call from unified builder
4. **Add translations**: `/translations/en.json` (entity name) + `/custom_translations/en.json` (descriptions)
5. **Sync all language files** (de, nb, nl, sv)

**See** existing binary sensors in `binary_sensor/` package for implementation patterns.

**Modify price calculations:**
Edit `utils/price.py` or `utils/average.py`. These are stateless pure functions operating on price lists.

**Add a new config flow step:**

The config flow is split into three separate flow handlers:

1. **User Flow** (`config_flow/user_flow.py`) - Initial setup and reauth

    - `async_step_user()` - API token input
    - `async_step_select_home()` - Home selection
    - `async_step_reauth()` / `async_step_reauth_confirm()` - Reauth flow

2. **Subentry Flow** (`config_flow/subentry_flow.py`) - Add additional homes

    - `async_step_user()` - Select from available homes
    - `async_step_init()` - Subentry options

3. **Options Flow** (`config_flow/options_flow.py`) - Reconfiguration
    - `async_step_init()` - General settings
    - `async_step_current_interval_price_rating()` - Price rating thresholds
    - `async_step_volatility()` - Volatility settings
    - `async_step_best_price()` - Best price period settings
    - `async_step_peak_price()` - Peak price period settings
    - `async_step_price_trend()` - Price trend thresholds

To add a new step:

1. Add schema function to `config_flow/schemas.py`
2. Add step method to appropriate flow handler
3. Add translations to `/translations/*.json`
4. Update step navigation (next step calls)
5. Update `_STEP_INFO` dict in options flow if adding to multi-step wizard

**Add a new service:**

1. Define schema in `services.py` (top-level constants)
2. Add service definition to `services.yaml`
3. Implement handler function in `services.py`
4. Register in `async_setup_services()`

**Change update intervals:**
Edit `UPDATE_INTERVAL` in `coordinator/core.py` (default: 15 min) for API polling, or `QUARTER_HOUR_BOUNDARIES` in `coordinator/constants.py` for entity refresh timing (defaults to `[0, 15, 30, 45]`). Timer scheduling uses `async_track_utc_time_change()` for absolute-time triggers, not relative delays.

**Debug GraphQL queries:**
Check `api.py` → `QueryType` enum and `_build_query()` method. Queries are dynamically constructed based on operation type.

## Debugging Unknown Home Assistant Patterns

When encountering unfamiliar HA patterns (especially UI/config flow/translation related):

**1. Check Official HA Documentation First:**

-   **Config Flow**: https://developers.home-assistant.io/docs/config_entries_config_flow_handler
-   **Translations**: https://developers.home-assistant.io/docs/internationalization/core
-   **Selectors**: https://developers.home-assistant.io/docs/blueprint/selectors
-   **Data Entry Flow**: https://developers.home-assistant.io/docs/data_entry_flow_index

**2. Search HA Core Codebase:**

-   Repository: https://github.com/home-assistant/core
-   Look for similar patterns in core integrations (use GitHub search)
-   Check `homeassistant/helpers/` for utility patterns
-   Example: Search for `translation_key` usage to see real-world examples

**3. Test Incrementally:**

-   Make small changes, test each one
-   Don't assume complex solutions work without verification
-   Ask user to test with `./scripts/develop` when needed

**Real Example from This Project:**
During translation implementation, we tried several incorrect structures:

-   ❌ `selector.select.options.{field_name}` (didn't work)
-   ❌ `selector.select.{translation_key}` (didn't work)
-   ❌ `options.step.{step_id}.data.{field}.options` (overly complex)

Only after consulting the official HA docs did we discover the correct pattern:

-   ✅ `selector.{translation_key}.options.{value}` (simple, flat structure)

**Lesson:** When stuck, consult official docs first - don't guess at complex nested structures.

## Anti-Patterns to Avoid

**Never do these:**

-   ❌ **Blocking operations in event loop**: Use `aiohttp` with `async_get_clientsession(hass)`, not `requests.get()`. Use `await asyncio.sleep()`, not `time.sleep()`.
-   ❌ **Processing data inside try block**: Move data processing outside exception handlers. Only API calls belong in try blocks.
-   ❌ **Hardcoded strings (not translatable)**: Use `translation_key` instead of `_attr_name = "Temperature Sensor"`.
-   ❌ **Accessing hass.data directly in tests**: Use proper fixtures.
-   ❌ **User-configurable polling intervals**: Integration determines this, not users.
-   ❌ **Using standard library datetime**: Use `dt_util.now()` instead of `datetime.now()`.

**See code for correct patterns:**
-   Async operations: `api/client.py`
-   Exception handling: `coordinator/core.py`
-   Translations: `sensor/definitions.py` (translation_key usage)
-   Test fixtures: `tests/conftest.py`
-   Time handling: Any file importing `dt_util`
