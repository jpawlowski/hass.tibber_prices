---
name: blueprint-import
description: >-
  Migrate an existing Home Assistant custom integration into the blueprint's structure and tooling without
  breaking the installations already running it. Use when asked to "import my integration", "migrate my existing
  integration into the blueprint", "adopt the blueprint in my repository", "move my custom component over",
  "restructure my integration to match this layout", or when switching from another template such as the upstream
  ludeeus one. Covers what must stay byte-identical, the git strategy, the phase order that keeps every step
  revertable, the stock-taking audit, and applying this project's rules to legacy code. SYMPTOMS — load this if you are about to: change the integration's domain during the move; run
  the whole migration as one commit; restructure packages before the imported code is green; let an automated
  rename touch unique IDs or translation keys; let the import become a rewrite; start editing without a
  record of the current entity IDs; or merge old agent instructions into `AGENTS.md`.
---

# Import an existing integration

A published integration has users. Their automations, dashboards, and statistics are bound to entity IDs, unique IDs,
state values and action names — none of which the migration is allowed to change. Everything else is negotiable.

**The whole procedure is one long behaviour-preserving refactor.** Treat any observable difference as a bug in the
migration, not as an improvement, unless the developer explicitly asked for it.

## Phase 0 — Baseline first, before touching anything

Without a record of the current behaviour, nothing in the later phases is verifiable.

Two records are needed, and they are not the same thing. This phase captures what the code **does**.
[`ha-grill`](../ha-grill/SKILL.md) captures what the maintainer **wants** — how many installations are at stake,
what is deliberately unusual in there, what they already know is broken, and whether a breaking release is on the
table at all. Run that interview first: its answers decide how much of phases 3 to 7 is affordable, and an import
planned without them optimises for the wrong constraint.

1. **Capture the identity of every entity.** From a running installation, export the entity IDs and unique IDs of the
   integration's entities (the entity registry, or the diagnostics download). If no live instance is available, derive
   them from the code and say so — a derived baseline is weaker.
2. **Record the contract** in a scratch file under `.agents/scratch/`:
   - the domain
   - the `unique_id` format for the config entry and for each entity
   - the keys stored in `entry.data` and `entry.options`, and the config entry `VERSION` / `MINOR_VERSION`
   - the service action names and their field names
   - the `device_class`, `state_class`, unit and attribute names of every entity
   - any `Store` / `.storage` key the integration writes
3. **Note what the integration depends on**: `manifest.json` → `requirements`, the minimum Home Assistant version, and
   whether it uses discovery.

This file is the acceptance test for phases 4 to 6. Nothing in it may change without an explicit decision under
[`ha-breaking-changes`](../ha-breaking-changes/SKILL.md).

## Phase 1 — Repository, then `initialize.sh`

**Stay in the existing GitHub repository.** Issues, stars, releases and the catalog listing are tied to the repository
URL, not to the commit history inside it. Bring the blueprint into that repository rather than starting a new one
from the template. The recommended way overlays an initialised blueprint onto the existing `main` as one pull
request — history kept, no force push — with the alternatives and the repository settings to re-check in
[`references/git-strategy.md`](references/git-strategy.md).

Then run `initialize.sh` **with the identifiers the integration already has**. With the overlay,
`script/import-overlay` runs it for you: pass the options below after its `--`, except `--domain` and `--force`,
which it sets itself from the target.

- `--domain` **must** be the existing domain. It is the primary key of every config entry and the prefix of every
  entity ID. Changing it does not migrate anything — it orphans every installation. If the developer wants a
  different domain, stop and treat it as its own breaking change with its own decision.
- `--title` should match the name users already see, unless a rename is deliberate.
- `--namespace` sets the class prefix. Picking the prefix the code already uses means no rename happens at all, which
  is the safest option. If you do pick a new one, phase 2's verification exists precisely to catch what the rename
  swept up.

`initialize.sh` normally refuses to run outside a fresh single-commit template clone; `--force` is required here. Use
`--dry-run` first.

## Phase 2 — Drop the code in unchanged, and get it green

