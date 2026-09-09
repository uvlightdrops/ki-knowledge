"""Tests for the dashboard widget registry and taxonomy."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from ki_knowledge.django_site.dashboard_registry import (
    area_widget_ids,
    builtin_areas,
    frontpage_aggregate_widgets,
    layout_positions_for_widgets,
    legacy_widget_aliases,
    widget_by_id,
    widget_registry,
    widget_hierarchy,
)
from ki_knowledge.django_site.infosite_models import DashboardDefinition, DashboardWidgetPlacement, ensure_domain_registered
from ki_knowledge.django_site.views import _load_dashboard_widget_ids


def test_widget_registry_has_functional_areas_only():
    registry = widget_registry()
    assert all(widget_id not in registry for widget_id in ("dashboard.domain.management.v1",))
    assert "admin.domain.management.v1" in registry
    assert "datasources.import.quick.v1" in registry
    assert "knowledge.semantic.monitor.v1" in registry
    assert "infooutput.overview.summary.v1" in registry
    assert "settings.layout.registry.v1" in registry


def test_widget_hierarchy_contains_expected_categories():
    hierarchy = widget_hierarchy()

    assert "datasources" in hierarchy
    assert "knowledge" in hierarchy
    assert "infooutput" in hierarchy
    assert "admin" in hierarchy
    assert "settings" in hierarchy

    assert "overview" in hierarchy["datasources"]
    assert "semantic" in hierarchy["knowledge"]
    assert "domain" in hierarchy["admin"]


def test_area_widget_ids_filters_functional_areas():
    assert area_widget_ids("admin")
    assert area_widget_ids("datasources")
    assert area_widget_ids("knowledge")
    assert area_widget_ids("infooutput")
    assert area_widget_ids("settings")

    assert all("dashboard" not in widget_id for widget_id in area_widget_ids("admin"))


def test_legacy_aliases_map_to_canonical_widget_ids():
    aliases = legacy_widget_aliases()

    assert aliases["domain-management"] == "admin.domain.management.v1"
    assert aliases["knowledge-summary"] == "admin.domain.db.overview.v1"
    assert aliases["semantic-monitor"] == "knowledge.semantic.monitor.v1"
    assert aliases["status"] == "admin.system.status.v1"


def test_frontpage_aggregate_uses_functional_overview_widgets():
    overview = frontpage_aggregate_widgets()

    assert overview == [
        "datasources.overview.summary.v1",
        "knowledge.overview.summary.v1",
        "infooutput.overview.summary.v1",
    ]


def test_layout_positions_for_widgets_assigns_a_simple_grid():
    positions = layout_positions_for_widgets([
        "datasources.overview.summary.v1",
        "knowledge.semantic.monitor.v1",
        "infooutput.overview.summary.v1",
    ])

    assert positions["datasources.overview.summary.v1"] == {"x": 0, "y": 0, "w": 12, "h": 1}
    assert positions["knowledge.semantic.monitor.v1"] == {"x": 0, "y": 1, "w": 6, "h": 1}
    assert positions["infooutput.overview.summary.v1"] == {"x": 0, "y": 2, "w": 12, "h": 1}


def test_widget_lookup_resolves_legacy_aliases():
    spec = widget_by_id("domain-management")
    assert spec is not None
    assert spec.widget_id == "admin.domain.management.v1"


def test_builtin_areas_are_functional_only():
    assert builtin_areas() == [
        "datasources",
        "knowledge",
        "infooutput",
        "admin",
        "settings",
    ]


@pytest.mark.django_db
def test_persisted_dashboard_configuration_is_loaded_for_dashboard_area():
    User = get_user_model()
    user = User.objects.create_user(username="dashboard-user", password="secret")
    domain = ensure_domain_registered("demo-dashboard")
    dashboard = DashboardDefinition.objects.create(
        owner=user,
        domain=domain,
        area_key="dashboard",
        slug="dashboard-demo-dashboard",
        title="Demo dashboard",
    )
    DashboardWidgetPlacement.objects.create(
        dashboard=dashboard,
        widget_id="datasources.overview.summary.v1",
        sort_index=0,
    )
    DashboardWidgetPlacement.objects.create(
        dashboard=dashboard,
        widget_id="knowledge.overview.summary.v1",
        sort_index=1,
    )

    request = RequestFactory().get("/", {"domain": "demo-dashboard"})
    SessionMiddleware(lambda request: None).process_request(request)
    request.session.save()
    request.user = user

    selected = _load_dashboard_widget_ids(request, area_key="dashboard", fallback=list(frontpage_aggregate_widgets()))

    assert selected == [
        "datasources.overview.summary.v1",
        "knowledge.overview.summary.v1",
    ]


def test_domain_summary_cache_avoids_repeated_store_scan(monkeypatch):
    from ki_knowledge.django_site import services

    services._FALLBACK_CACHE.clear()
    calls = {"count": 0}

    class DummyStore:
        def list_sources(self):
            calls["count"] += 1
            return []

        def list_artifacts(self):
            return []

    monkeypatch.setattr(services, "store", lambda: DummyStore())

    first = services.domain_knowledge_summary("demo-domain")
    second = services.domain_knowledge_summary("demo-domain")

    assert first == {"sources": 0, "records": 0, "artifacts": 0, "recent_sources": [], "recent_artifacts": []}
    assert second == first
    assert calls["count"] == 1

    services.invalidate_domain_summary_cache("demo-domain")
    services._FALLBACK_CACHE.clear()
