# The old repository's agent knowledge

For [`blueprint-import`](../SKILL.md), phase 3. An integration that already worked with agents brings rules,
procedures and decisions written for them. Some of it is knowledge no one else has; most of it is a copy of general
advice, a rule the blueprint now ships, or a description of code that has since changed. Taken over whole, it costs
context in every session and contradicts the shipped rules; dropped whole, it loses what the project learned.

**Sort it rule by rule, never file by file.** The overlay keeps the blueprint's `AGENTS.md`, `CLAUDE.md` and
`.agents/`; the old files stay readable with `git show main:<path>`.

## Where it is

`script/import-overlay` lists the files under _Agent instructions_ in `.agents/scratch/import-overlay.md`:
`AGENTS.md`, `CLAUDE.md` and `GEMINI.md` at any depth, `.github/copilot-instructions.md`, `.github/instructions/`,
`.github/prompts/`, `.github/agents/`, `.cursor/`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `.claude/`,
`.codex/`, `.opencode/` and an older `.agents/`. Look beyond the list too: a developer documentation site or a
`docs/` section written for agents, and long comment blocks addressed to them.

`.claude/settings.json` and its relatives hold permissions and hooks, not knowledge: compare them with the blueprint's
and carry over a project-specific permission. `settings.local.json` is personal and never committed.

## Sort each rule into one bucket

Work in a table in `.agents/scratch/import-agent-knowledge.md` — source and line, the rule in a few words, bucket,
target:

| Bucket                | Test                                                                                 | What happens                                                                        |
| --------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| **Shipped**           | A blueprint instructions file, skill or `AGENTS.md` says the same                    | Dropped                                                                             |
| **General**           | Python, Home Assistant or tool knowledge any reader can look up                      | Dropped                                                                             |
| **Stale**             | It names a file, symbol, script or setting that no longer exists, or a replaced tool | Dropped, with the missing name as evidence                                          |
| **Conflict**          | It contradicts a shipped rule                                                        | The developer decides: dropped, or a project deviation with its reason              |
| **Decision**          | It records a choice and why it was made                                              | A decision record, `migrated-from` set, shown to the developer before it is written |
| **Project rule**      | It holds for this integration only, and an agent would get it wrong without it       | The area's project instructions file, or `AGENTS.md` if it bears on most sessions   |
| **Project procedure** | Several steps only this project has: capturing a payload, debugging its calculation  | A project skill                                                                     |
| **Explanation**       | It explains the domain or the design to a person                                     | `docs/development/` — `ARCHITECTURE.md`, `GLOSSARY.md`                              |

The homes, their names and their size limits are [`blueprint-lessons`](../../blueprint-lessons/SKILL.md) §3; a rule
there is written as a rule plus one sentence of why, whatever shape it had in the old file.

**Find the stale ones mechanically before judging the rest.** For every path, module, class, function, script and
command the old text names, check that it exists — `git ls-files`, `rg` from the repository root, `script/<name>`.
An instruction about code that is gone is stale however sensible it reads.

## Then

- **Report the inventory before writing anything**: how many rules in each bucket, every Conflict and every Decision
  in full. The developer answers those; the rest follows the table.
- **Carry it over as its own commit**, after the phase 2 checkpoint and before phase 4, so the project rules guide the
  refactoring and a revert of either leaves the other intact.
- **Expect most of it to go.** Several thousand lines of old instructions typically end as a handful of project
  files. A large remainder means the sorting was too lenient, not that the project is special.
