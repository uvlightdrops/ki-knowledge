"""ki-knowledge adapter for the yaml_cfg_wizard settings editor (/settings/config/sync/)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import django
import pytest
import yaml

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret
from django.test import RequestFactory
from django.urls import reverse
from jsonschema import Draft7Validator

from ki_knowledge.django_site import config_editor as ce

REPO_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "ki_knowledge.schema.yaml"
CRED_SECRET = "creds-only-s3cr3t-value"
DSN_SECRET = "dsn-pw-9f8e7d"
URL_SECRET = "url-pw-1a2b3c"
DIST = ("apps", "ki_knowledge", "distributed")


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _dist(**values):
    return {"apps": {"ki_knowledge": {"distributed": values}}}


def _get(data, *keys):
    for key in keys:
        data = data[key]
    return data


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Isolated project dir: ki.yaml, active stage, runtime layer, creds and app schema."""
    for key in list(os.environ):
        if key.startswith("KI_CFG_") or key in {"KI_STAGE", "KI_PROFILE"}:
            monkeypatch.delenv(key, raising=False)
    (tmp_path / "schema").mkdir()
    shutil.copy(REPO_SCHEMA, tmp_path / "schema" / "ki_knowledge.schema.yaml")
    _write(tmp_path / "ki.yaml", _dist(federation_id="base-fed", node_role="standalone"))
    _write(
        tmp_path / "config" / "stages" / "dev.yaml",
        _dist(public_url="http://stage.lan:8000", postgres_dsn=f"postgresql://u:{DSN_SECRET}@db/x"),
    )
    (tmp_path / "config" / "stages" / ".active_stage").write_text("dev", encoding="utf-8")
    _write(tmp_path / "config" / "runtime" / "runtime.yaml", _dist(public_url="http://runtime.lan:8000", extra_key=1))
    _write(tmp_path / "creds.yaml", {"apps": {"ki_knowledge": {"distributed": {"sync_shared_secret": CRED_SECRET}}}})
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _runtime_layer(project: Path) -> dict:
    return yaml.safe_load((project / "config" / "runtime" / "runtime.yaml").read_text(encoding="utf-8"))


# --- resolver ---------------------------------------------------------------------


def test_resolver_matches_ki_core_resolution(project):
    from ki_core import load_config

    assert ce.resolve_candidate("runtime", _runtime_layer(project)) == dict(load_config())


def test_resolver_replaces_runtime_layer_instead_of_merging(project):
    effective = ce.resolve_candidate("runtime", {})
    assert _get(effective, *DIST, "public_url") == "http://stage.lan:8000"
    assert "extra_key" not in _get(effective, *DIST)
    effective = ce.resolve_candidate("runtime", _dist(federation_id="rt-fed"))
    assert _get(effective, *DIST, "federation_id") == "rt-fed"
    assert _get(effective, *DIST, "public_url") == "http://stage.lan:8000"


def test_resolver_keeps_env_above_runtime_layer(project, monkeypatch):
    monkeypatch.setenv("KI_CFG_APPS__KI_KNOWLEDGE__DISTRIBUTED__FEDERATION_ID", "env-fed")
    effective = ce.resolve_candidate("runtime", _dist(federation_id="rt-fed"))
    assert _get(effective, *DIST, "federation_id") == "env-fed"


def test_resolver_rejects_unknown_file_and_base_schema_violation_without_values(project):
    with pytest.raises(KeyError):
        ce.resolve_candidate("stage", {})
    with pytest.raises(Exception) as excinfo:
        ce.resolve_candidate("runtime", {"http": {"request_timeout": "slow-leaky-value"}})
    assert "slow-leaky-value" not in str(excinfo.value)


def test_effective_schema_rejects_unsafe_urls_and_wrong_types(project):
    validator = Draft7Validator(ce.editor_schema())
    assert not list(validator.iter_errors(ce.resolve_candidate("runtime", _runtime_layer(project))))
    for bad in (f"http://admin:{URL_SECRET}@host", "http://host/?token=x", "ftp://host", "javascript:alert(1)"):
        assert list(validator.iter_errors(ce.resolve_candidate("runtime", _dist(public_url=bad)))), bad
    assert list(validator.iter_errors(ce.resolve_candidate("runtime", _dist(federation_id=5))))


