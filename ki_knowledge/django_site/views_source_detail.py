"""Source detail, source-backed InfoSites and graph views."""

from __future__ import annotations

from urllib.parse import urlencode
import json

from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .data_display import artifact_content_preview, display_data_path, display_source_ref
from .knowledge_browser import graph_3d_context, graph_context, store
from .knowledge_summary import domain_source_ids
from .views_common import _active_semantic_domain, _display_mode, _int_param
from .views_content import artifacts, records


@require_GET

def source_detail(request: HttpRequest, source_id: str):
    active_domain = _active_semantic_domain(request)
    store_obj = store()
    source = store_obj.get_source(source_id)
    if source is None:
        return HttpResponseBadRequest("source not found")
    if source_id not in domain_source_ids(active_domain):
        return HttpResponseBadRequest("source not in active domain")
    from .record_browser import group_records
    from .infosite_records import find_source_infosite_project

    infosite_project = find_source_infosite_project(
        domain=active_domain,
        source_id=source_id,
        source_title=source.title,
    )

    display_mode = _display_mode(request, default="table")
    record_query = request.GET.get("q", "").strip()[:200]
    page_size = 50
    page = _int_param(request, "page", 1, 1, 100000)
    records, record_count = store_obj.browse_records(
        source_id,
        query_text=record_query,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    page_count = max(1, (record_count + page_size - 1) // page_size)
    requested_page = page
    page = min(requested_page, page_count)
    if page != requested_page:
        records, record_count = store_obj.browse_records(
            source_id,
            query_text=record_query,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
    artifacts = store_obj.list_artifacts(source_id=source_id)
    workbench_source = {}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        from .sources_browser import source_rows
        from .source_access import decorate_rows

        workbench_source = decorate_rows(active_domain, source_rows(active_domain, [source], {}))[0]
    record_page_base = reverse("source-detail", args=[source_id])

    def artifact_display_url(mode: str) -> str:
        return f"{record_page_base}?{urlencode({'q': record_query, 'page': page, 'display': mode})}"

    display_artifacts = []
    for artifact in artifacts:
        try:
            structured_content = json.dumps(json.loads(artifact.content), ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            structured_content = artifact.content
        display_artifacts.append(
            {
                **artifact.__dict__,
                "display_source_id": display_source_ref(artifact.source_id),
                "display_preview": artifact_content_preview(artifact.artifact_type, artifact.content),
                "display_content": structured_content,
            }
        )
    return render(
        request,
        "kicli_django/source_detail.html",
        {
            "source": source,
            "workbench_source": workbench_source,
            "infosite_project": infosite_project,
            "display_source_id": display_source_ref(source.source_id),
            "display_location": display_data_path(source.location),
            "records": records,
            "record_groups": group_records(records),
            "record_query": record_query,
            "record_count": record_count,
            "record_page": page,
            "record_page_count": page_count,
            "record_first_index": (page - 1) * page_size + 1 if record_count else 0,
            "record_last_index": min(page * page_size, record_count),
            "record_prev_url": (
                f"{record_page_base}?{urlencode({'q': record_query, 'page': page - 1})}"
                if page > 1 else ""
            ),
            "record_next_url": (
                f"{record_page_base}?{urlencode({'q': record_query, 'page': page + 1})}"
                if page < page_count else ""
            ),
            "display_records": [
                {
                    **record.__dict__,
                    "display_source_id": display_source_ref(record.source_id),
                    "display_path": display_source_ref(record.path),
                }
                for record in records
            ],
            "artifacts": artifacts,
            "display_artifacts": display_artifacts,
            "display_mode": display_mode,
            "records_toggle_cards_url": artifact_display_url("cards"),
            "records_toggle_table_url": artifact_display_url("table"),
            "artifacts_toggle_cards_url": artifact_display_url("cards"),
            "artifacts_toggle_table_url": artifact_display_url("table"),
            "graph_url": reverse("source-graph", args=[source_id]),
            "graph_3d_url": reverse("source-graph-3d", args=[source_id]),
        },
    )


@require_POST
def create_source_infosite_project(request: HttpRequest):
    """Create an InfoSite project whose first source is this source's records."""
    from django.conf import settings
    from django.contrib import messages
    from django.shortcuts import redirect

    from .infosite_records import create_infosite_project_from_records

    source_id = request.POST.get("source_id", "").strip()
    active_domain = _active_semantic_domain(request)
    if not source_id or source_id not in domain_source_ids(active_domain):
        return HttpResponseBadRequest("source not found in active domain")

    store_obj = store()
    source = store_obj.get_source(source_id)
    if source is None:
        return HttpResponseBadRequest("source not found")

    try:
        project, created = create_infosite_project_from_records(
            source=source,
            records=store_obj.list_records(source_id=source_id),
            domain=active_domain,
            data_root=settings.KI_CONFIG.knowledge_data_root,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("source-detail", source_id=source_id)

    if created:
        messages.success(request, "InfoSite-Projekt mit den Records dieser Quelle wurde angelegt.")
    else:
        messages.info(request, "Für diese Quelle existiert bereits ein InfoSite-Projekt.")
    return redirect("infosite:project_detail", project_id=project.id)


@require_GET

def source_graph(request: HttpRequest, source_id: str):
    active_domain = _active_semantic_domain(request)
    store_obj = store()
    if store_obj.get_source(source_id) is None:
        return HttpResponseBadRequest("source not found")
    if source_id not in domain_source_ids(active_domain):
        return HttpResponseBadRequest("source not in active domain")
    ctx = graph_context(source_id)
    return render(
        request,
        "kicli_django/graph.html",
        {
            "source_id": source_id,
            "graph_html": ctx["graph_html"],
            "stats": ctx["stats"],
            "graph_3d_url": reverse("source-graph-3d", args=[source_id]),
        },
    )


@require_GET

def source_graph_3d(request: HttpRequest, source_id: str):
    active_domain = _active_semantic_domain(request)
    store_obj = store()
    source = store_obj.get_source(source_id)
    if source is None:
        return HttpResponseBadRequest("source not found")
    if source_id not in domain_source_ids(active_domain):
        return HttpResponseBadRequest("source not in active domain")
    ctx = graph_3d_context(source_id)
    return render(
        request,
        "kicli_django/graph_3d.html",
        {
            "source": source,
            "source_id": source_id,
            "graph_3d": ctx["graph_3d"],
            "stats": ctx["stats"],
            "graph_2d_url": reverse("source-graph", args=[source_id]),
        },
    )
