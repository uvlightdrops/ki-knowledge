"""Source inventory filters, browsing and per-file/source actions."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods
from markupsafe import Markup
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

from .dashboard_registry import default_widget_ids_for_area
from .knowledge_browser import store
from .views_common import (
    _active_semantic_domain,
    _load_dashboard_widget_ids,
    _load_dashboard_widget_widths,
)


_SOURCES_SORT_OPTIONS = (
    ("updated", "Zuletzt aktualisiert"), ("title", "Titel"), ("records", "Meiste Einträge"),
    ("kind", "Typ"), ("path", "Pfad"), ("status", "Status"),
)


_SOURCES_STATUS_OPTIONS = (
    ("imported", "Importiert"), ("new", "Neu"), ("queued", "Warteschlange"),
    ("failed", "Fehlgeschlagen"), ("unsupported", "Nicht unterstützt"),
)


_SOURCES_PRESETS = (
    TablePreset("all", "Alle", {}),
    TablePreset("new", "Neu", {"status": "new"}),
    TablePreset("failed", "Fehlgeschlagen", {"status": "failed"}),
    TablePreset("pdf", "PDFs", {"kind": "pdf"}),
    TablePreset("markdown", "Markdown", {"kind": "markdown"}),
    TablePreset("owl", "Ontologien", {"kind": "owl"}),
)


def _sources_table_spec() -> TableSpec:
    from .sources_browser import FOLDER_KEYS, KIND_KEYS, STATUS_KEYS, SORT_KEYS

    kind_labels = {"markdown": "Markdown", "pdf": "PDF", "owl": "Ontologie", "table": "Tabelle", "image": "Bild", "tei": "TEI", "other": "Sonstige"}
    folder_labels = {key: f"{key}/" for key in (*FOLDER_KEYS, "jira")}
    return TableSpec(
        filters=(
            ChoiceFilter("kind", "Typ", tuple((key, kind_labels.get(key, key)) for key in KIND_KEYS)),
            ChoiceFilter("status", "Status", tuple((key, label) for key, label in _SOURCES_STATUS_OPTIONS if key in STATUS_KEYS)),
            ChoiceFilter("folder", "Herkunft", tuple((key, folder_labels[key]) for key in (*FOLDER_KEYS, "jira"))),
            TextFilter("path", "Pfad", max_length=200, placeholder="Unterordner/Pfadpräfix"),
            TextFilter("q", "Suche", max_length=200, placeholder="Titel oder Pfad suchen …"),
        ),
        sorts=tuple(SortOption(key, label) for key, label in _SOURCES_SORT_OPTIONS if key in SORT_KEYS),
        default_sort="updated",
        choice_params=(ChoiceFilter("display", "Darstellung", (("table", "Tabelle"), ("cards", "Karten"))),),
    )


def _sources_query(params: Any):
    raw = params.copy() if hasattr(params, "copy") else dict(params)
    if not raw.get("kind") and raw.get("type"):
        raw["kind"] = raw.get("type")
    return parse_table_query(_sources_table_spec(), raw)


def _sources_filters(params: Any) -> dict[str, str]:
    query = _sources_query(params)
    return {**dict(query.values), "page": str(query.page) if query.page > 1 else ""}


def _sources_url(filters: dict[str, str], **overrides: str) -> str:
    spec = _sources_table_spec()
    page = filters.get("page", "")
    query = parse_table_query(spec, {**filters, "page": page})
    return query.url(reverse("sources"), **overrides)


@require_GET

def sources(request: HttpRequest):
    from .knowledge_summary import _domain_scoped_sources
    from .page_widgets import build_sources_widget_cards
    from .sources_browser import (
        PAGE_SIZE, domain_folders, filter_rows, folder_counts, kind_counts, source_inventory, status_counts,
    )
    from ki_knowledge.integrations.mixed_ingest import tesseract_binary

    active_domain = _active_semantic_domain(request)
    table_query = _sources_query(request.GET)
    filters = _sources_filters(request.GET)
    store_obj = store()
    domain_sources = _domain_scoped_sources(active_domain)
    folders = domain_folders(active_domain)
    inventory = source_inventory(active_domain, domain_sources, store_obj.source_stats(), folders)
    all_rows = inventory["rows"]
    selected = filter_rows(
        all_rows, kind=filters["kind"], status=filters["status"], folder=filters["folder"],
        path=filters["path"], query=filters["q"], sort=filters["sort"],
    )
    page_data = paginate(selected, table_query, PAGE_SIZE, reverse("sources"))
    page_rows = list(page_data.items)
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        from .source_access import decorate_rows

        decorate_rows(active_domain, page_rows)
    for row in page_rows:
        row["detail_url"] = reverse("source-detail", args=[row["source_id"]]) if row["imported"] else ""
        if row.get("workflow") == "jira":
            row["workflow_url"] = reverse("data-sources")
        row["item_value"] = f"{row.get('folder', '')}:{row.get('relative', '')}"
        row["folder_href"] = table_query.url(reverse("sources"), folder=row.get("folder", ""), path="", page=1) if row.get("folder") else ""
        parts = [part for part in str(row.get("relative", "")).split("/")[:-1] if part]
        prefix = ""
        links = []
        for part in parts:
            prefix = f"{prefix}/{part}".strip("/")
            links.append({"label": part, "href": table_query.url(reverse("sources"), folder=row.get("folder", ""), path=prefix, page=1)})
        row["path_links"] = links
    kind_map = {chip["key"]: chip["count"] for chip in kind_counts(all_rows) if chip["key"]}
    spec = _sources_table_spec()
    facets = [
        {"label": "Typ", "options": facet_options(spec, table_query, "kind", kind_map, reverse("sources"))},
        {"label": "Status", "options": facet_options(spec, table_query, "status", status_counts(all_rows), reverse("sources"))},
        {"label": "Herkunft", "options": facet_options(spec, table_query, "folder", folder_counts(all_rows), reverse("sources"))},
    ]
    toolbar_context = {
        "base_url": reverse("sources"),
        "presets": preset_links(spec, table_query, _SOURCES_PRESETS, reverse("sources")),
        "facets": facets,
        "text_filters": [
            {"key": "path", "label": "Pfad", "value": filters["path"], "max_length": 200, "placeholder": "Unterordner/Pfadpräfix"},
            {"key": "q", "label": "Suche", "value": filters["q"], "max_length": 200, "placeholder": "Titel oder Pfad suchen …"},
        ],
        "hidden_items": [(k, v) for k, v in table_query.hidden_items() if k in {"kind", "status", "folder"}],
        "sort_options": sort_links(spec, table_query, reverse("sources")),
        "choice_params": [{
            "key": "display", "label": "Darstellung",
            "options": [
                {"value": value, "label": label, "active": filters["display"] == value}
                for value, label in (("table", "Tabelle"), ("cards", "Karten"))
            ],
        }],
        "reset_url": reverse("sources"),
    }
    pending = inventory["pending"]
    ctx = {
        "active_domain": active_domain,
        "sources": domain_sources,
        "toolbar_html": Markup(render_to_string("widgetkit_django/table_toolbar.html", toolbar_context)),
        "kind": filters["kind"],
        "status": filters["status"],
        "folder": filters["folder"],
        "path": filters["path"],
        "query": filters["q"],
        "sort": filters["sort"],
        "display": filters["display"],
        "sort_options": _SOURCES_SORT_OPTIONS,
        "base_url": reverse("sources"),
        "header_links": {key: table_query.url(reverse("sources"), sort=key, page=1) for key, _label in _SOURCES_SORT_OPTIONS},
        "display_table_href": table_query.url(reverse("sources"), display="table", page=1),
        "display_cards_href": table_query.url(reverse("sources"), display="cards", page=1),
        "rows": page_rows,
        "total": page_data.total,
        "total_all": len(all_rows),
        "first_index": page_data.first_index,
        "last_index": page_data.last_index,
        "prev_href": page_data.prev_href,
        "next_href": page_data.next_href,
        "pending": pending,
        "unimported_new": pending["new"],
        "current_folder_new": next((group["new"] for group in pending["folders"] if group["key"] == filters["folder"]), 0),
        "max_files": 200,
        "ocr_missing": tesseract_binary() is None and any(
            item["kind"] == "image" for group in pending["folders"] for item in group["files"]
        ),
        "action_url": reverse("sources-action"),
        "generate_url": reverse("generate-action"),
        "filter_params": filters,
    }
    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="datasources",
        fallback=default_widget_ids_for_area("datasources", "sources"),
        subpage_key="sources",
    )
    widget_cards = build_sources_widget_cards(
        request=request,
        ctx=ctx,
        widget_ids=widget_ids,
        widget_widths=_load_dashboard_widget_widths(request, area_key="datasources", subpage_key="sources"),
    )
    return render(
        request,
        "kicli_django/sources.html",
        {"widget_cards": widget_cards, "active_domain": active_domain, "source_count": len(all_rows)},
    )


@require_http_methods(["POST"])

def sources_action(request: HttpRequest):
    """Per-source (reimport/delete) and per-file (import) actions of the sources browser."""
    from .knowledge_summary import _domain_scoped_sources
    from .sources_browser import FOLDER_KEYS, delete_source, import_all_unimported, import_folder_file, reimport_source, resolve_folder_file

    active_domain = _active_semantic_domain(request)
    filters = _sources_filters(request.POST)
    action = request.POST.get("action", "").strip()
    image_processing = "asset" if request.POST.get("image_processing") == "asset" else "ocr"
    redirect = HttpResponseRedirect(_sources_url(filters))
    store_obj = store()

    if action in {"reimport", "delete"}:
        source_id = request.POST.get("source_id", "").strip()
        source = next((item for item in _domain_scoped_sources(active_domain) if item.source_id == source_id), None)
        if source is None:
            return HttpResponseBadRequest("source not in active domain")
        result = (
            reimport_source(active_domain, source, image_processing=image_processing)
            if action == "reimport"
            else delete_source(active_domain, store_obj, source)
        )
        (messages.success if result["ok"] else messages.error)(request, result["message"])
        return redirect
    if action == "import_file":
        folder = request.POST.get("folder", "").strip()
        if folder not in FOLDER_KEYS:
            return HttpResponseBadRequest("unknown folder")
        result = import_folder_file(
            active_domain,
            folder,
            request.POST.get("file", "").strip(),
            image_processing=image_processing,
        )
        (messages.success if result["ok"] else messages.error)(request, result["message"])
        return redirect
    if action == "import_selected":
        items = request.POST.getlist("item")[:100]
        if not items:
            messages.info(request, "Keine Dateien ausgewählt.")
            return redirect
        selected = []
        for item in items:
            folder, separator, relative = item.partition(":")
            folder = folder.strip()
            relative = relative.strip()
            if not separator or folder not in FOLDER_KEYS or resolve_folder_file(active_domain, folder, relative) is None:
                return HttpResponseBadRequest("invalid selected file")
            selected.append((folder, relative))
        results = [
            import_folder_file(active_domain, folder, relative, image_processing=image_processing)
            for folder, relative in selected
        ]
        ok = sum(1 for item in results if item["ok"])
        messages.success(request, f"{ok} von {len(results)} ausgewählten Datei(en) importiert bzw. eingereiht.")
        for item in [item for item in results if not item["ok"]][:10]:
            messages.warning(request, item["message"])
        return redirect
    if action == "import_all":
        folder = request.POST.get("folder", "").strip()
        if folder and folder not in FOLDER_KEYS:
            return HttpResponseBadRequest("unknown folder")
        results = import_all_unimported(
            active_domain,
            _domain_scoped_sources(active_domain),
            folder=folder,
            image_processing=image_processing,
        )
        ok = sum(1 for item in results if item["ok"])
        if results:
            messages.success(request, f"{ok} von {len(results)} Datei(en) importiert bzw. eingereiht.")
        else:
            messages.info(request, "Nichts zu importieren.")
        for item in [item for item in results if not item["ok"]][:10]:
            messages.warning(request, item["message"])
        return redirect
    return HttpResponseBadRequest("unknown action")
