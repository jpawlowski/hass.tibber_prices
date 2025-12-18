# Refactoring Guide

This guide explains how to plan and execute major refactorings in this project.

## When to Plan a Refactoring

Not every code change needs a detailed plan. Create a refactoring plan when:

🔴 **Major changes requiring planning:**

-   Splitting modules into packages (>5 files affected, >500 lines moved)
-   Architectural changes (new packages, module restructuring)
-   Breaking changes (API changes, config format migrations)

🟡 **Medium changes that might benefit from planning:**

-   Complex features with multiple moving parts
-   Changes affecting many files (>3 files, unclear best approach)
-   Refactorings with unclear scope

🟢 **Small changes - no planning needed:**

-   Bug fixes (straightforward, `<`100 lines)
-   Small features (`<`3 files, clear approach)
-   Documentation updates
-   Cosmetic changes (formatting, renaming)

## The Planning Process

### 1. Create a Planning Document

Create a file in the `planning/` directory (git-ignored for free iteration):

```bash
# Example:
touch planning/my-feature-refactoring-plan.md
```

**Note:** The `planning/` directory is git-ignored, so you can iterate freely without polluting git history.

### 2. Use the Planning Template

Every planning document should include:

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

See `planning/README.md` for detailed template explanation.

### 3. Iterate Freely

Since `planning/` is git-ignored:

-   Draft multiple versions
-   Get AI assistance without commit pressure
-   Refine until the plan is solid
-   No need to clean up intermediate versions

### 4. Implementation Phase

Once plan is approved:

