from __future__ import annotations

import json
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from .dashboard_registry import default_widget_ids_for_area
from .page_widgets import build_data_sources_widget_cards
from .services import (
    artifact_content_preview,
    create_pdf_import_job,
    delete_pdf_import_jobs,
    data_dir,
    display_data_path,
    display_source_ref,
    discover_pdf_files,
    domain_knowledge_summary,
    domain_pdf_dir,
    domain_registry_overview,
    domain_source_ids,
    generate_all_artifacts,
    get_pdf_batch_processor,
    graph_3d_context,
    graph_context,
    import_markdown_directory,
    import_markdown_file,
    import_ontology_directory,
    import_ontology_file,
    import_ontology_url,
    jira_cache_db_path,
    jira_csv_path,
    jira_daily_timeline,
    jira_domain_analysis,
    jira_domain_terms,
    jira_exclusion_add,
    jira_exclusion_remove,
    jira_excluded_terms,
    jira_forget_jira_term,
    jira_graph_explorer,
    jira_hybrid_search,
    jira_issue_count,
    jira_support_chat_answer,
    knowledge_api_browser_context,
    knowledge_api_default_url,
    load_prompt_library_context,
    ollama_available_models,
    ollama_chat_answer,
    ollama_runtime_settings,
    parse_prompt_backlog,
    parse_prompt_templates,
    pdf_import_jobs,
    pdf_import_report,
    prompt_batch_outputs,
    render_markdown_html,
    root_markdown_tree,
    run_dashboard_task,
    run_prompt_backlog_batch,
    save_ollama_chat_markdown,
    save_prompt_library_documents,
    semantic_domain_states,
    semantic_job_detail,
    semantic_jobs,
    semantic_store,
    semantic_term_detail,
    semantic_terms,
    source_in_domain,
    store,
    tree_lines,
    workspace_markdown_files,
    workspace_ontology_files,
)
from .views_common import (
    _active_semantic_domain,
    _choice_param,
    _display_mode,
    _int_param,
    _int_post_param,
    _load_dashboard_widget_ids,
    _load_dashboard_widget_widths,
    _paginate_items,
    _redirect_with_filters,
    _selected_markdown,
)

_JIRA_CHAT_SESSION_KEY = "jira_support_chat_history"
_OLLAMA_CHAT_SESSION_KEY = "ollama_chat_history"
_KNOWLEDGE_API_URL_SESSION_KEY = "knowledge_api_url"
_SEMANTIC_DOMAIN_SESSION_KEY = "semantic_active_domain"
_DASHBOARD_BUILDER_SESSION_KEY = "dashboard_builder_widgets"

def data_sources_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    display_mode = _display_mode(request, default="cards")
    store_obj = store()
    all_domains = domain_registry_overview(active_domain)
    markdown_files = workspace_markdown_files(domain=active_domain)
    ontology_files = workspace_ontology_files(domain=active_domain)
    domain_states = semantic_domain_states()
    active_state = next((item for item in domain_states if item.get("domain") == active_domain), {"domain": active_domain})
    owl_sources = [
        source
        for source in store_obj.list_sources(source_type="owl")
        if source_in_domain(source, domain=active_domain)
    ]
    sources_list = [
        source
        for source in store_obj.list_sources()
        if source_in_domain(source, domain=active_domain)
    ]
    pdf_dir = domain_pdf_dir(active_domain)
    pdf_jobs = active_state.get("pdf_jobs") or {"pending": 0, "processing": 0, "done": 0, "failed": 0, "total": 0}
    configured_widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="datasources",
        fallback=default_widget_ids_for_area("datasources"),
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="datasources")
    widget_cards = build_data_sources_widget_cards(
        request=request,
        active_domain=active_domain,
        all_domains=all_domains,
        active_domain_state=active_state,
        markdown_count=len(markdown_files),
        data_dir=display_data_path(data_dir(active_domain)),
        jira_issues=jira_issue_count(active_domain),
        jira_csv_path=display_data_path(jira_csv_path(active_domain)),
        jira_cache_db=display_data_path(jira_cache_db_path(active_domain)),
        pdf_count=int(active_state.get("pdf_files", 0) or 0),
        pdf_dir=display_data_path(pdf_dir) if active_state.get("has_pdf_source") or pdf_dir.exists() else "unused",
        pdf_jobs=pdf_jobs,
        ontology_count=len(ontology_files),
        ontology_dir=display_data_path(active_state.get("ontology_dir")),
        owl_sources=len(owl_sources),
        sources=sources_list,
        widget_ids=configured_widget_ids,
        widget_widths=widget_widths,
    )
    return render(
        request,
        "kicli_django/data_sources.html",
        {
            "active_domain": active_domain,
            "active_domain_state": active_state,
            "display_mode": display_mode,
            "all_domains": all_domains,
            "widget_cards": widget_cards,

            "data_sources_toggle_cards_url": f"{reverse('data-sources')}?display=cards",
            "data_sources_toggle_table_url": f"{reverse('data-sources')}?display=table",
            "jira_issues": jira_issue_count(active_domain),
            "jira_csv_path": display_data_path(jira_csv_path(active_domain)),
            "jira_cache_db": display_data_path(jira_cache_db_path(active_domain)),
            "data_dir": display_data_path(data_dir(active_domain)),
            "pdf_dir": display_data_path(pdf_dir) if active_state.get("has_pdf_source") or pdf_dir.exists() else "unused",
            "pdf_default_path": str(pdf_dir) if (active_state.get("has_pdf_source") or pdf_dir.exists()) else "",
            "pdf_count": int(active_state.get("pdf_files", 0) or 0),
            "pdf_jobs": pdf_jobs,
            "ontology_dir": display_data_path(active_state.get("ontology_dir")),
            "markdown_count": len(markdown_files),
            "markdown_examples": [
                {**item, "display_path": display_data_path(item["path"])}
                for item in markdown_files[:6]
            ],
            "ontology_count": len(ontology_files),
            "ontology_examples": [
                {**item, "display_path": display_data_path(item["path"])}
                for item in ontology_files[:8]
            ],
            "owl_sources": len(owl_sources),
            "sources": sources_list,
        },
    )


@require_http_methods(["GET", "POST"])

