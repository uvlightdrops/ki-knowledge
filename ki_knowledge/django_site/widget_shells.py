from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render

from .dashboard_registry import builtin_areas, widget_by_id, widget_ids
from .widget_shell_models import WidgetShellDefinition
from .views_common import _active_semantic_domain, _load_shell_builder_state, _save_shell_builder_state


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
        "stats",
        "links",
        "rows",
    ).first()
    if saved:
        payload = saved
    else:
        preset = next((item for item in _registry_shell_presets() if item["widget_id"] == preset_id), None)
        payload = preset or {"widget_id": preset_id}
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
        "stats",
        "links",
        "rows",
    ).first()
    active_preset = saved or base_preset or {"widget_id": preset_id}
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
        "stats": [],
        "links": [],
        "rows": [],
    }
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
            "stats": shell.stats,
            "links": shell.links,
            "rows": shell.rows,
            "saved": True,
        }
    )
