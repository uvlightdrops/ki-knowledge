import json
import socket
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.db.backends.utils import CursorWrapper
from django.template.loader import render_to_string
from django.test import RequestFactory

from widgetkit_django.preview import _ReadOnlyFragment
from ki_knowledge.django_site import views_dashboard
from ki_knowledge.django_site import page_widgets
from ki_knowledge.django_site.dashboard_registry import (
    canonical_widget_id, default_widget_ids_for_area, widget_by_id, widget_registry,
)
from ki_knowledge.django_site import widget_catalog_preview


LIVE_RENDER_WIDGET_DATA = page_widgets.render_widget_data


def test_sources_browser_renders_quick_import_alongside_native_widgets(monkeypatch):
    context = widget_catalog_preview.build_catalog_preview_context("anthro")
    context.update({"filter_params": {}, "display": "table", "sources": []})
    loaded = []

    def load_context(ctx):
        loaded.append(ctx["active_domain"])
        return ctx

    monkeypatch.setattr(page_widgets, "_sources_datasource_context", load_context)
    monkeypatch.setattr(
        "ki_knowledge.django_site.quick_import.quick_import_rows",
        lambda domain, state, sources: [],
    )
    cards = page_widgets.build_sources_widget_cards(
        request=None,
        ctx=context,
        widget_ids=[
            "datasources.sources.list.v1",
            "datasources.import.quick.v1",
            "datasources.jobs.recent.v1",
        ],
    )
    assert [card["widget_id"] for card in cards] == [
        "datasources.sources.list.v1",
        "datasources.import.quick.v1",
        "datasources.jobs.recent.v1",
    ]
    assert loaded == ["anthro"]
    assert "<em>anthro</em>" in cards[1]["body"]
    assert 'action="/data-sources/quick-import/"' in cards[1]["body"]


