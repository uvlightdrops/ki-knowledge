from __future__ import annotations

import json
from urllib.parse import quote

from django.db import connection
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render

from .dashboard_registry import builtin_areas, widget_by_id, widget_ids
from .page_widgets import preview_payload_for_widget
from .widget_shell_models import WidgetShellDefinition
from .views_common import _active_semantic_domain, _load_shell_builder_state, _save_shell_builder_state


SOURCE_TABLE_OPTIONS = [
    ("django_site_domain", "django_site_domain"),
    ("django_site_dashboarddefinition", "django_site_dashboarddefinition"),
    ("django_site_dashboardwidgetplacement", "django_site_dashboardwidgetplacement"),
    ("django_site_infositeproject", "django_site_infositeproject"),
    ("django_site_sourcedocument", "django_site_sourcedocument"),
    ("django_site_generateddocument", "django_site_generateddocument"),
    ("knowledge_sources", "knowledge_sources"),
    ("knowledge_blocks", "knowledge_blocks"),
    ("pdf_import_jobs", "pdf_import_jobs"),
]


def available_source_tables() -> list[str]:
    return [name for _, name in SOURCE_TABLE_OPTIONS]


def _table_preview_payload(source_table: str, *, limit: int = 5) -> dict[str, object]:
    if not source_table:
        return {"stats": [], "links": [], "rows": []}
    quoted = connection.ops.quote_name(source_table)
    with connection.cursor() as cursor:
        table_names = set(connection.introspection.table_names())
        if source_table not in table_names:
            return {
                "stats": [{"label": "Table", "value": source_table}, {"label": "Rows", "value": "0"}],
                "links": [{"label": "Open builder", "url": "/settings/layout/shell-builder/"}],
                "rows": [{"label": "Table missing", "value": "not found"}],
            }
        cursor.execute(f"SELECT * FROM {quoted} LIMIT %s", [limit])
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description or ()]

    if not rows:
        return {
            "stats": [{"label": "Table", "value": source_table}, {"label": "Rows", "value": "0"}],
            "links": [{"label": "Open builder", "url": "/settings/layout/shell-builder/"}],
            "rows": [{"label": "No rows", "value": "empty"}],
        }

    prepared_rows: list[dict[str, str]] = []
    for row in rows:
        mapping = {name: value for name, value in zip(columns, row)}
        label_name = next((key for key in ("title", "label", "name", "display_name", "slug", "domain", "id", "username") if key in mapping), None)
        value_name = next((key for key in ("value", "status", "count", "description", "kind", "type", "category", "source_type", "updated_at") if key in mapping), None)
        url_name = next((key for key in ("url", "href", "path", "detail_url", "link") if key in mapping), None)

        label = mapping.get(label_name) if label_name is not None else (mapping.get("id") if "id" in mapping else "Row")
        value = mapping.get(value_name) if value_name is not None else ""
        item = {"label": str(label or "Row"), "value": str(value or "")}
        url_value = mapping.get(url_name) if url_name is not None else None
        if url_value:
            item["url"] = str(url_value)
        prepared_rows.append(item)

    return {
        "stats": [{"label": "Table", "value": source_table}, {"label": "Rows", "value": str(len(rows))}],
        "links": [{"label": "Open table", "url": f"/settings/layout/shell-builder/?source={quote(source_table)}"}],
        "rows": prepared_rows,
    }


def _registry_shell_presets() -> list[dict[str, object]]:
    presets = []
    for widget_id in widget_ids():
        spec = widget_by_id(widget_id)
        presets.append(
            {
                "widget_id": widget_id,
                "label": spec.label if spec is not None else widget_id,
                "description": spec.description if spec is not None else "",
                "area": spec.area if spec is not None else (widget_id.split(".")[0] if "." in widget_id else "custom"),
                "group": spec.area if spec is not None else (widget_id.split(".")[0] if "." in widget_id else "custom"),
                "category": spec.category if spec is not None else (widget_id.split(".")[1] if "." in widget_id else "custom"),
                "width": str(spec.default_w if spec is not None else 6),
                "height": str(spec.default_h if spec is not None else 1),
                "stats": [{"label": "Status", "value": "draft"}],
                "links": [{"label": "Docs", "url": "/settings/layout/widgets/"}],
                "rows": [{"label": "Type", "value": "shell"}],
            }
        )
    return presets


def widget_shell_builder_view(request: HttpRequest):
    return widget_shell_builder_list_view(request)