With the overlay, the integration folder never left — skip to making it green. With options B or C, copy
`custom_components/<domain>/` from the old repository over the blueprint's generated one — **replacing it, not
merging into it**. The blueprint's example platforms, API client and entities are demonstrations; keeping any of them
alongside real code ships broken entities.

Home Assistant does not care about the internal file layout, so a flat set of modules is perfectly valid at this
point. Do not restructure yet.

Then make it pass, changing as little as possible:

```bash
script/lint          # fixes formatting, reports the rest
script/type-check
script/hassfest
script/test
```

Reconcile `manifest.json` → `requirements` with the root `requirements.txt`, and restore any `hacs.json` fields the
old repository had that `initialize.sh` did not carry over ([`blueprint-tooling`](../blueprint-tooling/SKILL.md)).

**Verify against phase 0 and commit.** This checkpoint — old code, new tooling, everything green — is the fallback
every later phase can be reverted to. Reaching it is the milestone worth reporting.

## Phase 3 — Take stock, before deciding how much to fix

The phase 2 checkpoint is the only moment where the whole integration is in front of you, running, with nothing
changed yet. Audit it here and the result is an inventory of what you inherited; audit it at the end and it is a
verdict on your own work.

Run a full audit with [`ha-quality-review`](../ha-quality-review/SKILL.md) against the imported code. Then sort every
finding — the sorting, not the audit, is what makes the result usable:

| Bucket       | What lands in it                                                                                                   | What happens to it                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| **Free**     | Nothing a user can observe: layering, typing, file structure, deprecated APIs, missing tests, absent diagnostics   | Folded into phases 4 to 6 as you reach them             |
| **Costly**   | Anything on the phase 0 contract: entity names, `state_class`, units, unique ID format, renamed or removed options | Batched — one decision, one migration, one release      |
| **Deferred** | Needs a real device, a vendor answer, or a decision nobody can make today                                          | Written down with what it blocks, never quietly dropped |

**Costly findings are batched, not dripped.** Five releases that each rename a few entities cost users five
interruptions; one release that renames them all, with a migration and a changelog entry they can act on, costs one.
Collect them, present them together, and let the developer choose the release
([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)).

Turn the result into a phased plan in `.agents/scratch/` ([`ha-planning`](../ha-planning/SKILL.md)) — phases 4 to 7
then execute it. Weigh it against what the interview established: an integration with thousands of installations whose
maintainer does not want a major release has a Free-only backlog, and that is a legitimate outcome, not a failed
import.

**Take stock of the agent knowledge too.** Old `AGENTS.md`, `CLAUDE.md`, Copilot and Cursor instructions are sorted
rule by rule into what the blueprint already ships, what is stale, the project's own rules, and its decisions — never
merged as a file ([`references/agent-knowledge.md`](references/agent-knowledge.md)).

**This phase changes no code.** A finding you fixed while cataloguing is a finding nobody reviewed, and it spends the
phase 2 checkpoint you may still need to fall back to.

## Phase 4 — Modernise the APIs, and nothing else

Old integrations accumulate APIs that Home Assistant has since deprecated or removed. Fix those now, while the file
layout is still familiar and a diff is easy to read. [`ha-modern-apis`](../ha-modern-apis/SKILL.md) carries the full
table; the ones that show up in nearly every legacy integration, together with the upstream-template patterns worth
recognising, are in [`references/legacy-patterns.md`](references/legacy-patterns.md).

This phase is strictly behaviour-preserving. Resist every improvement that changes what a user observes — note it for
later instead. Commit separately from phase 5.

## Phase 5 — Restructure into the blueprint layout

Only now move code into `api/`, `coordinator/`, `entity/`, `config_flow_handler/`, `<platform>/`, `service_actions/`,
`utils/` as described in `docs/development/ARCHITECTURE.md` and the "Integration Structure" section of
[`AGENTS.md`](../../../AGENTS.md).

This is file movement and import rewriting, not redesign. Two things to be deliberate about:

- The blueprint keeps a thin `config_flow.py` shim at the top level and the real flow in `config_flow_handler/`.
  Home Assistant discovers the flow through the shim, so it must stay.