@pytest.fixture(autouse=True)
def forbid_catalog_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Catalog tests must not query databases or connect to networks")

    monkeypatch.setattr(CursorWrapper, "execute", forbidden)
    monkeypatch.setattr(CursorWrapper, "executemany", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(page_widgets, "domain_knowledge_summary", forbidden)
    monkeypatch.setattr(page_widgets, "domain_registry_overview", forbidden)
    monkeypatch.setattr(page_widgets, "render_widget_data", forbidden)
    monkeypatch.setattr(views_dashboard, "_active_semantic_domain", forbidden)
    monkeypatch.setattr("ki_knowledge.django_site.views_common.maybe_send_automatic_heartbeat", forbidden)
    monkeypatch.setattr("ki_knowledge.django_site.services.semantic_domain_states", forbidden)
    monkeypatch.setattr("ki_knowledge.django_site.source_workflow.mixed_files_summary", forbidden)
    monkeypatch.setattr("ki_knowledge.django_site.quick_import.quick_import_rows", forbidden)


class ReadOnlyMarkup(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        assert tag in _ReadOnlyFragment.allowed_tags - {"form"}
        assert not ({"href", "action", "src", "name", "id", "form", "formaction", "contenteditable"} & attrs.keys())
        assert not any(key.startswith(("on", "data-", "hx-")) for key in attrs)
        if tag in {"button", "input", "select", "textarea"}:
            assert "disabled" in attrs
            assert attrs["aria-disabled"] == "true"
        if tag == "a":
            assert attrs["aria-disabled"] == "true"


@pytest.mark.parametrize("widget_id", list(widget_registry()))
def test_every_registered_widget_has_domain_scoped_readonly_sample(widget_id):
    domain = 'selected-"<&/script>-domain'
    spec = widget_by_id(widget_id)
    payload = page_widgets.preview_payload_for_widget(widget_id, active_domain=domain)
    assert payload["widget_id"] == widget_id
    assert payload["label"] == spec.label
    assert payload["description"] == spec.description
    assert payload["area"] == spec.area
    assert payload["width"] == spec.default_w
    assert payload["height"] == spec.default_h
    assert payload["active_domain"] == domain
    assert payload["preview_mode"] == "sample"
    assert payload["readonly"] is True
    assert isinstance(payload["note"], str)
    if payload["status"] != "sample":
        assert payload["note"]
    assert payload["body_html"].strip()
    assert domain not in payload["body_html"]
    assert "default" not in payload["body_html"]
    assert json.loads(json.dumps(payload)) == payload
    ReadOnlyMarkup().feed(payload["body_html"])
    expected_status = (
        "planned" if widget_id.startswith("infooutput.quiz.") else "sample"
    )
    assert payload["status"] == expected_status


def test_batch_builds_sample_context_once_and_reuses_real_renderers(monkeypatch):
    contexts = []
    original = widget_catalog_preview.build_catalog_preview_context

    def build(domain):
        context = original(domain)
        contexts.append(context)
        return context

    monkeypatch.setattr(widget_catalog_preview, "build_catalog_preview_context", build)
    payloads = page_widgets.build_widget_preview_payload(
        widget_ids=list(widget_registry()), active_domain="research",
    )
    assert len(contexts) == 1
    context = contexts[0]
    overrides = {
        "datasources.import.quick.v1", "datasources.mix.overview.v1",
        "datasources.sources.list.v1",
        "datasources.sources.unimported.v1", "admin.workspace.config.v1",
        "admin.sync.hosts.v1",
    }
    handlers = page_widgets._widget_fragment_handlers()
    for payload in payloads:
        if payload["widget_id"] not in overrides:
            assert payload["body_html"] == widget_catalog_preview.readonly_preview_html(
                handlers[payload["widget_id"]](context),
            )


def test_preview_aliases_and_domain_context_validation():
    payload = page_widgets.preview_payload_for_widget(
        "datasources.domain.overview.v1", active_domain="research",
    )
    assert payload["widget_id"] == "admin.domain.management.v1"
    assert escape("research") in payload["body_html"]
    with pytest.raises(ValueError, match="different domain"):
        page_widgets.preview_payload_for_widget(
            "admin.domain.management.v1", active_domain="research",
            preview_context=widget_catalog_preview.build_catalog_preview_context("other"),
        )
    with pytest.raises(ValueError, match="Unknown catalog widget"):
        page_widgets.preview_payload_for_widget("unknown", active_domain="research")


def test_preview_only_helpers_use_exact_templates(monkeypatch):
    fragments = []
    original = widget_catalog_preview.render_fragment

    def render(name, context):
        fragments.append((name, context))
        return original(name, context)

    monkeypatch.setattr(widget_catalog_preview, "render_fragment", render)
    monkeypatch.setattr(page_widgets, "render_fragment", render)
    ids = [
        "datasources.import.quick.v1", "datasources.mix.overview.v1",
        "datasources.sources.list.v1",
        "datasources.sources.unimported.v1", "datasources.markdown.files.v1",
        "datasources.ontology.overview.v1", "admin.workspace.config.v1",
    ]
    page_widgets.build_widget_preview_payload(widget_ids=ids, active_domain="research")
    assert [name for name, _ in fragments] == [
        "datasources_import_quick", "datasources_mix_overview",
        "sources_list", "sources_unimported",
        "datasources_markdown_files", "datasources_ontology_overview",
        "admin_workspace_config",
    ]
    assert all("default" not in str(context) for _, context in fragments)


def test_datasource_summary_widgets_render_distinct_domain_data_and_actions():
    context = widget_catalog_preview.build_catalog_preview_context("research")
    handlers = page_widgets._widget_fragment_handlers()

    markdown_html = handlers["datasources.markdown.files.v1"]({
        **context, "display_mode": "table",
    })
    assert "sample-guide.md" in markdown_html
    assert 'name="import_type" value="file"' in markdown_html
    assert "No Markdown files" not in markdown_html

    ontology_html = handlers["datasources.ontology.overview.v1"](context)
    assert "1</strong> ontology file(s)" in ontology_html
    assert "1</strong> imported OWL source(s)" in ontology_html

    discovery_html = handlers["datasources.sources.discovery.v1"](context)
    assert "3 Markdown" in discovery_html
    assert "2 PDF" in discovery_html
    assert "markdown: 1" in discovery_html
    assert "Sources:</strong> 2" not in discovery_html

    jobs_html = handlers["datasources.jobs.recent.v1"](context)
    assert "PDF queue" in jobs_html
    assert "Jira issues" in jobs_html
    assert "semantic jobs" not in jobs_html

    datasource_ids = [
        spec.widget_id for spec in widget_registry().values()
        if spec.area == "datasources"
    ]
    assert all(widget_id in handlers for widget_id in datasource_ids)


def test_readonly_fragment_removes_all_active_markup_and_escapes_text():
    html = widget_catalog_preview.readonly_preview_html("""
        <script>fetch('/mutate')</script><style>@import '/track';</style>
        <iframe src="/mutate"></iframe><img src="/track">
        <form action="/mutate" onsubmit="submit()"><input type="hidden" value="secret">
        <input type="file" name="files"><select onchange="submit()"><option selected>X</option></select>
        <button formaction="/mutate" onclick="submit()">Run</button></form>
        <a href="javascript:alert(1)" hx-post="/mutate" data-action="delete" id="live">Go</a>
        <p title="&quot; &amp;" style="color:red;background:url('/track')">A &lt; B &amp; C</p>
    """)
    ReadOnlyMarkup().feed(html)
    assert "secret" not in html
    assert "/mutate" not in html
    assert "/track" not in html
    assert "fetch(" not in html
    assert 'style="color:red"' in html
    assert "A &lt; B &amp; C" in html


def test_renderer_errors_are_not_disguised_as_empty_previews(monkeypatch):
    def broken(context):
        raise ValueError("Broken real renderer")

    monkeypatch.setattr(page_widgets, "_widget_fragment_handlers", lambda: {
        "knowledge.overview.summary.v1": broken,
    })
    with pytest.raises(ValueError, match="Broken real renderer"):
        page_widgets.preview_payload_for_widget(
            "knowledge.overview.summary.v1", active_domain="research",
        )


def test_runtime_widgets_and_shells_keep_live_rendering_behavior(monkeypatch):
    from ki_knowledge.django_site import widget_shells

    calls = []
    live_payload = {"widget_id": "knowledge.overview.summary.v1", "stats": [{"value": "live"}]}

    def resolve(adapter, fallback):
        def render(spec):
            calls.append(spec.widget_id)
            return live_payload
        return render

    monkeypatch.setattr(page_widgets, "resolve_integration_adapter", resolve)
    assert LIVE_RENDER_WIDGET_DATA("knowledge.overview.summary.v1") is live_payload
    assert calls == ["knowledge.overview.summary.v1"]
    assert widget_shells.render_widget_data is LIVE_RENDER_WIDGET_DATA
    cards = page_widgets.build_admin_widget_cards(
        active_domain="research", domain_rows=[], domain_states=[],
        widget_ids=["admin.domain.create.v1", "admin.workspace.config.v1"],
    )
    assert '<form method="post" action="/admin-overview/domains/">' in cards[0]["body"]
    assert '<button type="submit">' in cards[0]["body"]
    assert "disabled" not in cards[0]["body"]
    assert "/data/knowledge" in cards[1]["body"]
    settings = page_widgets.build_settings_widget_cards(
        active_domain="research", config_summary={},
        widget_ids=["settings.layout.registry.v1"],
    )
    assert '<a href="' in settings[0]["body"]


def test_domain_widgets_have_single_admin_identity():
    registry = widget_registry()
    for old_id, new_id in [
        ("datasources.domain.overview.v1", "admin.domain.management.v1"),
        ("datasources.domain.switcher.v1", "admin.domain.switcher.v1"),
    ]:
        assert old_id not in registry
        assert canonical_widget_id(old_id) == new_id
        assert widget_by_id(old_id).area == "admin"
    assert not any(item.startswith("datasources.domain.") for item in default_widget_ids_for_area("datasources"))
    assert not any(item.startswith("datasources.domain.") for item in default_widget_ids_for_area("datasources", "workspace"))


def test_datasource_aliases_and_defaults_only_offer_supported_widgets():
    assert canonical_widget_id("datasources.source.list.v1") == "datasources.sources.list.v1"
    assert widget_by_id("datasources.source.list.v1").widget_id == "datasources.sources.list.v1"
    assert widget_by_id("datasources.ai.summary.v1") is None
    assert "datasources.source.list.v1" not in widget_registry()
    assert "datasources.ai.summary.v1" not in widget_registry()
    assert "datasources.markdown.files.v1" in default_widget_ids_for_area("datasources", "workspace")
    assert all(
        widget_by_id(widget_id) is not None
        for area in ("datasources",)
        for widget_id in default_widget_ids_for_area(area)
    )


def test_saved_layout_drops_retired_widgets_and_resolves_source_list_alias(monkeypatch):
    from ki_knowledge.django_site import views_common

    placements = [
        SimpleNamespace(widget_id="datasources.ai.summary.v1"),
        SimpleNamespace(widget_id="datasources.source.list.v1"),
        SimpleNamespace(widget_id="datasources.sources.list.v1"),
    ]

    class LayoutStore:
        def load_layout(self, **kwargs):
            return SimpleNamespace(exists=True, placements=placements)

    monkeypatch.setattr(views_common, "_LAYOUT_STORE", LayoutStore())
    monkeypatch.setattr(views_common, "_active_semantic_domain", lambda request: "research")
    monkeypatch.setattr(views_common, "ensure_domain_registered", lambda domain: object())
    request = RequestFactory().get("/")
    request.user = SimpleNamespace(is_authenticated=False)
    request.session = {}

    assert views_common._load_dashboard_widget_ids(
        request, area_key="datasources", fallback=[],
    ) == ["datasources.sources.list.v1"]


def test_catalog_counts_are_global_when_filtered(monkeypatch):
    captured = {}
    monkeypatch.setattr(views_dashboard, "render", lambda request, template, context: captured.update(context))
    views_dashboard.widget_catalog_view(RequestFactory().get("/", {"area": "datasources", "domain": "research"}))
    specs = list(widget_registry().values())
    for tab in captured["area_tabs"]:
        assert tab["count"] == sum(tab["key"] == "all" or spec.area == tab["key"] for spec in specs)
    assert all(spec.area == "datasources" for spec in captured["widget_catalog"])
    html = render_to_string("kicli_django/widget_catalog.html", captured)
    for spec in captured["widget_catalog"]:
        assert f'<code class="wk-catalog-id">{spec.widget_id}</code>' in html
        assert f'<span class="wk-catalog-size">{spec.default_w} × {spec.default_h}</span>' in html
    assert 'class="db-widget-footer"' not in html
    assert f'<span class="wk-catalog-count">{len(specs)}</span>' in html
    assert all(item["active_domain"] == "research" for item in captured["widget_preview_payload"])
    assert "domain=research" in html
    assert "unpkg.com" not in html
    assert "Selected domain:" in html


@pytest.mark.parametrize("query,session,environment,expected", [
    ("Research Team", "session-domain", "configured-domain", "research-team"),
    ("", "session-domain", "configured-domain", "session-domain"),
    ("", "", "configured-domain", "configured-domain"),
    ("", "", "", "default"),
])
def test_catalog_domain_selection_is_readonly_and_has_no_heartbeat(
    monkeypatch, query, session, environment, expected,
):
    from ki_knowledge.django_site.context_processors import active_domain

    request = RequestFactory().get("/", {"domain": query})
    request.session = {"semantic_active_domain": session}
    original_session = dict(request.session)
    monkeypatch.setenv("KNOWLEDGE_DEFAULT_DOMAIN", environment)
    monkeypatch.setattr(views_dashboard, "render", lambda request, template, context: context)
    context = views_dashboard.widget_catalog_view(request)
    assert request.session == original_session
    assert context["active_domain"] == expected
    assert active_domain(request)["global_active_domain"] == expected
    assert all(item["active_domain"] == expected for item in context["widget_preview_payload"])


def test_audit_document_covers_every_canonical_registration():
    document = (Path(__file__).resolve().parents[1] / "docs/widget-catalog-preview-audit.md").read_text()
    for widget_id in widget_registry():
        assert f"| `{widget_id}` |" in document


def test_catalog_page_renders_with_request_without_data_or_network_access():
    from django.contrib.auth.models import AnonymousUser

    request = RequestFactory().get("/settings/layout/widgets/", {"domain": "research"})
    request.session = {}
    request.user = AnonymousUser()
    response = views_dashboard.widget_catalog_view(request)
    assert response.status_code == 200
    html = response.content.decode()
    assert "unpkg.com" not in html
    assert "Selected domain:" in html
    assert request.session == {}


def test_workspace_renders_saved_domain_aliases_with_admin_handlers(monkeypatch):
    fragments = []
    monkeypatch.setattr("ki_knowledge.django_site.services.semantic_domain_states", lambda: [])

    def render_fragment(name, context):
        fragments.append(name)
        return f"<p>{name}</p>"

    monkeypatch.setattr(page_widgets, "render_fragment", render_fragment)
    cards = page_widgets.build_workspace_widget_cards(
        request=None, active_domain="default", all_domains=[],
        active_domain_state={}, markdown_count=0, sources=[],
        widget_ids=["datasources.domain.overview.v1", "datasources.domain.switcher.v1"],
    )
    assert fragments == ["admin_domain_management", "domain_switcher"]
    assert [card["widget_id"] for card in cards] == [
        "admin.domain.management.v1", "admin.domain.switcher.v1",
    ]
