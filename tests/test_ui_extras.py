from widgetkit_django.layout_targets import layout_builder_url


def test_layout_builder_url_builds_subpage_query():
    assert layout_builder_url("datasources", "sources") == "/settings/layout/builder/?area=datasources&subpage=sources"
