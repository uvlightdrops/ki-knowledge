"""Shared rootless Uberspace deployment workflow."""
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


class DeploymentError(RuntimeError):
    pass


@dataclass(frozen=True)
class Deployment:
    domain: str
    document_root: Path
    data_root: Path
    backup_root: Path
    dsn: str
    port: int
    exclude_provider_postgis: bool = False


class UberspaceDeployment:
    def __init__(self, root: Path, version: int):
        if version not in (7, 8):
            raise ValueError("Supported Uberspace versions: 7, 8.")
        self.ROOT = root.resolve()
        self.version = version
        self.name = f"uberspace{version}"
        self.STAGE = f"prod-{self.name}"
        self.label = f"U{version}"
        self.target = "supervisord" if version == 7 else "systemd-user"
        self.WEB_ROOT = Path("/var/www/virtual") / getpass.getuser()

    def run(self, command: list[str], *, cwd: Path | None = None, capture: bool = False,
            env: dict[str, str] | None = None, timeout: int = 300,
            pass_fds: tuple[int, ...] = ()) -> str:
        result = subprocess.run(command, cwd=cwd or self.ROOT, env=env, text=True,
                                capture_output=capture, timeout=timeout, pass_fds=pass_fds)
        if result.returncode:
            # Captured output may contain connection strings; do not echo it.
            raise DeploymentError(f"{Path(command[0]).name} failed (exit {result.returncode}).")
        return result.stdout.strip() if capture else ""

    def stackctl(self, *args: str, capture: bool = False) -> str:
        return self.run([sys.executable, "-m", "stackctl", *args], capture=capture)

    @staticmethod
    def absolute_path(value: str, name: str) -> Path:
        if not value or not Path(value).expanduser().is_absolute():
            raise DeploymentError(f"{name} must be an explicit absolute path.")
        return Path(value).expanduser().resolve()

    @staticmethod
    def validate_domain(domain: str) -> str:
        label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        if not re.fullmatch(rf"(?=.{{1,253}}$){label}(?:\.{label})+", domain):
            raise DeploymentError("Set a lowercase DNS domain without scheme, path or wildcards.")
        if domain.endswith(".example.org") or domain.endswith(".example.com"):
            raise DeploymentError("Replace the example domain first.")
        return domain

    def configuration(self) -> tuple[Deployment, AppConfig]:
        from django.conf import settings
        from ki_knowledge.app_config import AppConfig
        from ki_knowledge.config_runtime import knowledge_data_root
        from stackctl.spec import build_stack

        cfg = AppConfig.from_env()
        options = cfg.raw.get_path(f"apps.ki_knowledge.{self.name}", {}) or {}
        domain = self.validate_domain(options.get("domain", ""))
        document = self.absolute_path(options.get("document_root", ""), "document_root")
        data = self.absolute_path(cfg.knowledge_data_root, "knowledge.data_root")
        backup = self.absolute_path(options.get("backup_root", ""), "backup_root")
        if not document.is_relative_to(self.WEB_ROOT.resolve()) or document == self.WEB_ROOT.resolve():
            raise DeploymentError("document_root must be inside this account's /var/www/virtual directory.")
        if not document.is_dir():
            raise DeploymentError("Create/verify the domain DocumentRoot before deployment.")
        home = Path.home().resolve()
        for path in (data, backup):
            if not path.is_relative_to(home) or path == home:
                raise DeploymentError("Data and backups must use dedicated directories inside the private home.")
            if (path.is_relative_to(self.ROOT) or self.ROOT.is_relative_to(path)
                    or path.is_relative_to(document)):
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
            raise DeploymentError(f"Verify {self.label} proxy headers and explicitly configure secure_proxy_ssl_header.")
        if Path(settings.STATIC_ROOT).resolve() != document / "static":
            raise DeploymentError("static_root must equal document_root/static.")
        if not settings.MEDIA_ROOT or not Path(settings.MEDIA_ROOT).resolve().is_relative_to(data):
            raise DeploymentError("media_root must be private and inside knowledge.data_root.")
        if knowledge_data_root(cfg).resolve() != data:
            raise DeploymentError("Conflicting data-root overrides.")
        if settings.KNOWLEDGE_STORE_TARGET.kind != "postgres" or not settings.POSTGRES_DSN:
            raise DeploymentError(f"This {self.label} deployment requires PostgreSQL for Django and KnowledgeStore.")
        for path in (self.ROOT / "creds.yaml", Path.home() / ".pgpass"):
            if path.exists() and path.stat().st_mode & 0o077:
                raise DeploymentError(f"{path.name} must have private permissions (0600).")
        stack = build_stack(cfg.raw["stack"], self.ROOT)
        if stack.target != self.target or set(stack.services) != {"api", "django", "postgres", "ollama"}:
            raise DeploymentError(f"Expected the {self.label} {self.target} stack with api/django/postgres/ollama.")
        for name in ("postgres", "ollama"):
            if stack.service(name).kind != "external":
                raise DeploymentError(f"{name} must remain external; no cluster/model management here.")
        for name in ("api", "django"):
            service = stack.service(name)
            if service.env.get("KI_STAGE") != self.STAGE or service.prepare or service.post_start:
                raise DeploymentError(f"{name}: explicit {self.label} stage and no automatic preparation hooks required.")
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
        excluded = options.get("exclude_provider_postgis", False)
        if not isinstance(excluded, bool) or (excluded and self.version != 8):
            raise DeploymentError("exclude_provider_postgis is an explicit U8-only boolean.")
        return Deployment(domain, document, data, backup, settings.POSTGRES_DSN,
                          stack.service("django").port, excluded), cfg

    def check_dependencies(self, deployment: Deployment, cfg: AppConfig) -> None:
        import psycopg
        import requests

        if importlib.util.find_spec("gunicorn") is None:
            raise DeploymentError(f"Gunicorn missing; rerun the {self.label} bootstrap with the {self.name} extra.")
        manager_tools = ("supervisorctl",) if self.version == 7 else ("systemctl", "journalctl")
        for tool in (*manager_tools, "pg_dump", "git", "uberspace"):
            if not shutil.which(tool):
                raise DeploymentError(f"Required host program missing: {tool}")
        if self.version == 8:
            self.run(["systemctl", "--user", "show-environment"], capture=True, timeout=15)
        if deployment.exclude_provider_postgis:
            help_text = self.run(["pg_dump", "--help"], capture=True)
            if "--exclude-extension" not in help_text:
                raise DeploymentError("Provider PostGIS exclusion requires pg_dump with --exclude-extension support.")
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
    def locked(self):
        directory = self.ROOT / "var"
        directory.mkdir(mode=0o700, exist_ok=True)
        with (directory / "uberspace.lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DeploymentError("Another Uberspace deployment is running.") from None
            yield handle.fileno()

    def repositories(self) -> list[Path]:
        import stackctl as tool

        manifest = tomllib.loads((self.ROOT / "pyproject.toml").read_text())
        source = Path(os.environ.get("STACKCTL_SRC_DIR", str(self.ROOT.parent))).expanduser().resolve()
        paths = [self.ROOT, Path(tool.__file__).resolve().parents[2]]
        for sibling in manifest["tool"]["stackctl"]["siblings"]:
            paths.append((source / sibling.get("path", sibling["name"])).resolve())
        return list(dict.fromkeys(paths))

    def revisions(self, paths: list[Path], *, clean: bool = False) -> dict[str, str]:
        result = {}
        for path in paths:
            if clean:
                if self.run(["git", "status", "--porcelain"], cwd=path, capture=True):
                    raise DeploymentError(f"Dirty checkout: {path.name}. No automatic stash or reset.")
                self.run(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd=path, capture=True)
            result[str(path)] = self.run(["git", "rev-parse", "HEAD"], cwd=path, capture=True)
        return result

    def backup(self, deployment: Deployment) -> Path:
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
        if set(parameters) - set(names):
            raise DeploymentError("Backup DSN has unsupported parameters; use host/port/dbname/user/sslmode.")
        env = dict(os.environ)
        env.update({names[key]: value for key, value in parameters.items()})
        env["PGCONNECT_TIMEOUT"] = "10"
        exclusions = []
        if deployment.exclude_provider_postgis:
            exclusions = [
                "--exclude-table=public.spatial_ref_sys",
                "--exclude-schema=tiger", "--exclude-schema=tiger_data", "--exclude-schema=topology",
                "--exclude-extension=postgis", "--exclude-extension=postgis_topology",
                "--exclude-extension=postgis_tiger_geocoder", "--exclude-extension=fuzzystrmatch",
            ]
        self.run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
                  *exclusions, "--file", str(target / "postgres.dump")],
                 env=env, capture=True, timeout=1800)
        with tarfile.open(target / "data.tar.gz", "w:gz", dereference=False) as archive:
            if deployment.data_root.exists():
                archive.add(deployment.data_root, arcname="data")
        manifest = {
            "stage": self.STAGE, "revisions": self.revisions(self.repositories()),
            "packages": self.run([sys.executable, "-m", "pip", "freeze"], capture=True),
            "dump_exclusions": exclusions,
            "note": "Symlinks retained, not followed. Back up external source trees separately.",
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        config_backup = target / "config"
        config_backup.mkdir(mode=0o700)
        for path in (self.ROOT / "ki.yaml", self.ROOT / "creds.yaml",
                     self.ROOT / "config/runtime/runtime.yaml"):
            if path.is_file():
                shutil.copyfile(path, config_backup / path.name)
        print(f"Backup: {target}", flush=True)
        return target

    @staticmethod
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

    def apply(self, deployment: Deployment) -> None:
        self.django_check()
        self.run([sys.executable, "manage.py", "migrate", "--no-input"], timeout=1800)
        self.run([sys.executable, "manage.py", "shell", "-c",
                  "from ki_knowledge.integrations.knowledge_store import KnowledgeStore; "
                  "from django.conf import settings; KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)"])
        self.run([sys.executable, "manage.py", "collectstatic", "--no-input"], timeout=600)
        self.stackctl("start")
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

    def configure_web(self, deployment: Deployment, confirmed: str | None) -> None:
        self.run(["uberspace", "web", "backend", "list"])
        if confirmed != deployment.domain:
            raise DeploymentError("Review backends, then repeat web --confirm-domain DOMAIN to approve replacing these two paths.")
        if self.version == 7:
            self.run(["uberspace", "web", "backend", "set", f"{deployment.domain}/",
                      "--http", "--port", str(deployment.port)])
            self.run(["uberspace", "web", "backend", "set", f"{deployment.domain}/static", "--apache"])
        else:
            self.run(["uberspace", "web", "backend", "add", f"{deployment.domain}/",
                      "port", str(deployment.port), "--force"])
            self.run(["uberspace", "web", "backend", "add", f"{deployment.domain}/static",
                      "static", "--force"])
        self.run(["uberspace", "web", "backend", "list"])

    def apply_after_update(self) -> int:
        from django.core.exceptions import ImproperlyConfigured
        from stackctl.spec import SpecError

        try:
            fd = int(os.environ.pop("KI_UBERSPACE_LOCK_FD", "-1"))
            inherited = os.fstat(fd)
            expected = (self.ROOT / "var/uberspace.lock").stat()
            if (inherited.st_dev, inherited.st_ino) != (expected.st_dev, expected.st_ino):
                raise DeploymentError("Update child needs the inherited deployment lock.")
            os.chdir(self.ROOT)
            os.environ["KI_STAGE"] = self.STAGE
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
            deployment, cfg = self.configuration()
            self.check_dependencies(deployment, cfg)
            self.apply(deployment)
        except (DeploymentError, ImproperlyConfigured, SpecError, OSError, ValueError,
                subprocess.TimeoutExpired) as exc:
            print(f"deploy: update apply failed ({type(exc).__name__}); writers may remain stopped.",
                  file=sys.stderr)
            return 1
        return 0

    def main(self, argv: list[str] | None = None) -> int:
        from django.core.exceptions import ImproperlyConfigured
        from stackctl.spec import SpecError

        args_list = sys.argv[1:] if argv is None else argv
        if args_list == ["_apply_after_update"]:
            return self.apply_after_update()
        parser = argparse.ArgumentParser(description=f"{self.label} deployment via stackctl.")
        parser.add_argument("action", choices=("check", "apply", "backup", "update", "web"))
        parser.add_argument("--confirm-domain")
        args = parser.parse_args(args_list)
        if Path(sys.prefix).resolve() != (self.ROOT / ".venv").resolve():
            parser.error("Use this checkout's .venv/bin/python.")
        os.chdir(self.ROOT)
        if os.environ.get("KI_STAGE", self.STAGE) != self.STAGE:
            parser.error(f"Conflicting KI_STAGE; use {self.STAGE}.")
        transient = [name for name in os.environ if (
            name.startswith(("KI_CFG_", "DJANGO_", "KNOWLEDGE_"))
            or name in {"KI_KNOWLEDGE_POSTGRES_DSN", "KI_KNOWLEDGE_STORE_BACKEND", "KI_PROFILE"}
        ) and name != "DJANGO_SETTINGS_MODULE"]
        if transient:
            parser.error("Remove process-only config overrides; persist them in runtime/creds first: "
                         + ", ".join(sorted(transient)))
        if os.environ.get("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings") != "ki_knowledge.django_site.settings":
            parser.error("Use ki_knowledge.django_site.settings.")
        os.environ["KI_STAGE"] = self.STAGE
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
        os.umask(0o077)
        try:
            with self.locked() as lock_fd:
                deployment, cfg = self.configuration()
                self.check_dependencies(deployment, cfg)
                if args.action == "check":
                    self.django_check()
                    print(f"{self.label} configuration, PostgreSQL/pgvector and Ollama preflight passed.")
                elif args.action == "web":
                    self.configure_web(deployment, args.confirm_domain)
                else:
                    paths = self.repositories()
                    if args.action == "update":
                        self.revisions(paths, clean=True)
                    self.stackctl("stop", "django", "api")
                    saved = self.backup(deployment)
                    if args.action == "backup":
                        print(f"Writers remain stopped. Restart explicitly with KI_STAGE={self.STAGE} stackctl start.")
                        return 0
                    if args.action == "update":
                        before = {path: hashlib.sha256((path / "pyproject.toml").read_bytes()).digest()
                                  for path in paths}
                        for path in paths:
                            self.run(["git", "pull", "--ff-only"], cwd=path, capture=True, timeout=180)
                        if any(hashlib.sha256((path / "pyproject.toml").read_bytes()).digest() != before[path]
                               for path in paths):
                            self.run([sys.executable, "-m", "pip", "install", "-e", str(paths[1])])
                            self.run([sys.executable, "-m", "stackctl", "install"],
                                     env=dict(os.environ, STACKCTL_EXTRAS=self.name), timeout=1800)
                        self.run([sys.executable, "-m", "pip", "check"])
                        self.run([sys.executable, str(self.ROOT / f"deploy/{self.name}/deploy.py"),
                                  "_apply_after_update"], timeout=1800,
                                 env=dict(os.environ, KI_UBERSPACE_LOCK_FD=str(lock_fd)),
                                 pass_fds=(lock_fd,))
                    else:
                        self.apply(deployment)
                    print(f"Deployment finished. Restore point: {saved}")
        except (DeploymentError, ImproperlyConfigured, SpecError, OSError, subprocess.TimeoutExpired) as exc:
            print(f"deploy: {exc}\nNo automatic rollback. Check state; writers may remain stopped.",
                  file=sys.stderr)
            return 1
        return 0
