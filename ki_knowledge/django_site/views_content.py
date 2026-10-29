"""Stored records, artifact browsing and artifact generation actions."""

from __future__ import annotations

from urllib.parse import urlencode
import re

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .data_display import artifact_content_preview, display_source_ref
from .knowledge_browser import generate_all_artifacts, store
from .knowledge_summary import domain_source_ids
from .views_common import (
    _active_semantic_domain,
    _display_mode,
    _int_param,
    _paginate_items,
    _redirect_with_filters,
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


_PREVIEW_WORDS = 32
_PREVIEW_CHARS = 260


def _record_preview(content: str | None) -> dict[str, str]:
    """Opening words of a record (markdown markers stripped) plus a longer tooltip text."""
    text = " ".join(re.sub(r"^\s*(?:#+|[-*+>]|\d+[.)])\s+", "", line) for line in str(content or "").splitlines())
    text = " ".join(text.split())
    words = text.split(" ")
    preview = " ".join(words[:_PREVIEW_WORDS])
    if len(preview) > _PREVIEW_CHARS:
        preview = preview[:_PREVIEW_CHARS].rsplit(" ", 1)[0]
    if preview != text:
        preview += " …"
    return {"preview": preview, "preview_full": text[:400]}


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
            scope = [source_id] if source_id else allowed_sources
            scope = [item for item in scope if item in allowed_sources]
            items, _total = store_obj.query_records(scope, block_type=block_type)
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
    scope = [source_id] if source_id else allowed_sources
    scope = [item for item in scope if item in allowed_sources]
    records_list, total_record_count = store_obj.query_records(
        scope,
        block_type=block_type,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    has_more = (page - 1) * page_size + len(records_list) < total_record_count
    display_records = [
        {
            **record.__dict__,
            "display_source_id": display_source_ref(record.source_id),
            "display_path": display_source_ref(record.path),
            **_record_preview(record.content),
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
            "records": display_records,
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


@require_http_methods(["POST"])

def generate_action(request: HttpRequest):
    source_id = request.POST.get("source_id", "").strip()
    if not source_id:
        return HttpResponseBadRequest("source_id missing")
    generate_all_artifacts(source_id, max_items=int(request.POST.get("max_items", "8")))
    return HttpResponseRedirect(reverse("source-detail", args=[source_id]))
