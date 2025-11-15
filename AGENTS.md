# Copilot Instructions

This is a **Home Assistant custom component** for Tibber electricity price data, distributed via **HACS**. It fetches, caches, and enriches **quarter-hourly** electricity prices with statistical analysis, price levels, and ratings.

## Documentation Metadata

-   **Last Major Update**: 2025-11-17
-   **Last Architecture Review**: 2025-11-17 (Module splitting refactoring completed - sensor.py split into sensor/ package with core.py, definitions.py, helpers.py, attributes.py. Created entity_utils/ package for shared icon/color/attribute logic. All phases complete.)
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

## Architecture Overview

**Core Data Flow:**

1. `TibberPricesApiClient` (`api.py`) queries Tibber's GraphQL API with `resolution:QUARTER_HOURLY` for user data and prices (yesterday/today/tomorrow - 192 intervals total)
2. `TibberPricesDataUpdateCoordinator` (`coordinator.py`) orchestrates updates every 15 minutes, manages persistent storage via `Store`, and schedules quarter-hour entity refreshes
3. Price enrichment functions (`price_utils.py`, `average_utils.py`) calculate trailing/leading 24h averages, price differences, and rating levels for each 15-minute interval
4. Entity platforms (`sensor/` package, `binary_sensor.py`) expose enriched data as Home Assistant entities
5. Custom services (`services.py`) provide API endpoints for integrations like ApexCharts

**Key Patterns:**

