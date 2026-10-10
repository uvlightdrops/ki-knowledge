from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.node_sync import INSTANCE_ID, NodeSettings, describe
from ki_knowledge.node_sync.client import PATH_HEARTBEAT
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
    sync_client,
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


def export_local_sync_payload(domains: list[str] | None = None, **include: bool) -> dict[str, Any]:
    """include_projects / include_documents / include_knowledge, all default True."""
    return local_sync_payload(domains, **include)


def export_knowledge_sync_payload(domains: list[str] | None = None) -> dict[str, Any]:
    return knowledge_sync_payload(domains)


def import_remote_heartbeat(payload: dict[str, Any]):
    return apply_remote_node_heartbeat(payload)


def import_remote_domain_sync(payload: dict[str, Any]) -> dict[str, Any]:
    return apply_remote_domain_payload(payload)


def pull_domains_from_master(
    *, domains: list[str] | None = None, operation_id: str = ""
) -> dict[str, Any]:
    return pull_from_master(domains=domains, operation_id=operation_id)


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


def get_node_settings() -> NodeSettings:
    """Framework-free view of the local node for the shared node/sync layer (ki_knowledge.node_sync)."""
    runtime = get_runtime_node_settings()
    config = getattr(settings, "KI_CONFIG", None) or Config.from_env()
    display_name = NodeConfig.objects.filter(node_id=runtime.node_id).values_list("display_name", flat=True).first()
    return NodeSettings(
        node_id=runtime.node_id,
        role=runtime.role,
        enabled=runtime.distributed_enabled,
        sync_on_connect=runtime.sync_on_connect,
        federation_id=str(getattr(config, "distributed_federation_id", "") or "default").strip() or "default",
        master_url=runtime.master_url if runtime.role == "host" else "",
        public_url=str(getattr(config, "distributed_public_url", "") or "").strip(),
        legacy_base_url=runtime.base_url,
        display_name=display_name or "",
        shared_secret=runtime.sync_shared_secret,
    )


def describe_local_node() -> dict[str, Any]:
    return describe(get_node_settings())


def send_master_heartbeat(*, include_status: bool = True) -> dict[str, Any]:
    node = get_node_settings()
    if not node.heartbeat_ready:
        return {"status": "skipped", "reason": "heartbeat not configured"}

    client = sync_client(node.master_url)
    result = client.heartbeat(node.heartbeat_payload(instance_id=INSTANCE_ID))
    return {"heartbeat_url": client.url(PATH_HEARTBEAT), **result}


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
