# Question bank

Working list for [`ha-grill`](../SKILL.md). Read the section that matches the change, plus "Never ask these".

Each entry is a **decision**, not a script — ask it one at a time, with your recommendation attached, and in the
developer's vocabulary rather than this table's ("Ask in the developer's language" in [`../SKILL.md`](../SKILL.md)).
The right-hand column is why it earns a turn: what breaks, or what you would otherwise guess.

## 0. Before the first question

Answer these from the repository, then confirm the result in one line instead of asking:

| Look at                                   | Tells you                                                  |
| ----------------------------------------- | ---------------------------------------------------------- |
| `manifest.json`                           | `integration_type`, `iot_class`, dependencies, discovery   |
| `custom_components/<domain>/coordinator/` | The current payload shape and update interval              |
| The platform directories and `PLATFORMS`  | Which surfaces already exist                               |
| `translations/en.json`, `icons.json`      | Naming conventions already in use                          |
| `docs/development/decisions/README.md`    | Choices already made, and what they oblige                 |
| `git log --oneline -20`                   | What the developer has been working on, and in which style |

If `initialize.sh` still exists, the repository has not been initialised — settle that before anything else
([`AGENTS.md`](../../../../AGENTS.md)).

## 1. A new integration on the fresh blueprint

Order matters here: each block constrains the next. **Settle the first two blocks before assuming any of the rest
applies** — an integration that derives its values from what Home Assistant already knows has no payload, no
credentials and no rate limit, and half of what follows would be a wasted turn.

**What kind of integration this is**

| Decision                                                                              | Why it earns a turn                                                |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| A device, a cloud service, a local service, or something produced rather than fetched | Decides which of the blocks below apply at all                     |
| `integration_type`: `device`, `service`, `hub`, or `helper`                           | Leaving it unset is not neutral — Home Assistant reads it as `hub` |
| For a device or plan-gated service: which model, firmware, or tier                    | Decides which endpoints and fields exist at all                    |
| Who else has integrated it — a Marketplace one, a Core integration, nobody            | An existing one may be the answer instead of this repository       |

**Where the values come from** — the branch everything else hangs off

| The source                                                                         | What it means for the rest                                                       |
| ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| A network or bus endpoint: HTTP, WebSocket, MQTT, Bluetooth, serial, a vendor SDK  | "Access" and "The payload" below apply in full                                   |
| Other entities, a local file or database, a computation, the calendar or the clock | No API client and no payload — use "Produced, not fetched" instead               |
| Nothing readable: the integration only sends commands                              | `iot_class: assumed_state`, and optimistic state becomes the central question    |
| IR or RF codes for a device, sent through a blaster another integration owns       | A consumer: no API client or coordinator; the user picks the emitter in the flow |

More than one source is normal — a cloud service whose values are then combined locally answers both. Ask which
blocks apply rather than forcing the integration into one of them.

**Access** — when there is an endpoint

| Decision                                                | Why it earns a turn                                              |
| ------------------------------------------------------- | ---------------------------------------------------------------- |
| Local network, cloud API, or both                       | `iot_class`, and whether the integration survives an outage      |
| Protocol: REST, WebSocket, MQTT, Bluetooth, proprietary | API client shape, and whether a library beats writing one        |
| Auth: none, API key, username/password, OAuth2, token   | Config flow fields, and whether reauth is needed                 |
| Do credentials expire, rotate, or get revoked           | Reauth is not optional if they do                                |
| Rate limits, or a documented minimum poll interval      | `UPDATE_INTERVAL`; a ban is a support ticket you cannot fix      |
| A maintained PyPI library that already wraps this       | The most expensive decision to revisit — record it as a decision |

**The payload** — when something is fetched, insist on a real one

| Decision                                                    | Why it earns a turn                                           |
| ----------------------------------------------------------- | ------------------------------------------------------------- |
| A captured response: curl output, a log line, vendor docs   | Nothing below can be answered without it                      |
| One call or several per refresh                             | Coordinator structure, and whether entities need partial data |
| Which fields are absent when a feature is off or unlicensed | The difference between `None` and "unavailable" per entity    |
| Units, and whether the device can be switched between them  | Wrong units are a breaking change once released               |
| Which values are enumerations, and their complete set       | `select`/`sensor` options and their translation keys          |

**Produced, not fetched** — when the values are computed, derived or accumulated

| Decision                                                                 | Why it earns a turn                                                             |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| Which entities, inputs or files it reads                                 | Whether it needs a state listener, a template, a file watcher, or a timer       |
| What happens when a source is missing, unavailable or the wrong type     | The largest source of bug reports in integrations of this kind                  |
| Derived fresh on every read, or accumulated over time                    | Accumulated state has to survive a restart — `RestoreEntity` or `Store`         |
| Does it hold state the user sets, and must that outlive a restart        | Decides between the config entry, `Store`, and restoring from the state machine |
| Is a coordinator right here at all, or does an event listener replace it | Polling something local on a timer is pure waste                                |
| Is the computation cheap enough to run in the event loop                 | Anything heavier belongs in an executor, and that decision is easier now        |

