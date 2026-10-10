"""Capabilities of a ki-knowledge node, mapped onto the existing HTTP endpoints.

Versions are (major, minor). Protocol 0.1 = today's ``/knowledge/sync/*`` JSON
endpoints; a shared, versioned wire schema with ia3simworld will become 1.0.
"""

from __future__ import annotations

PROTOCOL_VERSIONS: tuple[tuple[int, int], ...] = ((0, 1),)

Version = tuple[int, int]

# name -> (version, roles offering it, endpoint)
CAPABILITIES: dict[str, tuple[Version, tuple[str, ...], str]] = {
    "knowledge.node.describe": ((1, 0), ("master", "host", "standalone"), "GET /knowledge/sync/node/"),
    "knowledge.node.heartbeat": ((1, 0), ("master",), "POST /knowledge/sync/heartbeat/"),
    "knowledge.snapshot.export": ((1, 0), ("master", "host", "standalone"), "GET /knowledge/sync/export/"),
    "knowledge.snapshot.import": ((1, 0), ("master",), "POST /knowledge/sync/push/"),
    # remote command: master asks a host to pull from the master
    "knowledge.domain.pull": ((1, 0), ("host",), "POST /knowledge/sync/pull/"),
}


def capabilities_for_role(role: str) -> list[tuple[str, Version]]:
    return [(name, version) for name, (version, roles, _endpoint) in CAPABILITIES.items() if role in roles]
