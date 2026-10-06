from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

from ki_knowledge.app_config import AppConfig as Config
from .infosite_models import Domain, NodeConfig, current_node_id

from .distributed_sync import (
    LocalNodeSnapshot,
    apply_remote_domain_payload,
    apply_remote_node_heartbeat,
    ensure_local_node_config,
    export_sync_summary,
    known_host_registry,
    knowledge_sync_payload,
    local_node_snapshot,
    local_sync_payload,
    pull_from_master,
    remote_domain_catalog,
    resolved_master_url,
    resolved_sync_secret,
    trigger_host_pull,
)


def _is_connection_error(exc: Exception) -> bool:
    return isinstance(exc, requests.exceptions.RequestException | ConnectionError)


def get_local_node_snapshot() -> LocalNodeSnapshot:
    return local_node_snapshot()


def ensure_local_node():
    return ensure_local_node_config()


def get_master_url() -> str:
    return resolved_master_url()


def get_sync_secret() -> str:
    return resolved_sync_secret()


def export_local_sync_payload(domains: list[str] | None = None) -> dict[str, Any]:
    return local_sync_payload(domains)


def export_knowledge_sync_payload(domains: list[str] | None = None) -> dict[str, Any]:
    return knowledge_sync_payload(domains)


def import_remote_heartbeat(payload: dict[str, Any]):
    return apply_remote_node_heartbeat(payload)


def import_remote_domain_sync(payload: dict[str, Any]) -> dict[str, Any]:
    return apply_remote_domain_payload(payload)


def pull_domains_from_master(*, domains: list[str] | None = None) -> dict[str, Any]:
    return pull_from_master(domains=domains)


def export_sync_snapshot(*, domains: list[str] | None = None) -> dict[str, Any]:
    return export_sync_summary(domains=domains)


def fetch_master_domain_catalog(*, master_url: str | None = None) -> dict[str, Any]:
    return remote_domain_catalog(master_url=master_url)


def list_known_hosts():
    return known_host_registry()


def send_host_pull_command(*, host_node_id: str, domains: list[str] | None = None) -> dict[str, Any]:
    return trigger_host_pull(host_node_id=host_node_id, domains=domains)


def import_remote_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return apply_remote_domain_payload(payload)


def build_domain_catalog_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    domains_payload = payload.get("domains")
    if not isinstance(domains_payload, list):
        raise ValueError("sync payload missing domains list")
    local_domains = {node.slug for node in Domain.objects.all().only("slug")}
    catalog = []
    for item in domains_payload:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug", "")).strip()
        if not slug:
            continue
        catalog.append(
            {
                "slug": slug,
                "display_name": str(item.get("display_name", "")).strip() or slug,
                "description": str(item.get("description", "")).strip(),
                "home_node": str(item.get("home_node", "")).strip(),
                "sync_mode": str(item.get("sync_mode", "")).strip() or "push",
                "visibility": str(item.get("visibility", "")).strip() or "private",
                "project_count": int(item.get("project_count", 0) or 0),
                "available_locally": slug in local_domains,
            }
        )
    return {"domain_count": len(catalog), "domains": catalog}


@dataclass
class RuntimeNodeSettings:
    node_id: str
    role: str
    base_url: str
    sync_on_connect: bool
    distributed_enabled: bool
    master_url: str
    sync_shared_secret: str


def get_runtime_node_settings() -> RuntimeNodeSettings:
    config = getattr(settings, "KI_CONFIG", None) or Config.from_env()
    node_id = current_node_id()
    node = NodeConfig.objects.filter(node_id=node_id).first()
    role = str((node.role if node and node.role else getattr(config, "distributed_node_role", "standalone")) or "standalone").strip() or "standalone"
    base_url = str(node.base_url if node and node.base_url else "").strip()
    sync_on_connect = node.sync_on_connect if node is not None else bool(getattr(config, "distributed_sync_on_connect", True))
    distributed_enabled = node.is_enabled if node is not None else bool(getattr(config, "distributed_enabled", False))
    master_url = base_url if role == "host" and base_url else str(getattr(config, "distributed_master_url", "") or "").strip()
    sync_shared_secret = str((node.sync_shared_secret if node and node.sync_shared_secret else getattr(config, "distributed_sync_shared_secret", "")) or "").strip()
    return RuntimeNodeSettings(
        node_id=node_id,
        role=role,
        base_url=base_url,
        sync_on_connect=bool(sync_on_connect),
        distributed_enabled=bool(distributed_enabled),
        master_url=master_url,
        sync_shared_secret=sync_shared_secret,
    )


