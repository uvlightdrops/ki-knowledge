from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml

from ki_knowledge.app_config import AppConfig, ConfigDict
from stackctl.spec import build_stack, deep_merge


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(f"u7_{name}", ROOT / f"deploy/uberspace7/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def deploy():
    return load_script("deploy")


@pytest.fixture
def configured(deploy, tmp_path, monkeypatch):
    home = tmp_path / "home"
    root = home / "src/project"
    root.mkdir(parents=True)
    web = tmp_path / "web/account"
    document = web / "knowledge.test.org"
    document.mkdir(parents=True)
    data = home / "data"
    monkeypatch.setattr(deploy, "ROOT", root)
    monkeypatch.setattr(deploy, "WEB_ROOT", web)
    monkeypatch.setattr(Path, "home", lambda: home)
    raw = yaml.safe_load((ROOT / "config/defaults/stack.yaml").read_text())
    stage = yaml.safe_load((ROOT / "config/stages/prod-uberspace7.yaml").read_text())
    merged = deep_merge(raw, stage)
    merged["knowledge"] = {"data_root": str(data)}
    merged["llm"]["providers"] = {"ollama": {"base_url": "http://127.0.0.1:11434"}}
    merged["apps"]["ki_knowledge"]["uberspace7"] = {
        "domain": "knowledge.test.org", "document_root": str(document),
        "backup_root": str(home / "backups"),
    }
    cfg = AppConfig(knowledge_data_root=str(data), ollama_base_url="http://127.0.0.1:11434",
                    raw=ConfigDict(merged))
    monkeypatch.setattr(AppConfig, "from_env", lambda: cfg)
    settings = SimpleNamespace(
        DEBUG=False, ALLOWED_HOSTS=["knowledge.test.org"], SECRET_KEY="random" * 12,
        SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
        SECURE_SSL_REDIRECT=True, SECURE_HSTS_SECONDS=3600,
        CSRF_TRUSTED_ORIGINS=["https://knowledge.test.org"],
        WAGTAILADMIN_BASE_URL="https://knowledge.test.org",
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        STATIC_ROOT=document / "static", MEDIA_ROOT=str(data / "media"),
        POSTGRES_DSN="postgresql://app@127.0.0.1:5432/knowledge",
        KNOWLEDGE_STORE_TARGET=SimpleNamespace(kind="postgres"),
    )
    monkeypatch.setattr("django.conf.settings", settings)
    return cfg, settings


def test_stage_has_no_docker_or_automatic_migration_hooks():
    raw = yaml.safe_load((ROOT / "config/defaults/stack.yaml").read_text())["stack"]
    stage = yaml.safe_load((ROOT / "config/stages/prod-uberspace7.yaml").read_text())["stack"]
    stack = build_stack(deep_merge(raw, stage), ROOT)
    assert stack.target == "supervisord"
    assert stack.service("postgres").kind == "external"
    assert stack.service("ollama").kind == "external"
    assert not stack.service("ollama").post_start
    assert not stack.service("django").prepare
    assert "gunicorn" in stack.service("django").command
    assert stack.service("django").host == "0.0.0.0"
    assert stack.service("api").host == "127.0.0.1"
    assert stack.service("api").env["UVICORN_RELOAD"] == "false"


def test_valid_configuration_uses_external_postgres_and_tunnel(deploy, configured):
    result, _ = deploy.configuration()
    assert result.domain == "knowledge.test.org"
    assert result.port == 8000


@pytest.mark.parametrize("domain,valid", [
    ("xn--bcher-kva.test.org", True),
    ("knowledge.test.org", True),
    ("bad-.test.org", False),
    ("bad..test.org", False),
    ("a" * 64 + ".test.org", False),
    ("https://knowledge.test.org", False),
])
def test_domain_validation_respects_dns_labels(deploy, domain, valid):
    if valid:
        assert deploy.validate_domain(domain) == domain
    else:
        with pytest.raises(deploy.DeploymentError):
            deploy.validate_domain(domain)


@pytest.mark.parametrize("setting,value", [
    ("DEBUG", True), ("ALLOWED_HOSTS", ["*"]), ("SECRET_KEY", "short"),
    ("SESSION_COOKIE_SECURE", False), ("CSRF_TRUSTED_ORIGINS", []),
    ("SECURE_PROXY_SSL_HEADER", None), ("SECURE_SSL_REDIRECT", False),
    ("STATIC_ROOT", "/home/private/static"), ("MEDIA_ROOT", "/var/www/media"),
    ("POSTGRES_DSN", "postgresql://app@elsewhere:5432/knowledge"),
    ("WAGTAILADMIN_BASE_URL", "http://localhost:8000"),
])
def test_rejects_unsafe_effective_settings(deploy, configured, setting, value):
    _, settings = configured
    setattr(settings, setting, value)
    with pytest.raises(deploy.DeploymentError):
        deploy.configuration()


def test_rejects_public_backups_and_nonprivate_credentials(deploy, configured):
    cfg, _ = configured
    options = cfg.raw["apps"]["ki_knowledge"]["uberspace7"]
    options["backup_root"] = options["document_root"]
    with pytest.raises(deploy.DeploymentError):
        deploy.configuration()
    options["backup_root"] = str(Path.home() / "backups")
    credentials = deploy.ROOT / "creds.yaml"
    credentials.write_text("{}")
    credentials.chmod(0o644)
    with pytest.raises(deploy.DeploymentError, match="0600"):
        deploy.configuration()


def test_lock_rejects_concurrent_deploy(deploy, tmp_path, monkeypatch):
    monkeypatch.setattr(deploy, "ROOT", tmp_path)
    with deploy.locked():
        with pytest.raises(deploy.DeploymentError, match="Another"):
            with deploy.locked():
                pytest.fail("Second lock acquired")


def test_web_requires_explicit_domain_confirmation(deploy, configured, monkeypatch):
    deployment, _ = deploy.configuration()
    calls = []
    monkeypatch.setattr(deploy, "run", lambda command, **kwargs: calls.append(command))
    with pytest.raises(deploy.DeploymentError, match="confirm-domain"):
        deploy.configure_web(deployment, None)
    assert calls == [["uberspace", "web", "backend", "list"]]
    deploy.configure_web(deployment, deployment.domain)
    assert calls[2] == ["uberspace", "web", "backend", "set", "knowledge.test.org/",
                        "--http", "--port", "8000"]
    assert calls[3][-2:] == ["knowledge.test.org/static", "--apache"]


def test_command_error_never_echoes_captured_secret(deploy, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=1, stdout="password", stderr="postgres://secret"))
    with pytest.raises(deploy.DeploymentError) as error:
        deploy.run(["pg_dump"], capture=True)
    assert "secret" not in str(error.value)
    assert "password" not in str(error.value)


