from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from ki_knowledge.django_site.distributed_runtime import maybe_send_automatic_heartbeat
from ki_knowledge.django_site.views_dashboard import admin_sync_view


def _request(path: str = "/admin-overview/sync/"):
    request = RequestFactory().get(path)
    SessionMiddleware(lambda request: None).process_request(request)
    request.session.save()
    request.session["semantic_active_domain"] = "default"
    request.user = get_user_model()()
    return request


def test_automatic_heartbeat_does_not_raise_on_unreachable_master(monkeypatch):
    monkeypatch.setattr(
        "ki_knowledge.django_site.distributed_runtime.get_runtime_node_settings",
        lambda: SimpleNamespace(
            node_id="host-a",
            role="host",
            distributed_enabled=True,
            sync_on_connect=True,
            master_url="http://192.168.1.50:8000",
        ),
    )
    monkeypatch.setattr(
        "ki_knowledge.django_site.distributed_runtime.safe_send_master_heartbeat",
        lambda include_status=True: {"status": "unreachable", "reason": "network unreachable"},
    )

    result = maybe_send_automatic_heartbeat()

    assert result["status"] == "unreachable"


def test_admin_sync_view_stays_renderable_when_master_catalog_is_unreachable(monkeypatch):
    monkeypatch.setattr("ki_knowledge.django_site.views_dashboard._active_semantic_domain", lambda request: "default")
    monkeypatch.setattr("ki_knowledge.django_site.views_dashboard._load_dashboard_widget_ids", lambda *args, **kwargs: [])
    monkeypatch.setattr("ki_knowledge.django_site.views_dashboard.persist_local_node_settings", lambda: SimpleNamespace(node_id="host-a"))
    monkeypatch.setattr(
        "ki_knowledge.django_site.views_dashboard.get_runtime_node_settings",
        lambda: SimpleNamespace(role="host", distributed_enabled=True),
    )
    monkeypatch.setattr(
        "ki_knowledge.django_site.views_dashboard.safe_fetch_master_domain_catalog",
        lambda master_url=None: (None, "network unreachable"),
    )
    monkeypatch.setattr("ki_knowledge.django_site.views_dashboard.semantic_domain_states", lambda: [])
    monkeypatch.setattr("ki_knowledge.django_site.views_dashboard.domain_registry_overview", lambda active_domain: [])
    monkeypatch.setattr("ki_knowledge.django_site.views_dashboard.list_known_hosts", lambda: [])
    monkeypatch.setattr(
        "ki_knowledge.services.distributed_sync_runner.get_job_store",
        lambda: SimpleNamespace(list_jobs=lambda domain=None, limit=20: []),
    )

    response = admin_sync_view(_request())

    assert response.status_code == 200
    assert b"Distributed Sync" in response.content
