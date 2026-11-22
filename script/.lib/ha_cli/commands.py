"""The debugging commands of `script/ha`.

Everything here answers a question an agent would otherwise have to ask a human
to click through the UI for: what state is this entity in, did the config entry
load, what did the integration log, what does its diagnostics dump say.

Listings default to the entities, devices, and config entries of *this*
integration. `--all` widens them to the whole instance.
"""

import json
from typing import TYPE_CHECKING, Any

from .client import EXIT_UNREACHABLE, TOKEN_FILE, HaError
from .instance import CONFIG_DIR, develop_run, run_state
from .output import emit_json, emit_pairs, emit_table

if TYPE_CHECKING:
    import argparse

    from .client import HaClient

META_FILE = CONFIG_DIR / ".storage" / "dev_access_token.json"

LOG_LEVELS = ("debug", "info", "warning", "error", "critical")


async def our_entries(client: HaClient, domain: str) -> list[dict[str, Any]]:
    """Return the config entries belonging to this integration."""
    return await client.rest("GET", "/api/config/config_entries/entry", params={"domain": domain})


async def resolve_entry(client: HaClient, domain: str, entry_id: str | None) -> dict[str, Any]:
    """Return one config entry, defaulting to this integration's only one."""
    if entry_id:
        entries = await client.rest("GET", "/api/config/config_entries/entry")
        for entry in entries:
            if entry["entry_id"] == entry_id:
                return entry
        raise HaError(f"no config entry with id {entry_id}")

    entries = await our_entries(client, domain)
    if not entries:
        raise HaError(f"{domain} has no config entry — add the integration in the UI first")
    if len(entries) > 1:
        listed = ", ".join(f"{entry['title']} ({entry['entry_id']})" for entry in entries)
        raise HaError(f"{domain} has several config entries, pass one explicitly: {listed}")
    return entries[0]


async def our_entity_ids(client: HaClient, domain: str) -> set[str]:
    """Return the entity ids this integration owns, from the entity registry."""
    entries = await client.ws("config/entity_registry/list")
    return {entry["entity_id"] for entry in entries if entry.get("platform") == domain}


async def cmd_status(client: HaClient, args: argparse.Namespace) -> int:
    """Show whether Home Assistant is up, since when, and what it is running.

    Reports the local run lock alongside the API answer, because the developer
    and the agent both start and stop this instance. `started`/`uptime` are what
    tell you that the instance answering now is not the one you left behind.
    """
    local = run_state()
    try:
        config = await client.rest("GET", "/api/config")
        core = await client.rest("GET", "/api/core/state")
    except HaError as err:
        if err.code != EXIT_UNREACHABLE:
            raise
        verdict = (
            "a local Home Assistant holds config/.ha_run.lock but is not answering yet — it may still be starting"
            if local.running
            else "no local Home Assistant is running — start it with ./script/develop"
        )
        if args.json:
            emit_json({"reachable": False, "local_lock_held": local.running, "detail": str(err)})
        else:
            print(f"not reachable at {client.url}")
            print(verdict)
        return EXIT_UNREACHABLE

    run = develop_run() if local.running else {}
    if args.json:
        emit_json(
            {"config": config, "core": core, "local_lock_held": local.running, "uptime": local.uptime, "run": run}
        )
        return 0
    emit_pairs(
        {
            "url": client.url,
            "state": core.get("state"),
            "version": config.get("version"),
            "environment": run.get("slot") or "-",
            "started_by": run.get("started_by") or "-",
            "location": config.get("location_name"),
            "config_dir": config.get("config_dir"),
            "started": local.started.isoformat(timespec="seconds") if local.started else "-",
            "uptime": local.uptime if local.running else "-",
            "pid": local.pid or "-",
        }
    )
    return 0


async def cmd_states(client: HaClient, args: argparse.Namespace) -> int:
    """Show entity states, scoped to this integration by default."""
    if args.entity_id:
        state = await client.rest("GET", f"/api/states/{args.entity_id}")
        if args.json:
            emit_json(state)
        else:
            emit_pairs({**{k: v for k, v in state.items() if k != "attributes"}, **state["attributes"]})
        return 0

    states = await client.rest("GET", "/api/states")
    if not args.all:
        owned = await our_entity_ids(client, args.domain)
        states = [state for state in states if state["entity_id"] in owned]
    if args.json:
        emit_json(states)
        return 0

    columns = ["entity_id", "state", "last_updated"]
    if args.attributes:
        columns.append("attributes")
    emit_table(states, columns, empty=f"no entities for {args.domain} — is the config entry loaded?")
    return 0


