from __future__ import annotations

import json
from urllib.parse import urlencode

from django.core.cache import cache
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .dashboard_registry import (
    builtin_areas,
    default_widget_ids_for_area,
    frontpage_aggregate_widgets,
    widget_by_id,
    widget_hierarchy,
    widget_ids,
)
from .infosite_models import Domain, GeneratedDocument
from .page_widgets import (
    build_admin_widget_cards,
    build_knowledge_widget_cards,
    build_output_widget_cards,
    build_settings_widget_cards,
    build_widget_preview_payload,
)
from .services import (
    available_data_domains,
    data_layout_snapshot,
    display_data_path,
    domain_knowledge_summary,
    domain_registry_overview,
    normalize_semantic_domain,
    run_dashboard_task,
    semantic_monitoring_snapshot,
    semantic_terms,
)
from .views_common import (
    _active_semantic_domain,
    _display_mode,
    _frontpage_dashboard_widgets,
    _format_task_message,
    _int_param,
    _int_post_param,
    _load_dashboard_widget_ids,
    _load_dashboard_widget_widths,
    _obj_attr_or_key,
    _paginate_items,
    _redirect_with_filters,
    _selected_markdown,
    _sync_dashboard_selection,
)

_JIRA_CHAT_SESSION_KEY = "jira_support_chat_history"
_OLLAMA_CHAT_SESSION_KEY = "ollama_chat_history"
_KNOWLEDGE_API_URL_SESSION_KEY = "knowledge_api_url"
_SEMANTIC_DOMAIN_SESSION_KEY = "semantic_active_domain"
_DASHBOARD_BUILDER_SESSION_KEY = "dashboard_builder_widgets"

