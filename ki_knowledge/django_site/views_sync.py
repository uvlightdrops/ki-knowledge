from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ki_knowledge.app_config import AppConfig as Config

from .distributed_api import (
    describe_local_node,
    ensure_local_node,
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
        # csrf_exempt endpoints: without a secret, refuse cross-site browser requests
        origin = request.headers.get("Origin", "")
        cross_origin = bool(origin) and origin.split("://", 1)[-1] != request.get_host()
        if cross_origin or request.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
            return HttpResponseForbidden("cross-site requests require a configured sync secret")
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
    payload = export_local_sync_payload(include_projects=False, include_knowledge=False)
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


@require_GET
def sync_node_view(request: HttpRequest):
    """Node description for the shared node layer (capabilities, protocol versions; no secrets)."""
    return JsonResponse(describe_local_node())


# machine-to-machine: authenticated by X-KI-Sync-Secret, not by session/CSRF cookie
@csrf_exempt
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
    payload = export_local_sync_payload(
        domains or None,
        include_projects=include_projects,
        include_documents=include_projects and include_documents,
        include_knowledge=include_knowledge,
    )
    return JsonResponse(payload)


# machine-to-machine: authenticated by X-KI-Sync-Secret, not by session/CSRF cookie
@csrf_exempt
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


# machine-to-machine: authenticated by X-KI-Sync-Secret, not by session/CSRF cookie
@csrf_exempt
@require_POST
def sync_pull_view(request: HttpRequest):
    denied = _require_sync_secret(request)
    if denied is not None:
        return denied
    domains = [item.strip() for item in request.POST.getlist("domain") if item.strip()]
    operation_id = (request.headers.get("X-KI-Operation-Id", "") or request.POST.get("operation_id", "")).strip()[:64]
    try:
        result = pull_domains_from_master(domains=domains or None, operation_id=operation_id)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    except Exception as exc:
        return HttpResponseBadRequest(f"master pull failed: {exc}")
    return JsonResponse({"status": "ok", **result})