def widget_shell_builder_preset_json_view(request: HttpRequest, preset_id: str):
    saved = WidgetShellDefinition.objects.filter(widget_id=preset_id).values(
        "widget_id",
        "label",
        "description",
        "area",
        "category",
        "width",
        "height",
        "source_type",
        "source_table",
        "stats",
        "links",
        "rows",
    ).first()
    preset = next((item for item in _registry_shell_presets() if item["widget_id"] == preset_id), None)
    if saved and saved.get("source_type") == "table" and saved.get("source_table"):
        table_payload = _table_preview_payload(str(saved["source_table"]))
        saved = dict(saved)
        saved["stats"] = table_payload.get("stats", [])
        saved["links"] = table_payload.get("links", [])
        saved["rows"] = table_payload.get("rows", [])
        payload = saved
    elif saved and (saved.get("stats") or saved.get("links") or saved.get("rows") or saved.get("description") or saved.get("label")) and not (
        saved.get("stats") == [] and saved.get("links") == [] and saved.get("rows") == []
    ):
        payload = saved
    else:
        if preset is not None:
            live_payload = preview_payload_for_widget(preset_id)
            payload = {
                "widget_id": live_payload.get("widget_id", preset["widget_id"]),
                "label": live_payload.get("label", preset.get("label", "")),
                "description": live_payload.get("description", preset.get("description", "")),
                "area": preset.get("area", "custom"),
                "category": preset.get("category", "overview"),
                "width": str(preset.get("width", "6")),
                "height": str(preset.get("height", "1")),
                "source_type": "table",
                "source_table": "django_site_domain",
                "stats": live_payload.get("stats", preset.get("stats", [])),
                "links": live_payload.get("links", preset.get("links", [])),
                "rows": live_payload.get("rows", preset.get("rows", [])),
            }
        else:
            payload = saved or {"widget_id": preset_id}
    return JsonResponse(payload)


def widget_shell_builder_list_view(request: HttpRequest):
    presets = _registry_shell_presets()
    grouped_presets: dict[str, list[dict[str, object]]] = {}
    for preset in presets:
        grouped_presets.setdefault(str(preset["group"]), []).append(preset)
    for preset in presets:
        if WidgetShellDefinition.objects.filter(widget_id=preset["widget_id"]).exists():
            preset["shell_url"] = f"/settings/layout/shells/{preset['widget_id']}/"
        else:
            preset["shell_url"] = f"/settings/layout/shells/new/{preset['widget_id']}/"
    active_widget_id = request.GET.get("widget_id", "").strip()
    active_preset = None
    if active_widget_id:
        active_preset = WidgetShellDefinition.objects.filter(widget_id=active_widget_id).values(
            "widget_id",
            "label",
            "description",
            "area",
            "category",
            "width",
            "height",
            "source_type",
            "source_table",
            "stats",
            "links",
            "rows",
        ).first()
        if active_preset is None:
            active_preset = next((preset for preset in presets if str(preset["widget_id"]) == active_widget_id), None)
    return render(
        request,
        "kicli_django/widget_shell_builder.html",
        {
            "active_domain": _active_semantic_domain(request),
            "presets": presets,
            "grouped_presets": grouped_presets,
            "active_widget_id": active_widget_id,
            "active_preset_json": active_preset,
            "builtins": builtin_areas(),
            "widths": [3, 4, 6, 8, 12],
            "source_tables": available_source_tables(),
        },
    )


def widget_shell_overview_view(request: HttpRequest):
    shells = list(WidgetShellDefinition.objects.order_by("widget_id"))
    if not shells:
        shells = _registry_shell_presets()
    return render(
        request,
        "kicli_django/widget_shell_overview.html",
        {
            "shells": shells,
        },
    )


def widget_shell_builder_new_view(request: HttpRequest, preset_id: str):
    return widget_shell_builder_edit_view(request, preset_id=preset_id, create_mode=True)


