# Planning Directory

**Purpose**: Work-in-progress planning documents for major refactorings and architectural changes.

**Status**: 🚫 **GIT-IGNORED** (files in this directory are NOT committed to the repository)

---

## Why This Directory Exists

Large-scale refactorings require careful planning before implementation. This directory provides a space for:

1. **Detailed planning documents** - Breaking down complex changes into phases
2. **Architecture proposals** - Evaluating different approaches
3. **Migration strategies** - Step-by-step transformation plans
4. **Risk analysis** - Identifying potential issues before coding

## Directory Structure

```
planning/
├── README.md                           # This file
├── <feature>-refactoring-plan.md       # Active planning documents
└── archive/                            # Completed plans (optional)
```

## Document Lifecycle

### 1. **Planning Phase** (WIP, in planning/)

-   Document created in `planning/`
-   Iterative refinement with AI assistance
-   Multiple revisions until plan is solid
-   **NOT committed to git** (allows messy iteration)

### 2. **Review Phase** (Ready for implementation)

-   Plan is reviewed and finalized
-   Decision: Implement or Archive

### 3. **Implementation Phase** (Active work)

-   Plan used as reference during implementation
-   Can be updated as issues are discovered
-   Still in `planning/` until complete

### 4. **Completion Phase** (Done)

-   **Option A**: Move to `docs/development/` as historical reference

    -   Rename: `planning/config-flow-refactoring-plan.md` → `docs/development/config-flow-refactoring.md`
    -   Update status to "✅ COMPLETED"
    -   Commit to repository as documentation

-   **Option B**: Delete if superseded by code/docs

    -   Plan served its purpose
    -   Code and AGENTS.md are the source of truth

-   **Option C**: Archive in `planning/archive/`
    -   Keep for reference but don't commit
    -   Useful for "why we didn't do X" decisions

## Planning Document Template

See `docs/development/module-splitting-plan.md` for a successful example of a completed plan that was moved to documentation.

### Required Sections

1. **Status & Metadata**

    ```markdown
    **Status**: 🔄 PLANNING | 🚧 IN PROGRESS | ✅ COMPLETED | ❌ CANCELLED
    **Created**: YYYY-MM-DD
    **Last Updated**: YYYY-MM-DD
    ```

2. **Problem Statement**

    - What's the issue?
    - Why does it need fixing?
    - Current pain points

3. **Proposed Solution**

    - High-level approach
    - File structure (before/after)
    - Module responsibilities

4. **Migration Strategy**

    - Phase-by-phase breakdown
    - Dependencies between phases
    - Testing checkpoints

5. **Risks & Mitigation**

    - What could go wrong?
    - How to prevent it?
    - Rollback strategy

6. **Success Criteria**
    - How do we know it worked?
    - Metrics to measure
    - Testing requirements

## Active Plans

<!-- Update this list as plans are created/completed -->

-   None (all previous plans completed and moved to docs/)

## Best Practices

### ✅ DO:

-   Iterate freely - planning/ is git-ignored for a reason
-   Break complex changes into clear phases
-   Document file lifecycle (CREATE/MODIFY/DELETE/RENAME)
-   Include code examples and patterns
-   Estimate time per phase
-   Plan testing after each phase

### ❌ DON'T:

-   Start coding before plan is solid
-   Skip the "Why?" section
-   Forget to update status as you progress
-   Commit planning/ files to git (they're ignored!)
-   Over-plan simple changes (some things don't need a plan)

## When to Create a Planning Document

**Create a plan when:**

-   🔴 Major refactoring (>5 files, >500 lines changed)
-   🔴 Architectural changes (new packages, restructuring)
-   🔴 Breaking changes (API changes, config format changes)
-   🟡 Complex features (multiple moving parts, unclear approach)

**Skip planning for:**

-   🟢 Bug fixes (straightforward)
-   🟢 Small features (<3 files, clear approach)
-   🟢 Documentation updates
-   🟢 Cosmetic changes (formatting, renaming)

## Integration with AGENTS.md

When planning is complete and implementation successful:

1. Update `AGENTS.md` with new patterns/conventions
2. Move plan to `docs/development/` if it has lasting value
3. Delete or archive if superseded by docs

The planning document and `AGENTS.md` serve different purposes:

-   **Planning doc**: Temporary guide DURING transformation
-   **AGENTS.md**: Permanent guide AFTER transformation

---

**Remember**: Planning documents are throwaway scaffolding. The real documentation lives in `AGENTS.md` and `docs/`.