def dashboard(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    scoped_knowledge = domain_knowledge_summary(active_domain)
    sources = scoped_knowledge["recent_sources"]
    artifacts = scoped_knowledge["recent_artifacts"]
    configured_widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="dashboard",
        fallback=list(frontpage_aggregate_widgets()),
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="dashboard")
    settings_widget_ids = _load_dashboard_widget_ids(request, area_key="settings", fallback=[])
    configured_widget_ids = [
        widget_id
        for widget_id in [*settings_widget_ids, *configured_widget_ids]
        if widget_id and widget_id not in {""}
    ]
    seen: set[str] = set()
    deduped_widget_ids: list[str] = []
    for widget_id in configured_widget_ids:
        if widget_id in seen:
            continue
        seen.add(widget_id)
        deduped_widget_ids.append(widget_id)
    configured_widget_ids = deduped_widget_ids
    dashboard_widgets = []
    for widget_id in configured_widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        if widget_id == "datasources.overview.summary.v1":
            recent_source = sources[0] if sources else None
            recent_source_title = _obj_attr_or_key(recent_source, "title", "—")
            label, default_size, body = (
                "Data Sources Overview",
                "wide",
                "<table class='dashboard-monitor-table' style='width:100%; border-collapse:collapse;'><tbody>"
                f"<tr><th style='text-align:left; width:60%;'>Sources</th><td>{int(scoped_knowledge['sources'])}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Recent source</th><td>{recent_source_title}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Active domain</th><td>{active_domain}</td></tr>"
                "</tbody></table>"
                + (
                    "<ul style='margin:10px 0 0; padding-left:18px;'>"
                    + "".join(
                        f"<li><a href='{reverse('source-detail', args=[_obj_attr_or_key(source, 'source_id', '')])}'>{_obj_attr_or_key(source, 'title', 'Untitled source')}</a></li>"
                        for source in sources[:3]
                    )
                    + "</ul>"
                    if sources else "<p class='muted' style='margin:10px 0 0;'>No sources yet.</p>"
                ),
            )
        elif widget_id == "knowledge.overview.summary.v1":
            label, default_size, body = (
                "Knowledge Overview",
                "balanced",
                "<table class='dashboard-monitor-table' style='width:100%; border-collapse:collapse;'><tbody>"
                f"<tr><th style='text-align:left; width:60%;'>Sources</th><td>{int(scoped_knowledge['sources'])}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Records</th><td>{int(scoped_knowledge['records'])}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Artifacts</th><td>{int(scoped_knowledge['artifacts'])}</td></tr>"
                "</tbody></table>"
                "<div class='dashboard-actions' style='margin-top:10px;'>"
                f"<a href='{reverse('knowledge')}'><button type='button'>Open knowledge</button></a>"
                f"<a href='{reverse('records')}'><button type='button'>Records</button></a>"
                "</div>",
            )
        elif widget_id == "infooutput.overview.summary.v1":
            recent_docs = (
                GeneratedDocument.objects.filter(project__domain=active_domain)
                .select_related("project")
                .order_by("-generated_at")[:3]
            )
            label, default_size, body = (
                "Info Output Overview",
                "balanced",
                "<table class='dashboard-monitor-table' style='width:100%; border-collapse:collapse;'><tbody>"
                f"<tr><th style='text-align:left; width:60%;'>Generated documents</th><td>{len(recent_docs)}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Artifacts</th><td>{int(scoped_knowledge['artifacts'])}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Active domain</th><td>{active_domain}</td></tr>"
                "</tbody></table>"
                + (
                    "<ul style='margin:10px 0 0; padding-left:18px;'>"
                   + "".join(
                       f"<li>{_obj_attr_or_key(doc, 'display_path', _obj_attr_or_key(doc, 'file_path', 'Generated document'))}</li>"
                       for doc in recent_docs
                   )
                   + "</ul>"
                   if recent_docs else "<p class='muted' style='margin:10px 0 0;'>No generated documents yet.</p>"
                ),
            )
        else:
            if spec.area in {"admin", "settings"}:
                domain_rows = domain_registry_overview(active_domain)
                helper_cards = build_admin_widget_cards(
                    active_domain=active_domain,
                    domain_rows=domain_rows,
                    widget_ids=[widget_id],
                    widget_widths=widget_widths,
                ) if spec.area == "admin" else build_settings_widget_cards(
                    active_domain=active_domain,
                    config_summary={"active_area": spec.area, "active_domain": active_domain},
                    widget_ids=[widget_id],
                    widget_widths=widget_widths,
                )
                helper_card = helper_cards[0] if helper_cards else {"label": spec.label, "body": f"<p class='muted'>{spec.description}</p>", "width": widget_widths.get(widget_id, spec.default_w if spec is not None else 6)}
                label, default_size, body = (helper_card["label"], spec.default_size, helper_card["body"])
            else:
                label, default_size, body = (
                    spec.label,
                    spec.default_size,
                    f"<p class='muted' style='margin:0;'>{spec.description}</p>",
                )
        dashboard_widgets.append({
            "widget_id": widget_id,
            "label": label,
            "default_size": default_size,
            "body": body,
            "width": widget_widths.get(widget_id, spec.default_w if spec is not None else 6),
        })

    if not dashboard_widgets:
        dashboard_widgets = _frontpage_dashboard_widgets(
            request,
            active_domain=active_domain,
            source_count=int(scoped_knowledge["sources"]),
            record_count=int(scoped_knowledge["records"]),
            artifact_count=int(scoped_knowledge["artifacts"]),
            sources=sources,
            artifacts=artifacts,
        )
    return render(
        request,
        "kicli_django/dashboard.html",
        {
            "sources": sources[:8],
            "artifacts": artifacts[:8],
            "available_domains": available_data_domains(),
            "layout": {
                **data_layout_snapshot(active_domain),
                "active_markdown_dir": display_data_path(data_layout_snapshot(active_domain)["active_markdown_dir"]),
                "active_jira_dir": display_data_path(data_layout_snapshot(active_domain)["active_jira_dir"]),
            },
            "active_domain": active_domain,
            "source_count": int(scoped_knowledge["sources"]),
            "artifact_count": int(scoped_knowledge["artifacts"]),
            "record_count": int(scoped_knowledge["records"]),
            "dashboard_widgets": dashboard_widgets,
            "task_status": request.GET.get("task_status", "").strip(),
            "task_message": request.GET.get("task_message", "").strip(),
        },
    )


@vary_on_cookie
@require_GET

def dashboard_monitoring(request: HttpRequest):
    return JsonResponse(semantic_monitoring_snapshot(_active_semantic_domain(request)))


@require_http_methods(["POST"])

