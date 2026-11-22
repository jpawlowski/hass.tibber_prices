"""Mint, rotate, or revoke the development long-lived access token.

Gives local tooling — `script/ha` above all — authenticated access to the
development Home Assistant instance without a human creating a token in the UI.

The token is minted offline, by booting Home Assistant's own `AuthManager`
against the stopped config directory the way `homeassistant/scripts/auth.py`
does. Home Assistant writes `config/.storage/auth` itself, so the store schema,
the JWT claim set, and the file mode are its responsibility, not ours.

Home Assistant must be stopped. `AuthStore.async_load()` schedules an
unconditional save 300 seconds after boot that rewrites the whole store from
memory, so a token injected into a running instance is discarded without a
trace. This module holds Home Assistant's own `.ha_run.lock` for the whole
operation, which makes that race impossible in both directions.

Called by `script/setup/seed-auth`, which maps the exit codes below onto the
project's logging helpers.
"""

import argparse
import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import TYPE_CHECKING

from ha_cli.instance import CONFIG_DIR, LOCK_FILE

from homeassistant.auth import auth_manager_from_config
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.config_entries import ConfigEntries
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

if TYPE_CHECKING:
    from collections.abc import Generator

    from homeassistant.auth.models import User

# Exit codes — the contract with script/setup/seed-auth.
EXIT_MINTED = 0
EXIT_ERROR = 1
EXIT_STILL_VALID = 10
EXIT_NOT_ONBOARDED = 11
EXIT_HA_RUNNING = 12
EXIT_REVOKED = 13
EXIT_NOTHING_TO_REVOKE = 14

STORAGE_DIR = CONFIG_DIR / ".storage"
AUTH_STORE = STORAGE_DIR / "auth"
TOKEN_FILE = STORAGE_DIR / "dev_access_token"
META_FILE = STORAGE_DIR / "dev_access_token.json"

DEFAULT_CLIENT_NAME = "blueprint-dev-cli"
DEFAULT_LIFESPAN_DAYS = 30
ROTATE_BEFORE_DAYS = 7


def write_private(path: Path, content: str) -> None:
    """Write content to path atomically, readable only by the owner."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        tmp_path.chmod(0o600)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def token_is_usable() -> bool:
    """Return True when the stored token exists and is still worth keeping.

    The metadata alone is not enough: a token whose refresh token has been
    removed from the auth store — by `script/setup/reset`, by the UI, or by a
    restored config directory — authenticates nothing, so the refresh token id
    is checked against the store as well.
    """
    if not TOKEN_FILE.is_file() or not META_FILE.is_file():
        return False
    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
        store = json.loads(AUTH_STORE.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False

    known = {token["id"] for token in store["data"]["refresh_tokens"]}
    if meta.get("refresh_token_id") not in known:
        return False
    remaining = float(meta.get("expires_at", 0)) - datetime.now(UTC).timestamp()
    return remaining > ROTATE_BEFORE_DAYS * 86400


@contextmanager
def run_lock() -> Generator[bool]:
    """Hold Home Assistant's single-instance lock, yielding whether we got it.

    `homeassistant.runner.ensure_single_execution` takes the same `flock` on the
    same file, so holding it means Home Assistant cannot start underneath us,
    and failing to take it means Home Assistant is already running.
    """
    with LOCK_FILE.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True


async def load_hass() -> HomeAssistant:
    """Boot the minimum of Home Assistant needed to reach the auth store.

    Mirrors `homeassistant/scripts/auth.py`: the device and entity registries
    are loaded because `AuthStore.async_load()` resolves user permissions
    against them.
    """
    hass = HomeAssistant(str(CONFIG_DIR.resolve()))
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    dr.async_setup(hass)
    await asyncio.gather(dr.async_load(hass), er.async_load(hass))
    hass.auth = await auth_manager_from_config(hass, [{"type": "homeassistant"}], [])
    return hass


async def pick_user(hass: HomeAssistant) -> User | None:
    """Return the account to mint for: the owner, else any active administrator.

    Never keyed on a user name — downstream repositories onboard under their own.
    """
    if (owner := await hass.auth.async_get_owner()) is not None:
        return owner
    for user in await hass.auth.async_get_users():
        if user.is_admin and not user.system_generated:
            return user
    return None


async def run(client_name: str, lifespan_days: int, revoke: bool) -> int:
    """Mint or revoke the token, then flush the auth store to disk."""
    hass = await load_hass()
    try:
        user = await pick_user(hass)
        if user is None:
            print("no active administrator account in the auth store")
            return EXIT_NOT_ONBOARDED

        removed = 0
        for token in list(user.refresh_tokens.values()):
            if token.client_name == client_name:
                hass.auth.async_remove_refresh_token(token)
                removed += 1

        if revoke:
            TOKEN_FILE.unlink(missing_ok=True)
            META_FILE.unlink(missing_ok=True)
            if not removed:
                print("no development token to revoke")
                return EXIT_NOTHING_TO_REVOKE
            print(f"Revoked the development token for {user.name}")
            return EXIT_REVOKED

        refresh_token = await hass.auth.async_create_refresh_token(
            user,
            client_name=client_name,
            token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
            access_token_expiration=timedelta(days=lifespan_days),
        )
        access_token = hass.auth.async_create_access_token(refresh_token)
        expires_at = datetime.now(UTC) + timedelta(days=lifespan_days)

        write_private(TOKEN_FILE, access_token)
        write_private(
            META_FILE,
            json.dumps(
                {
                    "refresh_token_id": refresh_token.id,
                    "client_name": client_name,
                    "user_id": user.id,
                    "user_name": user.name,
                    "created_at": refresh_token.created_at.isoformat(),
                    "expires_at": expires_at.timestamp(),
                    "expires_at_iso": expires_at.isoformat(),
                    "ha_version": HA_VERSION,
                },
                indent=2,
            )
            + "\n",
        )
        verb = "Rotated" if removed else "Minted"
        print(f"{verb} development token for {user.name}, valid until {expires_at:%Y-%m-%d %H:%M} UTC")
        return EXIT_MINTED
    finally:
        # A freshly constructed HomeAssistant sits in CoreState.not_running, and
        # async_stop() returns early in that state without firing
        # EVENT_HOMEASSISTANT_FINAL_WRITE — so the delayed save never lands and
        # the token is minted into memory only. force=True runs the full
        # shutdown and flushes the auth store.
        await hass.async_stop(force=True)


def main() -> int:
    """Parse arguments, apply the guards, and dispatch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rotate now, even if the token is still valid")
    parser.add_argument("--revoke", action="store_true", help="remove the token and its refresh token")
    args = parser.parse_args()

    if not AUTH_STORE.is_file():
        print("Home Assistant is not onboarded yet")
        return EXIT_NOT_ONBOARDED

    client_name = os.environ.get("HA_DEV_TOKEN_CLIENT_NAME", DEFAULT_CLIENT_NAME)
    lifespan_days = int(os.environ.get("HA_DEV_TOKEN_DAYS", DEFAULT_LIFESPAN_DAYS))

    with run_lock() as acquired:
        if not acquired:
            print("Home Assistant is running")
            return EXIT_HA_RUNNING
        if not args.force and not args.revoke and token_is_usable():
            print("the development token is still valid")
            return EXIT_STILL_VALID
        try:
            return asyncio.run(run(client_name, lifespan_days, args.revoke))
        except Exception as err:  # noqa: BLE001 — the caller decides how loud this is
            print(f"{type(err).__name__}: {err}")
            return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
