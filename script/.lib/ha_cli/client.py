"""Transport for the development Home Assistant instance.

Wraps the REST API and the WebSocket API behind one object so the commands can
stay declarative. Every failure is turned into `HaError` carrying the process
exit code the caller should use, so no command has to think about aiohttp.
"""

import asyncio
import json
import os
from typing import TYPE_CHECKING, Any, Self

import aiohttp

from .instance import CONFIG_DIR

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Exit codes — see the module docstring of ha_cli/__main__.py.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_UNREACHABLE = 2
EXIT_AUTH = 3

TOKEN_FILE = CONFIG_DIR / ".storage" / "dev_access_token"
DEFAULT_URL = "http://127.0.0.1:8123"

_UNREACHABLE_HINT = "Home Assistant is not reachable at {url} — start it with ./script/develop"
_NO_TOKEN_HINT = (
    "no development token yet — run ./script/develop, complete onboarding in the "
    "browser if you have not, then restart it once"
)
_BAD_TOKEN_HINT = (
    "the development token was rejected — rotate it with `script/ha token --rotate` (Home Assistant stopped)"
)


class HaError(Exception):
    """A failure that should end the process with a specific exit code."""

    def __init__(self, message: str, code: int = EXIT_ERROR, status: int | None = None) -> None:
        """Store the message, the exit code, and the HTTP status if there was one."""
        super().__init__(message)
        self.code = code
        self.status = status


def read_token() -> str:
    """Return the access token, preferring HA_TOKEN over the seeded file."""
    if token := os.environ.get("HA_TOKEN"):
        return token.strip()
    if not TOKEN_FILE.is_file():
        raise HaError(_NO_TOKEN_HINT, EXIT_AUTH)
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise HaError(_NO_TOKEN_HINT, EXIT_AUTH)
    return token


class HaClient:
    """REST and WebSocket access to one Home Assistant instance."""

    def __init__(self, url: str, token: str, timeout: float) -> None:
        """Configure the client without opening any connection yet."""
        self.url = url.rstrip("/")
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_id = 0

    async def __aenter__(self) -> Self:
        """Open the HTTP session.

        No session-wide timeout: it would also bound the WebSocket connection,
        and `ha watch` deliberately holds one open for longer than any request.
        The timeout is applied per REST call instead.
        """
        self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self._token}"})
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close the WebSocket and the HTTP session."""
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._session is not None:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        """Return the open session, or fail loudly if used outside the context."""
        if self._session is None:
            raise HaError("HaClient used outside its async context")
        return self._session

    async def rest(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: dict[str, str] | None = None,
        as_text: bool = False,
    ) -> Any:
        """Call a REST endpoint and return the decoded body.

        Args:
            as_text: return the raw body instead of parsing it as JSON, for the
                endpoints that answer in plain text (`/api/template`) or serve a
                file (`/api/error_log`).
        """
        try:
            async with self.session.request(
                method,
                f"{self.url}{path}",
                json=payload,
                params=params,
                timeout=self._timeout,
            ) as response:
                body = await response.text()
                if response.status in (401, 403):
                    raise HaError(_BAD_TOKEN_HINT, EXIT_AUTH)
                if response.status == 404:
                    raise HaError(f"not found: {path}", status=404)
                if response.status >= 400:
                    raise HaError(
                        f"Home Assistant returned {response.status}: {body.strip()}",
                        status=response.status,
                    )
                if as_text:
                    return body
                return json.loads(body) if body else None
        except aiohttp.ClientConnectionError as err:
            raise HaError(_UNREACHABLE_HINT.format(url=self.url), EXIT_UNREACHABLE) from err
        except TimeoutError as err:
            raise HaError(f"timed out talking to {self.url}", EXIT_UNREACHABLE) from err

    async def _connect_ws(self) -> aiohttp.ClientWebSocketResponse:
        """Open and authenticate a WebSocket connection, reusing an open one."""
        if self._ws is not None and not self._ws.closed:
            return self._ws
        ws_url = f"{self.url.replace('http', 'ws', 1)}/api/websocket"
        try:
            ws = await self.session.ws_connect(ws_url)
        except aiohttp.ClientConnectionError as err:
            raise HaError(_UNREACHABLE_HINT.format(url=self.url), EXIT_UNREACHABLE) from err

        # auth_required -> auth -> auth_ok, per homeassistant/components/websocket_api/auth.py
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": self._token})
        result = await ws.receive_json()
        if result.get("type") != "auth_ok":
            await ws.close()
            raise HaError(_BAD_TOKEN_HINT, EXIT_AUTH)
        self._ws = ws
        return ws

    async def ws(self, command: str, **payload: Any) -> Any:
        """Send one WebSocket command and return its result."""
        ws = await self._connect_ws()
        self._ws_id += 1
        message_id = self._ws_id
        await ws.send_json({"id": message_id, "type": command, **payload})
        while True:
            message = await ws.receive_json()
            if message.get("id") != message_id or message.get("type") != "result":
                continue
            if not message.get("success"):
                error = message.get("error", {})
                raise HaError(f"{command}: {error.get('message', error)}")
            return message.get("result")

    async def ws_events(self, command: str, seconds: float, **payload: Any) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to a WebSocket stream and yield events until seconds elapse."""
        ws = await self._connect_ws()
        self._ws_id += 1
        message_id = self._ws_id
        await ws.send_json({"id": message_id, "type": command, **payload})

        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while (remaining := deadline - loop.time()) > 0:
            try:
                message = await asyncio.wait_for(ws.receive_json(), timeout=remaining)
            except TimeoutError, TypeError:
                return
            if message.get("id") != message_id:
                continue
            if message.get("type") == "result" and not message.get("success"):
                error = message.get("error", {})
                raise HaError(f"{command}: {error.get('message', error)}")
            if message.get("type") == "event":
                yield message["event"]