**Update model**

| Decision                                                   | Why it earns a turn                                                                            |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Push or poll, and if push, what happens when it drops out  | Coordinator versus listener; `iot_class`                                                       |
| How fast the data genuinely changes                        | An interval faster than the data is pure load                                                  |
| Does a command's effect show up in the next poll, or later | Whether writes update optimistically — fine for a slow cloud or a long poll, which corrects it |

**Starting without a connection** — Home Assistant is often up before the router after a power cut

| Decision                                                                         | Why it earns a turn                                                               |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Does one response stay true for a known period, or is it a point-in-time reading | Decides whether a cached payload may be restored at all, or would be a lie        |
| If it has a validity window, how long — a day, an hour, until a published time   | When to discard the cache and go `unknown` instead of serving it                  |
| Does the current value follow the clock within that payload                      | A scheduler recomputing locally, rather than polling often enough to catch a flip |
| Should the integration load at all when the first fetch fails                    | Restoring from `Store` versus `ConfigEntryNotReady` and no entities whatsoever    |

**Identity**

| Decision                                                              | Why it earns a turn                                                                                          |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| A stable per-install identifier — serial, MAC, account ID             | Config entry `unique_id`; never a host, IP, URL or chosen name                                               |
| Does that identifier survive a factory reset or an account migration  | If not, users lose their history                                                                             |
| If nothing external identifies it, is that genuinely the case         | Then the entry has no `unique_id` and `entry_id` carries identity — correct for a helper, a bug for a device |
| One config entry per device, or one entry covering many               | Device model, subentries                                                                                     |
| Are the other devices separate products behind a hub, or parts of one | A hub's products get `via_device_id`; an outlet of a power strip is a child device                           |
| Is there a device at all, or only entities                            | A computed integration may legitimately register none                                                        |
| Will the same account or source ever be added twice                   | Duplicate handling in the flow                                                                               |

**Surface and failure**

| Decision                                                                      | Why it earns a turn                                     |
| ----------------------------------------------------------------------------- | ------------------------------------------------------- |
| Which values are entities, which are attributes, which are nothing            | Attributes are not searchable, graphable or automatable |
| Which of the demo platforms map to something real — the rest get deleted      | A kept demo platform ships broken entities              |
| What the user should see when the source is unreachable, missing or invalid   | Unavailable versus stale versus a repair issue          |
| Anything worth a service action rather than an entity                         | One-shot commands and anything that returns data        |
| Is there a documented API or schema version, and what happens when it changes | Whether the client has to negotiate or fail loudly      |
| Does it surface anything that is not an entity — a panel, a webhook, an event | None of that comes from the example platforms           |

## 2. A new platform or entity in an existing integration

