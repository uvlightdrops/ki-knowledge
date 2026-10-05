from __future__ import annotations

from widgetkit_django.layout_targets import nav_areas_config
from .services import default_semantic_domain, normalize_semantic_domain


def active_domain(request):
    raw = request.session.get("semantic_active_domain", "")
    if raw:
        resolved = normalize_semantic_domain(str(raw))
    else:
        resolved = default_semantic_domain()
    return {
        "active_domain": resolved,
        "global_active_domain": resolved,
    }


def nav_areas(request):
    """Determine the active top-level nav area (longest matching URL prefix
    wins) and expose all areas' submenus, so base.html can render a dynamic
    submenu row for whichever area is currently active."""
    path = request.path
    best_key = "dashboard"
    best_len = 0
    all_areas = nav_areas_config()
    for area in all_areas:
        for prefix in area["prefixes"]:
            if path.startswith(prefix) and len(prefix) > best_len:
                best_key = area["key"]
                best_len = len(prefix)
    return {
        "nav_active_area": best_key,
        "nav_areas": all_areas,
    }