def dashboard_task_action(request: HttpRequest):
    task_name = request.POST.get("task_name", "").strip()
    if not task_name:
        return HttpResponseBadRequest("task_name missing")
    domain = normalize_semantic_domain(
        request.POST.get("domain", "").strip() or request.session.get(_SEMANTIC_DOMAIN_SESSION_KEY, "")
    )
    request.session[_SEMANTIC_DOMAIN_SESSION_KEY] = domain
    request.session.modified = True
    target_domain = request.POST.get("target_domain", "").strip() or None
    try:
        result = run_dashboard_task(task_name, domain=domain, target_domain=target_domain)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    if task_name == "domain_create" and result.get("domain"):
        request.session[_SEMANTIC_DOMAIN_SESSION_KEY] = str(result["domain"])
        request.session.modified = True
    task_status = "ok"
    task_message = _format_task_message(result)
    query = urlencode(
        {
            "domain": domain,
            "task_status": task_status,
            "task_message": f"{task_name}: {task_message}",
        }
    )
    return HttpResponseRedirect(f"{reverse('dashboard')}?{query}")


@require_GET

def knowledge_landing_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    scoped_knowledge = domain_knowledge_summary(active_domain)
    configured_widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="knowledge",
        fallback=default_widget_ids_for_area("knowledge"),
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="knowledge")
    widget_cards = build_knowledge_widget_cards(
        active_domain=active_domain,
        scoped_knowledge=scoped_knowledge,
        quick_links=[
            ("Knowledge API", "/knowledge/api/", "Search knowledge sources and inspect the browser context."),
            ("Sources", "/data-sources/sources/", "Browse all ingested sources in the active domain."),
            ("Records", "/knowledge/records/", "Inspect available records and their metadata."),
            ("Artifacts", "/knowledge/artifacts/", "Review generated artifacts and summaries."),
            ("Jobs", "/knowledge/jobs/", "Check background tasks and sync jobs."),
            ("Knowledge Blocks", "/output/infosite/dashboard/", "Open Infosite projects to extract and inspect knowledge blocks."),
            ("Semantic Layer", "/knowledge/semantic/", "Explore the semantic vocabulary, term extraction and concept graph."),
            ("Support Chat", "/knowledge/chat/support/", "Ask questions across the available source types."),
            ("Ollama Chat", "/knowledge/chat/ollama/", "Local LLM chat for ad-hoc exploration of the knowledge base."),
        ],
        widget_ids=configured_widget_ids,
        widget_widths=widget_widths,
    )
    return render(
        request,
        "kicli_django/knowledge_landing.html",
        {
            "active_domain": active_domain,
            "source_count": int(scoped_knowledge["sources"]),
            "record_count": int(scoped_knowledge["records"]),
            "artifact_count": int(scoped_knowledge["artifacts"]),
            "widget_cards": widget_cards,
            "quick_links": [
                ("Knowledge API", "/knowledge/api/", "Search knowledge sources and inspect the browser context."),
                ("Sources", "/data-sources/sources/", "Browse all ingested sources in the active domain."),
                ("Records", "/knowledge/records/", "Inspect available records and their metadata."),
                ("Artifacts", "/knowledge/artifacts/", "Review generated artifacts and summaries."),
                ("Jobs", "/knowledge/jobs/", "Check background tasks and sync jobs."),
                ("Knowledge Blocks", "/output/infosite/dashboard/", "Open Infosite projects to extract and inspect knowledge blocks."),
                ("Semantic Layer", "/knowledge/semantic/", "Explore the semantic vocabulary, term extraction and concept graph."),
                ("Support Chat", "/knowledge/chat/support/", "Ask questions across the available source types."),
                ("Ollama Chat", "/knowledge/chat/ollama/", "Local LLM chat for ad-hoc exploration of the knowledge base."),
            ],
        },
    )


@vary_on_cookie
@require_GET

def semantic_landing_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    terms = semantic_terms(domain=active_domain)
    return render(
        request,
        "kicli_django/semantic_landing.html",
        {
            "active_domain": active_domain,
            "term_count": len(terms),
            "quick_links": [
                ("Semantic Layer", "/knowledge/semantic/terms/", "Explore the semantic vocabulary and concept graph."),
                ("Support Chat", "/knowledge/chat/support/", "Use a source-agnostic semantic chat across domain data."),
                ("Knowledge API", "/knowledge/api/", "Inspect the knowledge graph and browser context."),
                ("Data Sources", "/data-sources/", "Return to the source overview and import entry points."),
            ],
        },
    )


