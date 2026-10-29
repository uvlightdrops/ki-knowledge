"""Jira retrieval, term analysis and exclusion HTTP views."""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from ki_knowledge.django_site.jira_workflow import (
    jira_cache_db_path,
    jira_daily_timeline,
    jira_domain_analysis,
    jira_domain_terms,
    jira_excluded_terms,
    jira_exclusion_add,
    jira_exclusion_remove,
    jira_forget_jira_term,
    jira_graph_explorer,
    jira_hybrid_search,
)

from .views_common import (
    _active_semantic_domain,
    _choice_param,
    _display_mode,
    _int_param,
    _paginate_items,
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
