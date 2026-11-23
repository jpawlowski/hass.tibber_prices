"""Whether Home Assistant is running locally, and since when.

The development instance is shared: the developer starts, stops, and restarts it
while an agent is working, and the agent does the same. Neither side may assume
its own last action still holds. This answers the question authoritatively and
cheaply, so nobody has to go digging through `ps` output.

`homeassistant/runner.py` holds an exclusive `flock` on `.ha_run.lock` for as
long as it runs, and deliberately never unlinks the file — so the file existing
proves nothing, and only the lock does. The contents are what the last run wrote
at startup, and are current only while that lock is held.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path

# script/ha exports the config directory of the active Home Assistant environment.
CONFIG_DIR = Path(os.environ.get("HA_CONFIG_DIR", "config"))
LOCK_FILE = CONFIG_DIR / ".ha_run.lock"
DEVELOP_RUN = Path(".local/ha-develop.json")


@dataclass(frozen=True)
class RunState:
    """What the run lock says about the local instance."""

    running: bool
    pid: int | None = None
    started: datetime | None = None

    @property
    def uptime(self) -> str:
        """Return how long the instance has been up, as a short human string."""
        if self.started is None:
            return "unknown"
        seconds = int((datetime.now(UTC) - self.started).total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def run_state() -> RunState:
    """Return whether a local Home Assistant currently holds its run lock."""
    if not LOCK_FILE.is_file():
        return RunState(running=False)
    try:
        with LOCK_FILE.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                running = True
            else:
                running = False
            handle.seek(0)
            raw = handle.read().strip()
    except OSError:
        return RunState(running=False)

    if not running or not raw:
        return RunState(running=running)
    try:
        info = json.loads(raw)
        started = datetime.fromtimestamp(float(info["start_ts"]), tz=UTC)
    except ValueError, KeyError, TypeError:
        return RunState(running=True)
    return RunState(running=True, pid=info.get("pid"), started=started)


def develop_run() -> dict[str, str]:
    """Return what script/develop recorded about the instance it last started: environment, version, who."""
    try:
        return json.loads(DEVELOP_RUN.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
