"""Tests for script/.lib/ha_envs.sh, with stubbed version resolution and venv builds."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

LIB = Path(__file__).parents[1] / ".lib"
STUBS = """
target_ha_version() { local -n _r="$1"; _r="$STUB_MINIMUM"; }
resolve_ha_version() {
    local -n _r="$1"
    case "$2" in latest) _r="$STUB_LATEST" ;; beta) _r="$STUB_BETA" ;; *) _r="$2" ;; esac
}
ha_envs_create_venv() { mkdir -p "$1/bin" "$1/lib"; echo "home = stub" >"$1/pyvenv.cfg"; touch "$1/bin/activate"; }
ha_envs_install() {
    [[ " ${STUB_FAIL:-} " == *" $2 "* ]] && return 1
    echo "$2" >>"$1/installs"
    echo "$2" >"$1/bin/version"
}
"""
VERSIONS = {"STUB_MINIMUM": "2026.11.2", "STUB_LATEST": "2026.11.2", "STUB_BETA": "2026.12.0b1"}


def _outside_container() -> dict[str, str]:
    """The environment without what marks a dev container or CI, so the venv root is the test's own."""
    hidden = {"REMOTE_CONTAINERS", "CODESPACES", "GITHUB_ACTIONS", "VIRTUAL_ENV"}
    return {k: v for k, v in os.environ.items() if k not in hidden}


def _bash(workdir: Path, commands: str, **stubs: str) -> subprocess.CompletedProcess[str]:
    """Run commands with the library and the stubs loaded, in workdir, outside any dev container or CI."""
    env = _outside_container()
    script = "\n".join(
        [
            "set -euo pipefail",
            *(f"source {LIB / name}" for name in ("output.sh", "ha_envs.sh")),
            STUBS,
            commands,
        ]
    )
    return subprocess.run(
        ["bash", "-c", script],
        cwd=workdir,
        env={**env, **VERSIONS, **stubs},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    """A project directory with a hacs.json on the 2026.11 release."""
    (tmp_path / "hacs.json").write_text('{"homeassistant": "2026.11.0"}\n', encoding="utf-8")
    return tmp_path


def _root(workdir: Path) -> Path:
    return workdir / ".local" / "ha-venv"


def _slot(workdir: Path, slot: str) -> str:
    return (_root(workdir) / "slots" / slot).readlink().name


def _versions(workdir: Path) -> list[str]:
    return sorted(path.name for path in (_root(workdir) / "versions").iterdir())


@pytest.mark.unit
def test_minimum_and_latest_on_one_version_share_a_venv(workdir: Path) -> None:
    """Two slots on the same release point at one venv; the beta always gets its own."""
    result = _bash(workdir, "for s in minimum latest beta; do ha_envs_refresh $s; done; ha_envs_prune")

    assert result.returncode == 0, result.stderr
    assert _slot(workdir, "minimum") == _slot(workdir, "latest") == "2026.11.2"
    assert _slot(workdir, "beta") == "2026.12.0b1"
    assert _versions(workdir) == ["2026.11.2", "2026.12.0b1"]


@pytest.mark.unit
def test_beta_stays_a_pre_release_while_older_than_latest(workdir: Path) -> None:
    """Right after a stable release the beta keeps the last pre-release instead of taking the release."""
    result = _bash(
        workdir, "ha_envs_refresh latest; ha_envs_refresh beta", STUB_LATEST="2026.12.0", STUB_BETA="2026.12.0rc2"
    )

    assert result.returncode == 0, result.stderr
    assert _slot(workdir, "latest") == "2026.12.0"
    assert _slot(workdir, "beta") == "2026.12.0rc2"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("slot", "stubs"),
    [("beta", {"STUB_BETA": "2026.12.0"}), ("latest", {"STUB_LATEST": "2026.12.0b1"})],
    ids=["beta-given-a-release", "latest-given-a-pre-release"],
)
def test_a_slot_never_takes_the_other_kind(workdir: Path, slot: str, stubs: dict[str, str]) -> None:
    """Beta only ever holds a pre-release and latest only a release; anything else fails and builds nothing."""
    result = _bash(workdir, f"ha_envs_refresh {slot}", **stubs)

    assert result.returncode == 1
    assert not (_root(workdir) / "slots" / slot).exists()
    assert not (_root(workdir) / "versions").exists()