def workspace(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    selected = _selected_markdown(request)
    query = request.GET.get("q", "")
    display_mode = _display_mode(request, default="cards")
    tree = root_markdown_tree(query=query, domain=active_domain)
    markdown_files = workspace_markdown_files(query=query, domain=active_domain)
    source_preview = None
    source_preview_html = None
    if selected:
        try:
            source_preview = selected.read_text(encoding="utf-8")
            source_preview_html = render_markdown_html(source_preview)
        except OSError:
            source_preview = None
            source_preview_html = None
    return render(
        request,
        "kicli_django/workspace.html",
        {
            "data_dir": display_data_path(data_dir(active_domain)),
            "active_domain": active_domain,
            "tree_lines": tree_lines(tree) if tree else [],
            "markdown_files": markdown_files,
            "selected": selected,
            "source_preview": source_preview,
            "source_preview_html": source_preview_html,
            "query": query,
            "display_mode": display_mode,
            "workspace_toggle_cards_url": f"{reverse('workspace')}?{urlencode({'q': query, 'display': 'cards'})}",
            "workspace_toggle_table_url": f"{reverse('workspace')}?{urlencode({'q': query, 'display': 'table'})}",
        },
    )


@require_GET

def sources(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    display_mode = _display_mode(request, default="cards")
    store_obj = store()
    source_type = request.GET.get("type") or None
    sources_list = [
        source
        for source in store_obj.list_sources(source_type=source_type)
        if source_in_domain(source, domain=active_domain)
    ]
    scoped_knowledge = domain_knowledge_summary(active_domain)
    markdown_files = workspace_markdown_files(domain=active_domain)
    ontology_files = workspace_ontology_files(domain=active_domain)
    domain_states = semantic_domain_states()
    active_state = next((item for item in domain_states if item.get("domain") == active_domain), {"domain": active_domain})
    owl_sources = [
        source
        for source in store_obj.list_sources(source_type="owl")
        if source_in_domain(source, domain=active_domain)
    ]
    return render(
        request,
        "kicli_django/sources.html",
        {
            "sources": sources_list,
            "source_type": source_type or "(all)",
            "source_count": len(sources_list),
            "artifact_count": int(scoped_knowledge["artifacts"]),
            "markdown_count": len(markdown_files),
            "ontology_count": len(ontology_files),
            "ontology_examples": [
                {**item, "display_path": display_data_path(item["path"])}
                for item in ontology_files[:8]
            ],
            "jira_issues": jira_issue_count(active_domain),
            "data_dir": display_data_path(data_dir(active_domain)),
            "jira_csv_path": display_data_path(jira_csv_path(active_domain)),
            "jira_cache_db": display_data_path(jira_cache_db_path(active_domain)),
            "active_domain": active_domain,
            "active_domain_state": active_state,
            "display_mode": display_mode,
            "sources_toggle_cards_url": f"{reverse('sources')}?{urlencode({'type': source_type or '', 'display': 'cards'})}",
            "sources_toggle_table_url": f"{reverse('sources')}?{urlencode({'type': source_type or '', 'display': 'table'})}",
            "owl_sources": len(owl_sources),
            "markdown_examples": markdown_files[:6],
        },
    )


@require_GET

def source_detail(request: HttpRequest, source_id: str):
    active_domain = _active_semantic_domain(request)
    store_obj = store()
    source = store_obj.get_source(source_id)
    if source is None:
        return HttpResponseBadRequest("source not found")
    if source_id not in domain_source_ids(active_domain):
        return HttpResponseBadRequest("source not in active domain")
    display_mode = _display_mode(request, default="table")
    records = store_obj.list_records(source_id=source_id, limit=1000)
    artifacts = store_obj.list_artifacts(source_id=source_id)
    record_toggle_base = f"{reverse('source-detail', args=[source_id])}?display={{mode}}"
    return render(
        request,
        "kicli_django/source_detail.html",
        {
            "source": source,
            "display_source_id": display_source_ref(source.source_id),
            "display_location": display_data_path(source.location),
            "records": records,
            "display_records": [
                {
                    **record.__dict__,
                    "display_source_id": display_source_ref(record.source_id),
                    "display_path": display_source_ref(record.path),
                }
                for record in records
            ],
            "artifacts": artifacts,
            "display_artifacts": [
                {
                    **artifact.__dict__,
                    "display_source_id": display_source_ref(artifact.source_id),
                    "display_preview": artifact_content_preview(artifact.artifact_type, artifact.content),
                }
                for artifact in artifacts
            ],
            "display_mode": display_mode,
            "records_toggle_cards_url": record_toggle_base.format(mode="cards"),
            "records_toggle_table_url": record_toggle_base.format(mode="table"),
            "artifacts_toggle_cards_url": record_toggle_base.format(mode="cards"),
            "artifacts_toggle_table_url": record_toggle_base.format(mode="table"),
            "graph_url": reverse("source-graph", args=[source_id]),
            "graph_3d_url": reverse("source-graph-3d", args=[source_id]),
        },
    )


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


@require_http_methods(["GET", "POST"])

def artifacts(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    store_obj = store()
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        artifact_type = request.POST.get("type") or None
        allowed_sources = domain_source_ids(active_domain)
        if action == "delete":
            artifact_ids = [item.strip() for item in request.POST.getlist("artifact_ids") if item.strip()]
            if not artifact_ids:
                return HttpResponseBadRequest("artifact_ids missing")
            store_obj.delete_artifacts(artifact_ids)
            return _redirect_with_filters(
                reverse("artifacts"),
                request,
                ["type", "display"],
            )
        if action == "delete_all":
            items = [
                item
                for item in store_obj.list_artifacts(artifact_type=artifact_type)
                if item.source_id in allowed_sources
            ]
            if not items:
                return _redirect_with_filters(reverse("artifacts"), request, ["type", "display"])
            store_obj.delete_artifacts([item.artifact_id for item in items])
            return _redirect_with_filters(
                reverse("artifacts"),
                request,
                ["type", "display"],
            )
        return HttpResponseBadRequest("action missing")

    artifact_type = request.GET.get("type") or None
    display_mode = _display_mode(request, default="cards")
    page_size = _int_param(request, "limit", default=50, minimum=1, maximum=2000)
    page = max(1, _int_param(request, "page", default=1, minimum=1, maximum=100000))
    allowed_sources = domain_source_ids(active_domain)
    artifacts_list = [
        item
        for item in store_obj.list_artifacts(artifact_type=artifact_type)
        if item.source_id in allowed_sources
    ]
    display_artifacts = [
        {
            **artifact.__dict__,
            "display_source_id": display_source_ref(artifact.source_id),
            "display_preview": artifact_content_preview(artifact.artifact_type, artifact.content),
        }
        for artifact in artifacts_list
    ]
    paged_artifacts, total_count, has_more = _paginate_items(display_artifacts, page=page, page_size=page_size)
    next_page_url = (
        f"{reverse('artifacts')}?{urlencode({'type': artifact_type or '', 'limit': page_size, 'page': page + 1, 'display': display_mode})}"
    )
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "kicli_django/artifacts_rows_fragment.html",
            {
                "artifacts": paged_artifacts,
                "has_more": has_more,
                "next_page_url": next_page_url,
            },
        )
    artifact_toggle_base = f"{reverse('artifacts')}?type={artifact_type or ''}&display={{mode}}"
    return render(
        request,
        "kicli_django/artifacts.html",
        {
            "artifacts": artifacts_list,
            "display_artifacts": paged_artifacts,
            "total_artifact_count": total_count,
            "page": page,
            "limit": page_size,
            "has_more": has_more,
            "next_page_url": next_page_url,
            "artifact_type": artifact_type or "(all)",
            "active_domain": active_domain,
            "display_mode": display_mode,
            "artifacts_toggle_cards_url": artifact_toggle_base.format(mode="cards"),
            "artifacts_toggle_table_url": artifact_toggle_base.format(mode="table"),
        },
    )


@require_http_methods(["GET", "POST"])

def records(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    store_obj = store()
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        source_id = request.POST.get("source_id", "").strip() or None
        block_type = request.POST.get("block_type", "").strip() or None
        allowed_sources = domain_source_ids(active_domain)
        if action == "delete":
            record_ids = [item.strip() for item in request.POST.getlist("record_ids") if item.strip()]
            if not record_ids:
                return HttpResponseBadRequest("record_ids missing")
            store_obj.delete_records(record_ids)
            return _redirect_with_filters(
                reverse("records"),
                request,
                ["source_id", "block_type", "limit", "display"],
            )
        if action == "delete_all":
            query_source = source_id if source_id else None
            items = [
                item
                for item in store_obj.list_records(source_id=query_source, block_type=block_type)
                if item.source_id in allowed_sources
            ]
            if not items:
                return _redirect_with_filters(reverse("records"), request, ["source_id", "block_type", "limit", "display"])
            store_obj.delete_records([item.block_id for item in items])
            return _redirect_with_filters(
                reverse("records"),
                request,
                ["source_id", "block_type", "limit", "display"],
            )
        return HttpResponseBadRequest("action missing")

    source_id = request.GET.get("source_id", "").strip() or None
    block_type = request.GET.get("block_type", "").strip() or None
    page_size = _int_param(request, "limit", default=50, minimum=1, maximum=2000)
    page = max(1, _int_param(request, "page", default=1, minimum=1, maximum=100000))
    display_mode = _display_mode(request, default="table")
    allowed_sources = domain_source_ids(active_domain)
    scoped_knowledge = domain_knowledge_summary(active_domain)
    total_record_count = int(scoped_knowledge["records"])
    if source_id and source_id not in allowed_sources:
        raw_records = []
    else:
        query_source = source_id if source_id else None
        raw_records = [
            item
            for item in store_obj.list_records(source_id=query_source, block_type=block_type)
            if item.source_id in allowed_sources
        ]
        total_record_count = len(raw_records)
    records_list, total_record_count, has_more = _paginate_items(raw_records, page=page, page_size=page_size)
    display_records = [
        {
            **record.__dict__,
            "display_source_id": display_source_ref(record.source_id),
            "display_path": display_source_ref(record.path),
        }
        for record in records_list
    ]
    next_page_url = (
        f"{reverse('records')}?{urlencode({'source_id': source_id or '', 'block_type': block_type or '', 'limit': page_size, 'page': page + 1, 'display': display_mode})}"
    )

    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "kicli_django/records_rows_fragment.html",
            {
                "records": display_records,
                "has_more": has_more,
                "next_page_url": next_page_url,
            },
        )

    return render(
        request,
        "kicli_django/records.html",
        {
            "records": records_list,
            "total_record_count": total_record_count,
            "display_records": display_records,
            "source_id": source_id or "(all)",
            "block_type": block_type or "(all)",
            "limit": page_size,
            "page": page,
            "has_more": has_more,
            "next_page_url": next_page_url,
            "active_domain": active_domain,
            "display_mode": display_mode,
            "records_toggle_cards_url": (
                f"{reverse('records')}?{urlencode({'source_id': source_id or '', 'block_type': block_type or '', 'limit': page_size, 'display': 'cards'})}"
            ),
            "records_toggle_table_url": (
                f"{reverse('records')}?{urlencode({'source_id': source_id or '', 'block_type': block_type or '', 'limit': page_size, 'display': 'table'})}"
            ),
        },
    )


@require_http_methods(["GET", "POST"])

def jobs_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "cancel":
            job_ids = [item.strip() for item in request.POST.getlist("job_ids") if item.strip()]
            if not job_ids:
                return HttpResponseBadRequest("job_ids missing")
            store_obj = semantic_store(domain)
            cancelled = store_obj.cancel_jobs(job_ids)
            next_url = request.POST.get("next", "").strip() or reverse("jobs")
            if not next_url.startswith("/"):
                next_url = reverse("jobs")
            separator = "&" if "?" in next_url else "?"
            return HttpResponseRedirect(f"{next_url}{separator}notice={cancelled} job(s) cancelled")
        return HttpResponseBadRequest("action missing")

    status = request.GET.get("status", "").strip() or None
    job_type = request.GET.get("job_type", "").strip() or None
    page_size = _int_param(request, "limit", default=200, minimum=1, maximum=2000)
    page = max(1, _int_param(request, "page", default=1, minimum=1, maximum=100000))
    display_mode = _display_mode(request, default="table")
    all_jobs = semantic_jobs(status=status, job_type=job_type, limit=max(page_size * 10, 5000), domain=domain)
    jobs, total_count, has_more = _paginate_items(all_jobs, page=page, page_size=page_size)
    next_page_url = (
        f"{reverse('jobs')}?{urlencode({'status': status or '', 'job_type': job_type or '', 'limit': page_size, 'page': page + 1, 'display': display_mode})}"
    )
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "kicli_django/jobs_rows_fragment.html",
            {"jobs": jobs, "has_more": has_more, "next_page_url": next_page_url},
        )
    return render(
        request,
        "kicli_django/jobs.html",
        {
            "jobs": jobs,
            "status": status or "(all)",
            "job_type": job_type or "(all)",
            "limit": page_size,
            "page": page,
            "has_more": has_more,
            "next_page_url": next_page_url,
            "total_job_count": total_count,
            "active_domain": domain,
            "available_job_types": sorted({job.job_type for job in all_jobs}),
            "display_mode": display_mode,
            "jobs_toggle_cards_url": f"{reverse('jobs')}?{urlencode({'status': status or '', 'job_type': job_type or '', 'limit': page_size, 'display': 'cards'})}",
            "jobs_toggle_table_url": f"{reverse('jobs')}?{urlencode({'status': status or '', 'job_type': job_type or '', 'limit': page_size, 'display': 'table'})}",
        },
    )


@require_http_methods(["GET", "POST"])

def job_detail_view(request: HttpRequest, job_id: str):
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "cancel":
            store_obj = semantic_store(_active_semantic_domain(request))
            cancelled = store_obj.cancel_jobs([job_id])
            return HttpResponseRedirect(reverse("job-detail", args=[job_id]))
        return HttpResponseBadRequest("action missing")
    detail = semantic_job_detail(job_id, domain=_active_semantic_domain(request))
    if detail is None:
        return HttpResponseBadRequest("job not found")
    return render(
        request,
        "kicli_django/job_detail.html",
        {
            "job": detail["job"],
            "term": detail["term"],
            "facts": detail["facts"],
            "prompt": detail["prompt"],
        },
    )


@require_GET

def jira_domain_terms_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    page_size = _int_param(request, "limit", default=200, minimum=1, maximum=1000)
    page = max(1, _int_param(request, "page", default=1, minimum=1, maximum=100000))
    min_count = _int_param(request, "min_count", default=2, minimum=1, maximum=100)
    sort = _choice_param(
        request,
        "sort",
        default="relevance",
        allowed={"relevance", "term", "count", "issue_count"},
    )
    order = _choice_param(request, "order", default="desc", allowed={"asc", "desc"})
    all_terms = jira_domain_terms(limit=max(page_size * 10, 5000), min_count=min_count, sort=sort, order=order, domain=domain)
    terms, total_count, has_more = _paginate_items(all_terms, page=page, page_size=page_size)
    next_page_url = (
        f"{reverse('jira-domain-terms')}?{urlencode({'min_count': min_count, 'limit': page_size, 'sort': sort, 'order': order, 'page': page + 1, 'display': _display_mode(request, default='table')})}"
    )
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "kicli_django/jira_domain_terms_rows_fragment.html",
            {"terms": terms, "has_more": has_more, "next_page_url": next_page_url},
        )
    display_mode = _display_mode(request, default="table")
    return render(
        request,
        "kicli_django/jira_domain_terms.html",
        {
            "terms": terms,
            "limit": page_size,
            "page": page,
            "has_more": has_more,
            "next_page_url": next_page_url,
            "total_term_count": total_count,
            "min_count": min_count,
            "sort": sort,
            "order": order,
            "cache_db": jira_cache_db_path(domain),
            "active_domain": domain,
            "display_mode": display_mode,
            "domain_terms_toggle_cards_url": f"{reverse('jira-domain-terms')}?{urlencode({'min_count': min_count, 'limit': page_size, 'sort': sort, 'order': order, 'display': 'cards'})}",
            "domain_terms_toggle_table_url": f"{reverse('jira-domain-terms')}?{urlencode({'min_count': min_count, 'limit': page_size, 'sort': sort, 'order': order, 'display': 'table'})}",
        },
    )


