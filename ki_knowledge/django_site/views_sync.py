from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ki_knowledge.app_config import AppConfig as Config

from .distributed_api import (
    ensure_local_node,
    export_knowledge_sync_payload,
    export_local_sync_payload,
    get_sync_secret,
    import_remote_domain_sync,
    import_remote_heartbeat,
    pull_domains_from_master,
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


def _configured_sync_secret() -> str:
    return get_sync_secret()


def _require_sync_secret(request: HttpRequest):
    expected = _configured_sync_secret()
    if not expected:
        return None
    provided = (
        request.headers.get("X-KI-Sync-Secret", "").strip()
        or request.GET.get("sync_secret", "").strip()
        or request.POST.get("sync_secret", "").strip()
    )
    if provided != expected:
        return HttpResponseForbidden("sync secret missing or invalid")
    return None


@require_GET
def sync_status_view(request: HttpRequest):
    node = ensure_local_node()
    payload = export_local_sync_payload()
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
    denied = _require_sync_secret(request)
    if denied is not None:
        return denied
    try:
        payload = _json_body(request)
        node = import_remote_heartbeat(payload)
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
    denied = _require_sync_secret(request)
    if denied is not None:
        return denied
    domains = [item.strip() for item in request.GET.getlist("domain") if item.strip()]
    include_projects = request.GET.get("include_projects", "1").strip() != "0"
    include_documents = request.GET.get("include_documents", "1").strip() != "0"
    include_knowledge = request.GET.get("include_knowledge", "1").strip() != "0"
    payload = export_local_sync_payload(domains or None)
    if not include_projects:
        for domain in payload["domains"]:
            domain["projects"] = []
    elif not include_documents:
        for domain in payload["domains"]:
            for project in domain["projects"]:
                project["documents"] = []
    if include_knowledge:
        knowledge_payload = export_knowledge_sync_payload(domains or None)
        by_slug = {entry["slug"]: entry for entry in knowledge_payload["domains"]}
        for domain in payload["domains"]:
            knowledge_entry = by_slug.get(domain["slug"], {})
            domain["knowledge_sources"] = knowledge_entry.get("knowledge_sources", [])
            domain["knowledge_records"] = knowledge_entry.get("knowledge_records", [])
            domain["knowledge_artifacts"] = knowledge_entry.get("knowledge_artifacts", [])
            domain["knowledge_relations"] = knowledge_entry.get("knowledge_relations", [])
    else:
        for domain in payload["domains"]:
            domain["knowledge_sources"] = []
            domain["knowledge_records"] = []
            domain["knowledge_artifacts"] = []
            domain["knowledge_relations"] = []
    return JsonResponse(payload)


@require_POST
def sync_push_view(request: HttpRequest):
    denied = _require_sync_secret(request)
    if denied is not None:
        return denied
    try:
        payload = _json_body(request)
        result = import_remote_domain_sync(payload)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return JsonResponse({"status": "ok", **result})


@require_POST
def sync_pull_view(request: HttpRequest):
    denied = _require_sync_secret(request)
    if denied is not None:
        return denied
    domains = [item.strip() for item in request.POST.getlist("domain") if item.strip()]
    try:
        result = pull_domains_from_master(domains=domains or None)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    except Exception as exc:
        return HttpResponseBadRequest(f"master pull failed: {exc}")
    return JsonResponse({"status": "ok", **result})
