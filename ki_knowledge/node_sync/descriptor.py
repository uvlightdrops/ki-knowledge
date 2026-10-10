from __future__ import annotations

import importlib.util
import uuid
from typing import Any

from .capabilities import CAPABILITIES, PROTOCOL_VERSIONS, capabilities_for_role
from .settings import NodeSettings

# Deployment identity: a new value per process start (node_id stays stable).
INSTANCE_ID = uuid.uuid4().hex


def node_core_available() -> bool:
    return importlib.util.find_spec("ki_node_core") is not None


def describe(settings: NodeSettings, *, instance_id: str = INSTANCE_ID) -> dict[str, Any]:
    """JSON view of the node for ``GET /knowledge/sync/node/`` (field names as in NodeDescriptor)."""
    return {
        "node_id": settings.node_id,
        "instance_id": instance_id,
        "federation_id": settings.federation_id,
        "role": settings.role,
        "display_name": settings.display_name or None,
        "endpoint": settings.endpoint or None,
        "coordinator_endpoint": settings.coordinator_endpoint or None,
        "distributed_enabled": settings.enabled,
        "protocol_versions": [f"{major}.{minor}" for major, minor in PROTOCOL_VERSIONS],
        "capabilities": [
            {"name": name, "version": f"{major}.{minor}", "endpoint": CAPABILITIES[name][2]}
            for name, (major, minor) in capabilities_for_role(settings.role)
        ],
        "node_core": node_core_available(),
    }


def to_descriptor(settings: NodeSettings, *, instance_id: str = INSTANCE_ID):
    """``ki_node_core.NodeDescriptor`` for this node (requires the ``node`` extra)."""
    try:
        from ki_node_core import Capability, NodeDescriptor, NodeRole, ProtocolVersion
    except ImportError as exc:
        raise RuntimeError(
            "ki-node-core is not installed (pip install -e ../ia3simworld/packages/ki-node-core)"
        ) from exc
    return NodeDescriptor(
        node_id=settings.node_id,
        instance_id=instance_id,
        federation_id=settings.federation_id,
        role=NodeRole(settings.role),
        protocol_versions=tuple(ProtocolVersion(major, minor) for major, minor in PROTOCOL_VERSIONS),
        capabilities=tuple(
            Capability(name, ProtocolVersion(*version)) for name, version in capabilities_for_role(settings.role)
        ),
        endpoint=settings.endpoint or None,
        coordinator_endpoint=settings.coordinator_endpoint or None,
        display_name=settings.display_name or None,
    )