@require_http_methods(["GET", "POST"])

def jira_exclusions_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    display_mode = _display_mode(request, default="table")
    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        term = request.POST.get("term", "").strip()
        kind = request.POST.get("kind", "exception").strip() or "exception"
        if not term:
            return HttpResponseBadRequest("term missing")
        if action == "remove":
            jira_exclusion_remove(term, domain=domain)
        elif action == "exclude_and_forget":
            jira_forget_jira_term(term, kind=kind, domain=domain)
        else:
            jira_exclusion_add(term, kind=kind, domain=domain)
        next_url = request.POST.get("next", "").strip()
        if not next_url.startswith("/"):
            next_url = reverse("jira-exclusions")
        return HttpResponseRedirect(next_url)
    return render(
        request,
        "kicli_django/jira_exclusions.html",
        {
            "exclusions": jira_excluded_terms(domain=domain),
            "cache_db": jira_cache_db_path(domain),
            "active_domain": domain,
            "display_mode": display_mode,
            "exclusions_toggle_cards_url": f"{reverse('jira-exclusions')}?display=cards",
            "exclusions_toggle_table_url": f"{reverse('jira-exclusions')}?display=table",
        },
    )


@require_http_methods(["GET", "POST"])

def jira_support_chat_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    history = request.session.get(_JIRA_CHAT_SESSION_KEY, [])
    source_types = request.GET.get("source_types", "").strip() or request.POST.get("source_types", "").strip()
    parsed_source_types = None if not source_types else [part.strip() for part in source_types.split(",") if part.strip()]
    if request.method == "POST":
        if request.POST.get("action", "").strip() == "clear":
            request.session[_JIRA_CHAT_SESSION_KEY] = []
            request.session.modified = True
            return HttpResponseRedirect(reverse("jira-support-chat"))
        question = request.POST.get("question", "").strip()
        if not question:
            return HttpResponseBadRequest("question missing")
        limit = _int_post_param(request, "limit", default=8, minimum=1, maximum=20)
        result = jira_support_chat_answer(question, limit=limit, domain=domain, source_types=parsed_source_types)
        entry = {
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
            "graph_expanded": result["graph_expanded"],
            "prompt": result["prompt"],
            "hits": result.get("hits", []),
            "source_details": result.get("source_details", []),
        }
        history = [entry, *history][:20]
        request.session[_JIRA_CHAT_SESSION_KEY] = history
        request.session.modified = True
        return HttpResponseRedirect(reverse("jira-support-chat"))
    return render(
        request,
        "kicli_django/jira_support_chat.html",
        {
            "history": history,
            "cache_db": jira_cache_db_path(domain),
            "active_domain": domain,
            "source_types": parsed_source_types or ["markdown", "pdf", "jira", "owl"],
        },
    )


