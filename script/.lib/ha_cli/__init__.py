"""Developer CLI for the local Home Assistant instance, invoked via `script/ha`.

Split so each part stays readable on its own:

- `client`   REST and WebSocket transport, and the exit-code taxonomy
- `output`   table and JSON rendering, plus redaction
- `commands` the debugging commands
- `flows`    driving config, options, and reconfigure flows
"""