@pytest.mark.parametrize(
    "value,safe",
    [("", True), (None, True), ("https://node.example.org:8443/ki", True), ("http://user:pw@host", False),
     ("http://user@host", False), ("http://host#frag", False), (" http://host", False), (42, False)],
)
def test_is_safe_url(value, safe):
    assert ce.is_safe_url(value) is safe


# --- scope: allowlist, DB precedence, target file -----------------------------------


def test_allowlist_excludes_db_owned_and_secret_fields():
    editable = {path for path, _label, _desc in ce.EDITABLE_FIELDS}
    db_owned = {path for path, _db in ce.DB_OWNED_FIELDS}
    assert editable == {ce.PUBLIC_URL_PATH, ce.FEDERATION_ID_PATH}
    assert not editable & db_owned
    assert not any(word in path for path in editable for word in ("secret", "password", "token", "api_key", "dsn"))
    assert "apps.ki_knowledge.distributed.node_id" not in editable


def test_node_settings_read_yaml_only_fields_from_resolved_config(monkeypatch):
    """public_url/federation_id have no NodeConfig column; settings.KI_CONFIG holds only defaults."""
    from ki_knowledge.django_site import distributed_api

    monkeypatch.setattr(
        distributed_api,
        "get_runtime_node_settings",
        lambda: distributed_api.RuntimeNodeSettings("n1", "master", "", True, True, "", ""),
    )
    monkeypatch.setattr(
        distributed_api.NodeConfig.objects,
        "filter",
        lambda **kw: SimpleNamespace(values_list=lambda *a, **k: SimpleNamespace(first=lambda: "")),
    )
    monkeypatch.setattr(
        distributed_api.Config,
        "from_env",
        lambda: SimpleNamespace(distributed_federation_id="lab", distributed_public_url="http://n1.lan:8000"),
    )
    node = distributed_api.get_node_settings()
    assert (node.federation_id, node.public_url) == ("lab", "http://n1.lan:8000")


def test_runtime_target_is_project_owned(project):
    assert ce.runtime_target() == project / "config" / "runtime" / "runtime.yaml"
    outside = project.parent / f"{project.name}-outside"
    outside.mkdir()
    shutil.rmtree(project / "config" / "runtime")
    (project / "config" / "runtime").symlink_to(outside, target_is_directory=True)
    assert ce.runtime_target() is None


# --- view: authorization, CSRF, read-only fallback, secrets -------------------------


def _user(**flags):
    base = {"is_authenticated": True, "is_active": True, "is_superuser": False, "is_staff": False}
    base.update(flags)
    return SimpleNamespace(**base)


def _request(method="get", user=None, data=None, csrf=False):
    factory = RequestFactory()
    if method == "get":
        request = factory.get("/settings/config/sync/")
    else:
        token = _mask_cipher_secret(_get_new_csrf_string()) if csrf else None
        request = factory.post("/settings/config/sync/", data=data or {})
        if token:
            request.COOKIES["csrftoken"] = token
            request.META["HTTP_X_CSRFTOKEN"] = token
    request.user = user or _user(is_superuser=True)
    request.session = {}
    return request


def test_url_is_registered():
    assert reverse("settings-config-sync") == "/settings/config/sync/"


@pytest.mark.parametrize(
    "user",
    [_user(is_authenticated=False), _user(), _user(is_staff=True), _user(is_superuser=True, is_active=False)],
)
def test_non_superusers_are_forbidden(user, monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "build_editor", lambda *a, **k: calls.append("build") or object())
    with pytest.raises(PermissionDenied):
        ce.settings_config_sync_view(_request(user=user))
    with pytest.raises(PermissionDenied):
        ce.settings_config_sync_view(_request("post", user=user, data={"action": "set"}, csrf=True))
    assert calls == []


@pytest.mark.django_db
def test_post_requires_csrf_token(monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "build_editor", lambda *a, **k: object())
    monkeypatch.setattr(
        ce, "_load_render_editor", lambda: lambda request, editor, template, context=None: calls.append(context) or HttpResponse("ok")
    )
    data = {"file": "runtime", "revision": "r1", "path": ce.FEDERATION_ID_PATH, "action": "set", "value": "x"}
    response = ce.settings_config_sync_view(_request("post", data=data))
    assert response.status_code == 403 and calls == []
    response = ce.settings_config_sync_view(_request("post", data=data, csrf=True))
    assert response.status_code == 200 and calls and calls[0]["editable"] is True