async def cmd_entity(client: HaClient, args: argparse.Namespace) -> int:
    """Show one entity's state next to its registry entry and its source."""
    state = await client.rest("GET", f"/api/states/{args.entity_id}")
    try:
        registry = await client.ws("config/entity_registry/get", entity_id=args.entity_id)
    except HaError:
        registry = {}
    sources = await client.ws("entity/source")

    if args.json:
        emit_json({"state": state, "registry": registry, "source": sources.get(args.entity_id)})
        return 0

    emit_pairs(
        {
            "entity_id": state["entity_id"],
            "state": state["state"],
            "last_changed": state.get("last_changed"),
            "unique_id": registry.get("unique_id"),
            "platform": registry.get("platform"),
            "device_id": registry.get("device_id"),
            "entity_category": registry.get("entity_category"),
            "disabled_by": registry.get("disabled_by"),
            "hidden_by": registry.get("hidden_by"),
            "config_entry_id": registry.get("config_entry_id"),
        }
    )
    print()
    emit_pairs(state["attributes"], empty="no attributes")
    return 0


async def cmd_entities(client: HaClient, args: argparse.Namespace) -> int:
    """List registry entries, so unique ids and disabled state are visible."""
    entries = await client.ws("config/entity_registry/list")
    if not args.all:
        entries = [entry for entry in entries if entry.get("platform") == args.domain]
    if args.json:
        emit_json(entries)
        return 0
    emit_table(
        entries,
        ["entity_id", "unique_id", "entity_category", "disabled_by", "hidden_by", "device_id"],
        empty=f"no registry entries for {args.domain}",
    )
    return 0


async def cmd_devices(client: HaClient, args: argparse.Namespace) -> int:
    """List devices, scoped to this integration's config entries by default."""
    devices = await client.ws("config/device_registry/list")
    if not args.all:
        entry_ids = {entry["entry_id"] for entry in await our_entries(client, args.domain)}
        devices = [device for device in devices if device.get("config_entry_id") in entry_ids]
    if args.json:
        emit_json(devices)
        return 0
    emit_table(
        devices,
        ["id", "name", "manufacturer", "model", "sw_version", "via_device_id", "parent_device_id", "disabled_by"],
        empty=f"no devices for {args.domain}",
    )
    return 0


async def cmd_entries(client: HaClient, args: argparse.Namespace) -> int:
    """Show config entry state — the first thing to check on a setup failure."""
    entries = (
        await client.rest("GET", "/api/config/config_entries/entry")
        if args.all
        else await our_entries(client, args.domain)
    )
    if args.json:
        emit_json(entries)
        return 0
    emit_table(
        entries,
        ["entry_id", "title", "domain", "state", "reason", "source", "disabled_by"],
        empty=f"{args.domain} has no config entry — add the integration in the UI first",
    )
    return 0


async def cmd_reload(client: HaClient, args: argparse.Namespace) -> int:
    """Reload a config entry — cheaper than restarting the whole instance."""
    entry = await resolve_entry(client, args.domain, args.entry_id)
    result = await client.rest("POST", f"/api/config/config_entries/entry/{entry['entry_id']}/reload")
    if args.json:
        emit_json(result)
        return 0
    if result.get("require_restart"):
        print(f"reloaded {entry['title']}, but Home Assistant needs a restart to finish")
    else:
        print(f"reloaded {entry['title']}")
    return 0


async def cmd_diagnostics(client: HaClient, args: argparse.Namespace) -> int:
    """Download config entry (or device) diagnostics without the UI."""
    entry = await resolve_entry(client, args.domain, args.entry_id)
    path = f"/api/diagnostics/config_entry/{entry['entry_id']}"
    if args.device:
        path = f"{path}/device/{args.device}"
    try:
        emit_json(await client.rest("GET", path))
    except HaError as err:
        if err.status == 404:
            raise HaError(
                f"{entry['domain']} does not implement diagnostics — "
                "add async_get_config_entry_diagnostics to diagnostics.py"
            ) from err
        raise
    return 0


def response_label(response: dict[str, Any] | None) -> str:
    """Describe whether an action returns response data, and whether `--response` is optional."""
    if not response:
        return "-"
    return "optional" if response.get("optional") else "required"


async def cmd_services(client: HaClient, args: argparse.Namespace) -> int:
    """List service actions, scoped to this integration by default."""
    domains = await client.rest("GET", "/api/services")
    wanted = args.service_domain or (None if args.all else args.domain)
    if wanted:
        domains = [item for item in domains if item["domain"] == wanted]
    if args.json:
        emit_json(domains)
        return 0
    rows = [
        {
            "action": f"{item['domain']}.{name}",
            "name": service.get("name", ""),
            "fields": ", ".join(service.get("fields", {})) or "-",
            "response": response_label(service.get("response")),
        }
        for item in domains
        for name, service in sorted(item["services"].items())
    ]
    emit_table(rows, ["action", "name", "fields", "response"], empty=f"no service actions for {wanted}")
    return 0


def parse_data(pairs: list[str], blob: str | None) -> dict[str, Any]:
    """Turn `key=value` arguments and an optional JSON blob into service data.

    Values are parsed as JSON when possible, so `brightness=255` is a number and
    `name=Kitchen` stays a string.
    """
    data: dict[str, Any] = json.loads(blob) if blob else {}
    for pair in pairs:
        if "=" not in pair:
            raise HaError(f"expected key=value, got {pair!r}")
        key, _, raw = pair.partition("=")
        try:
            data[key] = json.loads(raw)
        except ValueError:
            data[key] = raw
    return data


