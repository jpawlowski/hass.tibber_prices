@AGENTS.md

# Claude Code Instructions

Claude Code reads `CLAUDE.md`, not `AGENTS.md`, so the import above is what loads the shared instruction file every
agent in this repository uses. Everything else — project identity, architecture, workflow rules, validation — lives
there and is not repeated here.

## How the pieces reach Claude Code

| What              | Path Claude Code reads        | Real location           |
| ----------------- | ----------------------------- | ----------------------- |
| Agent skills      | `.claude/skills/`             | `.agents/skills/`       |
| Path-scoped rules | `.claude/rules/instructions/` | `.agents/instructions/` |

Both are symlinks. **Edit the real `.agents/` paths**, so your diff shows the same file another maintainer would
touch.

Path-scoped rules load automatically for the file you are working on, matched by the `paths` key in each file's
frontmatter. If they appear not to apply, that key is the first thing to check — a rule with no `paths` loads into
every session instead, and a malformed one silently loads into none.
