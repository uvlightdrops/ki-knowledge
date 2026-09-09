from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from .dashboard_registry import (
    default_widget_ids_for_area,
    frontpage_aggregate_widgets,
    layout_positions_for_widgets,
    widget_by_id,
)
from .infosite_models import (
    DashboardDefinition,
    DashboardWidgetPlacement,
    GeneratedDocument,
    ensure_domain_registered,
)
from .services import (
    default_semantic_domain,
    normalize_semantic_domain,
)
from .ui_dispatcher import resolve_ui_action

_JIRA_CHAT_SESSION_KEY = "jira_support_chat_history"
_OLLAMA_CHAT_SESSION_KEY = "ollama_chat_history"
_KNOWLEDGE_API_URL_SESSION_KEY = "knowledge_api_url"
_SEMANTIC_DOMAIN_SESSION_KEY = "semantic_active_domain"
_DASHBOARD_BUILDER_SESSION_KEY = "dashboard_builder_widgets"


def _active_semantic_domain(request: HttpRequest) -> str:
    query_domain = request.GET.get("domain", "").strip()
    if query_domain:
        domain = normalize_semantic_domain(query_domain)
        request.session[_SEMANTIC_DOMAIN_SESSION_KEY] = domain
        request.session.modified = True
        return domain
    session_domain = request.session.get(_SEMANTIC_DOMAIN_SESSION_KEY, "")
    if session_domain:
        return normalize_semantic_domain(str(session_domain))
    default_domain = default_semantic_domain()
    request.session[_SEMANTIC_DOMAIN_SESSION_KEY] = default_domain
    request.session.modified = True
    return default_domain



def _selected_markdown(request: HttpRequest) -> Path | None:
    raw = request.GET.get("path", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.exists() and path.is_file() and path.suffix.lower() in {".md", ".markdown"}:
        return path
    return None



def _int_param(request: HttpRequest, name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.GET.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))



def _display_mode(request: HttpRequest, default: str = "table") -> str:
    mode = request.GET.get("display", "").strip().lower()
    if mode in {"cards", "table"}:
        return mode
    return default



def _get_or_create_dashboard(request: HttpRequest, *, area_key: str = "settings") -> DashboardDefinition:
    active_domain = _active_semantic_domain(request)
    domain_obj = ensure_domain_registered(active_domain)
    if domain_obj is None:
        raise ValueError("No active domain available for dashboard persistence")
    dashboard_slug = f"{area_key}-{active_domain}"
    owner = request.user if getattr(request.user, "is_authenticated", False) else None
    dashboard, _ = DashboardDefinition.objects.get_or_create(
        owner=owner,
        domain=domain_obj,
        area_key=area_key,
        slug=dashboard_slug,
        defaults={"title": f"{area_key.title()} dashboard for {active_domain}"},
    )
    return dashboard



def _load_dashboard_widget_ids(request: HttpRequest, *, area_key: str = "dashboard", fallback: list[str] | None = None) -> list[str]:
    """Return the persisted layout for a dashboard area or a safe fallback."""
    if fallback is None:
        fallback = list(default_widget_ids_for_area(area_key))
    active_domain = _active_semantic_domain(request)
    domain_obj = ensure_domain_registered(active_domain)
    if domain_obj is None:
        return list(fallback)

    owner = request.user if getattr(request.user, "is_authenticated", False) else None
    dashboard = (
        DashboardDefinition.objects.filter(domain=domain_obj, area_key=area_key, owner=owner)
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if dashboard is None:
        dashboard = DashboardDefinition.objects.filter(domain=domain_obj, area_key=area_key, owner__isnull=True).order_by("-updated_at", "-created_at").first()
    if dashboard is None:
        return list(fallback)

    selected = list(
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard)
        .order_by("sort_index", "widget_id")
        .values_list("widget_id", flat=True)
    )
    if not selected:
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard).delete()
        for index, widget_id in enumerate(fallback):
            if widget_by_id(widget_id) is None:
                continue
            position = layout_positions_for_widgets(fallback)[widget_id]
            DashboardWidgetPlacement.objects.create(
                dashboard=dashboard,
                widget_id=widget_id,
                sort_index=index,
                x=position["x"],
                y=position["y"],
                w=position["w"],
                h=position["h"],
            )
        return list(fallback)
    return selected