def widget_shell_builder_edit_view(request: HttpRequest, preset_id: str, create_mode: bool = False):
    presets = _registry_shell_presets()
    grouped_presets: dict[str, list[dict[str, object]]] = {}
    for preset in presets:
        grouped_presets.setdefault(str(preset["group"]), []).append(preset)
    shell_state = _load_shell_builder_state(request)
    for preset in presets:
        if WidgetShellDefinition.objects.filter(widget_id=preset["widget_id"]).exists():
            preset["shell_url"] = f"/settings/layout/shells/{preset['widget_id']}/"
        else:
            preset["shell_url"] = f"/settings/layout/shells/new/{preset['widget_id']}/"
    base_preset = next((preset for preset in presets if str(preset["widget_id"]) == preset_id), None)
    saved = WidgetShellDefinition.objects.filter(widget_id=preset_id).values(
        "widget_id",
        "label",
        "description",
        "area",
        "category",
        "width",
        "height",
        "source_type",
        "source_table",
        "stats",
        "links",
        "rows",
    ).first()
    active_preset = saved or base_preset or {"widget_id": preset_id}
    if saved and saved.get("source_type") == "table" and saved.get("source_table"):
        table_payload = _table_preview_payload(str(saved["source_table"]))
        active_preset = dict(saved)
        active_preset["stats"] = table_payload.get("stats", [])
        active_preset["links"] = table_payload.get("links", [])
        active_preset["rows"] = table_payload.get("rows", [])
    elif saved and saved.get("stats") == [] and saved.get("links") == [] and saved.get("rows") == []:
        active_preset = base_preset or preview_payload_for_widget(preset_id) or saved
    if create_mode and base_preset and not saved:
        active_preset = base_preset
    return render(
        request,
        "kicli_django/widget_shell_builder.html",
        {
            "active_domain": _active_semantic_domain(request),
            "presets": presets,
            "grouped_presets": grouped_presets,
            "shell_state": shell_state,
            "active_widget_id": preset_id,
            "active_preset_json": active_preset,
            "builtins": builtin_areas(),
            "widths": [3, 4, 6, 8, 12],
            "source_tables": available_source_tables(),
        },
    )


def widget_shell_builder_list_view_legacy(request: HttpRequest):
    return widget_shell_builder_list_view(request)


def widget_shell_builder_save_view(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    raw_payload = request.POST.get("payload", "").strip()
    if not raw_payload and request.body:
        try:
            decoded_body = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded_body = {}
        if isinstance(decoded_body, dict):
            raw_payload = json.dumps(decoded_body)
    payload: dict[str, object] = {}
    if raw_payload:
        try:
            loaded_payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            loaded_payload = {}
        if isinstance(loaded_payload, dict):
            payload = loaded_payload
    widget_id = str(payload.get("widget_id") or request.POST.get("widget_id", "")).strip()
    if not widget_id:
        return JsonResponse({"error": "widget_id required"}, status=400)
    data = {
        "widget_id": widget_id,
        "label": str(payload.get("label") or request.POST.get("label", "")).strip(),
        "description": str(payload.get("description") or request.POST.get("description", "")).strip(),
        "area": str(payload.get("area") or request.POST.get("area", "")).strip(),
        "category": str(payload.get("category") or request.POST.get("category", "")).strip(),
        "width": str(payload.get("width") or request.POST.get("width", "6")).strip(),
        "height": str(payload.get("height") or request.POST.get("height", "1")).strip(),
        "source_type": str(payload.get("source_type") or request.POST.get("source_type", "table")).strip() or "table",
        "source_table": str(payload.get("source_table") or request.POST.get("source_table", "")).strip(),
        "stats": [],
        "links": [],
        "rows": [],
    }
    if str(data.get("source_type", "")).strip() == "table" and str(data.get("source_table", "")).strip():
        source_payload = _table_preview_payload(str(data["source_table"]))
        data["stats"] = list(source_payload.get("stats", []))
        data["links"] = list(source_payload.get("links", []))
        data["rows"] = list(source_payload.get("rows", []))
    else:
        data["stats"] = list(payload.get("stats", data["stats"]))
        data["links"] = list(payload.get("links", data["links"]))
        data["rows"] = list(payload.get("rows", data["rows"]))
    shell, _ = WidgetShellDefinition.objects.update_or_create(
        widget_id=widget_id,
        defaults={
            "label": str(data.get("label", "")),
            "description": str(data.get("description", "")),
            "area": str(data.get("area", "")),
            "category": str(data.get("category", "")),
            "width": str(data.get("width", "6")),
            "height": str(data.get("height", "1")),
            "source_type": str(data.get("source_type", "table")),
            "source_table": str(data.get("source_table", "")),
            "stats": list(data.get("stats", [])),
            "links": list(data.get("links", [])),
            "rows": list(data.get("rows", [])),
        },
    )
    return JsonResponse(
        {
            "widget_id": shell.widget_id,
            "label": shell.label,
            "description": shell.description,
            "area": shell.area,
            "category": shell.category,
            "width": shell.width,
            "height": shell.height,
            "source_type": shell.source_type,
            "source_table": shell.source_table,
            "stats": shell.stats,
            "links": shell.links,
            "rows": shell.rows,
            "saved": True,
        }
    )
