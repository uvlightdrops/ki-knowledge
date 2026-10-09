#!/usr/bin/env python
"""Start, stop and inspect the local ki-knowledge stack.

Services (in start order):
  postgres  Docker container from deploy/postgres (started with ``docker compose`` if down)
  ollama    only checked (embeddings, chat); runs as its own system service
  api       FastAPI knowledge API  (examples/run_knowledge_api.py, port 8090)
  django    Django/Wagtail UI      (manage.py migrate + runserver, port 8000)

Every service is first probed on its port; a running instance is left alone,
no matter who started it.  Processes started here run detached; PIDs go to
``var/run/<name>.pid`` and output to ``var/log/<name>.log``.

Hosts and ports come from ``deploy/stack.env`` (see ``stack.env.example``);
real environment variables win.  All entries are passed on to the services,
so Django settings like ``DJANGO_DEBUG`` can live there too.

    python deploy/devstack.py install          # sibling repos + this project into .venv
    python deploy/devstack.py status
    python deploy/devstack.py start            # everything
    python deploy/devstack.py start django
    python deploy/devstack.py stop             # api + django
    python deploy/devstack.py restart django
    python deploy/devstack.py logs django -f
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "var" / "run"
LOG_DIR = ROOT / "var" / "log"
STACK_ENV = ROOT / "deploy" / "stack.env"
PYTHON = sys.executable
START_TIMEOUT = 60
# Sibling repos (not on PyPI), in install order: directory name -> (git URL, branch for a fresh clone).
# Cloned next to this repo unless KI_SRC_DIR says otherwise; existing checkouts are used as they are.
SIBLINGS = {
    "yaml_cfg_wizard": ("https://github.com/uvlightdrops/yaml-cfg-wizard.git", "devel"),
    "ki-core": ("https://github.com/uvlightdrops/ki-core.git", "master"),
    "widgetkit-django": ("https://github.com/uvlightdrops/widgetkit-django.git", "devel"),
}


def load_stack_env(path: Path = STACK_ENV) -> None:
    """``KEY=value`` lines into ``os.environ`` (existing variables are kept)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_stack_env()


@dataclass(frozen=True)
class Service:
    name: str
    port: int
    host: str = "127.0.0.1"
    command: list[str] = field(default_factory=list)  # empty: not started by this script
    prepare: list[str] = field(default_factory=list)  # runs (blocking) before ``command``
    url: str = ""
    marker: str = ""  # command-line fragment identifying our own process

    @property
    def probe_host(self) -> str:
        return "127.0.0.1" if self.host in {"", "0.0.0.0", "::"} else self.host

    @property
    def pid_file(self) -> Path:
        return RUN_DIR / f"{self.name}.pid"

    @property
    def log_file(self) -> Path:
        return LOG_DIR / f"{self.name}.log"