@vary_on_cookie
@require_GET

def output_landing_view(request: HttpRequest):
    """Landing page for the 'Info Output' area: formats that publish
    processed knowledge outward (currently Infosite; Quiz is a placeholder
    for a future format, see docs/navigation-ia-proposal.md).

    Also shows a per-domain overview of generated InfoSite output files
    (GeneratedDocument), analogous to the Data-Sources domain table, plus a
    flat table of the most recent 25 generated documents across domains.
    """
    active_domain = _active_semantic_domain(request)
    configured_widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="infooutput",
        fallback=default_widget_ids_for_area("infooutput"),
    )
    domain_stats = []
    for domain in Domain.objects.all():
        docs = GeneratedDocument.objects.filter(project__domain=domain.slug)
        counts = docs.aggregate(
            total=Count("id"),
            none=Count("id", filter=Q(review_status="none")),
            in_review=Count("id", filter=Q(review_status="in_review")),
            approved=Count("id", filter=Q(review_status="approved")),
            rejected=Count("id", filter=Q(review_status="rejected")),
        )
        domain_stats.append(
            {
                "slug": domain.slug,
                "display_name": domain.display_name or domain.slug,
                "is_active": domain.slug == active_domain,
                **counts,
            }
        )

    recent_documents = (
        GeneratedDocument.objects.select_related("project")
        .prefetch_related("used_sources")
        .order_by("-generated_at")[:25]
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="infooutput")
    widget_cards = build_output_widget_cards(
        active_domain=active_domain,
        domain_stats=domain_stats,
        recent_documents=recent_documents,
        formats=[
            {
                "label": "Infosite",
                "url": "/output/infosite/dashboard/",
                "status": "aktiv",
                "description": "Browsable Markdown-Präsentationen aus Quelldokumenten generieren, mit AI-Refinement.",
            },
            {
                "label": "Quiz",
                "url": None,
                "status": "geplant",
                "description": "Noch kein Konzept — geplantes Ausgabeformat zur Wissensabfrage aus Knowledge Blocks.",
            },
        ],
        widget_ids=configured_widget_ids,
        widget_widths=widget_widths,
    )

    return render(
        request,
        "kicli_django/output_landing.html",
        {
            "active_domain": active_domain,
            "domain_stats": domain_stats,
            "recent_documents": recent_documents,
            "widget_cards": widget_cards,
            "formats": [
                {
                    "label": "Infosite",
                    "url": "/output/infosite/dashboard/",
                    "status": "aktiv",
                    "description": "Browsable Markdown-Präsentationen aus Quelldokumenten generieren, mit AI-Refinement.",
                },
                {
                    "label": "Quiz",
                    "url": None,
                    "status": "geplant",
                    "description": "Noch kein Konzept — geplantes Ausgabeformat zur Wissensabfrage aus Knowledge Blocks.",
                },
            ],
        },
    )


@require_GET

def output_quiz_view(request: HttpRequest):
    """Placeholder page for the planned Quiz output format (no data model or
    generator yet, see docs/navigation-ia-proposal.md, offene Frage 6)."""
    active_domain = _active_semantic_domain(request)
    return render(
        request,
        "kicli_django/output_quiz.html",
        {"active_domain": active_domain},
    )


@require_GET

def admin_overview_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    configured_widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="admin",
        fallback=default_widget_ids_for_area("admin"),
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="admin")
    domain_rows = domain_registry_overview(active_domain)
    widget_cards = build_admin_widget_cards(
        active_domain=active_domain,
        domain_rows=domain_rows,
        widget_ids=configured_widget_ids,
        widget_widths=widget_widths,
    )
    return render(
        request,
        "kicli_django/admin_overview.html",
        {
            "active_domain": active_domain,
            "widget_cards": widget_cards,
            "quick_links": [
                ("Domain overview", "/admin-overview/", "Current domain and admin-level system facts."),
                ("Settings", "/settings/", "Configuration and layout controls."),
                ("Dashboard Builder", "/settings/layout/builder/?area=admin", "Arrange the admin area widgets."),
            ],
        },
    )


@require_GET

