from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .distributed_sync import (
    apply_remote_domain_payload,
    apply_remote_node_heartbeat,
    ensure_local_node_config,
    local_sync_payload,
)


def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid json body: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json body must be an object")
    return payload


@require_GET
def sync_status_view(request: HttpRequest):
    node = ensure_local_node_config()
    payload = local_sync_payload()
    return JsonResponse(
        {
            "status": "ok",
            "node_id": node.node_id,
            "role": node.role,
            "distributed_enabled": payload["node"]["distributed_enabled"],
            "master_url": payload["node"]["master_url"],
            "domain_count": len(payload["domains"]),
        }
    )


@require_POST
def sync_heartbeat_view(request: HttpRequest):
    try:
        payload = _json_body(request)
        node = apply_remote_node_heartbeat(payload)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return JsonResponse(
        {
            "status": "ok",
            "node_id": node.node_id,
            "role": node.role,
        }
    )


@require_GET
def sync_export_view(request: HttpRequest):
    domains = [item.strip() for item in request.GET.getlist("domain") if item.strip()]
    include_projects = request.GET.get("include_projects", "1").strip() != "0"
    include_documents = request.GET.get("include_documents", "1").strip() != "0"
    payload = local_sync_payload(domains or None)
    if not include_projects:
        for domain in payload["domains"]:
            domain["projects"] = []
    elif not include_documents:
        for domain in payload["domains"]:
            for project in domain["projects"]:
                project["documents"] = []
    return JsonResponse(payload)


@require_POST
def sync_push_view(request: HttpRequest):
    try:
        payload = _json_body(request)
        result = apply_remote_domain_payload(payload)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return JsonResponse({"status": "ok", **result})