@require_http_methods(["GET", "POST"])

def support_chat_view(request: HttpRequest):
    return jira_support_chat_view(request)


@require_http_methods(["GET", "POST"])

def prompt_backlog_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    prompt_context = load_prompt_library_context(domain)
    ollama_settings = ollama_runtime_settings()
    available_models = ollama_available_models(ollama_settings["base_url"])
    default_model = ollama_settings["model"]
    notice = request.GET.get("notice", "").strip()
    error_message = ""

    if request.method == "POST":
        action = request.POST.get("action", "save").strip() or "save"
        if "backlog_content" in request.POST:
            backlog_content = request.POST.get("backlog_content", "").strip()
        else:
            backlog_content = str(prompt_context["backlog_content"]).strip()
        if "templates_content" in request.POST:
            templates_content = request.POST.get("templates_content", "").strip()
        else:
            templates_content = str(prompt_context["templates_content"]).strip()
        model = request.POST.get("model", "").strip() or default_model
        system_prompt = request.POST.get("system_prompt", "").strip()
        try:
            saved_paths = save_prompt_library_documents(
                domain=domain,
                backlog_content=backlog_content,
                templates_content=templates_content,
            )
            notice = "Prompt-Dokumente gespeichert"
            if action in {"run", "run_import", "run_import_semantic"}:
                batch_result = run_prompt_backlog_batch(
                    domain=domain,
                    backlog_content=backlog_content,
                    templates_content=templates_content,
                    model=model,
                    base_url=ollama_settings["base_url"],
                    system_prompt=system_prompt,
                    import_outputs=action in {"run_import", "run_import_semantic"},
                )
                save_prompt_library_documents(
                    domain=domain,
                    backlog_content=batch_result["updated_backlog_content"],
                    templates_content=templates_content,
                )
                notice = f"Batch verarbeitet: {batch_result['processed']} Prompt(s)"
                if batch_result["saved_files"]:
                    notice += f" · gespeichert: {len(batch_result['saved_files'])}"
                if action in {"run_import", "run_import_semantic"}:
                    notice += f" · importiert: {batch_result['imported_records']} Records"
                if action == "run_import_semantic":
                    enqueue = run_dashboard_task("semantic_records_enqueue", domain=domain)
                    run = run_dashboard_task("semantic_records_run", domain=domain)
                    notice += (
                        f" · semantik: queued {enqueue.get('enqueued', 0)},"
                        f" done {run.get('done', 0)}, failed {run.get('failed', 0)}"
                    )
            query = urlencode({"notice": notice})
            return HttpResponseRedirect(f"{reverse('prompt-backlog')}?{query}")
        except (OSError, RuntimeError, ValueError) as exc:
            error_message = str(exc)
            backlog_items = parse_prompt_backlog(backlog_content)
            template_names = sorted(parse_prompt_templates(templates_content).keys())
            prompt_context = {
                **prompt_context,
                "backlog_content": backlog_content,
                "templates_content": templates_content,
                "backlog_items": backlog_items,
                "open_items": [item for item in backlog_items if not bool(item["checked"])],
                "done_items": [item for item in backlog_items if bool(item["checked"])],
                "open_count": sum(1 for item in backlog_items if not bool(item["checked"])),
                "done_count": sum(1 for item in backlog_items if bool(item["checked"])),
                "template_names": template_names,
                "recent_outputs": prompt_batch_outputs(domain, limit=12),
            }
            prompt_context["saved_paths"] = saved_paths if "saved_paths" in locals() else {}

    return render(
        request,
        "kicli_django/prompt_backlog.html",
        {
            **prompt_context,
            "active_domain": domain,
            "available_models": available_models,
            "default_model": default_model,
            "default_system_prompt": f"Du bist ein hilfreicher Assistent fuer die Domain {domain}. Antworte klar und strukturiert.",
            "notice": notice,
            "error_message": error_message,
        },
    )