def settings_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="settings",
        fallback=default_widget_ids_for_area("settings"),
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="settings")
    config_summary = {
        "active_area": "settings",
        "active_domain": active_domain,
        "llm_provider": "ki",
        "knowledge_root": "/data/knowledge",
        "infosite_enabled": True,
    }
    widget_cards = build_settings_widget_cards(
        active_domain=active_domain,
        config_summary=config_summary,
        widget_ids=widget_ids,
        widget_widths=widget_widths,
    )
    return render(
        request,
        "kicli_django/settings.html",
        {
            "active_domain": active_domain,
            "widget_cards": widget_cards,
            "quick_links": [
                ("Configuration", "/settings/config/", "View active AppConfig values (LLM providers, knowledge paths, infosite, jira). Secrets are shown as set/not set only."),
                ("Dashboard Builder", "/settings/layout/builder/", "Arrange widgets by area and drag them into the active layout grid."),
            ],
        },
    )


# Config fields considered secret: never rendered in plaintext, only "gesetzt"/"nicht gesetzt".
_CONFIG_SECRET_FIELDS = {"ki_api_key", "openai_api_key", "jira_api_token"}

# Grouping of AppConfig fields into the settings sections shown in the GUI,
# mirroring the resolved YAML sections owned by ki-knowledge and ki-core.
_CONFIG_SECTIONS = [
    (
        "LLM Provider",
        "llm",
        ["ki_base_url", "ki_api_key", "ki_model", "ki_endpoint", "ollama_base_url", "ollama_model", "openai_api_key", "openai_model", "openai_base_url"],
    ),
    (
        "Knowledge Base",
        "knowledge",
        [
            "knowledge_data_root",
            "knowledge_markdown_root",
            "knowledge_jira_root",
            "knowledge_ontology_root",
            "knowledge_pdf_root",
            "knowledge_cache_db",
            "knowledge_graph_db",
            "knowledge_embed_model",
            "knowledge_default_domain",
        ],
    ),
    (
        "Infosite",
        "infosite",
        ["infosite_enabled", "infosite_title", "infosite_output_base_dir", "infosite_domain"],
    ),
    (
        "Jira",
        "jira",
        [
            "jira_url",
            "jira_username",
            "jira_api_token",
            "jira_csv_path",
            "jira_cache_db",
            "jira_graph_db",
            "jira_graph_cypher_path",
            "jira_csv_delimiter",
            "jira_csv_encoding",
            "jira_timeline_days",
            "jira_embed_model",
            "jira_use_hybrid_search",
            "jira_use_graph",
            "jira_cache_refresh",
        ],
    ),
    (
        "HTTP",
        "http",
        ["request_timeout", "http_verify_ssl"],
    ),
]


@require_GET

def settings_config_view(request: HttpRequest):
    """Read-only overview of the active AppConfig. Secrets are never
    rendered in plaintext, only as "gesetzt"/"nicht gesetzt"."""
    active_domain = _active_semantic_domain(request)
    from dataclasses import fields as dataclass_fields

    from ki_core.config import _find_yaml_config_path  # local import: optional dependency boundary
    from ki_knowledge.app_config import AppConfig

    config_path = _find_yaml_config_path()
    config = AppConfig.from_yaml()
    available_fields = {field.name for field in dataclass_fields(AppConfig) if field.name != "raw"}

    sections = []
    for title, key, fields in _CONFIG_SECTIONS:
        rows = []
        for field_name in fields:
            if field_name not in available_fields:
                continue
            raw_value = getattr(config, field_name, None)
            is_secret = field_name in _CONFIG_SECRET_FIELDS
            if is_secret:
                display_value = "✅ gesetzt" if raw_value else "— nicht gesetzt"
            else:
                display_value = raw_value if raw_value not in (None, "") else "—"
            rows.append({"field": field_name, "value": display_value, "is_secret": is_secret})
        sections.append({"title": title, "key": key, "rows": rows})

    return render(
        request,
        "kicli_django/settings_config.html",
        {
            "active_domain": active_domain,
            "config_path": str(config_path) if config_path else None,
            "sections": sections,
        },
    )


@require_GET

def layout_settings_view(request: HttpRequest):
    """Legacy alias: the drag-and-drop builder is the only supported layout editor."""
    return HttpResponseRedirect(reverse("settings-layout-builder"))


@require_http_methods(["GET", "POST"])

