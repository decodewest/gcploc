#!/usr/bin/env python3
"""gcploc CLI for managing local GCP emulators and control panel."""

import json
import os
import re
import signal
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

import click

EMULATOR_TARGETS = {"pubsub", "gcs", "cloudtasks"}
VALID_TARGETS = EMULATOR_TARGETS | {"services", "cp"}
TARGET_TO_COMPOSE_SERVICES = {
    "pubsub": ["pubsub"],
    "gcs": ["fakegcs"],
    "cloudtasks": ["cloudtasks"],
}
TARGET_TO_HOST_PORT = {
    "pubsub": int(os.getenv("GCPLOC_PUBSUB_HOST_PORT", "8085")),
    "gcs": int(os.getenv("GCPLOC_GCS_HOST_PORT", "4443")),
    "cloudtasks": int(os.getenv("GCPLOC_CLOUDTASKS_HOST_PORT", "8123")),
}

GCPLOC_CP_URL = os.getenv("GCPLOC_CP_URL", "http://localhost:5173")

COMPOSE_ROOT = Path(__file__).parent.parent.resolve()
CONTROL_PANEL_DIR = COMPOSE_ROOT / "control-panel"
CP_BACKEND_PATH = CONTROL_PANEL_DIR / "backend" / "server.py"
DEFAULT_ALIASES_FILE = COMPOSE_ROOT / ".gcploc.aliases.toml"
CP_STATE_FILE = COMPOSE_ROOT / ".gcploc.cp.state.json"


def _load_aliases() -> dict[str, list[str]]:
    aliases_file = Path(os.getenv("GCPLOC_ALIASES_FILE", str(DEFAULT_ALIASES_FILE)))
    if not aliases_file.exists():
        return {}

    with aliases_file.open("rb") as f:
        raw = tomllib.load(f)

    aliases = raw.get("aliases", {})
    if not isinstance(aliases, dict):
        raise click.ClickException("Invalid aliases config: 'aliases' must be a table.")

    normalized: dict[str, list[str]] = {}
    for name, targets in aliases.items():
        if not isinstance(name, str) or not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
            raise click.ClickException("Invalid aliases config: each alias must map to a list of string targets.")
        normalized[name.strip().lower()] = [t.strip().lower() for t in targets]
    return normalized


def _resolve_targets(requested: tuple[str, ...]) -> list[str]:
    aliases = _load_aliases()
    resolved: list[str] = []

    for target in requested:
        key = target.strip().lower()
        expanded = aliases.get(key, [key])
        resolved.extend(expanded)

    unknown = sorted({target for target in resolved if target not in VALID_TARGETS})
    if unknown:
        raise click.UsageError(
            f"Unknown target(s): {', '.join(unknown)}. "
            f"Valid targets: {', '.join(sorted(VALID_TARGETS))}."
        )

    return sorted(set(resolved))


def _expand_emulator_targets(targets: list[str]) -> list[str]:
    expanded: set[str] = set()
    for target in targets:
        if target == "services":
            expanded.update(EMULATOR_TARGETS)
        elif target in EMULATOR_TARGETS:
            expanded.add(target)
    return sorted(expanded)


def _run_compose(args: list[str], profiles: list[str] | None = None, **kwargs):
    env = None
    if profiles:
        env = os.environ.copy()
        env["COMPOSE_PROFILES"] = ",".join(sorted(set(profiles)))

    cmd = ["docker", "compose", *args]
    click.echo(f"[gcploc] {' '.join(cmd)}" + (f"  (profiles: {env['COMPOSE_PROFILES']})" if env else ""))

    result = subprocess.run(cmd, cwd=COMPOSE_ROOT, env=env, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _ensure_network():
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", "name=gcploc_net", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
    )
    if "gcploc_net" not in result.stdout:
        click.echo("[gcploc] Creating Docker network: gcploc_net")
        subprocess.run(["docker", "network", "create", "gcploc_net"], check=True)
    else:
        click.echo("[gcploc] Network gcploc_net already exists.")


