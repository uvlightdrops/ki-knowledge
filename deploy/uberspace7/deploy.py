#!/usr/bin/env python3
"""U7 deployment preparation; lifecycle operations always delegate to stackctl."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ki_knowledge.app_config import AppConfig

ROOT = Path(__file__).resolve().parents[2]
STAGE = "prod-uberspace7"
WEB_ROOT = Path("/var/www/virtual") / getpass.getuser()


class DeploymentError(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path = ROOT, capture: bool = False,
        env: dict[str, str] | None = None, timeout: int = 300,
        pass_fds: tuple[int, ...] = ()) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=capture,
                            timeout=timeout, pass_fds=pass_fds)
    if result.returncode:
        # Captured output may contain connection strings; do not echo it.
        raise DeploymentError(f"{Path(command[0]).name} failed (exit {result.returncode}).")
    return result.stdout.strip() if capture else ""


def stackctl(*args: str, capture: bool = False) -> str:
    return run([sys.executable, "-m", "stackctl", *args], capture=capture)


def absolute_path(value: str, name: str) -> Path:
    if not value or not Path(value).expanduser().is_absolute():
        raise DeploymentError(f"{name} must be an explicit absolute path.")
    return Path(value).expanduser().resolve()


def validate_domain(domain: str) -> str:
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if not re.fullmatch(rf"(?=.{{1,253}}$){label}(?:\.{label})+", domain):
        raise DeploymentError("Set a lowercase DNS domain without scheme, path or wildcards.")
    if domain.endswith(".example.org") or domain.endswith(".example.com"):
        raise DeploymentError("Replace the example domain first.")
    return domain


@dataclass(frozen=True)
class Deployment:
    domain: str
    document_root: Path
    data_root: Path
    backup_root: Path
    dsn: str
    port: int


def configuration() -> tuple[Deployment, AppConfig]:
    from django.conf import settings
    from ki_knowledge.app_config import AppConfig
    from ki_knowledge.config_runtime import knowledge_data_root
    from stackctl.spec import build_stack

    cfg = AppConfig.from_env()
    options = cfg.raw.get_path("apps.ki_knowledge.uberspace7", {}) or {}
    domain = validate_domain(options.get("domain", ""))
    document = absolute_path(options.get("document_root", ""), "document_root")
    data = absolute_path(cfg.knowledge_data_root, "knowledge.data_root")
    backup = absolute_path(options.get("backup_root", ""), "backup_root")
    if not document.is_relative_to(WEB_ROOT.resolve()) or document == WEB_ROOT.resolve():
        raise DeploymentError("document_root must be inside this account's /var/www/virtual directory.")
    if not document.is_dir():
        raise DeploymentError("Create/verify the domain DocumentRoot before deployment.")
    home = Path.home().resolve()
    for path in (data, backup):
        if not path.is_relative_to(home) or path == home:
            raise DeploymentError("Data and backups must use dedicated directories inside the private home.")
        if path.is_relative_to(ROOT) or ROOT.is_relative_to(path) or path.is_relative_to(document):
            raise DeploymentError("Data/backups must be separate from checkout and public DocumentRoot.")
    if data.is_relative_to(backup) or backup.is_relative_to(data):
        raise DeploymentError("Data and backup directories must not contain each other.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
    if settings.DEBUG or "*" in settings.ALLOWED_HOSTS or domain not in settings.ALLOWED_HOSTS:
        raise DeploymentError("Django needs debug=false and explicit allowed_hosts including domain.")
    if len(settings.SECRET_KEY) < 50 or settings.SECRET_KEY.startswith("django-insecure"):
        raise DeploymentError("Configure a private, random Django secret_key of at least 50 characters.")
    if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
        raise DeploymentError("Secure session and CSRF cookies are required.")
    if not settings.SECURE_SSL_REDIRECT or settings.SECURE_HSTS_SECONDS < 3600:
        raise DeploymentError("HTTPS redirect and HSTS (at least 3600 seconds) are required.")
    if f"https://{domain}" not in settings.CSRF_TRUSTED_ORIGINS:
        raise DeploymentError("csrf_trusted_origins must include https://domain.")
    if settings.WAGTAILADMIN_BASE_URL.rstrip("/") != f"https://{domain}":
        raise DeploymentError("wagtail_admin_base_url must be the public https://domain.")
    if settings.SECURE_PROXY_SSL_HEADER != ("HTTP_X_FORWARDED_PROTO", "https"):
        raise DeploymentError("Verify U7 proxy headers and explicitly configure secure_proxy_ssl_header.")
    if Path(settings.STATIC_ROOT).resolve() != document / "static":
        raise DeploymentError("static_root must equal document_root/static.")
    if not settings.MEDIA_ROOT or not Path(settings.MEDIA_ROOT).resolve().is_relative_to(data):
        raise DeploymentError("media_root must be private and inside knowledge.data_root.")
    if knowledge_data_root(cfg).resolve() != data:
        raise DeploymentError("Conflicting data-root overrides.")
    if settings.KNOWLEDGE_STORE_TARGET.kind != "postgres" or not settings.POSTGRES_DSN:
        raise DeploymentError("This U7 deployment requires PostgreSQL for Django and KnowledgeStore.")
    for path in (ROOT / "creds.yaml", Path.home() / ".pgpass"):
        if path.exists() and path.stat().st_mode & 0o077:
            raise DeploymentError(f"{path.name} must have private permissions (0600).")
    stack = build_stack(cfg.raw["stack"], ROOT)
    if stack.target != "supervisord" or set(stack.services) != {"api", "django", "postgres", "ollama"}:
        raise DeploymentError("Expected the U7 supervisord stack with api/django/postgres/ollama.")
    for name in ("postgres", "ollama"):
        if stack.service(name).kind != "external":
            raise DeploymentError(f"{name} must remain external; no cluster/model management here.")
    for name in ("api", "django"):
        service = stack.service(name)
        if service.env.get("KI_STAGE") != STAGE or service.prepare or service.post_start:
            raise DeploymentError(f"{name}: explicit U7 stage and no automatic preparation hooks required.")
    if stack.service("api").host != "127.0.0.1" or stack.service("django").host != "0.0.0.0":
        raise DeploymentError("API must bind loopback, Django must bind 0.0.0.0.")
    if len({stack.service(name).port for name in stack.services}) != len(stack.services):
        raise DeploymentError("Services must use distinct ports.")
    if not 1024 <= stack.service("django").port <= 65535:
        raise DeploymentError("Django must use an unprivileged TCP port.")
    url = urlparse(cfg.ollama_base_url)
    ollama = stack.service("ollama")
    if (url.scheme, url.hostname, url.port or 80, url.path.rstrip("/")) != (
        "http", "127.0.0.1", ollama.port, ""
    ) or ollama.host != "127.0.0.1":
        raise DeploymentError("Use the configured loopback SSH tunnel for Ollama (same external port).")
    pg = urlparse(settings.POSTGRES_DSN)
    postgres = stack.service("postgres")
    if pg.hostname != postgres.host or (pg.port or 5432) != postgres.port:
        raise DeploymentError("PostgreSQL DSN must match the external stack service host/port.")
    return Deployment(domain, document, data, backup, settings.POSTGRES_DSN,
                      stack.service("django").port), cfg


def check_dependencies(deployment: Deployment, cfg: AppConfig) -> None:
    import psycopg
    import requests

    if importlib.util.find_spec("gunicorn") is None:
        raise DeploymentError("Gunicorn missing; rerun the U7 bootstrap with the uberspace7 extra.")
    for tool in ("supervisorctl", "pg_dump", "git", "uberspace"):
        if not shutil.which(tool):
            raise DeploymentError(f"Required host program missing: {tool}")
    try:
        with psycopg.connect(deployment.dsn, connect_timeout=10) as conn:
            if not conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone():
                raise DeploymentError("Activate pgvector administratively in the target database first.")
            if conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user").fetchone()[0]:
                raise DeploymentError("Use a non-superuser application role.")
            if conn.execute("SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector").fetchone()[0] != 0:
                raise DeploymentError("pgvector cosine-distance smoke test failed.")
    except psycopg.Error as exc:
        raise DeploymentError(f"PostgreSQL preflight failed ({type(exc).__name__}); check private credentials.") from None
    try:
        response = requests.get(f"{cfg.ollama_base_url.rstrip('/')}/api/tags", timeout=(5, 20))
        response.raise_for_status()
        models = {item["name"] for item in response.json()["models"]}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise DeploymentError("Ollama tunnel/model listing failed; check the external service.") from None
    required = {cfg.knowledge_embed_model}
    if cfg.llm_default_provider == "ollama":
        required.add(cfg.ollama_model)
    elif cfg.llm_default_provider not in {"ki", "openai"}:
        raise DeploymentError("Configure a real chat provider, not mock.")
    for model in required:
        if model not in models and f"{model}:latest" not in models:
            raise DeploymentError(f"Required model is not installed on the dedicated Ollama host: {model}")


@contextmanager
def locked():
    directory = ROOT / "var"
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / "uberspace7.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DeploymentError("Another U7 deployment is running.") from None
        yield handle.fileno()


def repositories() -> list[Path]:
    import stackctl as tool

    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
    source = Path(os.environ.get("STACKCTL_SRC_DIR", str(ROOT.parent))).expanduser().resolve()
    paths = [ROOT, Path(tool.__file__).resolve().parents[2]]
    for sibling in manifest["tool"]["stackctl"]["siblings"]:
        paths.append((source / sibling.get("path", sibling["name"])).resolve())
    return list(dict.fromkeys(paths))


def revisions(paths: list[Path], *, clean: bool = False) -> dict[str, str]:
    result = {}
    for path in paths:
        if clean:
            if run(["git", "status", "--porcelain"], cwd=path, capture=True):
                raise DeploymentError(f"Dirty checkout: {path.name}. No automatic stash or reset.")
            run(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd=path, capture=True)
        result[str(path)] = run(["git", "rev-parse", "HEAD"], cwd=path, capture=True)
    return result


def backup(deployment: Deployment) -> Path:
    import psycopg

    deployment.backup_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if deployment.backup_root.stat().st_mode & 0o077:
        raise DeploymentError("backup_root must have private permissions (0700).")
    target = deployment.backup_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target.mkdir(mode=0o700)
    # Keep passwords out of process arguments; libpq also honours existing .pgpass.
    parameters = psycopg.conninfo.conninfo_to_dict(deployment.dsn)
    names = {"host": "PGHOST", "port": "PGPORT", "dbname": "PGDATABASE",
             "user": "PGUSER", "password": "PGPASSWORD", "sslmode": "PGSSLMODE"}
    unknown = set(parameters) - set(names)
    if unknown:
        raise DeploymentError("Backup DSN has unsupported parameters; use host/port/dbname/user/sslmode.")
    env = dict(os.environ)
    env.update({names[key]: value for key, value in parameters.items()})
    env["PGCONNECT_TIMEOUT"] = "10"
    run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
         "--file", str(target / "postgres.dump")], env=env, capture=True, timeout=1800)
    with tarfile.open(target / "data.tar.gz", "w:gz", dereference=False) as archive:
        if deployment.data_root.exists():
            archive.add(deployment.data_root, arcname="data")
    manifest = {"stage": STAGE, "revisions": revisions(repositories()),
                "packages": run([sys.executable, "-m", "pip", "freeze"], capture=True),
                "note": "Symlinks retained, not followed. Back up external source trees separately."}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    config_backup = target / "config"
    config_backup.mkdir(mode=0o700)
    for path in (ROOT / "ki.yaml", ROOT / "creds.yaml", ROOT / "config/runtime/runtime.yaml"):
        if path.is_file():
            shutil.copyfile(path, config_backup / path.name)
    print(f"Backup: {target}", flush=True)
    return target


def django_check() -> None:
    import django
    from django.core.checks import WARNING, run_checks

    django.setup()
    # Do not impose HSTS on other subdomains or request browser preloading.
    accepted = {"security.W005", "security.W021"}
    blocked = []
    for issue in run_checks(include_deployment_checks=True):
        if issue.level >= WARNING:
            print(str(issue), file=sys.stderr)
            if issue.id not in accepted:
                blocked.append(issue.id)
    if blocked:
        raise DeploymentError("Django deploy checks failed: " + ", ".join(blocked))


def apply(deployment: Deployment) -> None:
    django_check()
    run([sys.executable, "manage.py", "migrate", "--no-input"], timeout=1800)
    # Exercise the canonical schema owner, including pgvector and app-role schema rights.
    run([sys.executable, "manage.py", "shell", "-c",
         "from ki_knowledge.integrations.knowledge_store import KnowledgeStore; "
         "from django.conf import settings; KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)"])
    run([sys.executable, "manage.py", "collectstatic", "--no-input"], timeout=600)
    stackctl("start")
    import requests

    try:
        response = requests.get(f"http://127.0.0.1:{deployment.port}/",
                                headers={"Host": deployment.domain, "X-Forwarded-Proto": "https"},
                                timeout=(5, 30), allow_redirects=False)
        if not 200 <= response.status_code < 400:
            raise DeploymentError(f"Django HTTP readiness failed (HTTP {response.status_code}).")
    except requests.RequestException:
        raise DeploymentError("Django HTTP readiness failed after start.") from None
    print("Application ready locally. Public routing and authenticated feature checks remain separate.")


def configure_web(deployment: Deployment, confirmed: str | None) -> None:
    run(["uberspace", "web", "backend", "list"])
    if confirmed != deployment.domain:
        raise DeploymentError("Review backends, then repeat web --confirm-domain DOMAIN to approve replacing these two paths.")
    run(["uberspace", "web", "backend", "set", f"{deployment.domain}/",
         "--http", "--port", str(deployment.port)])
    run(["uberspace", "web", "backend", "set", f"{deployment.domain}/static", "--apache"])
    run(["uberspace", "web", "backend", "list"])


def main(argv: list[str] | None = None) -> int:
    from django.core.exceptions import ImproperlyConfigured
    from stackctl.spec import SpecError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "apply", "backup", "update", "web"))
    parser.add_argument("--confirm-domain")
    args = parser.parse_args(argv)
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        parser.error("Use this checkout's .venv/bin/python.")
    os.chdir(ROOT)
    if os.environ.get("KI_STAGE", STAGE) != STAGE:
        parser.error("Conflicting KI_STAGE; use prod-uberspace7.")
    transient = [name for name in os.environ if (
        name.startswith(("KI_CFG_", "DJANGO_", "KNOWLEDGE_"))
        or name in {"KI_KNOWLEDGE_POSTGRES_DSN", "KI_KNOWLEDGE_STORE_BACKEND", "KI_PROFILE"}
    ) and name != "DJANGO_SETTINGS_MODULE"]
    if transient:
        parser.error("Remove process-only config overrides; persist them in runtime/creds first: "
                     + ", ".join(sorted(transient)))
    if os.environ.get("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings") != "ki_knowledge.django_site.settings":
        parser.error("Use ki_knowledge.django_site.settings.")
    os.environ["KI_STAGE"] = STAGE
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
    os.umask(0o077)
    try:
        with locked() as lock_fd:
            deployment, cfg = configuration()
            check_dependencies(deployment, cfg)
            if args.action == "check":
                django_check()
                print("U7 configuration, PostgreSQL/pgvector and Ollama preflight passed.")
            elif args.action == "web":
                configure_web(deployment, args.confirm_domain)
            else:
                paths = repositories()
                if args.action == "update":
                    revisions(paths, clean=True)
                stackctl("stop", "django", "api")
                saved = backup(deployment)
                if args.action == "backup":
                    print("Writers remain stopped. Restart explicitly with stackctl start.")
                    return 0
                if args.action == "update":
                    before = {path: hashlib.sha256((path / "pyproject.toml").read_bytes()).digest()
                              for path in paths}
                    for path in paths:
                        run(["git", "pull", "--ff-only"], cwd=path, capture=True, timeout=180)
                    if any(hashlib.sha256((path / "pyproject.toml").read_bytes()).digest() != before[path]
                           for path in paths):
                        run([sys.executable, "-m", "pip", "install", "-e", str(paths[1])])
                        run([sys.executable, "-m", "stackctl", "install"],
                            env=dict(os.environ, STACKCTL_EXTRAS="uberspace7"), timeout=1800)
                    run([sys.executable, "-m", "pip", "check"])
                    # Execute the updated deployment code, keeping the parent lock held.
                    run([sys.executable, str(Path(__file__)), "_apply_after_update"],
                        timeout=1800, env=dict(os.environ, KI_U7_LOCK_FD=str(lock_fd)),
                        pass_fds=(lock_fd,))
                else:
                    apply(deployment)
                print(f"Deployment finished. Restore point: {saved}")
    except (DeploymentError, ImproperlyConfigured, SpecError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"deploy: {exc}\nNo automatic rollback. Check state; writers may remain stopped.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # Private child mode is only used while the parent update process owns the lock.
    if sys.argv[1:] == ["_apply_after_update"]:
        try:
            fd = int(os.environ.pop("KI_U7_LOCK_FD", "-1"))
            if os.fstat(fd).st_ino != (ROOT / "var/uberspace7.lock").stat().st_ino:
                raise DeploymentError("Update child needs the inherited deployment lock.")
            os.chdir(ROOT)
            os.environ["KI_STAGE"] = STAGE
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
            deployment, cfg = configuration()
            check_dependencies(deployment, cfg)
            apply(deployment)
        except (DeploymentError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            print(f"deploy: update apply failed ({type(exc).__name__}); writers may remain stopped.",
                  file=sys.stderr)
            raise SystemExit(1)
    else:
        raise SystemExit(main())
