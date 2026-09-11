from __future__ import annotations

from typing import Any

from django.middleware.csrf import get_token

from .dashboard_registry import widget_adapter_key, widget_by_id
from .infosite_models import GeneratedDocument
from .services import domain_knowledge_summary, domain_registry_overview
from ..widgetkit_core import empty_payload
from ..widgetkit_renderer import render_fragment, render_card
from ..widgetkit_integration import register_integration_adapter, resolve_integration_adapter


def _preview_rows(*rows: tuple[str, str]) -> list[dict[str, str]]:
    return [{"label": label, "value": value} for label, value in rows]


def _preview_links(*links: tuple[str, str]) -> list[dict[str, str]]:
    return [{"label": label, "url": url} for label, url in links]


def _preview_stats(*stats: tuple[str, str]) -> list[dict[str, str]]:
    return [{"label": label, "value": value} for label, value in stats]


def _widget_preview_from_spec(spec: Any) -> dict[str, Any]:
    payload = empty_payload(spec.widget_id, spec.label, spec.description)
    payload["stats"] = _preview_stats(("Preview", spec.label))
    return payload


def preview_payload_for_widget(widget_id: str) -> dict[str, Any]:
    spec = widget_by_id(widget_id)
    if spec is None:
        return {"widget_id": widget_id, "label": widget_id, "description": "", "stats": [], "rows": [], "links": []}
    payload = build_widget_preview_payload(widget_ids=[widget_id])
    if payload:
        return payload[0]
    return _widget_preview_from_spec(spec)


def render_widget_preview(spec: Any) -> dict[str, Any]:
    return resolve_adapter(widget_adapter_key(spec.widget_id), _widget_preview_from_spec)(spec)


def _card(widget_id: str, *, label: str, description: str, body: str, width: int = 6) -> dict[str, Any]:
    return {"widget_id": widget_id, "label": label, "description": description, "body": body, "width": max(3, min(int(width), 12))}


def _widget_width(spec: Any, *, widget_widths: dict[str, int] | None = None) -> int:
    if spec is None:
        return 6
    resolved = (widget_widths or {}).get(getattr(spec, "widget_id", ""), getattr(spec, "default_w", 6))
    try:
        width = int(resolved)
    except (TypeError, ValueError):
        width = int(getattr(spec, "default_w", 6))
    return max(3, min(width, 12))


def _build_widget_card(body: str, spec: Any, *, widget_widths: dict[str, int] | None = None) -> dict[str, str]:
    return _card(spec.widget_id, label=spec.label, description=spec.description, body=body, width=_widget_width(spec, widget_widths=widget_widths))


