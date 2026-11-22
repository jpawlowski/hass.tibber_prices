---
name: blueprint-scaffold
description: >-
  Turn this freshly initialised blueprint into a working integration for one concrete device, service or computed
  source — decide the manifest classification, write the API client if there is one, shape the coordinator
  payload, keep or delete each example entity platform, and get the first end-to-end run green. Use when asked to
  "transform the blueprint", "make this an integration for <device>", "implement the API client", "remove the
  example entities", "adapt the template to my service", or when the repository still ships the demo platforms
  and nobody has written real code yet. Covers the facts to gather first, the order the layers must be built in,
  and how to retire this skill. SYMPTOMS — load this if you are about to: invent a payload instead of asking for
  a real one; keep an example platform "for later"; write entities before the coordinator exists; build an API
  client for something that fetches nothing; leave `integration_type` unset and inherit `hub`; or scaffold a
  repository that already has real code.
---

# Scaffold the blueprint into a real integration

**This is a one-time task.** It runs once, in a repository that has been initialised with `initialize.sh` but still
contains the blueprint's example platforms. Everything it produces is ordinary integration code afterwards, maintained
with the `ha-*` skills.

**Stop if the repository already has real code.** Placeholder identifiers gone _and_ platforms that match a real
device mean scaffolding already happened. Adding an entity to an existing integration is
[`ha-entity-platform`](../ha-entity-platform/SKILL.md), not this. Migrating a pre-existing integration in is
[`blueprint-import`](../blueprint-import/SKILL.md).

## 1. Gather the facts — do not start without them

| Fact                                           | Why it decides something                                            |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| What the integration exposes, and to whom      | Which platforms survive step 4                                      |
| **Where its values come from**                 | Everything below; see the branch under it                           |
| **A real payload, or the real source**         | The coordinator's data shape, and every entity's value accessor     |
| What drives an update, and how often           | `iot_class`, `UPDATE_INTERVAL`, whether a listener replaces polling |
| **How long one response stays true**           | Whether the integration can start from cache with no network        |
| A stable per-install identifier, if one exists | The config entry `unique_id`                                        |

**Where the values come from is the branch, and it decides which further facts you need.**

- **A device or an endpoint** — HTTP, WebSocket, MQTT, Bluetooth, serial, a vendor SDK. Then you also need the
  protocol and base URL, the authentication, and whether credentials expire.
- **Produced rather than fetched** — computed from other entities, a local file or database, a calculation, the
  clock. There is no API client and no credentials; what you need instead is which sources it reads, what it does
  when one is missing or the wrong type, and whether the result has to survive a restart.
- **Write-only** — the integration sends commands and cannot read back. Then the question is what the entity shows
  in between, which is `assumed_state` and optimistic state.

An integration may sit in more than one of these. Establish which apply rather than forcing it into one.

Where something _is_ fetched, the payload is the fact that cannot be guessed. Ask for an actual captured response —
a curl dump, a log line, a screenshot of the vendor docs. Entities built against an invented shape look finished and
fail on first contact.

This table is the minimum, not the whole interview. [`ha-grill`](../ha-grill/SKILL.md) is how to get it out of the
developer — one question at a time, in dependency order — and it ends with a brief that steps 2 to 6 then execute.

If a maintained PyPI library already wraps this API, weigh it against a small `aiohttp` client using the criteria in
[`AGENTS.md`](../../../AGENTS.md) ("Custom Integration Flexibility"), and record the outcome in
a decision record in `docs/development/decisions/` ([`ha-planning`](../ha-planning/SKILL.md)). This is the decision that is most
expensive to revisit later.

## 2. Classify it in the manifest

`integration_type` drives how Home Assistant presents the integration and how you model devices:

- `device` — one physical thing per config entry. The common case.
- `service` — one account, cloud service or local daemon per config entry.
- `hub` — a gateway that fans out to several devices. Only if a single entry really yields many devices.
- `helper` — the integration produces its values from what Home Assistant already has, rather than fetching them.
  It appears under Helpers in the UI instead of under Devices & services, which is where its users will look for it.