- One entity class per file. Splitting a large platform module is the main real work of this phase.

After moving, re-run the full validation and re-verify the phase 0 contract. Unique IDs and translation keys are the
things most easily lost in a bulk rename.

## Phase 6 — Apply this project's rules to the imported code

The linters are mandatory but they only cover mechanics. What makes the import worthwhile is the guidance the linters
cannot express — apply it as a review pass, file type by file type, using the matching instructions file and skill:

| Area                      | What typically needs fixing in imported code                                                             |
| ------------------------- | -------------------------------------------------------------------------------------------------------- |
| Entities                  | `name=` and `icon=` in code instead of `translation_key` and `icons.json`; missing `state_class`         |
| Entity/coordinator layers | entities calling the API client directly instead of reading `coordinator.data`                           |
| Service actions           | registered in `async_setup_entry()` instead of `async_setup()`; `services.yaml` fields without selectors |
| Config flow               | no `unique_id`, or one derived from a host or IP; credentials in `entry.options`                         |
| Errors                    | bare `HomeAssistantError` with an English message instead of a translated one                            |
| Diagnostics               | absent, or present without `async_redact_data()`                                                         |
| Device registry           | unscoped registry lookups, or several subentries sharing one device                                      |

**Each of these can be a breaking change.** Adding a `translation_key` to an entity that had `name=` changes its
name, and adding a missing `state_class` changes its statistics. Check every one against the phase 0 contract and
raise it with the developer before implementing — see [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md).

The phase 3 backlog says which of these this repository actually has, and which bucket each one fell into — work from
that. The table above is what to look for when no audit was run.

Work through this in small commits, not one sweep. If the developer wants only the mandatory parts, phases 0 to 5
already stand on their own.

## Phase 7 — Tests, review, release

- Add tests for whatever the old repository had none of, starting with the config flow and one platform
  ([`ha-testing`](../ha-testing/SKILL.md)).
- Re-run [`ha-quality-review`](../ha-quality-review/SKILL.md). It now measures what the import produced rather than
  what it inherited, so compare it against the phase 3 audit and say what moved.
- Start Home Assistant with the **existing** `config/.storage` and confirm the entry loads, the entity IDs are
  unchanged and history is intact. A mocked suite cannot prove this.
- Release under [`ha-release`](../ha-release/SKILL.md). If anything in the phase 0 contract did change, it needs a
  `BREAKING CHANGE:` footer and a migration note for users.

Report which verification actually happened and which did not ([`AI_POLICY.md`](../../../AI_POLICY.md)).

The first new feature after an import is the one most likely to be built on assumptions the old repository never
stated. Run [`ha-grill`](../ha-grill/SKILL.md) before it, not after.

## Retire this skill when the import is done

Importing happens once. Afterwards this skill is dead weight in every session:

1. Delete `.agents/skills/blueprint-import/`.
2. Remove its rows from the catalogues in `.agents/skills/README.md` and `AGENTS.md`.
3. Add `.agents/skills/blueprint-import/` to `.templatesyncignore`, or the next weekly template-sync pull request
   restores it.

## Do not

- Do not change the domain, and do not "tidy up" a unique ID format, entity ID, or action name in passing.
- Do not apply the phase 6 rules as routine cleanup: swapping `name=` for a `translation_key` renames the entity in
  every dashboard, and adding a missing `state_class` rewrites its long-term statistics. Both need approval.
- Do not run phases 2 to 6 as one commit — a failure then has no revertable checkpoint.
- Do not let the phase 3 audit turn into a rewrite. It produces a backlog the developer decides on; an import that
  quietly became a redesign has no checkpoint left and no reviewer who can still tell the two apart.
- Do not restructure before the imported code is green in its original layout.
- Do not merge the blueprint's example entities with the imported ones.
- Do not trust an automated class rename around `unique_id`, `translation_key`, storage keys, or anything else the
  user's installation persisted; diff them explicitly.
- Do not abandon the old repository for a fresh one created from the template.