| Decision                                                             | Why it earns a turn                                                                                                                                  |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Which coordinator field backs it, exactly                            | If none does, this is a coordinator change first                                                                                                     |
| Entity, attribute of an existing entity, or diagnostic               | Decides `entity_category` and whether it belongs at all                                                                                              |
| Enabled by default, or `entity_registry_enabled_default=False`       | Ten noisy diagnostics per device is a complaint, not a feature                                                                                       |
| Device class, state class, unit                                      | Wrong ones break statistics and are breaking to correct                                                                                              |
| Which device does it belong to, in a multi-device setup              | Every device has exactly one owning config entry                                                                                                     |
| What its state is before the first successful refresh                | `unknown` versus `unavailable` is user-visible                                                                                                       |
| For a writable entity: what the API does with an invalid value       | Validation and the error the user gets                                                                                                               |
| Does the value exist on every model, firmware or plan tier           | Whether the entity is created conditionally                                                                                                          |
| Will people show it on a dashboard, use it in an automation, or both | State versus attribute, and what goes beside the state ([`ha-user-experience`](../../ha-user-experience/SKILL.md#reading-and-automating-pull-apart)) |
| Would anyone want an automation to start when this changes           | Then it is a state, not an attribute                                                                                                                 |
| For a fixed set of values: is there an order ("low" < "high")        | An ordinal beside the state lets automations compare                                                                                                 |

## 3. A new service action

| Decision                                                        | Why it earns a turn                                           |
| --------------------------------------------------------------- | ------------------------------------------------------------- |
| Could this be an entity instead                                 | An entity is automatable and visible; an action is neither    |
| Targets entities, devices, or nothing                           | `target:` versus fields                                       |
| Every field: type, range, required, and its selector            | A field without a selector is a free-text trap in the UI      |
| Does it return data                                             | `SupportsResponse`, and the shape callers will depend on      |
| Is it idempotent, and what happens when it is called twice fast | Whether it needs a lock or a debounce                         |
| What the user should see when the device rejects it             | A translated `HomeAssistantError`, never a swallowed log line |

## 4. Setup, options, reauth, discovery

| Decision                                                                          | Why it earns a turn                                     |
| --------------------------------------------------------------------------------- | ------------------------------------------------------- |
| The minimum needed to connect — everything else is options                        | Every extra setup field is a user who gives up          |
| Which settings must be changeable afterwards without re-adding                    | Options flow scope                                      |
| How many settings will there be in a year, not today                              | One form, sections, or a menu                           |
| Should an automation be able to change any of them                                | A config entity beside the option, and its cost         |
| Is the device discoverable — mDNS, DHCP, SSDP, Bluetooth, USB                     | A manifest matcher without a flow step fails `hassfest` |
| What the flow does when the credentials are right but the device is not reachable | Abort reason versus a form error                        |
| Does this change the shape of `entry.data`                                        | `VERSION`/`MINOR_VERSION` and `async_migrate_entry()`   |

## 5. Anything that reaches installs which already exist

Ask before implementing, not in the pull request ([`ha-breaking-changes`](../../ha-breaking-changes/SKILL.md)):

| Decision                                                    | Why it earns a turn                                      |
| ----------------------------------------------------------- | -------------------------------------------------------- |
| Do any entity IDs or unique IDs change                      | Automations and dashboards break silently                |
| Do state values, units, device classes or attributes change | Long-term statistics and history break                   |
| Is a config option, action or field removed or renamed      | Even an option that looks unused is in someone's YAML    |
| Is a migration possible, and is it worth the code           | The developer chooses; the default is migrate, not break |
| Does the minimum Home Assistant version rise                | Users on the old version stop receiving updates          |

## 6. Importing an existing integration

Run this before phase 0 of `blueprint-import` (retired). That phase records what the code
_does_ — the measured contract. This section records what the maintainer _wants_, and the two answer different
questions. Almost everything here decides how much of the import is affordable at all.

**Who is running this code**

| Decision                                                                 | Why it earns a turn                                               |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Roughly how many installations — download counts, issue traffic, or none | The single number that decides how expensive a breaking change is |
| Listed in the Marketplace catalog, or added as a custom repository       | The repository URL and its releases are load-bearing              |
| Is there a live installation to export the entity registry from          | Whether the phase 0 baseline is measured or merely derived        |
| Can the developer test against the real device after each phase          | What "verified" is allowed to mean in your reports                |

**What the maintainer actually wants**

| Decision                                                             | Why it earns a turn                                              |
| -------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Only the tooling and structure, or the quality standard as well      | Whether the later phases happen at all                           |
| Is a breaking release acceptable, and is one already planned         | Whether costly findings can be batched into it or must wait      |
| What they already know is wrong in there                             | The maintainer's list is better than any audit's, and it is free |
| What is deliberately unusual and must survive the audit              | Stops you "fixing" a workaround whose reason is undocumented     |
| Is part of it already slated for a rewrite                           | Do not modernise code that is about to be deleted                |
| Which features they have been unable to add in the current structure | Names the payoff the import is supposed to deliver               |

**Where the code came from**

| Decision                                                                | Why it earns a turn                                           |
| ----------------------------------------------------------------------- | ------------------------------------------------------------- |
| Which template, if any — the upstream one, a cookiecutter, hand-written | Predicts the patterns you will meet in `legacy-patterns.md`   |
| Open pull requests, or long-lived branches                              | The restructure phase invalidates every one of them           |
| Is anyone else committing to it right now                               | File moves turn their next merge into a manual reconstruction |
| The oldest Home Assistant version that must keep working                | Bounds which modern APIs are even available to you            |
| Is there a test suite, and has anyone trusted it recently               | Whether green means anything at the phase 2 checkpoint        |

## Never ask these

The answer is already fixed. Asking invites a reply you would have to overrule, and spends a turn doing it. State the
rule instead if it comes up.

- Whether to use `translation_key` or a hardcoded `name=`/`icon=` — see `blueprint.entities`.
- Whether entities may call the API client directly — they may not, ever.
- Whether to register a service action in `async_setup_entry()` — `async_setup()`, per the quality scale.
- Whether YAML configuration should be supported — no, config flow only.
- Whether diagnostics get redacted — always.
- Whether an IP, hostname or user-chosen name can serve as a unique ID — no.
- Which language files to translate — `en.json` only, unless the developer asks.
- Whether to write tests for a behavioural change — yes, proportionate ones.

## Three answers you must not take at face value

- **"Just like the example."** The blueprint's demo platforms demonstrate the file layout, not anyone's device. Ask
  what the real device exposes.
- **"Whatever you think is best."** Fine for a genuinely reversible choice; not for unique IDs, entity IDs, entry
  data, units or the coordinator's data shape. For those, make a recommendation and get an explicit yes.
- **"It should return something like…"** An imagined payload. It goes under **Open** in the brief until someone has
  seen a real response.