@require_http_methods(["GET", "POST"])

def ollama_chat_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    history = request.session.get(_OLLAMA_CHAT_SESSION_KEY, [])
    display_history = [
        {**item, "saved_path": display_data_path(item.get("saved_path", "") or None)}
        for item in history
    ]
    ollama_settings = ollama_runtime_settings()
    available_models = ollama_available_models(ollama_settings["base_url"])
    default_model = ollama_settings["model"]
    error_message = ""
    notice = request.GET.get("notice", "").strip()
    saved_path = display_data_path(request.GET.get("saved_path", "").strip() or None)
    imported_notice = request.GET.get("imported", "").strip()

    if request.method == "POST":
        action = request.POST.get("action", "ask").strip()

        if action in {"save_entry", "import_entry", "semantic_entry"}:
            entry_index_raw = request.POST.get("entry_index", "").strip()
            try:
                entry_index = int(entry_index_raw)
            except ValueError:
                return HttpResponseBadRequest("entry index missing")
            if entry_index < 0 or entry_index >= len(history):
                return HttpResponseBadRequest("entry not found")

            entry = history[entry_index]
            saved_path_value = str(entry.get("saved_path", "")).strip()
            saved_file = Path(saved_path_value) if saved_path_value else None

            if action in {"save_entry", "import_entry", "semantic_entry"} and saved_file is None:
                saved_file = save_ollama_chat_markdown(
                    domain=domain,
                    title=str(entry.get("title", "")).strip() or str(entry.get("question", ""))[:80],
                    question=str(entry.get("question", "")).strip(),
                    answer=str(entry.get("answer", "")).strip(),
                    model=str(entry.get("model", default_model)).strip() or default_model,
                    base_url=str(entry.get("base_url", ollama_settings["base_url"])).strip() or ollama_settings["base_url"],
                    system_prompt=str(entry.get("system_prompt", "")).strip(),
                    messages=[],
                )
                entry["saved_path"] = str(saved_file)
                saved_path = display_data_path(saved_file)

            if action in {"import_entry", "semantic_entry"}:
                if saved_file is None:
                    return HttpResponseBadRequest("saved file missing")
                imported = import_markdown_file(
                    saved_file,
                    source_name=saved_file.relative_to(data_dir(domain)).as_posix()
                    if saved_file.is_relative_to(data_dir(domain))
                    else saved_file.name,
                )
                entry["imported"] = f"{imported['imported']} records"
                imported_notice = entry["imported"]

            if action == "semantic_entry":
                enqueue = run_dashboard_task("semantic_records_enqueue", domain=domain)
                run = run_dashboard_task("semantic_records_run", domain=domain)
                entry["semantic"] = f"queued {enqueue.get('enqueued', 0)}, done {run.get('done', 0)}, failed {run.get('failed', 0)}"

            history[entry_index] = entry
            request.session[_OLLAMA_CHAT_SESSION_KEY] = history
            request.session.modified = True
            notice = "Eintrag aktualisiert"
            if entry.get("saved_path"):
                notice += f" · gespeichert: {entry['saved_path']}"
            if entry.get("imported"):
                notice += f" · importiert: {entry['imported']}"
            if entry.get("semantic"):
                notice += f" · semantik: {entry['semantic']}"
            query = urlencode({"notice": notice, "saved_path": entry.get("saved_path", ""), "imported": entry.get("imported", "")})
            return HttpResponseRedirect(f"{reverse('ollama-chat')}?{query}")

        if action == "clear":
            request.session[_OLLAMA_CHAT_SESSION_KEY] = []
            request.session.modified = True
            return HttpResponseRedirect(reverse("ollama-chat"))

        question = request.POST.get("question", "").strip()
        if not question:
            return HttpResponseBadRequest("question missing")

        model = request.POST.get("model", "").strip() or default_model
        system_prompt = request.POST.get("system_prompt", "").strip()
        title = request.POST.get("title", "").strip() or question[:80]
        history_messages: list[dict[str, str]] = []
        for item in reversed(history[:6]):
            user_question = str(item.get("question", "")).strip()
            user_answer = str(item.get("answer", "")).strip()
            if user_question:
                history_messages.append({"role": "user", "content": user_question})
            if user_answer:
                history_messages.append({"role": "assistant", "content": user_answer})
        try:
            result = ollama_chat_answer(
                question,
                history=history_messages,
                model=model,
                base_url=ollama_settings["base_url"],
                system_prompt=system_prompt,
            )
            entry = {
                "title": title,
                "question": result["question"],
                "answer": result["answer"],
                "model": result["model"],
                "base_url": result["base_url"],
                "system_prompt": system_prompt,
                "saved_path": "",
                "imported": "",
                "semantic": "",
            }
            try:
                if action in {"save", "save_import", "save_import_semantic"}:
                    saved_file = save_ollama_chat_markdown(
                        domain=domain,
                        title=title,
                        question=result["question"],
                        answer=result["answer"],
                        model=result["model"],
                        base_url=result["base_url"],
                        system_prompt=system_prompt,
                        messages=result["messages"],
                    )
                    entry["saved_path"] = str(saved_file)
                    saved_path = display_data_path(saved_file)
                    if action in {"save_import", "save_import_semantic"}:
                        imported = import_markdown_file(
                            saved_file,
                            source_name=saved_file.relative_to(data_dir(domain)).as_posix()
                            if saved_file.is_relative_to(data_dir(domain))
                            else saved_file.name,
                        )
                        entry["imported"] = f"{imported['imported']} records"
                        imported_notice = entry["imported"]
                        if action == "save_import_semantic":
                            enqueue = run_dashboard_task("semantic_records_enqueue", domain=domain)
                            run = run_dashboard_task("semantic_records_run", domain=domain)
                            entry["semantic"] = f"queued {enqueue.get('enqueued', 0)}, done {run.get('done', 0)}, failed {run.get('failed', 0)}"
            except (OSError, ValueError) as exc:
                error_message = str(exc)
                history = [entry, *history][:20]
                display_history = [
                    {**item, "saved_path": display_data_path(item.get("saved_path", "") or None)}
                    for item in history
                ]
                request.session[_OLLAMA_CHAT_SESSION_KEY] = history
                request.session.modified = True
                return render(
                    request,
                    "kicli_django/ollama_chat.html",
                    {
                        "history": display_history,
                        "active_domain": domain,
                        "available_models": available_models,
                        "default_model": default_model,
                        "default_system_prompt": f"Du bist ein hilfreicher Assistent fuer die Domain {domain}. Antworte klar und strukturiert.",
                        "notice": notice,
                        "saved_path": saved_path,
                        "imported_notice": imported_notice,
                        "error_message": error_message,
                    },
                )
            history = [entry, *history][:20]
            display_history = [
                {**item, "saved_path": display_data_path(item.get("saved_path", "") or None)}
                for item in history
            ]
            request.session[_OLLAMA_CHAT_SESSION_KEY] = history
            request.session.modified = True
            notice = "Antwort erzeugt"
            if entry["saved_path"]:
                notice += f" · gespeichert: {display_data_path(entry['saved_path'])}"
            if entry["imported"]:
                notice += f" · importiert: {entry['imported']}"
            if entry["semantic"]:
                notice += f" · semantik: {entry['semantic']}"
            query = urlencode(
                {
                    "notice": notice,
                    "saved_path": entry["saved_path"],
                    "imported": entry["imported"],
                }
            )
            return HttpResponseRedirect(f"{reverse('ollama-chat')}?{query}")
        except RuntimeError as exc:
            error_message = str(exc)

    return render(
        request,
        "kicli_django/ollama_chat.html",
        {
    "history": display_history,
            "active_domain": domain,
            "available_models": available_models,
            "default_model": default_model,
            "default_system_prompt": f"Du bist ein hilfreicher Assistent fuer die Domain {domain}. Antworte klar und strukturiert.",
            "notice": notice,
            "saved_path": saved_path,
            "imported_notice": imported_notice,
            "error_message": error_message,
        },
    )


