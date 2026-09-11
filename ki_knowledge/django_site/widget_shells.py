from __future__ import annotations

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
    preset = next((item for item in _registry_shell_presets() if item["widget_id"] == preset_id), None)
    saved = _load_shell_builder_state(request).get(preset_id)
    payload = saved or preset or {"widget_id": preset_id}
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
    return render(
        request,
        "kicli_django/widget_shell_builder.html",
        {
            "active_domain": _active_semantic_domain(request),
            "presets": presets,
            "grouped_presets": grouped_presets,
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
    saved = shell_state.get(preset_id)
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
        return render(request, "kicli_django/widget_shell_builder.html", {})
    raw_payload = request.POST.get("payload", "").strip()
    widget_id = request.POST.get("widget_id", "").strip()
    if not widget_id:
        return render(request, "kicli_django/widget_shell_builder.html", {})
    state = _load_shell_builder_state(request)
    if raw_payload:
        import json

        payload = json.loads(raw_payload)
        state[widget_id] = payload if isinstance(payload, dict) else {"widget_id": widget_id}
    else:
        state[widget_id] = {
            "widget_id": widget_id,
            "label": request.POST.get("label", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "area": request.POST.get("area", "").strip(),
            "category": request.POST.get("category", "").strip(),
            "width": request.POST.get("width", "6").strip(),
            "height": request.POST.get("height", "1").strip(),
            "stats": [],
            "links": [],
            "rows": [],
        }
    _save_shell_builder_state(request, state)
    return HttpResponseRedirect(f"/settings/layout/shells/{widget_id}/")
