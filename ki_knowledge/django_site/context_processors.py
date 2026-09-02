from __future__ import annotations

from .services import default_semantic_domain, normalize_semantic_domain


def active_domain(request):
    raw = request.session.get("semantic_active_domain", "")
    if raw:
        resolved = normalize_semantic_domain(str(raw))
    else:
        resolved = default_semantic_domain()
    return {"global_active_domain": resolved}