@require_GET

def jira_hybrid_search_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    query = request.GET.get("q", "").strip()
    limit = _int_param(request, "limit", default=8, minimum=1, maximum=50)
    display_mode = _display_mode(request, default="table")
    result = None
    if query:
        result = jira_hybrid_search(query, limit=limit, domain=domain)
    return render(
        request,
        "kicli_django/jira_hybrid_search.html",
        {
            "query": query,
            "limit": limit,
            "result": result,
            "cache_db": jira_cache_db_path(domain),
            "active_domain": domain,
            "display_mode": display_mode,
            "hybrid_toggle_cards_url": f"{reverse('jira-hybrid-search')}?{urlencode({'q': query, 'limit': limit, 'display': 'cards'})}",
            "hybrid_toggle_table_url": f"{reverse('jira-hybrid-search')}?{urlencode({'q': query, 'limit': limit, 'display': 'table'})}",
        },
    )


@require_GET

def jira_daily_timeline_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    days = _int_param(request, "days", default=14, minimum=1, maximum=365)
    display_mode = _display_mode(request, default="table")
    result = jira_daily_timeline(days=days, domain=domain)
    return render(
        request,
        "kicli_django/jira_daily_timeline.html",
        {
            **result,
            "active_domain": domain,
            "display_mode": display_mode,
            "timeline_toggle_cards_url": f"{reverse('jira-daily-timeline')}?{urlencode({'days': days, 'display': 'cards'})}",
            "timeline_toggle_table_url": f"{reverse('jira-daily-timeline')}?{urlencode({'days': days, 'display': 'table'})}",
        },
    )


@require_GET