-   **Dual translation system**: Standard HA translations in `/translations/` (config flow, UI strings per HA schema), supplemental in `/custom_translations/` (entity descriptions not supported by HA schema). Both must stay in sync. Use `async_load_translations()` and `async_load_standard_translations()` from `const.py`. When to use which: `/translations/` is bound to official HA schema requirements; anything else goes in `/custom_translations/` (requires manual translation loading). **Schema reference**: `/scripts/json_schemas/translation_schema.json` provides the structure for `/translations/*.json` files based on [HA's translation documentation](https://developers.home-assistant.io/docs/internationalization/core).

    -   **Select selector translations**: Use `selector.{translation_key}.options.{value}` structure (NOT `selector.select.{translation_key}`). Example:

        ```python
        # config_flow.py
        SelectSelector(SelectSelectorConfig(
            options=["LOW", "MODERATE", "HIGH"],
            translation_key="volatility"
        ))
        ```

        ```json
        # translations/en.json
        {
          "selector": {
            "volatility": {
              "options": {
                "low": "Low",
                "moderate": "Moderate",
                "high": "High"
              }
            }
          }
        }
        ```

        **CRITICAL:** When using `translation_key`, pass options as **plain string list**, NOT `SelectOptionDict`.

        **VALIDATION:** Selector option keys MUST be lowercase: `[a-z0-9-_]+` pattern (no uppercase, cannot start/end with hyphen/underscore). Hassfest will reject keys like `LOW`, `ANY`, `VERY_HIGH`. Use `low`, `any`, `very_high` instead.

        ```python
        # ✅ CORRECT with translation_key
        SelectSelector(SelectSelectorConfig(
            options=["LOW", "MODERATE", "HIGH"],  # Plain strings!
            translation_key="volatility"
        ))

        # ❌ WRONG - label parameter overrides translations
        SelectSelector(SelectSelectorConfig(
            options=[SelectOptionDict(value="LOW", label="Low"), ...],
            translation_key="volatility"  # translation_key is ignored when label is set!
        ))

        # ✅ SelectOptionDict ONLY for dynamic/non-translatable options
        SelectSelector(SelectSelectorConfig(
            options=[SelectOptionDict(value=home_id, label=home_name) for ...],
            # No translation_key - labels come from runtime data
        ))
        ```

-   **Price data enrichment**: All quarter-hourly price intervals get augmented with `trailing_avg_24h`, `difference`, and `rating_level` fields via `enrich_price_info_with_differences()` in `price_utils.py`. Enriched structure example:
    ```python
    {
      "startsAt": "2025-11-03T14:00:00+01:00",
      "total": 0.2534,              # Original from API
      "level": "NORMAL",            # Original from API
      "trailing_avg_24h": 0.2312,   # Added: 24h trailing average
      "difference": 9.6,            # Added: % diff from trailing avg
      "rating_level": "NORMAL"      # Added: LOW/NORMAL/HIGH based on thresholds
    }
    ```
-   **Sensor organization (refactored Nov 2025)**: The `sensor/` package is organized by **calculation method** rather than feature type, enabling code reuse through unified handler methods:
    -   **Interval-based sensors**: Use `_get_interval_value(interval_offset, value_type)` for current/next/previous interval data
    -   **Rolling hour sensors**: Use `_get_rolling_hour_value(hour_offset, value_type)` for 5-interval windows
    -   **Daily statistics**: Use `_get_daily_stat_value(day, stat_func)` for calendar day min/max/avg
    -   **24h windows**: Use `_get_24h_window_value(stat_func)` for trailing/leading statistics
    -   **See "Common Tasks" section** for detailed patterns and examples
-   **Quarter-hour precision**: Entities update on 00/15/30/45-minute boundaries via `_schedule_quarter_hour_refresh()` in coordinator, not just on data fetch intervals. This ensures current price sensors update without waiting for the next API poll.
-   **Currency handling**: Multi-currency support with major/minor units (e.g., EUR/ct, NOK/øre) via `get_currency_info()` and `format_price_unit_*()` in `const.py`.
-   **Intelligent caching strategy**: Minimizes API calls while ensuring data freshness:
    -   User data cached for 24h (rarely changes)
    -   Price data validated against calendar day - cleared on midnight turnover to force fresh fetch
    -   Cache survives HA restarts via `Store` persistence
    -   API polling intensifies only when tomorrow's data expected (afternoons)
    -   Stale cache detection via `_is_cache_valid()` prevents using yesterday's data as today's

**Component Structure:**

```
custom_components/tibber_prices/
├── __init__.py           # Entry setup, platform registration
├── coordinator.py        # DataUpdateCoordinator with caching/scheduling
├── api.py                # GraphQL client with retry/error handling
├── price_utils.py        # Price enrichment, level/rating calculations
├── average_utils.py      # Trailing/leading average utilities
├── services.py           # Custom services (get_price, ApexCharts, etc.)
├── sensor/               # Sensor platform (package)
│   ├── __init__.py       #   Platform setup (async_setup_entry)
│   ├── core.py           #   TibberPricesSensor class
│   ├── definitions.py    #   ENTITY_DESCRIPTIONS
│   ├── helpers.py        #   Pure helper functions
│   └── attributes.py     #   Attribute builders
├── binary_sensor.py      # Peak/best hour binary sensors
├── entity.py             # Base TibberPricesEntity class
├── entity_utils/         # Shared entity helpers (both platforms)
│   ├── __init__.py       #   Package exports
│   ├── icons.py          #   Icon mapping logic
│   ├── colors.py         #   Color mapping logic
│   └── attributes.py     #   Common attribute builders
├── data.py               # @dataclass TibberPricesData
├── const.py              # Constants, translation loaders, currency helpers
├── config_flow.py        # UI configuration flow
└── services.yaml         # Service definitions
```

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
-   Release management: `./scripts/prepare-release`, `./scripts/generate-release-notes`

**Release Note Backends (auto-installed in DevContainer):**

-   **Rust toolchain**: Minimal Rust installation via DevContainer feature
-   **git-cliff**: Template-based release notes (fast, reliable, installed via cargo in `scripts/setup`)
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
```

**Linting (auto-fix):**

```bash
./scripts/lint     # Runs ruff format + ruff check --fix
```

**Linting (check-only):**

```bash
./scripts/lint-check  # CI mode, no modifications
```

**Testing:**

```bash
pytest tests/      # Unit tests exist (test_*.py) but no framework enforced
```

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
> git add custom_components/tibber_prices/config_flow.py
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

**Structure:**

```
<type>(<scope>): <short summary (max 50-72 chars)>

<detailed description, wrapped at 72 chars>

Impact: <user-visible effects or context for future release notes>
```

**Best Practices:**

-   **Subject line**: Max 50 chars (hard limit 72), imperative mood ("Add" not "Added")
-   **Body**: Wrap at 72 chars, explain WHAT and WHY (not HOW - code shows that)
-   **Blank line**: Required between subject and body
-   **Impact section**: Our addition for release note generation (optional but recommended)

**Types:**

-   `feat`: New feature (appears in release notes as "New Features")
-   `fix`: Bug fix (appears in release notes as "Bug Fixes")
-   `docs`: Documentation only (appears in release notes as "Documentation")
-   `refactor`: Code restructure without behavior change (may or may not appear in release notes)
-   `chore`: Maintenance tasks (usually omitted from release notes)
-   `test`: Test changes only (omitted from release notes)
-   `style`: Formatting changes (omitted from release notes)

**Scope (optional but recommended):**

-   `translations`: Translation system changes
-   `config_flow`: Configuration flow changes
-   `sensors`: Sensor implementation
-   `api`: API client changes
-   `coordinator`: Data coordinator changes
-   `docs`: Documentation files

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

    - Script: `./scripts/prepare-release VERSION`
    - Bumps manifest.json version → commits → creates tag locally
    - You review and push when ready
    - Example: `./scripts/prepare-release 0.3.0`

2. **Auto-Tag Workflow** (safety net)

    - Workflow: `.github/workflows/auto-tag.yml`
    - Triggers on manifest.json changes
    - Automatically creates tag if it doesn't exist
    - Prevents "forgot to tag" mistakes

3. **Local Script** (testing, preview, and updating releases)

    - Script: `./scripts/generate-release-notes [FROM_TAG] [TO_TAG]`
    - Parses Conventional Commits between tags
    - Supports multiple backends (auto-detected):
        - **AI-powered**: GitHub Copilot CLI (best, context-aware)
        - **Template-based**: git-cliff (fast, reliable)
        - **Manual**: grep/awk fallback (always works)
    - **Auto-update feature**: If a GitHub release exists for TO_TAG, automatically offers to update release notes (interactive prompt)

    **Usage examples:**

    ```bash
    # Generate and preview notes
    ./scripts/generate-release-notes v0.2.0 v0.3.0

    # If release exists, you'll see:
    # → Generated release notes
    # → Detection: "A GitHub release exists for v0.3.0"
    # → Prompt: "Do you want to update the release notes on GitHub? [y/N]"
    # → Answer 'y' to auto-update, 'n' to skip

    # Force specific backend
    RELEASE_NOTES_BACKEND=copilot ./scripts/generate-release-notes v0.2.0 v0.3.0
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
./scripts/suggest-version

# Output shows:
# - Commit analysis (features, fixes, breaking changes)
# - Suggested version based on Semantic Versioning
# - Alternative versions (MAJOR/MINOR/PATCH)
# - Preview and release commands

# Step 2: Preview release notes (with AI if available)
./scripts/generate-release-notes v0.2.0 HEAD

# Step 3: Prepare release (bumps manifest.json + creates tag)
./scripts/prepare-release 0.3.0
# Or without argument to show suggestion first:
./scripts/prepare-release

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
./scripts/generate-release-notes v0.2.0 v0.3.0

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
./scripts/generate-release-notes

# Generate between specific tags
./scripts/generate-release-notes v1.0.0 v1.1.0

# Force specific backend
RELEASE_NOTES_BACKEND=manual ./scripts/generate-release-notes

# Disable AI (use in CI/CD)
USE_AI=false ./scripts/generate-release-notes
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
# Auto-installed in DevContainer via scripts/setup
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

**Validate JSON files:**

```bash
# After editing translation files, validate syntax (ruff doesn't check JSON)
python -m json.tool custom_components/tibber_prices/translations/de.json > /dev/null

# Or validate all translation files at once:
for f in custom_components/tibber_prices/translations/*.json; do
    python -m json.tool "$f" > /dev/null && echo "✓ $f" || echo "✗ INVALID: $f"
done
```

**Why:** `ruff` only formats/lints Python code. JSON syntax errors (trailing commas, missing quotes) will cause HA to fail at runtime with cryptic error messages. Always validate JSON after manual edits.

## Linting Best Practices

**Always use the provided scripts:**

```bash
./scripts/lint        # Auto-fix mode
./scripts/lint-check  # Check-only (CI mode)
```

**Why not call `ruff` directly?**

Calling `ruff` or `uv run ruff` directly can cause unintended side effects:

-   May install the integration as a Python package (creates `__pycache__`, `.egg-info`, etc.)
-   HA will then load the **installed** version instead of the **development** version from `custom_components/`
-   Causes confusing behavior where code changes don't take effect

**Exception:** If you need to run `ruff` with custom flags not supported by our scripts:

1. Run your custom `ruff` command
2. **Immediately after**, clean up any installation artifacts:

    ```bash
    # Remove any accidentally installed package
    uv pip uninstall tibber_prices 2>/dev/null || true

    # Clean up cache and build artifacts
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    ```

3. Ask user to restart HA: `./scripts/develop`

**When in doubt:** Stick to `./scripts/lint` - it's tested and safe.

**Key commands:**

-   Dev container includes `hass` CLI for manual HA operations
-   Use `uv run --active` prefix for running Python tools in the venv
-   `pyproject.toml` (under `[tool.ruff]`) enforces max line length 120, complexity ≤25, Python 3.13 target

## Critical Project-Specific Patterns

**1. Translation Loading (Async-First)**
Always load translations at integration setup or before first use:

```python
# In __init__.py async_setup_entry:
await async_load_translations(hass, "en")
await async_load_standard_translations(hass, "en")
```

Access cached translations synchronously later via `get_translation(path, language)`.

**2. Price Data Enrichment**
Never use raw API price data directly. Always enrich first:

```python
from .price_utils import enrich_price_info_with_differences

enriched = enrich_price_info_with_differences(
    price_info_data,  # Raw API response
    thresholds,       # User-configured rating thresholds
)
```

This adds `trailing_avg_24h`, `difference`, `rating_level` to each interval.

**3. Time Handling**
Always prefer Home Assistant utilities over standard library equivalents. Use `dt_util` from `homeassistant.util` instead of Python's `datetime` module.

**Critical:** Always use `dt_util.as_local()` when comparing API timestamps to local time:

```python
from homeassistant.util import dt as dt_util

# ✅ Use dt_util for timezone-aware operations
price_time = dt_util.parse_datetime(price_data["startsAt"])
price_time = dt_util.as_local(price_time)  # IMPORTANT: Convert to HA's local timezone
now = dt_util.now()  # Current time in HA's timezone

# ❌ Avoid standard library datetime for timezone operations
# from datetime import datetime
# now = datetime.now()  # Don't use this
```

When you need Python's standard datetime types (e.g., for type annotations), import only specific types:

```python
from datetime import date, datetime, timedelta  # For type hints
from homeassistant.util import dt as dt_util    # For operations

def _needs_tomorrow_data(self, tomorrow_date: date) -> bool:
    """Use date type hint but dt_util for operations."""
    price_time = dt_util.parse_datetime(starts_at)
    price_date = dt_util.as_local(price_time).date()  # Convert to local before extracting date
```

**4. Coordinator Data Structure**
Access coordinator data like:

```python
coordinator.data = {
    "user_data": {...},      # Cached user info from viewer query
    "priceInfo": {
        "yesterday": [...],  # List of enriched price dicts
        "today": [...],
        "tomorrow": [...],
        "currency": "EUR",
    },
}
```

**5. Service Response Pattern**
Services use `SupportsResponse.ONLY` and must return dicts:

```python
@callback
def async_setup_services(hass: HomeAssistant) -> None:
    hass.services.async_register(
        DOMAIN, "get_price", _get_price,
        schema=PRICE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
```

## Common Pitfalls (HA-Specific)

**1. Entity State Class Compatibility:**

```python
# ❌ Wrong - MONETARY with MEASUREMENT state class
class PriceSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT  # ← WRONG!

# ✅ Correct - MONETARY with TOTAL or None
class PriceSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL  # Or None for snapshots
```

Rule: Check [HA sensor docs](https://developers.home-assistant.io/docs/core/entity/sensor) for valid `device_class` + `state_class` combinations. Common mistakes: MONETARY requires TOTAL, TIMESTAMP requires None.

**2. Config Flow Input Validation:**

```python
# ❌ Missing validation - creates broken entries
async def async_step_user(self, user_input=None):
    if user_input is not None:
        return self.async_create_entry(title="Name", data=user_input)

# ✅ Always validate before creating entry
async def async_step_user(self, user_input=None):
    if user_input is not None:
        errors = {}
        try:
            await validate_api_connection(self.hass, user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(title="Name", data=user_input)
        return self.async_show_form(step_id="user", errors=errors, ...)
```

Rule: ALWAYS test API connection/validate data before `async_create_entry()`. Use specific error keys for proper translation.

**3. Don't Override async_update() with DataUpdateCoordinator:**

```python
# ❌ Unnecessary - coordinator handles this
class MySensor(CoordinatorEntity):
    async def async_update(self):
        await self.coordinator.async_request_refresh()

# ✅ Only implement properties
class MySensor(CoordinatorEntity):
    @property
    def native_value(self):
        return self.coordinator.data["value"]
```

Rule: When using `DataUpdateCoordinator`, entities get updates automatically. Don't implement `async_update()`.

**4. Service Response Declaration:**

```python
# ❌ Returns data without declaring response support
hass.services.async_register(DOMAIN, "get_data", handler)

# ✅ Explicit response support declaration
hass.services.async_register(
    DOMAIN, "get_data", handler,
    supports_response=SupportsResponse.ONLY,  # ONLY, OPTIONAL, or NONE
)
```

Rule: Services returning data MUST declare `supports_response`. Use `ONLY` for data-only services, `OPTIONAL` for dual-purpose, `NONE` for action-only.

## Code Quality Rules

**Ruff config (`pyproject.toml` under `[tool.ruff]`):**

We use **Ruff** (which replaces Black, Flake8, isort, and more) as our sole linter and formatter:

-   Max line length: **120** chars (not 88 from Ruff's default)
-   Max complexity: **25** (McCabe)
-   Target: Python 3.13
-   No unused imports/variables (`F401`, `F841`)
-   No mutable default args (`B008`)
-   Use `_LOGGER` not `print()` (`T201`)

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
-   **Check if released**: Use `./scripts/check-if-released <commit-hash>` to verify if code is in any `v*.*.*` tag
-   **Example**: If introducing breaking config change in commit `abc123`, run `./scripts/check-if-released abc123`:
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
    return coordinator.data["priceInfo"]["today"][0]["total"]

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
    "periods": [...],          # Nested structures last
    "intervals": [...],

    # 7. Extended descriptions (always last)
    "description": "...",      # Short description from custom_translations (always shown)
    "long_description": "...", # Detailed explanation from custom_translations (shown when CONF_EXTENDED_DESCRIPTIONS enabled)
    "usage_tips": "...",       # Usage examples from custom_translations (shown when CONF_EXTENDED_DESCRIPTIONS enabled)
}
```

**Critical: The `timestamp` Attribute**

The `timestamp` attribute **MUST always be first** in every sensor's attributes. It serves as the reference time indicating:

-   **For which interval** the state and attributes are valid
-   **Current interval sensors**: Contains `startsAt` of the current 15-minute interval
-   **Future/forecast sensors**: Contains `startsAt` of the future interval being calculated
-   **Statistical sensors (min/max)**: Contains `startsAt` of the specific interval when the extreme value occurs
-   **Statistical sensors (avg)**: Contains start of the day (00:00) since average applies to entire day

This allows users to verify data freshness and understand temporal context without parsing other attributes.

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

### Examples

**❌ Bad (Ambiguous):**

```python
attributes = {
    "future_avg_3h": 0.25,           # Future when? From when?
    "later_half_diff_%": 5.2,        # Later than what? Diff from what?
    "remaining_minutes": 45,          # Remaining in what?
    "status": "partial",              # Status of what?
    "hours": [{...}],                 # What about hours?
    "intervals_count": 12,            # Should be singular: interval_count
}
```

**✅ Good (Clear):**

```python
attributes = {
    "next_3h_avg": 0.25,                              # Average of next 3 hours from next interval
    "second_half_3h_diff_from_current_%": 5.2,        # Second half of 3h window vs current price
    "remaining_minutes_in_period": 45,                # Minutes remaining in the current period
    "data_status": "partial",                         # Status of data availability
    "intervals_by_hour": [{...}],                     # Intervals grouped by hour
    "interval_count": 12,                             # Number of intervals (singular)
}
```

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

**Example - Adding a "2 hours ago" interval sensor:**

```python
# 1. Add to INTERVAL_PRICE_SENSORS group in sensor/definitions.py
SensorEntityDescription(
    key="two_hours_ago_price",
    translation_key="two_hours_ago_price",
    name="Price 2 Hours Ago",
    icon="mdi:clock-time-eight",
    device_class=SensorDeviceClass.MONETARY,
    entity_registry_enabled_default=False,
    suggested_display_precision=2,
)

# 2. Add handler in sensor/core.py → _get_value_getter()
"two_hours_ago_price": lambda: self._get_interval_value(
    interval_offset=-8,  # 2 hours = 8 intervals (15 min each)
    value_type="price",
    in_euro=False
),

# 3. Add translations (en.json)
{
  "entity": {
    "sensor": {
      "two_hours_ago_price": {
        "name": "Price 2 Hours Ago"
      }
    }
  }
}

# 4. Add custom translations (custom_translations/en.json)
{
  "sensor": {
    "two_hours_ago_price": {
      "description": "Electricity price from 2 hours ago"
    }
  }
}
```

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

**Modify price calculations:**
Edit `price_utils.py` or `average_utils.py`. These are stateless pure functions operating on price lists.

**Add a new service:**

1. Define schema in `services.py` (top-level constants)
2. Add service definition to `services.yaml`
3. Implement handler function in `services.py`
4. Register in `async_setup_services()`

**Change update intervals:**
Edit `UPDATE_INTERVAL` in `coordinator.py` (default: 15 min) or `QUARTER_HOUR_BOUNDARIES` for entity refresh timing.

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

```python
# ❌ Blocking operations in event loop
data = requests.get(url)  # Use aiohttp with async_get_clientsession(hass)
time.sleep(5)             # Use await asyncio.sleep(5)

# ❌ Processing data inside try block
try:
    data = await api.get_data()
    processed = data["value"] * 100  # Move outside try
    self._attr_native_value = processed
except ApiError:
    pass

# ❌ Hardcoded strings (not translatable)
self._attr_name = "Temperature Sensor"  # Use translation_key instead

# ❌ Accessing hass.data directly in tests
coord = hass.data[DOMAIN][entry.entry_id]  # Use proper fixtures

# ❌ User-configurable polling intervals
vol.Optional("scan_interval"): cv.positive_int  # Not allowed, integration determines this

# ❌ Using standard library datetime for timezone operations
from datetime import datetime
now = datetime.now()  # Use dt_util.now() instead
```

**Do these instead:**

```python
# ✅ Async operations
data = await session.get(url)
await asyncio.sleep(5)

# ✅ Process after exception handling
try:
    data = await api.get_data()
except ApiError:
    return
processed = data["value"] * 100  # Safe processing after try/except

# ✅ Translatable entities
_attr_has_entity_name = True
_attr_translation_key = "temperature_sensor"

# ✅ Proper test setup with fixtures
@pytest.fixture
async def init_integration(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    return mock_config_entry

# ✅ Use Home Assistant datetime utilities
from homeassistant.util import dt as dt_util
now = dt_util.now()  # Timezone-aware current time
```
