from django.urls import reverse

from ki_knowledge.django_site.layout_targets import layout_builder_url


def test_layout_builder_url_builds_subpage_query():
    assert layout_builder_url("datasources", "sources") == (
        f"{reverse('settings-layout-builder')}?area=datasources&subpage=sources"
    )