def _url_reachable(url: str, timeout: float = 1.5) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _cp_state() -> dict:
    if not CP_STATE_FILE.exists():
        return {}
    try:
        return json.loads(CP_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cp_state(state: dict):
    CP_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _cp_running() -> bool:
    state = _cp_state()
    backend_pid = int(state.get("backend_pid", 0))
    frontend_pid = int(state.get("frontend_pid", 0))
    return _pid_running(backend_pid) or _pid_running(frontend_pid)


def _start_control_panel():
    if not CONTROL_PANEL_DIR.exists():
        raise click.ClickException("control-panel directory not found.")
    if not CP_BACKEND_PATH.exists():
        raise click.ClickException("control-panel backend server not found.")

    if _cp_running() or _url_reachable(GCPLOC_CP_URL):
        click.echo(f"[gcploc] Control panel already running at {GCPLOC_CP_URL}")
        return

    node_modules = CONTROL_PANEL_DIR / "node_modules"
    if not node_modules.exists():
        click.echo("[gcploc] Installing control panel dependencies...")
        install_result = subprocess.run(["npm", "install"], cwd=CONTROL_PANEL_DIR)
        if install_result.returncode != 0:
            raise click.ClickException("Failed to install control panel dependencies.")

    click.echo("[gcploc] Starting control panel backend...")
    backend_proc = subprocess.Popen(
        [sys.executable, str(CP_BACKEND_PATH)],
        cwd=COMPOSE_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    click.echo("[gcploc] Starting control panel frontend...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=CONTROL_PANEL_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    _save_cp_state(
        {
            "backend_pid": backend_proc.pid,
            "frontend_pid": frontend_proc.pid,
            "started_at": int(time.time()),
            "url": GCPLOC_CP_URL,
        }
    )

    click.echo(f"[gcploc] Control panel launch initiated: {GCPLOC_CP_URL}")
    if not _url_reachable(GCPLOC_CP_URL):
        click.echo("[gcploc] Control panel may take a few seconds to become reachable.")


def _stop_pid(pid: int):
    if not _pid_running(pid):
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(10):
        if not _pid_running(pid):
            return
        time.sleep(0.2)
    if _pid_running(pid):
        os.kill(pid, signal.SIGKILL)


def _stop_control_panel():
    state = _cp_state()
    backend_pid = int(state.get("backend_pid", 0))
    frontend_pid = int(state.get("frontend_pid", 0))

    if not _pid_running(backend_pid) and not _pid_running(frontend_pid):
        click.echo("[gcploc] Control panel is already stopped.")
        if CP_STATE_FILE.exists():
            CP_STATE_FILE.unlink(missing_ok=True)
        return

    click.echo("[gcploc] Stopping control panel...")
    if _pid_running(frontend_pid):
        _stop_pid(frontend_pid)
    if _pid_running(backend_pid):
        _stop_pid(backend_pid)

    CP_STATE_FILE.unlink(missing_ok=True)
    click.echo("[gcploc] Control panel stopped.")


def _get_running_port_owners() -> dict[int, list[str]]:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}

    owners: dict[int, list[str]] = {}
    port_pattern = re.compile(r":(\d+)->")
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        name, ports = parts[0].strip(), parts[1]
        for match in port_pattern.finditer(ports):
            host_port = int(match.group(1))
            owners.setdefault(host_port, []).append(name)
    return owners


def _ensure_required_ports_available(targets: list[str]):
    running_owners = _get_running_port_owners()
    gcploc_owned = _get_gcploc_container_names()
    conflicts: list[str] = []

    for target in targets:
        required_port = TARGET_TO_HOST_PORT.get(target)
        if required_port is None:
            continue
        owners = [name for name in running_owners.get(required_port, []) if name not in gcploc_owned]
        if owners:
            owner_list = ", ".join(sorted(set(owners)))
            conflicts.append(f"- {target} needs host port {required_port}, currently used by: {owner_list}")

    if conflicts:
        details = "\n".join(conflicts)
        raise click.ClickException(
            "Host port conflict detected before startup:\n"
            f"{details}\n"
            "Stop those containers, or set alternate ports in env (GCPLOC_PUBSUB_HOST_PORT, "
            "GCPLOC_GCS_HOST_PORT, GCPLOC_CLOUDTASKS_HOST_PORT) and retry."
        )


def _get_network_attached_container_names(network_name: str) -> set[str]:
    result = subprocess.run(
        ["docker", "network", "inspect", network_name, "--format", "{{json .Containers}}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()

    raw = result.stdout.strip()
    if not raw or raw == "null":
        return set()

    try:
        containers = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if not isinstance(containers, dict):
        return set()

    names: set[str] = set()
    for value in containers.values():
        if isinstance(value, dict):
            name = value.get("Name")
            if isinstance(name, str) and name:
                names.add(name)
    return names


def _get_gcploc_container_names() -> set[str]:
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=gcploc", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _has_gcploc_containers() -> bool:
    return bool(_get_gcploc_container_names())


def _has_running_emulator_containers() -> bool:
    result = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.project=gcploc",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return any(name in names for name in ["gcploc_pubsub", "gcploc_fakegcs", "gcploc_cloudtasks"])


def _find_non_gcploc_dependents() -> list[str]:
    attached = _get_network_attached_container_names("gcploc_net")
    if not attached:
        return []
    owned = _get_gcploc_container_names()
    return sorted(name for name in attached if name not in owned)


def _confirm_safe_stop(force: bool, targets: list[str], full_down: bool):
    dependents = _find_non_gcploc_dependents()
    if not dependents or force:
        return

    click.echo("[gcploc] Warning: containers currently attached to gcploc_net were detected:", err=True)
    for name in dependents:
        click.echo(f"  - {name}", err=True)

    action = "stop emulator services" if full_down else f"stop selected targets: {', '.join(targets)}"
    click.confirm(f"Proceed and {action}?", abort=True)


@click.group()
def cli():
    """Manage local GCP emulators and control panel."""


@cli.command()
@click.argument("targets", nargs=-1, required=True)
def start(targets: tuple[str, ...]):
    """Start emulator services and/or control panel.

    Targets: services, pubsub, gcs, cloudtasks, cp

    Examples:
        gcploc start services
        gcploc start gcs
        gcploc start cp
        gcploc start services cp
    """
    resolved = _resolve_targets(targets)
    cp_requested = "cp" in resolved
    emulator_targets = _expand_emulator_targets([t for t in resolved if t != "cp"])

    if emulator_targets:
        _ensure_required_ports_available(emulator_targets)
        _ensure_network()
        _run_compose(["up", "-d", "--wait"], profiles=emulator_targets)
        click.echo(f"[gcploc] Emulators started for: {', '.join(emulator_targets)}")
        if not cp_requested:
            click.echo(f"[gcploc] Control panel URL: {GCPLOC_CP_URL}")
            click.echo("[gcploc] Start control panel with: gcploc start cp")

    if cp_requested:
        _start_control_panel()
        if not _has_running_emulator_containers():
            click.echo("[gcploc] Control panel started, but no emulator services are currently running.")


@cli.command()
@click.argument("targets", nargs=-1, required=False)
@click.option("--force", is_flag=True, help="Skip dependency confirmation checks.")
def stop(targets: tuple[str, ...], force: bool):
    """Stop emulator services and/or control panel.

    Examples:
        gcploc stop                # stop services + control panel
        gcploc stop services       # stop all emulators only
        gcploc stop gcs            # stop selected emulator
        gcploc stop cp             # stop control panel only
    """
    if not targets:
        has_any = _has_gcploc_containers() or _cp_running()
        if not has_any:
            click.echo("[gcploc] No gcploc services or control panel found; everything is already stopped.")
            return

        if _has_gcploc_containers():
            _confirm_safe_stop(force=force, targets=["services"], full_down=True)
            _run_compose(["down"], profiles=["all"])
        _stop_control_panel()
        return

    resolved = _resolve_targets(targets)
    cp_requested = "cp" in resolved
    emulator_targets = _expand_emulator_targets([t for t in resolved if t != "cp"])

    if emulator_targets:
        _confirm_safe_stop(force=force, targets=emulator_targets, full_down=len(emulator_targets) == len(EMULATOR_TARGETS))
        if len(emulator_targets) == len(EMULATOR_TARGETS):
            if not _has_gcploc_containers():
                click.echo("[gcploc] No emulator containers found; emulator services already stopped.")
            else:
                _run_compose(["down"], profiles=["all"])
        else:
            services_to_stop: list[str] = []
            for target in emulator_targets:
                services_to_stop.extend(TARGET_TO_COMPOSE_SERVICES.get(target, []))
            services_to_stop = sorted(set(services_to_stop))
            if services_to_stop:
                _run_compose(["stop", *services_to_stop])

    if cp_requested:
        _stop_control_panel()


@cli.command()
def status():
    """Show running status for emulator services only."""
    _run_compose(["ps", "pubsub", "fakegcs", "cloudtasks"])


@cli.command("ports")
def ports_cmd():
    """Show required emulator host ports and current container owners."""
    running_owners = _get_running_port_owners()
    gcploc_owned = _get_gcploc_container_names()

    click.echo("[gcploc] Port ownership overview")
    for target in sorted(TARGET_TO_HOST_PORT):
        port = TARGET_TO_HOST_PORT[target]
        owners = sorted(set(running_owners.get(port, [])))
        if not owners:
            click.echo(f"- {target}: {port} (free)")
            continue

        owned_markers = [f"{name}{' (gcploc)' if name in gcploc_owned else ''}" for name in owners]
        click.echo(f"- {target}: {port} (in use by: {', '.join(owned_markers)})")


@cli.command()
@click.argument("service", required=False)
@click.option("-f", "--follow", is_flag=True, help="Follow log output.")
@click.option("-n", "--tail", default="50", help="Number of lines to show from the end.")
def logs(service: str | None, follow: bool, tail: str):
    """Show logs for emulator services.

    SERVICE: pubsub, fakegcs, cloudtasks (optional; shows all if omitted)
    """
    args = ["logs", f"--tail={tail}"]
    if follow:
        args.append("-f")
    if service:
        args.append(service)
    _run_compose(args)


@cli.command()
def doctor():
    """Check Docker, network, and emulator health."""
    click.echo("[gcploc] Checking Docker daemon...")
    result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True)
    if result.returncode != 0:
        click.echo("[gcploc] ERROR: Docker is not running.", err=True)
        sys.exit(1)
    click.echo(f"[gcploc] Docker OK (version {result.stdout.strip()})")

    click.echo("[gcploc] Checking gcploc_net network...")
    net_result = subprocess.run(
        ["docker", "network", "ls", "--filter", "name=gcploc_net", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
    )
    if "gcploc_net" in net_result.stdout:
        click.echo("[gcploc] gcploc_net: EXISTS")
    else:
        click.echo("[gcploc] gcploc_net: NOT FOUND (run: gcploc start services)")

    click.echo("[gcploc] Checking containers...")
    containers = {
        "gcploc_pubsub": 8085,
        "gcploc_fakegcs": 4443,
        "gcploc_cloudtasks": 8123,
    }
    ps_result = subprocess.run(
        ["docker", "ps", "--filter", "label=com.docker.compose.project=gcploc", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True,
    )
    running = ps_result.stdout.strip()
    for name, port in containers.items():
        if name in running:
            click.echo(f"[gcploc] {name} (:{port}): RUNNING")
        else:
            click.echo(f"[gcploc] {name} (:{port}): NOT RUNNING")

    if _cp_running():
        click.echo(f"[gcploc] Control panel process: RUNNING ({GCPLOC_CP_URL})")
    else:
        click.echo("[gcploc] Control panel process: NOT RUNNING")

    click.echo("[gcploc] Doctor check complete.")


if __name__ == "__main__":
    cli()