def test_backup_keeps_dsn_out_of_arguments(deploy, configured, monkeypatch):
    deployment, _ = deploy.configuration()
    deployment.data_root.mkdir()
    (deployment.data_root / "private.txt").write_text("private")
    calls = []
    monkeypatch.setattr(deploy, "run",
                        lambda command, **kwargs: calls.append((command, kwargs)) or "")
    monkeypatch.setattr(deploy, "repositories", lambda: [])
    monkeypatch.setattr(deploy, "revisions", lambda paths: {})
    target = deploy.backup(deployment)
    command, kwargs = calls[0]
    assert command[0] == "pg_dump"
    assert deployment.dsn not in command
    assert kwargs["env"]["PGDATABASE"] == "knowledge"
    assert kwargs["env"]["PGUSER"] == "app"
    assert (target / "manifest.json").exists()
    assert target.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("extension,superuser,models,expected", [
    (None, False, [], "Activate pgvector"),
    (("0.8",), True, [], "non-superuser"),
    (("0.8",), False, [], "Required model"),
    (("0.8",), False, ["nomic-embed-text:latest", "test-chat:latest"], None),
])
def test_dependency_preflight_requires_pgvector_app_role_and_models(
    deploy, configured, monkeypatch, extension, superuser, models, expected,
):
    deployment, cfg = deploy.configuration()
    cfg.llm_default_provider = "ollama"
    cfg.ollama_model = "test-chat"
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, query):
            value = extension if "pg_extension" in query else (
                (superuser,) if "pg_roles" in query else (0,))
            return SimpleNamespace(fetchone=lambda: value)
    monkeypatch.setattr("psycopg.connect", lambda *args, **kwargs: Connection())
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"models": [{"name": model} for model in models]},
    ))
    monkeypatch.setattr(deploy.shutil, "which", lambda tool: f"/bin/{tool}")
    if expected:
        with pytest.raises(deploy.DeploymentError, match=expected):
            deploy.check_dependencies(deployment, cfg)
    else:
        deploy.check_dependencies(deployment, cfg)


