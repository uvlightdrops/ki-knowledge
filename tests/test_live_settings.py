"""Project wiring around the shared runtime editor, isolated from live config."""

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
from django.middleware.csrf import _get_new_csrf_string
from django.test import RequestFactory
from django.urls import resolve, reverse
from ki_core.runtime_settings import EditorError, RuntimeSettings

from ki_knowledge.app_config import AppConfig, clear_config_cache
from ki_knowledge.django_site import live_settings
from ki_knowledge.llm_provider import chat_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def project(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("KI_CFG_") or key in {"KI_STAGE", "KI_PROFILE"}:
            monkeypatch.delenv(key)
    schema = tmp_path / "schema"
    schema.mkdir()
    shutil.copy(Path(__file__).resolve().parents[1] / "schema/ki_knowledge.schema.yaml", schema)
    (tmp_path / "ki.yaml").write_text("llm:\n  provider: mock\n", encoding="utf-8")
    (tmp_path / "creds.yaml").write_text(
        "llm:\n  providers:\n    ki:\n      api_key: never-display-this-test-credential\n", encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_settings, "PROJECT_ROOT", tmp_path)
    clear_config_cache()
    return tmp_path


def request(method="get", data=None, *, superuser=True, csrf=True):
    factory = RequestFactory()
    req = factory.get("/settings/config/") if method == "get" else factory.post(
        "/settings/config/", data=data or {},
    )
    req.user = SimpleNamespace(
        is_authenticated=True, is_active=True, is_superuser=superuser, username="admin",
    )
    req.session = {}
    if method == "post" and csrf:
        token = _get_new_csrf_string()
        req.COOKIES["csrftoken"] = token
        req.META["HTTP_X_CSRFTOKEN"] = token
    return req


def test_existing_settings_url_uses_shared_editor(project):
    view = resolve(reverse("settings-config")).func
    response = view(request())
    assert response.status_code == 200
    html = response.content.decode()
    assert "llm.provider" in html and "knowledge.data_root" in html
    assert "nextcloud" in html
    assert "never-display-this-test-credential" not in html
    assert reverse("admin-sync") in html


@pytest.mark.parametrize("method", ["get", "post"])
def test_shared_settings_requires_active_superuser(project, method):
    with pytest.raises(PermissionDenied):
        live_settings.settings_config_view(request(method, superuser=False))


def test_post_without_csrf_cannot_write(project):
    response = live_settings.settings_config_view(request(
        "post", {"action": "set", "path": "llm.provider", "value": "ollama"}, csrf=False,
    ))
    assert response.status_code == 403
    assert not (project / "config/runtime/runtime.yaml").exists()


def test_runtime_save_applies_to_next_app_client_and_survives_new_service(project):
    service = live_settings.build_runtime_settings()
    snapshot = service.snapshot()
    saved = service.save(snapshot["revision"], {
        "llm.provider": "ollama",
        "llm.providers.ollama.model": "next-request-model",
        "http.request_timeout": 49,
        "infosite.title": "New title",
    })
    assert saved["revision"] != snapshot["revision"]
    config = AppConfig.from_env()
    assert config.infosite_title == "New title"
    assert chat_client().default_model == "next-request-model"
    assert chat_client().timeout == 49
    assert live_settings.build_runtime_settings().snapshot()["revision"] == saved["revision"]
    layer = yaml.safe_load((project / "config/runtime/runtime.yaml").read_text())
    assert layer["llm"]["provider"] == "ollama"


def test_bootstrap_settings_are_marked_not_misrepresented_as_hot_reload(project):
    rows = {row["path"]: row for row in live_settings.build_runtime_settings().snapshot()["rows"]}
    assert rows["apps.ki_knowledge.django.debug"]["restart_required"]
    assert rows["knowledge.data_root"]["restart_required"]
    assert rows["knowledge.embed_model"]["restart_required"]
    assert not rows["llm.provider"]["restart_required"]
    assert not rows["http.request_timeout"]["restart_required"]


def test_db_owned_settings_and_node_identity_cannot_be_changed_in_yaml(project):
    service = live_settings.build_runtime_settings()
    snapshot = service.snapshot()
    for path in live_settings.EXCLUDED_PATHS:
        with pytest.raises(EditorError):
            service.save(snapshot["revision"], {path: "must-not-write"})
    assert not (project / "config/runtime/runtime.yaml").exists()


def test_nextcloud_domain_map_and_django_allowed_hosts_are_discoverable(project):
    service = live_settings.build_runtime_settings()
    rows = {row["path"]: row for row in service.snapshot()["rows"]}
    assert rows["apps.ki_knowledge.nextcloud.domains"]["editable"]
    assert rows["apps.ki_knowledge.django.allowed_hosts"]["editable"]
    service.save(service.snapshot()["revision"], {
        "apps.ki_knowledge.nextcloud.domains": {
            "books": {"input_root": "sources/books", "output_root": "output/books"},
        },
        "apps.ki_knowledge.django.allowed_hosts": ["localhost", "127.0.0.1"],
    })
    assert AppConfig.from_env().raw.get_path("apps.ki_knowledge.nextcloud.domains.books.input_root") == "sources/books"


def test_write_only_credential_applies_to_next_client_and_never_appears_in_snapshots(project):
    service = live_settings.build_runtime_settings()
    secret = "synthetic-client-secret"
    secret_snapshot = service.secret_snapshot()
    result = service.save_secret(secret_snapshot["revision"], "llm.providers.openai.api_key", secret)
    assert secret not in repr(result)
    assert secret not in repr(service.snapshot())
    service.save(service.snapshot()["revision"], {"llm.provider": "openai"})
    assert chat_client().api_key == secret
    clear_config_cache()
    assert chat_client().api_key == secret
    service.remove_secret(result["revision"], "llm.providers.openai.api_key")
    assert secret not in repr(service.secret_snapshot())


def test_secret_editor_cannot_override_db_owned_sync_credentials(project):
    service = live_settings.build_runtime_settings()
    revision = service.secret_snapshot()["revision"]
    before = (project / "creds.yaml").read_bytes()
    with pytest.raises(EditorError):
        service.save_secret(
            revision, "apps.ki_knowledge.distributed.sync_shared_secret", "synthetic-rejected",
        )
    assert (project / "creds.yaml").read_bytes() == before


def test_c2_menu_is_adjacent_and_uses_same_runtime_settings(project):
    from ki_knowledge.django_site.layout_targets import nav_areas_config

    menu = next(area["submenu"] for area in nav_areas_config() if area["key"] == "settings")
    index = next(i for i, item in enumerate(menu) if item[0] == "Configuration")
    assert menu[index + 1][0:2] == ("C2", reverse("settings-config-c2"))
    req = request()
    req.path = reverse("settings-config-c2")
    response = resolve(req.path).func(req)
    html = response.content.decode()
    assert response.status_code == 200
    assert 'class="wk-c2-table"' in html
    assert 'data-config-path="llm.provider"' in html
    assert "padding-left:28px" in html
    assert "runtime-settings-compact.css" in html
    assert "never-display-this-test-credential" not in html
    snapshot = live_settings.build_runtime_settings().snapshot()
    post = request("post", {
        "revision": snapshot["revision"], "change": "infosite.title",
        "value:infosite.title": "C2 persisted",
    })
    post.path = req.path
    response = resolve(req.path).func(post)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("settings-config-c2"))
    assert AppConfig.from_env().infosite_title == "C2 persisted"


def test_c2_preserves_auth_and_csrf(project):
    with pytest.raises(PermissionDenied):
        live_settings.settings_config_compact_view(request(superuser=False))
    response = live_settings.settings_config_compact_view(request("post", csrf=False))
    assert response.status_code == 403