@pytest.mark.django_db
def test_readonly_without_adapter_and_no_secrets(project, monkeypatch):
    _write(
        project / "config" / "runtime" / "runtime.yaml",
        _dist(public_url=f"http://admin:{URL_SECRET}@leak.lan", federation_id="rt-fed"),
    )
    monkeypatch.setattr(ce, "_load_render_editor", lambda: None)
    response = ce.settings_config_sync_view(_request())
    html = response.content.decode()
    assert response.status_code == 200
    assert "der optionale Editor" in html and 'name="action"' not in html
    assert "rt-fed" in html and reverse("admin-sync") in html
    for secret in (CRED_SECRET, DSN_SECRET, URL_SECRET, "leak.lan"):
        assert secret not in html
    assert ce.settings_config_sync_view(_request("post", data={"action": "set"}, csrf=True)).status_code == 405


def test_readonly_rows_report_override_and_effective(project):
    rows = {row["path"]: row for row in ce.readonly_rows()}
    assert set(rows) == {ce.PUBLIC_URL_PATH, ce.FEDERATION_ID_PATH}
    assert rows[ce.PUBLIC_URL_PATH]["overridden"] and rows[ce.PUBLIC_URL_PATH]["effective"] == "http://runtime.lan:8000"
    assert not rows[ce.FEDERATION_ID_PATH]["overridden"] and rows[ce.FEDERATION_ID_PATH]["effective"] == "base-fed"


# --- with the yaml_cfg_wizard editor core -----------------------------------------


@pytest.fixture
def editor_core():
    return pytest.importorskip("yaml_cfg_wizard.editor")


def _rows(snapshot):
    return {row["path"]: row for row in snapshot.rows}


def test_core_snapshot_exposes_only_allowlist_without_secrets(project, editor_core):
    snapshot = ce.build_editor().snapshot("runtime")
    assert set(_rows(snapshot)) == {ce.PUBLIC_URL_PATH, ce.FEDERATION_ID_PATH}
    dumped = repr(snapshot)
    for secret in (CRED_SECRET, DSN_SECRET):
        assert secret not in dumped


def test_core_conflict_on_stale_revision(project, editor_core):
    editor = ce.build_editor()
    stale = editor.snapshot("runtime").revision
    editor.save("runtime", stale, {ce.FEDERATION_ID_PATH: "first"})
    with pytest.raises(editor_core.ConflictError):
        editor.save("runtime", stale, {ce.FEDERATION_ID_PATH: "second"})
    assert _get(_runtime_layer(project), *DIST, "federation_id") == "first"


def test_core_remove_differs_from_empty(project, editor_core):
    editor = ce.build_editor()
    snapshot = editor.save("runtime", editor.snapshot("runtime").revision, {ce.FEDERATION_ID_PATH: ""})
    row = _rows(snapshot)[ce.FEDERATION_ID_PATH]
    assert row["overridden"] and row["override"] == "" and row["effective"] == ""
    snapshot = editor.save("runtime", snapshot.revision, {}, remove=[ce.FEDERATION_ID_PATH])
    row = _rows(snapshot)[ce.FEDERATION_ID_PATH]
    assert not row["overridden"] and row["effective"] == "base-fed"
    layer = _runtime_layer(project)
    assert "federation_id" not in _get(layer, *DIST) and _get(layer, *DIST, "extra_key") == 1


def test_core_rejects_unsafe_url_without_echoing_it(project, editor_core):
    editor = ce.build_editor()
    revision = editor.snapshot("runtime").revision
    before = (project / "config" / "runtime" / "runtime.yaml").read_bytes()
    with pytest.raises(editor_core.ValidationError) as excinfo:
        editor.save("runtime", revision, {ce.PUBLIC_URL_PATH: f"http://admin:{URL_SECRET}@host"})
    assert URL_SECRET not in str(excinfo.value)
    assert (project / "config" / "runtime" / "runtime.yaml").read_bytes() == before


def test_core_rejects_non_allowlisted_paths(project, editor_core):
    editor = ce.build_editor()
    revision = editor.snapshot("runtime").revision
    with pytest.raises(editor_core.EditorError):
        editor.save("runtime", revision, {"apps.ki_knowledge.distributed.node_role": "master"})
    with pytest.raises(editor_core.EditorError):
        editor.save("runtime", revision, {"apps.ki_knowledge.distributed.sync_shared_secret": "x"})


def _edit_request(revision, action="set", value="", path=ce.FEDERATION_ID_PATH, file="runtime"):
    return _request("post", csrf=True, data={
        "file": file, "revision": revision, "path": path, "action": action, "value": value,
    })


