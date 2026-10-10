"""Framework-free node/sync adapter between ki-knowledge and the shared ``ki-node-core``.

Nothing here imports Django or knowledge models: Django code builds a
:class:`NodeSettings` and uses :class:`SyncClient` for all outgoing sync requests.
``ki-node-core`` is optional (extra ``node``); only :func:`to_descriptor` needs it.
See doc/distributed-collaboration-plan.md, section "Gemeinsame Node-Basis".
"""

from .capabilities import CAPABILITIES, PROTOCOL_VERSIONS, capabilities_for_role
from .client import SyncClient
from .descriptor import INSTANCE_ID, describe, node_core_available, to_descriptor
from .settings import NodeSettings, new_operation_id

__all__ = [
    "CAPABILITIES",
    "INSTANCE_ID",
    "PROTOCOL_VERSIONS",
    "NodeSettings",
    "SyncClient",
    "capabilities_for_role",
    "describe",
    "new_operation_id",
    "node_core_available",
    "to_descriptor",
]