def _load_dashboard_widget_widths(request: HttpRequest, *, area_key: str = "dashboard") -> dict[str, int]:
    """Return persisted per-widget width values for the current area."""
    active_domain = _active_semantic_domain(request)
    domain_obj = ensure_domain_registered(active_domain)
    if domain_obj is None:
        return {}

    owner = request.user if getattr(request.user, "is_authenticated", False) else None
    dashboard = (
        DashboardDefinition.objects.filter(domain=domain_obj, area_key=area_key, owner=owner)
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if dashboard is None:
        dashboard = DashboardDefinition.objects.filter(domain=domain_obj, area_key=area_key, owner__isnull=True).order_by("-updated_at", "-created_at").first()
    if dashboard is None:
        return {}

    widths: dict[str, int] = {}
    for placement in DashboardWidgetPlacement.objects.filter(dashboard=dashboard):
        try:
            width = int(placement.w or 6)
        except (TypeError, ValueError):
            continue
        if 3 <= width <= 12:
            widths[placement.widget_id] = width
    return widths


def _sync_dashboard_selection(request: HttpRequest, *, area_key: str = "settings") -> list[str]:
    """Persist the selected widget ids and a simple grid layout for the dashboard."""
    action = request.POST.get("action", "").strip()
    widget_id = request.POST.get("widget_id", "").strip() or None
    raw_order = request.POST.get("widget_order", "").strip()
    raw_sizes = request.POST.get("widget_sizes", "").strip()
    widget_order: list[str] | None = None
    widget_sizes: dict[str, int] | None = None
    if raw_order:
        try:
            loaded = json.loads(raw_order)
        except ValueError:
            loaded = []
        if isinstance(loaded, list):
            widget_order = [str(item) for item in loaded if str(item).strip()]
    if raw_sizes:
        try:
            loaded = json.loads(raw_sizes)
        except ValueError:
            loaded = {}
        if isinstance(loaded, dict):
            cleaned: dict[str, int] = {}
            for key, value in loaded.items():
                try:
                    width = int(value)
                except (TypeError, ValueError):
                    continue
                if 3 <= width <= 12:
                    cleaned[str(key)] = width
            if cleaned:
                widget_sizes = cleaned

    selections = resolve_ui_action(
        action,
        request=request,
        area_key=area_key,
        widget_id=widget_id,
        widget_order=widget_order,
        widget_sizes=widget_sizes,
    )
    request.session[_DASHBOARD_BUILDER_SESSION_KEY] = selections
    request.session.modified = True
    return selections



def _frontpage_dashboard_widgets(
    request: HttpRequest,
    *,
    active_domain: str,
    source_count: int,
    record_count: int,
    artifact_count: int,
    sources: list,
    artifacts: list,
) -> list[dict[str, object]]:
    """Build the HTML for the home dashboard overview widgets.

    These widgets are intentionally function-based and use the functional widget
    IDs from the registry instead of the legacy page-centric dashboard boxes.
    """

    def value_for(item, field_name: str, default: str = "—") -> str:
        if item is None:
            return default
        if isinstance(item, dict):
            return str(item.get(field_name, default))
        return str(getattr(item, field_name, default))

    def widget_body(widget_id: str) -> tuple[str, str, str]:
        spec = widget_by_id(widget_id)
        if spec is None:
            return (widget_id, "custom", "<p class='muted'>Widget unavailable.</p>")

        if widget_id == "datasources.overview.summary.v1":
            source_items = list(sources[:3])
            body = (
                "<table class='dashboard-monitor-table' style='width:100%; border-collapse:collapse;'><tbody>"
                f"<tr><th style='text-align:left; width:60%;'>Sources</th><td>{source_count}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Recent source</th><td>{value_for(source_items[0], 'title') if source_items else '—'}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Active domain</th><td>{active_domain}</td></tr>"
                "</tbody></table>"
            )
            if source_items:
                body += "<ul style='margin:10px 0 0; padding-left:18px;'>" + "".join(
                    f"<li><a href='{reverse('source-detail', args=[value_for(item, 'source_id')])}'>{value_for(item, 'title', value_for(item, 'source_id'))}</a></li>"
                    for item in source_items
                ) + "</ul>"
            else:
                body += "<p class='muted' style='margin:10px 0 0;'>No sources yet.</p>"
            return (spec.label, spec.default_size, body)

        if widget_id == "knowledge.overview.summary.v1":
            return (
                spec.label,
                spec.default_size,
                "<table class='dashboard-monitor-table' style='width:100%; border-collapse:collapse;'><tbody>"
                f"<tr><th style='text-align:left; width:60%;'>Sources</th><td>{source_count}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Records</th><td>{record_count}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Artifacts</th><td>{artifact_count}</td></tr>"
                "</tbody></table>"
                "<div class='dashboard-actions' style='margin-top:10px;'>"
                f"<a href='{reverse('knowledge')}'><button type='button'>Open knowledge</button></a>"
                f"<a href='{reverse('records')}'><button type='button'>Records</button></a>"
                "</div>",
            )

        if widget_id == "infooutput.overview.summary.v1":
            recent_docs = (
                GeneratedDocument.objects.filter(project__domain=active_domain)
                .select_related("project")
                .order_by("-generated_at")[:3]
            )
            body = (
                "<table class='dashboard-monitor-table' style='width:100%; border-collapse:collapse;'><tbody>"
                f"<tr><th style='text-align:left; width:60%;'>Generated documents</th><td>{len(recent_docs)}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Artifacts</th><td>{artifact_count}</td></tr>"
                f"<tr><th style='text-align:left; width:60%;'>Active domain</th><td>{active_domain}</td></tr>"
                "</tbody></table>"
            )
            if recent_docs:
                body += "<ul style='margin:10px 0 0; padding-left:18px;'>" + "".join(
                    f"<li>{value_for(doc, 'display_path', value_for(doc, 'file_path', 'Generated document'))}</li>"
                    for doc in recent_docs
                ) + "</ul>"
            else:
                body += "<p class='muted' style='margin:10px 0 0;'>No generated documents yet.</p>"
            return (spec.label, spec.default_size, body)

        if spec.area == "admin":
            rows = []
            for entry in []:
                rows.append(entry)
            return (
                spec.label,
                spec.default_size,
                f"<p><strong>Active domain:</strong> {active_domain}</p><p><strong>Area:</strong> {spec.area}</p><p><a href='{reverse('admin-overview')}'>Open admin overview</a></p>",
            )
        if spec.area == "settings":
            return (
                spec.label,
                spec.default_size,
                f"<p><strong>Active domain:</strong> {active_domain}</p><p><strong>Area:</strong> {spec.area}</p><p><a href='{reverse('settings')}'>Open settings</a></p>",
            )
        return (
            spec.label,
            spec.default_size,
            f"<p class='muted' style='margin:0;'>{spec.description}</p>",
        )

    widget_specs = []
    for own_widget_id in list(frontpage_aggregate_widgets()):
        label, default_size, body = widget_body(own_widget_id)
        widget_specs.append({
            "widget_id": own_widget_id,
            "label": label,
            "default_size": default_size,
            "body": body,
        })
    return widget_specs



def _choice_param(request: HttpRequest, name: str, default: str, allowed: set[str]) -> str:
    value = request.GET.get(name, "").strip().lower()
    if value in allowed:
        return value
    return default



def _paginate_items(items: list, *, page: int, page_size: int) -> tuple[list, int, bool]:
    total_count = len(items)
    requested_page = max(1, page)
    start_index = (requested_page - 1) * page_size
    page_items = items[start_index:start_index + page_size]
    has_more = start_index + len(page_items) < total_count
    return page_items, total_count, has_more



def _redirect_with_filters(default_url: str, request: HttpRequest, keys: list[str]) -> HttpResponseRedirect:
    params: dict[str, str] = {}
    for key in keys:
        value = request.POST.get(key, request.GET.get(key, "")).strip()
        if value and value != "(all)":
            params[key] = value
    if params:
        query = urlencode(params)
        if "?" in default_url:
            return HttpResponseRedirect(f"{default_url}&{query}")
        return HttpResponseRedirect(f"{default_url}?{query}")
    return HttpResponseRedirect(default_url)



def _int_post_param(request: HttpRequest, name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.POST.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))



def _format_task_message(result: dict[str, object]) -> str:
    parts: list[str] = []
    for key, value in result.items():
        if key == "task":
            continue
        if isinstance(value, list):
            text = ", ".join(str(item) for item in value) if value else "-"
        else:
            text = str(value)
        parts.append(f"{key}={text}")
    return "; ".join(parts)



def _obj_attr_or_key(item: object, name: str, default: str = "—") -> str:
    if item is None:
        return default
    if isinstance(item, dict):
        return str(item.get(name, default))
    return str(getattr(item, name, default))

