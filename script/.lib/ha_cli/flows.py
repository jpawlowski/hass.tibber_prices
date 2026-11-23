"""Driving config, options, and reconfigure flows from the terminal.

A config flow is otherwise only reachable through the browser, which makes it
the least testable part of an integration during development. These commands
walk the same HTTP endpoints the frontend uses, printing each step's schema so
the next `ha flow step` can be filled in without guessing.

Flow ids are printed on every step; a flow lives until it is finished or
aborted, so a session survives across several CLI invocations.
"""

from typing import TYPE_CHECKING, Any

from .client import HaError
from .commands import parse_data, resolve_entry
from .output import emit_json, emit_pairs, emit_table

if TYPE_CHECKING:
    import argparse

    from .client import HaClient

CONFIG_FLOW = "/api/config/config_entries/flow"
OPTIONS_FLOW = "/api/config/config_entries/options/flow"


async def resolve_flow(client: HaClient, flow_id: str) -> tuple[str, dict[str, Any]]:
    """Return the endpoint family of a running flow, and its current step.

    Config flows and options flows live under different URLs but their ids look
    identical, so the family is discovered rather than demanded from the caller.
    """
    for base in (CONFIG_FLOW, OPTIONS_FLOW):
        try:
            current = await client.rest("GET", f"{base}/{flow_id}")
        except HaError as err:
            if err.status != 404:
                raise
        else:
            return base, current
    raise HaError(f"no running flow with id {flow_id} — it may have finished or been aborted")


def step_defaults(schema: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Return the values the frontend would pre-fill this step's form with.

    Home Assistant validates a step against its whole schema, so submitting only
    the fields you want to change fails on every other one. The frontend avoids
    that by posting the full form; this reproduces it, and anything passed on the
    command line is layered on top.
    """
    defaults = {}
    for field in schema or []:
        name = field.get("name")
        if name is None:
            continue
        # A null default means "empty", and the frontend omits such fields rather
        # than posting null — which most schemas reject, since the selector's type
        # does not include None.
        if field.get("default") is not None:
            defaults[name] = field["default"]
        elif (suggested := (field.get("description") or {}).get("suggested_value")) is not None:
            defaults[name] = suggested
    return defaults


def describe_schema(schema: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Flatten a serialised voluptuous schema into printable field rows."""
    rows = []
    for field in schema or []:
        selector = field.get("selector") or {}
        rows.append(
            {
                "field": field.get("name"),
                "required": field.get("required", False),
                "type": field.get("type") or (next(iter(selector), "") if selector else ""),
                "default": field.get("default", field.get("description", {}).get("suggested_value")),
                "options": ", ".join(str(option) for option in field.get("options", [])) or "-",
            }
        )
    return rows


def render_step(result: dict[str, Any], args: argparse.Namespace) -> int:
    """Print a flow result, and return the process exit code it implies."""
    if args.json:
        emit_json(result)
        return 0

    flow_type = result.get("type")
    if flow_type == "form":
        emit_pairs(
            {
                "flow_id": result.get("flow_id"),
                "step_id": result.get("step_id"),
                "handler": result.get("handler"),
                "errors": result.get("errors") or "-",
                "placeholders": result.get("description_placeholders") or "-",
            }
        )
        print()
        emit_table(describe_schema(result.get("data_schema")), ["field", "required", "type", "default", "options"])
        print()
        print(f"next: script/ha flow step {result.get('flow_id')} <field>=<value> ...")
        return 0

    if flow_type == "create_entry":
        # An options flow finishes with the same result type, but carries no
        # entry — it updated one rather than creating it.
        entry = result.get("result") or {}
        if entry.get("entry_id"):
            print(f"created config entry {entry.get('title', '')} ({entry['entry_id']})")
        else:
            print(f"flow finished — config entry {result.get('handler', '')} updated")
        return 0

    if flow_type == "abort":
        # Reauth and reconfigure finish by aborting with a success reason, so the
        # reason decides the exit code rather than the result type.
        reason = str(result.get("reason", ""))
        if reason.endswith("_successful"):
            print(f"finished: {reason}")
            return 0
        print(f"aborted: {reason}")
        return 1

    if flow_type == "menu":
        emit_pairs({"flow_id": result.get("flow_id"), "step_id": result.get("step_id")})
        print()
        for option in result.get("menu_options") or []:
            print(f"  {option}")
        print()
        print(f"next: script/ha flow step {result.get('flow_id')} next_step_id=<option>")
        return 0

    emit_json(result)
    return 0


async def cmd_flow_handlers(client: HaClient, args: argparse.Namespace) -> int:
    """List the integrations that can start a config flow."""
    handlers = await client.rest("GET", "/api/config/config_entries/flow_handlers")
    if not args.all:
        handlers = [handler for handler in handlers if handler == args.domain]
    if args.json:
        emit_json(handlers)
        return 0
    for handler in handlers:
        print(handler)
    if not handlers:
        print(f"{args.domain} has no config flow — check config_flow in manifest.json")
    return 0


async def cmd_flow_start(client: HaClient, args: argparse.Namespace) -> int:
    """Start a config flow, or a reconfigure flow for an existing entry."""
    payload: dict[str, Any] = {"handler": args.flow_handler or args.domain}
    if args.reconfigure:
        entry = await resolve_entry(client, args.domain, None if args.reconfigure == "auto" else args.reconfigure)
        payload["entry_id"] = entry["entry_id"]
    result = await client.rest("POST", CONFIG_FLOW, payload=payload)
    return render_step(result, args)


async def cmd_flow_options(client: HaClient, args: argparse.Namespace) -> int:
    """Start an options flow for a config entry.

    The options endpoint takes the entry id as its `handler` — unlike the config
    flow endpoint, which takes a domain.
    """
    entry = await resolve_entry(client, args.domain, args.entry_id)
    result = await client.rest(
        "POST",
        OPTIONS_FLOW,
        payload={"handler": entry["entry_id"]},
    )
    return render_step(result, args)


async def cmd_flow_show(client: HaClient, args: argparse.Namespace) -> int:
    """Show the current step of a flow that is already running."""
    _, current = await resolve_flow(client, args.flow_id)
    return render_step(current, args)


async def cmd_flow_step(client: HaClient, args: argparse.Namespace) -> int:
    """Submit the current step and print whatever comes next.

    Fields not given on the command line fall back to the step's own defaults,
    so changing one option does not require restating the rest. `--exact` skips
    that and submits only what was passed.
    """
    base, current = await resolve_flow(client, args.flow_id)
    data = parse_data(args.data, args.json_data)
    if not args.exact:
        data = step_defaults(current.get("data_schema")) | data
    return render_step(await client.rest("POST", f"{base}/{args.flow_id}", payload=data), args)


async def cmd_flow_abort(client: HaClient, args: argparse.Namespace) -> int:
    """Abandon a running flow."""
    base, _ = await resolve_flow(client, args.flow_id)
    await client.rest("DELETE", f"{base}/{args.flow_id}")
    print(f"aborted flow {args.flow_id}")
    return 0