`entity`, `system`, `hardware` and `virtual` also exist, but they describe Home Assistant's own building blocks and
are not for a custom integration. **Omitting the key is not neutral** — Home Assistant reads a missing
`integration_type` as `hub`.

Set `iot_class` to match reality. Beyond `local_polling`, `cloud_polling`, `local_push` and `cloud_push` there is
`calculated`, for an integration that derives its values instead of fetching them, and `assumed_state`, for one that
sends commands it cannot read back.

Pick one to three `categories` with the developer — "what is this, and where would someone look for it?" — from the
list in `schemas/json/manifest_schema.json`, primary first, unless `initialize.sh` already wrote them. The
Marketplace catalog publishes them; when to add the key is in `blueprint.manifest`.

Add discovery matchers only when you will also implement the matching flow step
([`ha-config-flow`](../ha-config-flow/SKILL.md)); a matcher without a handler fails `script/hassfest`.

Declare runtime dependencies in **both** `manifest.json` → `requirements` and the root `requirements.txt`
([`blueprint-tooling`](../blueprint-tooling/SKILL.md)).

## 3. Build the layers bottom-up

Entities → coordinator → source. Build in the reverse of that order, because each layer is testable before the one
above it exists.

1. **`api/`** — the client and its exception types. Nothing Home Assistant-specific in here: no `hass`, no entity
   imports. Raise your own auth/connection/unknown exceptions and let the coordinator translate them. **When nothing
   is fetched, this package has nothing to hold — delete it** rather than leaving a client that wraps a calculation.
2. **`coordinator/`** — replace `_async_update_data` with the real call and return the shape the entities will read.
   Translate API exceptions into `ConfigEntryAuthFailed`, `UpdateFailed` or — when the failure will never resolve by
   itself, such as a closed account — `ConfigEntryError`, there and only there
   ([`ha-coordinator-debug`](../ha-coordinator-debug/SKILL.md)). If the values are produced rather than fetched, this
   is where the computation lives, driven by a state listener or a timer instead of a poll — and a coordinator that
   would only re-run a local calculation on a timer should be replaced by the listener outright. The polling interval
   is a constant, never a config field ([`blueprint.config_flow`](../../instructions/blueprint.config_flow.instructions.md)).
3. **`data.py` / `const.py`** — the runtime data container and the constants the platforms share.

If one response stays true for a defined period — a day's prices, a published forecast — decide **now** whether the
integration persists it and starts from that without a network. It changes the coordinator's shape (a `Store`, a
validity window, a scheduler instead of a short interval) and is awkward to retrofit; the rules are in
[`blueprint.coordinator`](../../instructions/blueprint.coordinator.instructions.md).

Decide the coordinator's data shape deliberately: a parsed model or `TypedDict` beats passing raw JSON around,
because every entity would otherwise repeat the same defensive key lookups.

### Bluetooth is a different coordinator

`DataUpdateCoordinator` polls, and a BLE device that broadcasts advertisements has nothing to poll. Pick by how the
data actually arrives:

| The device…                                                | Coordinator                                                                      |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Broadcasts, and feeds `sensor` / `binary_sensor` / `event` | `PassiveBluetoothProcessorCoordinator`                                           |
| Broadcasts, but some values need a connection              | `ActiveBluetoothProcessorCoordinator`                                            |
| Broadcasts, and feeds other platforms                      | `PassiveBluetoothDataUpdateCoordinator` / `ActiveBluetoothDataUpdateCoordinator` |
| Only answers when connected to                             | plain `DataUpdateCoordinator`                                                    |

- `bluetooth_adapters` goes in `dependencies` — it guarantees remote adapters are connected before you use them.
- Get the scanner from `bluetooth.async_get_scanner(hass)` and hand it to the library; never construct your own.
- Do not reuse a `BleakClient` across connections, use a connection timeout of at least 10 seconds, and go through
  `bleak-retry-connector`.
- Start the coordinator **after** `async_forward_entry_setups`, so every platform has had a chance to subscribe:
  `entry.async_on_unload(coordinator.async_start())`.
- An advertisement-only device needs `connectable: false` in the manifest matcher
  ([`ha-config-flow`](../ha-config-flow/references/discovery-matchers.md)).

