# Agent Skills

Task-triggered playbooks written against the open [Agent Skills standard](https://agentskills.io/specification), which
Claude Code, GitHub Copilot, VS Code, OpenAI Codex CLI, OpenCode, Cursor, Gemini CLI and others implement.

For how this directory is discovered, which client reads which path, the placeholder convention, and how to customize
any of it in your own repository, see [`../README.md`](../README.md). This file is about the skills themselves.

## Available skills

| Skill                                                   | Use when                                                                    |
| ------------------------------------------------------- | --------------------------------------------------------------------------- |
| [`ha-entity-platform`](ha-entity-platform/SKILL.md)     | adding or changing an entity platform or an individual entity               |
| [`ha-service-action`](ha-service-action/SKILL.md)       | adding or changing a service action (`services.yaml` + handler)             |
| [`ha-config-flow`](ha-config-flow/SKILL.md)             | config flow, options, reauth, reconfigure, discovery, subentries            |
| [`ha-coordinator-debug`](ha-coordinator-debug/SKILL.md) | entities unavailable, stale data, setup failures, runtime debugging         |
| [`ha-translations`](ha-translations/SKILL.md)           | `translations/*.json`, `icons.json`, entity and exception translations      |
| [`ha-user-experience`](ha-user-experience/SKILL.md)     | deciding what users see — states, attributes, icons, options, help, actions |
| [`ha-testing`](ha-testing/SKILL.md)                     | writing or fixing tests with `pytest-homeassistant`                         |
| [`ha-quality-review`](ha-quality-review/SKILL.md)       | auditing the integration against the Integration Quality Scale              |
| [`ha-modern-apis`](ha-modern-apis/SKILL.md)             | verifying an API is current, or fixing deprecation warnings                 |
| [`ha-breaking-changes`](ha-breaking-changes/SKILL.md)   | anything that could break existing installs — IDs, entry data, migrations   |
| [`blueprint-decisions`](blueprint-decisions/SKILL.md)   | recording or superseding an architectural decision, and its index           |
| [`blueprint-lessons`](blueprint-lessons/SKILL.md)       | keeping a lesson from a bug or a repeated correction; project skills        |
| [`ha-release`](ha-release/SKILL.md)                     | cutting a release, commit messages, changelog, release notes                |
| [`ha-marketplace`](ha-marketplace/SKILL.md)             | publishing through the Marketplace/HACS catalog, `hacs.json`, brand images  |
| [`blueprint-tooling`](blueprint-tooling/SKILL.md)       | validation scripts, hook scripts, dependencies, template sync               |
| [`blueprint-update`](blueprint-update/SKILL.md)         | carrying over blueprint changes the template sync cannot deliver            |
| [`blueprint-scaffold`](blueprint-scaffold/SKILL.md)     | turning the fresh template into an integration for one real device          |
| [`blueprint-import`](blueprint-import/SKILL.md)         | migrating an existing custom integration into this repository               |

`blueprint-scaffold` and `blueprint-import` are one-time skills: each ends with a step that removes itself once its
job is done. Leaving them in place costs context in every later session.

## Naming

Two namespaces are in use, by topic rather than by origin:

| Prefix       | Covers                                                            |
| ------------ | ----------------------------------------------------------------- |
| `ha-`        | Home Assistant integration development — entities, flows, testing |
| `blueprint-` | Tooling and agent workflow the template ships — scripts, lessons  |

Both are reserved for skills that ship with the blueprint. **Give your own skills a different prefix** — your
integration's short name works well. That keeps a future blueprint skill from colliding with yours, and makes it
obvious in a listing which skills you own.

The directory name is also the invocation name (`/ha-testing`), so keep it short and stable. Renaming a skill changes
how people invoke it and silently breaks any `.templatesyncignore` entry that pinned the old path.

## Writing a new skill

The [specification](https://agentskills.io/specification) defines the directory layout, the frontmatter fields and
their limits, and how progressive disclosure works. Do not memorise it — `script/skills-check` enforces every
mechanical rule and names the violation. What follows is only what the spec does _not_ tell you.

1. Create `.agents/skills/<kebab-case-name>/SKILL.md`.
2. **Write the description as a folded block scalar.** A plain one-line value cannot contain a colon followed by a
   space, which every realistic description does. The resulting YAML error makes the skill invisible to every client,
   silently.

   ```yaml
   ---
   name: my-skill
   description: >-
     What it does. Use when <triggers and keywords a developer would actually type>.
     SYMPTOMS — load this if you are about to: <agent mistakes this skill prevents>.
   ---
   ```

3. **End the description with a SYMPTOMS clause.** The description is the only thing an agent sees before activating.
   Triggers catch the user's phrasing; symptoms catch the agent's own bad habits — which is exactly when a skill is
   needed and least likely to be asked for by name.
4. **Stick to `name` and `description`.** The spec allows four more fields; each one is something a client in this
   repository's target set might not support.
5. **List reference files in a `File | When to read` table** so an agent can pick one without opening all of them.
6. Run `script/skills-check` and `script/markdown`.

## Authoring principles

**The context window is a public good.** Only write down what the agent does not already know. Challenge every
paragraph: does its token cost buy anything? General Python or async advice does not; this project's layering rules,
the Home Assistant contracts, and the reasons behind them do.

**Concise over complete.** These are working procedures, not tutorials. Prefer a rule and one example over an
explanation.

**Consistent terminology.** One term per concept, used the same way in every skill.

**Do not couple skills to tool names.** Reference this repository's `script/*` commands and Home Assistant concepts —
not the tool names of one particular agent, which differ per vendor and change over time.

**Do not restate `AGENTS.md` or the path-scoped instruction files.** Link to them.

**Stay template-sync safe.** Use the `<domain>` and `{ClassPrefix}` placeholders, never the concrete identifiers —
`script/skills-check` fails the build if a real one slips in.

## Validating skills

```bash
script/skills-check  # structure: frontmatter, limits, links, placeholders
```

`script/skills-check` runs as part of `script/lint`, `script/lint-check` and therefore CI, and as a pre-commit hook on
`.agents/skills/`. When the optional [`skills-ref`](https://pypi.org/project/skills-ref/) package is installed it also
cross-checks each skill with the Agent Skills reference validator.