def persist_runtime_node_settings_to_process() -> RuntimeNodeSettings:
    runtime = get_runtime_node_settings()
    config = getattr(settings, "KI_CONFIG", None)
    if config is not None:
        config.distributed_node_role = runtime.role
        config.distributed_master_url = runtime.master_url if runtime.role == "host" else ""
        config.distributed_sync_on_connect = runtime.sync_on_connect
        config.distributed_enabled = runtime.distributed_enabled
        config.distributed_sync_shared_secret = runtime.sync_shared_secret
    return runtime


def persist_local_node_settings(
    *,
    display_name: str | None = None,
    role: str | None = None,
    base_url: str | None = None,
    sync_on_connect: bool | None = None,
    is_enabled: bool | None = None,
    sync_shared_secret: str | None = None,
):
    defaults = get_runtime_node_settings()
    node, _ = NodeConfig.objects.get_or_create(
        node_id=defaults.node_id,
        defaults={
            "role": defaults.role,
            "base_url": defaults.base_url,
            "sync_on_connect": defaults.sync_on_connect,
            "is_enabled": defaults.distributed_enabled,
            "sync_shared_secret": defaults.sync_shared_secret,
        },
    )
    if display_name is not None:
        node.display_name = display_name
    if role is not None:
        node.role = role
    if base_url is not None:
        node.base_url = base_url
    if sync_on_connect is not None:
        node.sync_on_connect = sync_on_connect
    if is_enabled is not None:
        node.is_enabled = is_enabled
    if sync_shared_secret:
        node.sync_shared_secret = sync_shared_secret
    node.save()
    persist_runtime_node_settings_to_process()
    return node


def send_master_heartbeat(*, include_status: bool = True) -> dict[str, Any]:
    runtime = get_runtime_node_settings()
    if runtime.role != "host" or not runtime.distributed_enabled or not runtime.master_url:
        return {"status": "skipped", "reason": "heartbeat not configured"}

    heartbeat_url = runtime.master_url.rstrip("/") + "/knowledge/sync/heartbeat/"
    payload = {
        "node_id": runtime.node_id,
        "display_name": NodeConfig.objects.filter(node_id=runtime.node_id).values_list("display_name", flat=True).first() or "",
        "role": runtime.role,
        "base_url": runtime.base_url,
        "sync_on_connect": runtime.sync_on_connect,
        "is_enabled": runtime.distributed_enabled,
    }
    headers = {"Content-Type": "application/json"}
    if runtime.sync_shared_secret:
        headers["X-KI-Sync-Secret"] = runtime.sync_shared_secret
    response = requests.post(
        heartbeat_url,
        json=payload,
        headers=headers,
        timeout=max(getattr(getattr(settings, "KI_CONFIG", None) or Config.from_env(), "request_timeout", 30), 5),
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("heartbeat response must be an object")
    return {"heartbeat_url": heartbeat_url, **result}


def safe_send_master_heartbeat(*, include_status: bool = True) -> dict[str, Any]:
    try:
        return send_master_heartbeat(include_status=include_status)
    except Exception as exc:
        if _is_connection_error(exc):
            return {"status": "unreachable", "reason": str(exc)}
        raise


def safe_fetch_master_domain_catalog(*, master_url: str | None = None) -> tuple[dict[str, Any] | None, str]:
    try:
        return fetch_master_domain_catalog(master_url=master_url), ""
    except Exception as exc:
        if _is_connection_error(exc):
            return None, str(exc)
        raise
