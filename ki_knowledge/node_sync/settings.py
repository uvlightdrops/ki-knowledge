from __future__ import annotations

import uuid
from dataclasses import dataclass, field

ROLES = ("master", "host", "standalone")


def new_operation_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class NodeSettings:
    """Resolved local node settings, independent of NodeConfig/AppConfig.

    Legacy mapping (kept compatible): on a *host*, ``NodeConfig.base_url`` holds the
    **master** URL. The host's own reachable URL is ``public_url``
    (``apps.ki_knowledge.distributed.public_url``); only that is announced as
    ``base_url`` in heartbeats when set, otherwise the legacy value is sent.
    """

    node_id: str
    role: str = "standalone"
    enabled: bool = False
    sync_on_connect: bool = True
    federation_id: str = "default"
    master_url: str = ""
    public_url: str = ""
    legacy_base_url: str = ""
    display_name: str = ""
    shared_secret: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id must not be empty")
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}, not {self.role!r}")

    @property
    def endpoint(self) -> str:
        """Own reachable URL: public_url, or base_url on a master/standalone node."""
        if self.public_url:
            return self.public_url
        return "" if self.role == "host" else self.legacy_base_url

    @property
    def coordinator_endpoint(self) -> str:
        if self.role == "master":
            return self.endpoint
        return self.master_url if self.role == "host" else ""

    @property
    def heartbeat_ready(self) -> bool:
        return self.role == "host" and self.enabled and bool(self.master_url)

    def heartbeat_payload(self, *, instance_id: str) -> dict[str, object]:
        """Legacy heartbeat body plus additive shared-node fields (ignored by old masters)."""
        from .capabilities import PROTOCOL_VERSIONS, capabilities_for_role

        return {
            "node_id": self.node_id,
            "display_name": self.display_name,
            "role": self.role,
            "base_url": self.public_url or self.legacy_base_url,
            "sync_on_connect": self.sync_on_connect,
            "is_enabled": self.enabled,
            "instance_id": instance_id,
            "federation_id": self.federation_id,
            "protocol_versions": [f"{major}.{minor}" for major, minor in PROTOCOL_VERSIONS],
            "capabilities": [f"{name}@{major}.{minor}" for name, (major, minor) in capabilities_for_role(self.role)],
        }
