from __future__ import annotations

import json
from urllib.parse import urlencode

from requests.exceptions import RequestException

from django.contrib import messages
from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
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
from .infosite_models import Domain, GeneratedDocument, InfoSiteProject
from .infosite_models import NodeConfig, SyncRun, current_node_id
from .layout_targets import layout_builder_url, layout_targets_for_area
from widgetkit_django.registry import CallbackWidgetRegistry
from widgetkit_django.views import BuilderViewConfig, dashboard_builder_view as widgetkit_dashboard_builder_view
from .page_widgets import (
    build_admin_widget_cards,
    build_knowledge_widget_cards,
    build_output_widget_cards,
    build_settings_widget_cards,
    build_widget_preview_payload,
    render_widget_data,
)
from .widget_shells import widget_shell_builder_save_view, widget_shell_builder_view
from ..widgetkit_renderer import render_fragment
from .services import (
    available_data_domains,
    create_semantic_domain,
    data_layout_snapshot,
    delete_semantic_domain,
    display_data_path,
    domain_knowledge_summary,
    domain_registry_overview,
    normalize_semantic_domain,
    run_dashboard_task,
    semantic_domain_states,
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
from .layout_store import DjangoDashboardLayoutStore
from .distributed_api import (
    get_runtime_node_settings,
    list_known_hosts,
    persist_local_node_settings,
    safe_fetch_master_domain_catalog,
    send_host_pull_command,
    send_master_heartbeat,
)

_JIRA_CHAT_SESSION_KEY = "jira_support_chat_history"
_OLLAMA_CHAT_SESSION_KEY = "ollama_chat_history"
_KNOWLEDGE_API_URL_SESSION_KEY = "knowledge_api_url"
_SEMANTIC_DOMAIN_SESSION_KEY = "semantic_active_domain"
_DASHBOARD_BUILDER_SESSION_KEY = "dashboard_builder_widgets"


_WIDGETKIT_REGISTRY = CallbackWidgetRegistry(
    builtin_areas_fn=builtin_areas,
    widget_hierarchy_fn=widget_hierarchy,
    widget_ids_fn=lambda: list(widget_ids()),
    widget_by_id_fn=widget_by_id,
    default_widget_ids_for_area_fn=default_widget_ids_for_area,
)

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
        rendered = render_widget_data(widget_id)
        label, default_size, body = (rendered["label"], spec.default_size, rendered.get("body") or f"<p style='margin:0;'>{spec.description}</p>")
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
        quick_links=[],
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
            "quick_links": [],
        },
    )


@vary_on_cookie
@require_GET