def jira_graph_explorer_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    issue_key = request.GET.get("issue_key", "").strip()
    limit = _int_param(request, "limit", default=20, minimum=1, maximum=200)
    rebuild = request.GET.get("rebuild", "").strip() == "1"
    display_mode = _display_mode(request, default="table")
    result = jira_graph_explorer(issue_key=issue_key, limit=limit, rebuild=rebuild, domain=domain)
    return render(
        request,
        "kicli_django/jira_graph_explorer.html",
        {
            **result,
            "active_domain": domain,
            "limit": limit,
            "rebuild": rebuild,
            "display_mode": display_mode,
            "graph_toggle_cards_url": f"{reverse('jira-graph-explorer')}?{urlencode({'issue_key': issue_key, 'limit': limit, 'rebuild': '1' if rebuild else '', 'display': 'cards'})}",
            "graph_toggle_table_url": f"{reverse('jira-graph-explorer')}?{urlencode({'issue_key': issue_key, 'limit': limit, 'rebuild': '1' if rebuild else '', 'display': 'table'})}",
        },
    )


@require_GET

def jira_domain_analysis_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    limit_terms = _int_param(request, "terms", default=20, minimum=1, maximum=200)
    min_count = _int_param(request, "min_count", default=2, minimum=1, maximum=50)
    query = request.GET.get("q", "").strip()
    limit_hits = _int_param(request, "hits", default=8, minimum=1, maximum=50)
    display_mode = _display_mode(request, default="table")
    result = jira_domain_analysis(
        limit_terms=limit_terms,
        min_count=min_count,
        query=query,
        limit_hits=limit_hits,
        domain=domain,
    )
    return render(
        request,
        "kicli_django/jira_domain_analysis.html",
        {
            **result,
            "active_domain": domain,
            "display_mode": display_mode,
            "analysis_toggle_cards_url": f"{reverse('jira-domain-analysis')}?{urlencode({'terms': limit_terms, 'min_count': min_count, 'q': query, 'hits': limit_hits, 'display': 'cards'})}",
            "analysis_toggle_table_url": f"{reverse('jira-domain-analysis')}?{urlencode({'terms': limit_terms, 'min_count': min_count, 'q': query, 'hits': limit_hits, 'display': 'table'})}",
        },
    )


@require_GET

def semantic_terms_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    status = request.GET.get("status", "").strip() or None
    limit = _int_param(request, "limit", default=300, minimum=1, maximum=2000)
    display_mode = _display_mode(request, default="table")
    items = semantic_terms(status=status, limit=limit, domain=domain)
    return render(
        request,
        "kicli_django/semantic_terms.html",
        {
            "terms": items,
            "status": status or "(all)",
            "limit": limit,
            "active_domain": domain,
            "display_mode": display_mode,
            "semantic_terms_toggle_cards_url": f"{reverse('semantic-terms')}?{urlencode({'status': status or '', 'limit': limit, 'display': 'cards'})}",
            "semantic_terms_toggle_table_url": f"{reverse('semantic-terms')}?{urlencode({'status': status or '', 'limit': limit, 'display': 'table'})}",
        },
    )


@require_GET

def semantic_term_detail_view(request: HttpRequest, term_id: str):
    detail = semantic_term_detail(term_id, domain=_active_semantic_domain(request))
    if detail is None:
        return HttpResponseBadRequest("term not found")
    return render(
        request,
        "kicli_django/semantic_term_detail.html",
        {
            "term": detail["term"],
            "facts": detail["facts"],
            "relations": detail["relations"],
        },
    )


@require_http_methods(["POST"])

def import_action(request: HttpRequest):
    raw_path = request.POST.get("path", "").strip()
    import_type = request.POST.get("import_type", "file")
    next_page = request.POST.get("next", "dashboard").strip() or "dashboard"
    if not raw_path:
        return HttpResponseBadRequest("path missing")
    path = Path(raw_path).expanduser()
    
    should_treat_as_directory = (
        import_type == "directory"
        or raw_path.endswith(("/", "\\"))
        or (not path.suffix and not raw_path.startswith(("http://", "https://")))
    )

    if path.is_file():
        if path.suffix.lower() == ".pdf":
            domain = _active_semantic_domain(request)
            try:
                job_id = create_pdf_import_job(str(path), domain=domain)
            except FileNotFoundError:
                return HttpResponseBadRequest("PDF file not found")
            messages.success(request, f"PDF import queued: {job_id}")
            return HttpResponseRedirect(f"{reverse('pdf-import-jobs')}?domain={domain}")
        # Detect OWL/RDF files by extension
        if path.suffix.lower() in {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}:
            import_ontology_file(path)
        else:
            import_markdown_file(path, source_name=request.POST.get("source_name") or path.name)
    elif should_treat_as_directory:
        path.mkdir(parents=True, exist_ok=True)
        # Auto-detect which importer to use based on file types in directory
        md_files = list(path.glob("**/*.md"))
        pdf_files = discover_pdf_files(path)
        ontology_suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
        ontology_files = [p for p in path.glob("**/*") if p.suffix.lower() in ontology_suffixes]

        if pdf_files:
            domain = _active_semantic_domain(request)
            created = 0
            for pdf_path in sorted({p.resolve(strict=False) for p in pdf_files}):
                try:
                    create_pdf_import_job(str(pdf_path), domain=domain)
                    created += 1
                except (FileNotFoundError, OSError, ValueError):
                    continue
            messages.success(request, f"Queued {created} PDF jobs for domain {domain}.")
            return HttpResponseRedirect(f"{reverse('pdf-import-jobs')}?domain={domain}")

        # Import all remaining types found (recursive)
        if md_files:
            import_markdown_directory(path)
        if ontology_files:
            import_ontology_directory(path)

        if not (md_files or pdf_files or ontology_files):
            messages.info(request, f"Directory prepared: {path}. No importable files found yet.")
            return HttpResponseRedirect(reverse(next_page))
    elif raw_path.startswith(("http://", "https://")) and import_type in {"file", "ontology"}:
        import_ontology_url(raw_path)
    else:
        return HttpResponseBadRequest("path not importable")
    return HttpResponseRedirect(reverse(next_page))


@require_http_methods(["POST"])

def generate_action(request: HttpRequest):
    source_id = request.POST.get("source_id", "").strip()
    if not source_id:
        return HttpResponseBadRequest("source_id missing")
    generate_all_artifacts(source_id, max_items=int(request.POST.get("max_items", "8")))
    return HttpResponseRedirect(reverse("source-detail", args=[source_id]))