DJANGO_HOST = os.getenv("KI_DJANGO_HOST", "127.0.0.1")
DJANGO_PORT = int(os.getenv("KI_DJANGO_PORT", "8000"))
API_HOST = os.environ.setdefault("KI_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.setdefault("KI_API_PORT", "8090"))
PG_HOST = os.getenv("KI_PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("KI_PG_PORT", "5432"))
OLLAMA_URL = os.getenv("KI_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
_ollama = urllib.parse.urlsplit(OLLAMA_URL)
_api_probe = "127.0.0.1" if API_HOST in {"", "0.0.0.0", "::"} else API_HOST
_django_probe = "127.0.0.1" if DJANGO_HOST in {"", "0.0.0.0", "::"} else DJANGO_HOST
os.environ.setdefault("KNOWLEDGE_API_URL", f"http://{_api_probe}:{API_PORT}/api/knowledge")

SERVICES = {
    service.name: service
    for service in (
        Service("postgres", PG_PORT, host=PG_HOST),
        Service("ollama", _ollama.port or 11434, host=_ollama.hostname or "127.0.0.1", url=f"{OLLAMA_URL}/api/tags"),
        Service(
            "api",
            API_PORT,
            host=API_HOST,
            command=[PYTHON, "examples/run_knowledge_api.py"],
            url=f"http://{_api_probe}:{API_PORT}/docs",
            marker="run_knowledge_api",
        ),
        Service(
            "django",
            DJANGO_PORT,
            host=DJANGO_HOST,
            # --insecure: serve static files also with DJANGO_DEBUG=false (runserver-only setup)
            command=[PYTHON, "manage.py", "runserver", "--insecure", f"{DJANGO_HOST}:{DJANGO_PORT}"],
            prepare=[PYTHON, "manage.py", "migrate", "--no-input"],
            url=f"http://{_django_probe}:{DJANGO_PORT}/",
            marker="manage.py runserver",
        ),
    )
}
MANAGED = [name for name, service in SERVICES.items() if service.command]


# --- probing -----------------------------------------------------------------------------


def port_open(service: Service, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((service.probe_host, service.port), timeout=timeout):
            return True
    except OSError:
        return False


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status < 500
    except Exception:
        return False


def listener_pid(port: int) -> int | None:
    """PID listening on ``port`` (via ``ss``; None if unknown or owned by another user)."""
    try:
        output = subprocess.run(
            ["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    marker = "pid="
    if marker not in output:
        return None
    return int(output.split(marker, 1)[1].split(",", 1)[0])


def cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode().strip()
    except OSError:
        return ""


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_pid(service: Service) -> int | None:
    try:
        pid = int(service.pid_file.read_text().strip())
    except (OSError, ValueError):
        return None
    if pid_alive(pid):
        return pid
    service.pid_file.unlink(missing_ok=True)
    return None


# --- actions -----------------------------------------------------------------------------


def status_line(service: Service) -> str:
    up = port_open(service)
    if service.name == "ollama" and up:
        up = http_ok(service.url)
    state = "läuft " if up else "gestoppt"
    detail = []
    pid = read_pid(service) or (listener_pid(service.port) if up else None)
    if pid:
        detail.append(f"PID {pid}")
        if read_pid(service) is None and service.command:
            detail.append("extern gestartet")
    if service.url and up:
        detail.append(service.url)
    return f"  {service.name:<9} {state}  :{service.port:<5} {'  '.join(detail)}"


def status(_names: list[str]) -> int:
    print("ki-knowledge Stack")
    for service in SERVICES.values():
        print(status_line(service))
    return 0


def start_postgres(service: Service) -> bool:
    compose_dir = ROOT / "deploy" / "postgres"
    if not (compose_dir / ".env").exists():
        print(f"  postgres: nicht erreichbar und {compose_dir / '.env'} fehlt – bitte manuell starten")
        return False
    print("  postgres: starte Container (docker compose up -d postgres) …")
    result = subprocess.run(["docker", "compose", "up", "-d", "postgres"], cwd=compose_dir)
    return result.returncode == 0 and wait_for_port(service)


def wait_for_port(service: Service, process: subprocess.Popen | None = None) -> bool:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if port_open(service):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.5)
    return False


def tail(path: Path, lines: int = 15) -> str:
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def start_service(service: Service) -> bool:
    if port_open(service):
        print(f"  {service.name}: läuft bereits (:{service.port})")
        return True
    if service.name == "postgres":
        return start_postgres(service)
    if not service.command:
        print(f"  {service.name}: nicht erreichbar (:{service.port}) – läuft als eigener Dienst, bitte dort starten")
        return False

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with service.log_file.open("a") as log:
        log.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} start {service.name} ===\n")
        log.flush()
        if service.prepare:
            print(f"  {service.name}: {' '.join(service.prepare[1:])} …")
            if subprocess.run(service.prepare, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode:
                print(f"  {service.name}: Vorbereitung fehlgeschlagen, siehe {service.log_file}")
                print(tail(service.log_file))
                return False
        process = subprocess.Popen(
            service.command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # detached: survives this script and the terminal
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    service.pid_file.write_text(str(process.pid))
    if wait_for_port(service, process):
        print(f"  {service.name}: gestartet (PID {process.pid}) {service.url}")
        return True
    print(f"  {service.name}: Start fehlgeschlagen, siehe {service.log_file}")
    print(tail(service.log_file))
    return False


def _terminate(pids: list[int]) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                if sig == signal.SIGTERM and os.getpgid(pid) == pid:
                    os.killpg(pid, sig)  # our own detached session incl. reloader children
                else:
                    os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(pid_alive(pid) for pid in pids):
            time.sleep(0.2)
        if not any(pid_alive(pid) for pid in pids):
            return


def stop_service(service: Service) -> bool:
    if not service.command:
        print(f"  {service.name}: wird nicht von hier gestoppt")
        return True
    pids = []
    own = read_pid(service)
    if own:
        pids.append(own)
    listener = listener_pid(service.port)
    if listener and listener not in pids:
        # Started by hand: only stop it if it is really our service from this project.
        if service.marker not in cmdline(listener) or Path(f"/proc/{listener}/cwd").resolve() != ROOT:
            print(f"  {service.name}: Port {service.port} gehört einem fremden Prozess (PID {listener}) – nicht gestoppt")
            return False
        pids.append(listener)
        parent = int(Path(f"/proc/{listener}/stat").read_text().rsplit(")", 1)[1].split()[1])
        if service.marker in cmdline(parent):
            pids.append(parent)  # autoreloader parent
    if not pids:
        print(f"  {service.name}: läuft nicht")
        return True
    _terminate(pids)
    service.pid_file.unlink(missing_ok=True)
    if port_open(service):
        print(f"  {service.name}: Port {service.port} ist noch belegt")
        return False
    print(f"  {service.name}: gestoppt")
    return True


def _selected(names: list[str], default: list[str]) -> list[Service]:
    unknown = [name for name in names if name not in SERVICES]
    if unknown:
        raise SystemExit(f"Unbekannter Dienst: {', '.join(unknown)} (verfügbar: {', '.join(SERVICES)})")
    return [SERVICES[name] for name in (names or default)]


def start(names: list[str]) -> int:
    ok = True
    for service in _selected(names, list(SERVICES)):
        ok = start_service(service) and ok
    return 0 if ok else 1


def stop(names: list[str]) -> int:
    ok = True
    for service in reversed(_selected(names, MANAGED)):
        ok = stop_service(service) and ok
    return 0 if ok else 1


def restart(names: list[str]) -> int:
    services = _selected(names, MANAGED)
    stopped = all([stop_service(service) for service in reversed(services)])
    if not stopped:
        return 1
    return 0 if all([start_service(service) for service in services]) else 1


def logs(names: list[str], follow: bool) -> int:
    services = _selected(names, MANAGED)
    files = [str(service.log_file) for service in services if service.log_file.exists()]
    if not files:
        print("Noch keine Logs (nur für hier gestartete Dienste).")
        return 1
    return subprocess.call(["tail", "-n", "40", *(["-F"] if follow else []), *files])


def install(_names: list[str]) -> int:
    """Install the sibling repos and this project editable into the running interpreter's venv."""
    if sys.prefix == sys.base_prefix:
        print("Bitte aus einer venv aufrufen (./kistack install legt .venv selbst an).")
        return 1
    src_dir = Path(os.getenv("KI_SRC_DIR", str(ROOT.parent))).expanduser()
    pip = [PYTHON, "-m", "pip", "install", "--quiet"]
    subprocess.run([*pip, "--upgrade", "pip"], check=False)
    for name, (url, branch) in SIBLINGS.items():
        path = src_dir / name
        if not path.is_dir():
            print(f"  {name}: klone {branch} nach {path}", flush=True)
            if subprocess.call(["git", "clone", "--quiet", "--branch", branch, url, str(path)]):
                return 1
        print(f"  {name}: pip install -e {path}", flush=True)
        if subprocess.call([*pip, "-e", str(path)]):
            return 1
    extras = os.getenv("KI_INSTALL_EXTRAS", "").strip()
    target = f"{ROOT}[{extras}]" if extras else str(ROOT)
    print(f"  ki-knowledge: pip install -e {target}", flush=True)
    return subprocess.call([*pip, "-e", target])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ki-knowledge: lokalen Stack installieren/starten/stoppen")
    parser.add_argument(
        "action", choices=["status", "start", "stop", "restart", "logs", "install"], nargs="?", default="status"
    )
    parser.add_argument("services", nargs="*", help=f"Dienste ({', '.join(SERVICES)}); Standard: alle")
    parser.add_argument("-f", "--follow", action="store_true", help="logs: fortlaufend anzeigen")
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    if args.action == "install":
        return install(args.services)
    if args.action == "logs":
        return logs(args.services, args.follow)
    code = {"status": status, "start": start, "stop": stop, "restart": restart}[args.action](args.services)
    if args.action != "status":
        print()
        status([])
    return code


if __name__ == "__main__":
    sys.exit(main())
