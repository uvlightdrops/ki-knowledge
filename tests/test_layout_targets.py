from ki_knowledge.django_site.layout_targets import layout_target, layout_targets_for_area, nav_areas_config


def test_layout_targets_for_datasources_include_sources_subpage():
    targets = layout_targets_for_area("datasources")

    assert any(item.key == "sources" and item.path == "/data-sources/sources/" for item in targets)


def test_layout_target_returns_requested_subpage():
    target = layout_target("admin", "status")

    assert (target.key, target.label, target.path) == (
        "status", "System Status", "/admin-overview/status/",
    )


def test_nav_areas_config_reuses_settings_submenu_for_layout_builder():
    areas = nav_areas_config()
    settings = next(area for area in areas if area["key"] == "settings")
    layout_builder = next(area for area in areas if area["key"] == "layout-builder")

    assert settings["submenu"] == layout_builder["submenu"]
