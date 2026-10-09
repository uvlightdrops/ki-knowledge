"""Book pipeline overview: per-stage progress of a domain's documents."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from widgetkit_django.table import (
    ChoiceFilter,
    SortOption,
    TablePreset,
    TableSpec,
    TextFilter,
    facet_options,
    paginate,
    parse_table_query,
    preset_links,
    sort_links,
)

from ki_knowledge.integrations.document_pipeline import (
    COMPLETE_STATUSES,
    FLAG_LABELS,
    STAGES,
    STAGE_BY_KEY,
    STATUS_LABELS,
    DocumentProgress,
)

from .book_pipeline import book_pipeline_overview, refresh_book_pipeline
from .views_common import _active_semantic_domain

__all__ = ["book_pipeline_view", "book_structure_view", "semantic_search_view"]

PIPELINE_PAGE_SIZE = 50
_SORTS = (
    ("title", "Titel"),
    ("progress", "Fortschritt"),
    ("pages", "Seiten"),
    ("chars", "Zeichen/Seite"),
    ("empty", "Leere Seiten"),
)
_PRESETS = (
    TablePreset("all", "Alle", {}),
    TablePreset("ingest-failed", "Import fehlgeschlagen", {"stage": "ingest", "status": "failed"}),
    TablePreset("quality-warning", "Qualitätshinweise", {"stage": "quality", "status": "warning"}),
    TablePreset("needs-ocr", "OCR nötig", {"flag": "needs_ocr"}),
    TablePreset("structure-open", "Gliederung offen", {"stage": "structure", "status": "pending"}),
)


def _table_spec() -> TableSpec:
    return TableSpec(
        filters=(
            ChoiceFilter("stage", "Stufe", tuple((stage.key, stage.label) for stage in STAGES)),
            ChoiceFilter("status", "Status", tuple(STATUS_LABELS.items())),
            ChoiceFilter("flag", "Hinweis", tuple(FLAG_LABELS.items())),
            TextFilter("q", "Suche", max_length=200, placeholder="Titel oder Quelle …"),
        ),
        sorts=tuple(SortOption(key, label) for key, label in _SORTS),
        default_sort="title",
    )


def _metric(document: DocumentProgress, key: str, default: Any = 0) -> Any:
    quality = document.state("quality").metrics
    if key in quality:
        return quality[key]
    return document.state("ingest").metrics.get(key, default)


def _matches(document: DocumentProgress, stage: str, status: str, flag: str, query: str) -> bool:
    if status:
        statuses = [document.effective_status(stage)] if stage else [document.effective_status(s.key) for s in STAGES]
        if status not in statuses:
            return False
    if flag and flag not in document.flags:
        return False
    if query:
        haystack = f"{document.source_id} {_metric(document, 'title', '')}".lower()
        if query.lower() not in haystack:
            return False
    return True


def _sort_key(sort: str):
    def title(document: DocumentProgress) -> str:
        return str(_metric(document, "title", "") or document.source_id).lower()

    return {
        "progress": lambda d: (-d.completed_stages, title(d)),
        "pages": lambda d: (-int(_metric(d, "pages_total", 0) or 0), title(d)),
        "chars": lambda d: (int(_metric(d, "chars_per_page", 0) or 0), title(d)),
        "empty": lambda d: (-float(_metric(d, "empty_page_ratio", 0) or 0), title(d)),
    }.get(sort, title)


def _row(document: DocumentProgress) -> dict[str, Any]:
    ingest = document.state("ingest")
    imported = document.effective_status("ingest") in COMPLETE_STATUSES
    return {
        "source_id": document.source_id,
        "title": _metric(document, "title", "") or document.source_id,
        "path": _metric(document, "path", ""),
        "detail_url": reverse("source-detail", args=[document.source_id]) if imported else "",
        "records_url": f"{reverse('records')}?{urlencode({'source_id': document.source_id})}" if imported else "",
        "pages": _metric(document, "pages_total", 0),
        "blocks": ingest.metrics.get("blocks", 0),
        "chars_per_page": _metric(document, "chars_per_page", "") if imported else "",
        "empty_percent": round(100 * float(_metric(document, "empty_page_ratio", 0) or 0)) if imported else "",
        "flags": [{"key": flag, "label": FLAG_LABELS.get(flag, flag)} for flag in document.flags],
        "error": ingest.error,
        "completed": document.completed_stages,
        "stages": [
            {
                "key": stage.key,
                "label": stage.label,
                "status": document.effective_status(stage.key),
                "status_label": STATUS_LABELS.get(document.effective_status(stage.key), ""),
                "error": document.state(stage.key).error,
                "detail": _stage_detail(document, stage.key),
                "url": (
                    reverse("book-structure", args=[document.source_id])
                    if stage.key == "structure" and document.state("structure").metrics
                    else ""
                ),
            }
            for stage in STAGES
        ],
        "reference_sections": ingest.metrics.get("reference_sections", 0),
    }


def _stage_detail(document: DocumentProgress, stage_key: str) -> str:
    metrics = document.state(stage_key).metrics
    if stage_key == "structure" and metrics:
        text = f"{metrics.get('sections', 0)} Abschnitte"
        if metrics.get("verified"):
            return (
                f"{text}, Kapitel-Recall {100 * float(metrics.get('titled_recall', 0)):.0f} %, "
                f"Präzision {100 * float(metrics.get('precision', 0)):.0f} %"
            )
        return f"{text}, ungeprüft"
    if stage_key in {"embeddings", "terms"} and metrics.get("blocks"):
        return f"{metrics.get('blocks_done', 0)} / {metrics['blocks']} Blöcke"
    return ""


@require_http_methods(["GET", "POST"])
def book_pipeline_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    base_url = reverse("book-pipeline")
    if request.method == "POST":
        if request.POST.get("action", "").strip() != "refresh":
            return HttpResponseBadRequest("action missing")
        result = refresh_book_pipeline(active_domain)
        messages.success(request, f"Status neu berechnet: {result['documents']} Bücher.")
        return HttpResponseRedirect(base_url)

    spec = _table_spec()
    table_query = parse_table_query(spec, request.GET)
    values = dict(table_query.values)
    stage, status, flag, query = values.get("stage", ""), values.get("status", ""), values.get("flag", ""), values.get("q", "")
    overview = book_pipeline_overview(active_domain)
    documents = overview["documents"]
    selected = sorted(
        (document for document in documents if _matches(document, stage, status, flag, query)),
        key=_sort_key(values.get("sort", "title")),
    )
    page_data = paginate(selected, table_query, PIPELINE_PAGE_SIZE, base_url)

    status_stage = stage or "ingest"
    status_counts = {key: 0 for key in STATUS_LABELS}
    for document in documents:
        status_counts[document.effective_status(status_stage)] += 1
    flag_counts = {key: sum(1 for document in documents if key in document.flags) for key in FLAG_LABELS}
    facets = [
        {
            "label": f"Status · {STAGE_BY_KEY[status_stage].label}",
            "options": facet_options(spec, table_query, "status", {k: v for k, v in status_counts.items() if v}, base_url),
        },
        {"label": "Hinweise", "options": facet_options(spec, table_query, "flag", {k: v for k, v in flag_counts.items() if v}, base_url)},
    ]
    toolbar_context = {
        "base_url": base_url,
        "presets": preset_links(spec, table_query, _PRESETS, base_url),
        "facets": facets,
        "text_filters": [{"key": "q", "label": "Suche", "value": query, "max_length": 200, "placeholder": "Titel oder Quelle …"}],
        "hidden_items": [(k, v) for k, v in table_query.hidden_items() if k in {"stage", "status", "flag"}],
        "sort_options": sort_links(spec, table_query, base_url),
        "choice_params": [],
        "reset_url": base_url,
    }
    funnel_rows = [
        {
            **item,
            "open_href": parse_table_query(spec, {}).url(base_url, stage=item["key"], status="pending"),
            "done_href": parse_table_query(spec, {}).url(base_url, stage=item["key"], status="done"),
        }
        for item in overview["funnel"]
    ]
    return render(
        request,
        "kicli_django/book_pipeline.html",
        {
            "active_domain": active_domain,
            "funnel": funnel_rows,
            "stages": STAGES,
            "total_documents": len(documents),
            "last_updated": overview["last_updated"].replace("T", " ")[:16],
            "toolbar_html": mark_safe(render_to_string("widgetkit_django/table_toolbar.html", toolbar_context)),
            "rows": [_row(document) for document in page_data.items],
            "total": page_data.total,
            "first_index": page_data.first_index,
            "last_index": page_data.last_index,
            "prev_href": page_data.prev_href,
            "next_href": page_data.next_href,
            "header_links": {key: table_query.url(base_url, sort=key, page=1) for key, _label in _SORTS},
            "sort": values.get("sort", "title"),
            "active_stage": STAGE_BY_KEY[stage].label if stage else "",
            "clear_stage_href": table_query.url(base_url, stage=None, status=None, page=1),
        },
    )


def book_structure_view(request: HttpRequest, source_id: str):
    """Detected outline of one book next to its reference outline (if any)."""
    from django.conf import settings
    from django.http import Http404

    from ki_knowledge.integrations.knowledge_store import KnowledgeStore
    from ki_knowledge.integrations.structure_eval import PAGE_TOLERANCE, TITLE_SIMILARITY, similarity

    from .book_structure import DETECTED_STRUCTURE_ARTIFACT
    from .source_workflow import REFERENCE_STRUCTURE_ARTIFACT

    store = KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)
    source = store.get_source(source_id)
    if source is None:
        raise Http404(source_id)
    detected = store.list_artifacts(source_id=source_id, artifact_type=DETECTED_STRUCTURE_ARTIFACT)
    reference = store.list_artifacts(source_id=source_id, artifact_type=REFERENCE_STRUCTURE_ARTIFACT)
    detected_meta = detected[0].metadata if detected else {}
    headings = list(detected_meta.get("headings", []))
    sections = list(reference[0].metadata.get("sections", [])) if reference else []

    def matched(item: dict[str, Any], others: list[dict[str, Any]], page_key: str, other_page_key: str) -> bool:
        page = int(item.get(page_key, 0) or 0)
        return any(
            abs(int(other.get(other_page_key, 0) or 0) - page) <= PAGE_TOLERANCE
            and similarity(str(item.get("title", "")), str(other.get("title", ""))) >= TITLE_SIMILARITY
            for other in others
        )

    records_url = f"{reverse('records')}?{urlencode({'source_id': source_id})}"
    return render(
        request,
        "kicli_django/book_structure.html",
        {
            "source": source,
            "records_url": records_url,
            "method": detected_meta.get("method", ""),
            "evaluation": detected_meta.get("evaluation"),
            "evaluation_flat": detected_meta.get("evaluation_flat"),
            "headings": [
                {**heading, "matched": bool(sections) and matched(heading, sections, "page", "page_index")}
                for heading in headings
            ],
            "sections": [
                {**section, "matched": matched(section, headings, "page_index", "page")} for section in sections
            ],
            "has_reference": bool(sections),
        },
    )


@require_http_methods(["GET"])
def semantic_search_view(request: HttpRequest):
    """Semantic block search over the active domain (Ollama embeddings)."""
    from .block_search import semantic_block_search

    domain = _active_semantic_domain(request)
    query = request.GET.get("q", "").strip()
    try:
        limit = max(1, min(100, int(request.GET.get("limit", "20"))))
    except ValueError:
        limit = 20
    result = semantic_block_search(domain, query, limit=limit)
    hits = []
    for record, score in result["hits"]:
        text = " ".join(str(record.content or "").split())
        hits.append(
            {
                "record": record,
                "score": round(100 * score),
                "preview": text[:420] + ("…" if len(text) > 420 else ""),
                "source_title": str(record.metadata.get("source_name", "") or record.source_id),
                "page": record.metadata.get("page") or record.title,
                "records_url": f"{reverse('records')}?{urlencode({'source_id': record.source_id})}",
            }
        )
    coverage = round(100 * result["embedded"] / result["blocks"], 1) if result["blocks"] else 0.0
    return render(
        request,
        "kicli_django/semantic_search.html",
        {
            "domain": domain,
            "query": query,
            "limit": limit,
            "hits": hits,
            "error": result["error"],
            "model": result["model"],
            "embedded": result["embedded"],
            "blocks": result["blocks"],
            "coverage": coverage,
        },
    )
