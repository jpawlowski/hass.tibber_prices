"""Regression tests for the synchronized architecture checker."""

from pathlib import Path
import subprocess
import sys

import pytest

CHECKER = Path(__file__).parents[1] / ".lib" / "architecture_check.py"


def _run_checker(
    tmp_path: Path,
    source: str,
    *,
    filename: str = "sensor.py",
    tracked: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the checker against one temporary integration source file."""
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    source_file = tmp_path / "custom_components" / "example" / filename
    source_file.parent.mkdir(parents=True)
    source_file.write_text(source, encoding="utf-8")
    if tracked:
        subprocess.run(["git", "add", str(source_file.relative_to(tmp_path))], cwd=tmp_path, check=True)
    return subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
@pytest.mark.parametrize("tracked", [False, True])
def test_checks_tracked_and_untracked_files(tmp_path: Path, *, tracked: bool) -> None:
    """Tracked and untracked integration files are both checked."""
    result = _run_checker(
        tmp_path,
        "from homeassistant.components.sensor import SensorEntityDescription\n"
        'SensorEntityDescription(key="x", name="Hardcoded")\n',
        tracked=tracked,
    )

    assert result.returncode == 1
    assert "sets `name=` directly" in result.stdout


@pytest.mark.unit
def test_checks_untracked_banned_filename(tmp_path: Path) -> None:
    """A newly created device automation file fails before it is staged."""
    result = _run_checker(tmp_path, '"""Forbidden platform."""\n', filename="device_trigger.py")

    assert result.returncode == 1
    assert "device triggers are frozen upstream" in result.stdout


@pytest.mark.unit
def test_checks_multiple_packages_without_following_package_symlinks(tmp_path: Path) -> None:
    """Every real package is checked without traversing a HACS-style directory symlink."""
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    first_source = tmp_path / "custom_components" / "first" / "sensor.py"
    second_source = tmp_path / "custom_components" / "second" / "sensor.py"
    linked_source = tmp_path / "installed" / "sensor.py"
    for source_file in (first_source, second_source, linked_source):
        source_file.parent.mkdir(parents=True, exist_ok=True)
    first_source.write_text('VALUE = "valid"\n', encoding="utf-8")
    second_source.write_text(
        "from homeassistant.components.sensor import SensorEntityDescription\n"
        'SensorEntityDescription(key="x", name="Hardcoded")\n',
        encoding="utf-8",
    )
    linked_source.write_text('raise RuntimeError("must not be scanned")\n', encoding="utf-8")
    (tmp_path / "custom_components" / "hacs").symlink_to(linked_source.parent, target_is_directory=True)
    subprocess.run(
        ["git", "add", str(first_source.relative_to(tmp_path)), str(second_source.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
    )

    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "custom_components/second/sensor.py" in result.stdout
    assert "custom_components/hacs" not in result.stdout
    assert "1 architecture finding(s) in 2 file(s)." in result.stdout


@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            (
                "from homeassistant.components.sensor import SensorEntityDescription as Description\n"
                'Description(key="x", name="Hardcoded")\n'
            ),
            "sets `name=` directly",
        ),
        (
            (
                "from homeassistant.components import sensor as sensor_platform\n"
                'sensor_platform.SensorEntityDescription(key="x", icon="mdi:test")\n'
            ),
            "sets `icon=` directly",
        ),
        (
            (
                "from homeassistant.components.sensor import SensorEntityDescription\n"
                "class MyDescription(SensorEntityDescription):\n"
                "    pass\n"
                'MyDescription(key="x", icon="mdi:test")\n'
            ),
            "sets `icon=` directly",
        ),
        (
            (
                "from homeassistant.components.sensor import SensorEntityDescription\n"
                "class MyDescription(SensorEntityDescription):\n"
                '    name: str | None = "Hardcoded"\n'
            ),
            "sets `name=` directly",
        ),
        (
            (
                "from homeassistant.components.sensor import SensorEntityDescription\n"
                'SensorEntityDescription(key="x", **{"name": "Hardcoded"})\n'
            ),
            "sets `name=` directly",
        ),
    ],
)
def test_detects_entity_description_metadata(tmp_path: Path, source: str, expected: str) -> None:
    """Aliases, subclasses, class defaults, and literal unpacking are checked."""
    result = _run_checker(tmp_path, source)

    assert result.returncode == 1
    assert expected in result.stdout


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        (
            "class AuditEntityDescription:\n"
            "    def __init__(self, *, name: str) -> None:\n"
            "        self.name = name\n"
            'AuditEntityDescription(name="Audit")\n'
        ),
        'from unrelated import AuditEntityDescription\nAuditEntityDescription(name="Audit")\n',
        'async def load(api):\n    return await api.async_get_device("device-id")\n',
        'from homeassistant.components.fan import FanEntityDescription\nFanEntityDescription(key="fan", name=None)\n',
    ],
)
def test_allows_unrelated_calls_and_documented_name_none(tmp_path: Path, source: str) -> None:
    """Unrelated same-named APIs and the documented main-entity name remain valid."""
    result = _run_checker(tmp_path, source)

    assert result.returncode == 0
    assert "no architecture findings" in result.stdout


@pytest.mark.unit
def test_registry_binding_does_not_leak_between_functions(tmp_path: Path) -> None:
    """A registry variable in one scope does not taint an unrelated same-named parameter."""
    result = _run_checker(
        tmp_path,
        "from homeassistant.helpers import device_registry as dr\n"
        "def get_registry():\n"
        "    registry = dr.async_get(hass)\n"
        "    return registry\n"
        "def load(registry):\n"
        '    return registry.async_get_device("device-id")\n',
    )

    assert result.returncode == 0
    assert "no architecture findings" in result.stdout


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        (
            "from homeassistant.helpers import device_registry as dr\n"
            "registry = dr.async_get(hass)\n"
            'registry.async_get_device(identifiers={("example", "id")})\n'
        ),
        (
            "from homeassistant.helpers.device_registry import async_get as get_registry\n"
            "registry = get_registry(hass)\n"
            'registry.async_get_device(connections={("mac", "00:11:22:33:44:55")})\n'
        ),
        (
            "from homeassistant.helpers import device_registry as dr\n"
            'dr.async_get(hass).async_get_device(identifiers={("example", "id")})\n'
        ),
        (
            "from homeassistant.helpers import device_registry as dr\n"
            "def lookup(registry: dr.DeviceRegistry):\n"
            '    return registry.async_get_device(identifiers={("example", "id")})\n'
        ),
    ],
)
def test_detects_known_device_registry_lookups(tmp_path: Path, source: str) -> None:
    """Only receivers known to be Home Assistant's DeviceRegistry are checked."""
    result = _run_checker(tmp_path, source)

    assert result.returncode == 1
    assert "DeviceRegistry.async_get_device() is unscoped" in result.stdout


@pytest.mark.unit
def test_allows_scoped_device_registry_lookup(tmp_path: Path) -> None:
    """Entry-scoped device registry lookups remain valid."""
    result = _run_checker(
        tmp_path,
        "from homeassistant.helpers import device_registry as dr\n"
        "registry = dr.async_get(hass)\n"
        'registry.async_get_device_by_identifier(("example", "id"), entry.entry_id)\n',
    )

    assert result.returncode == 0
    assert "no architecture findings" in result.stdout