def semantic_landing_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    terms = semantic_terms(domain=active_domain)
    scoped_knowledge = domain_knowledge_summary(active_domain)
    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="knowledge",
        fallback=default_widget_ids_for_area("knowledge", "semantic"),
        subpage_key="semantic",
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="knowledge", subpage_key="semantic")
    quick_links = [
        ("Semantic Layer", "/knowledge/semantic/terms/", "Explore the semantic vocabulary and concept graph."),
        ("Support Chat", "/knowledge/chat/support/", "Use a source-agnostic semantic chat across domain data."),
        ("Knowledge API", "/knowledge/api/", "Inspect the knowledge graph and browser context."),
        ("Data Sources", "/data-sources/", "Return to the source overview and import entry points."),
    ]
    widget_cards = build_knowledge_widget_cards(
        active_domain=active_domain,
        scoped_knowledge=scoped_knowledge,
        quick_links=quick_links,
        widget_ids=widget_ids,
        widget_widths=widget_widths,
        term_count=len(terms),
    )
    return render(
        request,
        "kicli_django/semantic_landing.html",
        {
            "active_domain": active_domain,
            "term_count": len(terms),
            "quick_links": quick_links,
            "widget_cards": widget_cards,
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
    domain_documents = (
        GeneratedDocument.objects.select_related("project")
        .filter(project__domain=active_domain)
        .order_by("-generated_at")[:10]
    )
    recent_projects = InfoSiteProject.objects.filter(domain=active_domain).order_by("-updated_at")[:10]
    widget_widths = _load_dashboard_widget_widths(request, area_key="infooutput")
    widget_cards = build_output_widget_cards(
        active_domain=active_domain,
        domain_stats=domain_stats,
        domain_documents=domain_documents,
        recent_projects=recent_projects,
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
    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="infooutput",
        fallback=default_widget_ids_for_area("infooutput", "quiz"),
        subpage_key="quiz",
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="infooutput", subpage_key="quiz")
    widget_cards = build_output_widget_cards(
        active_domain=active_domain,
        domain_stats=[],
        domain_documents=[],
        recent_projects=[],
        formats=[],
        widget_ids=widget_ids,
        widget_widths=widget_widths,
    )
    return render(
        request,
        "kicli_django/output_quiz.html",
        {
            "active_domain": active_domain,
            "widget_cards": widget_cards,
        },
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
    domain_states = semantic_domain_states()
    layout_raw = data_layout_snapshot(active_domain)
    sync_runs = list(SyncRun.objects.select_related("domain", "node").filter(domain__slug=active_domain).order_by("-started_at")[:12])
    local_node = persist_local_node_settings()
    runtime_node = get_runtime_node_settings()
    from ki_knowledge.services.distributed_sync_runner import get_job_store as get_sync_job_store
    sync_jobs = get_sync_job_store().list_jobs(domain=active_domain, limit=12)
    master_domain_catalog = None
    master_domain_catalog_error = ""
    if runtime_node.role == "host" and runtime_node.distributed_enabled:
        master_domain_catalog, master_domain_catalog_error = safe_fetch_master_domain_catalog()
    layout = {
        "data_root": display_data_path(layout_raw.get("data_root", "")),
        "active_markdown_dir": display_data_path(layout_raw.get("active_markdown_dir", "")),
        "active_jira_dir": display_data_path(layout_raw.get("active_jira_dir", "")),
    }
    widget_cards = build_admin_widget_cards(
        active_domain=active_domain,
        domain_rows=domain_rows,
        widget_ids=configured_widget_ids,
        widget_widths=widget_widths,
        domain_states=domain_states,
        layout=layout,
        csrf_token=get_token(request),
        sync_runs=sync_runs,
        sync_jobs=sync_jobs,
        local_node=local_node,
        runtime_node=runtime_node,
        master_domain_catalog=master_domain_catalog,
        master_domain_catalog_error=master_domain_catalog_error,
        known_hosts=list_known_hosts() if runtime_node.role == "master" else [],
    )
    return render(
        request,
        "kicli_django/admin_overview.html",
        {
            "active_domain": active_domain,
            "widget_cards": widget_cards,
            "quick_links": [
                ("Domain Management", "/admin-overview/domains/", "Domains anlegen, Datenverzeichnisse scannen und verwalten."),
                ("Distributed Sync", "/admin-overview/sync/", "Node-Konfiguration, Master-Katalog und Sync-Historie verwalten."),
                ("System Status", "/admin-overview/status/", "Laufzeitwerte, Pfade und Systemzustand prüfen."),
                ("Settings", "/settings/", "Configuration and layout controls."),
                ("Dashboard Builder", layout_builder_url("admin", "overview"), "Arrange the admin overview widgets."),
            ],
        },
    )


@require_http_methods(["GET", "POST"])
def admin_domain_management_view(request: HttpRequest):
    """Domain management page: create new domains, rescan data directories
    for domains that already exist on disk but are not yet registered, and
    remove domains that have no remaining source/db files.

    This closes the gap where ``create_semantic_domain``/``delete_semantic_domain``
    existed in the services layer but were never wired up to any view - there
    was no way to add a domain from the GUI. The page body reuses the
    ``admin_domain_create`` and ``admin_domain_management`` widgetkit fragments
    (also embedded as the ``admin.domain.create.v1`` and
    ``admin.domain.management.v1`` widget cards on the admin overview page),
    so both surfaces share one implementation.
    """

    active_domain = _active_semantic_domain(request)
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "create":
            new_domain = request.POST.get("domain", "").strip()
            try:
                result = create_semantic_domain(new_domain)
                messages.success(request, f"Domain '{result['domain']}' angelegt.")
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "scan":
            found = available_data_domains()
            messages.success(request, f"Datenverzeichnisse gescannt: {len(found)} Domain(s) gefunden ({', '.join(found) or '—'}).")
        elif action == "delete":
            target_domain = request.POST.get("domain", "").strip()
            try:
                result = delete_semantic_domain(target_domain)
                messages.success(request, f"Domain '{result['domain']}' entfernt ({len(result['removed'])} Datei(en)).")
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "sync_pull":
            try:
                result = run_dashboard_task("sync_pull_master", domain=active_domain)
                messages.success(
                    request,
                    f"Distributed-Sync-Job eingereiht. Worker starten mit "
                    f"'python manage.py process_distributed_sync_jobs --pending --domain {active_domain}'. "
                    f"{_format_task_message(result)}",
                )
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "sync_export":
            try:
                result = run_dashboard_task("sync_export_domain", domain=active_domain)
                messages.success(
                    request,
                    f"Distributed-Sync-Job eingereiht. Worker starten mit "
                    f"'python manage.py process_distributed_sync_jobs --pending --domain {active_domain}'. "
                    f"{_format_task_message(result)}",
                )
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "save_node_config":
            persist_local_node_settings(
                display_name=request.POST.get("display_name", "").strip(),
                role=request.POST.get("role", "").strip() or None,
                base_url=request.POST.get("base_url", "").strip(),
                sync_on_connect=request.POST.get("sync_on_connect", "").strip().lower() in {"1", "true", "yes", "on"},
                is_enabled=request.POST.get("is_enabled", "").strip().lower() in {"1", "true", "yes", "on"},
                sync_shared_secret=request.POST.get("sync_shared_secret", "").strip(),
            )
            messages.success(request, "Lokale Node-Konfiguration gespeichert und als aktive Runtime-Konfiguration übernommen.")
        elif action == "send_heartbeat":
            try:
                result = send_master_heartbeat()
                messages.success(request, f"Heartbeat gesendet. {_format_task_message(result)}")
            except Exception as exc:
                messages.error(request, f"Heartbeat fehlgeschlagen: {exc}")
        elif action == "adopt_master_domain":
            target_domain = request.POST.get("domain", "").strip()
            if not target_domain:
                messages.error(request, "Keine Domain zum Übernehmen angegeben.")
            else:
                Domain.objects.get_or_create(
                    slug=target_domain,
                    defaults={
                        "display_name": target_domain,
                        "home_node": "",
                        "sync_mode": "pull",
                        "visibility": "private",
                    },
                )
                try:
                    result = run_dashboard_task("sync_pull_master", domain=target_domain)
                    messages.success(
                        request,
                        f"Domain '{target_domain}' übernommen und Sync-Job eingereiht. Worker starten mit "
                        f"'python manage.py process_distributed_sync_jobs --pending --domain {target_domain}'. "
                        f"{_format_task_message(result)}",
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
        elif action == "run_sync_job":
            job_id = request.POST.get("job_id", "").strip()
            if not job_id:
                messages.error(request, "Keine Job-ID angegeben.")
            else:
                from ki_knowledge.services.distributed_sync_runner import run_sync_job

                try:
                    result = run_sync_job(job_id)
                    messages.success(
                        request,
                        f"Distributed-Sync-Job {job_id} ausgeführt. {_format_task_message(result)}",
                    )
                except Exception as exc:
                    messages.error(request, f"Distributed-Sync-Job {job_id} fehlgeschlagen: {exc}")
        else:
            return HttpResponseBadRequest("unknown action")
        return HttpResponseRedirect(reverse("admin-domains"))

    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="admin",
        fallback=default_widget_ids_for_area("admin", "domains"),
        subpage_key="domains",
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="admin", subpage_key="domains")
    domain_states = semantic_domain_states()
    domain_rows = domain_registry_overview(active_domain)
    sync_runs = list(SyncRun.objects.select_related("domain", "node").filter(domain__slug=active_domain).order_by("-started_at")[:12])
    local_node = persist_local_node_settings()
    runtime_node = get_runtime_node_settings()
    from ki_knowledge.services.distributed_sync_runner import get_job_store as get_sync_job_store
    sync_jobs = get_sync_job_store().list_jobs(domain=active_domain, limit=12)
    master_domain_catalog = None
    master_domain_catalog_error = ""
    if runtime_node.role == "host" and runtime_node.distributed_enabled:
        master_domain_catalog, master_domain_catalog_error = safe_fetch_master_domain_catalog()
    csrf_token = get_token(request)
    domain_management_url = reverse("admin-domains")
    create_html = render_fragment(
        "admin_domain_create",
        {"csrf_token": csrf_token, "domain_management_url": domain_management_url},
    )
    management_html = render_fragment(
        "admin_domain_management",
        {
            "domain_states": domain_states,
            "active_domain": active_domain,
            "csrf_token": csrf_token,
            "domain_management_url": domain_management_url,
        },
    )
    widget_cards = build_admin_widget_cards(
        active_domain=active_domain,
        domain_rows=domain_rows,
        widget_ids=widget_ids,
        widget_widths=widget_widths,
        domain_states=domain_states,
        csrf_token=csrf_token,
        domain_management_url=domain_management_url,
        sync_runs=sync_runs,
        sync_jobs=sync_jobs,
        local_node=local_node,
        runtime_node=runtime_node,
        master_domain_catalog=master_domain_catalog,
        master_domain_catalog_error=master_domain_catalog_error,
        known_hosts=list_known_hosts() if runtime_node.role == "master" else [],
        sync_admin_url=reverse("admin-sync"),
    )
    return render(
        request,
        "kicli_django/admin_domain_management.html",
        {
            "active_domain": active_domain,
            "domain_rows": domain_rows,
            "create_html": create_html,
            "management_html": management_html,
            "sync_runs": sync_runs,
            "sync_jobs": sync_jobs,
            "local_node": local_node,
            "runtime_node": runtime_node,
            "master_domain_catalog": master_domain_catalog,
            "master_domain_catalog_error": master_domain_catalog_error,
            "widget_cards": widget_cards,
        },
    )


@require_GET
def admin_system_status_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="admin",
        fallback=default_widget_ids_for_area("admin"),
        subpage_key="status",
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="admin", subpage_key="status")
    domain_states = [
        {
            **state,
            **{key: display_data_path(state[key]) for key in ("markdown_dir", "jira_dir", "ontology_dir", "pdf_dir", "mix_dir")},
        }
        for state in semantic_domain_states()
    ]
    layout_raw = data_layout_snapshot(active_domain)
    sync_runs = list(SyncRun.objects.select_related("domain", "node").filter(domain__slug=active_domain).order_by("-started_at")[:12])
    from ki_knowledge.services.distributed_sync_runner import get_job_store as get_sync_job_store
    sync_jobs = get_sync_job_store().list_jobs(domain=active_domain, limit=12)
    layout = {
        key: display_data_path(value) if isinstance(value, str) and "/" in value else value
        for key, value in layout_raw.items()
    }
    status_html = render_fragment(
        "admin_system_status",
        {
            "active_domain": active_domain,
            "registered_domain_count": len(domain_states),
            "layout": layout,
            "status_url": reverse("admin-status"),
        },
    )
    widget_cards = build_admin_widget_cards(
        active_domain=active_domain,
        domain_rows=domain_registry_overview(active_domain),
        widget_ids=widget_ids,
        widget_widths=widget_widths,
        domain_states=domain_states,
        layout=layout,
        status_url=reverse("admin-status"),
        sync_runs=sync_runs,
        sync_jobs=sync_jobs,
    )
    return render(
        request,
        "kicli_django/admin_system_status.html",
        {
            "active_domain": active_domain,
            "registered_domain_count": len(domain_states),
            "layout": layout,
            "domain_states": domain_states,
            "status_html": status_html,
            "sync_runs": sync_runs,
            "sync_jobs": sync_jobs,
            "widget_cards": widget_cards,
        },
    )


@require_http_methods(["GET", "POST"])
def admin_sync_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "save_node_config":
            persist_local_node_settings(
                display_name=request.POST.get("display_name", "").strip(),
                role=request.POST.get("role", "").strip() or None,
                base_url=request.POST.get("base_url", "").strip(),
                sync_on_connect=request.POST.get("sync_on_connect", "").strip().lower() in {"1", "true", "yes", "on"},
                is_enabled=request.POST.get("is_enabled", "").strip().lower() in {"1", "true", "yes", "on"},
                sync_shared_secret=request.POST.get("sync_shared_secret", "").strip(),
            )
            messages.success(request, "Lokale Node-Konfiguration gespeichert und als aktive Runtime-Konfiguration übernommen.")
            return HttpResponseRedirect(reverse("admin-sync"))
        if action == "send_heartbeat":
            try:
                result = send_master_heartbeat()
            except (RequestException, ConnectionError, ValueError) as exc:
                messages.error(request, f"Heartbeat fehlgeschlagen: {exc}")
            else:
                if result.get("status") == "skipped":
                    messages.warning(request, "Heartbeat nicht gesendet: Master-Verbindung ist nicht konfiguriert.")
                else:
                    messages.success(request, f"Heartbeat gesendet. {_format_task_message(result)}")
            return HttpResponseRedirect(reverse("admin-sync"))
        if action == "run_sync_job":
            job_id = request.POST.get("job_id", "").strip()
            if not job_id:
                messages.error(request, "Keine Job-ID angegeben.")
            else:
                from ki_knowledge.services.distributed_sync_runner import run_sync_job

                try:
                    result = run_sync_job(job_id)
                    messages.success(
                        request,
                        f"Distributed-Sync-Job {job_id} ausgeführt. {_format_task_message(result)}",
                    )
                except Exception as exc:
                    messages.error(request, f"Distributed-Sync-Job {job_id} fehlgeschlagen: {exc}")
            return HttpResponseRedirect(reverse("admin-sync"))
        if action == "trigger_host_pull":
            host_node_id = request.POST.get("host_node_id", "").strip()
            target_domain = request.POST.get("domain", "").strip()
            domains = [target_domain] if target_domain else []
            try:
                result = send_host_pull_command(host_node_id=host_node_id, domains=domains or None)
                messages.success(
                    request,
                    f"Host {host_node_id} hat Pull-Auftrag erhalten. {_format_task_message(result)}",
                )
            except Exception as exc:
                messages.error(request, f"Host-Pull für {host_node_id} fehlgeschlagen: {exc}")
            return HttpResponseRedirect(reverse("admin-sync"))
        return HttpResponseBadRequest("unknown action")
    local_node = persist_local_node_settings()
    runtime_node = get_runtime_node_settings()
    sync_runs = list(SyncRun.objects.select_related("domain", "node").filter(Q(domain__slug=active_domain) | Q(domain__isnull=True)).order_by("-started_at")[:20])
    from ki_knowledge.services.distributed_sync_runner import get_job_store as get_sync_job_store
    sync_jobs = get_sync_job_store().list_jobs(domain=active_domain, limit=20)
    master_domain_catalog = None
    master_domain_catalog_error = ""
    if runtime_node.role == "host" and runtime_node.distributed_enabled:
        master_domain_catalog, master_domain_catalog_error = safe_fetch_master_domain_catalog()
    known_hosts = list_known_hosts() if runtime_node.role == "master" else []
    return render(
        request,
        "kicli_django/admin_sync.html",
        {
            "active_domain": active_domain,
            "local_node": local_node,
            "runtime_node": runtime_node,
            "sync_runs": sync_runs,
            "sync_jobs": sync_jobs,
            "master_domain_catalog": master_domain_catalog,
            "master_domain_catalog_error": master_domain_catalog_error,
            "known_hosts": known_hosts,
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
                ("Dashboard Builder", layout_builder_url("settings", "overview"), "Arrange widgets by area and drag them into the active layout grid."),
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
    def _selection_loader(request: HttpRequest, area_key: str, subpage_key: str, fallback: list[str]) -> list[str]:
        selected_widget_ids = _load_dashboard_widget_ids(
            request,
            area_key=area_key,
            subpage_key=subpage_key,
            fallback=fallback,
        )
        request.session[_DASHBOARD_BUILDER_SESSION_KEY] = selected_widget_ids
        request.session.modified = True
        return selected_widget_ids

    def _selection_syncer(request: HttpRequest, area_key: str) -> list[str]:
        return _sync_dashboard_selection(request, area_key=area_key)

    return widgetkit_dashboard_builder_view(
        request,
        config=BuilderViewConfig(
            registry=_WIDGETKIT_REGISTRY,
            layout_store=DjangoDashboardLayoutStore(),
            active_domain_getter=_active_semantic_domain,
            selection_loader=_selection_loader,
            selection_syncer=_selection_syncer,
            base_template_name="base.html",
            builder_url=lambda area, subpage: layout_builder_url(area, subpage),
            page_targets_for_area=layout_targets_for_area,
            page_title="Dashboard Builder",
        ),
    )


@require_GET

def widget_catalog_view(request: HttpRequest):
    """A dedicated preview page for the canonical widget catalog and HTML output."""
    from .widget_catalog_preview import catalog_active_domain

    active_domain = catalog_active_domain(request)
    request._widget_catalog_domain = active_domain
    area_filter = (request.GET.get("area", "all") or "all").strip().lower()
    all_specs = [spec for widget_id in widget_ids() if (spec := widget_by_id(widget_id)) is not None]
    catalog = [spec for spec in all_specs if area_filter == "all" or spec.area == area_filter]
    widget_payload = build_widget_preview_payload(
        widget_ids=[spec.widget_id for spec in catalog], active_domain=active_domain,
    )
    catalog_url = reverse("settings-layout-widgets")
    area_tabs = [
        {
            "key": "all",
            "label": "All",
            "count": len(all_specs),
            "url": f"{catalog_url}?{urlencode({'area': 'all', 'domain': active_domain})}",
        }
    ]
    area_tabs.extend(
        {
            "key": area,
            "label": area.replace("_", " ").title(),
            "count": sum(spec.area == area for spec in all_specs),
            "url": f"{catalog_url}?{urlencode({'area': area, 'domain': active_domain})}",
        }
        for area in builtin_areas()
    )
    return render(
        request,
        "kicli_django/widget_catalog.html",
        {
            "active_domain": active_domain,
            "widget_catalog": catalog,
            "widget_preview_payload": widget_payload,
            "area_filter": area_filter,
            "area_tabs": area_tabs,
        },
    )