def _widget_fragment_handlers() -> dict[str, Any]:
    return {
        "datasources.domain.overview.v1": lambda ctx: render_fragment("datasources_domain_overview", {"all_domains": ctx["all_domains"]}),
        "datasources.overview.summary.v1": lambda ctx: render_fragment("datasources_overview_summary", {"sources": ctx["sources"], "markdown_count": ctx["markdown_count"], "owl_sources": ctx["owl_sources"]}),
        "datasources.import.quick.v1": lambda ctx: render_fragment("datasources_import_quick", {"csrf_token": ctx["csrf_token"]}),
        "datasources.sources.discovery.v1": lambda ctx: render_fragment("datasources_sources_discovery", {"markdown_count": ctx["markdown_count"], "sources": ctx["sources"]}),
        "datasources.jobs.recent.v1": lambda ctx: render_fragment("datasources_jobs_recent", {"pdf_jobs": ctx["pdf_jobs"], "jira_issues": ctx["jira_issues"]}),
        "knowledge.overview.summary.v1": lambda ctx: render_fragment("knowledge_overview_summary", {"scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.semantic.monitor.v1": lambda ctx: render_fragment("knowledge_semantic_monitor", {"active_domain": ctx["active_domain"]}),
        "knowledge.semantic.quick.v1": lambda ctx: render_fragment("knowledge_semantic_quick", {"active_domain": ctx["active_domain"]}),
        "knowledge.records.summary.v1": lambda ctx: render_fragment("knowledge_records_summary", {"scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.artifacts.summary.v1": lambda ctx: render_fragment("knowledge_artifacts_summary", {"scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.api.browser.v1": lambda ctx: render_fragment("knowledge_api_browser", {"active_domain": ctx["active_domain"], "scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.jobs.recent.v1": lambda ctx: render_fragment("knowledge_jobs_recent", {"active_domain": ctx["active_domain"], "scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.graph.overview.v1": lambda ctx: render_fragment("knowledge_graph_overview", {"active_domain": ctx["active_domain"], "scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.tools.summary.v1": lambda ctx: render_fragment("knowledge_tools_summary", {"quick_links": ctx["quick_links"]}),
        "admin.domain.db.overview.v1": lambda ctx: render_fragment("admin_domain_db_overview", {"domain_rows": ctx["domain_rows"]}),
        "settings.layout.registry.v1": lambda ctx: f"<p><strong>Active area:</strong> {ctx['config_summary'].get('active_area', 'settings')}</p><p><strong>Areas:</strong> dashboard, datasources, knowledge, infooutput, admin, settings</p><p><a href=\"/settings/layout/builder/\">Open layout builder</a></p>",
        "settings.config.summary.v1": lambda ctx: render_fragment("settings_config_summary", {"config_summary": ctx["config_summary"]}),
        "settings.layout.preview.v1": lambda ctx: render_fragment("settings_layout_preview", {"active_domain": ctx["active_domain"]}),
    }


def _adapter_domain_overview(spec: Any) -> dict[str, Any]:
    domain_rows = domain_registry_overview("default")
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(("Domains", str(len(domain_rows))), ("Active", "default")),
        "rows": _preview_rows(
            *[
                (
                    row["display_name"],
                    f"{row['knowledge_sources']} sources / {row['knowledge_records']} records",
                )
                for row in domain_rows[:5]
            ]
        ),
        "links": _preview_links(("Open data sources", "/data-sources/")),
    }


def _adapter_datasource_summary(spec: Any) -> dict[str, Any]:
    summary = domain_knowledge_summary("default")
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(
            ("Sources", str(int(summary["sources"]))),
            ("Records", str(int(summary["records"]))),
            ("Artifacts", str(int(summary["artifacts"]))),
        ),
        "rows": [],
        "links": _preview_links(("Open data sources", "/data-sources/")),
    }


def _adapter_import_quick(spec: Any) -> dict[str, Any]:
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": [],
        "rows": [],
        "links": _preview_links(("Import", "/data-sources/import/"), ("Workspace", "/data-sources/workspace/"), ("PDF jobs", "/data-sources/pdf/")),
    }


def _adapter_datasource_discovery(spec: Any) -> dict[str, Any]:
    summary = domain_knowledge_summary("default")
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(("Files", str(len(summary["recent_sources"]))), ("Sources", str(int(summary["sources"])))),
        "rows": [],
        "links": _preview_links(("Open sources", "/data-sources/sources/")),
    }


def _adapter_knowledge_overview(spec: Any) -> dict[str, Any]:
    summary = domain_knowledge_summary("default")
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(("Sources", str(int(summary["sources"]))), ("Records", str(int(summary["records"]))), ("Artifacts", str(int(summary["artifacts"])))),
        "rows": [],
        "links": _preview_links(("Open knowledge", "/knowledge/"), ("Records", "/knowledge/records/")),
    }


def _adapter_output_overview(spec: Any) -> dict[str, Any]:
    docs = GeneratedDocument.objects.select_related("project").order_by("-generated_at")[:5]
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(("Generated", str(docs.count())), ("Active", "default")),
        "rows": _preview_rows(*[(doc.display_path, doc.project.title) for doc in docs]),
        "links": _preview_links(("Open output", "/output/infosite/dashboard/")),
    }


def _adapter_admin_domain_db(spec: Any) -> dict[str, Any]:
    rows = domain_registry_overview("default")
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(("Domains", str(len(rows))), ("Configured", "yes")),
        "rows": _preview_rows(*[(row["display_name"], f"{row['knowledge_sources']} / {row['infosite_project_count']}") for row in rows[:5]]),
        "links": _preview_links(("Open admin", "/admin-overview/")),
    }


@register_integration_adapter("datasources.domain_overview")
def _registered_datasources_domain_overview(spec: Any) -> dict[str, Any]:
    return _adapter_domain_overview(spec)


@register_integration_adapter("datasources.summary")
def _registered_datasources_summary(spec: Any) -> dict[str, Any]:
    return _adapter_datasource_summary(spec)


@register_integration_adapter("datasources.import_quick")
def _registered_datasources_import_quick(spec: Any) -> dict[str, Any]:
    return _adapter_import_quick(spec)


@register_integration_adapter("datasources.discovery")
def _registered_datasources_discovery(spec: Any) -> dict[str, Any]:
    return _adapter_datasource_discovery(spec)


@register_integration_adapter("knowledge.overview")
def _registered_knowledge_overview(spec: Any) -> dict[str, Any]:
    return _adapter_knowledge_overview(spec)


@register_integration_adapter("infooutput.overview")
def _registered_infooutput_overview(spec: Any) -> dict[str, Any]:
    return _adapter_output_overview(spec)


@register_integration_adapter("admin.domain_db")
def _registered_admin_domain_db(spec: Any) -> dict[str, Any]:
    return _adapter_admin_domain_db(spec)


def render_widget_data(widget_id: str) -> dict[str, Any]:
    spec = widget_by_id(widget_id)
    if spec is None:
        return {"widget_id": widget_id, "label": widget_id, "description": "", "stats": [], "rows": [], "links": []}
    return resolve_integration_adapter(widget_adapter_key(widget_id), _widget_preview_from_spec)(spec)


def render_widget_html(widget_id: str) -> str:
    return render_card(render_widget_data(widget_id))


def render_widget_stats(widget_id: str) -> str:
    return render_fragment("stats", {"widget": render_widget_data(widget_id)})


def build_widget_preview_payload(*, widget_ids: list[str]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue

        payload.append(render_widget_data(widget_id))
    return payload


def build_data_sources_widget_cards(
    *,
    request: Any,
    active_domain: str,
    all_domains: list[dict[str, Any]],
    active_domain_state: dict[str, Any],
    markdown_count: int,
    data_dir: str,
    jira_issues: int,
    jira_csv_path: str,
    jira_cache_db: str,
    pdf_count: int,
    pdf_dir: str,
    pdf_jobs: dict[str, Any],
    ontology_count: int,
    ontology_dir: str,
    owl_sources: int,
    sources: list[Any],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    csrf_token = get_token(request) if request is not None else ""
    handlers = _widget_fragment_handlers()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        body = handler({"all_domains": all_domains, "sources": sources, "markdown_count": markdown_count, "owl_sources": owl_sources, "csrf_token": csrf_token, "pdf_jobs": pdf_jobs, "jira_issues": jira_issues}) if handler else f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_knowledge_widget_cards(
    *,
    active_domain: str,
    scoped_knowledge: dict[str, Any],
    quick_links: list[tuple[str, str, str]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        body = handler({"active_domain": active_domain, "scoped_knowledge": scoped_knowledge, "quick_links": quick_links}) if handler else f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_output_widget_cards(
    *,
    active_domain: str,
    domain_stats: list[dict[str, Any]],
    recent_documents: list[Any],
    formats: list[dict[str, Any]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        body = handler({"domain_stats": domain_stats, "recent_documents": recent_documents, "formats": formats}) if handler else f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_admin_widget_cards(
    *,
    active_domain: str,
    domain_rows: list[dict[str, Any]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        if widget_id == "admin.domain.management.v1":
            body = f"<p><strong>Active domain:</strong> {active_domain}</p><p><strong>Registered domains:</strong> {len(domain_rows)}</p>"
        elif widget_id == "admin.system.status.v1":
            body = f"<p><strong>Builder:</strong> active</p><p><strong>Admin area:</strong> enabled</p><p><strong>Active domain:</strong> {active_domain}</p><p><a href=\"/settings/\">Open settings</a></p>"
        elif widget_id == "admin.workspace.config.v1":
            body = f"<p><strong>Knowledge DB:</strong> /data/knowledge</p><p><strong>Active domain:</strong> {active_domain}</p><p><a href=\"/settings/config/\">Open config summary</a></p>"
        elif handler:
            body = handler({"domain_rows": domain_rows})
        else:
            body = f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_settings_widget_cards(
    *,
    active_domain: str,
    config_summary: dict[str, Any],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        if widget_id == "settings.layout.registry.v1":
            body = f"<p><strong>Active area:</strong> {config_summary.get('active_area', 'settings')}</p><p><strong>Areas:</strong> dashboard, datasources, knowledge, infooutput, admin, settings</p><p><a href=\"/settings/layout/builder/\">Open layout builder</a></p>"
        elif handler:
            body = handler({"config_summary": config_summary, "active_domain": active_domain})
        else:
            body = f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards
