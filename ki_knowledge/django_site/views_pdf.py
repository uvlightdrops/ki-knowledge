"""PDF inventory, import queue, reports and status HTTP views."""

from __future__ import annotations

import json

from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from ki_knowledge.integrations.pdf_inventory import scan_configured_pdf_inventory

from .data_display import display_data_path
from .pdf_jobs import (
    create_pdf_import_job,
    delete_pdf_import_jobs,
    get_pdf_batch_processor,
    pdf_import_jobs,
    pdf_import_report,
    start_pdf_worker,
)
from .views_common import _active_semantic_domain, _choice_param, _int_post_param


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
            timeout_seconds = _int_post_param(request, "timeout_seconds", 3600, minimum=30, maximum=86400)
            processor = get_pdf_batch_processor()
            cleanup = processor.cleanup_stale_jobs(domain=domain, timeout_seconds=timeout_seconds)
            messages.success(
                request,
                f"Expired {cleanup.get('timed_out', 0)} stale worker lease(s) for {domain}. "
                "No PDFs were processed; expired jobs are marked failed and can be retried explicitly.",
            )
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        if action == "retry-failed":
            processor = get_pdf_batch_processor()
            result = processor.retry_failed_jobs(domain=domain)
            messages.success(request, f"Requeued {result['retried']} failed PDF job(s) for {domain}.")
            return HttpResponseRedirect(reverse("pdf-import-jobs") + f"?domain={domain}")
        if action == "process-pending":
            result = start_pdf_worker(domain)
            if result["started"]:
                messages.success(request, f"PDF-Worker gestartet: {result['pending_at_start']} wartende Jobs für {domain}.")
            elif result["reason"] == "empty":
                messages.info(request, f"Keine wartenden PDF-Jobs für {domain}.")
            elif result["reason"] == "active":
                active_worker = result.get("worker") or {}
                messages.info(
                    request,
                    f"Ein PDF-Worker läuft bereits ({active_worker.get('domain', 'unbekannte Domain')}).",
                )
            else:
                messages.error(request, f"PDF-Worker konnte nicht gestartet werden: {result.get('error', 'unbekannter Fehler')}")
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
    worker_run = get_pdf_batch_processor().get_worker_run()
    
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
            "status_filter": status or "",
            "active_domain": domain,
            "report": report,
            "worker_run": worker_run,
            "worker_active": bool(worker_run and worker_run["status"] in {"starting", "running"}),
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
    
    worker = get_pdf_batch_processor().get_worker_run()
    return JsonResponse({"jobs": jobs, "summary": summary, "worker": worker})


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


@require_GET

def pdf_inventory_view(request: HttpRequest):
    """Read-only list of PDFs belonging to the active domain.

    Scanning only happens on an explicit ``?scan=1`` request; nothing is imported.
    """
    from .widget_catalog_preview import catalog_active_domain

    active_domain = catalog_active_domain(request)
    request._widget_catalog_domain = active_domain
    scan_requested = request.GET.get("scan", "").strip() == "1"
    include_text = request.GET.get("text", "").strip() == "1"
    sort = _choice_param(request, "sort", "title", {"title", "path"})
    inventory = None
    if scan_requested:
        inventory = scan_configured_pdf_inventory(domain=active_domain, include_first_page_text=include_text)
        if sort == "path":
            inventory.entries.sort(key=lambda entry: entry.relative_path)
    return render(
        request,
        "kicli_django/pdf_inventory.html",
        {
            "active_domain": active_domain,
            "scan_requested": scan_requested,
            "include_text": include_text,
            "sort": sort,
            "inventory": inventory,
            "summary": inventory.summary if inventory else None,
        },
    )
