# Agent configuration

This directory is the vendor-neutral home for shared agent instructions, skills, lifecycle-hook implementations, and
scratch work. Vendor discovery files under `.github/`, `.claude/`, `.codex/`, and `.opencode/` either link here or call the
shared implementation.

```text
.agents/
├── hooks/          shared lifecycle-hook implementations
├── instructions/   path-scoped style rules, one file per file type
├── skills/         task-triggered procedures (Agent Skills standard)
└── scratch/        working notes and generated reports — gitignored
```

## Which client reads what

Discovery paths are per-vendor; no standard defines them. Real directories live where the most clients look, and
symlinks fill the rest:

| Client         | Always-loaded context                   | Path-scoped rules                     | Skills            |
| -------------- | --------------------------------------- | ------------------------------------- | ----------------- |
| Codex CLI      | `AGENTS.md` (native)                    | — none; open the file yourself        | `.agents/skills/` |
| GitHub Copilot | `AGENTS.md` (native)                    | `.github/instructions/` via `applyTo` | `.agents/skills/` |
| VS Code        | `AGENTS.md` (native)                    | `.github/instructions/` via `applyTo` | `.agents/skills/` |
| Claude Code    | `CLAUDE.md`, which imports `@AGENTS.md` | `.claude/rules/` via `paths`          | `.claude/skills/` |
| OpenCode (v2)  | `AGENTS.md` (native; never `CLAUDE.md`) | — none; open the file yourself        | `.agents/skills/` |

```text
.agents/instructions/         real directory — edit here
.agents/skills/               real directory — edit here
.agents/hooks/                real directory — called by vendor hook configs
.github/instructions        → ../.agents/instructions
.claude/rules/instructions  → ../../.agents/instructions
.claude/skills              → ../.agents/skills
```

Editing through a symlink edits the same file. Do it in `.agents/` anyway, so your diff shows the path other
maintainers see. Never turn a symlink back into a real directory — that is how vendor copies drift apart.

Lifecycle hooks are configured in `.claude/settings.json` for Claude Code, VS Code, and local Copilot, in
`.codex/hooks.json` for Codex, and in `.opencode/plugins/blueprint-hooks.js` for OpenCode. All of them call the same
scripts under `.agents/hooks/`; edit the shared script rather than forking behavior into a client directory.

Each instructions file carries the same glob list twice: `applyTo` for Copilot and VS Code, `paths` for Claude Code.
`script/skills-check` fails the build if the two disagree, or if `paths` is missing — a rule without it loads into
every Claude Code session instead of the files it was scoped to.

## The four layers

| Layer                             | Loaded                      | Contains                                             |
| --------------------------------- | --------------------------- | ---------------------------------------------------- |
| `AGENTS.md`                       | always                      | project identity, workflow rules, validation loop    |
| `.agents/instructions/*.md`       | per touched file            | passive style rules for a file type                  |
| `.agents/skills/*/SKILL.md`       | when the task matches       | active procedures — how to carry out a specific task |
| `docs/development/`, `docs/user/` | when a human or agent reads | explanations, decisions, human-facing guides         |

Rule of thumb: _style rules_ belong in `instructions/`, _procedures_ belong in a skill, _explanations_ belong in
`docs/`. If you find yourself repeating a procedure in `AGENTS.md`, it is a skill.

Codex and OpenCode are the exception on layer two — their nested `AGENTS.md` support keys off the working directory
or the files read, not on file-type patterns, so no instructions file loads automatically. Every skill therefore names the instructions file it depends on.

## Placeholders

Files here use generic placeholders instead of this project's concrete identifiers, so template sync can update them
without clobbering an initialized repository:

| Placeholder     | Means                                                            | Example in this repo    |
| --------------- | ---------------------------------------------------------------- | ----------------------- |
| `<domain>`      | the integration domain, i.e. the `DOMAIN` constant in `const.py` | `ha_integration_domain` |
| `{ClassPrefix}` | the class name prefix used by every integration class            | `IntegrationBlueprint`  |

Substitute them mentally against `const.py` and `manifest.json`; never write them literally into code.

## Customizing in your own repository

This directory arrives through the template sync workflow. Where an addition belongs depends on who owns the
knowledge:

| Your addition is…                                 | Do this                                                  |
| ------------------------------------------------- | -------------------------------------------------------- |
| Generally useful for Home Assistant integrations  | Contribute it upstream — then the blueprint maintains it |
| Specific to your device, API or product decisions | Write your own skill — no sync configuration needed      |
| A correction or contradiction of a blueprint file | Take ownership of that file via `.templatesyncignore`    |
| A lesson from a bug or a repeated correction      | [`blueprint-lessons`](skills/blueprint-lessons/SKILL.md) |

**Add your own skills — nothing to configure.** Template sync is a merge, not a mirror: it only touches files that
changed _upstream_. A directory the blueprint does not have is never overwritten and never deleted. Create
`.agents/skills/<your-prefix>-<topic>/SKILL.md` and it is yours.

A companion skill is usually better than a fork. Skills do not exclude each other, so yours can extend a blueprint
skill instead of replacing it — say so in its description:

```yaml
description: >-
  MyDevice's API paginates by cursor and rate-limits per account. Use alongside the coordinator and API skills
  whenever fetching or debugging MyDevice data.
```

> [!NOTE]
> Do not add extra files inside a blueprint skill's directory. Reference files are only loaded when `SKILL.md` links
> to them, and `SKILL.md` is owned by the blueprint — so the link would be overwritten at the next sync. If you need
> the blueprint skill itself to change, take ownership of it or contribute the change upstream.

**Change a blueprint file — add it to `.templatesyncignore`.** Without an entry, the next sync that touches it
replaces your version, because the workflow resolves conflicts in the template's favour. With one, the file is yours —
including the job of keeping it current:

```text
# I maintain my own version of these
.agents/skills/ha-testing/
.agents/instructions/blueprint.python.instructions.md
```

**Switch a skill off — delete it _and_ ignore it.** A deleted directory comes back the next time the blueprint changes
that skill, so both steps are needed:

```bash
rm -r .agents/skills/ha-release
printf '.agents/skills/ha-release/\n' >> .templatesyncignore
```

If you find yourself re-applying the same edit after every sync PR, that is the signal to take ownership of the file
rather than fixing it again each week.

## Validation

```bash
script/skills-check   # skills, instruction files and agent protected paths — part of script/lint-check, so CI enforces it
```

Writing and maintaining skills is documented in [`skills/README.md`](skills/README.md).