@require_http_methods(["GET", "POST"])

def pdf_import_jobs_view(request: HttpRequest):
    """View PDF import jobs dashboard. Also handles new job enqueuing via POST."""
    
    if request.method == "POST":
        action = request.POST.get("action", "enqueue").strip() or "enqueue"
        domain = _active_semantic_domain(request)
        if action == "delete-one":
            job_id = request.POST.get("job_id", "").strip()
            if not job_id:
                return HttpResponseBadRequest("job_id missing")
            result = delete_pdf_import_jobs([job_id], domain=domain)
            if result["deleted"]:
                messages.success(request, f"Deleted PDF job: {job_id}")
            elif result["skipped_active"]:
                messages.error(request, f"Job is still active and was not deleted: {job_id}")
            else:
                messages.info(request, f"Job not found or outside domain: {job_id}")
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        if action == "delete-selected":
            job_ids = [job_id.strip() for job_id in request.POST.getlist("job_ids") if job_id.strip()]
            if not job_ids:
                return HttpResponseBadRequest("job_ids missing")
            result = delete_pdf_import_jobs(job_ids, domain=domain)
            messages.success(
                request,
                f"Deleted {result['deleted']} job(s); skipped active: {result['skipped_active']}, missing: {result['skipped_missing']}",
            )
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        if action == "delete-old":
            jobs_to_delete = [
                job["job_id"]
                for job in pdf_import_jobs(domain=domain, limit=2000)
                if job["status"] in {"done", "failed"}
            ]
            result = delete_pdf_import_jobs(jobs_to_delete, domain=domain)
            messages.success(request, f"Deleted {result['deleted']} old job(s) for {domain}.")
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        if action == "reset-stale":
            timeout_seconds = _int_post_param(request, "timeout_seconds", 30, minimum=5, maximum=3600)
            processor = get_pdf_batch_processor()
            cleanup = processor.cleanup_stale_jobs(domain=domain, timeout_seconds=timeout_seconds)
            retry = processor.process_pending_jobs(domain=domain, timeout_seconds=timeout_seconds)
            messages.success(
                request,
                (
                    f"Reset stale PDF jobs for {domain}: "
                    f"timed out {cleanup.get('timed_out', 0)}, "
                    f"recovered {retry.get('claimed', 0)} pending jobs "
                    f"({retry.get('done', 0)} done, {retry.get('failed', 0)} failed)."
                ),
            )
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        if action == "process-pending":
            timeout_seconds = _int_post_param(request, "timeout_seconds", 600, minimum=5, maximum=3600)
            processor = get_pdf_batch_processor()
            result = processor.process_pending_jobs(domain=domain, timeout_seconds=timeout_seconds)
            messages.success(
                request,
                (
                    f"Processed PDF jobs for {domain}: "
                    f"claimed {result.get('claimed', 0)}, "
                    f"done {result.get('done', 0)}, "
                    f"failed {result.get('failed', 0)}, "
                    f"recovered stale {result.get('timed_out', 0)}."
                ),
            )
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")

        pdf_path = request.POST.get("pdf_path", "").strip()
        domain = request.POST.get("domain", "").strip() or domain
        
        if not pdf_path or not domain:
            return HttpResponseBadRequest("pdf_path and domain required")
        
        try:
            job_id = create_pdf_import_job(pdf_path, domain=domain)
            messages.success(request, f"PDF import job created: {job_id}")
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        except Exception as exc:
            messages.error(request, f"Failed to create job: {exc}")
            return HttpResponseRedirect(reverse("pdf-import-jobs"))
    
    # Handle GET: Show jobs dashboard
    domain = _active_semantic_domain(request)
    status = request.GET.get("status", "").strip() or None
    jobs = pdf_import_jobs(domain=domain, status=status, limit=200)
    report = pdf_import_report(domain=domain, limit=8)
    
    summary = {
        "total": len(jobs),
        "pending": sum(1 for j in jobs if j["status"] == "pending"),
        "processing": sum(1 for j in jobs if j["status"] == "processing"),
        "done": sum(1 for j in jobs if j["status"] == "done"),
        "failed": sum(1 for j in jobs if j["status"] == "failed"),
    }
    
    return render(
        request,
        "kicli_django/pdf_import_jobs.html",
        {
            "jobs": jobs,
            "summary": summary,
            "status": status or "(all)",
            "active_domain": domain,
            "report": report,
        },
    )


@require_GET

def pdf_job_detail_view(request: HttpRequest, job_id: str):
    """Display a compact report for a completed PDF import job."""
    domain = _active_semantic_domain(request)
    processor = get_pdf_batch_processor()
    job = processor.get_job(job_id)
    if job is None or job.domain != domain:
        return HttpResponseBadRequest("job not found")

    summary = {
        "job_id": job.job_id,
        "domain": job.domain,
        "status": job.status,
        "pdf_path": job.pdf_path,
        "display_pdf_path": display_data_path(job.pdf_path),
        "source_id": job.source_id,
        "artifact_id": job.artifact_id,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "pages_total": job.pages_total,
        "pages_processed": job.pages_processed,
        "error_message": job.error_message,
        "content_preview": job.content_preview,
    }
    report = {}
    if job.result_json:
        try:
            report = json.loads(job.result_json)
        except (TypeError, ValueError):
            report = {}
    return render(
        request,
        "kicli_django/pdf_job_detail.html",
        {
            "job": summary,
            "report": report,
            "source_url": reverse("source-detail", args=[job.source_id]) if job.source_id else None,
            "back_url": reverse("pdf-import-jobs") + f"?domain={domain}",
        },
    )


@require_GET

def pdf_import_jobs_json(request: HttpRequest):
    """Return JSON with PDF import job status (for auto-refresh)."""
    domain = _active_semantic_domain(request)
    status = request.GET.get("status", "").strip() or None
    jobs = pdf_import_jobs(domain=domain, status=status)
    
    summary = {
        "total": len(jobs),
        "pending": sum(1 for j in jobs if j["status"] == "pending"),
        "processing": sum(1 for j in jobs if j["status"] == "processing"),
        "done": sum(1 for j in jobs if j["status"] == "done"),
        "failed": sum(1 for j in jobs if j["status"] == "failed"),
    }
    
    return JsonResponse({"jobs": jobs, "summary": summary})


@require_GET

def pdf_import_report_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    report = pdf_import_report(domain=domain, limit=12)
    return render(
        request,
        "kicli_django/pdf_import_report.html",
        {
            "active_domain": domain,
            "report": report,
        },
    )
