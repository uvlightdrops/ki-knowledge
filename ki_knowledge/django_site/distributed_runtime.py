from __future__ import annotations

from django.core.cache import cache

from .distributed_api import get_runtime_node_settings, safe_send_master_heartbeat

_HEARTBEAT_CACHE_KEY = "distributed-heartbeat:last-success"


def maybe_send_automatic_heartbeat() -> dict[str, str]:
    runtime = get_runtime_node_settings()
    if runtime.role != "host" or not runtime.distributed_enabled or not runtime.sync_on_connect or not runtime.master_url:
        return {"status": "skipped"}

    cache_key = f"{_HEARTBEAT_CACHE_KEY}:{runtime.node_id}:{runtime.master_url}"
    if cache.get(cache_key):
        return {"status": "throttled"}

    result = safe_send_master_heartbeat()
    if result.get("status") == "unreachable":
        cache.set(cache_key, "0", timeout=15)
        return {"status": "unreachable", "reason": str(result.get("reason", ""))}
    cache.set(cache_key, "1", timeout=60)
    return {"status": "sent"}
