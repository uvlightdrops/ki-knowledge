from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from ki_knowledge.django_site import page_widgets, views_dashboard


SYNC_WIDGETS = [
    "admin.sync.overview.v1",
    "admin.sync.history.v1",
    "admin.sync.catalog.v1",
    "admin.sync.master_domains.v1",
    "admin.sync.hosts.v1",
]


@pytest.mark.parametrize(
    ("role", "enabled", "catalog_error"),
    [
        ("standalone", False, ""),
        ("host", False, ""),
        ("host", True, ""),
        ("host", True, "Master nicht erreichbar"),
        ("master", True, ""),
    ],
)
def test_status_renders_configured_sync_widgets(monkeypatch, role, enabled, catalog_error):
    runtime = SimpleNamespace(
        role=role, distributed_enabled=enabled, sync_on_connect=False,
        node_id="test-node", base_url="", master_url="",
    )
    local_node = SimpleNamespace(node_id="test-node", display_name="Test")
    fetch_catalog = MagicMock(return_value=(None, catalog_error))
    hosts = MagicMock(return_value=[])
    captured = {}
    layouts = []

    def load_widgets(request, **kwargs):
        layouts.append(kwargs)
        return SYNC_WIDGETS

    def render(request, template, context):
        captured.update(context)
        return HttpResponse("ok")

    monkeypatch.setattr(views_dashboard, "_active_semantic_domain", lambda request: "research")
    monkeypatch.setattr(views_dashboard, "_load_dashboard_widget_ids", load_widgets)
    monkeypatch.setattr(views_dashboard, "_load_dashboard_widget_widths", lambda *a, **kw: {})
    monkeypatch.setattr(views_dashboard, "semantic_domain_states", lambda: [])
    monkeypatch.setattr(views_dashboard, "data_layout_snapshot", lambda domain: {})
    monkeypatch.setattr(views_dashboard, "domain_registry_overview", lambda domain: [])
    runs = MagicMock()
    runs.select_related.return_value.filter.return_value.order_by.return_value = []
    monkeypatch.setattr(views_dashboard, "SyncRun", SimpleNamespace(objects=runs))
    jobs = MagicMock()
    jobs.list_jobs.return_value = []
    monkeypatch.setattr(
        "ki_knowledge.services.distributed_sync_runner.get_job_store", lambda: jobs,
    )
    monkeypatch.setattr(views_dashboard, "persist_local_node_settings", lambda: local_node)
    monkeypatch.setattr(views_dashboard, "get_runtime_node_settings", lambda: runtime)
    monkeypatch.setattr(views_dashboard, "safe_fetch_master_domain_catalog", fetch_catalog)
    monkeypatch.setattr(views_dashboard, "list_known_hosts", hosts)
    monkeypatch.setattr(
        "ki_knowledge.django_site.distributed_api.local_domain_catalog",
        lambda: {"domains": []},
    )
    monkeypatch.setattr(views_dashboard, "render_fragment", lambda *a, **kw: "")
    monkeypatch.setattr(views_dashboard, "render", render)

    response = views_dashboard.admin_system_status_view(
        RequestFactory().get("/admin-overview/status/"),
    )

    assert response.status_code == 200
    assert captured["runtime_node"] is runtime
    assert captured["local_node"] is local_node
    assert [card["widget_id"] for card in captured["widget_cards"]] == SYNC_WIDGETS
    assert layouts[0]["subpage_key"] == "status"
    assert layouts[0]["fallback"] == [
        "admin.system.status.v1", "admin.workspace.config.v1",
    ]
    assert fetch_catalog.call_count == int(role == "host" and enabled)
    assert hosts.call_count == int(role == "master")
    if catalog_error:
        assert any(catalog_error in card["body"] for card in captured["widget_cards"])


@pytest.mark.parametrize("widget_id", SYNC_WIDGETS)
def test_sync_widgets_require_explicit_node_context(widget_id):
    with pytest.raises(ValueError, match=f"Widget {widget_id} requires local_node and runtime_node"):
        page_widgets.build_admin_widget_cards(
            active_domain="research", domain_rows=[], widget_ids=[widget_id],
        )