async def cmd_call(client: HaClient, args: argparse.Namespace) -> int:
    """Call a service action and show what it changed or returned."""
    if "." not in args.action:
        raise HaError(f"expected <domain>.<action>, got {args.action!r}")
    domain, _, service = args.action.partition(".")
    data = parse_data(args.data, args.json_data)
    params = {"return_response": ""} if args.response else None
    result = await client.rest("POST", f"/api/services/{domain}/{service}", payload=data, params=params)
    emit_json(result)
    return 0


async def cmd_template(client: HaClient, args: argparse.Namespace) -> int:
    """Render a Jinja template against live state."""
    rendered = await client.rest("POST", "/api/template", payload={"template": args.template}, as_text=True)
    print(rendered)
    return 0


async def cmd_logs(client: HaClient, args: argparse.Namespace) -> int:
    """Show the structured error log, newest last.

    Reads `system_log/list` rather than the log file: it is deduplicated, keeps
    the exception text with the record, and counts repeats.
    """
    records = await client.ws("system_log/list")
    threshold = LOG_LEVELS.index(args.level)

    def loud_enough(record: dict[str, Any]) -> bool:
        level = str(record.get("level", "error")).lower()
        # An unrecognised level is never filtered out — better a stray record
        # than a hidden one.
        return level not in LOG_LEVELS or LOG_LEVELS.index(level) >= threshold

    records = [
        record
        for record in records
        if loud_enough(record) and (not args.grep or args.grep.lower() in json.dumps(record, default=str).lower())
    ]
    records = records[-args.number :]
    if args.json:
        emit_json(records)
        return 0
    if not records:
        print(f"no log records at {args.level} or above")
        return 0
    for record in records:
        message = record.get("message")
        text = message[-1] if isinstance(message, list) and message else message
        source = record.get("source") or ["?", 0]
        print(f"[{record.get('level')}] {record.get('name')} ({source[0]}:{source[1]}) x{record.get('count', 1)}")
        print(f"  {text}")
        if record.get("exception"):
            for line in str(record["exception"]).strip().splitlines():
                print(f"  {line}")
    return 0


async def cmd_loglevel(client: HaClient, args: argparse.Namespace) -> int:
    """Raise or lower log levels at runtime, without editing YAML or restarting."""
    data = {}
    for pair in args.assignments:
        if "=" not in pair:
            raise HaError(f"expected <logger>=<level>, got {pair!r}")
        logger, _, level = pair.partition("=")
        if level not in LOG_LEVELS:
            raise HaError(f"unknown level {level!r}, expected one of {', '.join(LOG_LEVELS)}")
        data[logger] = level
    await client.rest("POST", "/api/services/logger/set_level", payload=data)
    for logger, level in data.items():
        print(f"{logger} -> {level}")
    return 0


async def cmd_watch(client: HaClient, args: argparse.Namespace) -> int:
    """Stream events for a while — the way to prove an entity actually updates."""
    wanted = set(args.entity)
    if not wanted and not args.all and args.event == "state_changed":
        wanted = await our_entity_ids(client, args.domain)

    seen = 0
    async for event in client.ws_events("subscribe_events", args.seconds, event_type=args.event):
        data = event.get("data", {})
        if wanted and data.get("entity_id") not in wanted:
            continue
        seen += 1
        if args.json:
            emit_json(event)
            continue
        if args.event == "state_changed":
            old = (data.get("old_state") or {}).get("state")
            new = (data.get("new_state") or {}).get("state")
            print(f"{event.get('time_fired')}  {data.get('entity_id')}  {old} -> {new}")
        else:
            print(f"{event.get('time_fired')}  {event.get('event_type')}  {json.dumps(data, default=str)}")
    if not seen and not args.json:
        print(f"no matching {args.event} events in {args.seconds:g}s")
    return 0


async def cmd_setup_info(client: HaClient, args: argparse.Namespace) -> int:
    """Show how long integrations took to set up, and this one's manifest."""
    timings = await client.ws("integration/setup_info")
    if not args.all:
        timings = [item for item in timings if item["domain"] == args.domain]
    try:
        manifest = await client.ws("manifest/get", integration=args.domain)
    except HaError:
        manifest = {}

    if args.json:
        emit_json({"setup": timings, "manifest": manifest})
        return 0
    emit_table(
        sorted(timings, key=lambda item: item["seconds"], reverse=True),
        ["domain", "seconds"],
        empty=f"{args.domain} did not set up — check `script/ha logs` and the manifest",
    )
    if manifest:
        print()
        emit_pairs(
            {
                key: manifest.get(key)
                for key in ("domain", "name", "version", "iot_class", "config_flow", "requirements", "dependencies")
            }
        )
    return 0


async def cmd_token(client: HaClient, args: argparse.Namespace) -> int:
    """Show the development token's metadata — never the token itself."""
    del client, args
    if not META_FILE.is_file():
        raise HaError("no development token — run ./script/develop")
    emit_pairs(json.loads(META_FILE.read_text(encoding="utf-8")) | {"token_file": str(TOKEN_FILE)})
    return 0