@pytest.mark.django_db
def test_real_view_save_reload_conflict_and_remove(project, editor_core):
    from ki_knowledge.app_config import AppConfig

    editor = ce.build_editor()
    stale = editor.snapshot("runtime").revision
    response = ce.settings_config_sync_view(_request())
    assert response.status_code == 200
    assert 'name="revision"' in response.content.decode()
    assert "csrftoken" in response.cookies
    response = ce.settings_config_sync_view(_edit_request(stale, value="new-fed"))
    assert response.status_code == 200 and "Gespeichert." in response.content.decode()
    assert AppConfig.from_env().distributed_federation_id == "new-fed"
    response = ce.settings_config_sync_view(_edit_request(stale, value="lost-update"))
    assert response.status_code == 409
    assert "lost-update" not in response.content.decode()
    assert AppConfig.from_env().distributed_federation_id == "new-fed"
    revision = editor.snapshot("runtime").revision
    response = ce.settings_config_sync_view(_edit_request(revision, value=""))
    assert response.status_code == 200
    assert _get(_runtime_layer(project), *DIST, "federation_id") == ""
    response = ce.settings_config_sync_view(_edit_request(editor.snapshot("runtime").revision, action="remove"))
    assert response.status_code == 200
    assert "federation_id" not in _get(_runtime_layer(project), *DIST)
    assert AppConfig.from_env().distributed_federation_id == "base-fed"


@pytest.mark.parametrize("value", [f"http://user:{URL_SECRET}@host", "[invalid", "{password: private}", "42"])
@pytest.mark.django_db
def test_real_view_validation_never_echoes_submitted_values(project, editor_core, value):
    revision = ce.build_editor().snapshot("runtime").revision
    before = (project / "config/runtime/runtime.yaml").read_bytes()
    response = ce.settings_config_sync_view(_edit_request(revision, value=value, path=ce.PUBLIC_URL_PATH))
    assert response.status_code == 400
    assert value not in response.content.decode()
    assert URL_SECRET not in response.content.decode()
    assert (project / "config/runtime/runtime.yaml").read_bytes() == before


@pytest.mark.django_db
def test_real_view_reports_higher_layer_precedence(project, editor_core, monkeypatch):
    monkeypatch.setenv("KI_CFG_APPS__KI_KNOWLEDGE__DISTRIBUTED__FEDERATION_ID", "env-fed")
    revision = ce.build_editor().snapshot("runtime").revision
    response = ce.settings_config_sync_view(_edit_request(revision, value="yaml-fed"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "yaml-fed" in html and "env-fed" in html and "von höherem Layer überschrieben" in html
    assert _get(_runtime_layer(project), *DIST, "federation_id") == "yaml-fed"


@pytest.mark.django_db
def test_real_view_rejects_forged_file_and_db_key(project, editor_core):
    revision = ce.build_editor().snapshot("runtime").revision
    response = ce.settings_config_sync_view(_edit_request(revision, file="../../creds.yaml", value="private"))
    assert response.status_code == 400 and "private" not in response.content.decode()
    response = ce.settings_config_sync_view(_edit_request(
        revision, path=f"{ce._DISTRIBUTED}.node_role", value="master",
    ))
    assert response.status_code == 400
    response = ce.settings_config_sync_view(_edit_request(revision, action="overwrite-all", value="private"))
    assert response.status_code == 400 and "private" not in response.content.decode()


@pytest.mark.django_db
def test_real_view_handles_broken_config_without_context_processor_leaks(project, editor_core):
    (project / "config/runtime/runtime.yaml").write_text("secret: [private")
    response = ce.settings_config_sync_view(_request())
    assert response.status_code == 400
    html = response.content.decode()
    assert "Configuration file cannot be read." in html and "private" not in html


@pytest.mark.django_db
def test_readonly_resolution_error_is_explicit_and_value_free(project, monkeypatch, caplog):
    monkeypatch.setattr(ce, "_load_render_editor", lambda: None)
    (project / "config/runtime/runtime.yaml").write_text("secret: [private")
    response = ce.settings_config_sync_view(_request())
    assert response.status_code == 400
    assert "Konfiguration konnte nicht aufgelöst werden." in response.content.decode()
    assert "private" not in response.content.decode() and "private" not in caplog.text
    assert "could not be resolved" in caplog.text
