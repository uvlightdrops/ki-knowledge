"""Semantic term and enrichment-job HTTP views."""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from ki_knowledge.django_site.knowledge_summary import (
    semantic_job_detail,
    semantic_jobs,
    semantic_store,
    semantic_term_detail,
    semantic_terms,
)

from .views_common import _active_semantic_domain, _display_mode, _int_param, _paginate_items


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
