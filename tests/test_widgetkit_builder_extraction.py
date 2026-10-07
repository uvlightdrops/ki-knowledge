from types import SimpleNamespace

from widgetkit_django.builder import build_dashboard_builder_context, placement_map_for_builder
from widgetkit_django.layout_store import LayoutPlacement, LayoutState
from widgetkit_django.layout_targets import PageTarget
from widgetkit_django.registry import CallbackWidgetRegistry
from widgetkit_django.views import BuilderViewConfig, dashboard_builder_view


def _registry() -> CallbackWidgetRegistry:
    spec = SimpleNamespace(
        widget_id="settings.layout.preview.v1",
        area="settings",
        category="layout",
        label="Layout Preview",
        description="Preview persisted layout.",
        default_w=6,
        default_h=1,
        default_size="balanced",
        min_w=3,
        resizable=True,
    )
    by_id = {spec.widget_id: spec}
    return CallbackWidgetRegistry(
        builtin_areas_fn=lambda: ["settings"],
        widget_hierarchy_fn=lambda: {
            "settings": {
                "layout": {
                    "_widgets": [spec],
                }
            }
        },
        widget_ids_fn=lambda: [spec.widget_id],
        widget_by_id_fn=by_id.get,
        default_widget_ids_for_area_fn=lambda area, subpage=None: [spec.widget_id],
    )


def test_builder_context_uses_registry_contract_and_custom_template_metadata():
    registry = _registry()
    context = build_dashboard_builder_context(
        active_domain="demo",
        area_key="settings",
        subpage_key="config",
        registry=registry,
        selected_widget_ids=["settings.layout.preview.v1"],
        placement_by_widget={
            "settings.layout.preview.v1": LayoutPlacement(
                widget_id="settings.layout.preview.v1",
                sort_index=0,
                w=8,
            )
        },
        builder_action_url="/custom-builder/?area=settings&subpage=config",
        area_tabs=[{"key": "settings", "label": "Settings", "url": "/custom-builder/"}],
        page_title="Custom Builder",
        page_subtitle="Custom subtitle",
        base_template_name="custom/base.html",
    )

    assert context["builder_action_url"] == "/custom-builder/?area=settings&subpage=config"
    assert context["area_tabs"][0]["url"] == "/custom-builder/"
    assert context["widgetkit_base_template"] == "custom/base.html"
    assert context["page_title"] == "Custom Builder"
    assert context["page_subtitle"] == "Custom subtitle"
    assert context["selected_widgets"][0]["width"] == 8
    assert context["unused_widgets"] == []


def test_placement_map_for_builder_reads_from_layout_store():
    placements = [
        LayoutPlacement(widget_id="settings.layout.preview.v1", sort_index=0, w=6),
        LayoutPlacement(widget_id="settings.layout.registry.v1", sort_index=1, w=4),
    ]

    class DummyStore:
        def load_layout(self, **kwargs):
            assert kwargs == {
                "area_key": "settings",
                "subpage_key": "config",
                "active_domain": "demo",
                "owner": None,
            }
            return LayoutState(exists=True, placements=tuple(placements))

    placement_map = placement_map_for_builder(
        store=DummyStore(),
        area_key="settings",
        subpage_key="config",
        active_domain="demo",
        owner=None,
    )

    assert list(placement_map) == [
        "settings.layout.preview.v1",
        "settings.layout.registry.v1",
    ]


def test_builder_controller_rejects_unknown_targets_and_invalid_mutations():
    from django.test import RequestFactory

    registry = _registry()

    class EmptyStore:
        def load_layout(self, **kwargs):
            return LayoutState(exists=False)

        def load_shared_layout(self, **kwargs):
            return LayoutState(exists=False)

        def replace_placements(self, **kwargs):
            raise AssertionError("invalid mutations must not reach persistence")

        def clear_placements(self, **kwargs):
            raise AssertionError("invalid mutations must not reach persistence")

    config = BuilderViewConfig(
        registry=registry,
        layout_store=EmptyStore(),
        active_domain_getter=lambda request: "demo",
        selection_loader=lambda request, area, subpage, fallback: fallback,
        selection_syncer=lambda request, area: (_ for _ in ()).throw(ValueError("invalid action")),
        builder_url=lambda area, subpage: f"/builder/?area={area}&subpage={subpage}",
        page_targets_for_area=lambda area: [PageTarget("overview", "Overview", "/reports/")],
    )
    request_factory = RequestFactory()

    unknown_target = dashboard_builder_view(
        request_factory.get("/builder/", {"area": "settings", "subpage": "missing"}),
        config=config,
    )
    assert unknown_target.status_code == 400

    invalid_action = dashboard_builder_view(
        request_factory.post("/builder/", {"area": "settings", "subpage": "overview"}),
        config=config,
    )
    assert invalid_action.status_code == 400
