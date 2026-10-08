from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.urls import reverse

from .dashboard_registry import widget_adapter_key, widget_by_id
from .infosite_models import GeneratedDocument
from .infosite_models import NodeConfig, SyncRun, current_node_id
from .layout_targets import layout_builder_url
from .services import domain_knowledge_summary, domain_registry_overview
from ..widgetkit_core import DataSourceSpec, TableDataSourceAdapter, empty_payload
from ..widgetkit_renderer import render_fragment, render_card
from ..widgetkit_integration import register_integration_adapter, resolve_integration_adapter

_TABLE_ADAPTER = TableDataSourceAdapter()


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


def preview_payload_for_widget(
    widget_id: str, *, active_domain: str, preview_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Offline catalog preview; runtime adapters remain in ``render_widget_data``."""
    spec = widget_by_id(widget_id)
    if spec is None:
        raise ValueError(f"Unknown catalog widget: {widget_id}")
    from .widget_catalog_preview import build_catalog_preview_context, render_catalog_widget

    context = preview_context if preview_context is not None else build_catalog_preview_context(active_domain)
    if context["active_domain"] != active_domain:
        raise ValueError("Catalog preview context belongs to a different domain")
    return render_catalog_widget(spec, context).to_payload()


def render_widget_preview(spec: Any, *, active_domain: str) -> dict[str, Any]:
    return preview_payload_for_widget(spec.widget_id, active_domain=active_domain)


def _card(widget_id: str, *, label: str, description: str, body: str, width: int = 6) -> dict[str, Any]:
    return {"widget_id": widget_id, "label": label, "description": description, "body": body, "width": max(3, min(int(width), 12))}


def _widget_min_width(spec: Any) -> int:
    if spec is None:
        return 3
    try:
        min_width = int(getattr(spec, "min_w", 3))
    except (TypeError, ValueError):
        min_width = 3
    return max(3, min(min_width, 12))


def _widget_width(spec: Any, *, widget_widths: dict[str, int] | None = None) -> int:
    if spec is None:
        return 6
    resolved = (widget_widths or {}).get(getattr(spec, "widget_id", ""), getattr(spec, "default_w", 6))
    try:
        width = int(resolved)
    except (TypeError, ValueError):
        width = int(getattr(spec, "default_w", 6))
    return max(_widget_min_width(spec), min(width, 12))


def _build_widget_card(body: str, spec: Any, *, widget_widths: dict[str, int] | None = None) -> dict[str, str]:
    return _card(spec.widget_id, label=spec.label, description=spec.description, body=body, width=_widget_width(spec, widget_widths=widget_widths))


def _render_quick_import(ctx: dict[str, Any]) -> str:
    from ki_knowledge.django_site.quick_import import UPLOAD_ACCEPT, quick_import_rows

    domain = ctx.get("active_domain") or ""
    rows = quick_import_rows(domain, ctx.get("active_domain_state") or {}, ctx.get("sources") or ())
    return render_fragment("datasources_import_quick", {
        "rows": rows,
        "any_files": any(row["can_import"] for row in rows),
        "active_domain": domain,
        "upload_accept": UPLOAD_ACCEPT,
        "csrf_token": ctx["csrf_token"],
    })


def _render_mix_overview(ctx: dict[str, Any]) -> str:
    from ki_knowledge.django_site.services import display_data_path
    from ki_knowledge.django_site.source_workflow import mixed_files_summary

    summary = mixed_files_summary(ctx.get("active_domain"))
    return render_fragment("datasources_mix_overview", {
        "mix": summary,
        "mix_dir": str(summary["dir"]),
        "mix_dir_display": display_data_path(summary["dir"]),
        "counts": [(kind, count) for kind, count in summary["counts"].items() if kind != "unsupported"],
        "unsupported": summary["counts"].get("unsupported", 0),
        "active_domain": ctx.get("active_domain"),
        "csrf_token": ctx["csrf_token"],
    })


def _render_markdown_files(ctx: dict[str, Any]) -> str:
    workspace_url = reverse("workspace")
    files = [
        {
            **item,
            "workspace_url": (
                f"{workspace_url}?{urlencode({'domain': ctx['active_domain'], 'path': item['path']})}"
            ),
        }
        for item in (ctx.get("markdown_files") or [])
    ]
    return render_fragment("datasources_markdown_files", {
        "active_domain": ctx["active_domain"],
        "markdown_count": ctx["markdown_count"],
        "markdown_files": files[:8],
        "action_url": reverse("import-action"),
        "all_files_url": f"{workspace_url}?{urlencode({'domain': ctx['active_domain'], 'q': ctx.get('query', '')})}",
        "csrf_token": ctx["csrf_token"],
        "display_mode": ctx.get("display_mode", "cards"),
        "query": ctx.get("query", ""),
    })


def _render_ontology_overview(ctx: dict[str, Any]) -> str:
    return render_fragment("datasources_ontology_overview", {
        "active_domain": ctx["active_domain"],
        "ontology_count": ctx["ontology_count"],
        "ontology_dir": ctx["ontology_dir"],
        "owl_sources": ctx["owl_sources"],
        "sources_url": f"{reverse('sources')}?{urlencode({'kind': 'owl', 'domain': ctx['active_domain']})}",
    })


def _render_source_browser_link(ctx: dict[str, Any]) -> str:
    widget_id = ctx["widget_id"]
    widget_copy = {
        "datasources.sources.filter.v1": (
            "Filter und Sortierung der Domain-Quellen verwenden.",
            "Filter öffnen",
        ),
        "datasources.sources.list.v1": (
            "Importierte und noch nicht importierte Dateien in einer domainweiten Liste prüfen.",
            "Quellenliste öffnen",
        ),
        "datasources.sources.unimported.v1": (
            "Neue, wartende oder fehlgeschlagene Dateien gezielt importieren.",
            "Importliste öffnen",
        ),
    }
    description, action_label = widget_copy[widget_id]
    return render_fragment("datasources_sources_browser_link", {
        "description": description,
        "action_label": action_label,
        "url": f"{reverse('sources')}?{urlencode({'domain': ctx['active_domain']})}",
        "source_count": len(ctx.get("sources", [])),
        "active_domain": ctx["active_domain"],
    })


def _source_type_counts(sources: list[Any]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for source in sources:
        source_type = getattr(source, "source_type", None)
        if source_type is None and isinstance(source, dict):
            source_type = source.get("source_type", source.get("kind"))
        if source_type:
            normalized = str(source_type)
            counts[normalized] = counts.get(normalized, 0) + 1
    return sorted(counts.items())


def _render_infooutput_overview(ctx: dict[str, Any]) -> str:
    domain = ctx["active_domain"]
    documents = ctx["domain_documents"]
    projects = ctx["recent_projects"]
    domain_row = next((row for row in ctx["domain_stats"] if row["slug"] == domain), {})
    return render_fragment("output_overview", {
        "domain": domain,
        "project_count": len(projects),
        "document_count": int(domain_row.get("total", len(documents)) or 0),
        "approved_count": int(domain_row.get("approved", 0) or 0),
        "recent_count": len(documents),
        "infosite_url": "/output/infosite/dashboard/",
    })


def _render_infooutput_projects(ctx: dict[str, Any]) -> str:
    projects = ctx["recent_projects"]
    return render_fragment("output_recent_projects", {
        "projects": [
            {
                "title": project.title,
                "domain": project.domain,
                "working_title": project.working_title,
                "status": project.generation_status,
                "url": f"/output/infosite/project/{project.id}/",
            }
            for project in projects
        ],
        "project_url": "/output/infosite/dashboard/",
    })


def _render_infooutput_documents(ctx: dict[str, Any], *, generated_only: bool = False) -> str:
    documents = ctx["domain_documents"]
    if generated_only:
        documents = [document for document in documents if document.review_status in {"approved", "in_review"}]
    return render_fragment("output_recent_documents", {
        "documents": [
            {
                "path": document.display_path,
                "title": document.project.title,
                "review_status": document.get_review_status_display(),
                "url": f"/output/infosite/project/{document.project_id}/preview/",
            }
            for document in documents[:10]
        ],
        "empty_message": (
            "Noch keine freigegebenen oder in Prüfung befindlichen Ausgabedokumente."
            if generated_only else "Für diese Domain gibt es noch keine Ausgabedokumente."
        ),
    })


def _render_infooutput_domains(ctx: dict[str, Any]) -> str:
    return render_fragment("output_domain_overview", {
        "domains": ctx["domain_stats"],
        "active_domain": ctx["active_domain"],
    })


def _render_infooutput_formats(ctx: dict[str, Any]) -> str:
    return render_fragment("output_formats", {"formats": ctx["formats"]})


def _render_knowledge_semantic_overview(ctx: dict[str, Any]) -> str:
    return render_to_string(
        "kicli_django/widgets/knowledge_semantic_overview.html",
        {
            "active_domain": ctx["active_domain"],
            "term_count": ctx["term_count"],
        },
    )


def _render_infosite_dashboard_stats(ctx: dict[str, Any]) -> str:
    stats = ctx["infosite_stats"]
    return render_to_string("infosite/widgets/dashboard_stats.html", {"stats": stats})


def _render_infosite_dashboard_projects(ctx: dict[str, Any]) -> str:
    return render_to_string("infosite/widgets/dashboard_projects.html", {"projects": ctx["infosite_projects"]})


def _render_infosite_import_workflow(ctx: dict[str, Any]) -> str:
    return render_to_string("infosite/widgets/dashboard_import_workflow.html", {})


def _render_infosite_refine_workflow(ctx: dict[str, Any]) -> str:
    return render_to_string("infosite/widgets/dashboard_refine_workflow.html", {})


def _render_infooutput_quiz_overview(ctx: dict[str, Any]) -> str:
    return render_to_string("kicli_django/widgets/output_quiz_overview.html", {})


def _render_infooutput_quiz_status(ctx: dict[str, Any]) -> str:
    return render_to_string("kicli_django/widgets/output_quiz_status.html", {"active_domain": ctx["active_domain"]})


def _sync_widget_context(ctx: dict[str, Any]) -> dict[str, Any]:
    local_node = ctx["local_node"]
    return {
        "local_node": local_node,
        "runtime_node": ctx["runtime_node"],
        "sync_runs": ctx["sync_runs"],
        "sync_jobs": ctx["sync_jobs"],
        "master_domain_catalog": ctx["master_domain_catalog"],
        "master_domain_catalog_error": ctx["master_domain_catalog_error"],
        "known_hosts": ctx.get("known_hosts", []),
        "sync_admin_url": ctx["sync_admin_url"],
        "domain_management_url": ctx["domain_management_url"],
        "worker_command_example": f"python manage.py process_distributed_sync_jobs --pending --domain {ctx['active_domain']}",
    }


def _render_domain_management(ctx: dict[str, Any]) -> str:
    domain_states = ctx.get("domain_states")
    if domain_states is None:
        from .services import semantic_domain_states

        domain_states = semantic_domain_states()
    return render_fragment("admin_domain_management", {
        "domain_states": domain_states,
        "active_domain": ctx["active_domain"],
        "csrf_token": ctx["csrf_token"],
        "domain_management_url": ctx.get("domain_management_url", "/admin-overview/domains/"),
    })


def _widget_fragment_handlers() -> dict[str, Any]:
    return {
        "datasources.overview.summary.v1": lambda ctx: render_fragment("datasources_overview_summary", {"sources": ctx["sources"], "markdown_count": ctx["markdown_count"], "owl_sources": ctx["owl_sources"]}),
        "datasources.import.quick.v1": _render_quick_import,
        "datasources.sources.discovery.v1": lambda ctx: render_fragment("datasources_sources_discovery", {
            "markdown_count": ctx["markdown_count"],
            "pdf_count": ctx["pdf_count"],
            "ontology_count": ctx["ontology_count"],
            "imported_by_type": _source_type_counts(ctx["sources"]),
            "sources_url": f"{reverse('sources')}?{urlencode({'domain': ctx['active_domain']})}",
        }),
        "datasources.mix.overview.v1": _render_mix_overview,
        "datasources.sources.filter.v1": _render_source_browser_link,
        "datasources.sources.list.v1": _render_source_browser_link,
        "datasources.sources.unimported.v1": _render_source_browser_link,
        "datasources.markdown.files.v1": _render_markdown_files,
        "datasources.ontology.overview.v1": _render_ontology_overview,
        "datasources.jobs.recent.v1": lambda ctx: render_fragment("datasources_jobs_recent", {
            "pdf_jobs": ctx["pdf_jobs"],
            "jira_issues": ctx["jira_issues"],
        }),
        "knowledge.overview.summary.v1": lambda ctx: render_fragment("knowledge_overview_summary", {"scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.semantic.overview.v1": _render_knowledge_semantic_overview,
        "knowledge.semantic.monitor.v1": lambda ctx: render_fragment("knowledge_semantic_monitor", {"active_domain": ctx["active_domain"]}),
        "knowledge.semantic.quick.v1": lambda ctx: render_fragment("knowledge_semantic_quick", {"active_domain": ctx["active_domain"]}),
        "knowledge.records.summary.v1": lambda ctx: render_fragment("knowledge_records_summary", {"scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.artifacts.summary.v1": lambda ctx: render_fragment("knowledge_artifacts_summary", {"scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.api.browser.v1": lambda ctx: render_fragment("knowledge_api_browser", {"active_domain": ctx["active_domain"], "scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.jobs.recent.v1": lambda ctx: render_fragment("knowledge_jobs_recent", {"active_domain": ctx["active_domain"], "scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.graph.overview.v1": lambda ctx: render_fragment("knowledge_graph_overview", {"active_domain": ctx["active_domain"], "scoped_knowledge": ctx["scoped_knowledge"]}),
        "knowledge.tools.summary.v1": lambda ctx: render_fragment("knowledge_tools_summary", {"quick_links": ctx["quick_links"]}),
        "admin.domain.db.overview.v1": lambda ctx: render_fragment("admin_domain_db_overview", {"domain_rows": ctx["domain_rows"]}),
        "admin.domain.switcher.v1": lambda ctx: render_fragment("domain_switcher", {"all_domains": ctx.get("domain_rows", ctx.get("all_domains", []))}),
        "admin.domain.management.v1": _render_domain_management,
        "admin.domain.create.v1": lambda ctx: render_fragment("admin_domain_create", {
            "csrf_token": ctx["csrf_token"],
            "domain_management_url": ctx["domain_management_url"],
        }),
        "admin.system.status.v1": lambda ctx: render_fragment("admin_system_status", {
            "active_domain": ctx["active_domain"],
            "registered_domain_count": ctx["registered_domain_count"],
            "layout": ctx["layout"],
            "status_url": ctx["status_url"],
        }),
        "admin.sync.overview.v1": lambda ctx: render_to_string("kicli_django/admin_sync_overview.html", _sync_widget_context(ctx)),
        "admin.sync.history.v1": lambda ctx: render_to_string("kicli_django/admin_sync_history.html", _sync_widget_context(ctx)),
        "admin.sync.catalog.v1": lambda ctx: render_to_string("kicli_django/admin_sync_catalog.html", _sync_widget_context(ctx)),
        "admin.sync.hosts.v1": lambda ctx: render_to_string("kicli_django/admin_sync_hosts.html", _sync_widget_context(ctx)),
        "infooutput.overview.summary.v1": _render_infooutput_overview,
        "infooutput.formats.summary.v1": _render_infooutput_formats,
        "infooutput.domain.overview.v1": _render_infooutput_domains,
        "infooutput.infosite.recent.v1": _render_infooutput_projects,
        "infooutput.documents.recent.v1": _render_infooutput_documents,
        "infooutput.generated.documents.v1": lambda ctx: _render_infooutput_documents(ctx, generated_only=True),
        "infooutput.infosite.stats.v1": _render_infosite_dashboard_stats,
        "infooutput.infosite.projects.v1": _render_infosite_dashboard_projects,
        "infooutput.infosite.workflow.import.v1": _render_infosite_import_workflow,
        "infooutput.infosite.workflow.refine.v1": _render_infosite_refine_workflow,
        "infooutput.quiz.overview.v1": _render_infooutput_quiz_overview,
        "infooutput.quiz.status.v1": _render_infooutput_quiz_status,
        "settings.layout.registry.v1": lambda ctx: render_fragment("settings_layout_registry", {
            "active_area": ctx["config_summary"].get("active_area", "settings"),
            "builder_url": layout_builder_url("settings", "overview"),
        }),
        "settings.config.summary.v1": lambda ctx: render_fragment("settings_config_summary", {"config_summary": ctx["config_summary"]}),
        "settings.layout.preview.v1": lambda ctx: render_fragment("settings_layout_preview", {"active_domain": ctx["active_domain"]}),
    }


def _adapter_domain_overview(spec: Any) -> dict[str, Any]:
    domain_rows = domain_registry_overview("default")
    rows = tuple(
        {
            "id": str(row.get("domain_key") or row.get("display_name") or index),
            "label": str(row.get("display_name") or "Domain"),
            "value": f"{row.get('knowledge_sources', 0)} sources / {row.get('knowledge_records', 0)} records",
            "url": "/data-sources/",
        }
        for index, row in enumerate(domain_rows[:5])
    )
    return _TABLE_ADAPTER.adapt(
        DataSourceSpec(
            source_id=spec.widget_id,
            source_type="table",
            label=spec.label,
            description=spec.description,
            stats=(("Domains", str(len(domain_rows))), ("Active", "default")),
            rows=rows,
            links=(("Open data sources", "/data-sources/"),),
            detail_url_template="/data-sources/",
        )
    )


def _adapter_datasource_summary(spec: Any) -> dict[str, Any]:
    summary = domain_knowledge_summary("default")
    return _TABLE_ADAPTER.adapt(
        DataSourceSpec(
            source_id=spec.widget_id,
            source_type="table",
            label=spec.label,
            description=spec.description,
            stats=(("Sources", str(int(summary["sources"]))), ("Records", str(int(summary["records"]))), ("Artifacts", str(int(summary["artifacts"])))),
            rows=(),
            links=(("Open data sources", "/data-sources/"),),
        )
    )


def _adapter_import_quick(spec: Any) -> dict[str, Any]:
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": [],
        "rows": [],
        "links": _preview_links(("Workspace", "/data-sources/workspace/"), ("PDF jobs", "/data-sources/pdf/"), ("Sources", "/data-sources/sources/")),
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


def _adapter_admin_sync(spec: Any) -> dict[str, Any]:
    local_node = NodeConfig.objects.filter(node_id=current_node_id()).first()
    sync_run_count = SyncRun.objects.count()
    labels = (
        ("Role", local_node.role if local_node else "standalone"),
        ("Enabled", "yes" if local_node and local_node.is_enabled else "no"),
        ("Runs", str(sync_run_count)),
    )
    links = [("Open sync admin", "/admin-overview/sync/")]
    if local_node and local_node.role == "host":
        links.append(("Domain management", "/admin-overview/domains/"))
    return {
        "widget_id": spec.widget_id,
        "label": spec.label,
        "description": spec.description,
        "stats": _preview_stats(*labels),
        "rows": [],
        "links": _preview_links(*links),
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


@register_integration_adapter("admin.sync")
def _registered_admin_sync(spec: Any) -> dict[str, Any]:
    return _adapter_admin_sync(spec)


def render_widget_data(widget_id: str) -> dict[str, Any]:
    spec = widget_by_id(widget_id)
    if spec is None:
        return {"widget_id": widget_id, "label": widget_id, "description": "", "stats": [], "rows": [], "links": []}
    return resolve_integration_adapter(widget_adapter_key(widget_id), _widget_preview_from_spec)(spec)


def render_widget_html(widget_id: str) -> str:
    return render_card(render_widget_data(widget_id))


def render_widget_stats(widget_id: str) -> str:
    return render_fragment("stats", {"widget": render_widget_data(widget_id)})


def build_widget_preview_payload(*, widget_ids: list[str], active_domain: str) -> list[dict[str, Any]]:
    from .widget_catalog_preview import build_catalog_preview_context

    context = build_catalog_preview_context(active_domain)
    return [
        preview_payload_for_widget(widget_id, active_domain=active_domain, preview_context=context)
        for widget_id in widget_ids if widget_by_id(widget_id) is not None
    ]


def build_data_sources_widget_cards(
    *,
    request: Any,
    active_domain: str,
    all_domains: list[dict[str, Any]],
    active_domain_state: dict[str, Any],
    markdown_count: int,
    markdown_files: list[dict[str, Any]],
    display_mode: str,
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
        handler = handlers.get(spec.widget_id)
        context = {
            "active_domain": active_domain,
            "active_domain_state": active_domain_state,
            "all_domains": all_domains,
            "sources": sources,
            "markdown_count": markdown_count,
            "markdown_files": markdown_files or [],
            "display_mode": display_mode,
            "owl_sources": owl_sources,
            "ontology_count": ontology_count,
            "ontology_dir": ontology_dir,
            "pdf_count": pdf_count,
            "csrf_token": csrf_token,
            "pdf_jobs": pdf_jobs,
            "jira_issues": jira_issues,
            "widget_id": spec.widget_id,
        }
        if handler is None:
            raise ValueError(f"No datasource widget renderer registered for {spec.widget_id}")
        body = handler(context)
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_sources_widget_cards(
    *,
    request: Any,
    ctx: dict[str, Any],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    """Cards for the sources browser; ``ctx`` comes from ``views_data_sources.sources``."""
    from markupsafe import Markup, escape

    csrf_token = get_token(request) if request is not None else ""
    hidden = Markup(f'<input type="hidden" name="csrfmiddlewaretoken" value="{escape(csrf_token)}">') + Markup("").join(
        Markup(f'<input type="hidden" name="{escape(key)}" value="{escape(value)}">')
        for key, value in ctx["filter_params"].items()
        if value
    )
    shared = {**ctx, "csrf_token": csrf_token, "hidden": hidden}
    templates = {
        "datasources.sources.list.v1": "sources_list",
        "datasources.sources.unimported.v1": "sources_unimported",
    }
    handlers = _widget_fragment_handlers()
    datasource_context = None
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None or spec.widget_id in seen:
            continue
        seen.add(spec.widget_id)
        template = templates.get(spec.widget_id)
        if template is not None:
            body = render_fragment(template, shared)
        else:
            handler = handlers.get(spec.widget_id)
            if handler is None or spec.area != "datasources":
                raise ValueError(f"No sources-browser widget renderer registered for {spec.widget_id}")
            if datasource_context is None:
                datasource_context = _sources_datasource_context(shared)
            body = handler({**datasource_context, "widget_id": spec.widget_id})
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def _sources_datasource_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Supply the same domain data for movable datasource widgets on the browser."""
    from .services import (
        display_data_path,
        jira_issue_count,
        semantic_domain_states,
        workspace_markdown_files,
        workspace_ontology_files,
    )

    domain = ctx["active_domain"]
    states = semantic_domain_states()
    state = next((item for item in states if item.get("domain") == domain), {})
    markdown_files = workspace_markdown_files(domain=domain)
    ontology_files = workspace_ontology_files(domain=domain)
    sources = ctx["sources"]
    return {
        **ctx,
        "active_domain_state": state,
        "all_domains": states,
        "markdown_files": markdown_files,
        "markdown_count": len(markdown_files),
        "display_mode": ctx["display"],
        "ontology_count": len(ontology_files),
        "ontology_dir": display_data_path(state.get("ontology_dir")),
        "owl_sources": sum(source.source_type == "owl" for source in sources),
        "pdf_count": int(state.get("pdf_files", 0) or 0),
        "pdf_jobs": state.get("pdf_jobs") or {
            "pending": 0, "processing": 0, "done": 0, "failed": 0, "total": 0,
        },
        "jira_issues": jira_issue_count(domain),
    }


def build_workspace_widget_cards(
    *,
    request: Any,
    active_domain: str,
    all_domains: list[dict[str, Any]],
    active_domain_state: dict[str, Any],
    markdown_count: int,
    markdown_files: list[dict[str, Any]] | None = None,
    display_mode: str = "cards",
    query: str = "",
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
        handler = handlers.get(spec.widget_id)
        if handler is None:
            raise ValueError(f"No workspace widget renderer registered for {spec.widget_id}")
        body = handler({
            "active_domain": active_domain,
            "active_domain_state": active_domain_state,
            "all_domains": all_domains,
            "sources": sources,
            "markdown_count": markdown_count,
            "markdown_files": markdown_files,
            "display_mode": display_mode,
            "query": query,
            "owl_sources": 0,
            "ontology_count": 0,
            "ontology_dir": "",
            "pdf_count": 0,
            "pdf_jobs": {"pending": 0, "processing": 0, "done": 0, "failed": 0, "total": 0},
            "csrf_token": csrf_token,
            "jira_issues": 0,
            "widget_id": spec.widget_id,
        })
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_knowledge_widget_cards(
    *,
    active_domain: str,
    scoped_knowledge: dict[str, Any],
    quick_links: list[tuple[str, str, str]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
    term_count: int | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        body = handler({
            "active_domain": active_domain,
            "scoped_knowledge": scoped_knowledge,
            "quick_links": quick_links,
            "term_count": term_count or 0,
        }) if handler else f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_output_widget_cards(
    *,
    active_domain: str,
    domain_stats: list[dict[str, Any]],
    domain_documents: list[Any],
    recent_projects: list[Any],
    formats: list[dict[str, Any]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
    infosite_projects: list[Any] | None = None,
    infosite_stats: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    infosite_projects = infosite_projects if infosite_projects is not None else []
    infosite_stats = infosite_stats if infosite_stats is not None else {}
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        body = handler({
            "active_domain": active_domain,
            "domain_stats": domain_stats,
            "domain_documents": domain_documents,
            "recent_projects": recent_projects,
            "formats": formats,
            "infosite_projects": infosite_projects,
            "infosite_stats": infosite_stats,
        }) if handler else f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards


def build_admin_widget_cards(
    *,
    active_domain: str,
    domain_rows: list[dict[str, Any]],
    widget_ids: list[str],
    widget_widths: dict[str, int] | None = None,
    domain_states: list[dict[str, Any]] | None = None,
    layout: dict[str, Any] | None = None,
    csrf_token: str = "",
    domain_management_url: str = "/admin-overview/domains/",
    status_url: str = "/admin-overview/status/",
    sync_runs: list[Any] | None = None,
    sync_jobs: list[Any] | None = None,
    local_node: Any | None = None,
    runtime_node: Any | None = None,
    master_domain_catalog: dict[str, Any] | None = None,
    master_domain_catalog_error: str = "",
    known_hosts: list[Any] | None = None,
    sync_admin_url: str = "/admin-overview/sync/",
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    handlers = _widget_fragment_handlers()
    domain_states = domain_states if domain_states is not None else []
    layout = layout if layout is not None else {}
    sync_runs = sync_runs if sync_runs is not None else []
    sync_jobs = sync_jobs if sync_jobs is not None else []
    known_hosts = known_hosts if known_hosts is not None else []
    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        handler = handlers.get(widget_id)
        if widget_id == "admin.domain.management.v1":
            body = handler({
                "domain_states": domain_states,
                "active_domain": active_domain,
                "csrf_token": csrf_token,
                "domain_management_url": domain_management_url,
            })
        elif widget_id == "admin.domain.create.v1":
            body = handler({
                "csrf_token": csrf_token,
                "domain_management_url": domain_management_url,
            })
        elif widget_id == "admin.system.status.v1":
            body = handler({
                "active_domain": active_domain,
                "registered_domain_count": len(domain_states),
                "layout": layout,
                "status_url": status_url,
            })
        elif widget_id in {"admin.sync.overview.v1", "admin.sync.history.v1", "admin.sync.catalog.v1", "admin.sync.hosts.v1"}:
            body = handler({
                "active_domain": active_domain,
                "local_node": local_node,
                "runtime_node": runtime_node,
                "sync_runs": sync_runs,
                "sync_jobs": sync_jobs,
                "master_domain_catalog": master_domain_catalog,
                "master_domain_catalog_error": master_domain_catalog_error,
                "known_hosts": known_hosts,
                "sync_admin_url": sync_admin_url,
                "domain_management_url": domain_management_url,
            })
        elif widget_id == "admin.workspace.config.v1":
            body = render_fragment("admin_workspace_config", {
                "active_domain": active_domain, "knowledge_root": "/data/knowledge",
            })
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
            body = handler({"config_summary": config_summary, "active_domain": active_domain})
        elif handler:
            body = handler({"config_summary": config_summary, "active_domain": active_domain})
        else:
            body = f"<p>{spec.description}</p>"
        cards.append(_build_widget_card(body, spec, widget_widths=widget_widths))
    return cards