@pytest.mark.unit
def test_a_refresh_moves_the_slot_forward_and_prunes_the_old_version(workdir: Path) -> None:
    """A newer beta replaces the previous one, which is deleted once nothing points at it."""
    _bash(workdir, "ha_envs_refresh beta")

    result = _bash(workdir, "ha_envs_refresh beta; ha_envs_prune", STUB_BETA="2026.12.0b2")

    assert result.returncode == 0, result.stderr
    assert _slot(workdir, "beta") == "2026.12.0b2"
    assert _versions(workdir) == ["2026.12.0b2"]


@pytest.mark.unit
def test_an_unchanged_environment_is_not_installed_again(workdir: Path) -> None:
    """A refresh skips the install when neither the version nor a requirements file changed."""
    _bash(workdir, "ha_envs_refresh minimum; ha_envs_refresh minimum")
    installs = _root(workdir) / "versions" / "2026.11.2" / "installs"
    assert installs.read_text(encoding="utf-8").splitlines() == ["2026.11.2"]

    (workdir / "requirements_test.txt").write_text("pytest-homeassistant==2026.11.2\n", encoding="utf-8")
    _bash(workdir, "ha_envs_refresh minimum")

    assert installs.read_text(encoding="utf-8").splitlines() == ["2026.11.2", "2026.11.2"]


@pytest.mark.unit
def test_a_failed_build_keeps_the_previous_version(workdir: Path) -> None:
    """The slot moves only after its new version built; the unfinished build is removed."""
    _bash(workdir, "ha_envs_refresh beta")

    result = _bash(workdir, "ha_envs_refresh beta", STUB_BETA="2026.12.0b2", STUB_FAIL="2026.12.0b2")

    assert result.returncode == 1
    assert _slot(workdir, "beta") == "2026.12.0b1"
    assert _versions(workdir) == ["2026.12.0b1"]


@pytest.mark.unit
def test_use_mirrors_the_active_slot_at_the_root(workdir: Path) -> None:
    """The root's bin and pyvenv.cfg follow the active slot, so every existing venv path keeps working."""
    _bash(workdir, "ha_envs_refresh minimum; ha_envs_refresh beta; ha_envs_use minimum")
    root = _root(workdir)
    assert (root / "bin" / "version").read_text(encoding="utf-8") == "2026.11.2\n"
    assert (root / "pyvenv.cfg").is_symlink()

    _bash(workdir, "ha_envs_use beta")

    assert (root / "bin" / "version").read_text(encoding="utf-8") == "2026.12.0b1\n"
    assert _bash(workdir, "ha_current_slot").stdout == "beta"


@pytest.mark.unit
def test_use_refuses_a_slot_that_is_not_installed(workdir: Path) -> None:
    """Switching to a missing slot says how to add it and leaves the active one alone."""
    _bash(workdir, "ha_envs_refresh minimum; ha_envs_use minimum")

    result = _bash(workdir, "ha_envs_use latest")

    assert result.returncode == 1
    assert "script/ha-env add latest" in result.stdout + result.stderr
    assert _bash(workdir, "ha_current_slot").stdout == "minimum"


@pytest.mark.unit
def test_remove_keeps_minimum_and_the_active_slot(workdir: Path) -> None:
    """Minimum and the active slot cannot be removed; another slot can, and its venv goes with the next prune."""
    _bash(workdir, "for s in minimum latest beta; do ha_envs_refresh $s; done; ha_envs_use latest")

    assert _bash(workdir, "ha_envs_remove minimum").returncode == 1
    assert _bash(workdir, "ha_envs_remove latest").returncode == 1
    result = _bash(workdir, "ha_envs_remove beta; ha_envs_prune")

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in (_root(workdir) / "slots").iterdir() if p.is_symlink()) == ["latest", "minimum"]
    assert _versions(workdir) == ["2026.11.2"]


@pytest.mark.unit
def test_migrate_clears_the_single_venv_of_the_old_layout(workdir: Path) -> None:
    """A root that is itself a venv is emptied, so its slots can be built; a migrated root is left alone."""
    root = _root(workdir)
    (root / "bin").mkdir(parents=True)
    (root / "pyvenv.cfg").write_text("home = old\n", encoding="utf-8")
    (root / ".ha-version").write_text("2026.10.4\n", encoding="utf-8")

    result = _bash(workdir, "ha_envs_migrate; ha_envs_refresh minimum; ha_envs_use minimum; ha_envs_migrate")

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in root.iterdir() if not path.is_symlink()) == ["slots", "versions"]
    assert (root / "bin" / "version").read_text(encoding="utf-8") == "2026.11.2\n"


@pytest.mark.unit
def test_notice_names_a_stale_latest_or_beta_and_a_minimum_off_the_hacs_release(workdir: Path) -> None:
    """Both notices need no network; a fresh beta, an old minimum and the hacs.json release print nothing."""
    _bash(workdir, "for s in minimum beta; do ha_envs_refresh $s; done")
    slots = _root(workdir) / "slots"
    result = _bash(workdir, "ha_envs_notice")
    assert result.stdout + result.stderr == ""

    os.utime(slots / ".beta.refreshed", (0, 0))
    os.utime(slots / ".minimum.refreshed", (0, 0))
    (workdir / "hacs.json").write_text('{"homeassistant": "2026.12.0"}\n', encoding="utf-8")
    result = _bash(workdir, "ha_envs_notice")
    output = result.stdout + result.stderr

    assert "beta (2026.12.0b1) was last refreshed over 7 days ago" in output
    assert "minimum (" not in output
    assert "hacs.json asks for 2026.12" in output

    _bash(workdir, "ha_envs_refresh beta")
    assert "beta (" not in _bash(workdir, "ha_envs_notice").stderr


def _config(workdir: Path, ran: str) -> None:
    """A config/ last run by Home Assistant `ran`, with a little state of its own."""
    (workdir / "config" / ".storage").mkdir(parents=True)
    (workdir / "config" / ".storage" / "core.config_entries").write_text("{}\n", encoding="utf-8")
    (workdir / "config" / ".HA_VERSION").write_text(f"{ran}\n", encoding="utf-8")
    (workdir / "config" / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")


@pytest.mark.unit
def test_a_new_config_dir_shares_files_and_starts_from_the_minimum_state(workdir: Path) -> None:
    """A newer environment links the shared files and copies config/'s state, which it can migrate forward."""
    _config(workdir, "2026.11.2")
    beta = workdir / ".local" / "ha-config" / "beta"

    result = _bash(workdir, f"ha_envs_prepare_config {beta} 2026.12.0b1")

    assert result.returncode == 0, result.stderr
    assert (beta / "configuration.yaml").is_symlink()
    assert (beta / "configuration.yaml").read_text(encoding="utf-8") == "default_config:\n"
    assert not (beta / ".storage").is_symlink()
    assert (beta / ".storage" / "core.config_entries").is_file()


@pytest.mark.unit
def test_an_older_environment_starts_with_empty_state(workdir: Path) -> None:
    """config/'s state is never handed to a Home Assistant older than the one that last wrote it."""
    _config(workdir, "2026.11.2")
    beta = workdir / ".local" / "ha-config" / "beta"

    result = _bash(workdir, f"ha_envs_prepare_config {beta} 2026.11.0b6")

    assert result.returncode == 0, result.stderr
    assert (beta / "configuration.yaml").is_symlink()
    assert not (beta / ".storage").exists()


@pytest.mark.unit
def test_an_existing_config_dir_keeps_its_own_state(workdir: Path) -> None:
    """Only a new config directory starts from config/; one with state of its own is left alone."""
    _config(workdir, "2026.11.2")
    beta = workdir / ".local" / "ha-config" / "beta"
    (beta / ".storage").mkdir(parents=True)
    (beta / ".storage" / "own").write_text("mine\n", encoding="utf-8")

    _bash(workdir, f"ha_envs_prepare_config {beta} 2026.12.0b1")

    assert sorted(path.name for path in (beta / ".storage").iterdir()) == ["own"]


@pytest.mark.unit
def test_the_guard_moves_aside_state_a_newer_version_wrote(workdir: Path) -> None:
    """State migrated by a newer Home Assistant is kept as a backup instead of breaking an older start."""
    _config(workdir, "2026.12.0")
    (workdir / "config" / "home-assistant_v2.db").write_text("db\n", encoding="utf-8")

    result = _bash(workdir, "ha_envs_guard_config config 2026.11.2; ha_envs_guard_config config 2026.12.0")

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in (workdir / "config").iterdir() if ".bak" in path.name) == [
        ".storage.2026.12.0.bak",
        "home-assistant_v2.db.2026.12.0.bak",
    ]
    assert not (workdir / "config" / ".storage").exists()


@pytest.mark.unit
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_a_shell_runs_the_venv_root_and_its_prompt_follows_a_switch(tmp_path: Path, shell: str) -> None:
    """The shell points at the venv root, so it follows a switch; the prompt names the slot and who switched."""
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} is not installed")
    root = tmp_path / "root"
    for version in ("2026.11.2", "2026.12.0b1"):
        (root / "versions" / version / "bin").mkdir(parents=True)
        (root / "versions" / version / "bin" / "activate").touch()
        (root / "versions" / version / ".ha-version").write_text(f"{version}\n", encoding="utf-8")
    (root / "slots").mkdir()
    (root / "slots" / "minimum").symlink_to("../versions/2026.11.2")
    (root / "slots" / "beta").symlink_to("../versions/2026.12.0b1")
    (root / "current").symlink_to("slots/minimum")
    (root / "bin").symlink_to("current/bin")
    (root / ".switched").write_text("minimum\tbeta\tagent (claude-code)\t14:03\n", encoding="utf-8")
    script = (
        f"PS1='$ '; source {LIB / 'ha_env_shell.sh'}; _ha_env_prompt; echo \"$PS1\"; "
        f'ln -sfn slots/beta {root}/current; _ha_env_prompt; echo "$PS1"; echo "$VIRTUAL_ENV"'
    )
    env = {**{k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}, "HA_ENV_ROOT": str(root)}

    result = subprocess.run([shell, "-c", script], env=env, capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["(ha-minimum 2026.11.2) $ ", "(ha-beta 2026.12.0b1) $ ", str(root)]
    assert "switched: minimum → beta (by agent (claude-code) at 14:03)" in result.stderr


PYPI = (
    '{"releases": {"2026.11.2": [{"requires_python": ">=3.14.2"}], "2026.12.0b1": [{"requires_python": ">=3.15.0"}]}}'
)


@pytest.mark.unit
def test_each_environment_gets_the_python_its_release_asks_for(workdir: Path) -> None:
    """The lower bound of requires-python picks the interpreter; downloads land beside the venvs."""
    script = f"""
source {LIB / "ha_envs.sh"}
_PYPI_JSON_CACHE='{PYPI}'
uv() {{ echo "UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR $*"; }}
ha_envs_create_venv "$PWD/.local/ha-venv/versions/2026.12.0b1" 2026.12.0b1
ha_envs_create_venv "$PWD/.local/ha-venv/versions/2099.1.0" 2099.1.0
"""
    result = _bash(workdir, script)

    assert result.returncode == 0, result.stderr
    with_python, without = [line for line in result.stdout.splitlines() if line.startswith("UV_PYTHON_INSTALL_DIR")]
    assert with_python.startswith(f"UV_PYTHON_INSTALL_DIR={_root(workdir)}/python venv")
    assert "--python-preference only-managed --python 3.15" in with_python
    assert "--python-preference only-managed" in without
    assert "--python 3" not in without


def _uv_listing(listing: list[dict[str, str]]) -> str:
    """A uv stub that lists these Python builds and records every other call in uv-calls."""
    return f"""uv() {{
    if [[ $1 == python && $2 == list ]]; then echo '{json.dumps(listing)}'; else echo "uv $*" >>"$PWD/uv-calls"; fi
}}"""


@pytest.mark.unit
def test_prune_uninstalls_downloaded_pythons_no_environment_uses(workdir: Path) -> None:
    """Uv lists its builds; one stays while a venv's home points at it, through uv's minor-version link."""
    python = _root(workdir) / "python"
    for build in ("3.15.2", "3.16.0"):
        (python / f"cpython-{build}-linux" / "bin").mkdir(parents=True)
        (python / f"cpython-{build[:4]}-linux").symlink_to(python / f"cpython-{build}-linux")
    _bash(workdir, "ha_envs_refresh beta")
    cfg = _root(workdir) / "versions" / "2026.12.0b1" / "pyvenv.cfg"
    cfg.write_text(f"home = {python}/cpython-3.15-linux/bin\n", encoding="utf-8")
    listing = [
        {"key": f"cpython-{b}-linux", "path": f"{python}/cpython-{b[:4]}-linux/bin/python3"}
        for b in ("3.15.2", "3.16.0")
    ]
    stub = _uv_listing(listing)

    result = _bash(workdir, stub + "\nha_envs_prune")

    assert result.returncode == 0, result.stderr
    assert (workdir / "uv-calls").read_text(encoding="utf-8") == (
        f"uv python uninstall --quiet --install-dir {python} cpython-3.16.0-linux\n"
    )


@pytest.mark.unit
def test_prune_survives_downloaded_pythons_without_any_environment(workdir: Path) -> None:
    """A Python download whose venv never got built is removed instead of aborting the caller."""
    python = _root(workdir) / "python"
    (python / "cpython-3.15.2-linux" / "bin").mkdir(parents=True)
    listing = [{"key": "cpython-3.15.2-linux", "path": f"{python}/cpython-3.15.2-linux/bin/python3"}]
    stub = _uv_listing(listing)

    result = _bash(workdir, stub + "\nha_envs_prune; echo done")

    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith("done\n")
    assert "cpython-3.15.2-linux" in (workdir / "uv-calls").read_text(encoding="utf-8")


@pytest.mark.unit
def test_inputs_hash_the_requirements_as_sha256sum_does(workdir: Path) -> None:
    """The format stays the one earlier builds recorded, so no environment is reinstalled for it."""
    (workdir / "requirements_test.txt").write_text("pytest-homeassistant==2026.11.2\n", encoding="utf-8")
    digest = hashlib.sha256(b"pytest-homeassistant==2026.11.2\n").hexdigest()

    result = _bash(workdir, "ha_envs_inputs 2026.11.2")

    assert result.stdout == f"2026.11.2\n{digest}  requirements_test.txt\n"


@pytest.mark.unit
def test_migrate_refuses_while_home_assistant_runs_from_the_old_venv(workdir: Path) -> None:
    """The single venv of the old layout is not cleared under a running instance."""
    root = _root(workdir)
    (root / "bin").mkdir(parents=True)
    (root / "pyvenv.cfg").write_text("home = old\n", encoding="utf-8")
    (workdir / "config").mkdir()

    with (workdir / "config" / ".ha_run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = _bash(workdir, "ha_envs_migrate")

    assert result.returncode == 1
    assert (root / "pyvenv.cfg").is_file()


def _copy_scripts(workdir: Path, *names: str) -> None:
    """Copy scripts and the shared library into workdir, so they run against its files."""
    shutil.copytree(LIB, workdir / "script" / ".lib")
    for name in names:
        (workdir / "script" / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(LIB.parent / name, workdir / "script" / name)


def _run_script(workdir: Path, name: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a script copied by _copy_scripts, outside any dev container or CI."""
    return subprocess.run(
        [str(workdir / "script" / name), *args],
        cwd=workdir,
        env=_outside_container(),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
def test_refresh_without_any_environment_points_at_bootstrap(workdir: Path) -> None:
    """Nothing installed yet is reported, not an unbound-variable error."""
    _copy_scripts(workdir, "ha-env")

    result = _run_script(workdir, "ha-env", "refresh")

    assert result.returncode == 1
    assert "script/setup/bootstrap" in result.stderr
    assert "unbound" not in result.stderr


@pytest.mark.unit
def test_reset_starts_the_active_environment_over_and_leaves_config_alone(workdir: Path) -> None:
    """With beta active, its own directory is emptied, and stays empty instead of copying config/'s state again."""
    _config(workdir, "2026.11.2")
    _copy_scripts(workdir, "setup/reset")
    (workdir / "script" / "setup" / "setup").write_text("#!/bin/bash\n", encoding="utf-8")
    (workdir / "script" / "setup" / "setup").chmod(0o755)
    beta = workdir / ".local" / "ha-config" / "beta"
    prepare = f"ha_envs_prepare_config {beta} 2026.12.0b1"
    assert _bash(workdir, f"ha_envs_refresh beta; ha_envs_use beta; {prepare}").returncode == 0

    result = _run_script(workdir, "setup/reset", "--yes")
    assert _bash(workdir, prepare).returncode == 0

    assert result.returncode == 0, result.stderr
    assert not (beta / ".storage").exists()
    assert (beta / "configuration.yaml").is_symlink()
    assert (workdir / "config" / ".storage" / "core.config_entries").is_file()


@pytest.mark.unit
def test_refresh_leaves_the_environment_home_assistant_runs_on(workdir: Path) -> None:
    """The running slot comes from the run record, which stays right after a forced switch away from it."""
    _bash(workdir, "ha_envs_refresh minimum; ha_envs_refresh beta; ha_envs_use minimum")
    (workdir / ".local" / "ha-develop.json").write_text('{"slot": "beta"}\n', encoding="utf-8")
    (workdir / ".local" / "ha-config" / "beta").mkdir(parents=True)

    with (workdir / ".local" / "ha-config" / "beta" / ".ha_run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = _bash(workdir, "ha_envs_refresh beta || echo status=$?", STUB_BETA="2026.12.0b2")

    assert "status=2" in result.stdout
    assert _slot(workdir, "beta") == "2026.12.0b1"


@pytest.mark.unit
def test_version_helpers_read_the_test_pin_train_and_kind(workdir: Path) -> None:
    """The plugin's repackaging suffix is not part of the Home Assistant version it names."""
    (workdir / "requirements_test.txt").write_text("pytest-homeassistant==2026.12.0b1.post1\n", encoding="utf-8")

    result = _bash(
        workdir,
        "ha_test_pin; ha_release_train 2026.11; ha_release_train 2026.11.0b3; "
        "ha_version_is_prerelease 2026.12.0b1 && echo pre; ha_version_is_prerelease 2026.12.0 || echo stable",
    )

    assert result.stdout.splitlines() == [
        "pytest-homeassistant 2026.12.0b1.post1 2026.12.0b1",
        "2026.11",
        "2026.11",
        "pre",
        "stable",
    ]


CUSTOM_PYPI = json.dumps(
    {
        "releases": {
            version: [{"requires_python": f">={python}"}]
            for version, python in {
                "2026.10.4": "3.13.2",
                "2026.11.0b6": "3.14.2",
                "2026.11.1": "3.14.2",
                "2026.12.1": "3.15.0",
                "2027.1.0": "3.15.0",
            }.items()
        }
    }
)


def _custom(workdir: Path, commands: str) -> subprocess.CompletedProcess[str]:
    """Run commands with the real venv creation, uv stubbed to record its calls, and the releases above on PyPI."""
    script = f"""
source {LIB / "ha_envs.sh"}
ha_envs_install() {{ echo "$2" >"$1/bin/version"; }}
_PYPI_JSON_CACHE='{CUSTOM_PYPI}'
uv() {{
    echo "uv $*" >>"$PWD/uv-calls"
    if [[ $1 == venv ]]; then mkdir -p "${{@: -1}}/bin" && touch "${{@: -1}}/bin/activate"; fi
}}
{commands}
"""
    return _bash(workdir, script)


@pytest.mark.unit
def test_custom_is_a_fixed_point_that_moves_down_onto_an_older_python(workdir: Path) -> None:
    """A refresh keeps the pin; a lower pin gets its own venv on its own Python, and the higher one goes."""
    result = _custom(
        workdir,
        "HA_ENVS_CUSTOM_VERSION=2026.12.1 ha_envs_refresh custom\n"
        "STUB_LATEST=2027.1.0 ha_envs_refresh custom\n"
        "HA_ENVS_CUSTOM_VERSION=2026.11.1 ha_envs_refresh custom\n"
        "ha_envs_prune",
    )

    assert result.returncode == 0, result.stderr
    assert _slot(workdir, "custom") == "2026.11.1"
    assert _versions(workdir) == ["2026.11.1"]
    venvs = [line for line in (workdir / "uv-calls").read_text(encoding="utf-8").splitlines() if " venv " in line]
    assert len(venvs) == 2
    assert "--python 3.15" in venvs[0]
    assert venvs[0].endswith("/versions/2026.12.1")
    assert "--python 3.14" in venvs[1]
    assert venvs[1].endswith("/versions/2026.11.1")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("version", "problem"),
    [
        ("2026.10.4", "older than 2026.11.0"),
        ("2026.11.0b6", "older than 2026.11.0"),
        ("2026.11.9", "not a release on PyPI"),
    ],
)
def test_custom_refuses_a_version_below_hacs_json_or_unreleased(workdir: Path, version: str, problem: str) -> None:
    """hacs.json's minimum is the floor, a pre-release of it included, and the version has to exist."""
    result = _custom(workdir, f"HA_ENVS_CUSTOM_VERSION={version} ha_envs_refresh custom")

    assert result.returncode == 1
    assert problem in result.stderr
    assert not (_root(workdir) / "slots" / "custom").exists()


@pytest.mark.unit
def test_custom_without_a_pin_says_how_to_set_one(workdir: Path) -> None:
    """A refresh of a custom that holds nothing names the command instead of guessing a version."""
    result = _custom(workdir, "ha_envs_refresh custom")

    assert result.returncode == 1
    assert "script/ha-env add custom <version>" in result.stderr


@pytest.mark.unit
def test_notice_names_a_custom_left_below_a_raised_minimum(workdir: Path) -> None:
    """After hacs.json moves up, a custom pinned below it is pointed out without the network."""
    assert _custom(workdir, "HA_ENVS_CUSTOM_VERSION=2026.11.1 ha_envs_refresh custom").returncode == 0
    (workdir / "hacs.json").write_text('{"homeassistant": "2026.12.0"}\n', encoding="utf-8")

    result = _bash(workdir, "ha_envs_notice")

    assert "custom holds Home Assistant 2026.11.1, older than 2026.12.0" in result.stdout


@pytest.mark.unit
def test_full_reset_of_another_environment_leaves_the_shared_configuration(workdir: Path) -> None:
    """configuration.yaml belongs to config/; resetting beta's directory never restores or removes it there."""
    _config(workdir, "2026.11.2")
    _copy_scripts(workdir, "setup/reset")
    (workdir / "script" / "setup" / "setup").write_text("#!/bin/bash\n", encoding="utf-8")
    (workdir / "script" / "setup" / "setup").chmod(0o755)
    assert _bash(workdir, "ha_envs_refresh beta; ha_envs_use beta").returncode == 0

    missing = _run_script(workdir, "setup/reset", "--full", "--yes")
    assert _bash(workdir, f"ha_envs_prepare_config {workdir}/.local/ha-config/beta 2026.12.0b1").returncode == 0
    full = _run_script(workdir, "setup/reset", "--full", "--yes")

    assert missing.returncode == 0, missing.stderr
    assert "does not exist yet" in missing.stdout
    assert full.returncode == 0, full.stderr
    assert not any((workdir / ".local" / "ha-config" / "beta").iterdir())
    assert (workdir / "config" / "configuration.yaml").read_text(encoding="utf-8") == "default_config:\n"


@pytest.mark.unit
def test_versions_compare_with_a_two_part_minimum_and_a_nightly(workdir: Path) -> None:
    """A hacs.json minimum like 2026.12 still floors custom, and a nightly sorts before its alpha."""
    script = """
for pair in "2026.12 2026.11.4" "2026.11.4 2026.12" "2026.12.0a1 2026.12.0.dev20261120"; do
    set -- $pair
    ha_version_newer "$1" "$2" && echo yes || echo no
done
ha_version_is_prerelease 2026.12.0.dev20261120 && echo nightly-pre
"""
    result = _bash(workdir, script)

    assert result.stdout.splitlines() == ["yes", "no", "yes", "nightly-pre"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pin", "named"),
    [
        ("2026.11.2.post1", "2026.11.2"),
        ("2026.11.2.dev1", "2026.11.2"),
        ("2026.12.0.dev20261120", "2026.12.0.dev20261120"),
    ],
)
def test_the_test_pin_keeps_a_nightly_and_drops_a_repackaging(workdir: Path, pin: str, named: str) -> None:
    """A short .devN is the plugin's own; Home Assistant's nightly .dev carries a date and stays a pre-release."""
    (workdir / "requirements_test.txt").write_text(f"pytest-homeassistant=={pin}\n", encoding="utf-8")

    assert _bash(workdir, "ha_test_pin_version").stdout == f"{named}\n"