def test_bootstrap_only_installs_no_lifecycle_or_routing(tmp_path, monkeypatch):
    bootstrap = load_script("bootstrap")
    root = tmp_path / "project"
    source = tmp_path / "stackctl"
    source.mkdir()
    (source / ".git").mkdir()
    (source / "pyproject.toml").write_text("[project]\nname='stackctl'\n")
    monkeypatch.setattr(bootstrap, "ROOT", root)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    assert bootstrap.main(["--stackctl-source", str(source)]) == 0
    assert calls[0][0][1:3] == ["-m", "venv"]
    assert calls[2][0][-2:] == ["stackctl", "install"]
    assert calls[2][1]["env"]["STACKCTL_EXTRAS"] == "uberspace7"
    assert all("supervisorctl" not in command and "uberspace" not in command for command, _ in calls)


@pytest.mark.parametrize("existing_python", [False, True])
def test_bootstrap_does_not_replace_incomplete_or_old_venv(tmp_path, monkeypatch, existing_python):
    bootstrap = load_script("bootstrap")
    root = tmp_path / "project"
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    if existing_python:
        python.touch()
    source = tmp_path / "stackctl"
    source.mkdir()
    (source / ".git").mkdir()
    (source / "pyproject.toml").write_text("[project]\nname='stackctl'\n")
    monkeypatch.setattr(bootstrap, "ROOT", root)
    calls = []

    def reject_old_interpreter(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(subprocess, "run", reject_old_interpreter)
    if existing_python:
        assert bootstrap.main(["--stackctl-source", str(source)]) == 1
        assert len(calls) == 1
        assert calls[0][:2] == [str(python), "-c"]
    else:
        with pytest.raises(SystemExit):
            bootstrap.main(["--stackctl-source", str(source)])
        assert calls == []


def test_django_settings_preserve_defaults_and_accept_host_paths(tmp_path, monkeypatch):
    cfg = AppConfig(knowledge_data_root=str(tmp_path / "data"), raw=ConfigDict({}))
    monkeypatch.setattr("ki_knowledge.config_runtime.config", lambda: cfg)
    for name in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS"):
        monkeypatch.delenv(name, raising=False)
    defaults = runpy.run_path(str(ROOT / "ki_knowledge/django_site/settings.py"))
    assert defaults["STATIC_ROOT"] == ROOT / "staticfiles"
    assert defaults["SECURE_PROXY_SSL_HEADER"] is None
    cfg.raw["apps"] = {"ki_knowledge": {"django": {
        "static_root": str(tmp_path / "public/static"),
        "media_root": str(tmp_path / "private/media"),
        "csrf_trusted_origins": ["https://knowledge.test.org"],
        "secure_proxy_ssl_header": ["HTTP_X_FORWARDED_PROTO", "https"],
        "session_cookie_secure": True, "csrf_cookie_secure": True,
        "secure_ssl_redirect": True, "secure_hsts_seconds": 3600,
    }}}
    configured = runpy.run_path(str(ROOT / "ki_knowledge/django_site/settings.py"))
    assert configured["STATIC_ROOT"] == tmp_path / "public/static"
    assert configured["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")
    assert configured["STORAGES"]["staticfiles"]["OPTIONS"]["directory_permissions_mode"] == 0o755
    assert configured["SESSION_COOKIE_SECURE"]
    assert configured["SECURE_HSTS_SECONDS"] == 3600


@pytest.fixture
def action_environment(deploy, tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.setattr(deploy, "ROOT", root)
    monkeypatch.setattr(sys, "prefix", str(root / ".venv"))
    for name in list(os.environ):
        if name.startswith(("KI_CFG_", "DJANGO_", "KNOWLEDGE_")) or name in {
            "KI_STAGE", "KI_PROFILE", "KI_KNOWLEDGE_STORE_BACKEND", "KI_KNOWLEDGE_POSTGRES_DSN",
        }:
            monkeypatch.delenv(name)
    monkeypatch.chdir(root)
    monkeypatch.setenv("KI_STAGE", deploy.STAGE)
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
    monkeypatch.setattr(deploy, "configuration", lambda: (SimpleNamespace(), SimpleNamespace()))
    monkeypatch.setattr(deploy, "check_dependencies", lambda *args: None)
    monkeypatch.setattr(deploy, "repositories", lambda: [root])
    return root


def test_dirty_update_fails_before_stopping_writers(deploy, action_environment, monkeypatch):
    calls = []
    def dirty(*args, **kwargs):
        raise deploy.DeploymentError("Dirty checkout")
    monkeypatch.setattr(deploy, "revisions", dirty)
    monkeypatch.setattr(deploy, "stackctl", lambda *args: calls.append(args))
    assert deploy.main(["update"]) == 1
    assert not calls


def test_failed_backup_never_migrates_or_restarts(deploy, action_environment, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "stackctl", lambda *args: calls.append(args))
    monkeypatch.setattr(deploy, "backup", lambda *args: (_ for _ in ()).throw(
        deploy.DeploymentError("Backup failed")))
    monkeypatch.setattr(deploy, "apply", lambda *args: calls.append("apply"))
    assert deploy.main(["apply"]) == 1
    assert calls == [("stop", "django", "api")]


def test_backup_precedes_migration_and_external_services_are_not_stopped(
    deploy, action_environment, monkeypatch,
):
    calls = []
    monkeypatch.setattr(deploy, "stackctl", lambda *args: calls.append(args))
    monkeypatch.setattr(deploy, "backup", lambda *args: calls.append("backup") or Path("/backup"))
    monkeypatch.setattr(deploy, "apply", lambda *args: calls.append("apply"))
    assert deploy.main(["apply"]) == 0
    assert calls == [("stop", "django", "api"), "backup", "apply"]


def test_production_django_deploy_check_passes(tmp_path):
    stages = tmp_path / "config/stages"
    stages.mkdir(parents=True)
    (stages / "prod-uberspace7.yaml").write_text(
        (ROOT / "config/stages/prod-uberspace7.yaml").read_text())
    (tmp_path / "ki.yaml").write_text(yaml.safe_dump({
        "knowledge": {"data_root": str(tmp_path / "data")},
        "apps": {"ki_knowledge": {"django": {
            "csrf_trusted_origins": ["https://knowledge.test.org"],
            "secure_proxy_ssl_header": ["HTTP_X_FORWARDED_PROTO", "https"],
        }}},
    }))
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("KI_CFG_", "DJANGO_", "KNOWLEDGE_"))
           and key not in {"KI_STAGE", "KI_PROFILE", "KI_KNOWLEDGE_POSTGRES_DSN"}}
    env.update({
        "KI_STAGE": "prod-uberspace7",
        "KI_CFG_KNOWLEDGE__DATA_ROOT": str(tmp_path / "data"),
        "DJANGO_SECRET_KEY": "nonsecret-test-" * 6,
        "DJANGO_ALLOWED_HOSTS": "knowledge.test.org",
        "KI_CFG_APPS__KI_KNOWLEDGE__DISTRIBUTED__POSTGRES_DSN": "",
        "KI_KNOWLEDGE_STORE_BACKEND": "sqlite",
        "DJANGO_SETTINGS_MODULE": "ki_knowledge.django_site.settings",
    })
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy; runpy.run_path(" + repr(str(ROOT / "deploy/uberspace7/deploy.py"))
         + ")['django_check']()"],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