### Infrared and radio remotes have no source of their own

An integration that knows a device's IR or RF codes — a TV, a fan, a wireless socket — but not the hardware that
sends them is a _consumer_: no `api/`, no coordinator, `integration_type: device` and `iot_class: assumed_state` —
the pattern is in [`other-platforms.md`](../ha-entity-platform/references/other-platforms.md#infrared-and-radio-frequency-devices).

## 4. Keep, adapt, delete each platform

The blueprint ships `binary_sensor`, `button`, `fan`, `number`, `select`, `sensor`, `switch` as worked examples. For
each one: does this integration have a real equivalent — a value it reads, computes, or a command it can send?

- **Yes** → adapt it. Reuse the file layout and the `EntityDescription` pattern
  ([`ha-entity-platform`](../ha-entity-platform/SKILL.md)).
- **No** → delete the whole directory. Not a stub, not a commented-out class.

Then update `PLATFORMS` in `custom_components/<domain>/__init__.py` to exactly the surviving list, and delete the
matching `entity.<platform>.*` blocks from `translations/en.json` and `icons.json`. A platform left in `PLATFORMS`
without a directory fails at setup; an orphaned translation key fails `script/hassfest`. The example tests under
`tests/` go in the same step as the code they cover: CI runs `script/test` on every pull request, so a test left
behind for a deleted platform turns it red.

Same treatment for `service_actions/` and `services.yaml` — the example actions go unless the device has a real
equivalent ([`ha-service-action`](../ha-service-action/SKILL.md)).

## 5. Config flow and identity

Ask for the minimum needed to connect, validate it by actually connecting, and set a `unique_id` from a serial
number, MAC, or account ID — never a host, IP, URL, or user-chosen name. Add reauth if credentials can expire.
Details and the reserved step names: [`ha-config-flow`](../ha-config-flow/SKILL.md).

The unique ID choice is effectively permanent — changing it later is a breaking change
([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)).

## 6. Strings, then validation, then a real run

1. `translations/en.json` and `icons.json` for every surviving entity, flow step, action and exception —
   English only, `en.json` only ([`ha-translations`](../ha-translations/SKILL.md)).
2. `script/lint` and `script/type-check` until both are clean, then `script/hassfest`.
3. Tests for the config flow and at least one platform ([`ha-testing`](../ha-testing/SKILL.md)), then `script/test`.
4. `script/develop`, add the integration through the UI, and confirm the entities carry real values. Scaffolding is
   not done until this has happened — a green suite proves the mocks agree with each other, not that the device
   answers.

Report honestly which of these you ran and which you could not ([`AI_POLICY.md`](../../../AI_POLICY.md)). Real-device
verification is the developer's to do, not yours to claim.

## 7. Finish the paperwork, then retire this skill

- Update `README.md` and `docs/user/` to describe the real integration.
- Replace the placeholder images in `custom_components/<domain>/brand/` — the rules are in
  [`ha-marketplace`](../ha-marketplace/SKILL.md#3-brand-images). Ask the developer for the files; do not invent
  artwork.
- Record the library-versus-own-client decision in `docs/development/decisions/` if you have not already.
- Commit in reviewable pieces, following [`ha-release`](../ha-release/SKILL.md). Never commit unasked.

Scaffolding happens once. Once the integration is real, this skill is dead weight in every future session, so remove
it as the last step:

1. Delete `.agents/skills/blueprint-scaffold/`.
2. Remove its rows from the catalogues in `.agents/skills/README.md` and `AGENTS.md`.
3. Add `.agents/skills/blueprint-scaffold/` to `.templatesyncignore` — without it, the next weekly template-sync
   pull request puts the skill straight back.

## Do not

- Do not write entities against a payload nobody has seen.
- Do not keep an example platform because it "might be useful later" — it ships broken entities to users.
- Do not hardcode `name=` or `icon=` while scaffolding with the intention of fixing it afterwards; the fix never
  comes and the entity IDs are already public by then.
- Do not skip `script/hassfest` because `script/check` passed — they check different things.
- Do not describe the result as tested when only the mocked suite ran.
