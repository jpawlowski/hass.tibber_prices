"""Command-line access to the development Home Assistant instance.

Invoked through `script/ha`, which resolves the integration domain and the
virtualenv first. Authenticates with the token `script/setup/seed-auth` mints,
so no credential ever has to appear in a command line or in an agent's context.

Exit codes:
    0  success
    1  the command failed
    2  Home Assistant is not reachable
    3  authentication failed
"""

import argparse
import asyncio
import os
import sys

from . import commands, flows
from .client import DEFAULT_URL, EXIT_ERROR, EXIT_OK, HaClient, HaError, read_token

DESCRIPTION = "Talk to the development Home Assistant instance."
EPILOG = (
    "Listings are scoped to this integration; pass --all to widen them.\n"
    "Set HA_URL and HA_TOKEN to target an instance other than the local one."
)


def build_parser(domain: str) -> argparse.ArgumentParser:
    """Build the full command tree."""
    parser = argparse.ArgumentParser(
        prog="script/ha",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="emit raw JSON instead of a table")
    parser.add_argument("--url", default=os.environ.get("HA_URL", DEFAULT_URL), help="instance URL")
    parser.add_argument("--timeout", type=float, default=10.0, help="request timeout in seconds")
    parser.add_argument("--domain", default=domain, help="integration domain to scope to")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler, help_text: str) -> argparse.ArgumentParser:
        child = sub.add_parser(name, help=help_text, description=help_text)
        child.set_defaults(func=handler)
        return child

    add("status", commands.cmd_status, "Show whether Home Assistant is up and what it runs")

    states = add("states", commands.cmd_states, "Show entity states for this integration")
    states.add_argument("entity_id", nargs="?", help="a single entity to show in full")
    states.add_argument("--all", action="store_true", help="every entity in the instance")
    states.add_argument("--attributes", action="store_true", help="include the attributes column")

    entity = add("entity", commands.cmd_entity, "Show state, registry entry, and source of one entity")
    entity.add_argument("entity_id")

    entities = add("entities", commands.cmd_entities, "List registry entries with their unique ids")
    entities.add_argument("--all", action="store_true", help="every entity in the instance")

    devices = add("devices", commands.cmd_devices, "List devices owned by this integration")
    devices.add_argument("--all", action="store_true", help="every device in the instance")

    entries = add("entries", commands.cmd_entries, "Show config entry state and failure reason")
    entries.add_argument("--all", action="store_true", help="every config entry in the instance")

    reload_ = add("reload", commands.cmd_reload, "Reload a config entry instead of restarting")
    reload_.add_argument("entry_id", nargs="?", help="defaults to this integration's only entry")

    diagnostics = add("diagnostics", commands.cmd_diagnostics, "Download config entry or device diagnostics")
    diagnostics.add_argument("entry_id", nargs="?", help="defaults to this integration's only entry")
    diagnostics.add_argument("--device", help="a device id, for device diagnostics")

    services = add("services", commands.cmd_services, "List service actions")
    services.add_argument("service_domain", nargs="?", help="defaults to this integration")
    services.add_argument("--all", action="store_true", help="every action in the instance")

    call = add("call", commands.cmd_call, "Call a service action")
    call.add_argument("action", help="<domain>.<action>")
    call.add_argument("data", nargs="*", default=[], help="key=value pairs")
    call.add_argument("--data", dest="json_data", help="service data as a JSON object")
    call.add_argument("--response", action="store_true", help="request response data")

    template = add("template", commands.cmd_template, "Render a Jinja template against live state")
    template.add_argument("template")

    logs = add("logs", commands.cmd_logs, "Show the structured error log")
    logs.add_argument("--level", choices=commands.LOG_LEVELS, default="warning", help="minimum level")
    logs.add_argument("--grep", help="only records containing this text")
    logs.add_argument("-n", "--number", type=int, default=25, help="how many records to show")

    loglevel = add("loglevel", commands.cmd_loglevel, "Change log levels without restarting")
    loglevel.add_argument("assignments", nargs="+", metavar="LOGGER=LEVEL")

    watch = add("watch", commands.cmd_watch, "Stream events to see whether state actually changes")
    watch.add_argument("--entity", action="append", default=[], help="restrict to an entity (repeatable)")
    watch.add_argument("--event", default="state_changed", help="event type to subscribe to")
    watch.add_argument("--seconds", type=float, default=30.0, help="how long to listen")
    watch.add_argument("--all", action="store_true", help="do not filter to this integration")

    setup_info = add("setup-info", commands.cmd_setup_info, "Show setup timings and the manifest")
    setup_info.add_argument("--all", action="store_true", help="every integration")

    token = add("token", commands.cmd_token, "Show the development token's metadata")
    token.add_argument("--rotate", action="store_true", help="mint a new token (Home Assistant must be stopped)")
    token.add_argument("--revoke", action="store_true", help="revoke the token (Home Assistant must be stopped)")

    flow = sub.add_parser("flow", help="Drive config, options, and reconfigure flows")
    flow_sub = flow.add_subparsers(dest="flow_command", required=True)

    def add_flow(name: str, handler, help_text: str) -> argparse.ArgumentParser:
        child = flow_sub.add_parser(name, help=help_text, description=help_text)
        child.set_defaults(func=handler)
        return child

    flow_handlers = add_flow("handlers", flows.cmd_flow_handlers, "List integrations that offer a config flow")
    flow_handlers.add_argument("--all", action="store_true", help="every handler in the instance")

    flow_start = add_flow("start", flows.cmd_flow_start, "Start a config or reconfigure flow")
    flow_start.add_argument("--handler", dest="flow_handler", help="integration domain (defaults to this one)")
    flow_start.add_argument(
        "--reconfigure",
        nargs="?",
        const="auto",
        help="reconfigure an existing entry, optionally by entry id",
    )

    flow_options = add_flow("options", flows.cmd_flow_options, "Start an options flow")
    flow_options.add_argument("entry_id", nargs="?", help="defaults to this integration's only entry")

    flow_show = add_flow("show", flows.cmd_flow_show, "Show the current step of a running flow")
    flow_show.add_argument("flow_id")

    flow_step = add_flow("step", flows.cmd_flow_step, "Submit the current step")
    flow_step.add_argument("flow_id")
    flow_step.add_argument("data", nargs="*", default=[], help="key=value pairs")
    flow_step.add_argument("--data", dest="json_data", help="step input as a JSON object")
    flow_step.add_argument("--exact", action="store_true", help="submit only what was passed, without step defaults")

    flow_abort = add_flow("abort", flows.cmd_flow_abort, "Abandon a running flow")
    flow_abort.add_argument("flow_id")

    return parser


async def dispatch(args: argparse.Namespace) -> int:
    """Open a client and run the selected command."""
    async with HaClient(args.url, read_token(), args.timeout) as client:
        return await args.func(client, args)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the command, and translate failures into exit codes."""
    domain = os.environ.get("INTEGRATION_DOMAIN", "")
    args = build_parser(domain).parse_args(argv)

    # `token --rotate/--revoke` is the one command that must run against a
    # stopped instance, so it delegates to the minting script rather than the API.
    if args.command == "token" and (args.rotate or args.revoke):
        flag = "--revoke" if args.revoke else "--force"
        os.execvp("script/setup/seed-auth", ["script/setup/seed-auth", flag])

    try:
        return asyncio.run(dispatch(args))
    except HaError as err:
        print(f"error: {err}", file=sys.stderr)
        return err.code
    except KeyboardInterrupt:
        return EXIT_ERROR
    except BrokenPipeError:
        # A reader closed the pipe first — `script/ha diagnostics | head`. Point
        # stdout at devnull so the interpreter's final flush does not raise it
        # again, and exit quietly the way every other shell tool does.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