-   Follow the phases defined in the plan
-   Test after each phase (don't skip!)
-   Update plan if issues discovered
-   Track progress through phase status

### 5. After Completion

**Option A: Archive in docs/development/**
If the plan has lasting value (successful pattern, reusable approach):

```bash
mv planning/my-feature-refactoring-plan.md docs/development/
git add docs/development/my-feature-refactoring-plan.md
git commit -m "docs: archive successful refactoring plan"
```

**Option B: Delete**
If the plan served its purpose and code is the source of truth:

```bash
rm planning/my-feature-refactoring-plan.md
```

**Option C: Keep locally (not committed)**
For "why we didn't do X" reference:

```bash
mkdir -p planning/archive
mv planning/my-feature-refactoring-plan.md planning/archive/
# Still git-ignored, just organized
```

## Real-World Example

The **sensor/ package refactoring** (Nov 2025) is a successful example:

**Before:**

-   `sensor.py` - 2,574 lines, hard to navigate

**After:**

-   `sensor/` package with 5 focused modules
-   Each module `<`800 lines
-   Clear separation of concerns

**Process:**

1. Created `planning/module-splitting-plan.md` (now in `docs/development/`)
2. Defined 6 phases with clear file lifecycle
3. Implemented phase by phase
4. Tested after each phase
5. Documented in AGENTS.md
6. Moved plan to `docs/development/` as reference

**Key learnings:**

-   Temporary `_impl.py` files avoid Python package conflicts
-   Test after EVERY phase (don't accumulate changes)
-   Clear file lifecycle (CREATE/MODIFY/DELETE/RENAME)
-   Phase-by-phase approach enables safe rollback

**Note:** The complete module splitting plan was documented during implementation but has been superseded by the actual code structure.

## Phase-by-Phase Implementation

### Why Phases Matter

Breaking refactorings into phases:

-   ✅ Enables testing after each change (catch bugs early)
-   ✅ Allows rollback to last good state
-   ✅ Makes progress visible
-   ✅ Reduces cognitive load (focus on one thing)
-   ❌ Takes more time (but worth it!)

### Phase Structure

Each phase should:

1. **Have clear goal** - What's being changed?
2. **Document file lifecycle** - CREATE/MODIFY/DELETE/RENAME
3. **Define success criteria** - How to verify it worked?
4. **Include testing steps** - What to test?
5. **Estimate time** - Realistic time budget

### Example Phase Documentation

```markdown
### Phase 3: Extract Helper Functions (Session 3)

**Goal**: Move pure utility functions to helpers.py

**File Lifecycle**:

-   ✨ CREATE `sensor/helpers.py` (utility functions)
-   ✏️ MODIFY `sensor/core.py` (import from helpers.py)

**Steps**:

1. Create sensor/helpers.py
2. Move pure functions (no state, no self)
3. Add comprehensive docstrings
4. Update imports in core.py

**Estimated time**: 45 minutes

**Success criteria**:

-   ✅ All pure functions moved
-   ✅ `./scripts/lint-check` passes
-   ✅ HA starts successfully
-   ✅ All entities work correctly
```

## Testing Strategy

### After Each Phase

Minimum testing checklist:

```bash
# 1. Linting passes
./scripts/lint-check

# 2. Home Assistant starts
./scripts/develop
# Watch for startup errors in logs

# 3. Integration loads
# Check: Settings → Devices & Services → Tibber Prices
# Verify: All entities appear

# 4. Basic functionality
# Test: Data updates without errors
# Check: Entity states update correctly
```

### Comprehensive Testing (Final Phase)

After completing all phases:

-   Test all entities (sensors, binary sensors)
-   Test configuration flow (add/modify/remove)
-   Test options flow (change settings)
-   Test services (custom service calls)
-   Test error handling (disconnect API, invalid data)
-   Test caching (restart HA, verify cache loads)
-   Test time-based updates (quarter-hour refresh)

## Common Pitfalls

### ❌ Skip Planning for Large Changes

**Problem:** "This seems straightforward, I'll just start coding..."

**Result:** Halfway through, realize the approach doesn't work. Wasted time.

**Solution:** If unsure, spend 30 minutes on a rough plan. Better to plan and discard than get stuck.

### ❌ Implement All Phases at Once

**Problem:** "I'll do all phases, then test everything..."

**Result:** 10+ files changed, 2000+ lines modified, hard to debug if something breaks.

**Solution:** Test after EVERY phase. Commit after each successful phase.

### ❌ Forget to Update Documentation

**Problem:** Code is refactored, but AGENTS.md and docs/ still reference old structure.

**Result:** AI/humans get confused by outdated documentation.

**Solution:** Include "Documentation Phase" at the end of every refactoring plan.

### ❌ Ignore the Planning Directory

**Problem:** "I'll just create the plan in docs/ directly..."

**Result:** Git history polluted with draft iterations, or pressure to "commit something" too early.

**Solution:** Always use `planning/` for work-in-progress. Move to `docs/` only when done.

## Integration with AI Development

This project uses AI heavily (GitHub Copilot, Claude). The planning process supports AI development:

**AI reads from:**

-   `AGENTS.md` - Long-term memory, patterns, conventions (AI-focused)
-   `docs/development/` - Human-readable guides (human-focused)
-   `planning/` - Active refactoring plans (shared context)

**AI updates:**

-   `AGENTS.md` - When patterns change
-   `planning/*.md` - During refactoring implementation
-   `docs/development/` - After successful completion

**Why separate AGENTS.md and docs/development/?**

-   `AGENTS.md`: Technical, comprehensive, AI-optimized
-   `docs/development/`: Practical, focused, human-optimized
-   Both stay in sync but serve different audiences

See [AGENTS.md](https://github.com/jpawlowski/hass.tibber_prices/blob/main/AGENTS.md) section "Planning Major Refactorings" for AI-specific guidance.

## Tools and Resources

### Planning Directory

-   `planning/` - Git-ignored workspace for drafts
-   `planning/README.md` - Detailed planning documentation
-   `planning/*.md` - Active refactoring plans

### Example Plans

-   `docs/development/module-splitting-plan.md` - ✅ Completed, archived
-   `planning/config-flow-refactoring-plan.md` - 🔄 Planned (1013 lines → 4 modules)
-   `planning/binary-sensor-refactoring-plan.md` - 🔄 Planned (644 lines → 4 modules)
-   `planning/coordinator-refactoring-plan.md` - 🔄 Planned (1446 lines, high complexity)

### Helper Scripts

```bash
./scripts/lint-check   # Verify code quality
./scripts/develop      # Start HA for testing
./scripts/lint         # Auto-fix issues
```

## FAQ

### Q: When should I create a plan vs. just start coding?

**A:** If you're asking this question, you probably need a plan. 😊

Simple rule: If you can't describe the entire change in 3 sentences, create a plan.

### Q: How detailed should the plan be?

**A:** Detailed enough to execute without major surprises, but not a line-by-line script.

Good plan level:

-   Lists all files affected (CREATE/MODIFY/DELETE)
-   Defines phases with clear boundaries
-   Includes testing strategy
-   Estimates time per phase

Too detailed:

-   Exact code snippets for every change
-   Line-by-line instructions

Too vague:

-   "Refactor sensor.py to be better"
-   No phase breakdown
-   No testing strategy

### Q: What if the plan changes during implementation?

**A:** Update the plan! Planning documents are living documents.

If you discover:

-   Better approach → Update "Proposed Solution"
-   More phases needed → Add to "Migration Strategy"
-   New risks → Update "Risks & Mitigation"

Document WHY the plan changed (helps future refactorings).

### Q: Should every refactoring follow this process?

**A:** No! Use judgment:

-   **Small changes (`<`100 lines, clear approach)**: Just do it, no plan needed
-   **Medium changes (unclear scope)**: Write rough outline, refine if needed
-   **Large changes (>500 lines, >5 files)**: Full planning process

### Q: How do I know when a refactoring is successful?

**A:** Check the "Success Criteria" from your plan:

Typical criteria:

-   ✅ All linting checks pass
-   ✅ HA starts without errors
-   ✅ All entities functional
-   ✅ No regressions (existing features work)
-   ✅ Code easier to understand/modify
-   ✅ Documentation updated

If you can't tick all boxes, the refactoring isn't done.

## Summary

**Key takeaways:**

1. **Plan when scope is unclear** (>500 lines, >5 files, breaking changes)
2. **Use planning/ directory** for free iteration (git-ignored)
3. **Work in phases** and test after each phase
4. **Document file lifecycle** (CREATE/MODIFY/DELETE/RENAME)
5. **Update documentation** after completion (AGENTS.md, docs/)
6. **Archive or delete** plan after implementation

**Remember:** Good planning prevents half-finished refactorings and makes rollback easier when things go wrong.

---

**Next steps:**

-   Read `planning/README.md` for detailed template
-   Check `docs/development/module-splitting-plan.md` for real example
-   Browse `planning/` for active refactoring plans
