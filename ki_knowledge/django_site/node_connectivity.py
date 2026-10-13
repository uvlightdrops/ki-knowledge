"""Read-only, bounded HTTP descriptor checks for the header indicator."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
import hashlib
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit

import requests
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ki_knowledge.node_sync.netlog import log_probe
from .distributed_api import get_runtime_node_settings
from .infosite_models import NodeConfig

CACHE_SECONDS = 30
MAX_PEERS = 4
DISPLAY_LIMIT = 3
PROBE_SECONDS = 1.0
MAX_RESPONSE_BYTES = 16 * 1024
_executor = ThreadPoolExecutor(max_workers=MAX_PEERS, thread_name_prefix="node-descriptor")


@dataclass(frozen=True)
class Peer:
    node_id: str
    label: str
    url: str
    expected_id: str


def _origin(url: str) -> tuple[str, str, int] | None:
    try:
        parts = urlsplit(url)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or any(c.isspace() for c in url)):
            return None
        return parts.scheme, parts.hostname.lower(), parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None


def configured_peers(request) -> tuple[list[Peer], str]:
    runtime = get_runtime_node_settings()
    self_origin = _origin(request.build_absolute_uri("/"))
    peers = []
    seen = set()
    rows = NodeConfig.objects.filter(is_enabled=True).exclude(node_id=runtime.node_id).order_by("node_id")
    for row in rows.only("node_id", "display_name", "base_url"):
        url = row.base_url.strip()
        if url and _origin(url) == self_origin:
            continue
        peers.append(Peer(row.node_id, row.display_name or row.node_id, url, row.node_id))
        seen.add(url.rstrip("/"))
    if (runtime.role == "host" and runtime.distributed_enabled and runtime.master_url
            and runtime.master_url.rstrip("/") not in seen
            and _origin(runtime.master_url) != self_origin):
        peers.insert(0, Peer("configured-master", "Master", runtime.master_url, ""))
    return peers, runtime.node_id


def _result(peer: Peer, status: str, error: str = "", rtt_ms: int | None = None) -> dict:
    return {"node_id": peer.node_id, "label": peer.label, "status": status,
            "error": error, "rtt_ms": rtt_ms, "checked_at": time.time()}


def probe_peer(peer: Peer, local_id: str) -> dict:
    result = _probe_peer(peer, local_id)
    if result["status"] in {"reachable", "error"}:
        log_probe(peer.url, result["status"], result["error"], result["rtt_ms"])
    return result


def _probe_peer(peer: Peer, local_id: str) -> dict:
    if not peer.url:
        return _result(peer, "not_configured", "No descriptor URL configured")
    if _origin(peer.url) is None:
        return _result(peer, "error", "Invalid configured URL")
    parts = urlsplit(peer.url)
    url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") + "/knowledge/sync/node/", "", ""))
    started = time.monotonic()
    try:
        # No proxy environment, netrc authentication, cookies or sync secret.
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, timeout=(0.4, 0.6), allow_redirects=False, stream=True,
                             headers={"Accept": "application/json", "Accept-Encoding": "identity"}) as response:
                if response.status_code != 200:
                    return _result(peer, "error", f"HTTP {response.status_code}")
                body = bytearray()
                for chunk in response.iter_content(chunk_size=1024):
                    if time.monotonic() - started >= PROBE_SECONDS:
                        return _result(peer, "error", "Descriptor timeout (1 s)")
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        return _result(peer, "error", "Descriptor response too large")
                payload = json.loads(body)
        if not isinstance(payload, dict):
            return _result(peer, "error", "Invalid node descriptor")
        node_id = payload.get("node_id")
        versions = payload.get("protocol_versions")
        if (not isinstance(node_id, str) or not node_id.strip() or len(node_id) > 120
                or not isinstance(versions, list) or not versions
                or not all(isinstance(v, str) and re.fullmatch(r"\d+\.\d+", v) for v in versions)):
            return _result(peer, "error", "Invalid node descriptor")
        if node_id == local_id:
            return _result(peer, "error", "Descriptor identifies the local node")
        if peer.expected_id and node_id != peer.expected_id:
            return _result(peer, "error", "Descriptor node identity mismatch")
        elapsed = time.monotonic() - started
        if elapsed >= PROBE_SECONDS:
            return _result(peer, "error", "Descriptor timeout (1 s)")
        return _result(peer, "reachable", rtt_ms=round(elapsed * 1000))
    except requests.exceptions.Timeout:
        return _result(peer, "error", "Descriptor timeout (1 s)")
    except requests.exceptions.RequestException:
        return _result(peer, "error", "Descriptor connection failed")
    except (ValueError, UnicodeDecodeError):
        return _result(peer, "error", "Invalid node descriptor")


@login_required
@require_GET
def node_connectivity_view(request):
    peers, local_id = configured_peers(request)
    key_data = (local_id, request.scheme, request.get_host(), peers)
    key = "node-connectivity:v1:" + hashlib.sha256(repr(key_data).encode()).hexdigest()
    payload = cache.get(key)
    if payload is None:
        if not cache.add(key + ":lock", True, timeout=CACHE_SECONDS + 5):
            payload = {"status": "checking", "peers": [], "overflow": max(0, len(peers) - DISPLAY_LIMIT)}
        else:
            selected = peers[:MAX_PEERS]
            futures = [_executor.submit(probe_peer, peer, local_id) for peer in selected]
            done, _ = wait(futures, timeout=PROBE_SECONDS + 0.1)
            results = [future.result() if future in done else _result(peer, "error", "Descriptor timeout (1 s)")
                       for peer, future in zip(selected, futures)]
            # Do not let slow DNS or a trickling response hold the HTTP view open.
            for future in futures:
                if future not in done:
                    future.cancel()
            payload = {"status": "ok" if peers else "not_configured", "peers": results[:DISPLAY_LIMIT],
                       "overflow": max(0, len(peers) - DISPLAY_LIMIT),
                       "unprobed": max(0, len(peers) - MAX_PEERS)}
            cache.set(key, payload, timeout=CACHE_SECONDS)
            cache.delete(key + ":lock")
    response = JsonResponse({**payload, "cache_seconds": CACHE_SECONDS, "timeout_ms": 1000})
    response["Cache-Control"] = "no-store"
    return response