def dashboard_builder_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    registry = widget_hierarchy()
    area_key = request.GET.get("area", request.POST.get("area", "settings")).strip() or "settings"
    if area_key not in set(builtin_areas()):
        area_key = "settings"

    if request.method == "POST":
        selected_widget_ids = _sync_dashboard_selection(request, area_key=area_key)
        cache.clear()
    else:
        selected_widget_ids = _load_dashboard_widget_ids(
            request,
            area_key=area_key,
            fallback=default_widget_ids_for_area(area_key),
        )
        request.session[_DASHBOARD_BUILDER_SESSION_KEY] = selected_widget_ids
        request.session.modified = True

    from .dashboard_registry import widget_by_id, widget_ids
    from .infosite_models import DashboardWidgetPlacement

    placement_by_widget = {
        item.widget_id: item
        for item in DashboardWidgetPlacement.objects.filter(
            dashboard__domain__slug=active_domain,
            dashboard__area_key=area_key,
            dashboard__owner=request.user if getattr(request.user, 'is_authenticated', False) else None,
        )
    }

    selected_widget_meta = []
    for widget_id in selected_widget_ids:
        spec = widget_by_id(widget_id)
        if spec is None:
            continue
        placement = placement_by_widget.get(widget_id)
        width = placement.w if placement is not None else spec.default_w
        selected_widget_meta.append({"spec": spec, "width": width})

    all_widget_ids = list(widget_ids())
    unused_widget_ids = [widget_id for widget_id in all_widget_ids if widget_id not in selected_widget_ids]
    unused_specs = [
        widget_by_id(widget_id)
        for widget_id in unused_widget_ids
        if widget_by_id(widget_id) is not None and widget_by_id(widget_id).area == area_key
    ]
    widget_catalog = [
        widget_by_id(widget_id)
        for widget_id in all_widget_ids
        if widget_by_id(widget_id) is not None
    ]
    area_tabs = [
        {"key": area, "label": area.replace("_", " ").title()} for area in builtin_areas()
    ]
    widget_preview_payload = build_widget_preview_payload(widget_ids=all_widget_ids)
    widget_preview_payload_json = json.dumps(widget_preview_payload, ensure_ascii=False)

    widget_area_entries = []
    for area in builtin_areas():
        area_tree = registry.get(area, {})
        category_entries = []
        for category_name, category_value in area_tree.items():
            if category_name == "_widgets":
                continue
            category_entries.append({
                "name": category_name,
                "widgets": category_value.get("_widgets", []),
            })
        widget_area_entries.append({
            "area": area,
            "categories": category_entries,
        })

    return render(
        request,
        "kicli_django/dashboard_builder.html",
        {
            "active_domain": active_domain,
            "widget_area_entries": widget_area_entries,
            "selected_widgets": selected_widget_meta,
            "selected_widget_ids": selected_widget_ids,
            "unused_widgets": unused_specs,
            "area_key": area_key,
            "builtin_areas": builtin_areas(),
            "area_tabs": area_tabs,
            "widget_width_options": [3, 4, 6, 8, 9, 12],
        },
    )


@require_GET

def widget_catalog_view(request: HttpRequest):
    """A dedicated preview page for the canonical widget catalog and HTML output."""
    active_domain = _active_semantic_domain(request)
    area_filter = (request.GET.get("area", "all") or "all").strip().lower()
    catalog = [
        widget_by_id(widget_id)
        for widget_id in widget_ids()
        if widget_by_id(widget_id) is not None and (area_filter == "all" or widget_by_id(widget_id).area == area_filter)
    ]
    widget_payload = build_widget_preview_payload(widget_ids=[spec.widget_id for spec in catalog])
    payload_by_id = {item["widget_id"]: item for item in widget_payload}
    return render(
        request,
        "kicli_django/widget_catalog.html",
        {
            "active_domain": active_domain,
            "widget_catalog": catalog,
            "widget_preview_payload": widget_payload,
            "widget_preview_payload_json": json.dumps(widget_payload, ensure_ascii=False),
            "payload_by_id": payload_by_id,
            "area_filter": area_filter,
            "area_tabs": [{"key": "all", "label": "All"}] + [
                {"key": area, "label": area.replace("_", " ").title()} for area in builtin_areas()
            ],
        },
    )
